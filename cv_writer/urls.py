from django.urls import path
from . import views

urlpatterns = [
    # CV Improvement endpoints
    path('cv/improve/section/', views.improve_section, name='improve-section'),
    path('cv/improve_summary/', views.improve_summary, name='improve_summary'),
    path('cv/rewrite/', views.rewrite_cv, name='rewrite_cv'),
    path('cv/improvements/<int:cv_id>/', views.get_cv_improvements, name='cv-improvements'),
    
    # CV Rewrite Endpoints - direct paths with no 'cv/' prefix
    path('rewrite-cv/', views.initiate_rewrite_cv, name='initiate-rewrite-cv'),
    path('rewrite-cv/status/<str:session_id>/', views.rewrite_cv_status, name='rewrite-cv-status'),
    
    # Additional rewrite endpoints to match frontend requests
    path('rewrite/status/<str:session_id>/', views.rewrite_cv_status, name='rewrite-status'),
    
    # CV comparison endpoint
    path('rewrite/compare/<str:session_id>/', views.compare_rewritten_cv, name='compare-rewritten-cv'),
    
    # Save rewritten CV endpoint
    path('rewritten-cv/save/', views.save_rewritten_cv, name='save-rewritten-cv'),

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
    
    # CV Version management endpoints
    path('versions/', views.CVVersionListCreateView.as_view(), name='cv-versions'),
    path('versions/<int:pk>/', views.CVVersionDetailView.as_view(), name='cv-version-detail'),
    path('versions/<int:pk>/set-primary/', views.SetPrimaryVersionView.as_view(), name='set-primary-version'),
    path('versions/<int:pk>/clone/', views.CloneCVVersionView.as_view(), name='clone-cv-version'),
    path('versions/<int:pk>/edit/', views.EditCVVersionView.as_view(), name='edit-cv-version'),
    
    # Template selection endpoints
    path('templates/', views.CVTemplateListView.as_view(), name='cv-templates'),
    path('templates/<slug:slug>/', views.CVTemplateDetailView.as_view(), name='cv-template-detail'),
    path('cv/<int:pk>/set-template/', views.SetCVTemplateView.as_view(), name='set-cv-template'),
    path('cv/<int:cv_id>/template-selection/', views.CVTemplateSelectionDetailView.as_view(), name='cv-template-selection'),
]