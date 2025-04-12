"""
Custom middleware for handling CORS and authentication issues
"""
import logging

logger = logging.getLogger('api')

class CorsMiddleware:
    """
    Middleware to add CORS headers to every response, 
    especially useful for error responses where Django CORS headers middleware might not run
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before the view is called
        response = self.get_response(request)
        
        # Add CORS headers to every response
        response["Access-Control-Allow-Origin"] = request.headers.get('Origin', '*')
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With, Accept"
        )
        
        return response

    def process_exception(self, request, exception):
        """
        Handle exceptions and ensure CORS headers are still returned
        """
        logger.error(f"Exception in request: {str(exception)}")
        
        # Return a response with CORS headers even for exceptions
        from django.http import JsonResponse
        response = JsonResponse({"error": str(exception)}, status=500)
        
        response["Access-Control-Allow-Origin"] = request.headers.get('Origin', '*')
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With, Accept"
        )
        
        return response
