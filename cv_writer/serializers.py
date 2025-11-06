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
    CVTemplate,
    CVTemplateSelection,
)
from django.utils import timezone


class CVTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVTemplate
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "preview_image",
            "is_active",
            "order",
            "category",
            "has_color_options",
            "has_font_options",
            "has_layout_options",
        ]


class CvWriterSerializer(serializers.ModelSerializer):
    template_info = CVTemplateSerializer(source="template", read_only=True)

    # Nested serializers for related data (read-only)
    professional_summary = serializers.SerializerMethodField()
    experiences = serializers.SerializerMethodField()
    education = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    certifications = serializers.SerializerMethodField()
    interests = serializers.SerializerMethodField()
    references = serializers.SerializerMethodField()
    social_media = serializers.SerializerMethodField()
    original_parsed_cv_id = serializers.IntegerField(
        source="original_parsed_cv.id", read_only=True, allow_null=True
    )

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
            "title",
            "description",
            "status",
            "visibility",
            "created_at",
            "updated_at",
            "version_name",
            "version_purpose",
            "is_primary",
            "template",
            "template_info",
            "professional_summary",
            "experiences",
            "education",
            "skills",
            "languages",
            "certifications",
            "interests",
            "references",
            "social_media",
            "original_parsed_cv_id",
        ]

    def get_professional_summary(self, obj):
        try:
            # Ensure obj is a model instance with an ID
            if not hasattr(obj, 'id') or obj.id is None:
                return ""
                
            # Use .first() to handle multiple summaries gracefully
            # Get the most recent one by created_at
            summary = (
                ProfessionalSummary.objects.filter(cv=obj)
                .order_by("-created_at")
                .first()
            )
            return summary.summary if summary else ""
        except (ProfessionalSummary.DoesNotExist, AttributeError, TypeError):
            return ""

    def get_experiences(self, obj):
        try:
            # Ensure obj is a model instance with an ID
            if not hasattr(obj, 'id') or obj.id is None:
                return []
                
            experiences = Experience.objects.filter(cv=obj).order_by("-start_date")
            return ExperienceSerializer(experiences, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_education(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            education = Education.objects.filter(cv=obj).order_by("-start_date")
            return EducationSerializer(education, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_skills(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            # Filter skills by CV to get only this CV's skills
            skills = Skill.objects.filter(cv=obj)
            return SkillSerializer(skills, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_languages(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            # Filter languages by CV to get only this CV's languages
            languages = Language.objects.filter(cv=obj)
            return LanguageSerializer(languages, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_certifications(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            certifications = Certification.objects.filter(cv=obj).order_by(
                "-certificate_date"
            )
            return CertificationSerializer(certifications, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_interests(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            # Filter interests by CV to get only this CV's interests
            interests = Interest.objects.filter(cv=obj)
            return InterestSummarySerializer(interests, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_references(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            references = Reference.objects.filter(cv=obj)
            return ReferenceSerializer(references, many=True).data
        except (AttributeError, TypeError):
            return []

    def get_social_media(self, obj):
        try:
            if not hasattr(obj, 'id') or obj.id is None:
                return []
            social_media = SocialMedia.objects.filter(cv=obj)
            return SocialMediaSerializer(social_media, many=True).data
        except (AttributeError, TypeError):
            return []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add user email if available
        if instance.user and instance.user.email:
            data["user_email"] = instance.user.email
        return data


class ProfessionalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalSummary
        fields = ["id", "user", "cv", "summary", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = [
            "id",
            "user",
            "cv",
            "company_name",
            "job_title",
            "job_description",
            "achievements",
            "start_date",
            "end_date",
            "employment_type",
            "current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
            "company_name": {"allow_blank": True, "required": False},
            "job_title": {"allow_blank": True, "required": False},
            "job_description": {"allow_blank": True, "required": False},
        }


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = [
            "id",
            "user",
            "cv",
            "school_name",
            "degree",
            "field_of_study",
            "start_date",
            "end_date",
            "current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = [
            "id",
            "user",
            "cv",
            "skill_name",
            "skill_level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "name": instance.skill_name,
            "level": instance.skill_level,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = [
            "id",
            "user",
            "cv",
            "language",
            "proficiency",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }


class CertificationSerializer(serializers.ModelSerializer):
    # Map frontend field names to model field names
    issuing_organization = serializers.CharField(
        source="certificate_link", required=False, allow_blank=True, allow_null=True
    )
    issue_date = serializers.DateField(
        source="certificate_date", required=False, allow_null=True
    )

    def to_internal_value(self, data):
        # Convert empty strings to None for date fields
        if "issue_date" in data and data["issue_date"] == "":
            data["issue_date"] = None
        return super().to_internal_value(data)

    class Meta:
        model = Certification
        fields = [
            "id",
            "user",
            "cv",
            "certificate_name",
            "issuing_organization",
            "issue_date",
            "certificate_date",
            "certificate_link",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
            "certificate_name": {"required": False, "allow_blank": True},
            "certificate_date": {"required": False, "allow_null": True},
            "certificate_link": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            },
        }


class InterestSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ["id", "user", "cv", "name", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }


class ReferenceSerializer(serializers.ModelSerializer):
    position = serializers.CharField(source="title")

    class Meta:
        model = Reference
        fields = [
            "id",
            "user",
            "cv",
            "name",
            "position",
            "company",
            "email",
            "phone",
            "reference_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }


class SocialMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMedia
        fields = ["id", "user", "cv", "platform", "url", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]
        extra_kwargs = {
            "cv": {"required": False, "allow_null": True},
        }


class CVImprovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVImprovement
        fields = [
            "id",
            "section",
            "original_content",
            "improved_content",
            "improvement_type",
            "tokens_used",
            "status",
            "error_message",
            "created_at",
        ]


class CVTemplateSelectionSerializer(serializers.ModelSerializer):
    template_details = CVTemplateSerializer(source="template", read_only=True)

    class Meta:
        model = CVTemplateSelection
        fields = [
            "id",
            "template",
            "template_details",
            "color_scheme",
            "font_choice",
            "layout_option",
            "custom_css",
            "custom_settings",
        ]


class CVVersionSerializer(serializers.ModelSerializer):
    variants = serializers.SerializerMethodField()
    is_primary = serializers.BooleanField(required=False)
    version_name = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=100
    )
    version_purpose = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=200
    )

    class Meta:
        model = CvWriter
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "contact_number",
            "address",
            "city",
            "country",
            "additional_information",
            "title",
            "is_primary",
            "created_at",
            "updated_at",
            "parent_version",
            "version_name",
            "version_purpose",
            "variants",
        ]
        read_only_fields = [
            "user",
            "created_at",
            "updated_at",
        ]

    def get_variants(self, obj):
        # Get all variants of this CV version
        variants = CvWriter.objects.filter(parent_version=obj)
        return [
            {
                "id": variant.id,
                "title": variant.title,
                "version_name": variant.version_name,
                "version_purpose": variant.version_purpose,
                "created_at": variant.created_at,
                "is_primary": variant.is_primary,
            }
            for variant in variants
        ]

    def validate(self, attrs):
        # Ensure only one primary version exists per user
        user = self.context["request"].user
        is_primary = attrs.get("is_primary", False)

        # If setting as primary, unset primary for other versions
        if is_primary:
            CvWriter.objects.filter(user=user, is_primary=True).update(is_primary=False)

        # Validate version name length
        if "version_name" in attrs:
            if len(attrs["version_name"]) > 100:
                raise serializers.ValidationError(
                    {"version_name": "Version name cannot exceed 100 characters."}
                )

        # Validate version purpose length
        if "version_purpose" in attrs:
            if len(attrs["version_purpose"]) > 200:
                raise serializers.ValidationError(
                    {"version_purpose": "Version purpose cannot exceed 200 characters."}
                )

        # Validate visibility
        if "visibility" in attrs:
            valid_visibilities = ["private", "public", "shared"]
            if attrs["visibility"] not in valid_visibilities:
                raise serializers.ValidationError(
                    {"visibility": f"Visibility must be one of {valid_visibilities}"}
                )

        return attrs

    def update(self, instance, validated_data):
        """
        Custom update method to handle version details editing
        """
        # Prevent editing primary version's name or purpose
        if instance.is_primary and (
            "version_name" in validated_data or "version_purpose" in validated_data
        ):
            raise serializers.ValidationError(
                {"detail": "Cannot modify the primary version's name or purpose."}
            )

        # Allow updating version name, purpose, and visibility
        allowed_fields = ["version_name", "version_purpose", "visibility"]

        # Sanitize input data
        for field in allowed_fields:
            if field in validated_data:
                # Trim whitespace
                value = (
                    validated_data[field].strip()
                    if isinstance(validated_data[field], str)
                    else validated_data[field]
                )

                # Skip if value is empty string
                if value:
                    setattr(instance, field, value)

        # Validate version name uniqueness
        if "version_name" in validated_data:
            existing_versions = CvWriter.objects.filter(
                user=instance.user, version_name=validated_data["version_name"]
            ).exclude(pk=instance.pk)

            if existing_versions.exists():
                raise serializers.ValidationError(
                    {"version_name": "A version with this name already exists."}
                )

        # Validate visibility
        if "visibility" in validated_data:
            valid_visibilities = ["private", "public", "shared"]
            if validated_data["visibility"] not in valid_visibilities:
                raise serializers.ValidationError(
                    {"visibility": f"Visibility must be one of {valid_visibilities}"}
                )

        # Update timestamp
        instance.updated_at = timezone.now()
        instance.save()

        return instance

    def create(self, validated_data):
        # Ensure user is set
        validated_data["user"] = self.context["request"].user

        # Set default version name if not provided
        if "version_name" not in validated_data:
            existing_versions = CvWriter.objects.filter(
                user=validated_data["user"]
            ).count()
            validated_data["version_name"] = f"Version {existing_versions + 1}"

        # Set is_primary if not specified
        if "is_primary" not in validated_data:
            existing_versions = CvWriter.objects.filter(
                user=validated_data["user"]
            ).count()
            validated_data["is_primary"] = existing_versions == 0

        # Copy data from the primary version if this is a new version
        primary_version = CvWriter.objects.filter(
            user=validated_data["user"], is_primary=True
        ).first()
        if primary_version:
            validated_data.setdefault("first_name", primary_version.first_name)
            validated_data.setdefault("last_name", primary_version.last_name)
            validated_data.setdefault("address", primary_version.address)
            validated_data.setdefault("city", primary_version.city)
            validated_data.setdefault("country", primary_version.country)
            validated_data.setdefault("contact_number", primary_version.contact_number)
            validated_data.setdefault(
                "additional_information", primary_version.additional_information
            )

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent changing user
        validated_data.pop("user", None)

        # If updating primary status, ensure only one primary version
        if "is_primary" in validated_data and validated_data["is_primary"]:
            CvWriter.objects.filter(user=instance.user, is_primary=True).exclude(
                pk=instance.pk
            ).update(is_primary=False)

        return super().update(instance, validated_data)
