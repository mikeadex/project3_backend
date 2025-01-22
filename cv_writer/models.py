from django.db import models
from django.contrib.auth.models import User


class CvWriter(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="cv_writer"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=100)
    additional_information = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Education(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="education")
    school_name = models.CharField(max_length=100)
    degree = models.CharField(max_length=100)
    field_of_study = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school_name} - {self.degree}"

class ProfessionalSummary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="professional_summary")
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Professional summary for {self.user.username}"


class Interest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interest")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.user.username}"


class Experience(models.Model):
    EMPLOYMENT_TYPE = (
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Contract", "Contract"),
        ("Internship", "Internship"),
        ("Freelance", "Freelance"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="experience")
    company_name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    job_description = models.TextField()
    achievements = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    employment_type = models.CharField(max_length=100, choices=EMPLOYMENT_TYPE)
    current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} - {self.job_title}"


class Skill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="skill")
    skill_name = models.CharField(max_length=100)
    skill_level = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.skill_name


class Language(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="language")
    language_name = models.CharField(max_length=100)
    language_level = models.CharField(max_length=100)
    is_custom = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.language_name


class Certification(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="certification"
    )
    certificate_name = models.CharField(max_length=100)
    certificate_date = models.DateField()
    certificate_link = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.certificate_name} - {self.certificate_date}"


class Reference(models.Model):
    REFERENCE_TYPES = (
        ("Professional", "Professional"),
        ("Academic", "Academic"),
        ("Personal", "Personal"),
        ("Character", "Character"),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reference")
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    company = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    reference_type = models.CharField(max_length=20, choices=REFERENCE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.company}"


class SocialMedia(models.Model):
    PLATFORM_CHOICES = (
        ("LinkedIn", "LinkedIn"),
        ("GitHub", "GitHub"),
        ("Twitter", "Twitter"),
        ("Portfolio", "Portfolio"),
        ("Behance", "Behance"),
        ("Dribbble", "Dribbble"),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_media")
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'platform')

    def __str__(self):
        return f"{self.user.username} - {self.platform}"
