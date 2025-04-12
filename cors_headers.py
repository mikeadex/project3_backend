"""
CORS headers for deployment on hosting platforms like Render.com

This module can be used by wsgi.py or asgi.py to apply CORS headers
at the server level, bypassing Django's internal CORS handling
"""
import os
from urllib.parse import urlparse

class CORSMiddleware:
    """Apply CORS headers at the WSGI/ASGI level before Django processes the request"""
    
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):
            # Check for the origin header in the request
            origin = environ.get('HTTP_ORIGIN', '')
            
            # Track which CORS headers are already present
            existing_headers = {header[0].lower(): True for header in headers}
            
            # Access control headers to add (only if not already present)
            cors_headers = []
            
            # Only add headers that don't already exist
            if 'access-control-allow-origin' not in existing_headers:
                cors_headers.append(('Access-Control-Allow-Origin', origin or '*'))
                
            if 'access-control-allow-credentials' not in existing_headers:
                cors_headers.append(('Access-Control-Allow-Credentials', 'true'))
                
            if 'access-control-allow-methods' not in existing_headers:
                cors_headers.append(('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'))
                
            if 'access-control-allow-headers' not in existing_headers:
                cors_headers.append(('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'))
                
            if 'access-control-max-age' not in existing_headers:
                cors_headers.append(('Access-Control-Max-Age', '86400'))  # 24 hours
            
            # Combine existing headers with our CORS headers
            new_headers = list(headers) + cors_headers
            
            # Special handling for OPTIONS requests (preflight)
            if environ.get('REQUEST_METHOD') == 'OPTIONS' and status.startswith('404'):
                # Return 200 OK for preflight requests
                return start_response('200 OK', new_headers, exc_info)
                
            return start_response(status, new_headers, exc_info)
        
        # Handle OPTIONS preflight request directly
        if environ.get('REQUEST_METHOD') == 'OPTIONS':
            # For OPTIONS requests, check if this seems to be a preflight
            if 'HTTP_ACCESS_CONTROL_REQUEST_METHOD' in environ:
                # This is a preflight request, handle it directly
                headers = [
                    ('Content-Type', 'text/plain'),
                    ('Access-Control-Allow-Origin', environ.get('HTTP_ORIGIN', '*')),
                    ('Access-Control-Allow-Credentials', 'true'),
                    ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
                    ('Access-Control-Max-Age', '86400'),  # 24 hours
                ]
                start_response('200 OK', headers)
                return [b'']  # Empty response body
            
        # For non-OPTIONS requests, continue with normal processing
        return self.app(environ, custom_start_response)
