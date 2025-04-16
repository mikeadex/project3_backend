from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import logging
import asyncio
import tempfile
import time
from datetime import datetime
from django.utils import timezone
import traceback
import json
from docx import Document
from PyPDF2 import PdfReader
from asgiref.sync import sync_to_async
from django.db import close_old_connections
from .models import ParsedCV, CVRewriteSession
from .deepseek_service import DeepSeekService
from .serializers import ParsedCVSerializer
from .services import CVRewriteService

# Import CV Writer models for transfer functionality
from cv_writer.models import (
    CvWriter, 
    ProfessionalSummary, 
    Experience, 
    Education, 
    Skill, 
    Language, 
    Certification
)

# Configure logging
logger = logging.getLogger('ai_cv_parser')

class AICVParserViewSet(viewsets.ModelViewSet):
    queryset = ParsedCV.objects.all()
    serializer_class = ParsedCVSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset to only show the authenticated user's CVs"""
        return ParsedCV.objects.filter(user=self.request.user)
    
    def save_uploaded_file(self, file):
        """Save uploaded file to a temporary location and return the path"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            return temp_file.name
    
    def extract_text_from_file(self, file_path):
        """Extract text from PDF or DOCX file"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_extension == '.docx':
                doc = Document(file_path)
                text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            elif file_extension == '.pdf':
                reader = PdfReader(file_path)
                text = '\n'.join([page.extract_text() for page in reader.pages])
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_extension} file: {str(e)}")
            raise
    
    @action(detail=False, methods=['POST'], url_path='parse-cv')
    def parse_cv(self, request):
        """
        Parse a CV document and replace any existing parsed CV for this user.
        """
        try:
            logger.info(f"CV parsing request from user {request.user.username} (ID: {request.user.id})")
            
            # Validate request data
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No file uploaded'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            file = request.FILES['file']
            logger.info(f"Received file: {file.name} (size: {file.size} bytes)")

            # Check if user has confirmed overwrite if they have an existing CV
            force_overwrite = request.data.get('force_overwrite', 'false').lower() == 'true'
            
            # Check if user already has a parsed CV
            existing_cv = ParsedCV.objects.filter(user=request.user).first()
            if existing_cv and not force_overwrite:
                # User has an existing CV but hasn't confirmed overwrite
                return Response({
                    'error': 'Existing CV found',
                    'requires_confirmation': True,
                    'message': 'You already have a parsed CV. Parsing a new CV will replace your existing one. Do you want to continue?',
                    'existing_cv_id': existing_cv.id,
                    'existing_cv_name': existing_cv.file_name,
                    'existing_cv_date': existing_cv.uploaded_at
                }, status=status.HTTP_409_CONFLICT)
            
            # If we're here, either:
            # 1. User doesn't have an existing CV
            # 2. User has confirmed they want to overwrite their existing CV
            
            # Delete any existing parsed CVs for this user
            if existing_cv:
                # Clean up temporary file if it exists
                if existing_cv.temp_file_path and os.path.exists(existing_cv.temp_file_path):
                    try:
                        os.remove(existing_cv.temp_file_path)
                        logger.info(f"Removed temporary file of existing CV: {existing_cv.temp_file_path}")
                    except Exception as file_e:
                        logger.error(f"Error removing temporary file: {str(file_e)}")
                
                # Delete the existing CV
                existing_cv.delete()
                logger.info(f"Deleted existing ParsedCV record for user {request.user.username}")
            
            # Create a new ParsedCV record
            parsed_cv = ParsedCV.objects.create(
                user=request.user,
                file_name=file.name,
                file_size=file.size,
                mime_type=file.content_type,
                status='queued'
            )
            logger.info(f"Created new ParsedCV record with ID: {parsed_cv.id}")
            
            # Save uploaded file to temporary location
            temp_path = self.save_uploaded_file(file)
            logger.info(f"Saved uploaded file to temporary location: {temp_path}")
            
            # Update the ParsedCV record with the temporary file path
            parsed_cv.temp_file_path = temp_path
            parsed_cv.save(update_fields=['temp_file_path'])
            
            # Start processing the file asynchronously
            # This will need to be adjusted based on your actual processing logic
            # Here we're using a placeholder for the async processing
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                executor.submit(self._process_cv_file, parsed_cv.id, temp_path)
            
            return Response({
                'id': parsed_cv.id,
                'message': 'CV upload successful. Processing has begun.',
                'status': 'queued'
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            logger.error(f"Error in CV parsing: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_cv_file(self, cv_id, file_path):
        """
        Process a CV file asynchronously
        
        Args:
            cv_id (int): The ID of the ParsedCV record
            file_path (str): Path to the temporary file
        """
        try:
            # Get the ParsedCV record
            parsed_cv = ParsedCV.objects.get(id=cv_id)
            
            # Update status to processing
            parsed_cv.status = 'processing'
            parsed_cv.save(update_fields=['status'])
            logger.info(f"Processing ParsedCV {cv_id} - Status updated to processing")
            
            start_time = time.time()
            
            # Extract text from the file
            try:
                extracted_text = self.extract_text_from_file(file_path)
                parsed_cv.extracted_text = extracted_text
                parsed_cv.save(update_fields=['extracted_text'])
                logger.info(f"Extracted text from CV file for ParsedCV {cv_id}")
            except Exception as text_error:
                logger.error(f"Error extracting text from file: {str(text_error)}")
                parsed_cv.status = 'failed'
                parsed_cv.error_message = f"Error extracting text: {str(text_error)}"
                parsed_cv.save(update_fields=['status', 'error_message'])
                return
            
            # Parse the CV using DeepSeek API or other parsing method
            try:
                service = DeepSeekService()
                parsed_data = service.parse_document(file_path)
                
                # Check if we got an error response with fallback data
                if 'error' in parsed_data:
                    logger.warning(f"CV parsing returned an error: {parsed_data.get('error')}")
                    
                    # If we have fallback data, use it instead of failing
                    if 'parsed_data_fallback' in parsed_data:
                        logger.info("Using fallback parsed data")
                        parsed_cv.status = 'completed_with_errors'
                        parsed_cv.error_message = parsed_data.get('error', '') + ': ' + parsed_data.get('message', '')
                        parsed_cv.parsed_data = parsed_data.get('parsed_data_fallback', {})
                        parsed_cv.processed_at = timezone.now()
                        parsed_cv.processing_time = time.time() - start_time
                        parsed_cv.save(update_fields=['parsed_data', 'status', 'processed_at', 'processing_time', 'error_message'])
                        logger.info(f"ParsedCV {cv_id} processing completed with errors in {parsed_cv.processing_time:.2f} seconds")
                        return
                    else:
                        # No fallback data, mark as failed
                        raise ValueError(parsed_data.get('error', 'Unknown error'))
                
                # Save the parsed data
                parsed_cv.parsed_data = parsed_data
                parsed_cv.status = 'completed'
                parsed_cv.processed_at = timezone.now()
                parsed_cv.processing_time = time.time() - start_time
                parsed_cv.save(update_fields=['parsed_data', 'status', 'processed_at', 'processing_time'])
                logger.info(f"ParsedCV {cv_id} processing completed successfully in {parsed_cv.processing_time:.2f} seconds")
            except Exception as parse_error:
                logger.error(f"Error parsing CV: {str(parse_error)}")
                parsed_cv.status = 'failed'
                parsed_cv.error_message = f"Error parsing CV: {str(parse_error)}"
                parsed_cv.save(update_fields=['status', 'error_message'])
        
        except ParsedCV.DoesNotExist:
            logger.error(f"ParsedCV with ID {cv_id} not found")
        except Exception as e:
            logger.error(f"Error in CV processing: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                parsed_cv = ParsedCV.objects.get(id=cv_id)
                parsed_cv.status = 'failed'
                parsed_cv.error_message = f"Unexpected error: {str(e)}"
                parsed_cv.save(update_fields=['status', 'error_message'])
            except:
                pass
        finally:
            # Clean up temporary file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Removed temporary file: {file_path}")
                except Exception as file_e:
                    logger.error(f"Error removing temporary file: {str(file_e)}")
    
    def _process_parsed_cv_background(self, parsed_cv_id):
        """
        Background task to process a CV.
        This runs in a separate thread to prevent worker timeouts.
        """
        # Set up a new database connection for this thread
        close_old_connections()
        
        try:
            # Get the ParsedCV object
            parsed_cv = ParsedCV.objects.get(id=parsed_cv_id)
            logger.info(f"Starting background processing for ParsedCV ID {parsed_cv_id}")
            
            text = parsed_cv.extracted_text
            temp_path = parsed_cv.temp_file_path
            
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Parse CV with DeepSeek - this is the slow operation
                parser = DeepSeekService()
                parsed_data = loop.run_until_complete(parser.parse_cv(text))
                logger.info(f"Successfully parsed CV with DeepSeek for ParsedCV ID {parsed_cv_id}")
                
                # Update ParsedCV with parsed data
                parsed_cv.parsed_data = parsed_data
                parsed_cv.status = 'completed'
                parsed_cv.processed_at = timezone.now()
                parsed_cv.save()
                logger.info(f"ParsedCV record {parsed_cv_id} updated - Status: completed")
                
            except Exception as e:
                logger.error(f"Error parsing CV with DeepSeek: {str(e)}")
                logger.error(traceback.format_exc())
                parsed_cv.status = 'failed'
                parsed_cv.error_message = str(e)
                parsed_cv.save()
            finally:
                loop.close()
                
                # Clean up temporary file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                        logger.info(f"Removed temporary file: {temp_path}")
                    except Exception as file_e:
                        logger.error(f"Error removing temporary file: {str(file_e)}")
        
        except Exception as e:
            logger.error(f"Critical error in background CV processing for ID {parsed_cv_id}: {str(e)}")
            logger.error(traceback.format_exc())
            
            try:
                # Try to update the record even in case of errors
                parsed_cv = ParsedCV.objects.get(id=parsed_cv_id)
                parsed_cv.status = 'failed'
                parsed_cv.error_message = f"Critical processing error: {str(e)}"
                parsed_cv.save()
            except Exception as db_e:
                logger.error(f"Could not update ParsedCV record after error: {str(db_e)}")
    
    @action(detail=False, methods=['POST'], url_path='transfer-to-writer')
    def transfer_to_writer(self, request):
        """Transfer parsed CV data to the CV writer app"""
        try:
            # Get parsed data from request
            parsed_data = request.data.get('parsed_data')
            if not parsed_data:
                logger.warning(f"No parsed data provided in transfer request")
                return Response({
                    'error': 'No parsed data provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Transferring parsed data to CV Writer for user {request.user.username}")
            
            # Create a new CV in cv_writer
            cv_writer = CvWriter.objects.create(
                user=request.user,
                title="CV from AI Parser",
                status="active"
            )
            logger.info(f"Created new CV Writer record with ID: {cv_writer.id}")
            
            # Create professional summary if available
            if parsed_data.get('professional_summary'):
                ProfessionalSummary.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    content=parsed_data.get('professional_summary')
                )
                logger.info(f"Added professional summary to CV Writer")
            
            # Create experiences
            experiences = parsed_data.get('experience', [])
            for exp_data in experiences:
                # Default start/end dates if not available
                start_date = exp_data.get('start_date', None)
                end_date = exp_data.get('end_date', None)
                
                Experience.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    company=exp_data.get('company', 'Unknown Company'),
                    title=exp_data.get('title', 'Unknown Position'),
                    start_date=start_date,
                    end_date=end_date,
                    current=exp_data.get('current', False),
                    description=exp_data.get('description', '')
                )
            logger.info(f"Added {len(experiences)} experiences to CV Writer")
            
            # Create education entries
            education_entries = parsed_data.get('education', [])
            for edu_data in education_entries:
                # Default start/end dates if not available
                start_date = edu_data.get('start_date', None)
                end_date = edu_data.get('end_date', None)
                
                Education.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    institution=edu_data.get('institution', 'Unknown Institution'),
                    degree=edu_data.get('degree', 'Unknown Degree'),
                    field=edu_data.get('field', ''),
                    start_date=start_date,
                    end_date=end_date,
                    description=edu_data.get('description', '')
                )
            logger.info(f"Added {len(education_entries)} education entries to CV Writer")
            
            # Create skills
            skills = parsed_data.get('skills', [])
            for skill_data in skills:
                # Handle both string and object formats
                if isinstance(skill_data, str):
                    skill_name = skill_data
                    skill_level = 'Intermediate'  # Default level
                else:
                    skill_name = skill_data.get('name', 'Unknown Skill')
                    skill_level = skill_data.get('level', 'Intermediate')
                
                Skill.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    name=skill_name,
                    level=skill_level
                )
            logger.info(f"Added {len(skills)} skills to CV Writer")
            
            # Create languages
            languages = parsed_data.get('languages', [])
            for lang_data in languages:
                # Handle both string and object formats
                if isinstance(lang_data, str):
                    lang_name = lang_data
                    proficiency = 'Intermediate'  # Default level
                else:
                    lang_name = lang_data.get('name', 'Unknown Language')
                    proficiency = lang_data.get('proficiency', 'Intermediate')
                
                Language.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    name=lang_name,
                    proficiency=proficiency
                )
            logger.info(f"Added {len(languages)} languages to CV Writer")
            
            # Create certifications
            certifications = parsed_data.get('certifications', [])
            for cert_data in certifications:
                # Handle both string and object formats
                if isinstance(cert_data, str):
                    cert_name = cert_data
                    issuer = ''
                    issue_date = None
                else:
                    cert_name = cert_data.get('name', 'Unknown Certification')
                    issuer = cert_data.get('issuer', '')
                    issue_date = cert_data.get('issue_date', None)
                
                Certification.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    name=cert_name,
                    issuer=issuer,
                    issue_date=issue_date
                )
            logger.info(f"Added {len(certifications)} certifications to CV Writer")
            
            return Response({
                'status': 'success',
                'message': 'CV data transferred to CV Writer successfully',
                'cv_id': cv_writer.id
            })
            
        except Exception as e:
            logger.error(f"Error transferring CV data to writer: {str(e)}")
            logger.error(traceback.format_exc())
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['POST'])
    def job_status(self, request):
        """Get status of multiple jobs"""
        job_ids = request.data.get('job_ids', [])
        if not job_ids:
            return Response({"error": "No job IDs provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        results = {}
        for job_id in job_ids:
            try:
                cv = ParsedCV.objects.get(id=job_id, user=request.user)
                results[job_id] = {
                    "status": cv.status,
                    "error_message": cv.error_message,
                    "processed_at": cv.processed_at
                }
            except ParsedCV.DoesNotExist:
                results[job_id] = {"status": "not_found", "error_message": "CV not found"}
        
        return Response(results)

    @action(detail=True, methods=['GET'], url_path='status')
    def get_status(self, request, pk=None):
        """
        Get the status of a CV parsing job
        """
        try:
            cv = self.get_object()
            data = {
                "id": cv.id,
                "status": cv.status,
                "uploaded_at": cv.uploaded_at,
                "processed_at": cv.processed_at,
                "processing_time": cv.processing_time,
                "error_message": cv.error_message
            }
            return Response(data)
        except Exception as e:
            logger.error(f"Error getting CV status: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve CV status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['POST'])
    def analyze(self, request):
        """
        Analyze a CV to provide feedback on content quality and improvement suggestions.
        
        Request format:
        {
            "cv_id": 1,
            "parser_type": "parsed_cv"  # or "cv_writer"
        }
        """
        try:
            # Validate input data
            cv_id = request.data.get('cv_id')
            parser_type = request.data.get('parser_type', 'parsed_cv')
            
            if not cv_id:
                return Response({
                    'error': 'CV ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the CV data based on the parser type
            cv_data = None
            parsed_cv = None
            if parser_type == 'parsed_cv':
                # Get from the cv_parser module
                try:
                    parsed_cv = ParsedCV.objects.get(id=cv_id, user=request.user)
                    cv_data = parsed_cv.parsed_data
                    
                    # Check if we already have analysis data and it's not too old (e.g., less than 7 days)
                    if parsed_cv.analysis_data and parsed_cv.analysis_date and (timezone.now() - parsed_cv.analysis_date).days < 7:
                        # Return cached analysis
                        logger.info(f"Returning cached analysis for ParsedCV ID {cv_id}")
                        return Response({
                            'analysis': parsed_cv.analysis_data,
                            'cached': True,
                            'analysis_date': parsed_cv.analysis_date
                        })
                        
                except ParsedCV.DoesNotExist:
                    return Response({
                        'error': 'CV not found or you do not have permission to access it'
                    }, status=status.HTTP_404_NOT_FOUND)
            elif parser_type == 'cv_writer':
                # Get from the cv_writer module
                from cv_writer.models import CV, PersonalInfo, Experience, Education, Skill
                try:
                    cv = CV.objects.get(id=cv_id, user=request.user)
                    # Assemble CV data from different models
                    cv_data = self._assemble_cv_data(cv)
                except CV.DoesNotExist:
                    return Response({
                        'error': 'CV not found or you do not have permission to access it'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    'error': f'Invalid parser_type: {parser_type}'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not cv_data:
                return Response({
                    'error': 'No CV data found'
                }, status=status.HTTP_404_NOT_FOUND)
                
            # Prepare the prompt for analysis
            service = DeepSeekService()
            
            # Continue with existing prompt preparation
            prompt = f"""
            Please analyze this CV data and provide structured feedback on its strengths, weaknesses, and specific improvement suggestions.
            
            Evaluation criteria:
            - Content completeness
            - Format and structure
            - Skills relevance
            - Job history description quality
            - Education presentation
            - Overall impact
            - ATS readiness (will it pass Applicant Tracking Systems)
            - Experience level classification (entry-level, mid-career, senior professional)
            - Potential matching job roles
            
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
                }},
                "ats_readiness": {{
                    "score": (score 1-10),
                    "issues": [list of ATS issues],
                    "suggestions": [list of ATS optimization suggestions]
                }},
                "experience_level": {{
                    "classification": (entry-level, junior, mid-level, senior, executive),
                    "years_experience": (estimated years),
                    "career_stage": (brief description of career stage)
                }},
                "skills_assessment": {{
                    "technical_skills": [list of technical skills with ratings],
                    "soft_skills": [list of soft skills with ratings],
                    "skills_gaps": [potential skills gaps based on career goals or industry standards]
                }},
                "potential_roles": {{
                    "best_matches": [list of top 5 job roles that best match this CV],
                    "match_reasons": [brief explanations for why these roles are good matches],
                    "suggested_industries": [list of industries where this CV would be most competitive]
                }}
            }}
            
            Be specific, accurate, and actionable in your analysis.
            """
            
            # Make API request for analysis
            response = service.make_custom_request(prompt)
            
            if 'error' in response:
                return Response(response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # If we have a parsed_cv, store the analysis results
            if parser_type == 'parsed_cv' and parsed_cv:
                parsed_cv.analysis_data = response
                parsed_cv.analysis_date = timezone.now()
                parsed_cv.save(update_fields=['analysis_data', 'analysis_date'])
                logger.info(f"Stored analysis results for ParsedCV ID {cv_id}")
            
            return Response({
                'analysis': response,
                'cached': False,
                'analysis_date': timezone.now() if parser_type == 'parsed_cv' else None
            })
            
        except Exception as e:
            logger.error(f"Error analyzing CV: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['GET'])
    def download_parsed_data(self, request, pk=None):
        """Download the parsed CV data as JSON"""
        try:
            parsed_cv = self.get_object()
            
            if parsed_cv.status != 'completed':
                return Response({
                    'error': f'CV parsing is not completed. Current status: {parsed_cv.status}'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            return Response(parsed_cv.parsed_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in download_parsed_data: {e}")
            return Response({
                'error': f'Failed to retrieve parsed data: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rewrite_cv(request):
    """
    Endpoint to rewrite and improve CV content using DeepSeek.
    """
    try:
        # Get the CV data from the request
        cv_data = request.data
        if not cv_data:
            return Response(
                {'status': 'error', 'error': 'No CV data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create a rewrite session and immediately return the session ID
        # This avoids thread-related database issues by using the two-phase approach
        cv_id = cv_data.get('cv_id')
        if not cv_id:
            return Response(
                {'status': 'error', 'error': 'No CV ID provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create a rewrite session
        rewrite_session = CVRewriteSession.objects.create(
            user=request.user,
            cv_id=cv_id,
            status='initiated',
            input_data=json.dumps(cv_data)
        )
        
        # Start the processing in a separate thread
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            executor.submit(_process_rewrite_session_background, rewrite_session.id)
            
        return Response({
            'status': 'success', 
            'message': 'CV rewrite initiated successfully',
            'session_id': rewrite_session.id,
            'status_url': f"/api/ai_cv_parser/rewrite-status/{rewrite_session.id}/"
        }, status=status.HTTP_202_ACCEPTED)
            
    except Exception as e:
        logger.error(f"Error in rewrite_cv view: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def _process_rewrite_session_background(session_id):
    """
    Process a rewrite session in the background
    """
    try:
        # Get a fresh database connection for this thread
        close_old_connections()
        
        # Get the session
        rewrite_session = CVRewriteSession.objects.get(id=session_id)
        
        # Update status to processing
        rewrite_session.status = 'processing'
        rewrite_session.save(update_fields=['status'])
        
        try:
            # Parse the input data
            cv_data = json.loads(rewrite_session.input_data)
            
            # Initialize the service
            cv_rewrite_service = CVRewriteService()
            
            # Run synchronously in this thread
            result = cv_rewrite_service.rewrite_cv_sync(cv_data, rewrite_session.user)
            
            # Extract the new CV ID from the result if available
            new_cv_id = result.get('new_cv_id')
            
            # Update the session with the result and new CV ID
            rewrite_session.output_data = result
            rewrite_session.status = 'completed'
            
            # Only update new_cv_id if it's available
            if new_cv_id:
                rewrite_session.new_cv_id = new_cv_id
                rewrite_session.save(update_fields=['output_data', 'status', 'new_cv_id'])
                logger.info(f"Rewrite session {session_id} completed with new CV ID: {new_cv_id}")
            else:
                rewrite_session.save(update_fields=['output_data', 'status'])
                logger.warning(f"Rewrite session {session_id} completed but no new CV ID was provided")
            
        except Exception as process_error:
            logger.error(f"Error processing rewrite session {session_id}: {str(process_error)}", exc_info=True)
            rewrite_session.status = 'failed'
            rewrite_session.error_message = str(process_error)
            rewrite_session.save(update_fields=['status', 'error_message'])
    except Exception as outer_error:
        logger.error(f"Outer error in rewrite session background processing: {str(outer_error)}", exc_info=True)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rewrite_status(request, session_id):
    """
    Get the status of a CV rewrite session
    """
    try:
        rewrite_session = CVRewriteSession.objects.get(id=session_id, user=request.user)
        
        response_data = {
            'status': rewrite_session.status,
            'session_id': rewrite_session.id,
            'created_at': rewrite_session.created_at,
            'updated_at': rewrite_session.updated_at,
        }
        
        if rewrite_session.status == 'completed' and rewrite_session.output_data:
            response_data['result'] = rewrite_session.output_data
        
        if rewrite_session.status == 'failed' and rewrite_session.error_message:
            response_data['error'] = rewrite_session.error_message
            
        return Response(response_data, status=status.HTTP_200_OK)
        
    except CVRewriteSession.DoesNotExist:
        return Response(
            {'status': 'error', 'error': 'Rewrite session not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching rewrite session status: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_rewrite_session(request, session_id):
    """
    Phase 2: Process the AI rewriting for an existing session.
    This endpoint handles the long-running AI processing after
    a session has already been created.
    """
    # We'll use this helper function to execute the async code
    def process_session_async():
        return asyncio.run(_process_rewrite_session_async(request, session_id))
    
    try:
        # Run the async code in a synchronous context
        result = process_session_async()
        
        if result.get('status') == 'success':
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error processing rewrite session: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# This is the actual async implementation, separated from the view
async def _process_rewrite_session_async(request, session_id):
    """Internal async implementation for rewrite session processing"""
    try:
        # Get the session using sync_to_async to avoid async/sync context issues
        try:
            session = await sync_to_async(CVRewriteSession.objects.get)(id=session_id)
        except CVRewriteSession.DoesNotExist:
            return {
                'status': 'error',
                'error': f'Session with ID {session_id} not found'
            }
        
        # Check if session belongs to the current user
        if await sync_to_async(lambda: session.user.id != request.user.id)():
            return {
                'status': 'error',
                'error': 'You do not have permission to access this session'
            }
            
        # Process the session
        service = CVRewriteService()
        result = await service.process_rewrite_session(session)
        return result
            
    except Exception as e:
        logger.error(f"Error in async processing: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_cv(request, pk=None):
    """
    Analyze a CV to provide feedback on content quality and improvement suggestions.
    
    This endpoint accepts CV ID either in the URL (pk parameter) or in the request data.
    """
    logger.info(f"analyze_cv endpoint was called by user {request.user.username}")
    
    try:
        # Get the CV ID either from URL parameter or request data
        cv_id = pk  # From URL
        if not cv_id:
            cv_id = request.data.get('cv_id')  # From request body
            
        parser_type = request.data.get('parser_type', 'parsed_cv')
        
        logger.info(f"Analyzing CV with ID: {cv_id}, parser_type: {parser_type}")
        
        if not cv_id:
            logger.warning("No CV ID provided in analyze_cv request")
            return Response({
                'error': 'CV ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the CV data based on the parser type
        cv_data = None
        parsed_cv = None
        if parser_type == 'parsed_cv':
            # Get from the ai_cv_parser module
            try:
                from .models import ParsedCV
                parsed_cv = ParsedCV.objects.get(id=cv_id, user=request.user)
                cv_data = parsed_cv.parsed_data
                
                # Check if we already have analysis data and it's not too old (e.g., less than 7 days)
                if parsed_cv.analysis_data and parsed_cv.analysis_date and (timezone.now() - parsed_cv.analysis_date).days < 7:
                    # Return cached analysis
                    logger.info(f"Returning cached analysis for ParsedCV ID {cv_id}")
                    return Response({
                        'analysis': parsed_cv.analysis_data,
                        'cached': True,
                        'analysis_date': parsed_cv.analysis_date
                    })
                    
            except ParsedCV.DoesNotExist:
                # Try fallback to the legacy cv_parser module
                try:
                    from cv_parser.models import ParsedCV as LegacyParsedCV
                    legacy_cv = LegacyParsedCV.objects.get(id=cv_id, user=request.user)
                    cv_data = legacy_cv.parsed_data
                    logger.info(f"Found CV in legacy parser with ID {cv_id}")
                except Exception as legacy_error:
                    logger.error(f"CV not found in legacy parser either: {str(legacy_error)}")
                    return Response({
                        'error': 'CV not found or you do not have permission to access it'
                    }, status=status.HTTP_404_NOT_FOUND)
        elif parser_type == 'linkedin':
            # Get from the linkedin_parser module (if available)
            try:
                from linkedin_parser.models import LinkedInProfile
                linkedin_profile = LinkedInProfile.objects.get(id=cv_id, user=request.user)
                cv_data = linkedin_profile.profile_data
            except (ImportError, ModuleNotFoundError):
                logger.error("LinkedIn parser module not available")
                return Response({
                    'error': 'LinkedIn parser is not available'
                }, status=status.HTTP_501_NOT_IMPLEMENTED)
            except Exception as linkedin_error:
                logger.error(f"Error retrieving LinkedIn profile: {str(linkedin_error)}")
                return Response({
                    'error': 'LinkedIn profile not found or you do not have permission to access it'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'error': f'Invalid parser_type: {parser_type}'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not cv_data:
            return Response({
                'error': 'No CV data found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        # Prepare the prompt for analysis
        from .deepseek_service import DeepSeekService
        service = DeepSeekService()
        
        # Continue with existing prompt preparation
        prompt = f"""
        Please analyze this CV data and provide structured feedback on its strengths, weaknesses, and specific improvement suggestions.
        
        Evaluation criteria:
        - Content completeness
        - Format and structure
        - Skills relevance
        - Job history description quality
        - Education presentation
        - Overall impact
        - ATS readiness (will it pass Applicant Tracking Systems)
        - Experience level classification (entry-level, mid-career, senior professional)
        - Potential matching job roles
        
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
            }},
            "ats_readiness": {{
                "score": (score 1-10),
                "issues": [list of ATS issues],
                "suggestions": [list of ATS optimization suggestions]
            }},
            "experience_level": {{
                "classification": (entry-level, junior, mid-level, senior, executive),
                "years_experience": (estimated years),
                "career_stage": (brief description of career stage)
            }},
            "skills_assessment": {{
                "technical_skills": [list of technical skills with ratings],
                "soft_skills": [list of soft skills with ratings],
                "skills_gaps": [potential skills gaps based on career goals or industry standards]
            }},
            "potential_roles": {{
                "best_matches": [list of top 5 job roles that best match this CV],
                "match_reasons": [brief explanations for why these roles are good matches],
                "suggested_industries": [list of industries where this CV would be most competitive]
            }}
        }}
        
        Be specific, accurate, and actionable in your analysis.
        """
        
        # Make API request for analysis
        response = service.make_custom_request(prompt)
        
        if 'error' in response:
            return Response(response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # If we have a parsed_cv, store the analysis results
        if parser_type == 'parsed_cv' and parsed_cv:
            parsed_cv.analysis_data = response
            parsed_cv.analysis_date = timezone.now()
            parsed_cv.save(update_fields=['analysis_data', 'analysis_date'])
            logger.info(f"Stored analysis results for ParsedCV ID {cv_id}")
        
        return Response({
            'analysis': response,
            'cached': False,
            'analysis_date': timezone.now() if parser_type == 'parsed_cv' else None
        })
        
    except Exception as e:
        logger.error(f"Error analyzing CV: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(
            {'error': f'An unexpected error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_rewrite_session(request):
    """
    Create a new CV rewrite session.
    
    This endpoint initializes a rewrite session and returns the session ID,
    which can then be used to track progress and retrieve results.
    
    Request data should include:
    - cv_id: ID of the CV to rewrite
    
    Returns:
    - session_id: ID of the created session
    - status: Current status of the session (initially 'pending')
    """
    try:
        # Get CV ID from request data
        cv_id = request.data.get('cv_id')
        
        if not cv_id:
            return Response(
                {'error': 'CV ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the parsed CV
        try:
            parsed_cv = ParsedCV.objects.get(id=cv_id, user=request.user)
        except ParsedCV.DoesNotExist:
            return Response(
                {'error': 'Parsed CV not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create a rewrite session
        rewrite_session = CVRewriteSession.objects.create(
            user=request.user,
            cv_id=cv_id,
            status='pending',
            input_data={
                'cv_id': cv_id,
                'parsed_cv': ParsedCVSerializer(parsed_cv).data
            }
        )
        
        # Return the session ID
        return Response({
            'session_id': str(rewrite_session.id),
            'status': rewrite_session.status,
            'message': 'CV rewrite session created successfully',
            'created_at': rewrite_session.created_at
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Error creating rewrite session: {str(e)}", exc_info=True)
        return Response(
            {'error': f'Failed to create rewrite session: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
