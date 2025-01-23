from tokenize import Pointfloat
from django.shortcuts import render
from django.views.generic.edit import model_forms
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
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
)
from .serializers import (
    CvWriterSerializer,
    EducationSerializer,
    ExperienceSerializer,
    ProfessionalSummarySerializer,
    InterestSummarySerializer,
    SkillSerializer,
    LanguageSerializer,
    CertificationSerializer,
    ReferenceSerializer,
    SocialMediaSerializer,
)

"""
I created a BaseListCreateAPIView class that inherits from generics.ListCreateAPIView to handle repeated part of the logic. This make my code DRY, reusable and reduce redudancy
"""


class BaseListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return self.model.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BaseRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        return self.model.objects.filter(user=user)


class CvWriterListCreate(BaseListCreateAPIView):
    """Endpoints for listing and creating CVs for the authenticated user."""
    serializer_class = CvWriterSerializer
    queryset = CvWriter.objects.all()
    model = CvWriter

    def perform_create(self, serializer):
        # Check if user already has a CV
        try:
            existing_cv = CvWriter.objects.get(user=self.request.user)
            # Update existing CV
            for attr, value in serializer.validated_data.items():
                setattr(existing_cv, attr, value)
            existing_cv.save()
        except CvWriter.DoesNotExist:
            # Create new CV
            serializer.save(user=self.request.user)


class CvWriterDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = CvWriterSerializer
    model = CvWriter


class ProfessionalSummaryListCreate(BaseListCreateAPIView):
    serializer_class = ProfessionalSummarySerializer
    queryset = ProfessionalSummary.objects.all()
    model = ProfessionalSummary

class ProfessionalSummaryDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = ProfessionalSummarySerializer
    model = ProfessionalSummary

class InterestListCreate(BaseListCreateAPIView):
    serializer_class = InterestSummarySerializer
    queryset = Interest.objects.all()
    model = Interest


class InterestDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = InterestSummarySerializer
    model = Interest


class EducationListCreate(BaseListCreateAPIView):
    serializer_class = EducationSerializer
    queryset = Education.objects.all()
    model = Education


class EducationDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = EducationSerializer
    model = Education


class ExperienceListCreate(BaseListCreateAPIView):
    serializer_class = ExperienceSerializer
    queryset = Experience.objects.all()
    model = Experience


class ExperienceDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = ExperienceSerializer
    model = Experience


class CertificationListCreate(BaseListCreateAPIView):
    serializer_class = CertificationSerializer
    queryset = Certification.objects.all()
    model = Certification


class CertificationDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = CertificationSerializer
    model = Certification


class SkillListCreate(BaseListCreateAPIView):
    serializer_class = SkillSerializer
    queryset = Skill.objects.all()
    model = Skill


class SkillDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = SkillSerializer
    model = Skill


class LanguageListCreate(BaseListCreateAPIView):
    serializer_class = LanguageSerializer
    queryset = Language.objects.all()
    model = Language


class LanguageDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = LanguageSerializer
    model = Language


class ReferenceListCreate(BaseListCreateAPIView):
    serializer_class = ReferenceSerializer
    queryset = Reference.objects.all()
    model = Reference


class ReferenceDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = ReferenceSerializer
    model = Reference


class SocialMediaListCreate(BaseListCreateAPIView):
    serializer_class = SocialMediaSerializer
    queryset = SocialMedia.objects.all()
    model = SocialMedia


class SocialMediaDetailView(BaseRetrieveUpdateDestroyAPIView):
    serializer_class = SocialMediaSerializer
    model = SocialMedia


class CVListCreateView(ListCreateAPIView):
    queryset = CvWriter.objects.all()
    serializer_class = CvWriterSerializer

class CVRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = CvWriter.objects.all()
    serializer_class = CvWriterSerializer

class EducationListCreateView(ListCreateAPIView):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer

class EducationRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer

class ExperienceListCreateView(ListCreateAPIView):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer

class ExperienceRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer

class SkillListCreateView(ListCreateAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer

class SkillRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer

class CertificationListCreateView(ListCreateAPIView):
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer

class CertificationRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer


# Create your views here.
def cv_list(request):
    return render(request, "cv_list.html")


@api_view(['GET'])
@permission_classes([AllowAny])
def test_email(request):
    try:
        send_mail(
            'Test Email',
            'This is a test email from your Django application.',
            'noreply@myserviceplug.com',  # Must match DEFAULT_FROM_EMAIL
            ['creativemike21@gmail.com'],  # Replace with your email
            fail_silently=False,
        )
        return Response({'message': 'Test email sent successfully!'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)