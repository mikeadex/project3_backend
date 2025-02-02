from rest_framework import serializers
from .models import Opportunity, Employer, JobApplication, ApplicationEvent
from cv_writer.serializers import CvWriterSerializer

class EmployerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employer
        fields = '__all__'

class OpportunitySerializer(serializers.ModelSerializer):
    employer = EmployerSerializer(read_only=True)
    matching_score = serializers.FloatField(required=False)
    
    class Meta:
        model = Opportunity
        fields = '__all__'

class ApplicationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationEvent
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class JobApplicationSerializer(serializers.ModelSerializer):
    opportunity = OpportunitySerializer(read_only=True)
    opportunity_id = serializers.IntegerField(write_only=True)
    cv_used = CvWriterSerializer(read_only=True)
    cv_used_id = serializers.IntegerField(write_only=True, required=False)
    events = ApplicationEventSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = JobApplication
        fields = [
            'id', 'user', 'opportunity', 'opportunity_id', 
            'status', 'status_display', 'applied_date', 
            'cv_used', 'cv_used_id', 'cover_letter', 
            'notes', 'next_follow_up', 'events',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('user', 'applied_date', 'created_at', 'updated_at')

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)