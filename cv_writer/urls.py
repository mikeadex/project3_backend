from django.urls import path
from . import views

urlpatterns = [
    path('cv/', views.CvWriterListCreate.as_view(), name='cv-list-create'),
    path('cv/<int:id>/', views.CvWriterDetailView.as_view(), name='cv-detail'),
    path('education/', views.EducationListCreate.as_view(), name='education-list-create'),
    path('education/<int:id>/', views.EducationDetailView.as_view(), name='education-detail'),
    path('experience/', views.ExperienceListCreate.as_view(), name='experience-list-create'),
    path('experience/<int:id>/', views.ExperienceDetailView.as_view(), name='experience-detail'),
    path('professional-summary/', views.ProfessionalSummaryListCreate.as_view(), name='summary-list-create'),
    path('professional-summary/<int:id>/', views.ProfessionalSummaryDetailView.as_view(), name='summary-detail'),
    path('interest/', views.InterestListCreate.as_view(), name='interest-list-create'),
    path('interest/<int:id>/', views.InterestDetailView.as_view(), name='interest-detail'),
    path('skill/', views.SkillListCreate.as_view(), name='skill-list-create'),
    path('skill/<int:id>/', views.SkillDetailView.as_view(), name='skill-detail'),
    path('language/', views.LanguageListCreate.as_view(), name='language-list-create'),
    path('language/<int:id>/', views.LanguageDetailView.as_view(), name='language-detail'),
    path('certification/', views.CertificationListCreate.as_view(), name='certification-list-create'),
    path('certification/<int:id>/', views.CertificationDetailView.as_view(), name='certification-detail'),
    path('reference/', views.ReferenceListCreate.as_view(), name='reference-list-create'),
    path('reference/<int:id>/', views.ReferenceDetailView.as_view(), name='reference-detail'),
    path('social-media/', views.SocialMediaListCreate.as_view(), name='social-media-list-create'),
    path('social-media/<int:id>/', views.SocialMediaDetailView.as_view(), name='social-media-detail'),
]