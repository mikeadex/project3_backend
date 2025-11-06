from rest_framework import serializers
from .models import ParsedCV


class ParsedCVSerializer(serializers.ModelSerializer):
    """Serializer for the ParsedCV model"""

    username = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = ParsedCV
        fields = [
            "id",
            "user",
            "username",
            "file_name",
            "uploaded_at",
            "processed_at",
            "raw_text",
            "parsed_data",
            "analysis_data",
            "file_size",
            "mime_type",
            "processing_time",
            "status",
            "error_message",
            "template",
            "version_number",
            "original_parsed_cv",
            "quality_score",
            "is_primary",
        ]
        read_only_fields = [
            "id",
            "user",
            "username",
            "uploaded_at",
            "processed_at",
            "processing_time",
        ]

    def get_username(self, obj):
        return obj.user.username if obj.user else None

    def get_file_name(self, obj):
        # Return file_name if present, else fallback to empty string
        return getattr(obj, "file_name", "") or ""
