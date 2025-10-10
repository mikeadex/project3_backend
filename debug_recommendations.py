#!/usr/bin/env python
"""Debug recommendation engine to see what's happening"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth import get_user_model
from jobstract.recommendation_engine import JobRecommendationEngine
from cv_writer.models import CvWriter
from jobstract.models import Opportunity

User = get_user_model()

# Get the retail manager user (mike)
user = User.objects.get(username="mike")
cv = CvWriter.objects.filter(user=user, is_primary=True).first()

print("=" * 80)
print("RECOMMENDATION ENGINE DEBUG")
print("=" * 80)

# Create engine
engine = JobRecommendationEngine(user=user, cv=cv)

print(f"\n📋 USER PROFILE:")
print(f"  User: {user.username}")
print(f"  Career Field: {engine.user_profile.get('career_field')}")
print(f"  Career Change Field: {engine.user_profile.get('career_change_field')}")
print(f"  Job Titles: {engine.user_profile.get('job_titles')}")
print(f"  Skills: {list(engine.user_profile.get('skills', []))[:10]}")

print(f"\n📊 JOBS IN DATABASE:")
all_jobs = Opportunity.objects.filter(opportunity_type="job")[:20]
for job in all_jobs:
    title = job.title.lower()
    detected_field = None
    for field, keywords in engine.CAREER_FIELDS.items():
        for keyword in keywords:
            if keyword in title:
                detected_field = field
                break
        if detected_field:
            break
    print(f"  - {job.title[:60]} → Field: {detected_field}")

print(f"\n🎯 RECOMMENDATIONS:")
recommendations = engine.get_recommendations(limit=10)
print(f"  Total recommendations: {len(recommendations)}")
for rec in recommendations[:5]:
    job = rec["job"]
    score = rec["score"]
    print(f"  - [{score:.1f}%] {job.title[:50]}")

print("\n" + "=" * 80)
