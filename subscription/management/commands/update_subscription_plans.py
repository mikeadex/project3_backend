from django.core.management.base import BaseCommand
from subscription.models import SubscriptionPlan
import json


class Command(BaseCommand):
    help = 'Manage subscription plans in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all subscription plans in the database',
        )
        parser.add_argument(
            '--create-yearly',
            action='store_true',
            help='Create yearly versions of monthly plans',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix subscription plans metadata',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_plans()
        
        if options['create_yearly']:
            self.create_yearly_plans()
            
        if options['fix']:
            self.fix_plans()

    def list_plans(self):
        """List all subscription plans in the database"""
        plans = SubscriptionPlan.objects.all()
        self.stdout.write(self.style.SUCCESS(f'Found {plans.count()} subscription plans:'))
        
        for plan in plans:
            self.stdout.write(f'ID: {plan.id}')
            self.stdout.write(f'  Name: {plan.name}')
            self.stdout.write(f'  Slug: {plan.slug}')
            self.stdout.write(f'  Price: ${plan.price} per {plan.interval}')
            self.stdout.write(f'  Annual Price (calculated): ${plan.annual_price}')
            self.stdout.write(f'  Status: {plan.status}')
            self.stdout.write(f'  Max CV Generations: {plan.max_cv_generations}')
            self.stdout.write(f'  Max Job Applications: {plan.max_job_applications}')
            self.stdout.write(f'  Max Saved Jobs: {plan.max_saved_jobs}')
            self.stdout.write(f'  Has CV Analytics: {plan.has_cv_analytics}')
            self.stdout.write(f'  Has Job Alerts: {plan.has_job_alerts}')
            self.stdout.write(f'  Has Priority Support: {plan.has_priority_support}')
            self.stdout.write(f'  Has AI Interview Prep: {plan.has_ai_interview_prep}')
            self.stdout.write(f'  Stripe Price ID: {plan.stripe_price_id}')
            self.stdout.write(f'  Stripe Product ID: {plan.stripe_product_id}')
            self.stdout.write('---')

    def create_yearly_plans(self):
        """Create yearly versions of all monthly plans"""
        monthly_plans = SubscriptionPlan.objects.filter(interval='month')
        created = 0
        
        for monthly_plan in monthly_plans:
            # Check if yearly plan already exists
            yearly_plan_slug = f"{monthly_plan.slug}-yearly"
            
            try:
                SubscriptionPlan.objects.get(slug=yearly_plan_slug)
                self.stdout.write(f"Yearly plan already exists for {monthly_plan.name}")
                continue
            except SubscriptionPlan.DoesNotExist:
                # Create yearly plan
                yearly_plan = SubscriptionPlan.create_yearly_plan(monthly_plan)
                self.stdout.write(self.style.SUCCESS(
                    f"Created yearly plan: {yearly_plan.name} at ${yearly_plan.price}/year"
                ))
                created += 1
        
        self.stdout.write(self.style.SUCCESS(f"Created {created} new yearly plans"))

    def fix_plans(self):
        """Fix the subscription plans metadata to ensure they have the correct features"""
        plans = SubscriptionPlan.objects.all()
        updated = 0
        
        # Define default plans
        default_plans = {
            'free': {
                'name': 'Free',
                'description': 'Basic version of Ella',
                'price': 0,
                'max_cv_generations': 1,
                'max_job_applications': 5,
                'max_saved_jobs': 10,
                'has_cv_analytics': False,
                'has_job_alerts': False,
                'has_priority_support': False,
                'has_ai_interview_prep': False
            },
            'basic': {
                'name': 'Basic',
                'description': 'For occasional job seekers',
                'price': 9.99,
                'max_cv_generations': 3,
                'max_job_applications': 10,
                'max_saved_jobs': 20,
                'has_cv_analytics': True,
                'has_job_alerts': True,
                'has_priority_support': False,
                'has_ai_interview_prep': False
            },
            'pro': {
                'name': 'Pro',
                'description': 'For active job seekers',
                'price': 19.99,
                'max_cv_generations': 10,
                'max_job_applications': 50,
                'max_saved_jobs': 100,
                'has_cv_analytics': True,
                'has_job_alerts': True,
                'has_priority_support': True,
                'has_ai_interview_prep': True
            }
        }
        
        # Add default plans if they don't exist
        for slug, plan_data in default_plans.items():
            try:
                plan = SubscriptionPlan.objects.get(slug=slug)
                # Update existing plan
                was_updated = False
                
                # Check each field and update if needed
                for key, value in plan_data.items():
                    if getattr(plan, key) != value:
                        setattr(plan, key, value)
                        was_updated = True
                
                if was_updated:
                    plan.save()
                    self.stdout.write(self.style.SUCCESS(f"Updated plan: {plan.name}"))
                    updated += 1
                else:
                    self.stdout.write(f"Plan {plan.name} is already up to date")
                
            except SubscriptionPlan.DoesNotExist:
                # Create new plan
                new_plan = SubscriptionPlan.objects.create(
                    slug=slug,
                    interval='month',
                    status='active',
                    **plan_data
                )
                self.stdout.write(self.style.SUCCESS(f"Created new plan: {new_plan.name}"))
                updated += 1
        
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} subscription plans"))
