from django.contrib import admin
from .models import ParsedCV

@admin.register(ParsedCV)
class ParsedCVAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'file_name', 'status', 'uploaded_at', 'processed_at', 'processing_time')
    list_filter = ('status', 'uploaded_at')
    search_fields = ('file_name', 'user__username', 'user__email')
    readonly_fields = ('uploaded_at', 'processed_at', 'processing_time')
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'file_name', 'status', 'uploaded_at', 'processed_at')
        }),
        ('File Details', {
            'fields': ('file_size', 'mime_type', 'processing_time')
        }),
        ('Content', {
            'fields': ('raw_text',),
            'classes': ('collapse',)
        }),
        ('Parsed Data', {
            'fields': ('parsed_data',),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
