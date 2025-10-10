"""
Populate experience data for user 'paradigm_shift' based on their professional summary
"""

import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth.models import User
from cv_writer.models import CvWriter, Experience, Skill, ProfessionalSummary
from datetime import datetime, timedelta

user = User.objects.get(username="paradigm_shift")
cv = CvWriter.objects.filter(user=user).first()

print("=" * 70)
print(f"Populating Experience for: {user.username}")
print(f"CV: {cv.id} - {cv.title}")
print("=" * 70)

# Get professional summary
summary = ProfessionalSummary.objects.filter(user=user, cv=cv).first()

if summary:
    print(f"\n📝 Professional Summary:")
    print(summary.summary)
    print()

# Based on the summary, user is:
# - Full-Stack Software Developer
# - Background in Risk & Compliance Management
# - Co-founded an e-commerce venture
# Skills: Python, Django, JavaScript, PostgreSQL

experiences_to_create = [
    {
        "job_title": "Full-Stack Software Developer",
        "company_name": "Tech Company",  # Generic since not specified
        "start_date": (datetime.now() - timedelta(days=365 * 3)).date(),  # 3 years ago
        "end_date": None,
        "current": True,
        "job_description": "Developing secure and scalable applications using Python, Django, JavaScript, and PostgreSQL. Architecting robust back-end systems and responsive front-end interfaces. Managing API integration and cloud deployment.",
        "achievements": "Delivered end-to-end development solutions with focus on security and scalability",
        "employment_type": "Full-time",
    },
    {
        "job_title": "Risk & Compliance Manager",
        "company_name": "Financial Services Firm",  # Inferred from background
        "start_date": (datetime.now() - timedelta(days=365 * 5)).date(),  # 5 years ago
        "end_date": (datetime.now() - timedelta(days=365 * 3)).date(),  # 3 years ago
        "current": False,
        "job_description": "Managed risk and compliance operations in financial services. Specialized in regulatory compliance, risk assessment, and control frameworks.",
        "achievements": "Implemented compliance frameworks and risk management strategies",
        "employment_type": "Full-time",
    },
    {
        "job_title": "Co-Founder & Director",
        "company_name": "E-commerce Venture",
        "start_date": (
            datetime.now() - timedelta(days=365 * 4)
        ).date(),  # 4 years ago (overlapping with compliance role)
        "end_date": (datetime.now() - timedelta(days=365 * 2)).date(),  # 2 years ago
        "current": False,
        "job_description": "Co-founded and directed e-commerce business operations. Managed product development, marketing, and customer relations. Built and maintained e-commerce platform.",
        "achievements": "Successfully launched and scaled e-commerce business with entrepreneurial acumen",
        "employment_type": "Part-time",
    },
]

print("📋 Creating Experience Records:")
print("-" * 70)

for exp_data in experiences_to_create:
    exp, created = Experience.objects.get_or_create(
        user=user,
        cv=cv,
        company_name=exp_data["company_name"],
        job_title=exp_data["job_title"],
        defaults={
            "start_date": exp_data["start_date"],
            "end_date": exp_data["end_date"],
            "current": exp_data["current"],
            "job_description": exp_data["job_description"],
            "achievements": exp_data["achievements"],
            "employment_type": exp_data["employment_type"],
        },
    )

    if created:
        print(f"✅ Created: {exp_data['job_title']} at {exp_data['company_name']}")
        dates = f"{exp_data['start_date'].strftime('%Y-%m')}"
        if exp_data["current"]:
            dates += " - Present"
        elif exp_data["end_date"]:
            dates += f" - {exp_data['end_date'].strftime('%Y-%m')}"
        print(f"   Dates: {dates}")
    else:
        print(
            f"⚠️  Already exists: {exp_data['job_title']} at {exp_data['company_name']}"
        )

# Verify
print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

exp_count = Experience.objects.filter(user=user, cv=cv).count()
skill_count = Skill.objects.filter(user=user, cv=cv).count()

print(f"\n✅ Total Experiences: {exp_count}")
print(f"✅ Total Skills: {skill_count}")

print("\n📋 Experience List:")
for exp in Experience.objects.filter(user=user, cv=cv).order_by("-start_date"):
    status = (
        "Current"
        if exp.current
        else f"Ended {exp.end_date.strftime('%Y-%m') if exp.end_date else 'N/A'}"
    )
    print(f"  - {exp.job_title} at {exp.company_name} ({status})")

print("\n" + "=" * 70)
print("✅ POPULATION COMPLETE!")
print("=" * 70)
