from . import views
from django.urls import path

urlpatterns = [
    path("", views.cv_list, name="cv_list"),
    path("writer/", views.CvWriterListCreate.as_view(), name="cv-writer"),
    path(
        "writer/<int:pk>/",
        views.CvWriterDetailView.as_view(),
        name="cv-writer-detail",
    ),
    path("education/", views.EducationListCreate.as_view(), name="education"),
    path(
        "education/<int:pk>/",
        views.EducationDetailView.as_view(),
        name="education-detail",
    ),
    path("experience/", views.ExperienceListCreate.as_view(), name="experience"),
    path(
        "experience/<int:pk>/",
        views.ExperienceDetailView.as_view(),
        name="experience-detail",
    ),
    path(
        "certification/",
        views.CertificationListCreate.as_view(),
        name="certification",
    ),
    path(
        "certification/<int:pk>/",
        views.CertificationDetailView.as_view(),
        name="certification-detail",
    ),
    path("skill/", views.SkillListCreate.as_view(), name="skill"),
    path("skill/<int:pk>/", views.SkillDetailView.as_view(), name="skill-detail"),
    path("language/", views.LanguageListCreate.as_view(), name="language"),
    path(
        "language/<int:pk>/",
        views.LanguageDetailView.as_view(),
        name="language-detail",
    ),
    path("reference/", views.ReferenceListCreate.as_view(), name="reference"),
    path(
        "reference/<int:pk>/",
        views.ReferenceDetailView.as_view(),
        name="reference-detail",
    ),
    path(
        "social-media/",
        views.SocialMediaListCreate.as_view(),
        name="social-media",
    ),
    path(
        "social-media/<int:pk>/",
        views.SocialMediaDetailView.as_view(),
        name="social-media-detail",
    ),
    path(
        "professional-summary/",
        views.ProfessionalSummaryListCreate.as_view(),
        name="professional-summary"
    ),
    path(
        "professional-summary/<int:pk>/",
        views.ProfessionalSummaryDetailView.as_view(),
        name="professional-summary-detail"
    ),
    path("interest/",
    views.InterestListCreate.as_view(),
    name="interest"
    ),
    path("interest/<int:pk>/",
    views.InterestDetailView.as_view(),
    name="interest-detail"
    ),

    # delete later
    path("test-email/", views.test_email, name="test_email"),
]
