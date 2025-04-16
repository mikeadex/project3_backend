from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ParsedCV(models.Model):
    """Model to store parsed CV data"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_parsed_cvs')
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Raw text content
    raw_text = models.TextField(blank=True)
    
    # Extracted text from document
    extracted_text = models.TextField(blank=True)
    
    # Temporary file path for processing
    temp_file_path = models.CharField(max_length=512, blank=True)
    
    # Parsed data - using JSONField for flexibility
    parsed_data = models.JSONField(default=dict, blank=True)
    
    # File metadata
    file_size = models.IntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Processing metadata
    processing_time = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=50, default='pending', 
                             choices=[
                                 ('pending', 'Pending'),
                                 ('queued', 'Queued'),
                                 ('processing', 'Processing'),
                                 ('completed', 'Completed'),
                                 ('failed', 'Failed')
                             ])
    error_message = models.TextField(blank=True)
    
    # Analysis data and metadata
    analysis_data = models.JSONField(null=True, blank=True)  # Store CV analysis results
    analysis_date = models.DateTimeField(null=True, blank=True)  # Track when analysis was performed
    
    def __str__(self):
        return f"{self.file_name} - {self.user.username} ({self.status})"
    
    class Meta:
        verbose_name = "Parsed CV"
        verbose_name_plural = "Parsed CVs"
        ordering = ['-uploaded_at']

class CVRewriteSession(models.Model):
    """Model to store temporary CV rewrite session data"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cv_rewrite_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Reference to the source CV
    cv_id = models.IntegerField(null=True, blank=True)
    
    # Input data
    input_data = models.JSONField(default=dict)
    
    # Output data after AI processing
    output_data = models.JSONField(default=dict, blank=True)
    
    # Result data (complete rewrite results)
    result = models.JSONField(default=dict, blank=True)
    
    # Processing status
    status = models.CharField(max_length=50, default='pending', 
                             choices=[
                                 ('pending', 'Pending'),
                                 ('processing', 'Processing'),
                                 ('completed', 'Completed'),
                                 ('error', 'Error'),
                                 ('failed', 'Failed')
                             ])
    error_message = models.TextField(blank=True)
    
    # New CV created from this session
    new_cv_id = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"CV Rewrite Session - {self.user.username} ({self.status})"
    
    class Meta:
        verbose_name = "CV Rewrite Session"
        verbose_name_plural = "CV Rewrite Sessions"
        ordering = ['-created_at']
