from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CVParserViewSet

router = DefaultRouter()
router.register(r'', CVParserViewSet, basename='cv-parser')

urlpatterns = [
    path('', include(router.urls)),
    path('parse_document/', CVParserViewSet.as_view({'post': 'parse_document'}), name='parse_document'),
]