from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import logging
import tempfile
import time
from datetime import datetime
from django.utils import timezone
import traceback
import json
from docx import Document
from PyPDF2 import PdfReader
import asyncio
from django.db import close_old_connections
from asgiref.sync import sync_to_async

from .models import ParsedCV
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
