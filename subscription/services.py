from django.utils import timezone
from django.db import transaction
from django.conf import settings
import stripe
import logging
from .models import SubscriptionPlan, Subscription, FeatureUsage, SubscriptionUsageLog

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
            subscription = Subscription.objects.filter(
                user=user,
                status='active',
                end_date__gt=timezone.now()
            ).select_related('plan').first()
            
            if not subscription:
                logger.info(f"No active subscription found for user {user.email}")
                return False
                
            # Check if feature is included in plan
            features = subscription.plan.features
            if not features.get(feature, False):
                logger.info(f"Feature {feature} not available in user's plan")
                return False
                
            # Check usage limits if applicable
            feature_usage = FeatureUsage.objects.filter(
                subscription=subscription,
                feature_name=feature
            ).first()
            
            if feature_usage:
                limit = features.get(f"{feature}_limit")
                if limit and feature_usage.usage_count >= limit:
                    logger.info(f"Usage limit reached for feature {feature}")
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
                subscription = Subscription.objects.filter(
                    user=user,
                    status='active',
                    end_date__gt=timezone.now()
                ).select_for_update().first()
                
                if not subscription:
                    logger.warning(f"No active subscription found for user {user.email}")
                    return False
                
                # Update or create feature usage counter
                feature_usage, _ = FeatureUsage.objects.get_or_create(
                    subscription=subscription,
                    feature_name=feature,
                    defaults={'usage_count': 0}
                )
                feature_usage.usage_count += 1
                feature_usage.save()
                
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
                subscription = Subscription.objects.create(
                    user=user,
                    plan=plan,
                    status='pending' if payment_method_id else 'active',
                    start_date=timezone.now(),
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
                subscription = Subscription.objects.select_for_update().get(id=subscription_id)
                
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
            subscription = Subscription.objects.filter(
                user=user,
                status='active',
                end_date__gt=timezone.now()
            ).select_related('plan').first()
            
            if not subscription:
                return {
                    'has_active_subscription': False,
                    'subscription': None,
                    'feature_usage': None,
                    'recent_activity': None
                }
            
            # Get feature usage
            feature_usage = FeatureUsage.objects.filter(subscription=subscription)
            
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
                    'features': subscription.plan.features
                },
                'feature_usage': {
                    usage.feature_name: usage.usage_count 
                    for usage in feature_usage
                },
                'recent_activity': [
                    {
                        'action': log.action,
                        'timestamp': log.timestamp,
                        'details': log.details
                    }
                    for log in recent_activity
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription summary: {str(e)}")
            return None 