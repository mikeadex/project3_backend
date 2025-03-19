from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging
from datetime import datetime

from .models import ParsedCV

logger = logging.getLogger('ai_cv_parser')

@receiver(post_save, sender=ParsedCV)
def log_cv_saved(sender, instance, created, **kwargs):
    """Log when a ParsedCV record is created or updated"""
    action = "created" if created else "updated"
    logger.info(f"ParsedCV record {instance.id} {action} for user {instance.user.username} - Status: {instance.status}")

@receiver(post_delete, sender=ParsedCV)
def log_cv_deleted(sender, instance, **kwargs):
    """Log when a ParsedCV record is deleted"""
    logger.info(f"ParsedCV record {instance.id} deleted for user {instance.user.username}") 