from django.contrib import admin
from .models import (
    CvWriter,
    Education,
    Experience,
    Certification,
    Skill,
    Language,
    Reference,
    SocialMedia,
    ProfessionalSummary,
    Interest,
    CVImprovement
)

# Register your models here.
admin.site.register(CvWriter)
admin.site.register(Education)
admin.site.register(Experience)
admin.site.register(Certification)
admin.site.register(Skill)
admin.site.register(Language)
admin.site.register(Reference)
admin.site.register(SocialMedia)
admin.site.register(ProfessionalSummary)
admin.site.register(Interest)
admin.site.register(CVImprovement)
# Compare this snippet from cv_writer/models.py:
