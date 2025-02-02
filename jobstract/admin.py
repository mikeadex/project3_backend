from django.contrib import admin
from .models import Opportunity, Employer

# Register your models here.

@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ('employer_name', 'employer_website', 'is_nonprofit', 'charity_number')
    list_filter = ('is_nonprofit',)
    search_fields = ('employer_name', 'employer_website', 'charity_number')

@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('title', 'employer', 'location', 'mode', 'opportunity_type', 'time_commitment', 'experience_level', 'date_posted')
    list_filter = ('opportunity_type', 'mode', 'time_commitment', 'experience_level', 'employer__is_nonprofit')
    search_fields = ('title', 'description', 'location', 'employer__employer_name', 'skills_required')
    date_hierarchy = 'date_posted'
    raw_id_fields = ('employer',)
    readonly_fields = ('date_posted',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'employer', 'description', 'location', 'opportunity_type')
        }),
        ('Job Details', {
            'fields': ('mode', 'time_commitment', 'experience_level', 'salary_range', 'expenses_paid')
        }),
        ('Skills', {
            'fields': ('skills_required', 'skills_gained')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'date_posted')
        }),
        ('Links', {
            'fields': ('source', 'application_url')
        }),
    )
