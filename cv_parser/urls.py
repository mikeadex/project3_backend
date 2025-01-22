from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CVParserViewSet

router = DefaultRouter()
router.register(r'cv-parser', CVParserViewSet, basename='cv-parser')

urlpatterns = [
    path('', include(router.urls)),
]