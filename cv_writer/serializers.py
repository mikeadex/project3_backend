from rest_framework import serializers
from .models import (
    CvWriter,
    Education,
    Experience,
    ProfessionalSummary,
    Interest,
    Skill,
    Language,
    Certification,
    Reference,
    SocialMedia,
    CVImprovement,
)

class CvWriterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CvWriter
        fields = [
            'id', 'first_name', 'last_name', 'address', 'city', 'country',
            'contact_number', 'additional_information', 'title', 'description',
            'status', 'visibility', 'created_at', 'updated_at'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add user email if available
        if instance.user and instance.user.email:
            data['user_email'] = instance.user.email
        return data

class ProfessionalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalSummary
        fields = ['id', 'summary', 'created_at', 'updated_at']

class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = [
            'id', 'company_name', 'job_title', 'job_description',
            'achievements', 'start_date', 'end_date', 'employment_type',
            'current', 'created_at', 'updated_at'
        ]

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = [
            'id', 'school_name', 'degree', 'field_of_study',
            'start_date', 'end_date', 'current', 'created_at', 'updated_at'
        ]

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'skill_name', 'skill_level', 'created_at', 'updated_at']

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'name': instance.skill_name,
            'proficiency': instance.skill_level,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at
        }

class LanguageSerializer(serializers.ModelSerializer):
    language = serializers.CharField(source='language_name')
    proficiency = serializers.CharField(source='language_level')

    class Meta:
        model = Language
        fields = ['id', 'language', 'proficiency', 'is_custom', 'created_at', 'updated_at']

class CertificationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='certificate_name')
    date_obtained = serializers.DateField(source='certificate_date')
    issuing_organization = serializers.URLField(source='certificate_link')

    class Meta:
        model = Certification
        fields = ['id', 'name', 'date_obtained', 'issuing_organization', 'created_at', 'updated_at']

class InterestSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ['id', 'name', 'created_at', 'updated_at']

class ReferenceSerializer(serializers.ModelSerializer):
    position = serializers.CharField(source='title')

    class Meta:
        model = Reference
        fields = [
            'id', 'name', 'position', 'company', 'email', 'phone',
            'reference_type', 'created_at', 'updated_at'
        ]

class SocialMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMedia
        fields = ['id', 'platform', 'url', 'created_at', 'updated_at']

class CVImprovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVImprovement
        fields = [
            'id', 'section', 'original_content', 'improved_content',
            'improvement_type', 'tokens_used', 'status', 'error_message',
            'created_at'
        ]

class CVVersionSerializer(serializers.ModelSerializer):
    variants = serializers.SerializerMethodField()

    class Meta:
        model = CvWriter
        fields = [
            'id', 
            'user', 
            'title', 
            'is_primary', 
            'created_at', 
            'updated_at', 
            'parent_version', 
            'version_name', 
            'version_purpose',
            'variants'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_variants(self, obj):
        # Get all variant versions of this CV
        variants = obj.variants.all()
        return CVVersionSerializer(variants, many=True).data

    def create(self, validated_data):
        # Ensure the CV is created for the current user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent changing the user
        validated_data.pop('user', None)
        return super().update(instance, validated_data)
