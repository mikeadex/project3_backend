from django.utils import timezone
from django.db import transaction
from django.conf import settings
import stripe
import logging
from .models import SubscriptionPlan, UserSubscription, SubscriptionUsageLog

logger = logging.getLogger(__name__)

class SubscriptionService:
    """
    Service class to handle subscription-related business logic
    """
    
    @staticmethod
    def check_subscription_access(user, feature):
        """
        Check if a user has access to a specific feature based on their subscription
        """
        try:
            # Get user's active subscription
            subscription = UserSubscription.objects.filter(
                user=user,
                status='active',
                end_date__gt=timezone.now()
            ).select_related('plan').first()
            
            if not subscription:
                logger.info(f"No active subscription found for user {user.email}")
                return False
                
            # Check if the feature is available in the plan and within limits
            if feature == 'cv_generation':
                if subscription.cv_generations_used >= subscription.plan.max_cv_generations:
                    logger.info(f"CV generation limit reached for user {user.email}")
                    return False
            elif feature == 'job_application':
                if subscription.job_applications_used >= subscription.plan.max_job_applications:
                    logger.info(f"Job application limit reached for user {user.email}")
                    return False
            elif feature == 'saved_job':
                if subscription.saved_jobs_count >= subscription.plan.max_saved_jobs:
                    logger.info(f"Saved jobs limit reached for user {user.email}")
                    return False
            
            # Check other feature access based on plan
            if feature == 'cv_analytics' and not subscription.plan.has_cv_analytics:
                return False
            elif feature == 'job_alerts' and not subscription.plan.has_job_alerts:
                return False
            elif feature == 'priority_support' and not subscription.plan.has_priority_support:
                return False
            elif feature == 'ai_interview_prep' and not subscription.plan.has_ai_interview_prep:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking subscription access: {str(e)}")
            return False
    
    @staticmethod
    def log_feature_usage(user, feature, details=None):
        """
        Log usage of a subscription feature
        """
        try:
            with transaction.atomic():
                subscription = UserSubscription.objects.filter(
                    user=user,
                    status='active',
                    end_date__gt=timezone.now()
                ).select_for_update().first()
                
                if not subscription:
                    logger.warning(f"No active subscription found for user {user.email}")
                    return False
                
                # Update the appropriate usage counter based on feature
                if feature == 'cv_generation':
                    subscription.cv_generations_used += 1
                elif feature == 'job_application':
                    subscription.job_applications_used += 1
                elif feature == 'job_save':
                    subscription.saved_jobs_count += 1
                
                subscription.save()
                
                # Create usage log
                SubscriptionUsageLog.objects.create(
                    subscription=subscription,
                    action=feature,
                    details=details or {}
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error logging feature usage: {str(e)}")
            return False
    
    @staticmethod
    def create_subscription(user, plan, payment_method_id=None):
        """
        Create a new subscription for a user
        """
        try:
            with transaction.atomic():
                # If Stripe is configured, create/update Stripe customer and subscription
                if settings.STRIPE_SECRET_KEY and payment_method_id:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    
                    # Get or create Stripe customer
                    if not user.stripe_customer_id:
                        customer = stripe.Customer.create(
                            email=user.email,
                            payment_method=payment_method_id,
                            invoice_settings={'default_payment_method': payment_method_id}
                        )
                        user.stripe_customer_id = customer.id
                        user.save()
                    
                    # Create Stripe subscription
                    stripe_subscription = stripe.Subscription.create(
                        customer=user.stripe_customer_id,
                        items=[{'price': plan.stripe_price_id}],
                        payment_behavior='default_incomplete',
                        expand=['latest_invoice.payment_intent']
                    )
                
                # Create local subscription
                subscription = UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    status='pending' if payment_method_id else 'active',
                    start_date=timezone.now(),
                    cv_generations_used=0,
                    job_applications_used=0,
                    saved_jobs_count=0,
                    stripe_subscription_id=stripe_subscription.id if payment_method_id else None,
                    stripe_customer_id=user.stripe_customer_id if payment_method_id else None
                )
                
                logger.info(f"Created subscription for user {user.email} with plan {plan.name}")
                return subscription
                
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            raise
    
    @staticmethod
    def cancel_subscription(subscription_id):
        """
        Cancel a subscription
        """
        try:
            with transaction.atomic():
                subscription = UserSubscription.objects.select_for_update().get(id=subscription_id)
                
                # Cancel Stripe subscription if exists
                if subscription.stripe_subscription_id and settings.STRIPE_SECRET_KEY:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    stripe.Subscription.delete(subscription.stripe_subscription_id)
                
                subscription.status = 'cancelled'
                subscription.save()
                
                logger.info(f"Cancelled subscription {subscription_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return False
    
    @staticmethod
    def get_subscription_summary(user):
        """
        Get a summary of user's subscription status and usage
        """
        try:
            subscription = UserSubscription.objects.filter(
                user=user,
                status='active',
                end_date__gt=timezone.now()
            ).select_related('plan').first()
            
            if not subscription:
                return {
                    'has_active_subscription': False,
                    'subscription': None,
                    'usage': None,
                    'recent_activity': None
                }
            
            # Get usage directly from subscription
            usage = {
                'cv_generations': {
                    'used': subscription.cv_generations_used,
                    'total': subscription.plan.max_cv_generations,
                    'percentage': (subscription.cv_generations_used / subscription.plan.max_cv_generations * 100) 
                        if subscription.plan.max_cv_generations > 0 else 0
                },
                'job_applications': {
                    'used': subscription.job_applications_used,
                    'total': subscription.plan.max_job_applications,
                    'percentage': (subscription.job_applications_used / subscription.plan.max_job_applications * 100) 
                        if subscription.plan.max_job_applications > 0 else 0
                },
                'saved_jobs': {
                    'used': subscription.saved_jobs_count,
                    'total': subscription.plan.max_saved_jobs,
                    'percentage': (subscription.saved_jobs_count / subscription.plan.max_saved_jobs * 100) 
                        if subscription.plan.max_saved_jobs > 0 else 0
                }
            }
            
            # Get recent activity
            recent_activity = SubscriptionUsageLog.objects.filter(
                subscription=subscription
            ).order_by('-timestamp')[:5]
            
            return {
                'has_active_subscription': True,
                'subscription': {
                    'plan_name': subscription.plan.name,
                    'status': subscription.status,
                    'start_date': subscription.start_date,
                    'end_date': subscription.end_date,
                    'features': {
                        'cv_analytics': subscription.plan.has_cv_analytics,
                        'job_alerts': subscription.plan.has_job_alerts,
                        'priority_support': subscription.plan.has_priority_support,
                        'ai_interview_prep': subscription.plan.has_ai_interview_prep
                    }
                },
                'usage': usage,
                'recent_activity': [{
                    'action': log.action,
                    'timestamp': log.timestamp,
                    'details': log.details
                } for log in recent_activity]
            }
                
        except Exception as e:
            logger.error(f"Error getting subscription summary: {str(e)}")
            return {
                'has_active_subscription': False,
                'subscription': None,
                'usage': None,
                'recent_activity': None,
                'error': str(e)
            }