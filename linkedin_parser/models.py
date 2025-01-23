from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings

# Create your models here.

class LinkedInProfile(models.Model):
    """Model for storing LinkedIn profile data"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    linkedin_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Profile Data
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    headline = models.TextField(null=True, blank=True)
    vanity_name = models.CharField(max_length=255, null=True, blank=True)
    profile_picture_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email}'s LinkedIn Profile"

    class Meta:
        verbose_name = "LinkedIn Profile"
        verbose_name_plural = "LinkedIn Profiles"

    @property
    def full_name(self):
        """Get full name from first and last name"""
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return None

    @property
    def linkedin_url(self):
        """Get LinkedIn profile URL"""
        if self.vanity_name:
            return f"https://www.linkedin.com/in/{self.vanity_name}"
        return None


class LinkedInEducation(models.Model):
    profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE, related_name='education')
    school_name = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, null=True, blank=True)
    field_of_study = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school_name} - {self.degree or 'No degree'}"

    class Meta:
        verbose_name = "Education"
        verbose_name_plural = "Education"
        ordering = ['-end_date', '-start_date']


class LinkedInExperience(models.Model):
    profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE, related_name='experience')
    company_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} - {self.title}"

    class Meta:
        verbose_name = "Experience"
        verbose_name_plural = "Experience"
        ordering = ['-end_date', '-start_date']


class LinkedInSkill(models.Model):
    PROFICIENCY_CHOICES = [
        ('BEGINNER', 'Beginner'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('EXPERT', 'Expert')
    ]

    profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=255)
    proficiency_level = models.CharField(
        max_length=20,
        choices=PROFICIENCY_CHOICES,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.proficiency_level or 'No level'})"

    class Meta:
        verbose_name = "Skill"
        verbose_name_plural = "Skills"
        ordering = ['name']


class LinkedInCertification(models.Model):
    profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE, related_name='certifications')
    name = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255)
    issue_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    credential_id = models.CharField(max_length=255, null=True, blank=True)
    credential_url = models.URLField(max_length=255, null=True, blank=True)
    linkedin_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.issuing_organization}"


class LinkedInLanguage(models.Model):
    PROFICIENCY_LEVELS = [
        ('elementary', 'Elementary'),
        ('limited_working', 'Limited Working'),
        ('professional_working', 'Professional Working'),
        ('full_professional', 'Full Professional'),
        ('native_bilingual', 'Native or Bilingual')
    ]

    profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE, related_name='languages')
    name = models.CharField(max_length=100)
    proficiency = models.CharField(max_length=50, choices=PROFICIENCY_LEVELS, null=True, blank=True)
    linkedin_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.proficiency}"
