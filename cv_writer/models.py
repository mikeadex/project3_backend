from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class CvWriter(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    VISIBILITY_CHOICES = (
        ('private', 'Private'),
        ('public', 'Public'),
        ('shared', 'Shared'),
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="cv_versions"
    )
    # Personal Information from CV Parser
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=100)
    additional_information = models.TextField(null=True, blank=True)
    
    # New fields for LinkedIn integration
    title = models.CharField(max_length=200, null=True, blank=True)
    slug = models.SlugField(max_length=200, null=True, blank=True, unique=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', null=True, blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parent_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='variants')
    version_name = models.CharField(max_length=100, blank=True, null=True, default='Version 1')
    version_purpose = models.CharField(max_length=200, blank=True, null=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        version_info = f" - {self.version_name}" if self.version_name else ""
        return f"{self.first_name} {self.last_name}'s CV{version_info}"
        
    def save(self, *args, **kwargs):
        # If this is the first version for the user, set as primary
        if not self.pk:  # Only on first save
            existing_versions = CvWriter.objects.filter(user=self.user).count()
            if existing_versions == 0:
                self.is_primary = True
                self.version_name = 'Version 1'
            else:
                # Ensure unique version name
                base_name = 'Version'
                counter = 2  # Start from 2 since first version is already 'Version 1'
                while CvWriter.objects.filter(user=self.user, version_name=f'{base_name} {counter}').exists():
                    counter += 1
                self.version_name = f'{base_name} {counter}'

        # Generate slug if not provided
        if not self.slug:
            base_slug = slugify(f"{self.first_name}-{self.last_name}-cv")
            unique_slug = base_slug
            counter = 1
            # Ensure unique slug
            while CvWriter.objects.filter(slug=unique_slug).exclude(id=self.id).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug

        super().save(*args, **kwargs)

    def clone(self):
        # Create a new version based on this CV
        base_name = f"{self.version_name} - Copy" if self.version_name else "New Version"
        counter = 1
        unique_name = base_name
        while CvWriter.objects.filter(user=self.user, version_name=unique_name).exists():
            unique_name = f"{base_name} {counter}"
            counter += 1

        return CvWriter.objects.create(
            user=self.user,
            first_name=self.first_name,
            last_name=self.last_name,
            address=self.address,
            city=self.city,
            country=self.country,
            contact_number=self.contact_number,
            additional_information=self.additional_information,
            title=f"{self.title} - Copy",
            description=self.description,
            status=self.status,
            visibility=self.visibility,
            parent_version=self,
            version_name=unique_name,
            version_purpose=self.version_purpose,
            is_primary=False
        )

    class Meta:
        verbose_name_plural = 'CV Writers'
        ordering = ['-created_at']
        # Remove unique constraint on user
        # unique_together = ['user']  # Commented out to allow multiple versions


class CVImprovement(models.Model):
    cv = models.ForeignKey(CvWriter, on_delete=models.CASCADE, related_name='improvements')
    section = models.CharField(max_length=50, choices=[
        ('professional_summary', 'Professional Summary'),
        ('experience', 'Experience'),
        ('education', 'Education'),
        ('skills', 'Skills'),
        ('certifications', 'Certifications'),
        ('languages', 'Languages'),
        ('interests', 'Interests')
    ])
    original_content = models.TextField()
    improved_content = models.TextField()
    improvement_type = models.CharField(max_length=20, choices=[
        ('minimal', 'Quick Improvement'),
        ('full', 'Deep Improvement')
    ])
    tokens_used = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.cv.user.email} - {self.section} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Education(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="education")
    school_name = models.CharField(max_length=100)
    degree = models.CharField(max_length=100)
    field_of_study = models.CharField(max_length=100)
    start_date = models.DateField(null=True, blank=True)
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
    start_date = models.DateField(null=True, blank=True)
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
    certificate_date = models.DateField(null=True, blank=True)
    certificate_link = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.certificate_name}"


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
