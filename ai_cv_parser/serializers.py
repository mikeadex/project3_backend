from rest_framework import serializers
from .models import ParsedCV

class ParsedCVSerializer(serializers.ModelSerializer):
    """Serializer for the ParsedCV model"""
    
    username = serializers.SerializerMethodField()
    
    class Meta:
        model = ParsedCV
        fields = [
            'id', 'user', 'username', 'file_name', 'uploaded_at', 'processed_at',
            'raw_text', 'parsed_data', 'file_size', 'mime_type',
            'processing_time', 'status', 'error_message'
        ]
        read_only_fields = ['id', 'user', 'username', 'uploaded_at', 'processed_at', 'processing_time']
    
    def get_username(self, obj):
        return obj.user.username if obj.user else None 