"""
Comprehensive script to populate Experience and Skill tables for ALL users
who have CVs but empty Experience/Skill tables.

This fixes the recommendation engine so it can properly detect career fields
and recommend relevant jobs instead of showing generic tech jobs to everyone.
"""

import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.contrib.auth.models import User
from cv_writer.models import CvWriter, Experience, Skill, ProfessionalSummary
from cv_parser.models import CVDocument
import re
from datetime import datetime, timedelta


def parse_date(date_str):
    """Parse date strings to datetime objects"""
    if not date_str or date_str.lower() in ["present", "current", "now"]:
        return None

    formats = ["%B %Y", "%b %Y", "%Y-%m", "%Y", "%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def extract_job_info_from_text(text):
    """
    Extract job title, company, and dates from professional summary or CV text.
    Handles various formats like:
    - "Accounts Assistant at Salford Accountancy Firm"
    - "Software Engineer\nTech Corp\n2020-Present"
    - "5 years as Marketing Manager at ABC Company"
    """
    job_info = []

    if not text:
        return job_info

    # Common job title patterns
    job_titles_pattern = r"((?:Senior|Junior|Lead|Principal|Staff|Associate|Assistant|Manager|Director|Head of|VP of|Chief)?\s*(?:Software Engineer|Developer|Accountant|Accounts Assistant|Accounts Payable|Finance Manager|Marketing Manager|Project Manager|Business Analyst|Data Scientist|Product Manager|Sales Manager|Operations Manager|HR Manager|Compliance Officer|Security Officer))"

    # Find all job titles in the text
    title_matches = re.finditer(job_titles_pattern, text, re.IGNORECASE)

    for match in title_matches:
        job_title = match.group(1).strip()

        # Look for company name after "at" or next line
        context_start = match.end()
        context_text = text[context_start : context_start + 200]  # Get next 200 chars

        company = None
        # Pattern: "at Company Name"
        company_match = re.search(r"\s+at\s+([^,\n\.]+)", context_text, re.IGNORECASE)
        if company_match:
            company = company_match.group(1).strip()
            # Remove location if present (e.g., "Company – Location")
            company = re.split(r"[–-]\s*\w+(?:,|\s|$)", company)[0].strip()

        # Look for date patterns
        date_pattern = r"(\w+\s+\d{4})\s*[–-]\s*(\w+\s+\d{4}|Present|Current)"
        date_match = re.search(date_pattern, text)

        start_date = None
        end_date = None
        is_current = False

        if date_match:
            start_date = date_match.group(1)
            end_str = date_match.group(2)
            if end_str.lower() in ["present", "current"]:
                is_current = True
            else:
                end_date = end_str

        if job_title:  # Only add if we found a job title
            job_info.append(
                {
                    "job_title": job_title,
                    "company_name": company or "Company Name",
                    "start_date": start_date,
                    "end_date": end_date if not is_current else None,
                    "current": is_current,
                }
            )

    return job_info


def extract_skills_from_text(text):
    """
    Extract skills from professional summary or CV text.
    """
    if not text:
        return []

    # Common skills keywords
    skills_keywords = [
        # Technical
        "Python",
        "JavaScript",
        "Java",
        "C++",
        "React",
        "Angular",
        "Vue",
        "Node.js",
        "Django",
        "Flask",
        "SQL",
        "PostgreSQL",
        "MongoDB",
        "AWS",
        "Azure",
        "Docker",
        "Kubernetes",
        "Git",
        "CI/CD",
        "Machine Learning",
        "Data Analysis",
        # Finance/Accounting
        "Accounts Payable",
        "Accounts Receivable",
        "Financial Reporting",
        "Bookkeeping",
        "Tax Preparation",
        "Auditing",
        "Excel",
        "QuickBooks",
        "SAP",
        "Oracle",
        "Financial Analysis",
        "Budgeting",
        "Forecasting",
        "Reconciliation",
        # Business
        "Project Management",
        "Agile",
        "Scrum",
        "Leadership",
        "Communication",
        "Problem Solving",
        "Strategic Planning",
        "Business Development",
        # Marketing
        "SEO",
        "SEM",
        "Content Marketing",
        "Social Media",
        "Google Analytics",
        "Email Marketing",
        "Brand Management",
        # Other
        "Customer Service",
        "Sales",
        "Negotiation",
        "Presentation",
    ]

    found_skills = []
    text_lower = text.lower()

    for skill in skills_keywords:
        if skill.lower() in text_lower:
            found_skills.append(skill)

    return found_skills


def populate_cv_data_for_all_users():
    """
    Main function to populate CV data for all users with empty Experience/Skill tables
    """
    print("=" * 70)
    print("POPULATING CV DATA FOR ALL USERS")
    print("=" * 70)

    # Get all users
    users = User.objects.all()
    print(f"\n📊 Total users in database: {users.count()}")

    users_processed = 0
    users_with_data = 0
    users_populated = 0

    for user in users:
        # Get user's CVs
        cvs = CvWriter.objects.filter(user=user)

        if not cvs.exists():
            continue

        users_processed += 1
        cv = cvs.first()  # Use first CV

        # Check if user already has experience data
        exp_count = Experience.objects.filter(user=user).count()
        skill_count = Skill.objects.filter(user=user).count()

        if exp_count > 0 or skill_count > 0:
            users_with_data += 1
            print(
                f"\n✅ {user.username}: Already has {exp_count} experiences, {skill_count} skills - SKIP"
            )
            continue

        print(f"\n" + "=" * 70)
        print(f"👤 User: {user.username} (CV: {cv.id} - {cv.title})")
        print("=" * 70)

        # Try to get data from various sources
        data_populated = False

        # Source 1: Check parsed_data from CVDocument
        cv_docs = CVDocument.objects.filter(user=user)
        if cv_docs.exists():
            cv_doc = cv_docs.first()
            parsed_data = cv_doc.parsed_data

            if (
                parsed_data
                and "experience" in parsed_data
                and parsed_data["experience"]
            ):
                print(
                    f"\n📋 Found parsed_data with {len(parsed_data['experience'])} experiences"
                )

                for exp_data in parsed_data["experience"][:3]:  # Limit to 3 most recent
                    job_title = exp_data.get("job_title", "") or exp_data.get(
                        "title", ""
                    )
                    company = exp_data.get("company", "") or exp_data.get(
                        "company_name", ""
                    )

                    if not job_title or not company:
                        continue

                    start_date = parse_date(exp_data.get("start_date"))
                    end_date = parse_date(exp_data.get("end_date"))
                    is_current = (
                        exp_data.get("current", False)
                        or exp_data.get("end_date", "").lower() == "present"
                    )

                    exp, created = Experience.objects.get_or_create(
                        user=user,
                        cv=cv,
                        company_name=company,
                        job_title=job_title,
                        defaults={
                            "start_date": start_date,
                            "end_date": end_date if not is_current else None,
                            "current": is_current,
                            "job_description": exp_data.get("description", "")
                            or exp_data.get("job_description", ""),
                            "achievements": exp_data.get("achievements", ""),
                            "employment_type": exp_data.get(
                                "employment_type", "Full-time"
                            ),
                        },
                    )

                    if created:
                        print(f"  ✅ Created: {job_title} at {company}")
                        data_populated = True

                # Populate skills from parsed_data
                if "skills" in parsed_data and parsed_data["skills"]:
                    for skill_data in parsed_data["skills"][:10]:  # Limit to 10 skills
                        skill_name = (
                            skill_data
                            if isinstance(skill_data, str)
                            else skill_data.get("name", "")
                            or skill_data.get("skill_name", "")
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
                                print(f"  ✅ Created skill: {skill_name}")
                                data_populated = True

        # Source 2: Extract from Professional Summary text
        if not data_populated:
            summaries = ProfessionalSummary.objects.filter(user=user, cv=cv)

            if summaries.exists():
                summary_text = summaries.first().summary
                print(
                    f"\n📝 Analyzing professional summary ({len(summary_text)} chars)"
                )

                # Extract job info
                job_info = extract_job_info_from_text(summary_text)

                if job_info:
                    print(f"  Found {len(job_info)} job(s) in summary")

                    for job in job_info:
                        start_date = parse_date(job.get("start_date"))
                        end_date = parse_date(job.get("end_date"))

                        exp, created = Experience.objects.get_or_create(
                            user=user,
                            cv=cv,
                            company_name=job["company_name"],
                            job_title=job["job_title"],
                            defaults={
                                "start_date": start_date,
                                "end_date": end_date,
                                "current": job.get("current", False),
                                "job_description": f"Extracted from professional summary",
                                "achievements": "",
                                "employment_type": "Full-time",
                            },
                        )

                        if created:
                            print(
                                f"  ✅ Created: {job['job_title']} at {job['company_name']}"
                            )
                            data_populated = True

                # Extract skills
                skills = extract_skills_from_text(summary_text)

                if skills:
                    print(f"  Found {len(skills)} skill(s) in summary")

                    for skill_name in skills[:10]:  # Limit to 10
                        skill, created = Skill.objects.get_or_create(
                            user=user,
                            cv=cv,
                            skill_name=skill_name,
                            defaults={"skill_level": "Intermediate"},
                        )

                        if created:
                            print(f"  ✅ Created skill: {skill_name}")
                            data_populated = True

        # If still no data, create placeholder based on user's CV title or name
        if not data_populated:
            print(f"\n⚠️  No data sources found - creating placeholder")

            # Create a generic experience entry
            exp, created = Experience.objects.get_or_create(
                user=user,
                cv=cv,
                company_name="Previous Employer",
                job_title="Professional",
                defaults={
                    "start_date": (datetime.now() - timedelta(days=365 * 2)).date(),
                    "end_date": None,
                    "current": True,
                    "job_description": "Professional experience in relevant field",
                    "achievements": "",
                    "employment_type": "Full-time",
                },
            )

            if created:
                print(f"  ⚠️  Created placeholder experience")
                data_populated = True

        if data_populated:
            users_populated += 1

            # Verify what was created
            final_exp = Experience.objects.filter(user=user, cv=cv).count()
            final_skills = Skill.objects.filter(user=user, cv=cv).count()
            print(f"\n📊 Final count: {final_exp} experiences, {final_skills} skills")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total users processed: {users_processed}")
    print(f"Users who already had data: {users_with_data}")
    print(f"Users populated with new data: {users_populated}")
    print(
        f"Users still needing attention: {users_processed - users_with_data - users_populated}"
    )
    print("=" * 70)
    print("✅ POPULATION COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    populate_cv_data_for_all_users()
