from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid
from django.conf import settings

User = get_user_model()

class SubscriptionPlan(models.Model):
    """
    Defines the available subscription plans
    """
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)  # Default to 30 days (monthly subscription)
    features = models.JSONField(default=dict)  # Store features as JSON
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (${self.price})"

class Subscription(models.Model):
    """
    Tracks user subscriptions
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"

    def save(self, *args, **kwargs):
        # Set end_date if not set
        if not self.end_date:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

class FeatureUsage(models.Model):
    """
    Tracks usage of subscription features
    """
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='feature_usage')
    feature_name = models.CharField(max_length=100)
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['subscription', 'feature_name']
        verbose_name_plural = 'Feature Usage'

    def __str__(self):
        return f"{self.subscription.user.email} - {self.feature_name} ({self.usage_count})"

class SubscriptionUsageLog(models.Model):
    """
    Tracks detailed usage of subscription features
    """
    ACTION_CHOICES = [
        ('cv_generation', 'CV Generation'),
        ('job_application', 'Job Application'),
        ('job_save', 'Job Save'),
        ('job_alert', 'Job Alert'),
        ('interview_prep', 'Interview Preparation'),
    ]

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usage_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.subscription.user.email} - {self.action} at {self.timestamp}" 