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
            
            # Access control headers to add
            cors_headers = [
                ('Access-Control-Allow-Origin', origin or '*'),
                ('Access-Control-Allow-Credentials', 'true'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
                ('Access-Control-Max-Age', '86400'),  # 24 hours
            ]
            
            # Add CORS headers to every response
            new_headers = []
            for header in headers:
                # Skip existing CORS headers to avoid duplicates
                if not header[0].startswith('Access-Control-'):
                    new_headers.append(header)
            
            # Add our CORS headers
            new_headers.extend(cors_headers)
            
            # Special handling for OPTIONS requests (preflight)
            if environ.get('REQUEST_METHOD') == 'OPTIONS':
                # Return 200 OK for preflight requests with CORS headers only
                return start_response('200 OK', new_headers, exc_info)
                
            return start_response(status, new_headers, exc_info)
        
        # Handle OPTIONS preflight request directly
        if environ.get('REQUEST_METHOD') == 'OPTIONS':
            # For OPTIONS requests, return a 200 OK with CORS headers immediately
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
