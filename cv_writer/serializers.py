from pydoc import classname
from django.contrib.auth.models import User
from rest_framework import serializers
from cv_writer.models import (
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
        fields = [
            "id",
            "school_name",
            "degree",
            "field_of_study",
            "start_date",
            "end_date",
            "current",
            "user",
            "created_at",
        ]
        extra_kwargs = {"user": {"read_only": True}}


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = [
            "id",
            "company_name",
            "job_title",
            "job_description",
            "achievements",
            "start_date",
            "end_date",
            "employment_type",
            "current",
            "user",
            "created_at",
        ]
        extra_kwargs = {"user": {"read_only": True}}


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "user", "skill_name", "skill_level", "created_at"]
        extra_kwargs = {"user": {"read_only": True}}


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ["id", "user", "language_name", "language_level", "is_custom", "created_at"]
        extra_kwargs = {"user": {"read_only": True}}


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = [
            "id",
            "user",
            "certificate_name",
            "certificate_date",
            "certificate_link",
            "created_at",
        ]
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


