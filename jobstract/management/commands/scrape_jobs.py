from django.core.management.base import BaseCommand
from django.utils import timezone
from jobstract.models import Opportunity
from jobstract.services.sme_scraper import SMEScraper
from django.db import transaction
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically scrapes jobs from SME website and updates the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days of jobs to scrape (default: 1)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force scrape even if jobs were recently scraped'
        )

    def handle(self, *args, **options):
        days = options['days']
        force = options['force']
        
        try:
            # Check if we need to scrape based on last scrape time
            last_job = Opportunity.objects.order_by('-created_at').first()
            if last_job and not force:
                last_scrape_time = last_job.created_at
                time_since_last_scrape = timezone.now() - last_scrape_time
                
                if time_since_last_scrape < timedelta(hours=24):
                    logger.info("Jobs were recently scraped. Skipping...")
                    self.stdout.write(self.style.SUCCESS("Jobs were recently scraped. Skipping..."))
                    return

            logger.info(f"Starting job scraping for the last {days} days")
            self.stdout.write(f"Starting job scraping for the last {days} days...")

            # Initialize scraper
            scraper = SMEScraper()
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Scrape jobs
            jobs = scraper.scrape_jobs(start_date=start_date, end_date=end_date)
            
            if not jobs:
                logger.warning("No jobs found to scrape")
                self.stdout.write(self.style.WARNING("No jobs found to scrape"))
                return

            # Process jobs in batches to avoid memory issues
            batch_size = 100
            total_jobs = len(jobs)
            processed_jobs = 0
            
            for i in range(0, total_jobs, batch_size):
                batch = jobs[i:i + batch_size]
                
                with transaction.atomic():
                    for job_data in batch:
                        try:
                            # Check if job already exists
                            existing_job = Opportunity.objects.filter(
                                title=job_data['title'],
                                company=job_data['company'],
                                location=job_data['location'],
                                job_type=job_data['job_type']
                            ).first()
                            
                            if existing_job:
                                # Update existing job if needed
                                for key, value in job_data.items():
                                    setattr(existing_job, key, value)
                                existing_job.save()
                                processed_jobs += 1
                            else:
                                # Create new job
                                Opportunity.objects.create(**job_data)
                                processed_jobs += 1
                                
                        except Exception as e:
                            logger.error(f"Error processing job {job_data.get('title', 'Unknown')}: {str(e)}")
                            continue
                
                self.stdout.write(f"Processed {processed_jobs}/{total_jobs} jobs...")

            logger.info(f"Successfully scraped and processed {processed_jobs} jobs")
            self.stdout.write(self.style.SUCCESS(f"Successfully scraped and processed {processed_jobs} jobs"))

        except Exception as e:
            logger.error(f"Error during job scraping: {str(e)}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error during job scraping: {str(e)}"))
            raise 