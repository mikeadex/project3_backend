from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from subscription.models import SubscriptionPlan, UserSubscription, SubscriptionUsageLog
import random
from datetime import timedelta
import uuid
import re

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds subscription data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--plans-only',
            action='store_true',
            help='Only seed subscription plans, not subscriptions'
        )
        parser.add_argument(
            '--create-test-user',
            action='store_true',
            help='Create a test user if none exists'
        )

    def handle(self, *args, **options):
        self.stdout.write('Seeding subscription data...')
        
        # Create subscription plans
        self.create_subscription_plans()
        
        if not options['plans_only']:
            # Create test user if requested
            if options['create_test_user']:
                self.create_test_user()
            
            # Create subscriptions
            self.create_subscriptions()
            
            # Create usage data
            self.create_usage_data()
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded subscription data'))

    def create_subscription_plans(self):
        """Create test subscription plans"""
        # First, check if plans already exist to avoid duplicates
        if SubscriptionPlan.objects.exists():
            self.stdout.write('Subscription plans already exist. Skipping plan creation.')
            return
        
        # Define plans
        plans = [
            {
                'name': 'Free',
                'slug': 'free',
                'description': 'Basic CV building capabilities',
                'price': 0.00,
                'interval': 'month',
                'status': 'active',
                'max_cv_generations': 1,
                'max_job_applications': 0,
                'max_saved_jobs': 5,
                'has_cv_analytics': False,
                'has_job_alerts': False,
                'has_priority_support': False,
                'has_ai_interview_prep': False,
                'stripe_price_id': 'price_free',
                'stripe_product_id': 'prod_free',
            },
            {
                'name': 'Pro',
                'slug': 'pro-monthly',
                'description': 'Enhanced CV building with AI suggestions',
                'price': 9.99,
                'interval': 'month',
                'status': 'active',
                'max_cv_generations': 5,
                'max_job_applications': 20,
                'max_saved_jobs': 50,
                'has_cv_analytics': True,
                'has_job_alerts': True,
                'has_priority_support': False,
                'has_ai_interview_prep': False,
                'stripe_price_id': 'price_pro_monthly',
                'stripe_product_id': 'prod_pro',
            },
            {
                'name': 'Premium',
                'slug': 'premium-monthly',
                'description': 'Unlimited CV building with advanced features',
                'price': 19.99,
                'interval': 'month',
                'status': 'active',
                'max_cv_generations': 10,
                'max_job_applications': 50,
                'max_saved_jobs': 100,
                'has_cv_analytics': True,
                'has_job_alerts': True,
                'has_priority_support': True,
                'has_ai_interview_prep': True,
                'stripe_price_id': 'price_premium_monthly',
                'stripe_product_id': 'prod_premium',
            },
            {
                'name': 'Annual Pro',
                'slug': 'pro-annual',
                'description': 'Pro plan billed annually (2 months free)',
                'price': 99.99,
                'interval': 'year',
                'status': 'active',
                'max_cv_generations': 10,
                'max_job_applications': 50,
                'max_saved_jobs': 100,
                'has_cv_analytics': True,
                'has_job_alerts': True,
                'has_priority_support': True,
                'has_ai_interview_prep': False,
                'stripe_price_id': 'price_pro_annual',
                'stripe_product_id': 'prod_pro',
            }
        ]
        
        # Create plans
        for plan_data in plans:
            # Add timestamps
            plan_data['created_at'] = timezone.now()
            plan_data['updated_at'] = timezone.now()
            
            plan = SubscriptionPlan.objects.create(**plan_data)
            self.stdout.write(f'Created plan: {plan.name}')

    def create_test_user(self):
        """Create a test user if none exists"""
        if User.objects.filter(email='test@example.com').exists():
            self.stdout.write('Test user already exists. Skipping user creation.')
            return
        
        # Create a test user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword',
            is_active=True
        )
        
        # Set additional user fields if they exist
        if hasattr(user, 'first_name'):
            user.first_name = 'Test'
        if hasattr(user, 'last_name'):
            user.last_name = 'User'
        if hasattr(user, 'phone_number'):
            user.phone_number = '+1234567890'
        
        user.save()
        self.stdout.write(f'Created test user: {user.email}')

    def create_subscriptions(self):
        """Create test subscriptions for users"""
        # Get users (either all or just test user if it exists)
        users = User.objects.all()
        if users.count() == 0:
            self.stdout.write('No users found. Skipping subscription creation.')
            return
        
        # Get all plans
        plans = SubscriptionPlan.objects.all()
        if plans.count() == 0:
            self.stdout.write('No plans found. Skipping subscription creation.')
            return
        
        # For each user, create a subscription
        for user in users:
            # Skip if user already has a subscription
            if UserSubscription.objects.filter(user=user).exists():
                self.stdout.write(f'User {user.email} already has a subscription. Skipping.')
                continue
            
            # Randomly select a plan
            plan = random.choice(plans)
            
            # Create a subscription
            start_date = timezone.now() - timedelta(days=random.randint(1, 30))
            
            # Calculate end date based on plan interval
            if plan.interval == 'month':
                end_date = start_date + timedelta(days=30)
            elif plan.interval == 'year':
                end_date = start_date + timedelta(days=365)
            else:
                end_date = start_date + timedelta(days=30)  # Default
            
            # Generate random usage values that are within the plan limits
            cv_generations_used = random.randint(0, max(0, plan.max_cv_generations - 1))
            job_applications_used = random.randint(0, max(0, plan.max_job_applications - 1))
            saved_jobs_count = random.randint(0, max(0, plan.max_saved_jobs - 1))
            
            subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                status='active',
                start_date=start_date,
                end_date=end_date,
                cv_generations_used=cv_generations_used,
                job_applications_used=job_applications_used,
                saved_jobs_count=saved_jobs_count,
                stripe_subscription_id=f'sub_{uuid.uuid4().hex[:10]}',
                stripe_customer_id=f'cus_{uuid.uuid4().hex[:10]}'
            )
            
            self.stdout.write(f'Created subscription for {user.email}: {plan.name}')

    def create_usage_data(self):
        """Create subscription usage logs"""
        # Get all active subscriptions
        subscriptions = UserSubscription.objects.filter(status='active')
        if subscriptions.count() == 0:
            self.stdout.write('No active subscriptions found. Skipping usage data creation.')
            return
        
        # Define possible actions
        actions = ['cv_generation', 'job_application', 'job_save', 'job_alert', 'interview_prep']
        
        # For each subscription, create usage logs
        for subscription in subscriptions:
            # Create usage logs (5-10 random logs per subscription)
            log_count = random.randint(5, 10)
            for _ in range(log_count):
                action = random.choice(actions)
                timestamp = timezone.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                
                details = {}
                if action == 'cv_generation':
                    details = {'template': f'template_{random.randint(1, 5)}'}
                elif action == 'job_application':
                    details = {'job_id': f'job_{random.randint(1000, 9999)}'}
                
                SubscriptionUsageLog.objects.create(
                    subscription=subscription,
                    action=action,
                    timestamp=timestamp,
                    details=details
                )
            
            self.stdout.write(f'Created {log_count} usage logs for {subscription.user.email}')
