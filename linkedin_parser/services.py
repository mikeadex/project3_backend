import os
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.text import slugify
from .models import (
    LinkedInProfile,
    LinkedInEducation,
    LinkedInExperience,
    LinkedInSkill,
    LinkedInCertification,
    LinkedInLanguage
)
from cv_writer.models import (
    CvWriter,
    Education,
    Experience,
    Skill,
    Language,
    Certification,
    ProfessionalSummary
)
from urllib.parse import urlencode
import logging
from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)

class LinkedInOAuth:
    def __init__(self):
        self.client_id = settings.LINKEDIN_CLIENT_ID
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET
        self.scope = 'r_liteprofile r_emailaddress w_member_social'
        
    def get_authorization_url(self, state=None, redirect_uri=None):
        """Get LinkedIn authorization URL
        
        Args:
            state (str, optional): State parameter for security. Defaults to None.
            redirect_uri (str, optional): Callback URL. Defaults to None.
            
        Returns:
            str: Authorization URL
        """
        if not redirect_uri:
            redirect_uri = settings.LINKEDIN_REDIRECT_URI
            
        if not state:
            state = get_random_string(32)
            
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'scope': self.scope
        }
        
        logger.debug('LinkedIn OAuth params: %s', params)
        return f'https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}'
        
    def get_access_token(self, code, redirect_uri=None):
        """Exchange authorization code for access token
        
        Args:
            code (str): Authorization code from callback
            redirect_uri (str, optional): Callback URL. Defaults to None.
            
        Returns:
            dict: Access token response
        """
        if not redirect_uri:
            redirect_uri = settings.LINKEDIN_REDIRECT_URI
            
        url = 'https://www.linkedin.com/oauth/v2/accessToken'
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri
        }
        
        logger.debug('LinkedIn token request data: %s', {k: v for k, v in data.items() if k != 'client_secret'})
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()


