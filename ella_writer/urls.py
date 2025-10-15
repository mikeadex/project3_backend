from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.sitemaps.views import sitemap
from blog.sitemaps import BlogPostSitemap, CategorySitemap, StaticViewSitemap
from api.views import (
    CreateUserView,
    CustomConfirmEmailView,
    CustomPasswordResetView,
    CustomPasswordResetConfirmView,
    EmailVerificationSentView,
)
from dj_rest_auth.views import PasswordResetConfirmView
from dj_rest_auth.registration.views import VerifyEmailView
from allauth.account.views import confirm_email
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db import connection
from django.conf import settings
import time

# Sitemap configuration
sitemaps = {
    "blog": BlogPostSitemap,
    "categories": CategorySitemap,
    "static": StaticViewSitemap,
}


# Enhanced health check view with service status details
@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
def health_check(request):
    print("=== ENHANCED HEALTH CHECK CALLED ===")  # Debug
    start_time = time.time()
    health_data = {
        "status": "healthy",
        "timestamp": time.time(),
    }

    # Check database connection
    try:
        connection.ensure_connection()
        health_data["database"] = "connected"
    except Exception as e:
        health_data["database"] = "disconnected"
        health_data["status"] = "unhealthy"
        health_data["database_error"] = str(e)

    # Check AI services availability (DeepSeek, LLaMA, OpenAI)
    try:
        ai_services = {
            "deepseek": bool(
                hasattr(settings, "DEEPSEEK_API_KEY") and settings.DEEPSEEK_API_KEY
            ),
            "llama": bool(
                hasattr(settings, "LLAMA_API_KEY") and settings.LLAMA_API_KEY
            ),
            "openai": bool(
                hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY
            ),
        }
        health_data["ai_services"] = ai_services

        # Overall AI service status
        configured_count = sum(ai_services.values())
        if configured_count == 3:
            health_data["ai_service"] = "available"
        elif configured_count > 0:
            health_data["ai_service"] = "partial"
        else:
            health_data["ai_service"] = "not_configured"
    except Exception as e:
        health_data["ai_service"] = "error"
        health_data["ai_error"] = str(e)

    # Check file storage
    try:
        if hasattr(settings, "MEDIA_ROOT"):
            health_data["storage"] = "available"
        else:
            health_data["storage"] = "not_configured"
    except Exception as e:
        health_data["storage"] = "error"
        health_data["storage_error"] = str(e)

    # Calculate response time
    health_data["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

    # Mock uptime (in production, track actual uptime)
    health_data["uptime_seconds"] = 864000  # 10 days as example

    return JsonResponse(health_data, status=200)


urlpatterns = [
    path("admin/", admin.site.urls),
    # Sitemap
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    # ⚠️  CRITICAL: Custom social auth overrides MUST come BEFORE allauth.urls
    # Override specific allauth URLs with our SPA-compatible handlers
    path(
        "accounts/social/signup/",
        EmailVerificationSentView.as_view(),
        name="socialaccount_signup",
    ),
    path(
        "accounts/signup/", EmailVerificationSentView.as_view(), name="account_signup"
    ),
    path("accounts/login/", EmailVerificationSentView.as_view(), name="account_login"),
    path(
        "accounts/social/login/cancelled/",
        EmailVerificationSentView.as_view(),
        name="socialaccount_login_cancelled",
    ),
    path(
        "accounts/social/login/error/",
        EmailVerificationSentView.as_view(),
        name="socialaccount_login_error",
    ),
    # Default allauth URLs (after our custom overrides)
    path("accounts/", include("allauth.urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("home.urls")),
    path("api/cv_parser/", include("cv_parser.urls")),
    path("api/cv_writer/", include("cv_writer.urls")),
    path("models_trainer/", include("models_trainer.urls")),
    path("api/linkedin/", include("linkedin_parser.urls")),
    path("api/jobstract/", include("jobstract.urls")),
    path("api/ai_cv_parser/", include("ai_cv_parser.urls")),
    path("api/subscription/", include("subscription.urls")),
    path("api/blog/", include("blog.urls")),
    path("api/users/", include("users.urls")),  # Debug endpoints
    # Health check endpoint for monitoring
    path("api/health/", health_check, name="health_check"),
    path(
        "api/health-status/", health_check, name="health_status"
    ),  # Alternative endpoint
    # TinyMCE URLs
    path("tinymce/", include("tinymce.urls")),
    # Authentication endpoints
    path("api/token/", TokenObtainPairView.as_view(), name="get_token"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("api/user/register/", CreateUserView.as_view(), name="register"),
    # Email confirmation
    path(
        "api/user/verify-email/<key>",
        CustomConfirmEmailView.as_view(),
        name="account_confirm_email",
    ),
    path(
        "api/user/verify-email/",
        VerifyEmailView.as_view(),
        name="account_email_verification_sent",
    ),
    path(
        "api/user/password/reset/",
        CustomPasswordResetView.as_view(),
        name="rest_password_reset",
    ),
    path(
        "api/user/password/reset/confirm/<uidb64>/<token>/",
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    # Custom email confirmation view (must be before dj-rest-auth registration URLs)
    path(
        "api/auth/registration/account-confirm-email/<key>/",
        CustomConfirmEmailView.as_view(),
        name="account_confirm_email",
    ),
    path(
        "api/auth/registration/account-email-verification-sent/",
        EmailVerificationSentView.as_view(),
        name="account_email_verification_sent",
    ),
    # dj-rest-auth URLs
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
