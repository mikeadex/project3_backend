from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AICVParserViewSet
from .guest_views import GuestCVAnalysisViewSet
from . import views

router = DefaultRouter()
router.register(r"parser", AICVParserViewSet, basename="ai-cv-parser")
router.register(r"guest", GuestCVAnalysisViewSet, basename="guest-cv-analysis")

urlpatterns = [
    path("", include(router.urls)),
]
