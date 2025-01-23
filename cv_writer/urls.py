from django.urls import path
from . import views

urlpatterns = [
    path('cv/', views.CvWriterListCreate.as_view(), name='cv-list-create'),
    path('cv/<int:pk>/', views.CvWriterDetailView.as_view(), name='cv-detail'),
    path('education/', views.EducationListCreate.as_view(), name='education-list-create'),
    path('education/<int:pk>/', views.EducationDetailView.as_view(), name='education-detail'),
    path('experience/', views.ExperienceListCreate.as_view(), name='experience-list-create'),
    path('experience/<int:pk>/', views.ExperienceDetailView.as_view(), name='experience-detail'),
    path('skill/', views.SkillListCreate.as_view(), name='skill-list-create'),
    path('skill/<int:pk>/', views.SkillDetailView.as_view(), name='skill-detail'),
    path('certification/', views.CertificationListCreate.as_view(), name='certification-list-create'),
    path('certification/<int:pk>/', views.CertificationDetailView.as_view(), name='certification-detail'),
]