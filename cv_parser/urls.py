from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CVParserViewSet

router = DefaultRouter()
router.register(r'parsed_cvs', CVParserViewSet, basename='parsed_cv')

urlpatterns = [
    path('', include(router.urls)),
]