from rest_framework import serializers
from django.contrib.auth.models import User
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
)


class CvWriterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CvWriter
        fields = [
            "id",
            "first_name",
            "last_name",
            "address",
            "city",
            "country",
            "contact_number",
            "additional_information",
            "user",
            "created_at",
        ]
        extra_kwargs = {"user": {"read_only": True}}

class ProfessionalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalSummary
        fields = [
            "id",
            "summary",
            "user",
            "created_at"
        ]
        extra_kwargs = {"user": {"read_only": True}}


class InterestSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = [
            "id",
            "name",
            "user",
            "created_at"
        ]
        extra_kwargs = {"user": {"read_only": True}}

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = '__all__'

class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = '__all__'

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = '__all__'

class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = '__all__'

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ["id", "user", "language_name", "language_level", "is_custom", "created_at"]
        extra_kwargs = {"user": {"read_only": True}}


class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = [
            "id",
            "user",
            "name",
            "title",
            "company",
            "email",
            "phone",
            "reference_type",
            "created_at",
        ]
        extra_kwargs = {"user": {"read_only": True}}


class SocialMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMedia
        fields = [
            "id",
            "user",
            "platform",
            "url",
            "created_at",
        ]
        extra_kwargs = {"user": {"read_only": True}}


class CVSerializer(serializers.ModelSerializer):
    education = EducationSerializer(many=True, read_only=True)
    experience = ExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)

    class Meta:
        model = CvWriter
        fields = '__all__'
        extra_kwargs = {"user": {"read_only": True}}
