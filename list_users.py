#!/usr/bin/env python
"""
Quick check - What usernames exist and which ones might be yours
"""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth import get_user_model
from cv_writer.models import CvWriter

User = get_user_model()

print("\n" + "=" * 70)
print("ALL USERS WITH CVs")
print("=" * 70 + "\n")

users = User.objects.all().order_by("-date_joined")

for user in users[:20]:  # Show last 20 users
    cvs = CvWriter.objects.filter(user=user).count()

    if cvs > 0:
        primary_cv = CvWriter.objects.filter(user=user, is_primary=True).first()
        if not primary_cv:
            primary_cv = (
                CvWriter.objects.filter(user=user).order_by("-created_at").first()
            )

        # Try to get job info
        from cv_writer.models import Experience

        exps = Experience.objects.filter(cv=primary_cv)[:1]

        job_info = ""
        if exps.exists():
            job_info = f" - {exps.first().job_title}"

        created = user.date_joined.strftime("%Y-%m-%d")

        print(f"👤 {user.username:20s} | CVs: {cvs} | Joined: {created}{job_info}")

print("\n" + "=" * 70)
print("\nTo debug a specific user, run:")
print("  python debug_user_recs.py")
print("  Then enter the username")
print("=" * 70 + "\n")
