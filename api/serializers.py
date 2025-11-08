from django.contrib.auth.models import User
from rest_framework import serializers
from django.conf import settings
from dj_rest_auth.serializers import PasswordResetSerializer as DefaultPasswordResetSerializer
from dj_rest_auth.registration.serializers import RegisterSerializer

class CustomRegisterSerializer(RegisterSerializer):
    """Custom registration serializer that doesn't require username"""
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    
    def validate_username(self, username):
        """Make username optional and auto-generate from email if not provided"""
        return username
    
    def get_cleaned_data(self):
        """Override to handle optional username"""
        data = super().get_cleaned_data()
        
        # If no username provided, generate one from email
        if not data.get('username'):
            email = data.get('email', '')
            # Use email prefix as username, make it unique
            username_base = email.split('@')[0] if email else 'user'
            username = username_base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1
            data['username'] = username
            
        return data

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class CustomPasswordResetSerializer(DefaultPasswordResetSerializer):
    def save(self):
        request = self.context.get('request')
        # Set up the email options
        opts = {
            'use_https': request.is_secure(),
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL'),
            'email_template_name': 'registration/password_reset_email.html',
            'subject_template_name': 'registration/password_reset_subject.txt',
            'request': request,
            'html_email_template_name': 'registration/password_reset_email.html',
            'extra_email_context': {
                'frontend_url': settings.FRONTEND_URL,
                'site_name': settings.SITE_NAME,
            }
        }
        self.reset_form.save(**opts)
