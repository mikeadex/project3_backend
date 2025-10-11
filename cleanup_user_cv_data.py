#!/usr/bin/env python
"""
Clean User CV Data - Remove old mixed experience/skill data

This script:
1. Finds your user account
2. Shows current Experience/Skill data
3. Clears ALL old data
4. Forces re-population from your current CV
"""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth import get_user_model
from cv_writer.models import Experience, Skill, CvWriter
from ai_cv_parser.models import ParsedCV

User = get_user_model()

print("=" * 70)
print("CV DATA CLEANUP SCRIPT")
print("=" * 70)

# Get your username
username = input("\nEnter your username: ").strip()

try:
    user = User.objects.get(username=username)
    print(f"\n✅ Found user: {user.username} (ID: {user.id})")
except User.DoesNotExist:
    print(f"\n❌ User '{username}' not found!")
    exit(1)

# Show current CV
print("\n" + "=" * 70)
print("CURRENT CV DATA")
print("=" * 70)

cvs = CvWriter.objects.filter(user=user)
print(f"\nTotal CVs: {cvs.count()}")

primary_cv = cvs.filter(is_primary=True).first()
if not primary_cv:
    primary_cv = cvs.order_by("-created_at").first()

if primary_cv:
    print(f"Primary CV: ID {primary_cv.id} (Created: {primary_cv.created_at})")
else:
    print("❌ No CV found!")
    exit(1)

# Show current experiences
print("\n📋 CURRENT EXPERIENCES:")
experiences = Experience.objects.filter(cv=primary_cv)
print(f"Total: {experiences.count()}")

for exp in experiences:
    current_str = "(CURRENT)" if exp.current else ""
    print(f"  - {exp.job_title} at {exp.company_name} {current_str}")

# Show current skills
print("\n🎯 CURRENT SKILLS:")
skills = Skill.objects.filter(cv=primary_cv)
print(f"Total: {skills.count()}")

for skill in skills[:15]:
    print(f"  - {skill.skill_name}")
if skills.count() > 15:
    print(f"  ... and {skills.count() - 15} more")

# Ask for confirmation
print("\n" + "=" * 70)
print("⚠️  WARNING: This will DELETE all experience and skill data!")
print("=" * 70)

confirm = (
    input("\nDo you want to CLEAR this data and re-populate from parsed CV? (yes/no): ")
    .strip()
    .lower()
)

if confirm != "yes":
    print("\n❌ Cancelled. No changes made.")
    exit(0)

# Clear old data
print("\n🗑️  Deleting old data...")
exp_count = experiences.count()
skill_count = skills.count()

experiences.delete()
skills.delete()

print(f"✅ Deleted {exp_count} experiences and {skill_count} skills")

# Re-populate from ParsedCV
print("\n🔄 Re-populating from parsed CV data...")

parsed_cv = ParsedCV.objects.filter(user=user).order_by("-uploaded_at").first()

if not parsed_cv:
    print("❌ No parsed CV found! Please upload a CV first.")
    exit(1)

print(f"Using ParsedCV ID: {parsed_cv.id}")
print(f"File: {parsed_cv.file_name}")
print(f"Uploaded: {parsed_cv.uploaded_at}")

if not parsed_cv.parsed_data:
    print("❌ No parsed data available! CV needs to be parsed first.")
    exit(1)

# Import and use the save function
from cv_writer.services import save_rewritten_cv_to_database

try:
    result_cv = save_rewritten_cv_to_database(
        rewritten_cv_data=parsed_cv.parsed_data,
        user=user,
        cv_writer_instance=primary_cv,
    )

    print("\n✅ Successfully re-populated CV data!")

    # Show new data
    print("\n" + "=" * 70)
    print("NEW DATA POPULATED")
    print("=" * 70)

    new_experiences = Experience.objects.filter(cv=primary_cv)
    print(f"\n📋 NEW EXPERIENCES: {new_experiences.count()}")
    for exp in new_experiences:
        current_str = "(CURRENT)" if exp.current else ""
        print(f"  - {exp.job_title} at {exp.company_name} {current_str}")

    new_skills = Skill.objects.filter(cv=primary_cv)
    print(f"\n🎯 NEW SKILLS: {new_skills.count()}")
    for skill in new_skills[:15]:
        print(f"  - {skill.skill_name}")
    if new_skills.count() > 15:
        print(f"  ... and {new_skills.count() - 15} more")

    print("\n" + "=" * 70)
    print("✅ CLEANUP COMPLETE!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Refresh your browser")
    print("2. Check job recommendations")
    print("3. Should now show jobs matching your CV's career field")

except Exception as e:
    print(f"\n❌ Error re-populating data: {str(e)}")
    import traceback

    traceback.print_exc()
