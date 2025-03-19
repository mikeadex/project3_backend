from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count
from django.db import transaction
from datetime import datetime, timedelta
import stripe
from django.conf import settings
from .models import SubscriptionPlan, UserSubscription, SubscriptionUsageLog, Subscription
from .serializers import (
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    SubscriptionUsageLogSerializer, SubscriptionSummarySerializer,
    SubscriptionSerializer, SubscriptionCreateSerializer
)
from .services import SubscriptionService
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing subscription plans
    """
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subscriptions
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter subscriptions to return only those belonging to the current user
        """
        return Subscription.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """
        Return different serializers for different actions
        """
        if self.action == 'create':
            return SubscriptionCreateSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        """
        Create a new subscription
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            plan = get_object_or_404(SubscriptionPlan, id=serializer.validated_data['plan_id'])
            payment_method_id = serializer.validated_data.get('payment_method_id')
            
            subscription = SubscriptionService.create_subscription(
                user=request.user,
                plan=plan,
                payment_method_id=payment_method_id
            )
            
            response_serializer = SubscriptionSerializer(subscription)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return Response(
                {"error": "Failed to create subscription"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def create_payment_intent(self, request):
        """
        Create a Stripe PaymentIntent for subscription
        """
        try:
            plan_id = request.data.get('plan_id')
            if not plan_id:
                return Response(
                    {"error": "plan_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
            
            # Create or get customer
            if not request.user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    metadata={'user_id': str(request.user.id)}
                )
                request.user.stripe_customer_id = customer.id
                request.user.save()

            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(plan.price * 100),  # Convert to cents
                currency='usd',
                customer=request.user.stripe_customer_id,
                metadata={
                    'plan_id': plan_id,
                    'user_id': str(request.user.id)
                }
            )

            # Create a pending subscription
            subscription = Subscription.objects.create(
                user=request.user,
                plan=plan,
                status='pending',
                stripe_customer_id=request.user.stripe_customer_id
            )

            return Response({
                'clientSecret': intent.client_secret,
                'subscription': SubscriptionSerializer(subscription).data
            })

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return Response(
                {"error": "Failed to create payment intent"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """
        Confirm a subscription after successful payment
        """
        subscription = self.get_object()
        payment_method_id = request.data.get('payment_method_id')

        if not payment_method_id:
            return Response(
                {"error": "payment_method_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=subscription.stripe_customer_id,
            )

            # Set as default payment method
            stripe.Customer.modify(
                subscription.stripe_customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )

            # Update subscription status
            subscription.status = 'active'
            subscription.save()

            return Response(SubscriptionSerializer(subscription).data)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error confirming subscription: {str(e)}")
            return Response(
                {"error": "Failed to confirm subscription"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get subscription summary for the current user
        """
        summary = SubscriptionService.get_subscription_summary(request.user)
        
        if summary is None:
            return Response(
                {"error": "Failed to get subscription summary"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer = SubscriptionSummarySerializer(summary)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def check_access(self, request):
        """
        Check if user has access to a specific feature
        """
        feature = request.data.get('feature')
        if not feature:
            return Response(
                {"error": "Feature parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        has_access = SubscriptionService.check_subscription_access(
            request.user,
            feature
        )
        
        return Response({
            "has_access": has_access,
            "feature": feature
        })

class UserSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user subscriptions
    """
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSubscription.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a subscription
        """
        subscription = self.get_object()

        try:
            # Cancel Stripe subscription
            if subscription.stripe_subscription_id:
                stripe.Subscription.delete(subscription.stripe_subscription_id)

            # Update subscription record
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.save()

            return Response(UserSubscriptionSerializer(subscription).data)

        except stripe.error.StripeError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get subscription summary including usage and limits
        """
        user = request.user
        
        # Get active subscription
        active_subscription = self.get_queryset().filter(
            status='active',
            end_date__gt=timezone.now()
        ).first()

        # Get available plans
        available_plans = SubscriptionPlan.objects.filter(status='active')

        # Get usage for current month
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage_this_month = SubscriptionUsageLog.objects.filter(
            subscription__user=user,
            timestamp__gte=month_start
        ).values('action').annotate(count=Count('id'))

        # Get recent activity
        recent_activity = SubscriptionUsageLog.objects.filter(
            subscription__user=user
        ).order_by('-timestamp')[:10]

        data = {
            'active_subscription': active_subscription,
            'available_plans': available_plans,
            'usage_this_month': {
                log['action']: log['count'] for log in usage_this_month
            },
            'recent_activity': recent_activity
        }

        serializer = SubscriptionSummarySerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def log_usage(self, request, pk=None):
        """
        Log usage of a subscription feature
        """
        subscription = self.get_object()
        action = request.data.get('action')
        details = request.data.get('details', {})

        if not action:
            return Response(
                {'error': 'Action is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Create usage log
            log = SubscriptionUsageLog.objects.create(
                subscription=subscription,
                action=action,
                details=details
            )

            # Update usage counters
            if action == 'cv_generation':
                subscription.cv_generations_used += 1
            elif action == 'job_application':
                subscription.job_applications_used += 1
            elif action == 'job_save':
                subscription.saved_jobs_count += 1

            subscription.save()

        return Response(SubscriptionUsageLogSerializer(log).data)

class SubscriptionWebhookView(viewsets.ViewSet):
    """
    Handle Stripe webhooks for subscription events
    """
    permission_classes = []  # No authentication required for webhooks

    def create(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )

            # Handle the event
            if event.type == 'invoice.payment_succeeded':
                self._handle_payment_succeeded(event.data.object)
            elif event.type == 'invoice.payment_failed':
                self._handle_payment_failed(event.data.object)
            elif event.type == 'customer.subscription.deleted':
                self._handle_subscription_deleted(event.data.object)

            return Response({'status': 'success'})

        except stripe.error.SignatureVerificationError:
            return Response(
                {'error': 'Invalid signature'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _handle_payment_succeeded(self, invoice):
        subscription = UserSubscription.objects.filter(
            stripe_subscription_id=invoice.subscription
        ).first()

        if subscription:
            # Extend subscription period
            if subscription.plan.interval == 'monthly':
                subscription.end_date = timezone.now() + timedelta(days=30)
            elif subscription.plan.interval == 'yearly':
                subscription.end_date = timezone.now() + timedelta(days=365)

            subscription.status = 'active'
            subscription.save()

    def _handle_payment_failed(self, invoice):
        subscription = UserSubscription.objects.filter(
            stripe_subscription_id=invoice.subscription
        ).first()

        if subscription:
            subscription.status = 'past_due'
            subscription.save()

    def _handle_subscription_deleted(self, subscription_object):
        subscription = UserSubscription.objects.filter(
            stripe_subscription_id=subscription_object.id
        ).first()

        if subscription:
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.save() 