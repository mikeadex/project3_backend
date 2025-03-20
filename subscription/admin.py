from django.contrib import admin
from .models import (
    SubscriptionPlan, UserSubscription, SubscriptionUsageLog,
    SubscriptionFeature, PlanFeature
)

# Register your models here.

@admin.register(SubscriptionFeature)
class SubscriptionFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'is_highlighted', 'display_order')
    list_filter = ('is_highlighted',)
    search_fields = ('name', 'key', 'description')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('display_order', 'name')

class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 1
    autocomplete_fields = ('feature',)

@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ('plan', 'feature', 'is_available', 'value_limit')
    list_filter = ('is_available', 'plan', 'feature')
    search_fields = ('plan__name', 'feature__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'interval', 'status', 'is_popular', 'created_at')
    list_filter = ('status', 'interval', 'is_popular')
    search_fields = ('name', 'description', 'short_description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [PlanFeatureInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'short_description', 'is_popular')
        }),
        ('Pricing', {
            'fields': ('price', 'interval', 'status')
        }),
        ('Limits', {
            'fields': ('max_cv_generations', 'max_job_applications', 'max_saved_jobs')
        }),
        ('Features', {
            'fields': ('has_cv_analytics', 'has_job_alerts', 'has_priority_support', 'has_ai_interview_prep')
        }),
        ('Stripe Information', {
            'fields': ('stripe_price_id', 'stripe_product_id'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'plan')
    search_fields = ('user__email', 'plan__name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'plan', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'created_at', 'updated_at', 'canceled_at')
        }),
        ('Usage', {
            'fields': ('cv_generations_used', 'job_applications_used', 'saved_jobs_count')
        }),
        ('Stripe Information', {
            'fields': ('stripe_subscription_id', 'stripe_customer_id'),
            'classes': ('collapse',)
        })
    )

@admin.register(SubscriptionUsageLog)
class SubscriptionUsageLogAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'action', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('subscription__user__email', 'action')
    readonly_fields = ('timestamp',)