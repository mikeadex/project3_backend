from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging
from datetime import datetime

from .models import ParsedCV

logger = logging.getLogger("ai_cv_parser")


@receiver(post_save, sender=ParsedCV)
def log_cv_saved(sender, instance, created, **kwargs):
    """Log when a ParsedCV record is created or updated"""
    action = "created" if created else "updated"
    user_info = (
        f"guest session {instance.session_id}"
        if instance.is_guest
        else f"user {instance.user.username}"
    )
    logger.info(
        f"ParsedCV record {instance.id} {action} for {user_info} - Status: {instance.status}"
    )


@receiver(post_delete, sender=ParsedCV)
def log_cv_deleted(sender, instance, **kwargs):
    """Log when a ParsedCV record is deleted"""
    user_info = (
        f"guest session {instance.session_id}"
        if instance.is_guest
        else f"user {instance.user.username}"
    )
    logger.info(f"ParsedCV record {instance.id} deleted for {user_info}")
