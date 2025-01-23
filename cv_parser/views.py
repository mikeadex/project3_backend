from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CVDocument
from .parsers import DocumentParser
from rest_framework.parsers import MultiPartParser, FormParser
import os


class CVParserViewSet(viewsets.ModelViewSet):
    queryset = CVDocument.objects.all()
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['POST'])
    def parse_document(self, request):
        try:
            file_obj = request.FILES['file']
            file_extension = os.path.splitext(file_obj.name)[1].lower()

            # Create CVDocument instance
            cv_document = CVDocument.objects.create(
                user=request.user,
                document_type='pdf' if file_extension == '.pdf' else 'docx',
                file=file_obj
            )

            # Parse document
            parser = DocumentParser()
            if file_extension == '.pdf':
                text = parser.parse_pdf(cv_document.file.path)
            else:
                text = parser.parse_docx(cv_document.file.path)

            # Store original text
            cv_document.original_text = text
            
            # Extract structured data
            parsed_data = parser.extract_sections(text)
            cv_document.parsed_data = parsed_data
            cv_document.parsing_status = 'completed'
            cv_document.save()

            # Transfer to cv_writer models
            cv_document.transfer_to_cv_writer(user=request.user)

            return Response({
                'message': 'Document parsed successfully',
                'data': parsed_data
            })

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)