from tokenize import blank_re
from django.db import models
from django.contrib.auth.models import User
from cv_writer.models import (
    CvWriter, Education, Experience, Skill, Language, Certification, Reference, ProfessionalSummary, Interest, SocialMedia
)
from .parsers import DocumentParser

# Create your models here.
class CVDocument(models.Model):
    """
    Stored uploaed CV documents and parsed status
    """

    DOCUMENT_TYPE_CHOICES = (
        ('pdf', 'PDF Document'),
        ('docx', 'Word Document'),
        ('linkedin', 'LinkedIn profile'),
    )

    PARSING_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )


    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cv_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to='cv_documents/', null=True, blank=True)
    linkedin_profile_url = models.URLField(null=True, blank=True)
    original_text = models.TextField(null=True, blank=True)
    parsed_data = models.JSONField(null=True, blank=True)
    parsing_status = models.CharField(max_length=25, choices=PARSING_STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)
    is_training_data = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s CV - {self.document_type}"

    def transfer_to_cv_writer(self, user):
        """
        Transfer parsed CV data to CV Writer app models
        """
        if not self.parsed_data:
            raise ValueError("No parsed data available")
            
        parsed_data = self.parsed_data

        # Create or update CV Writer
        from cv_writer.models import CvWriter
        cv_writer, created = CvWriter.objects.update_or_create(
            user=user,
            defaults={
                'first_name': parsed_data['personal_info'].get('first_name', ''),
                'last_name': parsed_data['personal_info'].get('last_name', ''),
                'address': parsed_data['personal_info'].get('address', ''),
                'city': parsed_data['personal_info'].get('city', ''),
                'country': parsed_data['personal_info'].get('country', ''),
                'contact_number': parsed_data['personal_info'].get('contact_number', ''),
                'additional_information': parsed_data.get('additional_info', '')
            }
        )

        # Create Professional Summary
        from cv_writer.models import ProfessionalSummary
        if parsed_data.get('professional_summary'):
            ProfessionalSummary.objects.update_or_create(
                user=user,
                defaults={'summary': parsed_data['professional_summary']}
            )

        # Create Education entries
        from cv_writer.models import Education
        for edu in parsed_data.get('education', []):
            Education.objects.create(
                user=user,
                school_name=edu.get('school', ''),
                degree=edu.get('degree', ''),
                field_of_study=edu.get('field', ''),
                start_date=edu.get('start_date'),
                end_date=edu.get('end_date'),
                current=edu.get('current', False)
            )

        # Create Experience entries
        from cv_writer.models import Experience
        for exp in parsed_data.get('experience', []):
            Experience.objects.create(
                user=user,
                company_name=exp.get('company', ''),
                job_title=exp.get('title', ''),
                job_description=exp.get('description', ''),
                achievements=exp.get('achievements', ''),
                start_date=exp.get('start_date'),
                end_date=exp.get('end_date'),
                employment_type=exp.get('type', 'Full-time'),
                current=exp.get('current', False)
            )

        # Create Skill entries
        from cv_writer.models import Skill
        for skill in parsed_data.get('skills', []):
            Skill.objects.create(
                user=user,
                skill_name=skill.get('name', ''),
                skill_level=skill.get('level', 'Intermediate')
            )

        # Create Certification entries
        from cv_writer.models import Certification
        for cert in parsed_data.get('certifications', []):
            Certification.objects.create(
                user=user,
                certificate_name=cert.get('name', ''),
                certificate_date=cert.get('date'),
                certificate_link=cert.get('link', '')
            )

        return cv_writer

    class Meta:
        ordering = ['-created_at']


class ParsingMetaData(models.Model):
    """
    Stores metadata about parsing attempts from model training
    """

    cv_document = models.ForeignKey(CVDocument, on_delete=models.CASCADE, related_name='parsing_metadata')
    processing_time = models.FloatField(help_text='Time taken to parse in seconds')
    confidence_score = models.FloatField(help_text='Confidence score of parsing results')
    extracted_fields = models.JSONField(help_text='List of successfully extracted fields')
    model_version = models.CharField(max_length=50, help_text='Version of the parsing model used')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Parsing metadata for {self.cv_document}"

    class Meta:
        ordering = ['-created_at']
