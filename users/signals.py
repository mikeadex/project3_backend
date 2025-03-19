from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(pre_save, sender=User)
def ensure_user_setup(sender, instance, **kwargs):
    """
    Ensure user has required fields set before saving
    """
    if not instance.username and instance.email:
        instance.username = instance.email
        logger.info(f"Set username to email for user {instance.email}")

@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Handle any post-save user setup
    """
    if created:
        logger.info(f"New user created: {instance.email}")
    else:
        logger.info(f"User updated: {instance.email}") 