from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LinkedInParserViewSet, 
    DisconnectLinkedInView,
    linkedin_auth,
    linkedin_callback
)

router = DefaultRouter()
router.register(r'profiles', LinkedInParserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', linkedin_auth, name='linkedin_auth'),
    path('callback/', linkedin_callback, name='linkedin_callback'),
    path('profile/', LinkedInParserViewSet.as_view({'get': 'profile'}), name='linkedin_profile'),
    path('disconnect/', DisconnectLinkedInView.as_view(), name='linkedin_disconnect'),
]
