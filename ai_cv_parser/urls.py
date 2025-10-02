from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AICVParserViewSet
from . import views

router = DefaultRouter()
router.register(r"parser", AICVParserViewSet, basename="ai-cv-parser")

urlpatterns = [
    path("", include(router.urls)),
]
