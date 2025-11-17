from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from .signals import get_social_login_redirect
import logging

logger = logging.getLogger(__name__)

class CorsMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware for handling cross-origin requests
    """
    
    def process_response(self, request, response):
        """
        Add CORS headers to all responses
        """
        # Allow all origins for API requests
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response['Access-Control-Allow-Credentials'] = 'true'
        
        return response
    
    def process_request(self, request):
        """
        Handle preflight OPTIONS requests
        """
        if request.method == 'OPTIONS':
            from django.http import HttpResponse
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
            response['Access-Control-Allow-Credentials'] = 'true'
            return response

class SocialLoginRedirectMiddleware(MiddlewareMixin):
    """
    Middleware to intercept social login redirects and replace them with JWT token redirects
    """
    
    def process_response(self, request, response):
        """
        Process the response and check if we need to override social login redirects
        """
        
        # Add comprehensive logging for ALL requests
        if hasattr(request, 'path'):
            logger.debug(f"🔍 MIDDLEWARE: Processing request path: {request.path}")
            logger.debug(f"   User authenticated: {getattr(request, 'user', 'No user').is_authenticated if hasattr(request, 'user') else False}")
            logger.debug(f"   Response type: {type(response).__name__}")
            if isinstance(response, HttpResponseRedirect):
                logger.debug(f"   Redirect URL: {getattr(response, 'url', 'No URL')}")
        
        # Check if this is a redirect response from social login
        social_callback_patterns = [
            'google/login/callback',
            'github/login/callback', 
            'linkedin_oauth2/login/callback',
            '3rdparty/signup',  # GitHub and LinkedIn use this path
            'socialaccount/signup',  # Alternative allauth signup path
        ]
        
        is_social_callback = (isinstance(response, HttpResponseRedirect) and 
                            hasattr(request, 'path') and 
                            any(pattern in request.path for pattern in social_callback_patterns))
        
        # ALSO check for 200 OK HTML responses on callback paths (allauth rendering template)
        is_callback_html = (hasattr(request, "path") and 
                           hasattr(response, "status_code") and
                           response.status_code == 200 and
                           hasattr(request, "user") and request.user.is_authenticated and
                           any(pattern in request.path for pattern in social_callback_patterns))
        
        # DEBUG: Log what is_callback_html evaluates to
        if hasattr(request, "path") and "login/callback" in request.path:
            logger.info(f"🔍 DEBUG is_callback_html check for {request.path}:")
            logger.info(f"   has path: {hasattr(request, 'path')}")
            logger.info(f"   has status_code: {hasattr(response, 'status_code')}")
            logger.info(f"   status_code value: {response.status_code if hasattr(response, 'status_code') else 'None'}")
            logger.info(f"   status == 200: {response.status_code == 200 if hasattr(response, 'status_code') else False}")
            logger.info(f"   has user: {hasattr(request, 'user')}")
            logger.info(f"   user.is_authenticated: {request.user.is_authenticated if hasattr(request, 'user') else 'No user'}")
            logger.info(f"   pattern match: {any(pattern in request.path for pattern in social_callback_patterns)}")
            logger.info(f"   is_callback_html = {is_callback_html}")
        
        if is_social_callback:
            
            logger.info(f"🔍 MIDDLEWARE: Intercepted social login redirect")
            logger.info(f"   Original redirect: {response.url if hasattr(response, 'url') else 'Unknown'}")
            
            # Check if we have a stored social login redirect
            social_redirect = get_social_login_redirect()
            if social_redirect:
                logger.info(f"🚀 MIDDLEWARE: Replacing with JWT redirect: {social_redirect.url}")
                return social_redirect
            
            # Also check session for backup
            elif hasattr(request, 'session') and request.session.get('social_login_success'):
                redirect_url = request.session.get('social_login_redirect')
                if redirect_url:
                    logger.info(f"🚀 MIDDLEWARE: Using session JWT redirect: {redirect_url}")
                    # Clear the session flags
                    request.session.pop('social_login_success', None)
                    request.session.pop('social_login_redirect', None)
                    return HttpResponseRedirect(redirect_url)
        
        # Handle 200 OK HTML responses on callback paths
        elif is_callback_html:
            logger.info(f"🔍 MIDDLEWARE: Detected 200 OK HTML response on callback path: {request.path}")
            logger.info(f"   User: {request.user.email if hasattr(request.user, 'email') else 'Unknown'}")
            
            # Generate JWT tokens for authenticated social user
            from rest_framework_simplejwt.tokens import RefreshToken
            from django.conf import settings
            
            refresh = RefreshToken.for_user(request.user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            jwt_redirect_url = f"{settings.FRONTEND_URL}/social-callback?status=success&access={access_token}&refresh={refresh_token}"
            logger.info(f"🚀 MIDDLEWARE: Replacing HTML response with JWT redirect: {jwt_redirect_url}")
            
            return HttpResponseRedirect(jwt_redirect_url)
        
        # COMPREHENSIVE CHECK: Catch ANY allauth page access by authenticated social users
        elif (hasattr(request, 'user') and request.user.is_authenticated and 
              hasattr(request, 'path')):
            
            # Allauth paths that social users should NOT see
            allauth_paths = [
                '/accounts/',
                '/api/auth/registration/account-email-verification-sent/',
                '/accounts/login/',
                '/accounts/signup/',
                '/accounts/3rdparty/signup/',
                '/accounts/socialaccount/signup/',
            ]
            
            # Check if current request path is an allauth page
            is_allauth_page = any(path in request.path for path in allauth_paths)
            
            # Also check for redirect responses to allauth pages
            is_allauth_redirect = False
            if isinstance(response, HttpResponseRedirect):
                redirect_url = str(getattr(response, 'url', ''))
                is_allauth_redirect = any(page in redirect_url for page in [
                    '/accounts/signup/',
                    '/accounts/login/', 
                    '/accounts/3rdparty/signup/',
                    '/accounts/socialaccount/signup/',
                    'ellacv.com/dashboard'  # Direct dashboard redirects
                ])
            
            if (is_allauth_page or is_allauth_redirect):
                logger.info(f"🔄 MIDDLEWARE: Authenticated user accessing allauth page")
                logger.info(f"   User: {request.user.email if hasattr(request.user, 'email') else 'Unknown'}")
                logger.info(f"   Path: {request.path}")
                logger.info(f"   Is redirect: {isinstance(response, HttpResponseRedirect)}")
                if isinstance(response, HttpResponseRedirect):
                    logger.info(f"   Redirect URL: {getattr(response, 'url', 'Unknown')}")
                
                # Check if user has social accounts (indicating social login)
                if hasattr(request.user, 'socialaccount_set') and request.user.socialaccount_set.exists():
                    logger.info(f"🔐 MIDDLEWARE: Social user detected, generating JWT redirect")
                    
                    # Generate JWT tokens for this authenticated social user
                    from rest_framework_simplejwt.tokens import RefreshToken
                    from django.conf import settings
                    
                    refresh = RefreshToken.for_user(request.user)
                    access_token = str(refresh.access_token)
                    refresh_token = str(refresh)
                    
                    jwt_redirect_url = f'{settings.FRONTEND_URL}/social-callback?status=success&access={access_token}&refresh={refresh_token}'
                    logger.info(f"🚀 MIDDLEWARE: Generated JWT redirect: {jwt_redirect_url}")
                    
                    return HttpResponseRedirect(jwt_redirect_url)
                else:
                    logger.info(f"ℹ️  MIDDLEWARE: User has no social accounts, allowing allauth page")
        
        return response