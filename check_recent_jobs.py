#!/usr/bin/env python
"""Check what jobs are in the database"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Ella-backend.settings")
django.setup()

from jobstract.models import Opportunity

# Get recent jobs
jobs = Opportunity.objects.filter(opportunity_type="job").order_by("-created_at")[:100]

print("=" * 80)
print("RECENT JOBS IN DATABASE")
print("=" * 80)

# Group by categories
tech_jobs = []
retail_jobs = []
business_jobs = []
healthcare_jobs = []
finance_jobs = []
other_jobs = []

tech_keywords = ["developer", "engineer", "programmer", "software", "devops", "it"]
retail_keywords = [
    "retail",
    "store",
    "shop",
    "merchandising",
    "sales associate",
    "cashier",
]
business_keywords = ["manager", "analyst", "consultant", "operations", "administrator"]
healthcare_keywords = [
    "nurse",
    "doctor",
    "medical",
    "healthcare",
    "clinical",
    "pharmacist",
]
finance_keywords = ["accountant", "financial", "finance", "auditor", "payroll"]

for job in jobs:
    title_lower = job.title.lower()

    if any(keyword in title_lower for keyword in tech_keywords):
        tech_jobs.append(job.title)
    elif any(keyword in title_lower for keyword in retail_keywords):
        retail_jobs.append(job.title)
    elif any(keyword in title_lower for keyword in healthcare_keywords):
        healthcare_jobs.append(job.title)
    elif any(keyword in title_lower for keyword in finance_keywords):
        finance_jobs.append(job.title)
    elif any(keyword in title_lower for keyword in business_keywords):
        business_jobs.append(job.title)
    else:
        other_jobs.append(job.title)

print(f"\n📱 TECHNOLOGY JOBS ({len(tech_jobs)}):")
for job in tech_jobs[:10]:
    print(f"  - {job[:70]}")
if len(tech_jobs) > 10:
    print(f"  ... and {len(tech_jobs) - 10} more")

print(f"\n🏪 RETAIL JOBS ({len(retail_jobs)}):")
for job in retail_jobs[:10]:
    print(f"  - {job[:70]}")
if len(retail_jobs) > 10:
    print(f"  ... and {len(retail_jobs) - 10} more")

print(f"\n💼 BUSINESS/OPERATIONS JOBS ({len(business_jobs)}):")
for job in business_jobs[:10]:
    print(f"  - {job[:70]}")
if len(business_jobs) > 10:
    print(f"  ... and {len(business_jobs) - 10} more")

print(f"\n🏥 HEALTHCARE JOBS ({len(healthcare_jobs)}):")
for job in healthcare_jobs[:10]:
    print(f"  - {job[:70]}")
if len(healthcare_jobs) > 10:
    print(f"  ... and {len(healthcare_jobs) - 10} more")

print(f"\n💰 FINANCE JOBS ({len(finance_jobs)}):")
for job in finance_jobs[:10]:
    print(f"  - {job[:70]}")
if len(finance_jobs) > 10:
    print(f"  ... and {len(finance_jobs) - 10} more")

print(f"\n❓ OTHER JOBS ({len(other_jobs)}):")
for job in other_jobs[:10]:
    print(f"  - {job[:70]}")
if len(other_jobs) > 10:
    print(f"  ... and {len(other_jobs) - 10} more")

print("\n" + "=" * 80)
print(f"TOTAL JOBS: {len(jobs)}")
print("=" * 80)
