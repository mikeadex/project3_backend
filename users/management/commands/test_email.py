from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Test email configuration and send a test email'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email address to send test to', default='creativemike21@gmail.com')

    def handle(self, *args, **options):
        self.stdout.write("🧪 DJANGO EMAIL CONFIGURATION TEST")
        self.stdout.write("=" * 50)
        
        # Show current email configuration
        self.stdout.write("📧 EMAIL SETTINGS:")
        self.stdout.write(f"   Backend: {getattr(settings, 'EMAIL_BACKEND', 'Not set')}")
        self.stdout.write(f"   Host: {getattr(settings, 'EMAIL_HOST', 'Not set')}")
        self.stdout.write(f"   Port: {getattr(settings, 'EMAIL_PORT', 'Not set')}")
        self.stdout.write(f"   Use TLS: {getattr(settings, 'EMAIL_USE_TLS', 'Not set')}")
        self.stdout.write(f"   Host User: {getattr(settings, 'EMAIL_HOST_USER', 'Not set')}")
        self.stdout.write(f"   Host Password: {'✅ Set' if getattr(settings, 'EMAIL_HOST_PASSWORD', '') else '❌ Not set'}")
        self.stdout.write(f"   Default From: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set')}")
        
        self.stdout.write("\n🔧 ENVIRONMENT VARIABLES:")
        self.stdout.write(f"   EMAIL_PROVIDER: {os.getenv('EMAIL_PROVIDER', 'Not set')}")
        self.stdout.write(f"   BREVO_API_KEY: {'✅ Set' if os.getenv('BREVO_API_KEY') else '❌ Not set'}")
        self.stdout.write(f"   BREVO_EMAIL: {os.getenv('BREVO_EMAIL', 'Not set')}")
        self.stdout.write(f"   USE_TESTMAIL_TESTING: {os.getenv('USE_TESTMAIL_TESTING', 'Not set')}")
        
        # Test email sending
        test_email = options['email']
        self.stdout.write(f"\n📧 SENDING TEST EMAIL TO: {test_email}")
        
        try:
            result = send_mail(
                subject='🧪 Django Email Test - Ella CV',
                message='This is a test email from Django to verify email configuration is working.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[test_email],
                fail_silently=False
            )
            
            if result:
                self.stdout.write(self.style.SUCCESS("✅ EMAIL SENT SUCCESSFULLY!"))
                self.stdout.write("🎉 Email configuration is working!")
            else:
                self.stdout.write(self.style.ERROR("❌ EMAIL SENDING FAILED - send_mail returned 0"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ EMAIL SENDING FAILED: {str(e)}"))
            self.stdout.write(f"Error type: {type(e).__name__}")
            
        self.stdout.write("=" * 50)
