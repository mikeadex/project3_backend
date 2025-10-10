"""
Script to populate Experience and Skill tables from existing CV data for user 'mall'
This fixes the issue where templates show experience data but database tables are empty
"""

import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth.models import User
from cv_writer.models import CvWriter, Experience, Skill, Education
import json
import re
from datetime import datetime


def parse_date(date_str):
    """Parse date strings like 'June 2010' or 'Present' to datetime"""
    if not date_str or date_str.lower() in ["present", "current"]:
        return None

    # Try various date formats
    formats = [
        "%B %Y",  # June 2010
        "%b %Y",  # Jun 2010
        "%Y-%m",  # 2010-06
        "%Y",  # 2010
        "%m/%Y",  # 06/2010
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    return None


def extract_experience_from_text(cv):
    """Extract experience data from professional summary or other text fields"""
    experiences = []

    # Get professional summary if exists
    summary_obj = cv.professional_summaries.first()
    if summary_obj:
        summary_text = summary_obj.summary

        # Look for job titles and companies in the text
        # Pattern: Job Title\nCompany Name\nDate - Date
        # This is a simplified parser - may need adjustment based on actual format
        lines = summary_text.split("\n")

        current_exp = {}
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Check if line looks like a job title (often in bold or first in section)
            if "Accounts Assistant" in line or "Assistant" in line:
                if current_exp:
                    experiences.append(current_exp)
                current_exp = {"job_title": line}

            # Check if line looks like a company name
            elif (
                "Firm" in line or "Company" in line or "–" in line or "-" in line
            ) and current_exp:
                # Extract company name (may have location after em-dash)
                company_parts = re.split(r"[–-]", line)
                current_exp["company_name"] = company_parts[0].strip()
                if len(company_parts) > 1:
                    current_exp["location"] = company_parts[1].strip()

            # Check if line looks like dates
            elif re.search(r"\d{4}|Present", line) and current_exp:
                date_match = re.search(
                    r"(\w+\s+\d{4})\s*[–-]\s*(\w+\s+\d{4}|Present)", line
                )
                if date_match:
                    current_exp["start_date"] = date_match.group(1)
                    current_exp["end_date"] = date_match.group(2)

        # Add last experience
        if current_exp:
            experiences.append(current_exp)

    return experiences


def populate_cv_data():
    """Main function to populate CV data"""
    print("=" * 60)
    print("POPULATING CV DATA FOR USER 'mall'")
    print("=" * 60)

    # Get user 'mall'
    try:
        user = User.objects.get(username="mall")
        print(f"✅ Found user: {user.username}")
    except User.DoesNotExist:
        print("❌ User 'mall' not found!")
        return

    # Get their CV
    cvs = CvWriter.objects.filter(user=user)
    print(f"\n📄 Found {cvs.count()} CV(s) for user 'mall'")

    if not cvs.exists():
        print("❌ No CVs found for user 'mall'!")
        return

    # Use the first CV
    cv = cvs.first()
    print(f"\n✅ Using CV: {cv.id} - {cv.title}")

    # Check for parsed_data (if using cv_parser app)
    from cv_parser.models import CVDocument

    cv_docs = CVDocument.objects.filter(user=user)

    parsed_data = None
    if cv_docs.exists():
        cv_doc = cv_docs.first()
        parsed_data = cv_doc.parsed_data
        print(f"\n✅ Found parsed_data from CVDocument {cv_doc.id}")

    # Manual experience data for Rachel Smith (Accounts Assistant)
    # Based on the template data you provided
    manual_experience = [
        {
            "company_name": "Salford Accountancy Firm",
            "job_title": "Accounts Assistant",
            "location": "Coventry",
            "start_date": "June 2010",
            "end_date": "Present",
            "current": True,
            "job_description": """• Processed client invoices and managed payment runs, ensuring timely settlement of accounts payable and maintaining positive vendor relationships
• Reconciled financial accounts and investigated discrepancies, contributing to accurate monthly financial reporting
• Resolved client financial queries and expense-related matters, delivering professional support and maintaining service standards
• Executed payment runs and managed expense processing, adhering to strict deadlines and internal controls
• Provided cross-functional support across the finance team, ensuring continuity of key accounting functions during staff absences""",
            "employment_type": "Full-time",
            "achievements": "Maintained 100% accuracy in payment processing, contributed to successful monthly close processes",
        }
    ]

    # Populate Experience
    print("\n" + "=" * 60)
    print("POPULATING EXPERIENCE DATA")
    print("=" * 60)

    # Check if parsed_data has experience
    if parsed_data and "experience" in parsed_data:
        print(f"\n📋 Found {len(parsed_data['experience'])} experiences in parsed_data")
        for exp_data in parsed_data["experience"]:
            print(
                f"\n  Processing: {exp_data.get('job_title', 'N/A')} at {exp_data.get('company', 'N/A')}"
            )

            # Create Experience record
            start_date = parse_date(exp_data.get("start_date"))
            end_date = parse_date(exp_data.get("end_date"))
            is_current = (
                exp_data.get("current", False)
                or exp_data.get("end_date", "").lower() == "present"
            )

            exp, created = Experience.objects.get_or_create(
                user=user,
                cv=cv,
                company_name=exp_data.get("company", ""),
                job_title=exp_data.get("job_title", ""),
                defaults={
                    "start_date": start_date,
                    "end_date": end_date if not is_current else None,
                    "current": is_current,
                    "job_description": exp_data.get("description", "")
                    or exp_data.get("job_description", ""),
                    "achievements": exp_data.get("achievements", ""),
                    "employment_type": exp_data.get("employment_type", "Full-time"),
                },
            )

            if created:
                print(f"  ✅ Created: {exp.job_title} at {exp.company_name}")
            else:
                print(f"  ⚠️  Already exists: {exp.job_title} at {exp.company_name}")
    else:
        print(
            "\n📋 No parsed_data found, using manual experience data for Rachel Smith"
        )
        for exp_data in manual_experience:
            start_date = parse_date(exp_data.get("start_date"))
            end_date = (
                parse_date(exp_data.get("end_date"))
                if not exp_data.get("current")
                else None
            )

            exp, created = Experience.objects.get_or_create(
                user=user,
                cv=cv,
                company_name=exp_data["company_name"],
                job_title=exp_data["job_title"],
                defaults={
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": exp_data.get("current", False),
                    "job_description": exp_data.get("job_description", ""),
                    "achievements": exp_data.get("achievements", ""),
                    "employment_type": exp_data.get("employment_type", "Full-time"),
                },
            )

            if created:
                print(f"\n  ✅ Created: {exp.job_title} at {exp.company_name}")
            else:
                print(f"\n  ⚠️  Already exists: {exp.job_title} at {exp.company_name}")

    # Populate Skills
    print("\n" + "=" * 60)
    print("POPULATING SKILLS DATA")
    print("=" * 60)

    # Manual skills for Accounts Assistant role
    manual_skills = [
        {"skill_name": "Accounts Payable", "skill_level": "Advanced"},
        {"skill_name": "Financial Reporting", "skill_level": "Intermediate"},
        {"skill_name": "Invoice Processing", "skill_level": "Advanced"},
        {"skill_name": "Account Reconciliation", "skill_level": "Advanced"},
        {"skill_name": "Excel", "skill_level": "Advanced"},
        {"skill_name": "Payment Processing", "skill_level": "Advanced"},
        {"skill_name": "Expense Management", "skill_level": "Intermediate"},
        {"skill_name": "Financial Software", "skill_level": "Intermediate"},
    ]

    if parsed_data and "skills" in parsed_data and parsed_data["skills"]:
        print(f"\n📋 Found {len(parsed_data['skills'])} skills in parsed_data")
        for skill_data in parsed_data["skills"]:
            skill_name = (
                skill_data
                if isinstance(skill_data, str)
                else skill_data.get("name", "") or skill_data.get("skill_name", "")
            )
            skill_level = (
                skill_data.get("level", "Intermediate")
                if isinstance(skill_data, dict)
                else "Intermediate"
            )

            if skill_name:
                skill, created = Skill.objects.get_or_create(
                    user=user,
                    cv=cv,
                    skill_name=skill_name,
                    defaults={"skill_level": skill_level},
                )

                if created:
                    print(f"  ✅ Created: {skill.skill_name} ({skill.skill_level})")
                else:
                    print(f"  ⚠️  Already exists: {skill.skill_name}")
    else:
        print(
            "\n📋 No skills in parsed_data, using manual skills for Accounts Assistant role"
        )
        for skill_data in manual_skills:
            skill, created = Skill.objects.get_or_create(
                user=user,
                cv=cv,
                skill_name=skill_data["skill_name"],
                defaults={"skill_level": skill_data["skill_level"]},
            )

            if created:
                print(f"  ✅ Created: {skill.skill_name} ({skill.skill_level})")
            else:
                print(f"  ⚠️  Already exists: {skill.skill_name}")

    # Verify results
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    exp_count = Experience.objects.filter(user=user, cv=cv).count()
    skill_count = Skill.objects.filter(user=user, cv=cv).count()

    print(f"\n✅ Total Experiences for {user.username}: {exp_count}")
    print(f"✅ Total Skills for {user.username}: {skill_count}")

    if exp_count > 0:
        print("\n📋 Experience List:")
        for exp in Experience.objects.filter(user=user, cv=cv):
            print(f"  - {exp.job_title} at {exp.company_name}")

    if skill_count > 0:
        print("\n📋 Skills List:")
        for skill in Skill.objects.filter(user=user, cv=cv)[:10]:
            print(f"  - {skill.skill_name} ({skill.skill_level})")

    print("\n" + "=" * 60)
    print("✅ POPULATION COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    populate_cv_data()
