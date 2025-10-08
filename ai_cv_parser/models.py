from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import secrets

User = get_user_model()


class ParsedCV(models.Model):
    """Model to store parsed CV data"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_parsed_cvs",
        null=True,
        blank=True,
    )
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # Guest session support
    session_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True, db_index=True
    )
    is_guest = models.BooleanField(default=False, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Raw text content
    raw_text = models.TextField(blank=True)

    # Extracted text from document
    extracted_text = models.TextField(blank=True)

    # Temporary file path for processing
    temp_file_path = models.CharField(max_length=512, blank=True)

    # Parsed data - using JSONField for flexibility
    parsed_data = models.JSONField(default=dict, blank=True)

    # File metadata
    file_size = models.IntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)

    # Processing metadata
    processing_time = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=50,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("queued", "Queued"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
    )
    error_message = models.TextField(blank=True)

    # Analysis data and metadata
    analysis_data = models.JSONField(null=True, blank=True)  # Store CV analysis results
    analysis_date = models.DateTimeField(
        null=True, blank=True
    )  # Track when analysis was performed

    def __str__(self):
        return f"{self.file_name} - {self.user.username} ({self.status})"

    class Meta:
        verbose_name = "Parsed CV"
        verbose_name_plural = "Parsed CVs"
        ordering = ["-uploaded_at"]


class CVRewriteSession(models.Model):
    """Model to store temporary CV rewrite session data"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="cv_rewrite_sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Reference to the source CV
    cv_id = models.IntegerField(null=True, blank=True)

    # Input data
    input_data = models.JSONField(default=dict)

    # Output data after AI processing
    output_data = models.JSONField(default=dict, blank=True)

    # Result data (complete rewrite results)
    result = models.JSONField(default=dict, blank=True)

    # Processing status
    status = models.CharField(
        max_length=50,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("error", "Error"),
            ("failed", "Failed"),
        ],
    )
    error_message = models.TextField(blank=True)

    # New CV created from this session
    new_cv_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"CV Rewrite Session - {self.user.username} ({self.status})"

    class Meta:
        verbose_name = "CV Rewrite Session"
        verbose_name_plural = "CV Rewrite Sessions"
        ordering = ["-created_at"]


class EmailVerification(models.Model):
    """
    Track email verifications for CV analysis access.
    Prevents abuse by limiting 1 CV analysis per verified email.
    Supports Phase 2: Email verification for premium features.
    """

    # Core fields
    email = models.EmailField(db_index=True)
    parsed_cv = models.ForeignKey(
        "ParsedCV", on_delete=models.CASCADE, related_name="email_verifications"
    )
    name = models.CharField(max_length=255, blank=True)

    # Verification token and status
    verification_token = models.CharField(max_length=64, unique=True, db_index=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Metadata for tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()

    # Email tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    link_clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "email_verifications"
        verbose_name = "Email Verification"
        verbose_name_plural = "Email Verifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "is_verified"]),
            models.Index(fields=["verification_token"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["expires_at"]),
        ]
        # Prevent duplicate email usage - one verified email per CV
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(is_verified=True),
                name="unique_verified_cv_email",
            )
        ]

    def __str__(self):
        status = "Verified" if self.is_verified else "Pending"
        return f"{self.email} - {status}"

    @classmethod
    def generate_token(cls):
        """Generate secure random token for email verification"""
        return secrets.token_urlsafe(32)

    @classmethod
    def create_verification(
        cls, email, parsed_cv, name="", ip_address=None, user_agent=None
    ):
        """
        Create new email verification request

        Args:
            email: Email address to verify
            parsed_cv: ParsedCV instance this verification is for
            name: User's name (optional)
            ip_address: Client IP address (optional)
            user_agent: Client user agent (optional)

        Returns:
            EmailVerification instance
        """
        token = cls.generate_token()
        expires_at = timezone.now() + timedelta(hours=24)

        return cls.objects.create(
            email=email.lower().strip(),
            parsed_cv=parsed_cv,
            name=name,
            verification_token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def is_expired(self):
        """Check if verification has expired"""
        return timezone.now() > self.expires_at

    def mark_verified(self):
        """Mark verification as complete"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.link_clicked_at = timezone.now()
        self.save(update_fields=["is_verified", "verified_at", "link_clicked_at"])

    def mark_email_sent(self):
        """Mark verification email as sent"""
        self.email_sent = True
        self.email_sent_at = timezone.now()
        self.save(update_fields=["email_sent", "email_sent_at"])
