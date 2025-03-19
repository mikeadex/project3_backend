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
                                 ('processing', 'Processing'),
                                 ('completed', 'Completed'),
                                 ('failed', 'Failed')
                             ])
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.file_name} - {self.user.username} ({self.status})"
    
    class Meta:
        verbose_name = "Parsed CV"
        verbose_name_plural = "Parsed CVs"
        ordering = ['-uploaded_at']
