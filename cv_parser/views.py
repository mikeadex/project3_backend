from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CVDocument
from .parsers import DocumentParser
from rest_framework.parsers import MultiPartParser, FormParser
import os
import logging

logger = logging.getLogger(__name__)

class CVParserViewSet(viewsets.ModelViewSet):
    queryset = CVDocument.objects.all()
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['POST'])
    def parse_document(self, request):
        try:
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return Response({
                    'error': 'Authentication required'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Validate file upload
            if 'file' not in request.FILES:
                return Response({
                    'error': 'No file uploaded'
                }, status=status.HTTP_400_BAD_REQUEST)

            file_obj = request.FILES['file']
            file_extension = os.path.splitext(file_obj.name)[1].lower()

            # Validate file type
            if file_extension not in ['.pdf', '.docx']:
                return Response({
                    'error': 'Unsupported file type. Only PDF and DOCX are allowed.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create CVDocument instance
            cv_document = CVDocument.objects.create(
                user=request.user,
                document_type='pdf' if file_extension == '.pdf' else 'docx',
                file=file_obj,
                parsing_status='processing'
            )

            # Parse document
            parser = DocumentParser()
            try:
                if file_extension == '.pdf':
                    text = parser.parse_pdf(cv_document.file.path)
                else:
                    text = parser.parse_docx(cv_document.file.path)
            except Exception as parse_error:
                cv_document.parsing_status = 'failed'
                cv_document.error_message = str(parse_error)
                cv_document.save()
                logger.error(f"Document parsing failed: {parse_error}")
                return Response({
                    'error': f'Failed to parse document: {parse_error}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Store original text
            cv_document.original_text = text
            
            # Extract structured data
            try:
                parsed_data = parser.parse_document(cv_document.file.path, 'pdf' if file_extension == '.pdf' else 'docx')
                cv_document.parsed_data = parsed_data
                cv_document.parsing_status = 'completed'
                cv_document.save()
            except Exception as parse_error:
                cv_document.parsing_status = 'failed'
                cv_document.error_message = str(parse_error)
                cv_document.save()
                logger.error(f"Failed to extract structured data: {parse_error}")
                return Response({
                    'error': f'Failed to extract structured data: {parse_error}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Transfer to cv_writer models
            try:
                cv_document.transfer_to_cv_writer(user=request.user)
            except Exception as transfer_error:
                logger.warning(f"Failed to transfer to CV writer: {transfer_error}")
                # Not a critical error, so we'll still return the parsed data

            return Response({
                'message': 'Document parsed successfully',
                'data': parsed_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error in parse_document: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)