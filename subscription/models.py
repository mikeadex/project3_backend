from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid
from django.conf import settings

User = get_user_model()

class SubscriptionFeature(models.Model):
    """
    Defines individual features that can be associated with subscription plans
    """
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon identifier or class")
    is_highlighted = models.BooleanField(default=False, help_text="Whether this feature should be highlighted in plan comparisons")
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Order in which to display the feature")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Subscription Feature'
        verbose_name_plural = 'Subscription Features'

    def __str__(self):
        return self.name


class SubscriptionPlan(models.Model):
    """
    Defines the available subscription plans
    """
    INTERVAL_CHOICES = [
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.CharField(unique=True, max_length=50, default='example')
    description = models.TextField()
    short_description = models.CharField(max_length=200, blank=True, help_text="Brief description displayed in plan cards")
    features = models.ManyToManyField(SubscriptionFeature, through='PlanFeature', related_name='plans')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default='month')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    max_cv_generations = models.IntegerField(default=0)
    max_job_applications = models.IntegerField(default=0)
    max_saved_jobs = models.IntegerField(default=0)
    has_cv_analytics = models.BooleanField(default=False)
    has_job_alerts = models.BooleanField(default=False)
    has_priority_support = models.BooleanField(default=False)
    has_ai_interview_prep = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False, help_text="Indicates if this is a featured/popular plan")
    stripe_price_id = models.CharField(max_length=100, default='')
    stripe_product_id = models.CharField(max_length=100, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (${self.price}/{self.interval})"
    
    @property
    def annual_price(self):
        """
        Calculate annual price (10 months for a yearly subscription - giving 2 months free)
        Only used as a fallback if there's no yearly plan matching this monthly plan
        """
        if self.interval == 'year':
            return round(float(self.price), 2)
        return round(float(self.price) * 10, 2)
    
    @property
    def stripe_annual_price_id(self):
        """
        Get Stripe price ID for the annual version of this plan
        Only used as a fallback if there's no yearly plan matching this monthly plan
        """
        if self.interval == 'year':
            return self.stripe_price_id
        return ''
    
    @classmethod
    def get_yearly_plan_for(cls, monthly_plan):
        """
        Try to find a matching yearly plan for this monthly plan
        Returns None if no matching yearly plan exists
        """
        yearly_plan_slug = f"{monthly_plan.slug}-yearly"
        try:
            return cls.objects.get(slug=yearly_plan_slug, interval='year')
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def create_yearly_plan(cls, monthly_plan):
        """
        Create a yearly version of a monthly plan
        """
        yearly_price = round(float(monthly_plan.price) * 10, 2)
        
        yearly_plan = cls(
            name=f"{monthly_plan.name} (Yearly)",
            slug=f"{monthly_plan.slug}-yearly",
            description=monthly_plan.description,
            short_description=monthly_plan.short_description,
            price=yearly_price,
            interval='year',
            status=monthly_plan.status,
            max_cv_generations=monthly_plan.max_cv_generations,
            max_job_applications=monthly_plan.max_job_applications,
            max_saved_jobs=monthly_plan.max_saved_jobs,
            has_cv_analytics=monthly_plan.has_cv_analytics,
            has_job_alerts=monthly_plan.has_job_alerts,
            has_priority_support=monthly_plan.has_priority_support,
            has_ai_interview_prep=monthly_plan.has_ai_interview_prep,
            is_popular=monthly_plan.is_popular,
            stripe_product_id=monthly_plan.stripe_product_id,
        )
        yearly_plan.save()
        return yearly_plan

class PlanFeature(models.Model):
    """
    Junction table for the many-to-many relationship between SubscriptionPlan and SubscriptionFeature
    """
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    feature = models.ForeignKey(SubscriptionFeature, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True, help_text="Whether this feature is available in this plan")
    value_limit = models.CharField(max_length=50, blank=True, help_text="Limit value for this feature, if applicable")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('plan', 'feature')
        verbose_name = 'Plan Feature'
        verbose_name_plural = 'Plan Features'
    
    def __str__(self):
        status = "✓" if self.is_available else "✗"
        value = f" ({self.value_limit})" if self.value_limit else ""
        return f"{self.plan.name} - {self.feature.name}: {status}{value}"

class UserSubscription(models.Model):
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
    cv_generations_used = models.IntegerField(default=0)
    job_applications_used = models.IntegerField(default=0)
    saved_jobs_count = models.IntegerField(default=0)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    canceled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"

    def save(self, *args, **kwargs):
        # Set end_date if not set
        if not self.end_date:
            # Calculate end date based on plan interval
            if self.plan.interval == 'month':
                days = 30
            elif self.plan.interval == 'year':
                days = 365
            else:
                days = 30  # Default
                
            self.end_date = self.start_date + timezone.timedelta(days=days)
        super().save(*args, **kwargs)

class FeatureUsage(models.Model):
    """
    Tracks usage of subscription features
    """
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='feature_usage')
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

    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='usage_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.subscription.user.email} - {self.action} at {self.timestamp}"