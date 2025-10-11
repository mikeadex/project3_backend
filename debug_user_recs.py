#!/usr/bin/env python
"""
Debug Current User's Recommendations

This script helps identify why a specific user is getting wrong recommendations.
"""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth import get_user_model
from cv_writer.models import Experience, Skill, CvWriter
from ai_cv_parser.models import ParsedCV
from jobstract.recommendation_engine import JobRecommendationEngine

User = get_user_model()

def debug_user_recommendations(username):
    """Debug why user is getting specific recommendations"""
    
    print("\n" + "="*70)
    print(f"DEBUGGING RECOMMENDATIONS FOR: {username}")
    print("="*70 + "\n")
    
    # Get user
    try:
        user = User.objects.get(username=username)
        print(f"✅ User: {user.username} (ID: {user.id})")
        print(f"   Email: {user.email}")
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return
    
    # Check CVs
    print("\n📄 CV Writer Records:")
    cvs = CvWriter.objects.filter(user=user)
    print(f"   Total CVs: {cvs.count()}")
    
    if cvs.count() == 0:
        print("   ❌ No CV found - user needs to upload a CV!")
        return
    
    primary_cv = cvs.filter(is_primary=True).first()
    if not primary_cv:
        primary_cv = cvs.order_by("-created_at").first()
        print(f"   ⚠️  No primary CV - using most recent: ID {primary_cv.id}")
    else:
        print(f"   ✅ Primary CV: ID {primary_cv.id}")
    
    # Check ParsedCV
    print("\n📋 Parsed CV Data:")
    parsed_cvs = ParsedCV.objects.filter(user=user).order_by("-uploaded_at")
    if parsed_cvs.exists():
        latest_parsed = parsed_cvs.first()
        print(f"   Latest upload: {latest_parsed.file_name}")
        print(f"   Status: {latest_parsed.status}")
        print(f"   Uploaded: {latest_parsed.uploaded_at}")
        
        if latest_parsed.parsed_data:
            # Show job titles from parsed data
            if "experience" in latest_parsed.parsed_data:
                print(f"\n   📊 Job Titles in Parsed CV:")
                for exp in latest_parsed.parsed_data["experience"][:5]:
                    job_title = exp.get("job_title") or exp.get("title", "Unknown")
                    company = exp.get("company") or exp.get("company_name", "Unknown")
                    print(f"      - {job_title} at {company}")
    else:
        print("   ⚠️  No parsed CV found")
    
    # Check Experiences in database
    print("\n💼 Experience Records in Database:")
    experiences = Experience.objects.filter(cv=primary_cv)
    print(f"   Total: {experiences.count()}")
    
    if experiences.count() > 0:
        print(f"\n   📋 Stored Experiences:")
        for exp in experiences[:5]:
            current = "(CURRENT)" if exp.current else ""
            print(f"      - {exp.job_title} at {exp.company_name} {current}")
    else:
        print("   ❌ NO EXPERIENCES IN DATABASE!")
        print("   This is why recommendations are wrong!")
        print("\n   💡 Solution: Run cleanup script to populate from parsed CV")
    
    # Check Skills
    print("\n🎯 Skills in Database:")
    skills = Skill.objects.filter(cv=primary_cv)
    print(f"   Total: {skills.count()}")
    
    if skills.count() > 0:
        print(f"\n   Top 10 skills:")
        for skill in skills[:10]:
            print(f"      - {skill.skill_name}")
    else:
        print("   ❌ NO SKILLS IN DATABASE!")
    
    # Run recommendation engine
    print("\n🎯 Recommendation Engine Analysis:")
    print("   " + "-"*66)
    
    try:
        engine = JobRecommendationEngine(user=user, cv=primary_cv)
        
        # Get user profile
        profile = engine.user_profile
        
        print(f"\n   👤 User Profile Built:")
        print(f"      Career Field: {profile.get('career_field', 'UNKNOWN')}")
        print(f"      Total Experience: {profile.get('total_years_experience', 0):.1f} years")
        print(f"      Relevant Experience: {profile.get('years_experience', 0):.1f} years")
        print(f"      Experience Level: {profile.get('experience_level', 'UNKNOWN')}")
        print(f"      Career Changer: {profile.get('is_career_changer', False)}")
        
        if profile.get('career_change_note'):
            print(f"      Note: {profile['career_change_note']}")
        
        print(f"\n      Skills Count: {len(profile.get('skills', []))}")
        if profile.get('skills'):
            skills_sample = list(profile['skills'])[:5]
            print(f"      Sample Skills: {', '.join(skills_sample)}")
        
        print(f"\n      Job Titles: {', '.join(profile.get('job_titles', [])[:3])}")
        
        # Get recommendations
        print(f"\n   🎯 Top 5 Recommendations:")
        recs = engine.get_recommendations(limit=5)
        
        if recs:
            for i, rec in enumerate(recs, 1):
                job = rec['job']
                score = rec['score']
                
                badge = "✅" if score >= 70 else "⚠️" if score >= 50 else "❌"
                
                print(f"\n   {i}. [{score:5.1f}%] {badge} {job.title}")
                print(f"      Company: {job.employer.employer_name}")
                print(f"      Level: {job.experience_level}")
                
                # Show score breakdown
                comp_scores = rec['component_scores']
                print(f"      Breakdown: Skills={comp_scores['skills']:.0f}% | "
                      f"Title={comp_scores['title']:.0f}% | "
                      f"Experience={comp_scores['experience']:.0f}% | "
                      f"Location={comp_scores['location']:.0f}%")
        else:
            print("   ❌ No recommendations generated!")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Diagnosis
    print("\n" + "="*70)
    print("DIAGNOSIS")
    print("="*70 + "\n")
    
    has_cv = cvs.count() > 0
    has_parsed = parsed_cvs.exists()
    has_exp = experiences.count() > 0
    has_skills = skills.count() > 0
    
    if not has_cv:
        print("❌ CRITICAL: No CV found")
        print("   Action: Upload a CV")
    elif not has_parsed:
        print("⚠️  WARNING: No parsed CV data")
        print("   Action: Upload a new CV")
    elif not has_exp and not has_skills:
        print("❌ CRITICAL: Database tables empty (no Experience/Skill records)")
        print("   Cause: Auto-population didn't run OR old data needs cleanup")
        print("   Action: Run cleanup script:")
        print(f"   → python cleanup_user_cv_data.py")
        print(f"   → Enter username: {username}")
    elif has_exp and has_skills:
        # Check if career field matches CV
        expected_field = None
        if parsed_cvs.exists() and parsed_cvs.first().parsed_data:
            # Try to detect expected field from job titles
            titles = []
            for exp in parsed_cvs.first().parsed_data.get("experience", [])[:3]:
                title = exp.get("job_title") or exp.get("title", "")
                titles.append(title.lower())
            
            titles_str = " ".join(titles)
            if any(kw in titles_str for kw in ["developer", "software", "engineer", "programmer"]):
                expected_field = "technology"
            elif any(kw in titles_str for kw in ["retail", "store", "manager", "sales"]):
                expected_field = "retail"
            elif any(kw in titles_str for kw in ["accountant", "finance", "accounts"]):
                expected_field = "finance"
        
        detected_field = profile.get('career_field', 'unknown')
        
        if expected_field and expected_field != detected_field:
            print(f"⚠️  MISMATCH: Career field detection issue")
            print(f"   CV shows: {expected_field.upper()} jobs")
            print(f"   Engine detected: {detected_field.upper()}")
            print(f"   Cause: Mixed/old experience data in database")
            print(f"   Action: Run cleanup script to refresh data")
        elif recs and recs[0]['score'] < 50:
            print(f"⚠️  LOW SCORES: Top match only {recs[0]['score']:.1f}%")
            print(f"   Cause: Skills/experience mismatch with available jobs")
            print(f"   Action: Normal - may need more job listings in this field")
        else:
            print(f"✅ WORKING CORRECTLY!")
            print(f"   Career Field: {detected_field}")
            print(f"   Top Recommendation: {recs[0]['job'].title if recs else 'N/A'}")
            print(f"   Match Score: {recs[0]['score']:.1f}% if recs else 'N/A'}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("USER RECOMMENDATION DEBUGGER")
    print("="*70)
    
    username = input("\nEnter username to debug: ").strip()
    
    if username:
        debug_user_recommendations(username)
    else:
        print("❌ No username provided!")
