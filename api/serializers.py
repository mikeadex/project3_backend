from django.contrib.auth.models import User
from rest_framework import serializers
from django.conf import settings
from dj_rest_auth.serializers import PasswordResetSerializer as DefaultPasswordResetSerializer

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
