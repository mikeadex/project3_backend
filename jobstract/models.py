from tabnanny import verbose
from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Employer(models.Model):
    employer_name = models.CharField(max_length=255)
    employer_website = models.URLField(null=True, blank=True)
    is_nonprofit = models.BooleanField(default=False)
    charity_number = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.employer_name

class Opportunity(models.Model):
    OPPORTUNITY_TYPES = (
        ('internship', 'Internship'),
        ('job', 'Job'),
        ('volunteer', 'Volunteer'),
    )
    JOB_MODE = (
        ('on_site', 'On Site'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    )

    TIME_COMMITMENT = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('flexible', 'Flexible'),
        ('one_off', 'One Off'),
        ('occasional', 'Occasional'),
    )

    EXPERIENCE_LEVEL = (
        ('entry_level', 'Entry Level'),
        ('junior', 'Junior'),
        ('mid', 'Mid Level'),
        ('senior', 'Senior'),
        ('lead', 'Lead'),
        ('manager', 'Manager'),
        ('director', 'Director'),
        ('executive', 'Executive'),
        ('no_experience', 'No Experience Required'),
    )

    employer = models.ForeignKey(Employer, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    opportunity_type = models.CharField(max_length=20, choices=OPPORTUNITY_TYPES, default='job')
    mode = models.CharField(max_length=20, choices=JOB_MODE)
    time_commitment = models.CharField(max_length=20, choices=TIME_COMMITMENT)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL, default='no_experience')

    # Fields may be null or blank for volunteer position
    salary_range = models.CharField(max_length=100, null=True, blank=True)
    expenses_paid = models.BooleanField(default=False)

    # Common fields
    skills_required = models.TextField(blank=True)
    skills_gained = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    date_posted = models.DateField()
    application_url = models.URLField()
    source = models.URLField()

    # metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_opportunity_type_display()}) at {self.employer.employer_name}"

    class Meta:
        verbose_name_plural = 'Opportunities'
        ordering = ['-date_posted']

class JobApplication(models.Model):
    STATUS_CHOICES = (
        ('applied', 'Applied'),
        ('screening', 'Screening'),
        ('interview', 'Interview'),
        ('offer', 'Offer'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_applications')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    applied_date = models.DateTimeField(auto_now_add=True)
    cv_used = models.ForeignKey('cv_writer.CvWriter', on_delete=models.SET_NULL, null=True, blank=True)
    cover_letter = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    next_follow_up = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_date']
        unique_together = ['user', 'opportunity']

    def __str__(self):
        return f"{self.user.username}'s application for {self.opportunity.title}"

class ApplicationEvent(models.Model):
    EVENT_TYPES = (
        ('status_change', 'Status Change'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('interview_completed', 'Interview Completed'),
        ('offer_received', 'Offer Received'),
        ('note_added', 'Note Added'),
        ('follow_up', 'Follow Up'),
    )

    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    event_date = models.DateTimeField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-event_date']

    def __str__(self):
        return f"{self.event_type} for {self.application}"