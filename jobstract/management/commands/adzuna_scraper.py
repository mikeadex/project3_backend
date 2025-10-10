from django.core.management.base import BaseCommand
from jobstract.models import Opportunity, Employer
import requests
from datetime import datetime
import time
import random
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings
from jobstract.utils.cleaner import Cleaner

# Load environment variables from .env file
env_path = Path(settings.BASE_DIR) / ".env"
load_dotenv(env_path)


class Command(BaseCommand):
    """
    Command to extract jobs from Adzuna API
    Adzuna aggregates jobs from 100+ job boards including Indeed, Monster, SME jobs, etc.
    Documentation: https://developer.adzuna.com/docs/search
    """

    help = "Fetch jobs from Adzuna API (aggregates 100+ job boards)"

    def __init__(self):
        super().__init__()
        self.cleaner = Cleaner()

    def add_arguments(self, parser):
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Print debug information",
        )
        parser.add_argument(
            "--location",
            type=str,
            default="UK",
            help="Location to search for jobs (e.g., London, Manchester, UK)",
        )
        parser.add_argument(
            "--keywords",
            type=str,
            default="",
            help="Keywords to search for (leave empty for all jobs)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Maximum age of jobs in days",
        )
        parser.add_argument(
            "--results",
            type=int,
            default=50,
            help="Number of results to fetch (max 50 per request)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update even if job already exists",
        )

    def handle(self, *args, **options):
        if options["debug"]:
            logging.basicConfig(level=logging.DEBUG)

        self.stdout.write("Starting Adzuna job fetching...")
        self.fetch_adzuna_jobs(
            location=options["location"],
            keywords=options["keywords"],
            max_days_old=options["days"],
            results_per_page=options["results"],
            force_update=options["force"],
        )
        self.stdout.write(self.style.SUCCESS("✅ Adzuna job fetching completed"))

    def fetch_adzuna_jobs(
        self,
        location="UK",
        keywords="",
        max_days_old=7,
        results_per_page=50,
        force_update=False,
    ):
        """Fetch jobs from Adzuna API"""
        app_id = os.getenv("ADZUNA_APP_ID")
        app_key = os.getenv("ADZUNA_APP_KEY")

        if not app_id or not app_key:
            self.stdout.write(
                self.style.ERROR(
                    "❌ ADZUNA_APP_ID or ADZUNA_APP_KEY not found in environment variables.\n"
                    "Please sign up at https://developer.adzuna.com/ to get your API credentials."
                )
            )
            return

        # Adzuna API endpoint for UK jobs
        base_url = f"https://api.adzuna.com/v1/api/jobs/gb/search/1"

        # Build parameters
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": min(results_per_page, 50),  # Max 50 per API
            "what": keywords,
            "where": location,
            "max_days_old": max_days_old,
            "sort_by": "date",  # Get newest jobs first
        }

        try:
            self.stdout.write(f"📡 Fetching jobs from Adzuna API...")
            self.stdout.write(f"   Location: {location}")
            self.stdout.write(f'   Keywords: {keywords if keywords else "All jobs"}')
            self.stdout.write(f"   Max age: {max_days_old} days")

            response = requests.get(base_url, params=params, timeout=30)

            # Log response status
            self.stdout.write(f"📊 Response status: {response.status_code}")

            if response.status_code == 429:
                self.stdout.write(
                    self.style.ERROR(
                        "⚠️  Rate limit exceeded. Free tier allows 250 calls/month.\n"
                        "Consider upgrading at https://developer.adzuna.com/pricing"
                    )
                )
                return

            response.raise_for_status()

            try:
                data = response.json()
            except ValueError as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to parse JSON response: {str(e)}")
                )
                return

            # Get results
            results = data.get("results", [])
            total_count = data.get("count", 0)

            self.stdout.write(
                f"📋 Found {total_count} total jobs, processing {len(results)} results"
            )

            created_count = 0
            updated_count = 0
            skipped_count = 0

            for job in results:
                try:
                    # Extract company information
                    company_data = job.get("company", {})
                    company_name = company_data.get("display_name", "Unknown Employer")

                    # Get or create employer
                    employer, _ = Employer.objects.get_or_create(
                        employer_name=company_name,
                        defaults={"employer_website": job.get("redirect_url", "")},
                    )

                    # Format salary range
                    salary_min = job.get("salary_min")
                    salary_max = job.get("salary_max")

                    if salary_min and salary_max:
                        salary_range = (
                            f"£{salary_min:,.0f} to £{salary_max:,.0f} per year"
                        )
                    elif salary_min:
                        salary_range = f"£{salary_min:,.0f}+ per year"
                    elif salary_max:
                        salary_range = f"Up to £{salary_max:,.0f} per year"
                    else:
                        salary_range = "Competitive"

                    # Parse date posted
                    date_posted = None
                    created_str = job.get("created")
                    if created_str:
                        try:
                            # Adzuna format: "2024-10-09T10:30:00Z"
                            date_posted = datetime.fromisoformat(
                                created_str.replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            self.stdout.write(
                                self.style.WARNING(
                                    f"⚠️  Could not parse date: {created_str}"
                                )
                            )
                            date_posted = datetime.now()
                    else:
                        date_posted = datetime.now()

                    # Extract location
                    location_data = job.get("location", {})
                    job_location = location_data.get("display_name", "UK")

                    # Clean location
                    job_location = self.cleaner.extract_location(job_location)

                    # Get description
                    description = job.get("description", "").strip()
                    if not description:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  Skipping job with no description: {job.get("title", "Unknown")}'
                            )
                        )
                        skipped_count += 1
                        continue

                    # Clean description
                    description = self.cleaner.clean_text(description)

                    # Extract job details
                    job_title = job.get("title", "").strip()
                    if not job_title:
                        self.stdout.write(
                            self.style.WARNING("⚠️  Skipping job with no title")
                        )
                        skipped_count += 1
                        continue

                    job_details = self.cleaner.extract_job_details(description)
                    skills_required = job_details.get("skills_required", "")

                    # Determine job mode (remote/hybrid/on_site)
                    mode = self.cleaner.determine_job_mode(job_title, description)

                    # Determine experience level
                    experience_level = self.cleaner.determine_experience_level(
                        job_title, description
                    )

                    # Determine time commitment (full-time/part-time)
                    contract_type = job.get("contract_type", "").lower()
                    if "part" in contract_type or "part time" in job_title.lower():
                        time_commitment = "part_time"
                    elif "contract" in contract_type:
                        time_commitment = "flexible"
                    else:
                        time_commitment = "full_time"

                    # Get application URL (Adzuna redirect URL)
                    application_url = job.get("redirect_url", "")
                    if not application_url:
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠️  Skipping job with no application URL: {job_title}"
                            )
                        )
                        skipped_count += 1
                        continue

                    # Create job data
                    job_data = {
                        "employer": employer,
                        "title": job_title,
                        "description": description,
                        "location": job_location,
                        "salary_range": salary_range,
                        "date_posted": date_posted,
                        "mode": mode,
                        "time_commitment": time_commitment,
                        "source": "https://www.adzuna.co.uk",
                        "application_url": application_url,
                        "opportunity_type": "job",
                        "experience_level": experience_level,
                        "skills_required": skills_required,
                        "skills_gained": "",
                        "expenses_paid": True,
                        "start_date": None,
                        "end_date": None,
                    }

                    # Create or update job
                    if force_update:
                        job_obj, created = Opportunity.objects.update_or_create(
                            title=job_data["title"],
                            employer=employer,
                            application_url=application_url,
                            defaults=job_data,
                        )
                    else:
                        # Only create if doesn't exist
                        job_obj, created = Opportunity.objects.get_or_create(
                            title=job_data["title"],
                            employer=employer,
                            application_url=application_url,
                            defaults=job_data,
                        )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✅ Created new job: {job_title[:60]} at {company_name}"
                            )
                        )
                    else:
                        if force_update:
                            updated_count += 1
                            self.stdout.write(
                                f"🔄 Updated existing job: {job_title[:60]}"
                            )
                        else:
                            skipped_count += 1
                            self.stdout.write(f"⏭️  Skipped duplicate: {job_title[:60]}")

                    # Be nice to the API
                    time.sleep(random.uniform(0.3, 0.7))

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error processing job: {str(e)}")
                    )
                    logging.exception("Error processing job")
                    skipped_count += 1
                    continue

            # Summary
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(self.style.SUCCESS("📊 ADZUNA SCRAPER SUMMARY"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(f"✅ Jobs created: {created_count}")
            self.stdout.write(f"🔄 Jobs updated: {updated_count}")
            self.stdout.write(f"⏭️  Jobs skipped: {skipped_count}")
            self.stdout.write(f"📋 Total processed: {len(results)}")
            self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))

        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR("❌ Request timeout. Please try again."))
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error fetching jobs from Adzuna: {str(e)}")
            )
            logging.exception("Error in fetch_adzuna_jobs")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Unexpected error: {str(e)}"))
            logging.exception("Unexpected error in Adzuna scraper")
