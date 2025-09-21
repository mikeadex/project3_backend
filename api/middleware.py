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
        
        # Check if this is a redirect response from social login
        if (isinstance(response, HttpResponseRedirect) and 
            hasattr(request, 'path') and 
            'google/login/callback' in request.path):
            
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
        
        # Check for any redirect to the frontend dashboard (backup approach)
        elif (isinstance(response, HttpResponseRedirect) and 
              hasattr(response, 'url') and 
              'ellacv.com/dashboard' in response.url):
            
            # Check if this might be from a social login
            if hasattr(request, 'session') and request.session.get('social_login_success'):
                redirect_url = request.session.get('social_login_redirect')
                if redirect_url:
                    logger.info(f"🔄 MIDDLEWARE: Dashboard redirect intercepted, using JWT redirect: {redirect_url}")
                    # Clear the session flags
                    request.session.pop('social_login_success', None)
                    request.session.pop('social_login_redirect', None)
                    return HttpResponseRedirect(redirect_url)
        
        return response