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
        try:
            # Get user's CV
            try:
                cv = CvWriter.objects.get(user=request.user)
                logger.info(f"Found CV for user {request.user.username}")
            except CvWriter.DoesNotExist:
                logger.warning(f"No CV found for user {request.user.username}")
                return Response(
                    {"detail": "Please create a CV to get personalized job recommendations."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get user's skills
            user_skills = set(
                skill.skill_name.lower() 
                for skill in Skill.objects.filter(user=request.user)
            )
            logger.info(f"Found {len(user_skills)} skills for user: {user_skills}")

            # Get user's experience level from most recent experience
            latest_experience = (
                Experience.objects
                .filter(user=request.user)
                .order_by('-end_date', '-start_date')
                .first()
            )
            if latest_experience:
                logger.info(f"Latest experience: {latest_experience.job_title}")

            # Base queryset
            queryset = Opportunity.objects.filter(
                opportunity_type='job'
            ).select_related('employer')
            
            logger.info(f"Found {queryset.count()} total jobs")
            
            # Score and sort opportunities based on skills match
            scored_opportunities = []
            for opportunity in queryset:
                score = 0
                
                # Calculate skills match score
                if opportunity.skills_required or opportunity.skills_gained:
                    required_skills = set(s.strip().lower() for s in (opportunity.skills_required or '').split(',') if s.strip())
                    gained_skills = set(s.strip().lower() for s in (opportunity.skills_gained or '').split(',') if s.strip())
                    all_job_skills = required_skills.union(gained_skills)
                    
                    if all_job_skills and user_skills:
                        # Calculate skills match percentage
                        matching_skills = user_skills.intersection(all_job_skills)
                        skills_score = len(matching_skills) / len(all_job_skills)
                        
                        # Boost score if user has required skills
                        if required_skills:
                            required_skills_match = user_skills.intersection(required_skills)
                            if required_skills_match:
                                skills_score += (len(required_skills_match) / len(required_skills)) * 0.3
                        
                        score += skills_score
                        logger.info(f"Job {opportunity.title} - Skills score: {skills_score}, Matching skills: {matching_skills}")
                
                # Boost score for matching job title or similar role
                if latest_experience:
                    job_title = latest_experience.job_title.lower()
                    opportunity_title = opportunity.title.lower()
                    
                    # Exact title match
                    if job_title in opportunity_title or opportunity_title in job_title:
                        score += 0.3
                        logger.info(f"Job {opportunity.title} - Exact title match bonus")
                    # Partial title match (check for common words)
                    else:
                        job_words = set(job_title.split())
                        opp_words = set(opportunity_title.split())
                        common_words = job_words.intersection(opp_words)
                        if common_words:
                            title_bonus = 0.1 * (len(common_words) / len(opp_words))
                            score += title_bonus
                            logger.info(f"Job {opportunity.title} - Partial title match bonus: {title_bonus}")
                
                # Only include opportunities with a minimum score
                if score > 0.05:  # Lowered threshold to 5% for testing
                    scored_opportunities.append((opportunity, score))
                    logger.info(f"Job {opportunity.title} - Final score: {score}")
            
            logger.info(f"Found {len(scored_opportunities)} jobs above threshold")
            
            # Sort by score and get top matches
            scored_opportunities.sort(key=lambda x: x[1], reverse=True)
            recommended_opportunities = []
            
            for opportunity, score in scored_opportunities[:10]:
                # Convert score to percentage and normalize to max 100%
                normalized_score = min(score, 1.0)  # Cap at 100%
                opportunity.matching_score = round(normalized_score * 100, 1)
                recommended_opportunities.append(opportunity)
            
            logger.info(f"Returning {len(recommended_opportunities)} recommendations")
            
            serializer = OpportunitySerializer(recommended_opportunities, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in recommendations: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Error getting recommendations: {str(e)}"},
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