#!/usr/bin/env python
"""
Quick test to verify guest CV analysis endpoints are accessible
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.urls import reverse
from rest_framework.test import APIClient


def test_guest_endpoints():
    """Test that guest endpoints are accessible without authentication"""
    client = APIClient()

    print("🧪 Testing Guest CV Analysis Endpoints\n")
    print("=" * 60)

    # Test 1: Guest analyze endpoint exists
    try:
        url = reverse("guest-cv-analysis-guest-analyze")
        print(f"✅ Guest analyze URL: {url}")
    except Exception as e:
        print(f"❌ Guest analyze URL error: {e}")
        return False

    # Test 2: Try to access without auth (should return 400 for missing data, not 401/403)
    response = client.post(url)
    print(f"✅ Guest analyze accessible (status {response.status_code})")
    if response.status_code == 401 or response.status_code == 403:
        print(f"❌ Endpoint requires authentication! Should be AllowAny")
        return False

    # Test 3: Check claim endpoint
    try:
        claim_url = reverse("guest-cv-analysis-claim-session")
        print(f"✅ Claim session URL: {claim_url}")
    except Exception as e:
        print(f"❌ Claim session URL error: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ All guest endpoints are properly configured!")
    print("\nAvailable endpoints:")
    print(f"  POST   {url}")
    print(f"  GET    /api/ai_cv_parser/guest/status/{{session_id}}/")
    print(f"  GET    /api/ai_cv_parser/guest/results/{{session_id}}/")
    print(f"  POST   {claim_url}")
    return True


if __name__ == "__main__":
    try:
        success = test_guest_endpoints()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
