from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AICVParserViewSet
from . import views

router = DefaultRouter()
router.register(r'parser', AICVParserViewSet, basename='ai-cv-parser')

urlpatterns = [
    path('rewrite/', views.rewrite_cv, name='rewrite-cv'),
    path('rewrite/create_session/', views.create_rewrite_session, name='create-rewrite-session'),
    path('rewrite/process/<int:session_id>/', views.process_rewrite_session, name='process-rewrite-session'),
    path('parser/analyze/', AICVParserViewSet.as_view({'post': 'analyze'}), name='analyze-cv'),
    path('parser/clear-all/', views.clear_all_parsed_cv_data, name='clear-all-parsed-cv-data'),
    path('analyze/', views.analyze_cv, name='analyze-cv-standalone'),
    path('', include(router.urls)),
]