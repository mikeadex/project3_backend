#!/usr/bin/env python3
"""
Test script to verify skills categorization for creative/media production skills.
"""
import os
import sys
import django

# Add the backend directory to the Python path
sys.path.insert(0, "/Users/michaeladeleye/Documents/Coding/ella/Ella-backend")

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from ai_cv_parser.views import AICVParserViewSet


def test_creative_skills_categorization():
    """Test skills categorization for creative/media production skills."""
    print("Testing creative skills categorization...")

    # Create a viewset instance
    viewset = AICVParserViewSet()

    # Skills from the actual CV
    creative_skills = [
        "Fine Art Photography & Videography",
        "Podcast Production and Audio Editing",
        "Adobe Creative Suite (Premiere Pro, Photoshop, Lightroom)",
        "DaVinci Resolve",
        "Licensed Drone Piloting",
        "Insta360 & Action Camera Operation",
        "Studio Lighting and High-End Retouching",
        "Social Media & Digital Content Management",
    ]

    print("Original skills:")
    for skill in creative_skills:
        print(f"  - {skill}")

    # Test categorization
    technical_skills, soft_skills = viewset._categorize_skills(creative_skills)

    print(f"\nCategorized as Technical Skills ({len(technical_skills)}):")
    for skill in technical_skills:
        print(f"  - {skill['skill']} (rating: {skill['rating']})")

    print(f"\nCategorized as Soft Skills ({len(soft_skills)}):")
    for skill in soft_skills:
        print(f"  - {skill['skill']} (rating: {skill['rating']})")

    # Expected results:
    # All 8 skills should be technical since they're all creative/media production skills
    # None should be soft skills

    print(f"\n✅ Expected: 8 technical, 0 soft")
    print(f"✅ Actual: {len(technical_skills)} technical, {len(soft_skills)} soft")

    if len(technical_skills) == 8 and len(soft_skills) == 0:
        print("✅ Skills categorization working correctly!")
    else:
        print("❌ Skills categorization needs improvement")


if __name__ == "__main__":
    test_creative_skills_categorization()
