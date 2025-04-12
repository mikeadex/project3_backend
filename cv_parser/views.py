from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import CVDocument, ParsedCV
from .parsers import DocumentParser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import logging
import json
import pprint
import tempfile
from datetime import datetime
import traceback
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .services import DeepSeekService
from rest_framework.views import APIView
from rest_framework import authentication, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from urllib3.exceptions import ReadTimeoutError, ConnectTimeoutError
from requests.exceptions import Timeout, ConnectionError

# Import CV Writer models
from cv_writer.models import (
    CvWriter, 
    ProfessionalSummary, 
    Experience, 
    Education, 
    Skill, 
    Language, 
    Certification
)

# Use the dedicated cv_parser logger
logger = logging.getLogger('cv_parser')

class CVParserViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    @action(detail=False, methods=['post'])
    def parse_document(self, request):
        """
        Parse a document using DeepSeek AI service
        """
        try:
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No file uploaded'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            file = request.FILES['file']
            if not file.name:
                return Response(
                    {'error': 'No file selected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Validate file type
            allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
            if file.content_type not in allowed_types:
                return Response(
                    {'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Save file temporarily
            file_path = os.path.join('temp', file.name)
            path = default_storage.save(file_path, ContentFile(file.read()))
            full_path = default_storage.path(path)
            
            try:
                # Parse the document using DeepSeek service
                service = DeepSeekService()
                result = service.parse_document(full_path)
                
                if 'error' in result:
                    return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                # Create ParsedCV object
                parsed_cv = ParsedCV.objects.create(
                    user=request.user,
                    original_file=file,
                    parsed_data=result
                )
                
                return Response({
                    'id': parsed_cv.id,
                    'data': result
                })
                
            finally:
                # Clean up temporary file
                if os.path.exists(full_path):
                    os.remove(full_path)
                    
        except Exception as e:
            logger.error(f"Error parsing document: {str(e)}", exc_info=True)
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['POST'])
    def transfer_to_writer(self, request):
        """
        Transfer parsed CV data to the CV writer app
        
        This endpoint accepts parsed CV data from the frontend and creates a new CV
        in the cv_writer app with the parsed data.
        """
        try:
            # Log the request information
            logger.info(f"CV transfer request from user {request.user.username} (ID: {request.user.id})")
            
            # Check if user is authenticated
            if not request.user.is_authenticated:
                logger.warning(f"Unauthenticated transfer request rejected")
                return Response({
                    'error': 'Authentication required'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get parsed data from request
            parsed_data = request.data.get('parsed_data')
            if not parsed_data:
                logger.warning(f"No parsed data provided in transfer request by user {request.user.username}")
                return Response({
                    'error': 'No parsed data provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Log the parsed data being transferred
            parsed_str = pprint.pformat(parsed_data)
            logger.info(f"Transferring parsed data to CV Writer:\n{parsed_str}")
            
            # Create a new CV in cv_writer
            cv_writer = CvWriter.objects.create(
                user=request.user,
                title="CV from Parser",
                status="active"
            )
            logger.info(f"Created new CV Writer record with ID: {cv_writer.id}")
            
            # Create professional summary if available
            if parsed_data.get('professional_summary'):
                logger.info(f"Adding professional summary to CV {cv_writer.id}")
                ProfessionalSummary.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    summary=parsed_data.get('professional_summary')
                )
            
            # Create experiences if available
            if parsed_data.get('experience'):
                logger.info(f"Adding {len(parsed_data.get('experience'))} experiences to CV {cv_writer.id}")
                for i, exp_data in enumerate(parsed_data.get('experience')):
                    logger.info(f"Adding experience {i+1}: {exp_data.get('job_title', '')} at {exp_data.get('company', '')}")
                    Experience.objects.create(
                        user=request.user,
                        cv=cv_writer,
                        job_title=exp_data.get('job_title', ''),
                        company_name=exp_data.get('company', ''),
                        position=exp_data.get('position', ''),
                        start_date=exp_data.get('start_date', ''),
                        end_date=exp_data.get('end_date', ''),
                        job_description=exp_data.get('job_description', '')
                    )
            
            # Create education entries if available
            if parsed_data.get('education'):
                logger.info(f"Adding {len(parsed_data.get('education'))} education entries to CV {cv_writer.id}")
                for i, edu_data in enumerate(parsed_data.get('education')):
                    logger.info(f"Adding education {i+1}: {edu_data.get('degree', '')} at {edu_data.get('school', '')}")
                    Education.objects.create(
                        user=request.user,
                        cv=cv_writer,
                        school_name=edu_data.get('school', ''),
                        degree=edu_data.get('degree', ''),
                        field_of_study=edu_data.get('field', ''),
                        start_date=edu_data.get('start_date', ''),
                        end_date=edu_data.get('end_date', ''),
                        details=edu_data.get('details', '')
                    )
            
            # Create skills if available
            if parsed_data.get('skills'):
                skills_count = len(parsed_data.get('skills'))
                logger.info(f"Adding {skills_count} skills to CV {cv_writer.id}")
                for i, skill_data in enumerate(parsed_data.get('skills')):
                    if isinstance(skill_data, dict):
                        skill_name = skill_data.get('name', '')
                        logger.info(f"Adding skill {i+1}: {skill_name} (from dictionary)")
                        Skill.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            name=skill_name,
                            level=skill_data.get('level', 'Intermediate'),
                            category="Technical Skills"
                        )
                    elif isinstance(skill_data, str):
                        logger.info(f"Adding skill {i+1}: {skill_data} (from string)")
                        Skill.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            name=skill_data,
                            level='Intermediate',
                            category="General"
                        )
            
            # Create languages if available
            if parsed_data.get('languages'):
                langs_count = len(parsed_data.get('languages'))
                logger.info(f"Adding {langs_count} languages to CV {cv_writer.id}")
                for i, lang_data in enumerate(parsed_data.get('languages')):
                    if isinstance(lang_data, dict):
                        lang_name = lang_data.get('language', '')
                        logger.info(f"Adding language {i+1}: {lang_name} (from dictionary)")
                        Language.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            language=lang_name,
                            proficiency=lang_data.get('proficiency', 'Intermediate')
                        )
                    elif isinstance(lang_data, str):
                        logger.info(f"Adding language {i+1}: {lang_data} (from string)")
                        Language.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            language=lang_data,
                            proficiency='Intermediate'
                        )
            
            # Create certifications if available
            if parsed_data.get('certifications'):
                certs_count = len(parsed_data.get('certifications'))
                logger.info(f"Adding {certs_count} certifications to CV {cv_writer.id}")
                for i, cert_data in enumerate(parsed_data.get('certifications')):
                    if isinstance(cert_data, dict):
                        cert_name = cert_data.get('name', '')
                        logger.info(f"Adding certification {i+1}: {cert_name}")
                        Certification.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            name=cert_name,
                            issuer=cert_data.get('issuer', ''),
                            date=cert_data.get('date', '')
                        )
            
            logger.info(f"Data successfully transferred to CV Writer with ID: {cv_writer.id}")
            return Response({
                'message': 'Data successfully transferred to CV Writer',
                'cv_id': cv_writer.id
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Unexpected error in transfer_to_writer: {e}", exc_info=True)
            return Response({
                'error': f'Failed to transfer data: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['POST'])
    def extract_sections(self, request):
        """
        Extract sections from CV text using DeepSeek's API
        
        This endpoint accepts raw CV text and segments it into sections using
        the DeepSeek API integration.
        """
        try:
            # Check if user is authenticated
            if not request.user.is_authenticated:
                logger.error(f"Unauthenticated request rejected for extract_sections")
                return Response({
                    'error': 'Authentication required. Please log in.'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            logger.info(f"Authenticated user {request.user.username} (ID: {request.user.id}) is attempting to extract sections")
            
            # Get text from request
            text = request.data.get('text')
            if not text:
                logger.warning(f"No text provided in extract_sections request by user {request.user.username}")
                return Response({
                    'error': 'No text provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Log the request
            logger.info(f"Section extraction request for text of length {len(text)} by user {request.user.username}")
            
            # Initialize the document parser
            parser = DocumentParser()
            
            # Extract sections
            extracted_sections = parser._segment_with_deepseek(text)
            
            # Log success
            section_count = len(extracted_sections.keys()) if extracted_sections else 0
            logger.info(f"Successfully extracted {section_count} sections for user {request.user.username}")
            
            return Response(extracted_sections, status=status.HTTP_200_OK)
            
        except Exception as e:
            user_id = request.user.id if request.user.is_authenticated else 'anonymous'
            logger.error(f"Error extracting sections for user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"Failed to extract sections: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ParseCVView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Parse a CV from an uploaded file
        """
        try:
            # Get the uploaded file
            cv_file = request.FILES.get('cv_file')
            
            if not cv_file:
                return Response({'error': 'No file was uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check file size (max 10MB)
            if cv_file.size > 10 * 1024 * 1024:  # 10MB in bytes
                return Response({'error': 'File too large. Maximum size is 10MB.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check file type
            file_type = cv_file.name.split('.')[-1].lower()
            if file_type not in ['pdf', 'docx', 'doc', 'txt']:
                return Response({'error': 'Invalid file type. Please upload PDF, Word, or text file.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the file to a temporary location
            with tempfile.NamedTemporaryFile(suffix=f'.{file_type}', delete=False) as tmp_file:
                for chunk in cv_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            
            try:
                # Parse the CV using DeepSeek API
                service = DeepSeekService()
                
                # Extended timeout for large documents - communicate to the client
                if cv_file.size > 5 * 1024 * 1024:  # If over 5MB
                    timeout = 120  # 2 minutes
                else:
                    timeout = 60  # 1 minute
                    
                # Parse with appropriate timeout
                parsed_data = service.parse_document(tmp_file_path, timeout)
                
                # Clean up the temporary file
                os.unlink(tmp_file_path)
                
                # Save original file to model's FileField
                # Reset file pointer to the beginning since we already read it
                cv_file.seek(0)
                file_path = f"parsed_cvs/{request.user.id}_{cv_file.name}"
                file_content = ContentFile(cv_file.read())
                file_storage_path = default_storage.save(file_path, file_content)
                
                # Save the parsed data
                parsed_cv = ParsedCV.objects.create(
                    user=request.user,
                    original_file=file_storage_path,
                    parsed_data=parsed_data
                )
                
                return Response({
                    'cv_id': parsed_cv.id,
                    'message': 'CV parsed successfully'
                }, status=status.HTTP_201_CREATED)
                
            except ReadTimeoutError as e:
                # Handle read timeout specifically
                logger.error(f"Read timeout error while parsing document: {str(e)}")
                os.unlink(tmp_file_path)  # Clean up
                return Response({
                    'error': 'The CV parsing is taking longer than expected. The file might be too complex or our servers are busy. Please try again with a smaller file or try later.'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)
                
            except ConnectTimeoutError as e:
                # Handle connection timeout specifically
                logger.error(f"Connection timeout error while parsing document: {str(e)}")
                os.unlink(tmp_file_path)  # Clean up
                return Response({
                    'error': 'Could not connect to the AI service. Please try again later.'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)
                
            except Timeout as e:
                logger.error(f"Timeout error while parsing document: {str(e)}")
                os.unlink(tmp_file_path)  # Clean up
                return Response({
                    'error': 'The CV parsing is taking longer than expected. The file might be too complex or our servers are busy. Please try again with a smaller file or try later.'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)
                
            except ConnectionError as e:
                logger.error(f"Connection error while parsing document: {str(e)}")
                os.unlink(tmp_file_path)  # Clean up
                return Response({
                    'error': 'Could not connect to the AI service. Please try again later.'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)
                
            except Exception as e:
                # Handle other errors during parsing
                logger.error(f"Error parsing document: {str(e)}", exc_info=True)
                os.unlink(tmp_file_path)  # Clean up
                return Response({
                    'error': 'Failed to parse CV. Please try again with a different file or contact support.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Unexpected error in parse_cv view: {str(e)}", exc_info=True)
            return Response({
                'error': 'An unexpected error occurred. Please try again later.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@require_http_methods(["GET"])
def parsed_cv_detail(request, cv_id):
    """
    Get details of a specific parsed CV.
    """
    try:
        # Validate authentication
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Authentication required'
            }, status=401)
            
        # Extract the token to get user information
        token = auth_header.split(' ')[1]
        
        # Validate token and get user
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token_obj = AccessToken(token)
            user_id = token_obj['user_id']
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"Failed to get user from token: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token'
            }, status=401)
        
        # Get the parsed CV object
        try:
            parsed_cv = ParsedCV.objects.get(id=cv_id, user=user)
        except ParsedCV.DoesNotExist:
            return JsonResponse({
                'error': 'CV not found or you do not have permission to access it'
            }, status=404)
        
        # Return the parsed CV data
        return JsonResponse({
            'id': parsed_cv.id,
            'created_at': parsed_cv.created_at,
            'parsed_data': parsed_cv.parsed_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching parsed CV: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
@csrf_exempt
def cv_from_parser(request):
    """
    Create a new CV in the CV writer system from a parsed CV.
    """
    try:
        # Validate authentication
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Authentication required'
            }, status=401)
            
        # Extract the token to get user information
        token = auth_header.split(' ')[1]
        
        # Validate token and get user
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token_obj = AccessToken(token)
            user_id = token_obj['user_id']
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"Failed to get user from token: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token'
            }, status=401)
        
        # Parse request body
        try:
            import json
            data = json.loads(request.body)
            parsed_cv_id = data.get('parsed_cv_id')
            
            if not parsed_cv_id:
                return JsonResponse({
                    'error': 'Parsed CV ID is required'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid request body'
            }, status=400)
        
        # Get the parsed CV
        try:
            parsed_cv = ParsedCV.objects.get(id=parsed_cv_id, user=user)
        except ParsedCV.DoesNotExist:
            return JsonResponse({
                'error': 'Parsed CV not found or you do not have permission to access it'
            }, status=404)
        
        # Import CV Writer models
        from cv_writer.models import CV, PersonalInfo, Experience, Education, Skill, Language, Certification, Interest
        
        # Map parsed data to CV writer format
        parsed_data = parsed_cv.parsed_data
        
        # Create new CV
        cv = CV.objects.create(
            user=user,
            title=f"CV from uploaded document - {datetime.now().strftime('%Y-%m-%d')}",
            description="Created from uploaded CV document",
            is_active=True
        )
        
        # Extract and create personal information
        contact_info = parsed_data.get('contact_info', {})
        name_parts = parsed_data.get('professional_summary', '').split(' ')[:2] if parsed_data.get('professional_summary') else ['', '']
        
        PersonalInfo.objects.create(
            cv=cv,
            first_name=name_parts[0] if len(name_parts) > 0 else '',
            last_name=name_parts[1] if len(name_parts) > 1 else '',
            email=contact_info.get('email', ''),
            phone=contact_info.get('phone', ''),
            address=contact_info.get('location', ''),
            summary=parsed_data.get('professional_summary', '')
        )
        
        # Create experiences
        for exp_data in parsed_data.get('experience', []):
            if isinstance(exp_data, dict):
                company = exp_data.get('company', '')
                role = exp_data.get('role', '')
                duration = exp_data.get('duration', '')
                responsibilities = exp_data.get('responsibilities', [])
                
                # Parse duration into start and end dates
                start_date = None
                end_date = None
                if duration:
                    try:
                        if '-' in duration:
                            date_parts = duration.split('-')
                            start_date = parse_date(date_parts[0].strip())
                            end_date = parse_date(date_parts[1].strip())
                        else:
                            start_date = parse_date(duration.strip())
                    except:
                        pass
                
                Experience.objects.create(
                    cv=cv,
                    company_name=company,
                    position=role,
                    start_date=start_date,
                    end_date=end_date,
                    description='\n'.join(responsibilities) if isinstance(responsibilities, list) else str(responsibilities)
                )
        
        # Create education
        for edu_data in parsed_data.get('education', []):
            if isinstance(edu_data, dict):
                institution = edu_data.get('institution', '')
                degree = edu_data.get('degree', '')
                duration = edu_data.get('duration', '')
                
                # Parse duration into start and end dates
                start_date = None
                end_date = None
                if duration:
                    try:
                        if '-' in duration:
                            date_parts = duration.split('-')
                            start_date = parse_date(date_parts[0].strip())
                            end_date = parse_date(date_parts[1].strip())
                        else:
                            end_date = parse_date(duration.strip())
                    except:
                        pass
                
                Education.objects.create(
                    cv=cv,
                    school_name=institution,
                    degree=degree,
                    field_of_study=edu_data.get('field', ''),
                    start_date=start_date,
                    end_date=end_date,
                    description=edu_data.get('description', '')
                )
        
        # Create skills
        for skill_name in parsed_data.get('skills', []):
            if skill_name:
                Skill.objects.create(
                    cv=cv,
                    name=skill_name if isinstance(skill_name, str) else str(skill_name),
                    level='Intermediate'  # Default level
                )
        
        # Create languages
        for lang_name in parsed_data.get('languages', []):
            if lang_name:
                Language.objects.create(
                    cv=cv,
                    language=lang_name if isinstance(lang_name, str) else str(lang_name),
                    proficiency='Intermediate'  # Default proficiency
                )
        
        # Create certifications
        for cert_data in parsed_data.get('certifications', []):
            if isinstance(cert_data, dict):
                Certification.objects.create(
                    cv=cv,
                    name=cert_data.get('name', ''),
                    issuing_organization=cert_data.get('issuer', ''),
                    date_obtained=parse_date(cert_data.get('year', '')) if cert_data.get('year') else None
                )
            elif cert_data:
                Certification.objects.create(
                    cv=cv,
                    name=cert_data if isinstance(cert_data, str) else str(cert_data)
                )
        
        # Return the new CV ID
        return JsonResponse({
            'success': True,
            'cv_id': cv.id,
            'message': 'CV created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating CV from parsed data: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=500)

def parse_date(date_string):
    """Helper function to parse date strings"""
    from datetime import datetime
    
    # Try different date formats
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y', '%B %Y', '%b %Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string.strip(), fmt).date()
        except:
            continue
    
    # If all formats fail, try to extract just a year
    import re
    year_match = re.search(r'\d{4}', date_string)
    if year_match:
        year = year_match.group(0)
        try:
            return datetime(int(year), 1, 1).date()
        except:
            pass
    
    return None

@require_http_methods(["POST"])
@csrf_exempt
def analyze_cv(request):
    """
    Analyze a parsed CV and provide feedback and improvement suggestions.
    """
    try:
        # Validate authentication
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Authentication required'
            }, status=401)
            
        # Extract the token to get user information
        token = auth_header.split(' ')[1]
        
        # Validate token and get user
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token_obj = AccessToken(token)
            user_id = token_obj['user_id']
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"Failed to get user from token: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token'
            }, status=401)
        
        # Parse request body
        try:
            import json
            data = json.loads(request.body)
            parsed_cv_id = data.get('parsed_cv_id')
            
            if not parsed_cv_id:
                return JsonResponse({
                    'error': 'Parsed CV ID is required'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid request body'
            }, status=400)
        
        # Get the parsed CV
        try:
            parsed_cv = ParsedCV.objects.get(id=parsed_cv_id, user=user)
        except ParsedCV.DoesNotExist:
            return JsonResponse({
                'error': 'Parsed CV not found or you do not have permission to access it'
            }, status=404)
        
        # Get CV data
        cv_data = parsed_cv.parsed_data
        
        # Use DeepSeek service to analyze CV
        service = DeepSeekService()
        
        # Define analysis criteria
        analysis_criteria = [
            "Content completeness (Are all essential sections present?)",
            "Format and structure (Is the information well-organized?)",
            "Skills relevance (Are skills clearly highlighted and relevant?)",
            "Job history description quality (Are responsibilities clear and impactful?)",
            "Education presentation (Is educational background properly presented?)",
            "Overall impact (How effective is the CV at showcasing the candidate's value?)"
        ]
        
        # Prepare the prompt for analysis
        prompt = f"""
        Please analyze this CV data and provide structured feedback on its strengths, weaknesses, and specific improvement suggestions.
        
        Evaluation criteria:
        - Content completeness
        - Format and structure
        - Skills relevance
        - Job history description quality
        - Education presentation
        - Overall impact
        
        CV Data:
        {json.dumps(cv_data, indent=2)}
        
        Please provide your analysis in JSON format with the following structure:
        {{
            "overall_score": (number between 1-10),
            "strengths": [list of strengths],
            "weaknesses": [list of weaknesses],
            "improvement_suggestions": [specific actionable suggestions],
            "section_scores": {{
                "content_completeness": (score 1-10),
                "format_structure": (score 1-10),
                "skills_relevance": (score 1-10),
                "job_history": (score 1-10),
                "education": (score 1-10),
                "overall_impact": (score 1-10)
            }}
        }}
        """
        
        # Make API request for analysis
        response = service.make_custom_request(prompt)
        
        if 'error' in response:
            return JsonResponse(response, status=500)
            
        return JsonResponse(response)
        
    except Exception as e:
        logger.error(f"Error analyzing CV: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=500)

@require_http_methods(["GET"])
def download_cv(request, cv_id):
    """
    Download a parsed CV as a PDF file.
    """
    try:
        # Validate authentication
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Authentication required'
            }, status=401)
            
        # Extract the token to get user information
        token = auth_header.split(' ')[1]
        
        # Validate token and get user
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token_obj = AccessToken(token)
            user_id = token_obj['user_id']
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
        except Exception as e:
            logger.error(f"Failed to get user from token: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token'
            }, status=401)
        
        # Get the parsed CV
        try:
            parsed_cv = ParsedCV.objects.get(id=cv_id, user=user)
        except ParsedCV.DoesNotExist:
            return JsonResponse({
                'error': 'CV not found or you do not have permission to access it'
            }, status=404)
        
        # Get CV data
        cv_data = parsed_cv.parsed_data
        
        # Generate PDF for the CV
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from io import BytesIO
        
        # Create a PDF buffer
        buffer = BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        
        # Get styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Heading1', fontName='Helvetica-Bold', fontSize=16, spaceAfter=12))
        styles.add(ParagraphStyle(name='Heading2', fontName='Helvetica-Bold', fontSize=14, spaceAfter=10, spaceBefore=10))
        styles.add(ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=12, spaceAfter=6))
        styles.add(ParagraphStyle(name='ListItem', fontName='Helvetica', fontSize=12, leftIndent=20))
        
        # Build the PDF content
        content = []
        
        # Extract name from contact_info if available
        name = "CV Document"
        if cv_data.get('contact_info') and isinstance(cv_data['contact_info'], dict):
            contact_info = cv_data['contact_info']
            if contact_info.get('name'):
                name = contact_info['name']
        
        # Add title
        content.append(Paragraph(name, styles['Heading1']))
        content.append(Spacer(1, 12))
        
        # Add professional summary
        if 'professional_summary' in cv_data and cv_data['professional_summary']:
            content.append(Paragraph("Professional Summary", styles['Heading2']))
            content.append(Paragraph(cv_data['professional_summary'], styles['Normal']))
            content.append(Spacer(1, 12))
        
        # Add skills
        if 'skills' in cv_data and cv_data['skills']:
            content.append(Paragraph("Skills", styles['Heading2']))
            
            if isinstance(cv_data['skills'], list):
                skills_list = []
                for skill in cv_data['skills']:
                    if isinstance(skill, str):
                        skills_list.append(ListItem(Paragraph(skill, styles['ListItem'])))
                    elif isinstance(skill, dict) and 'name' in skill:
                        skill_text = skill['name']
                        if 'level' in skill:
                            skill_text += f" ({skill['level']})"
                        skills_list.append(ListItem(Paragraph(skill_text, styles['ListItem'])))
                
                if skills_list:
                    content.append(ListFlowable(skills_list, bulletType='bullet'))
                else:
                    content.append(Paragraph("No specific skills listed", styles['Normal']))
            else:
                content.append(Paragraph(str(cv_data['skills']), styles['Normal']))
                
            content.append(Spacer(1, 12))
        
        # Add experience
        if 'experience' in cv_data and cv_data['experience']:
            content.append(Paragraph("Experience", styles['Heading2']))
            
            if isinstance(cv_data['experience'], list):
                for exp in cv_data['experience']:
                    if isinstance(exp, dict):
                        # Extract experience details
                        company = exp.get('company', '')
                        role = exp.get('role', '')
                        duration = exp.get('duration', '')
                        responsibilities = exp.get('responsibilities', [])
                        
                        # Format experience entry
                        exp_title = f"{role} at {company}"
                        if duration:
                            exp_title += f" ({duration})"
                            
                        content.append(Paragraph(exp_title, styles['Heading2']))
                        
                        # Add responsibilities
                        if responsibilities:
                            resp_list = []
                            
                            if isinstance(responsibilities, list):
                                for resp in responsibilities:
                                    if isinstance(resp, str):
                                        resp_list.append(ListItem(Paragraph(resp, styles['ListItem'])))
                                
                                if resp_list:
                                    content.append(ListFlowable(resp_list, bulletType='bullet'))
                            else:
                                content.append(Paragraph(str(responsibilities), styles['Normal']))
                    else:
                        content.append(Paragraph(str(exp), styles['Normal']))
                    
                    content.append(Spacer(1, 10))
            else:
                content.append(Paragraph(str(cv_data['experience']), styles['Normal']))
                
            content.append(Spacer(1, 12))
        
        # Add education
        if 'education' in cv_data and cv_data['education']:
            content.append(Paragraph("Education", styles['Heading2']))
            
            if isinstance(cv_data['education'], list):
                for edu in cv_data['education']:
                    if isinstance(edu, dict):
                        institution = edu.get('institution', '')
                        degree = edu.get('degree', '')
                        year = edu.get('year', '')
                        
                        edu_text = f"{degree} - {institution}"
                        if year:
                            edu_text += f" ({year})"
                            
                        content.append(Paragraph(edu_text, styles['Normal']))
                    else:
                        content.append(Paragraph(str(edu), styles['Normal']))
                    
                    content.append(Spacer(1, 6))
            else:
                content.append(Paragraph(str(cv_data['education']), styles['Normal']))
                
            content.append(Spacer(1, 12))
        
        # Add certifications
        if 'certifications' in cv_data and cv_data['certifications']:
            content.append(Paragraph("Certifications", styles['Heading2']))
            
            if isinstance(cv_data['certifications'], list):
                cert_list = []
                for cert in cv_data['certifications']:
                    if isinstance(cert, dict):
                        name = cert.get('name', '')
                        issuer = cert.get('issuer', '')
                        year = cert.get('year', '')
                        
                        cert_text = name
                        if issuer:
                            cert_text += f" - {issuer}"
                        if year:
                            cert_text += f" ({year})"
                            
                        cert_list.append(ListItem(Paragraph(cert_text, styles['ListItem'])))
                    elif isinstance(cert, str):
                        cert_list.append(ListItem(Paragraph(cert, styles['ListItem'])))
                
                if cert_list:
                    content.append(ListFlowable(cert_list, bulletType='bullet'))
                else:
                    content.append(Paragraph("No specific certifications listed", styles['Normal']))
            else:
                content.append(Paragraph(str(cv_data['certifications']), styles['Normal']))
                
            content.append(Spacer(1, 12))
        
        # Add languages
        if 'languages' in cv_data and cv_data['languages']:
            content.append(Paragraph("Languages", styles['Heading2']))
            
            if isinstance(cv_data['languages'], list):
                lang_list = []
                for lang in cv_data['languages']:
                    if isinstance(lang, str):
                        lang_list.append(ListItem(Paragraph(lang, styles['ListItem'])))
                    elif isinstance(lang, dict) and 'language' in lang:
                        lang_text = lang['language']
                        if 'proficiency' in lang:
                            lang_text += f" - {lang['proficiency']}"
                        lang_list.append(ListItem(Paragraph(lang_text, styles['ListItem'])))
                
                if lang_list:
                    content.append(ListFlowable(lang_list, bulletType='bullet'))
                else:
                    content.append(Paragraph("No specific languages listed", styles['Normal']))
            else:
                content.append(Paragraph(str(cv_data['languages']), styles['Normal']))
                
            content.append(Spacer(1, 12))
        
        # Add contact information
        if 'contact_info' in cv_data and cv_data['contact_info']:
            content.append(Paragraph("Contact Information", styles['Heading2']))
            
            if isinstance(cv_data['contact_info'], dict):
                contact_info = cv_data['contact_info']
                
                if 'email' in contact_info:
                    content.append(Paragraph(f"Email: {contact_info['email']}", styles['Normal']))
                
                if 'phone' in contact_info:
                    content.append(Paragraph(f"Phone: {contact_info['phone']}", styles['Normal']))
                
                if 'location' in contact_info:
                    content.append(Paragraph(f"Location: {contact_info['location']}", styles['Normal']))
            else:
                content.append(Paragraph(str(cv_data['contact_info']), styles['Normal']))
        
        # Build the PDF
        doc.build(content)
        
        # Get the value from the BytesIO buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        # Create the HttpResponse with PDF
        from django.http import HttpResponse
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{name.replace(" ", "_")}_CV.pdf"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error downloading CV: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=500)