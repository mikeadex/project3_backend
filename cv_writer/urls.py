from django.urls import path
from . import views

urlpatterns = [
    # CV Improvement endpoints
    path('cv/improve/section/', views.improve_section, name='improve-section'),
    path('cv/improve_summary/', views.improve_summary, name='improve_summary'),
    path('cv/rewrite/', views.rewrite_cv, name='rewrite_cv'),
    path('cv/improvements/<int:cv_id>/', views.get_cv_improvements, name='cv-improvements'),

    # Base CV endpoints
    path('cv/', views.CvWriterListCreate.as_view(), name='cv-list-create'),
    path('cv/<int:cv_id>/detail/', views.get_cv, name='get_cv'),
    path('cv/<int:cv_id>/improve/', views.improve_cv, name='improve-cv'),  

    # Section endpoints
    path('professional-summary/', views.ProfessionalSummaryListCreate.as_view(), name='professional-summary-list-create'),
    path('professional-summary/<int:id>/', views.ProfessionalSummaryDetailView.as_view(), name='professional-summary-detail'),
    
    path('experience/', views.ExperienceListCreate.as_view(), name='experience-list-create'),
    path('experience/<int:id>/', views.ExperienceDetailView.as_view(), name='experience-detail'),
    
    path('education/', views.EducationListCreate.as_view(), name='education-list-create'),
    path('education/<int:id>/', views.EducationDetailView.as_view(), name='education-detail'),
    
    path('skill/', views.SkillListCreate.as_view(), name='skill-list-create'),
    path('skill/<int:id>/', views.SkillDetailView.as_view(), name='skill-detail'),
    
    path('certification/', views.CertificationListCreate.as_view(), name='certification-list-create'),
    path('certification/<int:id>/', views.CertificationDetailView.as_view(), name='certification-detail'),

    path('interest/', views.InterestListCreate.as_view(), name='interest-list-create'),
    path('interest/<int:id>/', views.InterestDetailView.as_view(), name='interest-detail'),

    path('language/', views.LanguageListCreate.as_view(), name='language-list-create'),
    path('language/<int:id>/', views.LanguageDetailView.as_view(), name='language-detail'),

    path('reference/', views.ReferenceListCreate.as_view(), name='reference-list-create'),
    path('reference/<int:id>/', views.ReferenceDetailView.as_view(), name='reference-detail'),

    path('social-media/', views.SocialMediaListCreate.as_view(), name='social-media-list-create'),
    path('social-media/<int:id>/', views.SocialMediaDetailView.as_view(), name='social-media-detail'),

    # CV Versioning Endpoints
    path('cv/versions/', views.CVVersionListCreateView.as_view(), name='cv-version-list-create'),
    path('cv/versions/<int:pk>/', views.CVVersionDetailView.as_view(), name='cv-version-detail'),
    path('cv/versions/<int:pk>/set-primary/', views.SetPrimaryVersionView.as_view(), name='set-primary-version'),
    path('cv/versions/<int:pk>/clone/', views.CloneCVVersionView.as_view(), name='clone-cv-version'),
    path('cv/versions/<int:pk>/edit/', views.EditCVVersionView.as_view(), name='edit-cv-version'),
]