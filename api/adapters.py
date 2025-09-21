from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
import logging

logger = logging.getLogger(__name__)

class SPASocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for SPA (Single Page Application)
    Generates JWT tokens and redirects to frontend callback
    """
    
    def get_login_redirect_url(self, request):
        """
        Override the login redirect URL to include JWT tokens for SPA
        """
        logger.info(f"🔧 ADAPTER: get_login_redirect_url called for user: {getattr(request.user, 'email', 'Anonymous')}")
        
        if request.user.is_authenticated:
            # Generate JWT tokens for the authenticated user
            refresh = RefreshToken.for_user(request.user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            # Create SPA callback URL with tokens
            redirect_url = f'{settings.FRONTEND_URL}/auth/social-callback?status=success&access={access_token}&refresh={refresh_token}'
            
            logger.info(f"🔐 ADAPTER: Social login successful for user: {request.user.email} (ID: {request.user.id})")
            logger.info(f"🎯 ADAPTER: Generated JWT tokens - Access: {access_token[:20]}...")
            logger.info(f"🔄 ADAPTER: Returning redirect URL: {redirect_url}")
            
            return redirect_url
        else:
            # Fallback to default behavior if user not authenticated
            logger.error(f"❌ ADAPTER: Social login adapter called but user not authenticated")
            return super().get_login_redirect_url(request)
    
    def authentication_complete(self, request, sociallogin, **kwargs):
        """
        Override authentication complete to handle redirect with JWT tokens
        """
        logger.info(f"🔧 ADAPTER: authentication_complete called for user: {sociallogin.user.email if sociallogin.user else 'Unknown'}")
        
        # Call the parent method to complete authentication
        response = super().authentication_complete(request, sociallogin, **kwargs)
        
        # Check if user is now authenticated and generate JWT redirect
        if request.user.is_authenticated:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(request.user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            # Create redirect URL
            redirect_url = f'{settings.FRONTEND_URL}/auth/social-callback?status=success&access={access_token}&refresh={refresh_token}'
            
            logger.info(f"🚀 ADAPTER: Authentication complete, redirecting to: {redirect_url}")
            
            # Return HttpResponseRedirect instead of letting allauth handle it
            return HttpResponseRedirect(redirect_url)
        
        return response

class SPAAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for SPA compatibility
    """
    
    def get_login_redirect_url(self, request):
        """
        Override login redirect for regular logins too
        """
        if request.user.is_authenticated:
            # For regular logins, just redirect to frontend login success
            return f'{settings.FRONTEND_URL}/login-success'
        return super().get_login_redirect_url(request)
