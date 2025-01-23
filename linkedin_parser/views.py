from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
import logging
from .models import LinkedInProfile
from .services import LinkedInParserService
from .oauth import LinkedInOAuth
from cv_writer.models import CvWriter
from .serializers import (
    LinkedInProfileSerializer,
    LinkedInEducationSerializer,
    LinkedInExperienceSerializer,
    LinkedInSkillSerializer,
    LinkedInCertificationSerializer,
    LinkedInLanguageSerializer
)
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def linkedin_auth(request):
    """Start LinkedIn OAuth flow"""
    logger.info('Starting LinkedIn OAuth flow')
    
    try:
        oauth = LinkedInOAuth()
        
        # Get state and redirect_uri from query params
        state = request.GET.get('state')
        redirect_uri = request.GET.get('redirect_uri')
        
        # Store state in session
        if state:
            request.session['linkedin_oauth_state'] = state
            logger.debug('Stored OAuth state: %s', state)
            
        # Store redirect_uri in session for callback
        if redirect_uri:
            request.session['linkedin_oauth_redirect_uri'] = redirect_uri
            logger.debug('Stored OAuth redirect URI: %s', redirect_uri)
        
        # Get authorization URL
        auth_url = oauth.get_authorization_url(state=state, redirect_uri=redirect_uri)
        logger.info('Generated authorization URL')
        
        return Response({'authorization_url': auth_url})
    except Exception as e:
        logger.error('Error in LinkedIn OAuth flow: %s', str(e))
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def linkedin_callback(request):
    """Handle LinkedIn OAuth callback"""
    try:
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description')

        if error:
            logger.error('LinkedIn OAuth error: %s - %s', error, error_description)
            return Response({'error': error_description}, status=400)

        if not code:
            return Response({'error': 'No authorization code provided'}, status=400)

        # Verify state
        stored_state = request.session.get('linkedin_oauth_state')
        if not stored_state or stored_state != state:
            return Response({'error': 'Invalid state parameter'}, status=400)

        # Exchange code for access token
        oauth_service = LinkedInOAuth()
        tokens = oauth_service.get_access_token(code)
        
        if not tokens or 'access_token' not in tokens:
            return Response({'error': 'Failed to get access token'}, status=400)

        # Get or create user's LinkedIn profile
        parser_service = LinkedInParserService()
        profile, created = parser_service.update_or_create_profile(
            user=request.user,
            access_token=tokens['access_token'],
            refresh_token=tokens.get('refresh_token'),
            expires_at=tokens.get('expires_at')
        )

        # Clear OAuth session data
        request.session.pop('linkedin_oauth_state', None)

        return Response({
            'message': 'Successfully connected LinkedIn profile',
            'profile': {
                'id': profile.linkedin_id,
                'full_name': profile.full_name,
                'email': profile.email,
                'headline': profile.headline,
                'linkedin_url': profile.linkedin_url,
                'profile_picture_url': profile.profile_picture_url
            }
        })

    except Exception as e:
        logger.error('Error in OAuth callback: %s', str(e))
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get LinkedIn profile data"""
    try:
        profile = LinkedInProfile.objects.get(user=request.user)
        return Response({
            'id': profile.linkedin_id,
            'full_name': profile.full_name,
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'email': profile.email,
            'headline': profile.headline,
            'profile_picture_url': profile.profile_picture_url,
            'linkedin_url': profile.linkedin_url
        })
    except LinkedInProfile.DoesNotExist:
        return Response({'error': 'LinkedIn profile not connected'}, status=404)
    except Exception as e:
        logger.error('Error getting LinkedIn profile: %s', str(e))
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disconnect_profile(request):
    """Disconnect LinkedIn profile"""
    try:
        profile = LinkedInProfile.objects.get(user=request.user)
        profile.delete()
        return Response({'message': 'Successfully disconnected LinkedIn profile'})
    except LinkedInProfile.DoesNotExist:
        return Response({'error': 'LinkedIn profile not connected'}, status=404)
    except Exception as e:
        logger.error('Error disconnecting LinkedIn profile: %s', str(e))
        return Response({'error': str(e)}, status=500)

class LinkedInParserViewSet(viewsets.ModelViewSet):
    queryset = LinkedInProfile.objects.all()
    serializer_class = LinkedInProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get user's LinkedIn profile"""
        logger.info('Getting LinkedIn profile')
        
        try:
            profile = LinkedInProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except LinkedInProfile.DoesNotExist:
            return Response({'message': 'No LinkedIn profile connected'}, status=404)
        except Exception as e:
            logger.error('Error getting LinkedIn profile: %s', str(e))
            return Response({'message': str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def sync_profile(self, request, pk=None):
        """Sync LinkedIn profile data and create a CV"""
        logger.info('Syncing LinkedIn profile')
        
        profile = self.get_object()
        
        if not profile.access_token:
            logger.error('LinkedIn access token not found')
            return Response(
                {"error": "LinkedIn access token not found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            parser = LinkedInParserService(profile.access_token)
            parser.parse_and_save_profile(profile)
            
            logger.info('LinkedIn profile synced successfully')
            
            # Get the latest CV created during sync
            latest_cv = CvWriter.objects.filter(
                user=self.request.user
            ).order_by('-created_at').first()

            return Response({
                "message": "Profile sync completed successfully",
                "status": profile.sync_status,
                "cv_id": latest_cv.id if latest_cv else None
            })
        except Exception as e:
            logger.error('Failed to sync LinkedIn profile: %s', str(e))
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def education(self, request, pk=None):
        """Get education history"""
        logger.info('Getting education history')
        
        profile = self.get_object()
        education = profile.education.all()
        serializer = LinkedInEducationSerializer(education, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def experience(self, request, pk=None):
        """Get work experience"""
        logger.info('Getting work experience')
        
        profile = self.get_object()
        experience = profile.experience.all()
        serializer = LinkedInExperienceSerializer(experience, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def skills(self, request, pk=None):
        """Get skills"""
        logger.info('Getting skills')
        
        profile = self.get_object()
        skills = profile.skills.all()
        serializer = LinkedInSkillSerializer(skills, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def certifications(self, request, pk=None):
        """Get certifications"""
        logger.info('Getting certifications')
        
        profile = self.get_object()
        certifications = profile.certifications.all()
        serializer = LinkedInCertificationSerializer(certifications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def languages(self, request, pk=None):
        """Get languages"""
        logger.info('Getting languages')
        
        profile = self.get_object()
        languages = profile.languages.all()
        serializer = LinkedInLanguageSerializer(languages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def cv_list(self, request, pk=None):
        """Get list of CVs generated from this LinkedIn profile"""
        logger.info('Getting list of CVs')
        
        profile = self.get_object()
        cvs = CvWriter.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

        return Response({
            "cvs": [
                {
                    "id": cv.id,
                    "title": cv.title,
                    "created_at": cv.created_at,
                    "status": cv.status,
                    "url": f"/cv/{cv.slug}"
                }
                for cv in cvs
            ]
        })

class DisconnectLinkedInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Disconnect LinkedIn account from user's profile
        """
        logger.info('Attempting to disconnect LinkedIn')
        try:
            # Get the user's LinkedIn profile
            linkedin_profile = LinkedInProfile.objects.get(user=self.request.user)
            logger.info('Found LinkedIn profile')
            
            # Delete the LinkedIn profile
            linkedin_profile.delete()
            logger.info('Successfully deleted LinkedIn profile')
            
            return Response({
                'status': 'success',
                'message': 'LinkedIn account disconnected successfully'
            })
        except LinkedInProfile.DoesNotExist:
            logger.warning('No LinkedIn profile found')
            return Response({
                'status': 'error',
                'message': 'No LinkedIn account connected'
            }, status=404)
        except Exception as e:
            logger.error('Error disconnecting LinkedIn: %s', str(e))
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=500)
