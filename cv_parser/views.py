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
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .services import DeepSeekService

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
                logger.warning(f"No parsed data provided in transfer request from user {request.user.username}")
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

@require_http_methods(["POST"])
def parse_cv(request):
    """
    Handle CV file upload and parsing.
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'error': 'No file uploaded'
            }, status=400)
            
        file = request.FILES['file']
        if not file.name:
            return JsonResponse({
                'error': 'No file selected'
            }, status=400)
            
        # Validate file type
        allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if file.content_type not in allowed_types:
            return JsonResponse({
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            }, status=400)
            
        # Save file temporarily
        file_path = os.path.join(settings.MEDIA_ROOT, 'temp', file.name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
                
        # Parse the document
        service = DeepSeekService()
        result = service.parse_document(file_path)
        
        # Clean up temporary file
        os.remove(file_path)
        
        if 'error' in result:
            return JsonResponse(result, status=500)
            
        # Create ParsedCV object
        parsed_cv = ParsedCV.objects.create(
            user=request.user,
            original_file=file,
            parsed_data=result
        )
        
        return JsonResponse({
            'id': parsed_cv.id,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error processing CV: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=500)