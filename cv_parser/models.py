from tokenize import blank_re
from django.db import models
from django.contrib.auth.models import User
from cv_writer.models import (
    CvWriter, Education, Experience, Skill, Language, Certification, Reference, ProfessionalSummary, Interest, SocialMedia
)

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

    def transfer_to_cv_writer(self):
        """
        Transfer cleaned data to cv_writer models
        """
        if not self.parsed_data:
            raise ValueError("No parsed data available")

        data = self.parsed_data

        # Create or update cvWriter 
        cv_writer, _ = CvWriter.objects.update_or_create(
            user = self.user,
            defaults = {
                'first_name': data.get('first_name', ''),
                'last_name': data.get('last_name', ''),
                'address': data.get('address', ''),
                'city': data.get('city', ''),
                'country': data.get('country', ''),
                'contact_number': data.get('contact_number', ''),
                'additional_information': data.get('additional_information', ''),
            }
        )

        #  Professional Summary
        if 'professional_summary' in data:
            ProfessionalSummary.objects.update_or_create(
                user=self.user,
                defaults={'summary': data['professional_summary']}
            )

        #  Education 
        if 'education' in data:
            for edu in data['education']:
                Education.objects.update_or_create(
                user=self.user,
                school_name=edu.get('school', ''),
                degree=edu.get('degree', ''),
                field_of_study=edu.get('field', ''),
                start_date=edu.get('start_date'),
                end_date=edu.get('end_date'),
                current=edu.get('current', False),
                )

        # Work Experience
        if 'experience' in data:
            for exp in data['experience']:
                Experience.objects.update_or_create(
                    user=self.user,
                    company_name=exp.get('company', ''),
                    job_title=exp.get('title', ''),
                    job_description=exp.get('description', ''),
                    achievements=exp.get('achievements', ''),
                    start_date=exp.get('start_date'),
                    end_date=exp.get('end_date'),
                    employment_type=exp.get('type', 'Full-time'),
                    current=exp.get('current', False)
                )
        
        #  Skills
        if 'skills' in data:
            for skill in data['skills']:
                Skill.objects.create(
                    user=self.user,
                    skill_name=skill.get('name', ''),
                    skill_level=skill.get('level', 'Intermediate')
                )

        # Languages
        if 'languages' in data:
            for lang in data['languages']:
                Language.objects.create(
                    user=self.user,
                    language_name=lang.get('name', ''),
                    language_level=lang.get('level', 'Intermediate')
                )

        # Create Certifications
        if 'certifications' in data:
            for cert in data['certifications']:
                Certification.objects.create(
                    user=self.user,
                    certificate_name=cert.get('name', ''),
                    certificate_date=cert.get('date'),
                    certificate_link=cert.get('link', '')
                )

        # Create References
        if 'references' in data:
            for ref in data['references']:
                Reference.objects.create(
                    user=self.user,
                    name=ref.get('name', ''),
                    title=ref.get('title', ''),
                    company=ref.get('company', ''),
                    email=ref.get('email', ''),
                    phone=ref.get('phone', ''),
                    reference_type=ref.get('type', 'Professional')
                )

        # Create Social Media
        if 'social_media' in data:
            for social in data['social_media']:
                SocialMedia.objects.create(
                    user=self.user,
                    platform=social.get('platform', ''),
                    url=social.get('url', '')
                )

        self.parsing_status = 'completed'
        self.save()

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
