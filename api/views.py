from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from .serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from allauth.account.views import ConfirmEmailView
from django.shortcuts import render, redirect
from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from django.contrib import messages
import logging
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes

logger = logging.getLogger('django')

class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


class CustomConfirmEmailView(ConfirmEmailView):
    template_name = 'account/email_confirm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.debug(f"Context data: {context}")
        return context

    def post(self, request, *args, **kwargs):
        logger.debug("Processing email confirmation")
        try:
            response = super().post(request, *args, **kwargs)
            messages.success(request, 'Email successfully confirmed!')
            return redirect('/')
        except Exception as e:
            logger.error(f"Error confirming email: {str(e)}")
            messages.error(request, 'Error confirming email. Please try again.')
            return redirect('/')

class CustomPasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            # Return success even if user doesn't exist for security
            return Response({"detail": "Password reset email has been sent."})

        # Generate token and uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Create reset link with frontend URL
        reset_url = f"{settings.FRONTEND_URL}/reset-password/confirm/{uid}/{token}"

        # Render email template
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': settings.SITE_NAME,
            'protocol': 'http' if settings.DEBUG else 'https',
            'domain': settings.FRONTEND_URL.replace('http://', '').replace('https://', '')
        }

        # Render email template
        email_body = render_to_string('registration/password_reset_email.html', context)
        email_subject = f"{settings.SITE_NAME} - Password Reset"

        try:
            # Send email
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return Response({"detail": "Password reset email has been sent."})
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return Response(
                {"error": "Failed to send password reset email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CustomPasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            uid = request.data.get('uid')
            token = request.data.get('token')
            password1 = request.data.get('new_password1')
            password2 = request.data.get('new_password2')

            if not uid or not token or not password1 or not password2:
                return Response(
                    {"error": "Missing required fields"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if password1 != password2:
                return Response(
                    {"error": "Passwords do not match"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Decode the uidb64 to get the user
            try:
                uid = urlsafe_base64_decode(uid).decode()
                user = get_user_model().objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
                return Response(
                    {"error": "Invalid reset link"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check the token
            if not default_token_generator.check_token(user, token):
                return Response(
                    {"error": "Invalid or expired reset link"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Set the new password
            user.set_password(password1)
            user.save()

            return Response({"detail": "Password has been reset successfully"})

        except Exception as e:
            logger.error(f"Password reset confirm error: {str(e)}")
            return Response(
                {"error": "Failed to reset password"},
                status=status.HTTP_400_BAD_REQUEST
            )

# Create your views here.
