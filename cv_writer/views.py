from tokenize import Pointfloat
from django.shortcuts import render
from django.views.generic.edit import model_forms
from django.core.mail import send_mail
from django.http import Http404

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
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from asgiref.sync import sync_to_async, async_to_sync

# Import models
import logging
logger = logging.getLogger(__name__)

from .models import (
    CvWriter,
    Education,
    Experience, 
    ProfessionalSummary,
    Skill,
    Language,
    Certification,
    Interest,
    Reference,
    SocialMedia,
    CVImprovement,
    CVTemplate,
    CVTemplateSelection,
)

# Import from ai_cv_parser for rewrite session
from ai_cv_parser.models import CVRewriteSession

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
    CVVersionSerializer,
    CVTemplateSerializer,
    CVTemplateSelectionSerializer
)
from .services import CVImprovementService
# Conditional import for local LLM service
try:
    from .local_llm import ResilientLLMService
    LOCAL_LLM_AVAILABLE = True
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Local LLM service not available: {e}")
    ResilientLLMService = None
    LOCAL_LLM_AVAILABLE = False
from django.db.models import Q
import logging
from ai_cv_parser.services import CVRewriteService
from .services import DeepSeekAPIService

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
        result = cv_improvement_service.improve_cv(cv_id)
        
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
            if not LOCAL_LLM_AVAILABLE or not ResilientLLMService:
                return Response(
                    {'error': 'Local LLM service not available. This feature requires llama_cpp installation.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
            llm_service = ResilientLLMService()  # Updated
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
def improve_entire_cv(request):
    """
    Comprehensive CV improvement for all sections to make it ATS-ready and compelling.
    """
    try:
        cv_id = request.data.get('cv_id')
        if not cv_id:
            return Response({
                'error': 'CV ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the CV and check ownership
        try:
            cv = CvWriter.objects.get(id=cv_id, user=request.user)
        except CvWriter.DoesNotExist:
            return Response({
                'error': 'CV not found or access denied'
            }, status=status.HTTP_404_NOT_FOUND)
        
        improvements = {}
        
        # Use external API services directly - bypass local model entirely
        try:
            import httpx
            import os
            
            # Get API keys directly from environment
            deepseek_key = os.getenv('DEEPSEEK_API_KEY')
            mistral_key = os.getenv('MISTRAL_API_KEY') 
            groq_key = os.getenv('GROQ_API_KEY')
            
            if not any([deepseek_key, mistral_key, groq_key]):
                return Response({
                    'error': 'No AI API keys found. Please configure DEEPSEEK_API_KEY, MISTRAL_API_KEY, or GROQ_API_KEY.',
                    'details': 'Environment variables not loaded properly'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
            # Create a simple function to call AI APIs
            async def call_ai_api(prompt_text):
                try:
                    # Try DeepSeek first
                    if deepseek_key:
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                "https://api.deepseek.com/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {deepseek_key}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "model": "deepseek-chat",
                                    "messages": [{"role": "user", "content": prompt_text}],
                                    "max_tokens": 1000,
                                    "temperature": 0.7
                                },
                                timeout=30.0
                            )
                            if response.status_code == 200:
                                data = response.json()
                                return data["choices"][0]["message"]["content"]
                    
                    # Fallback to Groq
                    if groq_key:
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                "https://api.groq.com/openai/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {groq_key}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "model": "llama3-8b-8192",
                                    "messages": [{"role": "user", "content": prompt_text}],
                                    "max_tokens": 1000,
                                    "temperature": 0.7
                                },
                                timeout=30.0
                            )
                            if response.status_code == 200:
                                data = response.json()
                                return data["choices"][0]["message"]["content"]
                    
                    return None
                except Exception as e:
                    logger.error(f"Error calling AI API: {str(e)}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error setting up AI service: {str(e)}")
            return Response({
                'error': 'Failed to initialize AI service',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Improve Professional Summary
        try:
            professional_summary = ProfessionalSummary.objects.filter(user=request.user, cv=cv).first()
            if professional_summary and professional_summary.summary:
                
                # Create improvement prompt for professional summary
                prompt = f"""Transform this professional summary into an ATS-optimized, compelling statement.

REQUIREMENTS:
- Use powerful action verbs and industry keywords
- Quantify achievements where possible
- Show clear value proposition to employers
- Keep it concise (3-4 sentences)
- Make it sound confident and professional

Original summary: {professional_summary.summary}

Return ONLY the improved professional summary:"""
                
                result = async_to_sync(call_ai_api)(prompt)
                if result:
                    improvements['professional_summary'] = {
                        'original': professional_summary.summary,
                        'improved': result
                    }
        except Exception as e:
            logger.error(f"Error improving professional summary: {str(e)}")
        
        # Improve Work Experience
        try:
            experiences = Experience.objects.filter(user=request.user).order_by('-start_date')
            improved_experiences = []
            for exp in experiences:
                if exp.job_description:
                    
                    prompt = f"""Transform this job experience into compelling, ATS-optimized bullet points.

REQUIREMENTS:
- Start each bullet point with strong action verbs (Managed, Developed, Implemented, etc.)
- Quantify results where possible (percentages, numbers, timeframes)
- Focus on achievements, not just job duties
- Use industry-relevant keywords
- Make it compelling to recruiters
- Format as clean bullet points

Original experience: {exp.job_description}

Return ONLY the improved experience bullet points:"""
                    
                    result = async_to_sync(call_ai_api)(prompt)
                    if result:
                        improved_experiences.append({
                            'id': exp.id,
                            'job_title': exp.job_title,
                            'company_name': exp.company_name,
                            'original': exp.job_description,
                            'improved': result
                        })
            if improved_experiences:
                improvements['experiences'] = improved_experiences
        except Exception as e:
            logger.error(f"Error improving experiences: {str(e)}")
        
        # Improve Skills
        try:
            skills = Skill.objects.filter(user=request.user)
            if skills.exists():
                skills_text = ", ".join([f"{skill.skill_name} ({skill.skill_level})" for skill in skills])
                
                prompt = f"""Improve and organize these skills professionally for an accounting role.

REQUIREMENTS:
- Use industry-standard skill names for accounting
- Assign realistic proficiency levels: Beginner, Intermediate, Advanced, Expert
- Remove basic skills like "Number" and "Maths" 
- Add relevant accounting software and tools
- Focus on professional accounting skills
- NO asterisks, bullets, or special formatting

Original skills: {skills_text}

Return ONLY a comma-separated list like this:
Advanced Excel, Intermediate QuickBooks, Expert Financial Analysis, Advanced Tax Preparation, Intermediate SAP, Expert Bookkeeping, Advanced Financial Reporting, Intermediate Auditing"""
                
                result = async_to_sync(call_ai_api)(prompt)
                if result:
                    improvements['skills'] = {
                        'original': skills_text,
                        'improved': result
                    }
        except Exception as e:
            logger.error(f"Error improving skills: {str(e)}")
        
        # Improve Education
        try:
            education = Education.objects.filter(user=request.user).order_by('-start_date').first()
            if education:
                education_text = f"{education.degree} in {education.field_of_study} from {education.school_name}"
                if education.description:
                    education_text += f". {education.description}"
                    
                prompt = f"""Enhance this education section with proper professional formatting.

REQUIREMENTS:
- Use proper degree titles and formatting
- Include relevant coursework, honors, or achievements if applicable
- Add GPA if it's 3.5 or higher (make a reasonable assumption)
- Make it concise and professional

Original education: {education_text}

Return ONLY the improved education section:"""
                
                result = async_to_sync(call_ai_api)(prompt)
                if result:
                    improvements['education'] = {
                        'original': education_text,
                        'improved': result
                    }
        except Exception as e:
            logger.error(f"Error improving education: {str(e)}")
        
        if not improvements:
            return Response({
                'error': 'No content found to improve or all improvements failed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'status': 'success',
            'improvements': improvements,
            'message': f'Successfully improved {len(improvements)} sections'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in improve_entire_cv: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred during CV improvement',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_sample_contact_info(request):
    """
    Add sample contact information including LinkedIn and GitHub to the CV.
    This is a helper endpoint for testing.
    """
    try:
        cv_id = request.data.get('cv_id')
        if not cv_id:
            return Response({
                'error': 'CV ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the CV and check ownership
        try:
            cv = CvWriter.objects.get(id=cv_id, user=request.user)
        except CvWriter.DoesNotExist:
            return Response({
                'error': 'CV not found or access denied'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update CV with full address if missing
        if not cv.address:
            cv.address = "123 Professional Street, Business District"
            cv.save()
        
        # Add sample social media links if they don't exist
        sample_social_media = [
            {'platform': 'LinkedIn', 'url': 'https://linkedin.com/in/mike-adex'},
            {'platform': 'GitHub', 'url': 'https://github.com/mike-adex'},
            {'platform': 'Portfolio', 'url': 'https://mikeadex.com'}
        ]
        
        for social in sample_social_media:
            SocialMedia.objects.get_or_create(
                user=request.user,
                platform=social['platform'],
                defaults={'url': social['url'], 'cv': cv}
            )
        
        return Response({
            'status': 'success',
            'message': 'Sample contact information added successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error adding sample contact info: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_improvement(request):
    """
    Apply an AI improvement to a specific CV section.
    """
    try:
        cv_id = request.data.get('cv_id')
        section = request.data.get('section')
        improved_content = request.data.get('improved_content')
        
        if not all([cv_id, section, improved_content]):
            return Response({
                'error': 'Missing required fields: cv_id, section, improved_content'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the CV and check ownership
        try:
            cv = CvWriter.objects.get(id=cv_id, user=request.user)
        except CvWriter.DoesNotExist:
            return Response({
                'error': 'CV not found or access denied'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Apply improvement based on section type
        if section == 'professional_summary':
            # Update or create professional summary
            professional_summary, created = ProfessionalSummary.objects.get_or_create(
                user=request.user, 
                cv=cv,
                defaults={'summary': improved_content}
            )
            if not created:
                professional_summary.summary = improved_content
                professional_summary.save()
                
        elif section.startswith('experiences_'):
            # Extract experience ID from section name (e.g., 'experiences_0')
            try:
                exp_index = int(section.split('_')[1])
                experiences = Experience.objects.filter(user=request.user).order_by('-start_date')
                if exp_index < len(experiences):
                    experience = experiences[exp_index]
                    # COMPLETELY REPLACE - clear old content and set only improved content
                    experience.job_description = ""  # Clear old description
                    experience.achievements = improved_content  # Set improved content as achievements
                    experience.save()
            except (ValueError, IndexError):
                return Response({
                    'error': 'Invalid experience section format'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        elif section == 'skills':
            # Parse improved skills and replace all existing skills
            try:
                # Delete all existing skills for the user
                Skill.objects.filter(user=request.user).delete()
                
                # Parse the improved content (format: "Advanced Excel, Intermediate QuickBooks, ...")
                skills_list = [skill.strip() for skill in improved_content.split(',')]
                
                # Create new skills
                for skill_text in skills_list:
                    skill_text = skill_text.strip()
                    if skill_text:
                        # Extract proficiency level and skill name
                        # Expected format: "Advanced Excel" or "Intermediate QuickBooks"
                        words = skill_text.split()
                        if len(words) >= 2:
                            proficiency = words[0]  # First word is proficiency
                            skill_name = ' '.join(words[1:])  # Rest is skill name
                            
                            # Validate proficiency level
                            valid_levels = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
                            if proficiency not in valid_levels:
                                proficiency = 'Intermediate'  # Default fallback
                            
                            # Create new skill
                            Skill.objects.create(
                                user=request.user,
                                skill_name=skill_name,
                                skill_level=proficiency
                            )
                        else:
                            # If format doesn't match, create with default proficiency
                            Skill.objects.create(
                                user=request.user,
                                skill_name=skill_text,
                                skill_level='Intermediate'
                            )
            except Exception as e:
                logger.error(f"Error updating skills: {str(e)}")
                return Response({
                    'error': 'Failed to update skills',
                    'details': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
            
        elif section == 'education':
            # Update the first education record's description
            education = Education.objects.filter(user=request.user).order_by('-start_date').first()
            if education:
                education.description = improved_content
                education.save()
        
        return Response({
            'status': 'success',
            'message': f'Successfully applied improvement to {section}'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error applying improvement: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred while applying improvement',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def improve_summary(request):
    """
    Real-time improvement of professional summary using AI.
    
    Supports two improvement scenarios:
    1. Improving summary for an existing CV
    2. Improving a provided summary directly
    
    Request should contain either:
    - cv_id: ID of the CV to improve summary for
    - summary: Direct summary text to improve
    """
    try:
        # Extract parameters from request
        cv_id = request.data.get('cv_id')
        summary = request.data.get('summary')
        
        # Validate input
        if not cv_id and not summary:
            return Response({
                'error': 'Either cv_id or summary must be provided',
                'hint': 'Send either a cv_id to improve an existing CV summary, or a summary string to improve directly'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Scenario 1: Improve summary from CV
        if cv_id:
            try:
                cv = CvWriter.objects.get(id=cv_id, user=request.user)
                
                # Attempt to retrieve existing professional summary
                try:
                    professional_summary = ProfessionalSummary.objects.get(user=request.user, cv=cv)
                    summary = professional_summary.summary
                except ProfessionalSummary.DoesNotExist:
                    return Response({
                        'error': 'No professional summary found for this CV',
                        'status': 'no_summary'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            except CvWriter.DoesNotExist:
                return Response({
                    'error': f'CV with ID {cv_id} not found',
                    'status': 'cv_not_found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate summary is not empty
        if not summary or len(summary.strip()) < 10:
            return Response({
                'error': 'Summary is too short or empty',
                'hint': 'Provide a meaningful professional summary of at least 10 characters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Prepare improvement prompt
        improvement_prompt = f"""Improve this professional summary to make it more professional, impactful, and engaging. 

Requirements:
- Keep it concise (3-4 sentences maximum)
- Use strong action verbs and professional language
- Maintain all original information
- Make it sound more polished and confident
- Focus on value proposition to employers

Original summary:
{summary}

Return ONLY the improved summary text, nothing else:"""
        
        # Improve summary using AI service
        improvement_service = CVImprovementService()
        improved_summary = async_to_sync(improvement_service.primary_service.improve_text)(improvement_prompt)
        
        # Clean up the response to extract only the improved summary
        if improved_summary:
            # Remove common AI prefixes/suffixes and extract just the summary
            improved_summary = improved_summary.strip()
            
            # Remove common AI response patterns
            patterns_to_remove = [
                "Here is the improved summary:",
                "Here's the improved version:",
                "Improved summary:",
                "Enhanced summary:",
                "Professional summary:",
                "Of course. Here is the professionally enhanced text",
                "***",
                "**PROFESSIONALLY OPTIMIZED SUMMARY:**",
                "**Key Improvements:**",
                "IMPROVEMENT INSTRUCTIONS:",
                "OPTIMIZATION GUIDELINES:",
                "OBJECTIVE:",
                "Professional Summary Optimization Protocol"
            ]
            
            for pattern in patterns_to_remove:
                improved_summary = improved_summary.replace(pattern, "").strip()
            
            # If there are multiple paragraphs, take the first substantial one
            paragraphs = [p.strip() for p in improved_summary.split('\n\n') if p.strip()]
            if paragraphs:
                # Look for the actual improved summary (usually the first substantial paragraph)
                for paragraph in paragraphs:
                    # Skip meta text and find the actual summary
                    if (len(paragraph) > 50 and 
                        not paragraph.startswith(('*', '-', '>', 'Requirements:', 'Original summary:', 'ORIGINAL SUMMARY:')) and
                        not paragraph.upper().startswith(('OBJECTIVE', 'GUIDELINES', 'INSTRUCTIONS'))):
                        improved_summary = paragraph
                        break
                else:
                    # If no good paragraph found, use the first one
                    improved_summary = paragraphs[0]
            
            # Remove any remaining markdown or formatting
            improved_summary = improved_summary.replace('>', '').replace('*', '').strip()
            
            # Ensure it's not empty and not just the original
            if len(improved_summary) < 20 or improved_summary.lower() == summary.lower():
                improved_summary = None
        
        # If improvement fails, return original
        if not improved_summary:
            return Response({
                'status': 'partial_success',
                'original': summary,
                'improved': summary,
                'message': 'AI improvement unavailable. Original summary returned.'
            }, status=status.HTTP_200_OK)
        
        # Update professional summary if CV context exists
        if cv_id:
            try:
                professional_summary.summary = improved_summary
                professional_summary.save()
            except Exception as update_error:
                logger.warning(f"Could not update professional summary: {str(update_error)}")
        
        return Response({
            'status': 'success',
            'original': summary,
            'improved': improved_summary
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error in improve_summary: {str(e)}")
        return Response({
            'error': 'An unexpected error occurred during summary improvement',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rewrite_cv(request):
    """
    Rewrite and improve CV content using a dual-layer approach:
    1. DeepSeek AI for initial rewrite
    2. LLaMA API for evaluation and enhancement
    """
    try:
        # Import required models and services
        from ai_cv_parser.models import CVRewriteSession
        from ai_cv_parser.services import CVRewriteService
        from ai_cv_parser.deepseek_service import DeepSeekService
        from cv_writer.services import CVImprovementService
        
        cv_data = request.data.get('cv_data')
        if not cv_data:
            return Response(
                {'error': 'CV data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create a rewrite session to track progress
        rewrite_session = CVRewriteSession.objects.create(
            user=request.user,
            cv_id=cv_data.get('cv_id'),
            status='processing',
            input_data=cv_data
        )

        # Create a thread to process the CV rewrite in the background
        # This allows us to immediately return a response and update the session as processing continues
        import threading
        
        def process_rewrite_in_background(session_id, cv_data, user_id):
            try:
                from django.contrib.auth import get_user_model
                from django.db import connection
                import json
                import time
                
                # Create a new database connection for this thread
                connection.close()
                
                # Get the user and session
                User = get_user_model()
                user = User.objects.get(id=user_id)
                session = CVRewriteSession.objects.get(id=session_id)
                
                # Extract proper CV data structure
                # If we have parsed_cv with parsed_data, use that structure
                if 'parsed_cv' in cv_data and 'parsed_data' in cv_data['parsed_cv']:
                    processed_cv_data = cv_data['parsed_cv']['parsed_data']
                    logger.info(f"Extracted CV data from parsed_cv.parsed_data with keys: {list(processed_cv_data.keys())}")
                else:
                    processed_cv_data = cv_data
                    logger.info(f"Using original cv_data structure with keys: {list(cv_data.keys())}")
                
                # Debug log the actual CV data
                try:
                    import json
                    logger.info(f"PROCESSED CV DATA: {json.dumps(processed_cv_data, indent=2)[:1000]}...")
                except Exception as e:
                    logger.error(f"Error logging processed CV data: {str(e)}")
                
                # Update session to mark start of first stage - CV Data Analysis
                session.status = 'processing'
                session.result = {
                    'status': 'processing',
                    'current_stage': 1,
                    'message': 'Analyzing CV Data',
                    'progress': 20
                }
                session.save()
                
                # Allow some time for the frontend to show the first stage
                time.sleep(1)
                
                # STAGE 1: Initial Analysis - DeepSeek
                try:
                    # Update session for stage 1 completion
                    session.result = {
                        'status': 'processing',
                        'current_stage': 2,
                        'message': 'Enhancing language with DeepSeek AI',
                        'progress': 40
                    }
                    session.save()
                    
                    # Process initial rewrite with DeepSeek
                    cv_rewrite_service = CVRewriteService(deepseek_service=DeepSeekService())
                    initial_result = cv_rewrite_service.rewrite_cv_sync(processed_cv_data, user)
                    
                    # Log the structure of the initial result for debugging
                    logger.info(f"Initial rewrite structure: {list(initial_result.keys())}")
                    logger.info(f"Initial result status: {initial_result.get('status')}")
                    
                    # Add a direct enhancement using LLaMA - bypass DeepSeek if it didn't work
                    if not initial_result.get('rewritten_cv') and not initial_result.get('improved_sections'):
                        logger.warning("DeepSeek rewrite didn't produce usable output, enhancing original CV directly with LLaMA")
                        
                        # Initialize the CV improvement service
                        cv_improvement_service = CVImprovementService()
                        
                        # Create a direct enhancement of the original CV
                        direct_enhancement = {
                            'status': 'success',
                            'message': 'Direct enhancement with LLaMA',
                            'rewritten_cv': processed_cv_data,  # Start with original
                            'new_cv_id': initial_result.get('new_cv_id')
                        }
                        
                        # Update initial result for compatibility
                        initial_result['rewritten_cv'] = processed_cv_data
                    else:
                        # Structure the data correctly for the next step
                        # Make sure initial_result has a 'rewritten_cv' key for the enhancement service
                        if 'improved_sections' in initial_result and not 'rewritten_cv' in initial_result:
                            initial_result['rewritten_cv'] = initial_result['improved_sections']
                            logger.info(f"Copied improved_sections to rewritten_cv for compatibility")
                        elif not 'rewritten_cv' in initial_result and not 'improved_sections' in initial_result:
                            # Create a minimal structure to avoid errors
                            logger.warning(f"Neither rewritten_cv nor improved_sections found in initial_result")
                            initial_result['rewritten_cv'] = processed_cv_data
                            logger.info(f"Created fallback rewritten_cv from original cv_data")
                    
                    # STAGE 2: Professional Language Enhancement with DeepSeek complete
                    # Update session to mark start of stage 3 - Content Optimization
                    session.result = {
                        'status': 'processing',
                        'current_stage': 3,
                        'message': 'Optimizing content structure',
                        'progress': 60
                    }
                    session.save()
                    
                    # Allow some time to display the third stage
                    time.sleep(1)
                    
                    # STAGE 3: Content Optimization - LLaMA enhancement
                    cv_improvement_service = CVImprovementService()
                    
                    # Enhance the initial result using LLaMA
                    import asyncio
                    import inspect
                    
                    if inspect.iscoroutinefunction(cv_improvement_service.enhance_rewrite):
                        # If it's async, we need to run it in an event loop
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            enhanced_result = loop.run_until_complete(cv_improvement_service.enhance_rewrite(initial_result, user))
                        finally:
                            loop.close()
                    else:
                        # If it's a regular function, just call it normally
                        enhanced_result = cv_improvement_service.enhance_rewrite(initial_result, user)
                    
                    # STAGE 4: ATS Compatibility - Final touches
                    session.result = {
                        'status': 'processing',
                        'current_stage': 4,
                        'message': 'Finalizing ATS compatibility',
                        'progress': 80
                    }
                    session.save()
                    
                    # Allow time to display the fourth stage
                    time.sleep(1)
                    
                    # Combine results and finalize
                    final_result = {
                        'status': 'completed',
                        'session_id': str(session.id),
                        'message': 'CV successfully rewritten',
                        'progress': 100,
                        'initial_rewrite': initial_result,
                        'enhanced_rewrite': enhanced_result,
                        'new_cv_id': enhanced_result.get('new_cv_id') or initial_result.get('new_cv_id')
                    }
                    
                    # Make sure we have rewritten CV data in the final result
                    rewritten_cv = enhanced_result.get('rewritten_cv', {})
                    if not rewritten_cv:
                        # If enhanced result has no rewritten CV, try to get it from initial result
                        rewritten_cv = initial_result.get('rewritten_cv', {})
                        if not rewritten_cv and 'improved_sections' in initial_result:
                            rewritten_cv = initial_result.get('improved_sections', {})
                            
                    # If we still don't have rewritten CV data, use the processed original
                    if not rewritten_cv:
                        logger.warning("No rewritten CV data found in results, using processed original")
                        rewritten_cv = processed_cv_data
                    
                    # Add the rewritten CV to the final result
                    final_result['rewritten_cv'] = rewritten_cv
                    
                    # Log the original CV and rewritten CV for comparison
                    try:
                        # Create a formatted comparison log
                        import json
                        
                        # Format original CV data
                        original_cv_json = json.dumps(processed_cv_data, indent=2)
                        
                        # Format rewritten CV data
                        rewritten_cv_json = json.dumps(enhanced_result.get('rewritten_cv', {}), indent=2)
                        
                        # Log the comparison
                        logger.info(f"CV Rewrite Comparison for Session {session.id}:")
                        logger.info(f"Original CV:\n{original_cv_json}")
                        logger.info(f"Rewritten CV:\n{rewritten_cv_json}")
                        
                        # Add the original data to the session result for comparison
                        final_result['original_cv'] = processed_cv_data
                    except Exception as log_error:
                        logger.error(f"Error logging CV comparison: {str(log_error)}")
                    
                    # Update session with completed status and results
                    session.status = 'completed'
                    session.result = final_result
                    
                    # Store the new CV ID in the session
                    new_cv_id = enhanced_result.get('new_cv_id') or initial_result.get('new_cv_id')
                    
                    # Save the rewritten CV data to the database
                    try:
                        from .services import save_rewritten_cv_to_database
                        rewritten_cv = save_rewritten_cv_to_database(final_result['rewritten_cv'], user)
                        
                        # Add the CV writer ID to the result
                        final_result['cv_writer_id'] = str(rewritten_cv.id)
                        session.result = final_result
                        
                        logger.info(f"Saved rewritten CV data to database tables with CV ID: {rewritten_cv.id}")
                    except Exception as save_error:
                        logger.error(f"Error saving rewritten CV to database tables: {str(save_error)}")
                        # Continue with the process, don't fail the entire request
                    
                    if new_cv_id:
                        final_result['new_cv_id'] = new_cv_id
                        
                    session.save()
                    
                except Exception as e:
                    logger.error(f"Error in CV rewrite process: {str(e)}", exc_info=True)
                    session.status = 'error'
                    session.result = {
                        'status': 'error',
                        'message': f'Error processing CV rewrite: {str(e)}',
                        'error': str(e)
                    }
                    session.save()
            
            except Exception as e:
                logger.error(f"Error in background rewrite thread: {str(e)}", exc_info=True)
                try:
                    session = CVRewriteSession.objects.get(id=session_id)
                    session.status = 'error'
                    session.result = {
                        'status': 'error',
                        'message': f'Error during CV rewrite: {str(e)}',
                        'error': str(e)
                    }
                    session.save()
                except Exception as inner_e:
                    logger.error(f"Failed to update session after error: {str(inner_e)}")
        
        # Launch the background processing thread
        thread = threading.Thread(
            target=process_rewrite_in_background,
            args=(rewrite_session.id, cv_data, request.user.id)
        )
        thread.daemon = True
        thread.start()
        
        # Immediately return a response with the session ID
        return Response({
            'session_id': str(rewrite_session.id),
            'status': 'processing',
            'message': 'CV rewrite initiated successfully',
            'current_stage': 1,
            'progress': 10
        }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        logger.error(f"Error in rewrite_cv view: {str(e)}", exc_info=True)
        return Response(
            {'error': f'Failed to rewrite CV: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_rewritten_cv(request):
    """
    Save a rewritten CV from an AI rewrite session to the CV writer database.
    
    This view handles the final step after CV rewriting where the user chooses
    to save the rewritten CV to their account for further editing and use.
    
    The request should include the session_id of the CV rewrite session and
    optionally updated personal info.
    """
    logger = logging.getLogger('cv_writer')
    try:
        # Extract the session ID from the request data
        session_id = request.data.get('session_id')
        personal_info = request.data.get('personal_info', {})
        
        # Log the request
        logger.info(f"Save rewritten CV request: session_id={session_id}, personal_info={personal_info}")
        
        if not session_id:
            return Response(
                {'error': 'Session ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the rewrite session by ID
        try:
            rewrite_session = CVRewriteSession.objects.get(id=session_id)
            logger.info(f"Found rewrite session: {session_id}, status: {rewrite_session.status}, new_cv_id: {rewrite_session.new_cv_id}")
        except CVRewriteSession.DoesNotExist:
            return Response(
                {'error': 'Rewrite session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if the session belongs to the requesting user
        if rewrite_session.user != request.user:
            return Response(
                {'error': 'You do not have permission to access this session'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if the session is completed
        if rewrite_session.status != 'completed':
            return Response(
                {'error': f'Rewrite session is not completed, current status: {rewrite_session.status}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if the session has a new CV ID already
        if not rewrite_session.new_cv_id:
            # If no new CV ID exists, try to create a new CV using session result
            from .services import save_rewritten_cv_to_database
            
            # Check if the result contains rewritten CV data
            session_result = rewrite_session.result
            if isinstance(session_result, dict) and 'rewritten_cv' in session_result:
                try:
                    logger.info(f"Creating new CV from rewrite session result")
                    cv_writer_instance = save_rewritten_cv_to_database(session_result['rewritten_cv'], request.user)
                    
                    # Update the rewrite session with the new CV ID
                    rewrite_session.new_cv_id = cv_writer_instance.id
                    rewrite_session.save()
                    
                    logger.info(f"Created new CV with ID: {cv_writer_instance.id}")
                    
                    # Continue with the existing CV now that we've created one
                    new_cv = cv_writer_instance
                except Exception as e:
                    logger.error(f"Error creating new CV: {str(e)}", exc_info=True)
                    return Response(
                        {'error': f'Could not create a new CV from rewrite data: {str(e)}'}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                logger.error(f"Rewrite session does not have rewritten_cv data in result: {session_result}")
                return Response(
                    {'error': 'Rewrite session does not have a new CV ID and no rewritten CV data available'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Get the CV by ID
            try:
                new_cv = CvWriter.objects.get(id=rewrite_session.new_cv_id)
            except CvWriter.DoesNotExist:
                return Response(
                    {'error': 'Could not find the rewritten CV. It may have been deleted.'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
        # Make sure the CV belongs to the requesting user
        if new_cv.user != request.user:
            return Response(
                {'error': 'You do not have permission to access this CV'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update the CV with personal info if provided
        if personal_info:
            # Extract name fields
            if personal_info.get('name'):
                name_parts = personal_info['name'].split(' ', 1)
                if len(name_parts) > 0:
                    new_cv.first_name = name_parts[0]
                if len(name_parts) > 1:
                    new_cv.last_name = name_parts[1]
            else:
                # Try individual name fields
                if personal_info.get('first_name'):
                    new_cv.first_name = personal_info['first_name']
                if personal_info.get('last_name'):
                    new_cv.last_name = personal_info['last_name']
            
            # Update contact info - skip email as it's not in the model
            if personal_info.get('phone') or personal_info.get('contact_number'):
                new_cv.contact_number = personal_info.get('phone') or personal_info.get('contact_number')
            
            # Update location info
            if personal_info.get('address'):
                new_cv.address = personal_info['address']
            if personal_info.get('city'):
                new_cv.city = personal_info['city']
            if personal_info.get('country'):
                new_cv.country = personal_info['country']
            
            # Update job title/CV title if provided
            if personal_info.get('title') or personal_info.get('job_title'):
                new_cv.title = personal_info.get('job_title') or personal_info.get('title') or new_cv.title
            
            # Save the updated CV
            new_cv.save()
            
        # Return the CV ID for redirection
        return Response({
            'message': 'Rewritten CV saved successfully',
            'cv_id': new_cv.id
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger = logging.getLogger('cv_writer')
        logger.error(f"Error saving rewritten CV: {str(e)}", exc_info=True)
        return Response(
            {'error': f'An unexpected error occurred: {str(e)}'}, 
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_rewrite_cv(request):
    """
    Initiate the CV rewrite process.
    
    Expects:
    - cv_id: ID of the CV to rewrite
    - personal_info: Optional personal information
    
    Returns:
    - session_id: ID of the rewrite session for polling status
    """
    try:
        # Import inside function to avoid circular imports
        from ai_cv_parser.models import CVRewriteSession
        from ai_cv_parser.services import CVRewriteService
        
        cv_id = request.data.get('cv_id')
        if not cv_id:
            return Response(
                {'error': 'CV ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Get the CV to rewrite
        try:
            cv = CvWriter.objects.get(id=cv_id)
        except CvWriter.DoesNotExist:
            return Response(
                {'error': 'CV not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Check ownership
        if cv.user != request.user:
            return Response(
                {'error': 'You do not have permission to rewrite this CV'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create a rewrite session
        rewrite_session = CVRewriteSession.objects.create(
            user=request.user,
            cv_id=cv_id,
            status='pending'
        )
        
        # Start the rewrite process in the background
        # We'll use the existing rewrite_cv view function which will update the session
        # but return immediately to the client
        from django.db import close_old_connections
        close_old_connections()
        
        # Trigger the rewrite process asynchronously
        import threading
        thread = threading.Thread(
            target=_process_rewrite_in_background, 
            args=(rewrite_session.id, cv_id, request.user.id)
        )
        thread.daemon = True
        thread.start()
        
        # Return the session ID for status polling
        return Response({
            'message': 'CV rewrite initiated successfully',
            'session_id': rewrite_session.id
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logging.error(f"Error initiating CV rewrite: {str(e)}", exc_info=True)
        return Response(
            {'error': f'An unexpected error occurred: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def _process_rewrite_in_background(session_id, cv_id, user_id):
    """Process CV rewrite in background thread"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Import inside function to avoid circular imports
        from ai_cv_parser.models import CVRewriteSession, ParsedCV
        from ai_cv_parser.services import CVRewriteService
        from ai_cv_parser.deepseek_service import DeepSeekService
        from cv_writer.services import CVImprovementService
        
        # Ensure we have a fresh DB connection in this thread
        connection.close()
        
        User = get_user_model()
        user = User.objects.get(id=user_id)
        session = CVRewriteSession.objects.get(id=session_id)
        
        # Get the CV data
        try:
            cv = CvWriter.objects.get(id=cv_id)
            
            # Get the parsed CV data if available
            try:
                parsed_cv = ParsedCV.objects.filter(id=cv_id).first()
                if not parsed_cv:
                    # Create a parsed CV object from the CvWriter data
                    cv_data = {
                        'personal_info': {
                            'name': f"{cv.first_name} {cv.last_name}",
                            'contact_number': cv.contact_number,
                            'address': cv.address,
                            'city': cv.city,
                            'country': cv.country
                        }
                    }
                    
                    # Get the professional summary if available
                    summaries = cv.professional_summaries.all()
                    if summaries.exists():
                        cv_data['professional_summary'] = summaries.first().summary
                        
                    # Get experiences
                    experiences = cv.experiences.all()
                    if experiences.exists():
                        cv_data['experience'] = []
                        for exp in experiences:
                            cv_data['experience'].append({
                                'job_title': exp.job_title,
                                'company_name': exp.company_name,
                                'description': exp.job_description,
                                'start_date': exp.start_date,
                                'end_date': exp.end_date,
                                'current': exp.current
                            })
                            
                    # Get education
                    education = cv.educations.all()
                    if education.exists():
                        cv_data['education'] = []
                        for edu in education:
                            cv_data['education'].append({
                                'school_name': edu.school_name,
                                'degree': edu.degree,
                                'field_of_study': edu.field_of_study,
                                'description': edu.description,
                                'start_date': edu.start_date,
                                'end_date': edu.end_date
                            })
                            
                    # Get skills
                    skills = cv.skills.all()
                    if skills.exists():
                        cv_data['skills'] = []
                        for skill in skills:
                            cv_data['skills'].append({
                                'name': skill.skill_name,
                                'level': skill.skill_level
                            })
                else:
                    # Use the parsed CV data
                    cv_data = parsed_cv.parsed_data
            except Exception as e:
                logger.error(f"Error retrieving parsed CV data: {str(e)}")
                cv_data = {}
                
            # Update the session status
            session.status = 'processing'
            session.save()
            
            # Initialize the rewrite service
            rewrite_service = CVRewriteService()
            
            # Rewrite the CV
            import asyncio
            import inspect
            
            if inspect.iscoroutinefunction(rewrite_service.rewrite_cv):
                # If it's async, we need to run it in an event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    rewrite_result = loop.run_until_complete(rewrite_service.rewrite_cv(cv_data))
                finally:
                    loop.close()
            else:
                # If it's a regular function, just call it normally
                rewrite_result = rewrite_service.rewrite_cv(cv_data)
            
            # Update the session with the result
            session.status = 'completed'
            session.result = rewrite_result
            
            # Extract the new CV ID from the result if available
            if isinstance(rewrite_result, dict) and rewrite_result.get('new_cv_id'):
                session.new_cv_id = rewrite_result.get('new_cv_id')
            
            session.save()
            
        except CvWriter.DoesNotExist:
            logger.error(f"CV with ID {cv_id} not found")
            session.status = 'error'
            session.result = {
                'status': 'error',
                'message': f'CV with ID {cv_id} not found'
            }
            session.save()
            
    except Exception as e:
        logger.error(f"Error in background CV rewrite: {str(e)}", exc_info=True)
        
        # Update the session status if we can
        try:
            session = CVRewriteSession.objects.get(id=session_id)
            session.status = 'error'
            session.result = {
                'status': 'error',
                'message': str(e),
                'error': str(e)
            }
            session.save()
        except Exception as inner_e:
            logger.error(f"Error updating session status: {str(inner_e)}")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rewrite_cv_status(request, session_id):
    """
    Get the status of a CV rewrite session.
    
    Params:
    - session_id: ID of the rewrite session
    
    Returns:
    - status: pending, processing, completed, or error
    - result: the rewrite result if completed
    """
    try:
        # Import inside function to avoid circular imports
        from ai_cv_parser.models import CVRewriteSession
        
        # Get the rewrite session
        try:
            rewrite_session = CVRewriteSession.objects.get(
                id=session_id,
                user=request.user
            )
        except CVRewriteSession.DoesNotExist:
            return Response(
                {'error': 'Rewrite session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Return the session status and result if available
        response_data = {
            'session_id': rewrite_session.id,
            'status': rewrite_session.status,
            'created_at': rewrite_session.created_at,
            'updated_at': rewrite_session.updated_at
        }
        
        # Include result if status is completed or error
        if rewrite_session.status in ['completed', 'error']:
            response_data['result'] = rewrite_session.result
            
        if rewrite_session.new_cv_id:
            response_data['new_cv_id'] = rewrite_session.new_cv_id
            
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logging.error(f"Error getting rewrite session status: {str(e)}", exc_info=True)
        return Response(
            {'error': f'An unexpected error occurred: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compare_rewritten_cv(request, session_id):
    """
    Compare the original CV data with the rewritten CV data from a completed session.
    
    Returns a structured comparison showing both versions side by side for each section.
    """
    try:
        # Import here to avoid circular imports
        from ai_cv_parser.models import CVRewriteSession
        
        # Get the rewrite session
        try:
            rewrite_session = CVRewriteSession.objects.get(
                id=session_id,
                user=request.user
            )
        except CVRewriteSession.DoesNotExist:
            return Response(
                {'error': 'Rewrite session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Check if the rewrite was completed
        if rewrite_session.status != 'completed':
            return Response(
                {'error': f'Rewrite session is not completed. Current status: {rewrite_session.status}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Extract original and rewritten data from the session
        session_result = rewrite_session.result
        
        # Get original CV data (from input_data)
        original_cv = rewrite_session.input_data
        
        # Get rewritten CV data from the result
        rewritten_cv = session_result.get('rewritten_cv', {})
        
        # Build a structured comparison for each section
        comparison = {
            'session_id': session_id,
            'created_at': rewrite_session.created_at.isoformat(),
            'completed_at': rewrite_session.updated_at.isoformat(),
            'new_cv_id': rewrite_session.new_cv_id,
            'sections': {}
        }
        
        # Check if both original and rewritten data exist
        if not original_cv or not rewritten_cv:
            return Response(
                {'error': 'Missing data for comparison', 
                 'has_original': bool(original_cv),
                 'has_rewritten': bool(rewritten_cv)
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Compare each section that exists in either version
        all_sections = set(list(original_cv.keys()) + list(rewritten_cv.keys()))
        
        for section in all_sections:
            comparison['sections'][section] = {
                'original': original_cv.get(section, None),
                'rewritten': rewritten_cv.get(section, None)
            }
        
        # Add specific comparison for professional summary if it exists
        if 'professional_summary' in original_cv and 'professional_summary' in rewritten_cv:
            # If it's a dict with content field
            if isinstance(original_cv.get('professional_summary'), dict) and 'content' in original_cv['professional_summary']:
                comparison['sections']['professional_summary'] = {
                    'original': original_cv['professional_summary'].get('content', ''),
                    'rewritten': rewritten_cv['professional_summary']
                }
        
        # Add specific comparison for experiences if they exist
        if 'experiences' in original_cv and 'experiences' in rewritten_cv:
            experience_comparison = []
            
            # Get the max length of either list
            orig_exp = original_cv.get('experiences', [])
            rewr_exp = rewritten_cv.get('experiences', [])
            
            max_exps = max(len(orig_exp), len(rewr_exp))
            
            for i in range(max_exps):
                exp_comp = {
                    'index': i,
                    'original': orig_exp[i] if i < len(orig_exp) else None,
                    'rewritten': rewr_exp[i] if i < len(rewr_exp) else None
                }
                experience_comparison.append(exp_comp)
                
            comparison['sections']['experiences_detailed'] = experience_comparison
        
        # Add a summary of what sections were changed
        comparison['changes_summary'] = {}
        for section in all_sections:
            has_original = section in original_cv and original_cv[section]
            has_rewritten = section in rewritten_cv and rewritten_cv[section]
            
            if has_original and has_rewritten:
                comparison['changes_summary'][section] = 'modified'
            elif has_original and not has_rewritten:
                comparison['changes_summary'][section] = 'removed'
            elif not has_original and has_rewritten:
                comparison['changes_summary'][section] = 'added'
        
        return Response(comparison, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error comparing rewritten CV: {str(e)}", exc_info=True)
        return Response(
            {'error': f'Failed to compare CV versions: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Template-related views
class CVTemplateListView(generics.ListAPIView):
    """
    List all available CV templates.
    """
    serializer_class = CVTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only show active templates
        return CVTemplate.objects.filter(is_active=True).order_by('order', 'name')
    
    def list(self, request, *args, **kwargs):
        """Add category filtering and organization"""
        queryset = self.get_queryset()
        
        # Filter by category if specified
        category = request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
            
        serializer = self.get_serializer(queryset, many=True)
        
        # Organize by category if requested
        organize_by_category = request.query_params.get('organize_by_category', 'false').lower() == 'true'
        if organize_by_category:
            categories = {}
            for template in serializer.data:
                category = template.get('category', 'other')
                if category not in categories:
                    categories[category] = []
                categories[category].append(template)
            return Response(categories)
            
        return Response(serializer.data)

class CVTemplateDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific CV template.
    """
    serializer_class = CVTemplateSerializer
    permission_classes = [IsAuthenticated]
    queryset = CVTemplate.objects.all()
    lookup_field = 'slug'  # Use slug for retrieval

class SetCVTemplateView(generics.UpdateAPIView):
    """
    Set or update the template for a CV.
    """
    permission_classes = [IsAuthenticated]
    
    def update(self, request, *args, **kwargs):
        cv_id = kwargs.get('pk')
        template_id = request.data.get('template_id')
        
        try:
            cv = CvWriter.objects.get(id=cv_id, user=request.user)
        except CvWriter.DoesNotExist:
            return Response({"error": "CV not found"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            template = CVTemplate.objects.get(id=template_id, is_active=True)
        except CVTemplate.DoesNotExist:
            return Response({"error": "Template not found or inactive"}, status=status.HTTP_404_NOT_FOUND)
            
        # Update CV with new template
        cv.template = template
        cv.save()
        
        # Create or update template selection with customization options
        selection, created = CVTemplateSelection.objects.get_or_create(
            user=request.user,
            cv=cv,
            defaults={'template': template}
        )
        
        if not created:
            selection.template = template
            selection.save()
            
        # Update customization options if provided
        if 'color_scheme' in request.data:
            selection.color_scheme = request.data['color_scheme']
        if 'font_choice' in request.data:
            selection.font_choice = request.data['font_choice']
        if 'layout_option' in request.data:
            selection.layout_option = request.data['layout_option']
        if 'custom_css' in request.data:
            selection.custom_css = request.data['custom_css']
        if 'custom_settings' in request.data:
            selection.custom_settings = request.data['custom_settings']
            
        selection.save()
        
        # Return updated CV with template info
        serializer = CvWriterSerializer(cv)
        return Response(serializer.data)

class CVTemplateSelectionDetailView(generics.RetrieveUpdateAPIView):
    """
    Get or update template customization options for a CV.
    """
    serializer_class = CVTemplateSelectionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        cv_id = self.kwargs.get('cv_id')
        try:
            cv = CvWriter.objects.get(id=cv_id, user=self.request.user)
            selection, created = CVTemplateSelection.objects.get_or_create(
                user=self.request.user,
                cv=cv,
                defaults={'template': cv.template} if cv.template else {}
            )
            return selection
        except CvWriter.DoesNotExist:
            raise Http404("CV not found")


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_cv_data(request):
    """
    Clear all CV data for the authenticated user.
    This endpoint removes all CV-related data including:
    - CvWriter records
    - Education, Experience, Skills, etc.
    - Professional summaries
    - Social media links
    - Certifications, Languages, Interests
    - References
    - CV improvements and template selections
    """
    try:
        user = request.user
        confirmation = request.data.get('confirmation', '')
        
        # Require explicit confirmation
        if confirmation != 'CONFIRMED':
            return Response({
                'error': 'Missing confirmation token',
                'message': 'You must provide confirmation token to clear all CV data'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"User {user.username} requested to clear all CV data")
        
        # Count existing data before deletion
        cv_count = CvWriter.objects.filter(user=user).count()
        education_count = Education.objects.filter(user=user).count()
        experience_count = Experience.objects.filter(user=user).count()
        skill_count = Skill.objects.filter(user=user).count()
        
        # Delete all CV-related data for the user
        deleted_counts = {}
        
        # Delete main CV records (this will cascade to related data due to foreign keys)
        cv_deleted = CvWriter.objects.filter(user=user).delete()
        deleted_counts['cvs'] = cv_deleted[0] if cv_deleted[0] else 0
        
        # Delete individual sections (in case they exist without CV)
        education_deleted = Education.objects.filter(user=user).delete()
        deleted_counts['education'] = education_deleted[0] if education_deleted[0] else 0
        
        experience_deleted = Experience.objects.filter(user=user).delete()
        deleted_counts['experience'] = experience_deleted[0] if experience_deleted[0] else 0
        
        skill_deleted = Skill.objects.filter(user=user).delete()
        deleted_counts['skills'] = skill_deleted[0] if skill_deleted[0] else 0
        
        language_deleted = Language.objects.filter(user=user).delete()
        deleted_counts['languages'] = language_deleted[0] if language_deleted[0] else 0
        
        certification_deleted = Certification.objects.filter(user=user).delete()
        deleted_counts['certifications'] = certification_deleted[0] if certification_deleted[0] else 0
        
        interest_deleted = Interest.objects.filter(user=user).delete()
        deleted_counts['interests'] = interest_deleted[0] if interest_deleted[0] else 0
        
        reference_deleted = Reference.objects.filter(user=user).delete()
        deleted_counts['references'] = reference_deleted[0] if reference_deleted[0] else 0
        
        social_media_deleted = SocialMedia.objects.filter(user=user).delete()
        deleted_counts['social_media'] = social_media_deleted[0] if social_media_deleted[0] else 0
        
        # Delete professional summaries
        professional_summary_deleted = ProfessionalSummary.objects.filter(user=user).delete()
        deleted_counts['professional_summaries'] = professional_summary_deleted[0] if professional_summary_deleted[0] else 0
        
        # Delete CV improvements
        cv_improvement_deleted = CVImprovement.objects.filter(user=user).delete()
        deleted_counts['cv_improvements'] = cv_improvement_deleted[0] if cv_improvement_deleted[0] else 0
        
        # Delete template selections
        template_selection_deleted = CVTemplateSelection.objects.filter(user=user).delete()
        deleted_counts['template_selections'] = template_selection_deleted[0] if template_selection_deleted[0] else 0
        
        total_deleted = sum(deleted_counts.values())
        
        logger.info(f"Successfully cleared CV data for user {user.username}. Deleted counts: {deleted_counts}")
        
        return Response({
            'status': 'success',
            'message': f'Successfully cleared all CV data for user {user.username}',
            'deleted_counts': deleted_counts,
            'total_deleted': total_deleted,
            'summary': {
                'cvs_before': cv_count,
                'education_before': education_count,
                'experience_before': experience_count,
                'skills_before': skill_count,
                'total_items_deleted': total_deleted
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error clearing CV data for user {request.user.username}: {str(e)}")
        return Response({
            'error': 'Failed to clear CV data',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)