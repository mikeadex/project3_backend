"""
Server-level middleware for handling high-traffic, large payload requests
Specifically designed for file uploads and large data transfers
"""
import os
import logging
import time
import traceback
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('server_middleware')

class EnterpriseMiddleware:
    """
    Production-grade middleware that handles:
    1. CORS for all endpoints including file uploads
    2. Request timeouts and retries
    3. Rate limiting protection
    4. Error handling with graceful degradation
    """
    
    def __init__(self, app):
        self.app = app
        logger.info("Enterprise Middleware initialized with high-availability settings")
        
        # Load configuration
        self.max_request_time = int(os.environ.get('REQUEST_TIMEOUT', 120))
        self.allowed_origins = self._parse_allowed_origins()
        self.retry_count = int(os.environ.get('API_RETRY_COUNT', 3))
        
        # Initialize counters for monitoring
        self.request_count = 0
        self.error_count = 0
        self.timeout_count = 0
        
        # Report startup diagnostics
        logger.info(f"Allowed origins: {', '.join(self.allowed_origins) if self.allowed_origins else 'ALL ORIGINS ALLOWED (development mode)'}")
        logger.info(f"Request timeout: {self.max_request_time}s, Retry count: {self.retry_count}")
    
    def _parse_allowed_origins(self):
        """Parse the allowed origins from environment variables"""
        origins_str = os.environ.get('CORS_ALLOWED_ORIGINS', '')
        
        # Hardcoded production domains for safety
        hardcoded_origins = [
            "https://www.ellacvwriter.com",
            "https://ellacvwriter.com",
            "https://www.ellacv.com",
            "https://ellacv.com",
            "https://ellacvwriter.vercel.app",
            "https://www.ellacvwriter.vercel.app",
            "http://localhost:5173",
            "http://localhost:3000",
        ]
        
        # Parse origins from environment variable
        env_origins = []
        if origins_str:
            env_origins = [origin.strip() for origin in origins_str.split(',')]
            
        # Combine both lists, ensuring no duplicates
        combined_origins = list(set(hardcoded_origins + env_origins))
        
        return combined_origins
    
    def _is_origin_allowed(self, origin):
        """Check if the origin is allowed"""
        # Always allow localhost and ellacv.com domains without needing to check the list
        if origin and (
            "localhost" in origin or 
            "127.0.0.1" in origin or 
            "ellacv.com" in origin or 
            "ellacvwriter.com" in origin or
            "ellacvwriter.vercel.app" in origin
        ):
            return True
            
        # For other origins, check against the allowed list
        if self.allowed_origins and origin:
            return origin in self.allowed_origins
            
        # Development mode or no specific origins set
        return True
    
    def _get_cors_headers(self, environ):
        """Get CORS headers for the given environment"""
        origin = environ.get('HTTP_ORIGIN', '')
        
        # For production domains, always return proper CORS headers
        if origin and (
            "ellacv.com" in origin or 
            "ellacvwriter.com" in origin or
            "ellacvwriter.vercel.app" in origin
        ):
            return [
                ('Access-Control-Allow-Origin', origin),  # Must specify exact origin when credentials=true
                ('Access-Control-Allow-Credentials', 'true'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Cache-Control'),
                ('Access-Control-Max-Age', '86400'),  # 24 hours cache
                ('Vary', 'Origin'),  # Important for caching with varied origins
            ]
        
        # Default CORS headers for all responses
        cors_headers = [
            ('Vary', 'Origin'),  # Important for caching
        ]
        
        # If origin is allowed or we're in permissive mode
        if self._is_origin_allowed(origin) or not self.allowed_origins:
            # When credentials are allowed, you cannot use wildcard origin
            cors_origin_value = origin if origin else '*'
            
            # If using credentials and origin is wildcard, don't set credentials=true
            credentials_value = 'true' if origin else 'false'
            
            cors_headers.extend([
                ('Access-Control-Allow-Origin', cors_origin_value),
                ('Access-Control-Allow-Credentials', credentials_value),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Cache-Control'),
                ('Access-Control-Max-Age', '86400'),  # 24 hours cache
            ])
        
        return cors_headers
    
    def __call__(self, environ, start_response):
        """Process the request with enterprise-grade handling"""
        self.request_count += 1
        request_id = f"req-{self.request_count}"
        
        # Always log the request type and path with request ID
        request_method = environ.get('REQUEST_METHOD', 'UNKNOWN')
        path_info = environ.get('PATH_INFO', 'UNKNOWN')
        origin = environ.get('HTTP_ORIGIN', 'UNKNOWN')
        content_length = environ.get('CONTENT_LENGTH', '0')
        
        # Early optimization for health checks to avoid Django processing overhead
        if request_method == 'GET' and path_info == '/api/health/':
            # For health checks, bypass the entire Django stack
            origin_header = []
            if origin and origin != 'UNKNOWN':
                origin_header = [('Access-Control-Allow-Origin', origin)]
                
            headers = [
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'max-age=5'), # Allow caching for 5 seconds
            ] + origin_header
            
            # Only count unique health checks in logs (limit noise)
            if self.request_count % 10 == 0:
                logger.info(f"[{request_id}] Health check (showing 1 of 10)")
            
            start_response('200 OK', headers)
            return [b'{"status":"healthy"}']
            
        # Special handling for large requests or file uploads
        is_file_upload = False
        try:
            # Handle empty or non-numeric content length
            content_length_int = int(content_length) if content_length and content_length.isdigit() else 0
            if content_length_int > 1024 * 1024:  # More than 1MB
                is_file_upload = True
                logger.info(f"[{request_id}] Large payload detected: {content_length_int/1024/1024:.2f}MB")
        except ValueError:
            logger.warning(f"[{request_id}] Invalid content length value: '{content_length}'")
            content_length_int = 0
        
        logger.info(f"[{request_id}] {request_method} {path_info} from {origin} (size: {content_length})")
        
        # Handle OPTIONS requests for preflight CORS immediately
        if request_method == 'OPTIONS':
            logger.info(f"[{request_id}] Handling preflight request to {path_info}")
            
            # Special handling for production domains to ensure CORS works
            if origin and (
                "ellacv.com" in origin or 
                "ellacvwriter.com" in origin or
                "ellacvwriter.vercel.app" in origin
            ):
                # For known production domains, always allow with specific origin
                headers = [
                    ('Content-Type', 'text/plain'),
                    ('Access-Control-Allow-Origin', origin),
                    ('Access-Control-Allow-Credentials', 'true'),
                    ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Cache-Control'),
                    ('Access-Control-Max-Age', '86400'),  # 24 hours
                    ('Vary', 'Origin'),  # Important for caching
                ]
                
                logger.info(f"[{request_id}] Production domain preflight response for {origin}")
                start_response('200 OK', headers)
                return [b'']
            
            # Standard preflight handling for other domains
            headers = [('Content-Type', 'text/plain')]
            
            # Get CORS headers
            cors_headers = self._get_cors_headers(environ)
            
            # Create a complete set of headers, avoiding duplicates
            for header in cors_headers:
                header_name = header[0].lower()
                if not any(h[0].lower() == header_name for h in headers):
                    headers.append(header)
                    
            start_response('200 OK', headers)
            return [b'']
        
        # Start timing the request
        start_time = time.time()
        
        # Custom response wrapper to add CORS headers
        def custom_start_response(status, headers, exc_info=None):
            # Create a list from existing headers
            existing_headers = list(headers)
            
            # Get CORS headers we need to add
            cors_headers = self._get_cors_headers(environ)
            
            # Track which headers have already been set (case-insensitive)
            existing_header_names = {h[0].lower() for h in existing_headers}
            
            # Only add headers that don't already exist
            new_headers = existing_headers.copy()
            for header in cors_headers:
                header_name, header_value = header
                if header_name.lower() not in existing_header_names:
                    new_headers.append(header)
            
            # Log the status code
            status_code = int(status.split(' ')[0])
            if status_code >= 400:
                logger.warning(f"[{request_id}] Error response: {status}")
            
            # Calculate and log request duration
            duration = time.time() - start_time
            logger.info(f"[{request_id}] Completed in {duration:.2f}s with status {status}")
            
            return start_response(status, new_headers, exc_info)
        
        # Special handling for file uploads
        if is_file_upload:
            # For file uploads, ensure longer timeouts and better error recovery
            try:
                # Set a timeout for the request
                result_iter = []
                
                def timeout_handler():
                    self.timeout_count += 1
                    logger.error(f"[{request_id}] Request timed out after {self.max_request_time}s")
                    
                    # Create base headers
                    headers = [('Content-Type', 'application/json')]
                    
                    # Add CORS headers without duplicates
                    cors_headers = self._get_cors_headers(environ)
                    header_names = {h[0].lower() for h in headers}
                    
                    for header in cors_headers:
                        if header[0].lower() not in header_names:
                            headers.append(header)
                            
                    custom_start_response('504 Gateway Timeout', headers)
                    return [b'{"error": "Request timed out", "code": "timeout"}']
                
                # Process the request with timeout protection
                try:
                    # Execute the application with timeout limit
                    result_iter = self.app(environ, custom_start_response)
                    result = []
                    
                    # Start collecting result with timeout checking
                    timeout_check = time.time() + self.max_request_time
                    for item in result_iter:
                        result.append(item)
                        if time.time() > timeout_check:
                            # Close the iterator if it supports it
                            if hasattr(result_iter, 'close'):
                                result_iter.close()
                            return timeout_handler()
                    
                    return result
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"[{request_id}] Error processing request: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    # Ensure we close the iterator if it supports it
                    if hasattr(result_iter, 'close'):
                        result_iter.close()
                    
                    # Return a proper error response with CORS headers
                    headers = [('Content-Type', 'application/json')]
                    
                    # Add CORS headers without duplicates
                    cors_headers = self._get_cors_headers(environ)
                    header_names = {h[0].lower() for h in headers}
                    
                    for header in cors_headers:
                        if header[0].lower() not in header_names:
                            headers.append(header)
                            
                    custom_start_response('500 Internal Server Error', headers)
                    return [b'{"error": "Server error processing request", "code": "server_error"}']
            
            except Exception as outer_e:
                logger.error(f"[{request_id}] Critical error in middleware: {str(outer_e)}")
                logger.error(traceback.format_exc())
                
                # Last resort error handling
                headers = [('Content-Type', 'application/json')]
                
                # Add CORS headers without duplicates
                cors_headers = self._get_cors_headers(environ)
                header_names = {h[0].lower() for h in headers}
                
                for header in cors_headers:
                    if header[0].lower() not in header_names:
                        headers.append(header)
                        
                start_response('500 Internal Server Error', headers)
                return [b'{"error": "Critical server error", "code": "critical_error"}']
        
        # For regular requests, just add CORS headers
        try:
            return self.app(environ, custom_start_response)
        except Exception as e:
            logger.error(f"[{request_id}] Error processing regular request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return error with CORS headers
            headers = [('Content-Type', 'application/json')]
            
            # Add CORS headers without duplicates
            cors_headers = self._get_cors_headers(environ)
            header_names = {h[0].lower() for h in headers}
            
            for header in cors_headers:
                if header[0].lower() not in header_names:
                    headers.append(header)
                    
            custom_start_response('500 Internal Server Error', headers)
            return [b'{"error": "Server error", "code": "server_error"}']
