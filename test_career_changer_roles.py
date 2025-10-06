#!/usr/bin/env python
"""
Test script for career changer role suggestion logic.
Verifies that candidates with most experience in non-software fields
but with software skills/certs only get junior/entry-level software roles.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Ella-backend.settings")
django.setup()

from ai_cv_parser.views import ParsedCVViewSet


def test_career_changer_scenario():
    """
    Test scenario: 12 years risk management experience + 1-5 IT certs
    Expected: Should suggest junior/entry-level software roles, NOT senior roles
    """

    # Mock CV data: 12 years risk management, IT certifications
    cv_data = {
        "experience": [
            {
                "title": "Senior Risk Management Analyst",
                "company": "Financial Corp",
                "start_date": "2018",
                "end_date": "Present",
                "description": "Risk assessment and compliance",
            },
            {
                "title": "Risk Management Officer",
                "company": "Insurance Ltd",
                "start_date": "2015",
                "end_date": "2018",
                "description": "Enterprise risk management",
            },
            {
                "title": "Compliance Analyst",
                "company": "Bank Corp",
                "start_date": "2013",
                "end_date": "2015",
                "description": "Regulatory compliance and audits",
            },
        ],
        "skills": [
            {"skill": "Risk Management", "level": "Expert"},
            {"skill": "Compliance", "level": "Expert"},
            {"skill": "Python", "level": "Intermediate"},  # IT cert skill
            {"skill": "JavaScript", "level": "Beginner"},  # IT cert skill
            {"skill": "Django", "level": "Beginner"},  # IT cert skill
        ],
    }

    # Experience level calculation (12 years, senior classification initially)
    experience_level = {
        "classification": "senior",  # Would be senior due to 12 years
        "years_experience": 12,
        "career_stage": "Senior Management",
    }

    # Hard skills include software/IT
    hard_skills = [
        {"skill": "Risk Management", "rating": 9},
        {"skill": "Compliance", "rating": 9},
        {"skill": "Python", "rating": 6},
        {"skill": "JavaScript", "rating": 5},
        {"skill": "Django", "rating": 5},
    ]

    # Create viewset instance and call _generate_potential_roles
    viewset = ParsedCVViewSet()
    suggested_roles = viewset._generate_potential_roles(
        cv_data, hard_skills, experience_level
    )

    print("=" * 80)
    print("TEST: Career Changer Role Suggestions")
    print("=" * 80)
    print("\n📋 CV Summary:")
    print(f"  • Total Experience: {experience_level['years_experience']} years")
    print(f"  • Initial Classification: {experience_level['classification']}")
    print(f"  • Software Roles in Experience: 0/3")
    print(f"  • Software Skills: Python, JavaScript, Django (from certifications)")

    print("\n🎯 Suggested Roles:")
    for i, role in enumerate(suggested_roles, 1):
        print(f"  {i}. {role}")

    print("\n✅ Validation:")
    senior_keywords = [
        "Senior",
        "Principal",
        "Lead",
        "Director",
        "Manager",
        "Chief",
        "VP",
        "Head",
    ]
    has_senior_role = any(
        any(kw in role for kw in senior_keywords) for role in suggested_roles
    )
    has_junior_role = any(
        "Junior" in role or "Assistant" in role or "Entry" in role
        for role in suggested_roles
    )

    if has_senior_role:
        print("  ❌ FAIL: Suggested senior software roles for career changer")
        print("  Expected: Only junior/entry-level roles")
    else:
        print("  ✅ PASS: No senior software roles suggested")

    if has_junior_role or any("Developer" in role for role in suggested_roles):
        print("  ✅ PASS: Suggested appropriate entry-level/junior software roles")
    else:
        print("  ⚠️  WARNING: No software roles suggested at all")

    print("\n" + "=" * 80)
    return suggested_roles


def test_non_career_changer():
    """
    Test scenario: 12 years software development experience
    Expected: Should suggest senior/lead software roles
    """

    cv_data = {
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "Tech Corp",
                "start_date": "2018",
                "end_date": "Present",
            },
            {
                "title": "Software Developer",
                "company": "StartUp Inc",
                "start_date": "2015",
                "end_date": "2018",
            },
            {
                "title": "Junior Developer",
                "company": "Dev Agency",
                "start_date": "2013",
                "end_date": "2015",
            },
        ],
        "skills": [
            {"skill": "Python", "level": "Expert"},
            {"skill": "JavaScript", "level": "Expert"},
            {"skill": "React", "level": "Advanced"},
        ],
    }

    experience_level = {
        "classification": "senior",
        "years_experience": 12,
        "career_stage": "Senior Management",
    }

    hard_skills = [
        {"skill": "Python", "rating": 9},
        {"skill": "JavaScript", "rating": 9},
        {"skill": "React", "rating": 8},
    ]

    viewset = ParsedCVViewSet()
    suggested_roles = viewset._generate_potential_roles(
        cv_data, hard_skills, experience_level
    )

    print("\n" + "=" * 80)
    print("TEST: Non-Career Changer (Software Professional)")
    print("=" * 80)
    print("\n📋 CV Summary:")
    print(f"  • Total Experience: {experience_level['years_experience']} years")
    print(f"  • Initial Classification: {experience_level['classification']}")
    print(f"  • Software Roles in Experience: 3/3")

    print("\n🎯 Suggested Roles:")
    for i, role in enumerate(suggested_roles, 1):
        print(f"  {i}. {role}")

    print("\n✅ Validation:")
    senior_keywords = ["Senior", "Principal", "Lead", "Director", "Architect"]
    has_senior_role = any(
        any(kw in role for kw in senior_keywords) for role in suggested_roles
    )

    if has_senior_role:
        print("  ✅ PASS: Suggested senior software roles for experienced professional")
    else:
        print("  ❌ FAIL: No senior roles suggested for 12-year software professional")

    print("\n" + "=" * 80)
    return suggested_roles


if __name__ == "__main__":
    print("\n🧪 Testing Career Changer Role Suggestion Logic\n")

    # Test 1: Career changer (risk management → software)
    career_changer_roles = test_career_changer_scenario()

    # Test 2: Non-career changer (software professional)
    software_pro_roles = test_non_career_changer()

    print("\n✅ Testing complete!")
    print("\nSummary:")
    print("  - Career changer should get junior/entry-level roles only")
    print("  - Software professional should get senior/lead roles")
