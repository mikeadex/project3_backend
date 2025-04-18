from django.db import models, transaction, connection, close_old_connections
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.db.utils import OperationalError, InterfaceError
from datetime import datetime
import logging
import time
import django

User = get_user_model()


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
    
    # Template selection
    template = models.ForeignKey('CVTemplate', null=True, blank=True, on_delete=models.SET_NULL, related_name='cvs')
    
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
        # Check if this is a new CV (no ID yet)
        is_new = self.pk is None
        
        if is_new:
            try:
                # Get count of existing CVs for this user
                close_old_connections()
                
                try:
                    # Use transaction to ensure atomicity
                    with transaction.atomic():
                        existing_versions = CvWriter.objects.filter(user=self.user).count()
                        
                        # Set title to include version number if not already set 
                        if not self.title or self.title == "Untitled":
                            self.title = f"My CV #{existing_versions + 1}"
                except OperationalError:
                    # If there's a connection error, use a fallback title with timestamp
                    self.title = f"My CV ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
            except Exception as e:
                # Fallback in case of any other errors
                logger = logging.getLogger('cv_writer')
                logger.error(f"Error setting CV title: {str(e)}")
                
                if not self.title or self.title == "Untitled":
                    self.title = f"My CV ({int(time.time())})"
        
        try:
            if not self.version_name:
                # If no version name is set, try to set a default one
                try:
                    # Make sure title is set to something valid
                    if not self.title or len(self.title.strip()) == 0:
                        self.title = f"My CV ({int(time.time())})"
                    
                    # Use timestamp to ensure uniqueness
                    timestamp = int(time.time())
                    self.version_name = f"{self.title} ({timestamp})"
                except Exception as e:
                    # Log error but don't stop saving
                    logger.error(f"Error setting CV title: {str(e)}")
                    
                    if not self.title or self.title == "Untitled":
                        self.title = f"My CV ({int(time.time())})"
        except Exception as e:
            # Log but continue with save
            logger.warning(f"Error in pre-save processing: {str(e)}")
        
        # Call the original save method with retry logic
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                # Make sure we have a fresh connection before saving
                # Import at the module level to avoid scope issues
                from django.db import close_old_connections
                close_old_connections()
                
                # Attempt the save
                super().save(*args, **kwargs)
                return  # Success, exit the retry loop
            except InterfaceError as e:
                # Handle "connection already closed" errors
                retry_count += 1
                last_error = e
                
                if retry_count < max_retries:
                    logger.warning(f"Database connection error in CV save, retrying ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(0.5 * retry_count)  # Small delay before retry
                    
                    # Try to reconnect explicitly
                    from django.db import connection
                    connection.close()
                    try:
                        connection.connect()
                    except Exception as conn_err:
                        logger.warning(f"Error reconnecting to database: {str(conn_err)}")
                else:
                    # Final retry failed
                    logger.error(f"Failed to save CV after {max_retries} attempts: {str(e)}")
                    raise
            except Exception as e:
                # For other exceptions, don't retry
                logger.error(f"Error saving CV: {str(e)}")
                raise

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


class CVTemplate(models.Model):
    """Model for CV templates available in the system"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    preview_image = models.URLField(blank=True)
    
    # Template configuration - could be extended with specific options
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    # Template category/classification
    category = models.CharField(max_length=50, blank=True, choices=[
        ('modern', 'Modern'),
        ('classic', 'Classic'),
        ('creative', 'Creative'),
        ('professional', 'Professional'),
        ('technical', 'Technical')
    ])
    
    # Template customization options
    has_color_options = models.BooleanField(default=False)
    has_font_options = models.BooleanField(default=False)
    has_layout_options = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = "CV Template"
        verbose_name_plural = "CV Templates"


class CVTemplateSelection(models.Model):
    """Model to store user's template selections and preferences"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='template_selections')
    cv = models.ForeignKey(CvWriter, on_delete=models.CASCADE, related_name='template_selections')
    template = models.ForeignKey(CVTemplate, on_delete=models.CASCADE)
    
    # Template customization preferences
    color_scheme = models.CharField(max_length=50, blank=True)
    font_choice = models.CharField(max_length=50, blank=True)
    layout_option = models.CharField(max_length=50, blank=True)
    
    # Additional customizations
    custom_css = models.TextField(blank=True)
    custom_settings = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s template selection for CV #{self.cv.id}"
    
    class Meta:
        unique_together = ['user', 'cv']
        verbose_name = "Template Selection"
        verbose_name_plural = "Template Selections"


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
    cv = models.ForeignKey('CvWriter', on_delete=models.CASCADE, related_name="professional_summary", blank=True, null=True)
    summary = models.TextField(help_text="Professional summary of the CV")
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
