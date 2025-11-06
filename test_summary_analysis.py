#!/usr/bin/env python
"""
Test script for professional summary analysis enhancement.
Tests CV 132 (Finance Graduate) classification.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, "/Users/michaeladeleye/Documents/Coding/ella/Ella-backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from cv_parser.models import ParsedCV
from ai_cv_parser.views import AICVParserViewSet


def test_cv_132_classification():
    """Test that CV 132 (finance graduate) is correctly classified as entry-level."""

    print("=" * 80)
    print("TESTING: Professional Summary Analysis Enhancement")
    print("=" * 80)
    print()

    # Get CV 132
    try:
        cv = ParsedCV.objects.get(id=132)
        print(f"✅ Found CV 132 for user: {cv.user.email}")
    except ParsedCV.DoesNotExist:
        print("❌ CV 132 not found")
        return False

    # Get parsed data
    parsed_data = cv.parsed_data
    print(f"\n📄 CV DETAILS:")
    print(f"   Education: {parsed_data.get('education', [{}])[0].get('degree', 'N/A')}")

    summary = parsed_data.get("professional_summary", "")
    print(f"\n📝 PROFESSIONAL SUMMARY:")
    print(f"   {summary[:200]}...")

    experience = parsed_data.get("experience", [])
    if experience:
        exp = experience[0]
        print(f"\n💼 CURRENT ROLE:")
        print(f"   Company: {exp.get('company', 'N/A')}")
        print(f"   Title: {exp.get('title', 'N/A')}")

    # Test the _determine_experience_level method
    print(f"\n🔍 TESTING CLASSIFICATION...")
    print(
        f"   Expected: entry-level (due to 'graduate', 'trainee', 'aspiring' in summary)"
    )
    print()

    # Create viewset instance (just for method access)
    viewset = AICVParserViewSet()

    # Estimate years (would normally be calculated)
    years_exp = 12  # Mentioned in description

    # Call the method
    result = viewset._determine_experience_level(years_exp, parsed_data)

    print(f"\n📊 CLASSIFICATION RESULTS:")
    print(f"   Classification: {result.get('classification')}")
    print(f"   Years Experience: {result.get('years_experience')}")
    print(f"   Career Stage: {result.get('career_stage')}")

    if result.get("trajectory_warning"):
        print(f"\n⚠️  TRAJECTORY WARNING:")
        print(f"   {result.get('trajectory_warning')}")

    if result.get("consistency_score") is not None:
        print(f"\n📈 CAREER CONSISTENCY:")
        print(f"   Score: {result.get('consistency_score')}%")
        print(f"   Message: {result.get('consistency_message')}")

    if result.get("dominant_field"):
        print(f"   Dominant Field: {result.get('dominant_field')}")

    # Verify result
    print(f"\n{'=' * 80}")
    if result.get("classification") == "entry-level":
        print("✅ TEST PASSED: Finance graduate correctly classified as ENTRY-LEVEL")
        print(
            "   Despite 12 years experience, summary indicators overrode classification"
        )
        return True
    else:
        print(
            f"❌ TEST FAILED: Expected 'entry-level', got '{result.get('classification')}'"
        )
        print(
            f"   Summary should have detected: graduate, trainee, aspiring, assistant"
        )
        return False


if __name__ == "__main__":
    success = test_cv_132_classification()
    print("=" * 80)
    sys.exit(0 if success else 1)
