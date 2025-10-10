"""
Quick test script to verify recommendations for user 'mall'
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

user = User.objects.get(username="mall")
cv = CvWriter.objects.filter(user=user).first()

print("=" * 60)
print(f"User: {user.username}")
print(f"CV: {cv.id} - {cv.title}")

# Verify data is now populated
exp_count = Experience.objects.filter(user=user).count()
skills_count = Skill.objects.filter(user=user).count()
print(f"\n✅ Experiences: {exp_count}")
print(f"✅ Skills: {skills_count}")

if exp_count > 0:
    print(f"\n📋 Experience:")
    for exp in Experience.objects.filter(user=user):
        print(f"  - {exp.job_title} at {exp.company_name}")

if skills_count > 0:
    print(f"\n📋 Skills (first 5):")
    for skill in Skill.objects.filter(user=user)[:5]:
        print(f"  - {skill.skill_name}")

# Test recommendation engine
print("\n" + "=" * 60)
print("TESTING RECOMMENDATION ENGINE")
print("=" * 60)

engine = JobRecommendationEngine(user=user, cv=cv)

print(f"\n🎯 User Profile:")
print(f"  Career Field: {engine.user_profile['career_field']}")
print(f"  Years Experience: {engine.user_profile['years_experience']:.1f}")
print(f"  Skills Count: {len(engine.user_profile['skills'])}")
print(f"  Job Titles: {engine.user_profile['job_titles']}")

recs = engine.get_recommendations(limit=10)
print(f"\n📋 Top 10 Recommendations for {user.username} (Accounts Assistant):")
print(f"Expected: Finance/Accounting jobs, NOT tech jobs\n")

for i, rec in enumerate(recs, 1):
    job = rec["job"]
    score = rec["score"]
    # Get company name from employer relationship
    company = job.employer.employer_name if job.employer else "Unknown"

    print(f"{i:2d}. [{score:5.1f}%] {job.title}")
    print(f"     Company: {company}")
    print(f"     Location: {job.location}")
    print()

print("=" * 60)
print("✅ TEST COMPLETE!")
print("=" * 60)
