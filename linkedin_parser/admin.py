from django.contrib import admin
from .models import (
    LinkedInProfile,
    LinkedInEducation,
    LinkedInExperience,
    LinkedInSkill,
    LinkedInCertification,
    LinkedInLanguage
)

# Register your models here.

@admin.register(LinkedInProfile)
class LinkedInProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'email', 'headline', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'first_name', 'last_name', 'email', 'headline')
    readonly_fields = ('linkedin_id', 'created_at', 'updated_at')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'linkedin_id', 'email')
        }),
        ('Profile Information', {
            'fields': ('first_name', 'last_name', 'headline', 'vanity_name', 'profile_picture_url')
        }),
        ('OAuth Data', {
            'fields': ('access_token', 'refresh_token', 'expires_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'

@admin.register(LinkedInEducation)
class LinkedInEducationAdmin(admin.ModelAdmin):
    list_display = ('profile', 'school_name', 'degree', 'field_of_study', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('school_name', 'degree', 'field_of_study')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LinkedInExperience)
class LinkedInExperienceAdmin(admin.ModelAdmin):
    list_display = ('profile', 'company_name', 'title', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('company_name', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LinkedInSkill)
class LinkedInSkillAdmin(admin.ModelAdmin):
    list_display = ('profile', 'name', 'proficiency_level')
    list_filter = ('proficiency_level',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LinkedInCertification)
class LinkedInCertificationAdmin(admin.ModelAdmin):
    list_display = ('profile', 'name', 'issuing_organization', 'issue_date', 'expiration_date')
    search_fields = ('name', 'issuing_organization')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LinkedInLanguage)
class LinkedInLanguageAdmin(admin.ModelAdmin):
    list_display = ('profile', 'name', 'proficiency')
    search_fields = ('name',)
    list_filter = ('proficiency',)
    readonly_fields = ('created_at', 'updated_at')
