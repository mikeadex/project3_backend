from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSubscription
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=UserSubscription)
def subscription_saved(sender, instance, created, **kwargs):
    """
    Signal to handle actions when a subscription is saved
    """
    if created:
        logger.info(f"New subscription created for user {instance.user.id} - plan: {instance.plan.name}")
    elif instance.status == 'active' and instance.updated_at and hasattr(instance, 'paid_until'):
        # Subscription was updated/renewed
        logger.info(f"Subscription updated for user {instance.user.id} - plan: {instance.plan.name}")
    elif instance.status == 'canceled':
        logger.info(f"Subscription canceled for user {instance.user.id} - plan: {instance.plan.name}")

@receiver(pre_delete, sender=UserSubscription)
def subscription_deleted(sender, instance, **kwargs):
    """
    Signal to handle actions before a subscription is deleted
    """
    logger.warning(f"Subscription being deleted for user {instance.user.id} - plan: {instance.plan.name}") 