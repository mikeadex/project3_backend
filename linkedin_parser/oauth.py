import requests
import urllib.parse
from typing import Dict, Optional, Tuple
from django.conf import settings
from .models import LinkedInProfile

class LinkedInOAuth:
    """Handler for LinkedIn OAuth flow"""

    def __init__(self):
        self.config = settings.LINKEDIN_CONFIG
        self.client_id = self.config['CLIENT_ID']
        self.client_secret = self.config['CLIENT_SECRET']
        self.scope = self.config['SCOPE']
        self.auth_url = self.config['AUTH_URL']
        self.token_url = self.config['TOKEN_URL']

    def get_authorization_url(self, state: str, redirect_uri: str = None) -> str:
        """Get the LinkedIn authorization URL"""
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri or self.config['REDIRECT_URI'],
            'state': state,
            'scope': self.scope
        }
        
        # Use urllib to properly encode parameters
        query_string = urllib.parse.urlencode(params)
        return f"{self.auth_url}?{query_string}"

    def get_access_token(self, code: str, redirect_uri: str = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Exchange authorization code for access token"""
        try:
            response = requests.post(
                self.token_url,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri or self.config['REDIRECT_URI'],
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
            )
            response.raise_for_status()
            return response.json(), None
        except requests.exceptions.RequestException as e:
            return None, str(e)

    def handle_oauth_callback(self, code: str, profile: LinkedInProfile, redirect_uri: str = None) -> Tuple[bool, Optional[str]]:
        """Handle OAuth callback and update profile"""
        try:
            tokens, error = self.get_access_token(code, redirect_uri)
            if error:
                return False, error

            if not tokens or 'access_token' not in tokens:
                return False, "No access token received"

            # Update profile with tokens
            profile.access_token = tokens['access_token']
            if 'refresh_token' in tokens:
                profile.refresh_token = tokens['refresh_token']
            profile.save()

            return True, None
        except Exception as e:
            return False, str(e)
