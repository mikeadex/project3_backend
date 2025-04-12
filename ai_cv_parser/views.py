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
    
    @action(detail=False, methods=['POST'], url_path='parse')
    def parse_cv(self, request):
        """
        Parse a CV file and extract structured information.
        """
        try:
            logger.info(f"CV parsing request from user {request.user.username} (ID: {request.user.id})")
            
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            file = request.FILES['file']
            logger.info(f"Received file: {file.name} (size: {file.size} bytes)")

            # Create ParsedCV record
            parsed_cv = ParsedCV.objects.create(
                user=request.user,
                file_name=file.name,
                file_size=file.size,
                status='processing'
            )
            logger.info(f"ParsedCV record {parsed_cv.id} created for user {request.user.username} - Status: processing")

            # Save uploaded file to temporary location
            temp_path = self.save_uploaded_file(file)
            logger.info(f"Saved uploaded file to temporary location: {temp_path}")

            try:
                # Extract text from PDF
                text = self.extract_text_from_file(temp_path)
                logger.info(f"Text extracted from document: {len(text)} characters")

                # Update ParsedCV with extracted text
                parsed_cv.extracted_text = text
                parsed_cv.save()
                logger.info(f"ParsedCV record {parsed_cv.id} updated for user {request.user.username} - Status: processing")

                # Parse CV with DeepSeek
                parser = DeepSeekService()
                
                # Create event loop for async operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    parsed_data = loop.run_until_complete(parser.parse_cv(text))
                    logger.info("Successfully parsed CV with DeepSeek")
                finally:
                    loop.close()

                # Update ParsedCV with parsed data
                parsed_cv.parsed_data = parsed_data
                parsed_cv.status = 'completed'
                parsed_cv.processed_at = timezone.now()
                parsed_cv.save()
                logger.info(f"ParsedCV record {parsed_cv.id} updated for user {request.user.username} - Status: completed")

                # Clean up temporary file
                os.remove(temp_path)
                logger.info(f"Removed temporary file: {temp_path}")

                return Response({
                    'status': 'success',
                    'message': 'CV parsed successfully',
                    'data': parsed_data
                })

            except Exception as e:
                logger.error(f"Error parsing CV with DeepSeek: {str(e)}")
                parsed_cv.status = 'failed'
                parsed_cv.error_message = str(e)
                parsed_cv.save()
                raise

        except Exception as e:
            logger.error(f"Unexpected error in parse_cv: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
                    summary=parsed_data.get('professional_summary')
                )
            
            # Create experiences if available
            if parsed_data.get('experience'):
                for exp_data in parsed_data.get('experience'):
                    Experience.objects.create(
                        user=request.user,
                        cv=cv_writer,
                        job_title=exp_data.get('job_title', ''),
                        company_name=exp_data.get('company', ''),
                        location=exp_data.get('location', ''),
                        start_date=exp_data.get('start_date', ''),
                        end_date=exp_data.get('end_date', ''),
                        job_description=exp_data.get('description', '')
                    )
            
            # Create education entries if available
            if parsed_data.get('education'):
                for edu_data in parsed_data.get('education'):
                    Education.objects.create(
                        user=request.user,
                        cv=cv_writer,
                        school_name=edu_data.get('school', ''),
                        degree=edu_data.get('degree', ''),
                        field_of_study=edu_data.get('field', ''),
                        start_date=edu_data.get('start_date', ''),
                        end_date=edu_data.get('end_date', ''),
                        details=edu_data.get('description', '')
                    )
            
            # Create skills if available
            if parsed_data.get('skills'):
                for skill_data in parsed_data.get('skills'):
                    if isinstance(skill_data, dict):
                        Skill.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            name=skill_data.get('name', ''),
                            level=skill_data.get('level', 'Intermediate'),
                            category="Technical Skills"
                        )
                    elif isinstance(skill_data, str):
                        Skill.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            name=skill_data,
                            level='Intermediate',
                            category="General"
                        )
            
            # Create languages if available
            if parsed_data.get('languages'):
                for lang_data in parsed_data.get('languages'):
                    if isinstance(lang_data, dict):
                        Language.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            language=lang_data.get('language', ''),
                            proficiency=lang_data.get('level', 'Intermediate')
                        )
                    elif isinstance(lang_data, str):
                        Language.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            language=lang_data,
                            proficiency='Intermediate'
                        )
            
            # Create certifications if available
            if parsed_data.get('certifications'):
                for cert_data in parsed_data.get('certifications'):
                    if isinstance(cert_data, dict):
                        Certification.objects.create(
                            user=request.user,
                            cv=cv_writer,
                            name=cert_data.get('name', ''),
                            issuer=cert_data.get('issuer', ''),
                            date=cert_data.get('date', '')
                        )
            
            logger.info(f"Data successfully transferred to CV Writer with ID: {cv_writer.id}")
            return Response({
                'message': 'Data successfully transferred to CV Writer',
                'cv_id': cv_writer.id
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in transfer_to_writer: {e}")
            logger.error(traceback.format_exc())
            return Response({
                'error': f'Failed to transfer data: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    @action(detail=False, methods=['post'])
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
            if parser_type == 'parsed_cv':
                # Get from the cv_parser module
                from cv_parser.models import ParsedCV
                try:
                    parsed_cv = ParsedCV.objects.get(id=cv_id, user=request.user)
                    cv_data = parsed_cv.parsed_data
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
                    'error': 'Invalid parser type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # If we don't have CV data, return an error
            if not cv_data:
                return Response({
                    'error': 'Failed to retrieve CV data'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Initialize response data with default structure
            analysis_data = {
                "overall_score": 5,
                "strengths": [],
                "weaknesses": [],
                "improvement_suggestions": [],
                "section_scores": {
                    "content_completeness": 5,
                    "format_structure": 5,
                    "skills_relevance": 5,
                    "job_history": 5,
                    "education": 5,
                    "overall_impact": 5
                },
                "ats_readiness": {
                    "score": 5,
                    "issues": [],
                    "suggestions": []
                },
                "experience_level": {
                    "classification": "unknown",
                    "years_experience": 0,
                    "career_stage": "Unable to determine due to AI service error"
                },
                "skills_assessment": {
                    "technical_skills": [],
                    "soft_skills": [],
                    "skills_gaps": []
                },
                "potential_roles": {
                    "best_matches": [],
                    "match_reasons": [],
                    "suggested_industries": []
                },
                "ai_service_error": False
            }
            
            # Analyze employment gaps separately using our dedicated analyzer
            # This will work even if the DeepSeek API fails
            from .employment_gaps import analyze_employment_gaps
            try:
                employment_gaps_analysis = analyze_employment_gaps(cv_data)
                logger.info(f"Employment gaps analysis completed: {len(employment_gaps_analysis.get('gaps', []))} gaps found")
                
                # Add employment gaps analysis to the response data
                analysis_data['employment_gaps'] = employment_gaps_analysis
            except Exception as e:
                logger.error(f"Error analyzing employment gaps: {str(e)}")
                analysis_data['employment_gaps'] = {
                    "summary": "Employment gaps analysis failed due to an error.",
                    "gaps": [],
                    "has_significant_gaps": False,
                    "error": str(e)
                }
            
            # Try to get AI analysis from DeepSeek, but continue even if it fails
            ai_analysis_successful = False
            try:
                # Use DeepSeek service to analyze CV
                from .deepseek_service import DeepSeekService
                service = DeepSeekService()
                
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
                
                # Since DeepSeekService uses async methods, we need to run it in an event loop
                import asyncio
                
                # Call the async generate method and wait for the result
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(service.generate(prompt, temperature=0.7, max_tokens=2000))
                    
                    # Try to extract JSON from the response
                    try:
                        # First try direct JSON parsing
                        ai_data = json.loads(result)
                        
                        # Update the main analysis data with AI results
                        for key, value in ai_data.items():
                            # Don't overwrite employment gaps data
                            if key != 'employment_gaps':
                                analysis_data[key] = value
                        
                        ai_analysis_successful = True
                    except json.JSONDecodeError:
                        # If that fails, try to extract JSON from markdown code blocks
                        try:
                            # Look for content between ```json and ``` markers
                            if "```json" in result:
                                json_start = result.find("```json") + 7
                                json_end = result.find("```", json_start)
                                if json_end > json_start:
                                    json_content = result[json_start:json_end].strip()
                                    ai_data = json.loads(json_content)
                                    
                                    # Update the main analysis data with AI results
                                    for key, value in ai_data.items():
                                        # Don't overwrite employment gaps data
                                        if key != 'employment_gaps':
                                            analysis_data[key] = value
                                    
                                    ai_analysis_successful = True
                                else:
                                    raise ValueError("Could not find closing JSON code block")
                            # Try to find any JSON-like structure with braces
                            elif "{" in result and "}" in result:
                                json_start = result.find("{")
                                json_end = result.rfind("}") + 1
                                if json_end > json_start:
                                    json_content = result[json_start:json_end].strip()
                                    ai_data = json.loads(json_content)
                                    
                                    # Update the main analysis data with AI results
                                    for key, value in ai_data.items():
                                        # Don't overwrite employment gaps data
                                        if key != 'employment_gaps':
                                            analysis_data[key] = value
                                    
                                    ai_analysis_successful = True
                                else:
                                    raise ValueError("Could not extract valid JSON from content")
                            else:
                                raise ValueError("Response does not contain any JSON structure")
                        except (ValueError, json.JSONDecodeError) as e:
                            logger.error(f"Failed to extract JSON from DeepSeek response: {str(e)}")
                            # Try fallback service instead
                            raise Exception("Falling back to alternative AI service")
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"DeepSeek API unavailable, using fallback service: {str(e)}")
                analysis_data['ai_service_error'] = True
                analysis_data['ai_error_message'] = str(e)
                
                # Try fallback service as a backup
                try:
                    from .fallback_service import FallbackService
                    fallback = FallbackService()
                    
                    # Use the same prompt for consistency
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        logger.info("Attempting to use fallback AI service")
                        fallback_result = loop.run_until_complete(fallback.generate(prompt, temperature=0.7, max_tokens=2000))
                        
                        # Try to parse the fallback response
                        try:
                            fallback_data = json.loads(fallback_result)
                            
                            # Update the analysis data with fallback results
                            for key, value in fallback_data.items():
                                # Don't overwrite employment gaps data
                                if key != 'employment_gaps':
                                    analysis_data[key] = value
                            
                            # Mark as successful with fallback service note
                            ai_analysis_successful = True
                            analysis_data['ai_service_note'] = "Using fallback AI service due to DeepSeek API issues"
                            analysis_data['ai_service_error'] = False  # Clear the error since fallback worked
                            
                            logger.info("Successfully used fallback AI service")
                        except json.JSONDecodeError as je:
                            logger.error(f"Failed to parse fallback service response: {str(je)}")
                            # Keep original error state
                    finally:
                        loop.close()
                except Exception as fallback_error:
                    logger.error(f"Fallback service also failed: {str(fallback_error)}")
                    # Keep original error state
            
            # If AI analysis failed, add a notice in the response
            if not ai_analysis_successful:
                analysis_data['notification'] = "The AI-powered analysis is currently unavailable. Employment gaps analysis is still provided."
            
            return Response(analysis_data)
            
        except Exception as e:
            logger.error(f"Error analyzing CV: {str(e)}")
            logger.error(traceback.format_exc())
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        # Close any stale connections before starting
        close_old_connections()
        
        # Get the CV data from the request
        cv_data = request.data
        if not cv_data:
            return Response(
                {'status': 'error', 'error': 'No CV data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize the service
        cv_rewrite_service = CVRewriteService()
        
        # Create a new event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Close old connections before async operation
            close_old_connections()
            
            # Run the async operation
            result = loop.run_until_complete(cv_rewrite_service.rewrite_cv(cv_data, request.user))
            
            # Log the response structure
            logger.info(f"CV rewrite response structure: {result}")
            
            # Check result status to determine the appropriate HTTP status code
            if result.get('status') == 'success':
                return Response(result, status=status.HTTP_200_OK)
            elif result.get('status') == 'partial_success':
                # For partial success, return 200 but with the partial_success structure
                return Response(result, status=status.HTTP_200_OK)
            else:
                # Any other status is treated as an error
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        finally:
            loop.close()
            close_old_connections()
            
    except Exception as e:
        logger.error(f"Error in rewrite_cv view: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_rewrite_session(request):
    """
    Phase 1: Create a temporary session for CV rewriting.
    This endpoint quickly creates a database record and returns a session ID
    before any AI processing begins.
    """
    try:
        # Get CV data from request
        data = request.data.get('data', {})
        
        if not data:
            return Response(
                {'status': 'error', 'error': 'No CV data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create a new session record
        session = CVRewriteSession.objects.create(
            user=request.user,
            input_data=data,
            status='pending'
        )
        
        logger.info(f"Created CV rewrite session {session.id} for user {request.user.username}")
        
        return Response({
            'status': 'success',
            'message': 'CV rewrite session created',
            'session_id': session.id
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating CV rewrite session: {str(e)}", exc_info=True)
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