class LinkedInParserService:
    """Service for parsing LinkedIn profiles using LinkedIn's API"""

    BASE_URL = "https://api.linkedin.com/v2"
    USER_INFO_URL = "https://api.linkedin.com/v2/userinfo"  # OIDC userinfo endpoint

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request to LinkedIn API"""
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_profile_data(self) -> Dict[str, Any]:
        """Get basic profile information using OIDC userinfo endpoint"""
        try:
            # First get basic info from userinfo endpoint
            response = requests.get(self.USER_INFO_URL, headers=self.headers)
            response.raise_for_status()
            basic_data = response.json()
            print("Basic data from userinfo:", json.dumps(basic_data, indent=2))

            try:
                # Try to get additional profile data using lite profile endpoint
                profile_response = requests.get(
                    f"{self.BASE_URL}/v2/me",
                    headers=self.headers,
                    params={
                        'projection': '(id,firstName,lastName,profilePicture,vanityName,publicProfileUrl)'
                    }
                )
                profile_response.raise_for_status()
                profile_data = profile_response.json()
                print("Profile data from lite profile:", json.dumps(profile_data, indent=2))
            except Exception as e:
                print(f"Error getting additional profile data: {str(e)}")
                profile_data = {}

            # Get profile URL from member ID if available
            member_id = basic_data.get('sub')
            profile_url = None

            # Try to get profile URL from various sources in order of preference
            if profile_data:
                # 1. Try to get from public profile URL
                profile_url = profile_data.get('publicProfileUrl')
                if not profile_url:
                    # 2. Try to get from vanity name
                    vanity_name = profile_data.get('vanityName')
                    if vanity_name:
                        profile_url = f"https://www.linkedin.com/in/{vanity_name}"

            # 3. Fall back to member ID if nothing else works
            if not profile_url and member_id:
                profile_url = f"https://www.linkedin.com/in/michael-adeleye-{member_id}"

            # Get name from profile data if available, otherwise use basic data
            if profile_data and 'firstName' in profile_data and 'lastName' in profile_data:
                name = f"{profile_data['firstName']} {profile_data['lastName']}".strip()
            else:
                name = basic_data.get('name', '')

            # Merge the data, prioritizing the basic_data since it's more reliable
            return {
                'name': name,
                'email': basic_data.get('email', ''),
                'picture': basic_data.get('picture', ''),  # Use picture from userinfo
                'profile_url': profile_url,
                'headline': profile_data.get('headline', ''),
                'positions': profile_data.get('positions', {'elements': []}),
                'educations': profile_data.get('educations', {'elements': []}),
                'skills': profile_data.get('skills', {'elements': []}),
                'certifications': profile_data.get('certifications', {'elements': []}),
                'languages': profile_data.get('languages', {'elements': []})
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching LinkedIn profile data: {str(e)}")
            return {
                'name': '',
                'email': '',
                'picture': '',
                'profile_url': None,
                'headline': '',
                'positions': {'elements': []},
                'educations': {'elements': []},
                'skills': {'elements': []},
                'certifications': {'elements': []},
                'languages': {'elements': []}
            }

    def parse_and_save_profile(self, linkedin_profile: LinkedInProfile) -> None:
        """Parse LinkedIn profile data and save to database"""
        try:
            # Update sync status
            linkedin_profile.sync_status = 'in_progress'
            linkedin_profile.save()

            try:
                # Get profile data using OIDC userinfo endpoint
                profile_data = self.get_profile_data()
                print("Profile data received:", json.dumps(profile_data, indent=2))
            except Exception as e:
                print(f"Error getting profile data: {str(e)}")
                linkedin_profile.sync_status = 'failed'
                linkedin_profile.error_message = f"Failed to fetch profile data: {str(e)}"
                linkedin_profile.save()
                raise

            # Update profile fields
            linkedin_profile.name = profile_data.get('name', '')
            linkedin_profile.email = profile_data.get('email', '')
            linkedin_profile.profile_url = profile_data.get('profile_url', '')
            linkedin_profile.profile_picture_url = profile_data.get('picture', '')
            linkedin_profile.headline = profile_data.get('headline', '')
            linkedin_profile.save()

            try:
                # Create or update CV Writer instance
                cv_writer = self.create_cv_writer(linkedin_profile, profile_data)
            except Exception as e:
                print(f"Error creating CV Writer: {str(e)}")
                linkedin_profile.sync_status = 'failed'
                linkedin_profile.error_message = f"Failed to create CV Writer: {str(e)}"
                linkedin_profile.save()
                raise

            try:
                # Parse and save education
                self._parse_education(linkedin_profile, profile_data.get('educations', {}).get('elements', []))
                self._transfer_education_to_cv(linkedin_profile, cv_writer)

                # Parse and save experience
                self._parse_experience(linkedin_profile, profile_data.get('positions', {}).get('elements', []))
                self._transfer_experience_to_cv(linkedin_profile, cv_writer)

                # Parse and save skills
                self._parse_skills(linkedin_profile, profile_data.get('skills', {}).get('elements', []))
                self._transfer_skills_to_cv(linkedin_profile, cv_writer)

                # Parse and save certifications
                self._parse_certifications(linkedin_profile, profile_data.get('certifications', {}).get('elements', []))
                self._transfer_certifications_to_cv(linkedin_profile, cv_writer)

                # Parse and save languages
                self._parse_languages(linkedin_profile, profile_data.get('languages', {}).get('elements', []))

            except Exception as e:
                print(f"Error parsing profile sections: {str(e)}")
                linkedin_profile.sync_status = 'failed'
                linkedin_profile.error_message = f"Failed to parse profile sections: {str(e)}"
                linkedin_profile.save()
                raise

            # Update sync status
            linkedin_profile.sync_status = 'completed'
            linkedin_profile.last_synced = datetime.now()
            linkedin_profile.save()

        except Exception as e:
            print(f"Profile sync failed: {str(e)}")
            linkedin_profile.sync_status = 'failed'
            linkedin_profile.error_message = str(e)
            linkedin_profile.save()
            raise

    def create_cv_writer(self, linkedin_profile: LinkedInProfile, profile_data: Dict[str, Any]) -> CvWriter:
        """Create a CV Writer instance from LinkedIn profile data"""
        try:
            # Split name into first and last name
            name_parts = profile_data.get('name', '').split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Create a title from headline or name
            title = profile_data.get('headline', f"{first_name} {last_name}'s CV")

            # Create a description from summary or headline
            description = profile_data.get('summary', profile_data.get('headline', ''))

            # Create CV Writer with all available fields
            cv_writer, created = CvWriter.objects.get_or_create(
                user=linkedin_profile.user,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'address': '',  # Required field, but we don't have it from LinkedIn
                    'city': '',     # Required field, but we don't have it from LinkedIn
                    'country': '',  # Required field, but we don't have it from LinkedIn
                    'contact_number': '',  # Required field, but we don't have it from LinkedIn
                    'additional_information': profile_data.get('headline', ''),
                    'title': title,
                    'description': description,
                    'status': 'draft',
                    'visibility': 'private',
                }
            )

            if not created:
                # Update only if the CV Writer already exists
                cv_writer.first_name = first_name
                cv_writer.last_name = last_name
                cv_writer.additional_information = profile_data.get('headline', '')
                cv_writer.title = title
                cv_writer.description = description
                cv_writer.save()

            return cv_writer
        except Exception as e:
            print(f"Error creating CV Writer: {str(e)}")
            raise

    def _transfer_education_to_cv(self, linkedin_profile: LinkedInProfile, cv_writer: CvWriter) -> None:
        """Transfer LinkedIn education to CV Writer"""
        for edu in linkedin_profile.education.all():
            Education.objects.create(
                cv_writer=cv_writer,
                institution=edu.school_name,
                degree=edu.degree,
                field_of_study=edu.field_of_study,
                start_date=edu.start_date,
                end_date=edu.end_date,
                description=edu.description
            )

    def _transfer_experience_to_cv(self, linkedin_profile: LinkedInProfile, cv_writer: CvWriter) -> None:
        """Transfer LinkedIn experience to CV Writer"""
        for exp in linkedin_profile.experience.all():
            Experience.objects.create(
                cv_writer=cv_writer,
                company=exp.company_name,
                position=exp.title,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                description=exp.description
            )

    def _transfer_skills_to_cv(self, linkedin_profile: LinkedInProfile, cv_writer: CvWriter) -> None:
        """Transfer LinkedIn skills to CV Writer"""
        for skill in linkedin_profile.skills.all():
            Skill.objects.create(
                cv_writer=cv_writer,
                name=skill.name,
                level='Expert' if skill.endorsements > 10 else 'Intermediate'
            )

    def _transfer_certifications_to_cv(self, linkedin_profile: LinkedInProfile, cv_writer: CvWriter) -> None:
        """Transfer LinkedIn certifications to CV Writer"""
        for cert in linkedin_profile.certifications.all():
            Certification.objects.create(
                cv_writer=cv_writer,
                name=cert.name,
                issuer=cert.issuing_organization,
                date_obtained=cert.issue_date,
                expiry_date=cert.expiration_date,
                credential_id=cert.credential_id,
                credential_url=cert.credential_url
            )

    def _parse_education(self, profile: LinkedInProfile, education_data: list) -> None:
        """Parse and save education data"""
        # Clear existing education data
        profile.education.all().delete()

        for edu in education_data:
            LinkedInEducation.objects.create(
                profile=profile,
                school_name=edu.get('schoolName', ''),
                degree=edu.get('degreeName', ''),
                field_of_study=edu.get('fieldOfStudy', ''),
                start_date=self._parse_date(edu.get('startDate')),
                end_date=self._parse_date(edu.get('endDate')),
                description=edu.get('description', ''),
                linkedin_id=edu.get('id')
            )

    def _parse_experience(self, profile: LinkedInProfile, experience_data: list) -> None:
        """Parse and save experience data"""
        # Clear existing experience data
        profile.experience.all().delete()

        for exp in experience_data:
            LinkedInExperience.objects.create(
                profile=profile,
                company_name=exp.get('companyName', ''),
                title=exp.get('title', ''),
                location=exp.get('location', ''),
                start_date=self._parse_date(exp.get('startDate')),
                end_date=self._parse_date(exp.get('endDate')),
                description=exp.get('description', ''),
                employment_type=exp.get('employmentType', ''),
                linkedin_id=exp.get('id')
            )

    def _parse_skills(self, profile: LinkedInProfile, skills_data: list) -> None:
        """Parse and save skills data"""
        # Clear existing skills data
        profile.skills.all().delete()

        for skill in skills_data:
            LinkedInSkill.objects.create(
                profile=profile,
                name=skill.get('name', ''),
                endorsements=skill.get('endorsementCount', 0),
                linkedin_id=skill.get('id')
            )

    def _parse_certifications(self, profile: LinkedInProfile, certifications_data: list) -> None:
        """Parse and save certifications data"""
        # Clear existing certifications data
        profile.certifications.all().delete()

        for cert in certifications_data:
            LinkedInCertification.objects.create(
                profile=profile,
                name=cert.get('name', ''),
                issuing_organization=cert.get('authority', ''),
                issue_date=self._parse_date(cert.get('startDate')),
                expiration_date=self._parse_date(cert.get('endDate')),
                credential_id=cert.get('licenseNumber', ''),
                credential_url=cert.get('url', ''),
                linkedin_id=cert.get('id')
            )

    def _parse_languages(self, profile: LinkedInProfile, languages_data: list) -> None:
        """Parse and save languages data"""
        # Clear existing languages data
        profile.languages.all().delete()

        for lang in languages_data:
            LinkedInLanguage.objects.create(
                profile=profile,
                name=lang.get('name', ''),
                proficiency=self._map_proficiency(lang.get('proficiency', {}).get('level', '')),
                linkedin_id=lang.get('id')
            )

    def _parse_date(self, date_dict: Optional[Dict]) -> Optional[datetime]:
        """Parse LinkedIn date format"""
        if not date_dict:
            return None

        try:
            year = date_dict.get('year')
            month = date_dict.get('month', 1)
            day = date_dict.get('day', 1)
            return datetime(year=year, month=month, day=day).date()
        except (TypeError, ValueError):
            return None

    def _map_proficiency(self, proficiency: str) -> str:
        """Map LinkedIn language proficiency to our format"""
        proficiency_map = {
            'ELEMENTARY': 'elementary',
            'LIMITED_WORKING': 'limited_working',
            'PROFESSIONAL_WORKING': 'professional_working',
            'FULL_PROFESSIONAL': 'full_professional',
            'NATIVE_OR_BILINGUAL': 'native_bilingual'
        }
        return proficiency_map.get(proficiency.upper(), None)

    def get_profile_data_v2(self, access_token):
        """Get user's LinkedIn profile data using API v2
        
        Args:
            access_token (str): LinkedIn OAuth access token
            
        Returns:
            dict: Profile data including name, email, headline, etc.
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'cache-control': 'no-cache',
            'X-Restli-Protocol-Version': '2.0.0'
        }

        # Get basic profile
        profile_url = 'https://api.linkedin.com/v2/me'
        profile_response = requests.get(profile_url, headers=headers)
        profile_response.raise_for_status()
        profile_data = profile_response.json()

        # Get email address
        email_url = 'https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))'
        email_response = requests.get(email_url, headers=headers)
        email_response.raise_for_status()
        email_data = email_response.json()
        
        # Extract email from response
        email = email_data.get('elements', [{}])[0].get('handle~', {}).get('emailAddress')

        # Get profile picture
        profile_picture = self.get_profile_picture(headers)

        profile_info = {
            'linkedin_id': profile_data.get('id'),
            'first_name': profile_data.get('localizedFirstName'),
            'last_name': profile_data.get('localizedLastName'),
            'email': email,
            'headline': profile_data.get('headline'),
            'vanity_name': profile_data.get('vanityName'),
            'profile_picture_url': profile_picture
        }

        return profile_info

    def get_profile_picture(self, headers):
        """Get user's LinkedIn profile picture
        
        Args:
            headers (dict): Request headers with access token
            
        Returns:
            str: Profile picture URL or None
        """
        try:
            picture_url = 'https://api.linkedin.com/v2/me?projection=(profilePicture(displayImage~:playableStreams))'
            response = requests.get(picture_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if 'profilePicture' in data:
                elements = data['profilePicture']['displayImage~']['elements']
                if elements:
                    # Get the highest quality image
                    return max(elements, key=lambda x: x['data']['width'])['identifiers'][0]['identifier']
            return None
        except Exception as e:
            logger.error('Error getting profile picture: %s', str(e))
            return None

    def update_or_create_profile(self, user, access_token, refresh_token=None, expires_at=None):
        """Update or create LinkedIn profile in database
        
        Args:
            user: Django user instance
            access_token (str): LinkedIn OAuth access token
            refresh_token (str, optional): LinkedIn OAuth refresh token
            expires_at (datetime, optional): Token expiration datetime
            
        Returns:
            tuple: (LinkedInProfile instance, bool created)
        """
        try:
            # Get profile data from LinkedIn
            profile_data = self.get_profile_data_v2(access_token)
            
            # Update or create profile
            profile, created = LinkedInProfile.objects.update_or_create(
                user=user,
                linkedin_id=profile_data['linkedin_id'],
                defaults={
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'expires_at': expires_at,
                    'first_name': profile_data['first_name'],
                    'last_name': profile_data['last_name'],
                    'email': profile_data['email'],
                    'headline': profile_data['headline'],
                    'vanity_name': profile_data['vanity_name'],
                    'profile_picture_url': profile_data['profile_picture_url']
                }
            )
            
            return profile, created
            
        except Exception as e:
            logger.error('Error updating LinkedIn profile: %s', str(e))
            raise
