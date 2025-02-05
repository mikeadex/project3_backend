from tokenize import Pointfloat
from django.shortcuts import render
from django.views.generic.edit import model_forms
from django.core.mail import send_mail

from rest_framework import (
    generics, 
    status, 
    views as rest_views,
)
from rest_framework.permissions import (
    IsAuthenticated, 
    AllowAny
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.decorators import api_view, permission_classes

from .models import (
    CvWriter,
    Education,
    Experience,
    ProfessionalSummary,
    Interest,
    Skill,
    Language,
    Certification,
    Reference,
    SocialMedia,
    CVImprovement,
)
from .serializers import (
    CvWriterSerializer,
    EducationSerializer,
    ExperienceSerializer,
    ProfessionalSummarySerializer,
    InterestSummarySerializer,
    SkillSerializer,
    LanguageSerializer,
    CertificationSerializer,
    ReferenceSerializer,
    SocialMediaSerializer,
    CVImprovementSerializer,
    CVVersionSerializer
)
from .services import CVImprovementService
from .local_llm import LocalLLMService
from django.db.models import Q
import logging
logger = logging.getLogger(__name__)

cv_improvement_service = CVImprovementService()

"""
I created a BaseListCreateAPIView class that inherits from generics.ListCreateAPIView to handle repeated part of the logic. This make my code DRY, reusable and reduce redudancy
"""


class BaseListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return self.model.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BaseRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        return self.model.objects.filter(user=user)


class CvWriterListCreate(BaseListCreateAPIView):
    """Endpoints for listing and creating CVs for the authenticated user."""
    serializer_class = CvWriterSerializer
    queryset = CvWriter.objects.all()
    model = CvWriter

    def perform_create(self, serializer):
        # Check if user already has a CV
        try:
            existing_cv = CvWriter.objects.get(user=self.request.user)
            # Update existing CV
            for attr, value in serializer.validated_data.items():
                setattr(existing_cv, attr, value)
            existing_cv.save()
        except CvWriter.DoesNotExist:
            # Create new CV
            serializer.save(user=self.request.user)


class CvWriterDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = CvWriterSerializer
    model = CvWriter


class ProfessionalSummaryListCreate(BaseListCreateAPIView):
    serializer_class = ProfessionalSummarySerializer
    queryset = ProfessionalSummary.objects.all()
    model = ProfessionalSummary

class ProfessionalSummaryDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = ProfessionalSummarySerializer
    model = ProfessionalSummary

class InterestListCreate(BaseListCreateAPIView):
    serializer_class = InterestSummarySerializer
    queryset = Interest.objects.all()
    model = Interest


class InterestDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = InterestSummarySerializer
    model = Interest


class EducationListCreate(BaseListCreateAPIView):
    serializer_class = EducationSerializer
    queryset = Education.objects.all()
    model = Education


class EducationDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = EducationSerializer
    model = Education


class ExperienceListCreate(BaseListCreateAPIView):
    serializer_class = ExperienceSerializer
    queryset = Experience.objects.all()
    model = Experience


class ExperienceDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = ExperienceSerializer
    model = Experience


class CertificationListCreate(BaseListCreateAPIView):
    serializer_class = CertificationSerializer
    queryset = Certification.objects.all()
    model = Certification


class CertificationDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = CertificationSerializer
    model = Certification


class SkillListCreate(BaseListCreateAPIView):
    serializer_class = SkillSerializer
    queryset = Skill.objects.all()
    model = Skill


class SkillDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = SkillSerializer
    model = Skill


class LanguageListCreate(BaseListCreateAPIView):
    serializer_class = LanguageSerializer
    queryset = Language.objects.all()
    model = Language


class LanguageDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = LanguageSerializer
    model = Language


class ReferenceListCreate(BaseListCreateAPIView):
    serializer_class = ReferenceSerializer
    queryset = Reference.objects.all()
    model = Reference


class ReferenceDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = ReferenceSerializer
    model = Reference


class SocialMediaListCreate(BaseListCreateAPIView):
    serializer_class = SocialMediaSerializer
    queryset = SocialMedia.objects.all()
    model = SocialMedia


class SocialMediaDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = SocialMediaSerializer
    model = SocialMedia


class CVListCreateView(ListCreateAPIView):
    queryset = CvWriter.objects.all()
    serializer_class = CvWriterSerializer

class CVRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = CvWriter.objects.all()
    serializer_class = CvWriterSerializer

class EducationListCreateView(ListCreateAPIView):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer

class EducationRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer

class ExperienceListCreateView(ListCreateAPIView):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer

class ExperienceRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer

class SkillListCreateView(ListCreateAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer

class SkillRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer

class CertificationListCreateView(ListCreateAPIView):
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer

class CertificationRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer


# Create your views here.
def cv_list(request):
    return render(request, "cv_list.html")


@api_view(['GET'])
@permission_classes([AllowAny])
def test_email(request):
    try:
        send_mail(
            'Test Email',
            'This is a test email from your Django application.',
            'noreply@myserviceplug.com',  # Must match DEFAULT_FROM_EMAIL
            ['creativemike21@gmail.com'],  # Replace with your email
            fail_silently=False,
        )
        return Response({'message': 'Test email sent successfully!'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def improve_cv(request, cv_id):
    """
    Improve CV content using AI.
    """
    try:
        # Check if CV belongs to user
        cv = CvWriter.objects.get(id=cv_id, user=request.user)
        
        # Get improvements
        import asyncio
        result = asyncio.run(cv_improvement_service.improve_cv(cv_id))
        
        if result['status'] == 'success':
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
    except CvWriter.DoesNotExist:
        return Response(
            {'error': 'CV not found or access denied'},
            status=status.HTTP_404_NOT_FOUND
        )
    except FileNotFoundError as e:
        return Response(
            {
                'error': str(e),
                'details': 'The AI model file is not available. Please contact support.'
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        error_message = str(e)
        if 'LLAMA_MODEL_PATH' in error_message or 'model' in error_message.lower():
            return Response(
                {
                    'error': 'AI service temporarily unavailable',
                    'details': 'The CV improvement service is currently unavailable. Your CV has been saved and you can try improving it later.'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(
            {
                'error': 'An unexpected error occurred',
                'details': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def improve_section(request):
    """
    Improve a specific CV section.
    """
    try:
        section = request.data.get('section')
        content = request.data.get('content')
        cv_id = request.data.get('cv_id')
        
        if not all([section, content]):
            return Response(
                {'error': 'Missing required fields. Please provide section and content.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        print(f"Improving section: {section}")
        print(f"Content: {content}")
        
        try:
            llm_service = LocalLLMService()
            result = llm_service.improve_section(section, content)
            
            # Save improvement to database if cv_id is provided
            if cv_id:
                try:
                    cv = CvWriter.objects.get(id=cv_id, user=request.user)
                    CVImprovement.objects.create(
                        cv=cv,
                        section=section,
                        original_content=content,
                        improved_content=result['improved'],
                        status='completed'
                    )
                except CvWriter.DoesNotExist:
                    # Don't fail if CV doesn't exist, just don't save the improvement
                    pass
            
            return Response({
                'status': 'success',
                'improved': result['improved'],
                'original': content
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in LLM service: {str(e)}")
            return Response(
                {'error': f'Failed to improve section: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        print(f"Unexpected error in improve_section: {str(e)}")
        return Response(
            {'error': f'Unexpected error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def improve_summary(request):
    """
    Real-time improvement of professional summary using local LLM.
    """
    try:
        summary = request.data.get('summary')
        if not summary:
            return Response(
                {'error': 'No summary provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"Received summary for improvement: {summary[:100]}...")
        
        # Import the correct LLM service
        from jobstract.services.local_llm import improve_summary as llm_improve_summary
        
        # Improve summary
        try:
            print("Starting summary improvement...")
            improved_summary = llm_improve_summary(summary)
            
            print(f"Improvement result: {improved_summary}")
            
            if not improved_summary or improved_summary == summary:
                return Response({
                    'status': 'warning',
                    'original': summary,
                    'improved': summary
                }, status=status.HTTP_200_OK)
            
            return Response({
                'status': 'success',
                'original': summary,
                'improved': improved_summary
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            print(f"Error during summary improvement: {str(e)}")
            return Response(
                {'error': f'Failed to improve summary: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        print(f"Unexpected error in improve_summary view: {str(e)}")
        return Response(
            {'error': f'Unexpected error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rewrite_cv(request):
    """
    Rewrite the entire CV to be more professional and impactful.
    """
    try:
        cv_data = request.data.get('cv_data')
        if not cv_data:
            return Response(
                {'error': 'No CV data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print("Received CV data for rewriting")
        
        try:
            llm_service = LocalLLMService()
            print("LLM service initialized successfully")
        except Exception as e:
            print(f"Failed to initialize LLM service: {str(e)}")
            return Response(
                {'error': f'Failed to initialize LLM service: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            print("Starting CV rewrite...")
            import threading
            import queue
            
            def rewrite_in_thread(q):
                try:
                    result = llm_service.rewrite_cv(cv_data)
                    q.put(('success', result))
                except Exception as e:
                    q.put(('error', str(e)))
            
            # Create a queue for the result
            result_queue = queue.Queue()
            
            # Start the rewrite in a separate thread
            rewrite_thread = threading.Thread(
                target=rewrite_in_thread, 
                args=(result_queue,)
            )
            rewrite_thread.daemon = True
            rewrite_thread.start()
            
            # Wait for the result with timeout
            try:
                status_type, result = result_queue.get(timeout=180)  # 3-minute timeout
                
                if status_type == 'error':
                    raise Exception(result)
                
                print("CV rewrite completed successfully")
                
                # Save the rewritten CV to the database
                cv = CvWriter.objects.create(
                    user=request.user,
                    title=cv_data.get('title', 'Rewritten CV'),
                    content=result['rewritten'],
                    original_content=result['original'],
                    status='completed'
                )
                
                return Response({
                    'status': 'success',
                    'cv_id': cv.id,
                    'original': result['original'],
                    'rewritten': result['rewritten'],
                    'message': 'CV has been rewritten and saved'
                }, status=status.HTTP_200_OK)
                
            except queue.Empty:
                print("Operation timed out")
                return Response(
                    {'error': 'The operation took too long to complete. Please try again.'},
                    status=status.HTTP_504_GATEWAY_TIMEOUT
                )
            
        except Exception as e:
            print(f"Error during CV rewrite: {str(e)}")
            return Response(
                {'error': f'Failed to rewrite CV: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        print(f"Unexpected error in rewrite_cv view: {str(e)}")
        return Response(
            {'error': f'Unexpected error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cv_improvements(request, cv_id):
    """
    Get improvement history for a CV.
    """
    try:
        # Check if CV belongs to user
        cv = CvWriter.objects.get(id=cv_id, user=request.user)
        
        # Get improvements
        improvements = CVImprovement.objects.filter(cv=cv)
        serializer = CVImprovementSerializer(improvements, many=True)
        
        return Response({
            'status': 'success',
            'improvements': serializer.data
        }, status=status.HTTP_200_OK)
            
    except CvWriter.DoesNotExist:
        return Response(
            {'error': 'CV not found or access denied'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cv(request, cv_id):
    """
    Get a CV by ID with all its related data.
    """
    try:
        # Get CV and check ownership
        cv = CvWriter.objects.get(id=cv_id, user=request.user)
        
        # Get all related data
        professional_summary = ProfessionalSummary.objects.filter(user=request.user).first()
        experiences = Experience.objects.filter(user=request.user).order_by('-start_date')
        education = Education.objects.filter(user=request.user).order_by('-start_date')
        
        # Get and log skills data
        raw_skills = Skill.objects.filter(user=request.user)
        print("\nSkills Debug:")
        print("1. Raw skills from DB:")
        for skill in raw_skills:
            print(f"  - {skill.skill_name} ({skill.skill_level})")
        
        skills = raw_skills.exclude(
            Q(skill_name__isnull=True) | Q(skill_name='') |
            Q(skill_level__isnull=True) | Q(skill_level='')
        )
        print("\n2. Filtered skills:")
        for skill in skills:
            print(f"  - {skill.skill_name} ({skill.skill_level})")
        
        serialized_skills = SkillSerializer(skills, many=True).data
        print("\n3. Serialized skills:")
        for skill in serialized_skills:
            print(f"  - {skill}")
        
        languages = Language.objects.filter(user=request.user)
        certifications = Certification.objects.filter(user=request.user)
        interests = Interest.objects.filter(user=request.user)
        social_media = SocialMedia.objects.filter(user=request.user)
        references = Reference.objects.filter(user=request.user)

        # Serialize CV data
        cv_data = CvWriterSerializer(cv).data
        
        # Add all related data
        response_data = {
            'professional_summary': ProfessionalSummarySerializer(professional_summary).data.get('summary') if professional_summary else None,
            'experiences': ExperienceSerializer(experiences, many=True).data,
            'education': EducationSerializer(education, many=True).data,
            'skills': serialized_skills,
            'languages': LanguageSerializer(languages, many=True).data,
            'certifications': CertificationSerializer(certifications, many=True).data,
            'interests': InterestSummarySerializer(interests, many=True).data,
            'social_media': SocialMediaSerializer(social_media, many=True).data,
            'references': ReferenceSerializer(references, many=True).data,
        }
        cv_data.update(response_data)
        
        print("\n4. Final response skills data:")
        print(f"  - {cv_data.get('skills')}")
        
        return Response(cv_data)
    except CvWriter.DoesNotExist:
        return Response({'error': 'CV not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CVVersionListCreateView(generics.ListCreateAPIView):
    serializer_class = CVVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            # Return all CV versions for the current user, sorted by primary first
            queryset = CvWriter.objects.filter(user=self.request.user).order_by('-is_primary', '-created_at')
            logger.info(f"Fetching CV versions for user {self.request.user.username}. Count: {queryset.count()}")
            return queryset
        except Exception as e:
            logger.error(f"Error in get_queryset: {str(e)}", exc_info=True)
            raise

    def perform_create(self, serializer):
        try:
            # Ensure the CV version is created for the current user
            # Check if this is the first version for the user
            existing_versions = CvWriter.objects.filter(user=self.request.user).count()
            
            # If this is the first version, set it as primary
            is_primary = existing_versions == 0

            logger.info(f"Creating CV version for user {self.request.user.username}. Is Primary: {is_primary}")

            # If creating a new version, copy data from the primary version
            primary_version = CvWriter.objects.filter(user=self.request.user, is_primary=True).first()
            
            serializer.save(
                user=self.request.user, 
                is_primary=is_primary
            )
        except Exception as e:
            logger.error(f"Error in perform_create: {str(e)}", exc_info=True)
            raise

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in list method: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CVVersionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CVVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return CV versions for the current user
        return CvWriter.objects.filter(user=self.request.user).order_by('-is_primary', '-created_at')

class SetPrimaryVersionView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            # Find the version to set as primary
            version = get_object_or_404(CvWriter, pk=pk, user=request.user)
            
            # Unset primary for all other versions
            CvWriter.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
            
            # Set this version as primary
            version.is_primary = True
            version.save()
            
            # Serialize and return the updated version
            serializer = CVVersionSerializer(version, context={'request': request})
            return Response(serializer.data)
        
        except Exception as e:
            logger.error(f"Error setting primary version: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CloneCVVersionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            # Find the CV version to clone
            original_version = CvWriter.objects.get(pk=pk, user=request.user)
            
            # Create a clone
            cloned_version = original_version.clone()
            
            # Serialize and return the cloned version
            serializer = CVVersionSerializer(cloned_version, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except CvWriter.DoesNotExist:
            return Response({'error': 'Version not found'}, status=status.HTTP_404_NOT_FOUND)

class EditCVVersionView(generics.UpdateAPIView):
    """
    View to edit details of a specific CV version.
    Allows updating version name, purpose, and visibility.
    """
    serializer_class = CVVersionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Ensure users can only edit their own CV versions
        """
        return CvWriter.objects.filter(user=self.request.user)
    
    def update(self, request, *args, **kwargs):
        """
        Custom update method with enhanced error handling
        """
        try:
            # Validate input data
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            
            # Validate input data
            serializer.is_valid(raise_exception=True)
            
            # Perform the update
            self.perform_update(serializer)
            
            # Return updated version details
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except serializers.ValidationError as e:
            # Handle validation errors from serializer
            return Response(
                {'error': str(e.detail)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except CvWriter.DoesNotExist:
            # Handle case where version doesn't exist
            return Response(
                {'error': 'CV version not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        except Exception as e:
            # Catch any unexpected errors
            return Response(
                {'error': 'An unexpected error occurred while editing the version'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_update(self, serializer):
        """
        Custom update to add additional validation
        """
        # Prevent editing primary version's name or purpose
        instance = serializer.instance
        if instance.is_primary:
            # Only allow updating visibility for primary version
            allowed_fields = ['visibility']
            for field in list(serializer.validated_data.keys()):
                if field not in allowed_fields:
                    raise serializers.ValidationError({
                        'detail': 'Cannot modify the primary version\'s details except visibility.'
                    })
        
        # Save the updated version
        serializer.save()