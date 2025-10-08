"""
Email Service for CV Analysis Verification
Handles sending verification emails for Phase 2 implementation.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger("ai_cv_parser")


class VerificationEmailService:
    """Service for sending email verification emails"""

    @staticmethod
    def send_verification_email(verification, ats_score=None):
        """
        Send verification email to user

        Args:
            verification: EmailVerification instance
            ats_score: Optional ATS score to include in email

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get frontend URL from settings
            frontend_url = getattr(settings, "FRONTEND_URL", "https://ellacv.com")

            # Build verification link
            verification_link = (
                f"{frontend_url}/cv-analysis/verify/{verification.verification_token}/"
            )

            # Email context
            context = {
                "name": verification.name or "there",
                "verification_link": verification_link,
                "ats_score": ats_score or "N/A",
                "expires_hours": 24,
                "frontend_url": frontend_url,
            }

            # Render email templates
            html_message = render_to_string("emails/verification_email.html", context)
            plain_message = strip_tags(html_message)

            # Email subject
            subject = "🎯 Verify your email to unlock your CV analysis"

            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[verification.email],
                html_message=html_message,
                fail_silently=False,
            )

            # Mark email as sent
            verification.mark_email_sent()

            logger.info(f"Verification email sent to {verification.email}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send verification email to {verification.email}: {str(e)}"
            )
            return False

    @staticmethod
    def get_verification_url(token):
        """
        Get full verification URL for a token

        Args:
            token: Verification token

        Returns:
            str: Full verification URL
        """
        frontend_url = getattr(settings, "FRONTEND_URL", "https://ellacv.com")
        return f"{frontend_url}/cv-analysis/verify/{token}/"
