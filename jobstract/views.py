from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
import logging
from datetime import datetime
from .models import Opportunity, Employer, JobApplication, ApplicationEvent
from .serializers import (
    OpportunitySerializer, EmployerSerializer,
    JobApplicationSerializer, ApplicationEventSerializer
)
from cv_writer.models import CvWriter, Skill, Experience, Education
from django.db import models

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class OpportunityViewSet(viewsets.ModelViewSet):
    queryset = Opportunity.objects.all().select_related('employer')
    serializer_class = OpportunitySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['mode', 'time_commitment', 'experience_level', 'opportunity_type', 'location']
    ordering_fields = ['created_at', 'date_posted']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Optionally restricts the returned opportunities,
        by filtering against query parameters in the URL.
        """
        queryset = super().get_queryset()

        # Get query parameters
        opportunity_type = self.request.query_params.get('opportunity_type', None)
        mode = self.request.query_params.get('mode', None)
        time_commitment = self.request.query_params.get('time_commitment', None)
        experience_level = self.request.query_params.get('experience_level', None)
        location = self.request.query_params.get('location', None)
        ordering = self.request.query_params.get('ordering', None)

        # Apply filters
        if opportunity_type:
            queryset = queryset.filter(opportunity_type=opportunity_type)
        if mode:
            queryset = queryset.filter(mode=mode)
        if time_commitment:
            queryset = queryset.filter(time_commitment=time_commitment)
        if experience_level:
            queryset = queryset.filter(experience_level=experience_level)
        if location:
            queryset = queryset.filter(location__icontains=location)
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset 

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated])
    def recommended(self, request):
        """Get job recommendations based on user's CV and preferences."""
        import traceback
        
        try:
            # Detailed logging of user and request context
            logger.info(f"Recommendation Request - User: {request.user.username}")
            logger.info(f"User ID: {request.user.id}")

            # Get user's primary CV or the most recent CV
            try:
                # First try to get the primary CV
                cv_queryset = CvWriter.objects.filter(user=request.user)
                logger.info(f"Total CVs found for user: {cv_queryset.count()}")
                
                cv = cv_queryset.filter(is_primary=True).first()
                
                # If no primary CV, get the most recent CV
                if not cv:
                    cv = cv_queryset.order_by('-created_at').first()
                
                if not cv:
                    logger.warning(f"No CV found for user {request.user.username}")
                    return Response(
                        {"detail": "Please create a CV to get personalized job recommendations."},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                logger.info(f"Using CV: {cv} for recommendations")
            except Exception as cv_error:
                logger.error(f"CV Retrieval Error: {cv_error}")
                logger.error(traceback.format_exc())
                return Response(
                    {"detail": "Error retrieving your CV. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Get user's skills with detailed logging
            try:
                user_skills = set(
                    skill.skill_name.lower() 
                    for skill in Skill.objects.filter(user=request.user)
                )
                logger.info(f"Found {len(user_skills)} skills for user: {user_skills}")
            except Exception as skill_error:
                logger.error(f"Skill Retrieval Error: {skill_error}")
                logger.error(traceback.format_exc())
                user_skills = set()

            # Get user's experience level from most recent experience
            try:
                latest_experience = (
                    Experience.objects
                    .filter(user=request.user)
                    .order_by('-end_date', '-start_date')
                    .first()
                )
                experience_level = 'entry_level'  # Default
                
                if latest_experience:
                    logger.info(f"Latest experience: {latest_experience.job_title}")
                    # Calculate years of experience
                    years_of_experience = 0
                    if latest_experience.start_date:
                        from datetime import date
                        years_of_experience = (date.today() - latest_experience.start_date).days / 365.25
                    
                    if years_of_experience > 5:
                        experience_level = 'senior'
                    elif years_of_experience > 2:
                        experience_level = 'mid'
                    else:
                        experience_level = 'entry_level'
                    
                    logger.info(f"Calculated Experience Level: {experience_level} (Years: {years_of_experience:.2f})")
                else:
                    logger.warning("No experience found for user")
            except Exception as exp_error:
                logger.error(f"Experience Retrieval Error: {exp_error}")
                logger.error(traceback.format_exc())
                experience_level = 'entry_level'

            # Base queryset with skill and experience matching
            try:
                queryset = Opportunity.objects.filter(
                    opportunity_type='job'
                ).select_related('employer')
                
                logger.info(f"Total job opportunities before filtering: {queryset.count()}")
                
                # Skill-based filtering
                if user_skills:
                    # Create a Q object to check for each skill
                    skill_query = models.Q()
                    for skill in user_skills:
                        skill_query |= models.Q(skills_required__icontains=skill) | \
                                       models.Q(skills_gained__icontains=skill)
                    
                    skill_matched_jobs = queryset.filter(skill_query)
                    
                    if skill_matched_jobs.exists():
                        queryset = skill_matched_jobs
                        logger.info(f"Skill-matched jobs: {queryset.count()}")
                
                # Experience level filtering
                queryset = queryset.filter(
                    experience_level__icontains=experience_level
                )
                
                logger.info(f"Jobs after experience level filtering: {queryset.count()}")

                # Limit recommendations
                queryset = queryset[:20]  # Limit to 20 recommendations
                logger.info(f"Final recommendations count: {queryset.count()}")
                
                # Serialize and return
                serializer = self.get_serializer(queryset, many=True)
                return Response(serializer.data)
            
            except Exception as query_error:
                logger.error(f"Query Processing Error: {query_error}")
                logger.error(traceback.format_exc())
                return Response(
                    {"detail": "Error processing job recommendations."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Unexpected error in recommendations: {e}")
            logger.error(traceback.format_exc())
            return Response(
                {"detail": "An unexpected error occurred while fetching recommendations."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated])
    def apply(self, request, pk=None):
        """Apply to a job opportunity."""
        opportunity = self.get_object()
        user = request.user

        # Check if already applied
        if JobApplication.objects.filter(user=user, opportunity=opportunity).exists():
            return Response(
                {"detail": "You have already applied to this opportunity."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the latest CV
        cv = CvWriter.objects.filter(user=user).order_by('-updated_at').first()
        if not cv:
            return Response(
                {"detail": "Please create a CV before applying."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create application
        application = JobApplication.objects.create(
            user=user,
            opportunity=opportunity,
            cv_used=cv,
            cover_letter=request.data.get('cover_letter', '')
        )

        # Create application event
        ApplicationEvent.objects.create(
            application=application,
            event_type='status_change',
            event_date=datetime.now(),
            description='Application submitted'
        )

        serializer = JobApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class JobApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['applied_date', 'next_follow_up']
    ordering = ['-applied_date']

    def get_queryset(self):
        return JobApplication.objects.filter(
            user=self.request.user
        ).select_related(
            'opportunity', 'opportunity__employer', 'cv_used'
        ).prefetch_related('events')

    @action(detail=True, methods=['POST'])
    def add_event(self, request, pk=None):
        """Add a new event to the application."""
        application = self.get_object()
        
        serializer = ApplicationEventSerializer(data={
            **request.data,
            'application': application.id,
            'event_date': datetime.now()
        })
        
        if serializer.is_valid():
            event = serializer.save()
            
            # Update application status if it's a status change event
            if event.event_type == 'status_change':
                new_status = request.data.get('new_status')
                if new_status and new_status in dict(JobApplication.STATUS_CHOICES):
                    application.status = new_status
                    application.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['POST'])
    def update_status(self, request, pk=None):
        """Update application status and create a status change event."""
        application = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status or new_status not in dict(JobApplication.STATUS_CHOICES):
            return Response(
                {"detail": "Invalid status provided."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status
        application.status = new_status
        application.save()
        
        # Create status change event
        ApplicationEvent.objects.create(
            application=application,
            event_type='status_change',
            event_date=datetime.now(),
            description=f'Status updated to {application.get_status_display()}'
        )
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)

class EmployerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Employer.objects.all()
    serializer_class = EmployerSerializer

def home(request):
    """Render the home page template"""
    return render(request, 'jobstract/index.html')