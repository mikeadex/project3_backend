#!/usr/bin/env python
"""
Diagnostic script to check for duplicate or shared professional summaries
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

from django.contrib.auth import get_user_model
from cv_writer.models import ProfessionalSummary, CvWriter

User = get_user_model()

def check_summaries():
    print("\n" + "="*80)
    print("PROFESSIONAL SUMMARY DIAGNOSTIC REPORT")
    print("="*80 + "\n")
    
    # Get all professional summaries
    all_summaries = ProfessionalSummary.objects.all()
    print(f"Total Professional Summaries in Database: {all_summaries.count()}\n")
    
    # Check for duplicate summaries (same text)
    summary_texts = {}
    for ps in all_summaries:
        text_preview = ps.summary[:100] if ps.summary else "EMPTY"
        if text_preview not in summary_texts:
            summary_texts[text_preview] = []
        summary_texts[text_preview].append({
            'id': ps.id,
            'user': ps.user.username,
            'cv_id': ps.cv.id if ps.cv else None,
            'full_text': ps.summary
        })
    
    # Report duplicates
    duplicates_found = False
    for text_preview, entries in summary_texts.items():
        if len(entries) > 1:
            duplicates_found = True
            print(f"⚠️  DUPLICATE SUMMARY FOUND:")
            print(f"   Preview: {text_preview}...")
            print(f"   Used by {len(entries)} records:\n")
            for entry in entries:
                print(f"   - ID: {entry['id']}, User: {entry['user']}, CV ID: {entry['cv_id']}")
            print()
    
    if not duplicates_found:
        print("✅ No duplicate summaries found.\n")
    
    # Check each user's summaries
    print("\n" + "-"*80)
    print("USER-SPECIFIC SUMMARY REPORT")
    print("-"*80 + "\n")
    
    users = User.objects.filter(is_active=True)
    for user in users:
        user_summaries = ProfessionalSummary.objects.filter(user=user)
        user_cvs = CvWriter.objects.filter(user=user)
        
        print(f"User: {user.username}")
        print(f"  CVs: {user_cvs.count()}")
        print(f"  Professional Summaries: {user_summaries.count()}")
        
        if user_summaries.exists():
            for ps in user_summaries:
                cv_info = f"CV #{ps.cv.id}" if ps.cv else "No CV linked"
                preview = ps.summary[:80] if ps.summary else "EMPTY"
                print(f"    - {cv_info}: {preview}...")
        print()
    
    # Check for orphaned summaries (no CV)
    print("\n" + "-"*80)
    print("ORPHANED SUMMARIES (No CV Link)")
    print("-"*80 + "\n")
    
    orphaned = ProfessionalSummary.objects.filter(cv__isnull=True)
    if orphaned.exists():
        print(f"⚠️  Found {orphaned.count()} summaries without a CV link:\n")
        for ps in orphaned:
            preview = ps.summary[:80] if ps.summary else "EMPTY"
            print(f"  ID: {ps.id}, User: {ps.user.username}, Summary: {preview}...")
    else:
        print("✅ No orphaned summaries found.")
    
    print("\n" + "="*80)
    print("END OF REPORT")
    print("="*80 + "\n")

if __name__ == "__main__":
    check_summaries()
