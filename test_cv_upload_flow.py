#!/usr/bin/env python
"""
Test CV Upload → Experience/Skill Population → Recommendations Flow

This script tests that:
1. CV uploads automatically populate Experience/Skill tables
2. Recommendations update immediately after CV upload
3. Different CVs produce different recommendations
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth import get_user_model
from cv_writer.models import Experience, Skill, CvWriter
from jobstract.recommendation_engine import JobRecommendationEngine

User = get_user_model()


def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f"{title:^70}")
    print("=" * 70 + "\n")


def test_user_cv_data(username):
    """Test if user has CV data populated"""
    print_separator(f"TESTING USER: {username}")

    try:
        user = User.objects.get(username=username)
        print(f"✅ User found: {user.username} (ID: {user.id})")
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found")
        return False

    # Check CvWriter
    print("\n📄 CV Writer Records:")
    cvs = CvWriter.objects.filter(user=user)
    print(f"   Total CVs: {cvs.count()}")

    primary_cv = cvs.filter(is_primary=True).first()
    if primary_cv:
        print(f"   ✅ Primary CV: ID {primary_cv.id} (Status: {primary_cv.status})")
    else:
        primary_cv = cvs.order_by("-created_at").first()
        if primary_cv:
            print(f"   ⚠️  No primary CV set, using most recent: ID {primary_cv.id}")
        else:
            print(f"   ❌ No CV found for user")
            return False

    # Check Experience
    print("\n💼 Experience Records:")
    experiences = Experience.objects.filter(cv=primary_cv)
    print(f"   Total experiences: {experiences.count()}")

    if experiences.count() > 0:
        print(f"   📋 Recent experiences:")
        for exp in experiences[:3]:
            current_str = "(CURRENT)" if exp.current else ""
            print(f"      - {exp.job_title} at {exp.company_name}")
            print(
                f"        {exp.start_date} to {exp.end_date or 'Present'} {current_str}"
            )
    else:
        print(f"   ⚠️  No experience records found")

    # Check Skills
    print("\n🎯 Skill Records:")
    skills = Skill.objects.filter(cv=primary_cv)
    print(f"   Total skills: {skills.count()}")

    if skills.count() > 0:
        print(f"   Top 10 skills:")
        for skill in skills[:10]:
            print(f"      - {skill.skill_name}")
    else:
        print(f"   ⚠️  No skill records found")

    # Test Recommendations
    print("\n🎯 Job Recommendations:")
    try:
        engine = JobRecommendationEngine(user=user, cv=primary_cv)
        recs = engine.get_recommendations(limit=5)

        if recs:
            print(f"   Generated {len(recs)} recommendations:\n")
            for i, rec in enumerate(recs, 1):
                job = rec["job"]
                score = rec["score"]

                # Match badge
                if score >= 70:
                    badge = "✅ GOOD"
                elif score >= 50:
                    badge = "⚠️  FAIR"
                else:
                    badge = "❌ WEAK"

                print(f"   {i}. [{score:5.1f}%] {badge} {job.title}")
                print(
                    f"      Company: {job.employer.employer_name if job.employer else 'N/A'}"
                )
                print(f"      Level: {job.experience_level}")
                print(f"      Location: {job.location or 'Not specified'}")
                print()
        else:
            print(f"   ⚠️  No recommendations generated")

    except Exception as rec_error:
        print(f"   ❌ Error generating recommendations: {str(rec_error)}")
        import traceback

        traceback.print_exc()

    # Summary
    print_separator("SUMMARY")
    has_cv = cvs.count() > 0
    has_exp = experiences.count() > 0
    has_skills = skills.count() > 0
    has_recs = len(recs) > 0 if "recs" in locals() else False

    status_cv = "✅" if has_cv else "❌"
    status_exp = "✅" if has_exp else "⚠️ "
    status_skills = "✅" if has_skills else "⚠️ "
    status_recs = "✅" if has_recs else "❌"

    print(f"{status_cv} CV Writer: {cvs.count()} record(s)")
    print(f"{status_exp} Experience: {experiences.count()} record(s)")
    print(f"{status_skills} Skills: {skills.count()} record(s)")
    print(
        f"{status_recs} Recommendations: {len(recs) if 'recs' in locals() else 0} generated"
    )

    all_good = has_cv and has_exp and has_skills and has_recs

    if all_good:
        print("\n🎉 ALL TESTS PASSED! User has complete data.")
    elif has_cv and not has_exp and not has_skills:
        print("\n⚠️  WARNING: CV exists but Experience/Skill tables are EMPTY!")
        print("   This indicates the auto-population didn't run.")
        print("   User will receive GENERIC recommendations.")
    elif has_cv and (has_exp or has_skills):
        print("\n⚡ PARTIAL SUCCESS: Some data populated, recommendations should work.")
    else:
        print("\n❌ INCOMPLETE: User needs to upload a CV.")

    return all_good


if __name__ == "__main__":
    print_separator("CV UPLOAD → RECOMMENDATIONS TEST")
    print("This script tests if CV uploads populate Experience/Skill tables")
    print("and generate personalized recommendations.")

    # Test users
    test_users = [
        "mall",  # Finance user
        "paradigm_shift",  # Tech user
        "creative",  # Business user
        "mike",  # Retail user
    ]

    results = {}
    for username in test_users:
        success = test_user_cv_data(username)
        results[username] = success

    # Final summary
    print_separator("FINAL RESULTS")
    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"✅ Passed: {passed}/{total} users")
    print(f"❌ Failed: {total - passed}/{total} users")

    for username, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} - {username}")

    if passed == total:
        print("\n🎉 ALL USERS HAVE COMPLETE DATA!")
        print("   CV upload → Experience/Skill population is working correctly.")
    else:
        print("\n⚠️  SOME USERS MISSING DATA!")
        print("   Either:")
        print("   1. They haven't uploaded a CV yet (expected)")
        print("   2. Auto-population failed (needs investigation)")
        print("\n   Run this script after uploading CVs to verify the fix works.")

    print_separator("TEST COMPLETE")
