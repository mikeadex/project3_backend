from django.dispatch import receiver
from allauth.socialaccount.signals import pre_social_login
from allauth.account.signals import user_logged_in
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Global variable to store the redirect response
_social_login_redirect_response = None

@receiver(user_logged_in)
def handle_social_login_success(sender, request, user, **kwargs):
    """
    Signal handler for when a user logs in (including social login)
    Generates JWT tokens and stores redirect response
    """
    global _social_login_redirect_response
    
    # Only handle social logins (check if this is from a social provider)
    if hasattr(user, 'socialaccount_set') and user.socialaccount_set.exists():
        logger.info(f"🔐 SIGNAL: Social login detected for user: {user.username} ({user.email})")
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Create redirect URL with tokens
        redirect_url = f'{settings.FRONTEND_URL}/auth/social-callback?status=success&access={access_token}&refresh={refresh_token}'
        
        logger.info(f"🎯 SIGNAL: Generated JWT tokens for social user: {user.email}")
        logger.info(f"🚀 SIGNAL: Creating redirect response to: {redirect_url}")
        
        # Store redirect response globally so the middleware can use it
        _social_login_redirect_response = HttpResponseRedirect(redirect_url)
        
        # Also store in session as backup
        request.session['social_login_redirect'] = redirect_url
        request.session['social_login_success'] = True
        
    else:
        logger.debug(f"Regular login (non-social) for user: {user.username}")


def get_social_login_redirect():
    """
    Get the stored social login redirect response
    """
    global _social_login_redirect_response
    response = _social_login_redirect_response
    _social_login_redirect_response = None  # Clear after use
    return response
