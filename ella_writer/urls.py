from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from api.views import (
    CreateUserView,
    CustomConfirmEmailView,
    CustomPasswordResetView,
    CustomPasswordResetConfirmView
)
from dj_rest_auth.views import PasswordResetConfirmView
from dj_rest_auth.registration.views import VerifyEmailView
from allauth.account.views import confirm_email

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/v1/", include("cv_writer.urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("home.urls")),
    path("api/cv_parser/", include("cv_parser.urls")),
    path("cv_writer/", include("cv_writer.urls")),
    path("models_trainer/", include("models_trainer.urls")),
    path("api/linkedin/", include("linkedin_parser.urls")),
    
    # Authentication endpoints
    path("api/token/", TokenObtainPairView.as_view(), name="get_token"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("api/user/register/", CreateUserView.as_view(), name="register"),
    
    # Email confirmation
    path('accounts/confirm-email/<str:key>/', CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    path('accounts/confirm-email/', TemplateView.as_view(template_name='account/verification_sent.html'), name='account_email_verification_sent'),
    path('api/auth/registration/account-confirm-email/<str:key>/', TemplateView.as_view(template_name='account/email_confirm.html'), name='account_confirm_email'),
    path('api/auth/registration/account-confirm-email/', VerifyEmailView.as_view(), name='account_email_verification_sent'),
    re_path(r'^api/auth/registration/account-confirm-email/(?P<key>[-:\w]+)/$', TemplateView.as_view(template_name='account/email_confirm.html'), name='account_confirm_email'),
    
    # Password reset endpoints
    path("api/auth/password/reset/", CustomPasswordResetView.as_view(), name="rest_password_reset"),
    path("api/auth/password/reset/confirm/", CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    
    # dj-rest-auth URLs
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
