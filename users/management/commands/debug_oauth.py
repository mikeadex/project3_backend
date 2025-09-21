from django.core.management.base import BaseCommand
from django.conf import settings
from allauth.socialaccount.models import SocialApp
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Debug OAuth configuration for social login providers'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 DEBUGGING OAUTH CONFIGURATION"))
        
        # Check environment variables
        self.stdout.write("\n📋 Environment Variables:")
        oauth_vars = {
            'GOOGLE_OAUTH_CLIENT_ID': os.getenv('GOOGLE_OAUTH_CLIENT_ID', ''),
            'GOOGLE_OAUTH_CLIENT_SECRET': os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', ''),
            'GITHUB_OAUTH_CLIENT_ID': os.getenv('GITHUB_OAUTH_CLIENT_ID', ''),
            'GITHUB_OAUTH_CLIENT_SECRET': os.getenv('GITHUB_OAUTH_CLIENT_SECRET', ''),
            'LINKEDIN_OAUTH_CLIENT_ID': os.getenv('LINKEDIN_OAUTH_CLIENT_ID', ''),
            'LINKEDIN_OAUTH_CLIENT_SECRET': os.getenv('LINKEDIN_OAUTH_CLIENT_SECRET', ''),
        }
        
        for var_name, value in oauth_vars.items():
            status = "✅ SET" if value else "❌ MISSING"
            masked_value = f"{value[:8]}...{value[-4:]}" if value and len(value) > 12 else "NOT SET"
            self.stdout.write(f"  {var_name}: {status} ({masked_value})")
        
        # Check Django settings
        self.stdout.write("\n⚙️  Django Settings:")
        social_settings = {
            'ACCOUNT_EMAIL_VERIFICATION': getattr(settings, 'ACCOUNT_EMAIL_VERIFICATION', 'NOT SET'),
            'SOCIALACCOUNT_EMAIL_VERIFICATION': getattr(settings, 'SOCIALACCOUNT_EMAIL_VERIFICATION', 'NOT SET'),
            'SOCIALACCOUNT_AUTO_SIGNUP': getattr(settings, 'SOCIALACCOUNT_AUTO_SIGNUP', 'NOT SET'),
            'LOGIN_REDIRECT_URL': getattr(settings, 'LOGIN_REDIRECT_URL', 'NOT SET'),
            'SOCIALACCOUNT_LOGIN_ON_GET': getattr(settings, 'SOCIALACCOUNT_LOGIN_ON_GET', 'NOT SET'),
        }
        
        for setting_name, value in social_settings.items():
            self.stdout.write(f"  {setting_name}: {value}")
            
        # Check SocialApp records in database
        self.stdout.write("\n🗄️  Database SocialApp Records:")
        try:
            social_apps = SocialApp.objects.all()
            if social_apps.exists():
                for app in social_apps:
                    sites_count = app.sites.count()
                    self.stdout.write(f"  {app.provider}: {app.name} (Sites: {sites_count})")
                    self.stdout.write(f"    Client ID: {app.client_id[:8]}...{app.client_id[-4:] if app.client_id else 'MISSING'}")
                    self.stdout.write(f"    Secret: {'SET' if app.secret else 'MISSING'}")
            else:
                self.stdout.write(f"  ❌ No SocialApp records found in database")
                self.stdout.write(f"  ℹ️  This may be why OAuth authentication is failing")
                
        except Exception as e:
            self.stdout.write(f"  ❌ Error checking database: {e}")
            
        # Check SOCIALACCOUNT_PROVIDERS configuration
        self.stdout.write("\n🔧 SOCIALACCOUNT_PROVIDERS Configuration:")
        providers = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
        for provider_name, config in providers.items():
            self.stdout.write(f"  {provider_name}:")
            if 'APP' in config:
                app_config = config['APP']
                client_id = app_config.get('client_id', '')
                secret = app_config.get('secret', '')
                self.stdout.write(f"    Client ID: {'SET' if client_id else 'MISSING'}")
                self.stdout.write(f"    Secret: {'SET' if secret else 'MISSING'}")
            if 'SCOPE' in config:
                self.stdout.write(f"    Scopes: {config['SCOPE']}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ OAuth debug completed!"))
