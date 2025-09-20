from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
import os

# Create your views here.

@require_http_methods(["GET"])
def debug_email_config(request):
    """Debug endpoint to show current email configuration"""
    if not settings.DEBUG and not os.getenv("SHOW_EMAIL_CONFIG", "false").lower() == "true":
        return JsonResponse({"error": "Debug endpoint disabled"}, status=403)
    
    config = {
        "email_settings": {
            "backend": getattr(settings, 'EMAIL_BACKEND', 'Not set'),
            "host": getattr(settings, 'EMAIL_HOST', 'Not set'),
            "port": getattr(settings, 'EMAIL_PORT', 'Not set'),
            "use_tls": getattr(settings, 'EMAIL_USE_TLS', 'Not set'),
            "host_user": getattr(settings, 'EMAIL_HOST_USER', 'Not set'),
            "host_password_set": bool(getattr(settings, 'EMAIL_HOST_PASSWORD', '')),
            "default_from": getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set'),
        },
        "environment_variables": {
            "EMAIL_PROVIDER": os.getenv('EMAIL_PROVIDER', 'Not set'),
            "BREVO_API_KEY_SET": bool(os.getenv('BREVO_API_KEY')),
            "BREVO_EMAIL": os.getenv('BREVO_EMAIL', 'Not set'),
            "USE_TESTMAIL_TESTING": os.getenv('USE_TESTMAIL_TESTING', 'Not set'),
            "FRONTEND_URL": os.getenv('FRONTEND_URL', 'Not set'),
        }
    }
    
    return JsonResponse(config)
