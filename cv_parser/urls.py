from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CVParserViewSet, ParseCVView, parsed_cv_detail, cv_from_parser, download_cv

router = DefaultRouter()
router.register(r'parsed_cvs', CVParserViewSet, basename='parsed_cv')

urlpatterns = [
    path('', include(router.urls)),
    path('parse-cv/', ParseCVView.as_view(), name='parse-cv'),
    # Add compatibility URL for frontend to match the API call in cvParser.js
    path('parse-document/', ParseCVView.as_view(), name='parse-document'),
    path('parsed-cv/<int:cv_id>/', parsed_cv_detail, name='parsed-cv-detail'),
    # Add compatibility URL for frontend requests
    path('parser/<int:cv_id>/', parsed_cv_detail, name='parser-detail'),
    path('cv-from-parser/', cv_from_parser, name='cv-from-parser'),
    path('download-cv/<int:cv_id>/', download_cv, name='download-cv'),
]