from rest_framework import serializers
from .models import (
    LinkedInProfile,
    LinkedInEducation,
    LinkedInExperience,
    LinkedInSkill,
    LinkedInCertification,
    LinkedInLanguage
)
from .services import LinkedInParserService

class LinkedInEducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedInEducation
        exclude = ('profile', 'created_at', 'updated_at')


class LinkedInExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedInExperience
        exclude = ('profile', 'created_at', 'updated_at')


class LinkedInSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedInSkill
        exclude = ('profile', 'created_at', 'updated_at')


class LinkedInCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedInCertification
        exclude = ('profile', 'created_at', 'updated_at')


class LinkedInLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedInLanguage
        exclude = ('profile', 'created_at', 'updated_at')


class LinkedInProfileSerializer(serializers.ModelSerializer):
    education = LinkedInEducationSerializer(many=True, read_only=True)
    experience = LinkedInExperienceSerializer(many=True, read_only=True)
    skills = LinkedInSkillSerializer(many=True, read_only=True)
    certifications = LinkedInCertificationSerializer(many=True, read_only=True)
    languages = LinkedInLanguageSerializer(many=True, read_only=True)

    class Meta:
        model = LinkedInProfile
        fields = [
            'id',
            'user',
            'profile_url',
            'profile_picture_url',
            'name',
            'email',
            'headline',
            'sync_status',
            'last_synced',
            'error_message',
            'created_at',
            'updated_at',
            'education',
            'experience',
            'skills',
            'certifications',
            'languages'
        ]
        read_only_fields = [
            'user',
            'sync_status',
            'last_synced',
            'error_message',
            'created_at',
            'updated_at'
        ]

    def get_profile_picture(self, obj):
        """Get the profile picture URL from the API response"""
        if not obj.access_token:
            return ''
            
        try:
            # Get profile data from the API
            parser = LinkedInParserService(obj.access_token)
            profile_data = parser.get_profile_data()
            return profile_data.get('picture', '')
        except Exception as e:
            print(f"Error getting profile picture: {str(e)}")
            return ''
