"""
Test career changer logic - Finance professional who pivoted to Software Development
Should get entry/junior tech jobs, NOT senior tech jobs despite 25 years total experience
"""

import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth.models import User
from cv_writer.models import CvWriter, Experience, Skill
from jobstract.recommendation_engine import JobRecommendationEngine
from datetime import datetime, timedelta

print("=" * 70)
print("TESTING CAREER CHANGER DETECTION")
print("=" * 70)

# Create test scenario: User with 20 years in finance, 2 years in tech
user = User.objects.get(username="paradigm_shift")  # Reuse existing user
cv = CvWriter.objects.filter(user=user).first()

# Clear existing experiences
Experience.objects.filter(user=user, cv=cv).delete()

print("\n📋 Creating Career Changer Profile:")
print("Scenario: 20 years in Finance/Credit Recovery → 2 years in Software Development")
print("-" * 70)

# Add 20 years of finance experience (past roles)
finance_roles = [
    {
        "job_title": "Senior Credit Recovery Manager",
        "company_name": "Financial Services Corp",
        "start_date": (datetime.now() - timedelta(days=365 * 22)).date(),
        "end_date": (datetime.now() - timedelta(days=365 * 15)).date(),
        "description": "Managed credit recovery operations, debt collection strategies, and team performance",
    },
    {
        "job_title": "Credit Risk Analyst",
        "company_name": "Banking Solutions Ltd",
        "start_date": (datetime.now() - timedelta(days=365 * 15)).date(),
        "end_date": (datetime.now() - timedelta(days=365 * 10)).date(),
        "description": "Analyzed credit risk, performed financial assessments, managed loan portfolios",
    },
    {
        "job_title": "Collections Manager",
        "company_name": "Debt Recovery Partners",
        "start_date": (datetime.now() - timedelta(days=365 * 10)).date(),
        "end_date": (datetime.now() - timedelta(days=365 * 5)).date(),
        "description": "Led collections team, implemented recovery strategies, managed accounts receivable",
    },
    {
        "job_title": "Finance Officer",
        "company_name": "Global Bank PLC",
        "start_date": (datetime.now() - timedelta(days=365 * 5)).date(),
        "end_date": (datetime.now() - timedelta(days=365 * 2)).date(),
        "description": "Handled financial operations, account management, and client relations",
    },
]

# Add 2 years of tech experience (current field)
tech_roles = [
    {
        "job_title": "Junior Software Developer",
        "company_name": "Tech Startup Inc",
        "start_date": (datetime.now() - timedelta(days=365 * 2)).date(),
        "end_date": None,
        "current": True,
        "description": "Building web applications with Python, Django, JavaScript, React. Learning full-stack development and cloud deployment",
    },
]

# Create finance experiences
print("\n📊 Finance Experience (Past):")
for role in finance_roles:
    exp = Experience.objects.create(
        user=user,
        cv=cv,
        job_title=role["job_title"],
        company_name=role["company_name"],
        start_date=role["start_date"],
        end_date=role["end_date"],
        current=False,
        job_description=role["description"],
        achievements="",
        employment_type="Full-time",
    )
    years = (role["end_date"] - role["start_date"]).days / 365.25
    print(f"  - {role['job_title']} ({years:.1f} years)")

# Create tech experience
print("\n💻 Tech Experience (Current):")
for role in tech_roles:
    exp = Experience.objects.create(
        user=user,
        cv=cv,
        job_title=role["job_title"],
        company_name=role["company_name"],
        start_date=role["start_date"],
        end_date=role.get("end_date"),
        current=role.get("current", False),
        job_description=role["description"],
        achievements="",
        employment_type="Full-time",
    )
    if role.get("current"):
        years = (datetime.now().date() - role["start_date"]).days / 365.25
        print(f"  - {role['job_title']} ({years:.1f} years - CURRENT)")

# Test recommendation engine
print("\n" + "=" * 70)
print("TESTING RECOMMENDATION ENGINE")
print("=" * 70)

engine = JobRecommendationEngine(user=user, cv=cv)

print(f"\n🎯 User Profile:")
print(f"  Career Field: {engine.user_profile['career_field']}")
print(f"  Total Experience: {engine.user_profile['total_years_experience']:.1f} years")
print(
    f"  Relevant Experience (in {engine.user_profile['career_field']}): {engine.user_profile['years_experience']:.1f} years"
)
print(f"  Experience Level: {engine.user_profile['experience_level']}")
print(f"  Career Changer: {engine.user_profile.get('is_career_changer', False)}")

if engine.user_profile.get("career_change_note"):
    print(f"\n  📝 Note: {engine.user_profile['career_change_note']}")

# Get recommendations
recs = engine.get_recommendations(limit=5)
print(f"\n💼 Top 5 Recommendations:")
print("-" * 70)

for i, rec in enumerate(recs, 1):
    job = rec["job"]
    score = rec["score"]
    company = job.employer.employer_name if job.employer else "Unknown"

    # Check if it's a senior role (which would be wrong for a junior dev)
    is_senior = any(
        word in job.title.lower()
        for word in ["senior", "lead", "principal", "staff", "architect"]
    )

    status = "⚠️ WRONG" if is_senior else "✅ GOOD"

    print(f"{i}. [{score:5.1f}%] {status} {job.title}")
    print(f"   Company: {company}")
    print(f"   Level: {job.experience_level or 'Not specified'}")
    print()

# Verification
print("=" * 70)
print("VERIFICATION")
print("=" * 70)

print(
    f"\n✅ Total years across all roles: {engine.user_profile['total_years_experience']:.1f}"
)
print(
    f"✅ Years in current field (tech): {engine.user_profile['years_experience']:.1f}"
)
print(f"✅ Experience level set to: {engine.user_profile['experience_level']}")

if engine.user_profile["years_experience"] < 3:
    print(f"\n✅ SUCCESS: User treated as JUNIOR/ENTRY-LEVEL despite 20+ years total")
    print(f"   This is correct for a career changer with only 2 years in tech!")
else:
    print(f"\n❌ ISSUE: User has {engine.user_profile['years_experience']:.1f} years")
    print(
        f"   Should be ~2 years (tech experience only), not {engine.user_profile['total_years_experience']:.1f} years (total)"
    )

print("\n" + "=" * 70)
print("✅ TEST COMPLETE!")
print("=" * 70)
