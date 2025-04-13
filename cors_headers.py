"""
CORS headers for deployment on hosting platforms like Render.com

This module can be used by wsgi.py or asgi.py to apply CORS headers
at the server level, bypassing Django's internal CORS handling
"""
import os
import logging
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('cors_middleware')

class CORSMiddleware:
    """Apply CORS headers at the WSGI/ASGI level before Django processes the request"""
    
    def __init__(self, app):
        self.app = app
        logger.info("CORS Middleware initialized")
    
    def __call__(self, environ, start_response):
        # Always log the request type and path
        request_method = environ.get('REQUEST_METHOD', 'UNKNOWN')
        path_info = environ.get('PATH_INFO', 'UNKNOWN')
        origin = environ.get('HTTP_ORIGIN', 'UNKNOWN')
        
        logger.info(f"CORS: {request_method} request to {path_info} from origin {origin}")
        
        # For OPTIONS preflight requests, we'll handle them directly
        if request_method == 'OPTIONS':
            logger.info(f"Handling OPTIONS preflight request to {path_info}")
            
            # Get headers needed for CORS response
            headers = [
                ('Content-Type', 'text/plain'),
                ('Access-Control-Allow-Origin', origin),
                ('Access-Control-Allow-Credentials', 'true'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept'),
                ('Access-Control-Max-Age', '86400'),  # 24 hours
                ('Vary', 'Origin'),  # Important for caching
            ]
            
            # Start the response ourselves
            start_response('200 OK', headers)
            return [b'']  # Empty response body
        
        # Define a wrapper for start_response that adds CORS headers
        def cors_start_response(status, headers, exc_info=None):
            # Create a new list with all original headers
            new_headers = list(headers)
            
            # Check if CORS headers already exist (added by EnterpriseMiddleware)
            existing_header_names = {h[0].lower() for h in headers}
            
            # Only add CORS headers if they haven't been added already
            if 'access-control-allow-origin' not in existing_header_names:
                cors_headers = {
                    'Access-Control-Allow-Origin': origin,
                    'Access-Control-Allow-Credentials': 'true',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With, Accept',
                    'Vary': 'Origin'
                }
                
                # Add CORS headers that don't already exist
                for name, value in cors_headers.items():
                    if name.lower() not in existing_header_names:
                        new_headers.append((name, value))
            
            logger.debug(f"Response status: {status}")
            logger.debug(f"Response headers: {new_headers}")
            
            # Call the original start_response with our modified headers
            return start_response(status, new_headers, exc_info)
        
        # Continue with normal processing for non-OPTIONS requests
        try:
            return self.app(environ, cors_start_response)
        except Exception as e:
            logger.error(f"Error in CORS middleware: {str(e)}")
            
            # Even on error, ensure CORS headers are returned
            headers = [
                ('Content-Type', 'text/plain'),
                ('Access-Control-Allow-Origin', origin),
                ('Access-Control-Allow-Credentials', 'true'),
                ('Vary', 'Origin'),
            ]
            
            # Return a 500 error with CORS headers
            start_response('500 Internal Server Error', headers)
            return [b'Internal Server Error']
