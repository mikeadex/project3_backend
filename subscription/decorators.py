from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .services import SubscriptionService

def require_subscription(feature):
    """
    Decorator to check if user has access to a feature based on their subscription
    
    Usage:
    @require_subscription('cv_generation')
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            # Check if user has access
            if not SubscriptionService.check_subscription_access(request.user, feature):
                return Response({
                    'error': 'Subscription required',
                    'feature': feature,
                    'message': f'Your current subscription does not include access to {feature}.'
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            # Log feature usage
            SubscriptionService.log_feature_usage(
                request.user,
                feature,
                details={'view': view_func.__name__}
            )
            
            # Call the view function
            return view_func(view_instance, request, *args, **kwargs)
        return _wrapped_view
    return decorator

def check_subscription(feature):
    """
    Decorator to check subscription without requiring it
    Adds subscription_active=True/False to the response
    
    Usage:
    @check_subscription('cv_analytics')
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            # Check subscription status
            has_access = SubscriptionService.check_subscription_access(
                request.user,
                feature
            )
            
            # Call the view function
            response = view_func(view_instance, request, *args, **kwargs)
            
            # If response is a Response object, add subscription info
            if isinstance(response, Response):
                if isinstance(response.data, dict):
                    response.data['subscription_active'] = has_access
                else:
                    # If data is not a dict, create a new response
                    original_data = response.data
                    response.data = {
                        'data': original_data,
                        'subscription_active': has_access
                    }
            
            return response
        return _wrapped_view
    return decorator 