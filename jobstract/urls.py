from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'opportunities', views.OpportunityViewSet, basename='opportunity')
router.register(r'employers', views.EmployerViewSet, basename='employer')
router.register(r'applications', views.JobApplicationViewSet, basename='application')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),  # API endpoints will be at /api/jobstract/opportunities/ and /api/jobstract/employers/
    path('home/', views.home, name='home'),  # Home view will be at /api/jobstract/home/
]
