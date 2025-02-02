from django.core.management.base import BaseCommand
from jobstract.models import Opportunity, Employer
import requests
from datetime import datetime
import time
import random
import logging
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings
from jobstract.utils.cleaner import Cleaner

# Load environment variables from .env file
env_path = Path(settings.BASE_DIR) / '.env'
load_dotenv(env_path)

class Command(BaseCommand):
    """
    Command to extract jobs from Reed using their API
    Documentation: https://www.reed.co.uk/developers/jobseeker
    """
    help = 'Fetch jobs from Reed API'

    def __init__(self):
        super().__init__()
        self.cleaner = Cleaner()

    def add_arguments(self, parser):
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print debug information',
        )
        parser.add_argument(
            '--location',
            type=str,
            default='',
            help='Location to search for jobs (e.g., London, Manchester). Leave empty for UK-wide search.',
        )
        parser.add_argument(
            '--distance',
            type=int,
            default=10,
            help='Distance from location in miles (only used if location is specified)',
        )
        parser.add_argument(
            '--keywords',
            type=str,
            help='Keywords to search for',
        )

    def handle(self, *args, **options):
        if options['debug']:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write('Starting Reed job fetching...')
        self.fetch_reed_jobs(
            location=options['location'],
            distance=options['distance'],
            keywords=options['keywords']
        )
        self.stdout.write(self.style.SUCCESS('Job fetching completed'))

    def fetch_reed_jobs(self, location='', distance=10, keywords=None):
        """Fetch jobs from Reed API"""
        api_key = os.getenv('REED_API_KEY')
        if not api_key:
            self.stdout.write(self.style.ERROR(
                'REED_API_KEY not found in environment variables. '
                'Please get an API key from https://www.reed.co.uk/developers/jobseeker'
            ))
            return

        base_url = 'https://www.reed.co.uk/api/1.0/search'
        
        # Build parameters
        params = {
            'resultsToTake': 100  # Maximum allowed by API
        }
        
        # Only add location parameters if a specific location is requested
        if location:
            params.update({
                'locationName': location,
                'distanceFromLocation': distance
            })
        
        if keywords:
            params['keywords'] = keywords

        # Reed API expects Basic Auth with API key as username and blank password
        auth = (api_key, '')

        try:
            self.stdout.write(f'Fetching jobs with params: {params}')
            response = requests.get(
                base_url, 
                params=params, 
                auth=auth,
                headers={'Content-Type': 'application/json'}
            )
            
            # Log the response for debugging
            self.stdout.write(f'Response status: {response.status_code}')
            self.stdout.write(f'Response headers: {response.headers}')
            
            if response.status_code == 500:
                self.stdout.write(self.style.WARNING('Reed API returned 500 error. Trying with smaller result set...'))
                params['resultsToTake'] = 50
                response = requests.get(
                    base_url, 
                    params=params, 
                    auth=auth,
                    headers={'Content-Type': 'application/json'}
                )
            
            response.raise_for_status()
            
            try:
                jobs_data = response.json()
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f'Failed to parse JSON response: {str(e)}'))
                self.stdout.write(f'Response content: {response.text[:500]}...')  # Show first 500 chars
                return
            
            total_results = jobs_data.get('totalResults', 0)
            results = jobs_data.get('results', [])
            
            self.stdout.write(f'Found {total_results} total jobs, processing {len(results)} results')
            
            for job in results:
                try:
                    # Get or create employer
                    employer_name = job.get('employerName', 'Unknown Employer')
                    employer, _ = Employer.objects.get_or_create(
                        employer_name=employer_name
                    )
                    
                    # Format salary range
                    min_salary = job.get('minimumSalary')
                    max_salary = job.get('maximumSalary')
                    currency_unit = job.get('currency', '£')
                    if currency_unit == 'GBP':
                        currency_unit = '£'
                    
                    # Detect if salary is per day
                    description = job.get('jobDescription', '').lower()
                    title = job.get('jobTitle', '').lower()
                    combined_text = f"{description} {title}"
                    
                    is_daily_rate = any(phrase in combined_text for phrase in [
                        'per day', '/day', 'daily rate', 'day rate',
                        'per diem', 'a day', 'pd', 'p/d'
                    ])

                    if min_salary and max_salary:
                        salary_range = f'{currency_unit}{min_salary:,.2f} to {currency_unit}{max_salary:,.2f}'
                    elif min_salary:
                        salary_range = f'{currency_unit}{min_salary:,.2f}'
                    elif max_salary:
                        salary_range = f'{currency_unit}{max_salary:,.2f}'
                    else:
                        salary_range = 'Not specified'
                    
                    # Add the time period
                    if salary_range != 'Not specified':
                        salary_range += ' per day' if is_daily_rate else ' per year'

                    # Parse date with fallback
                    date_posted = None
                    date_str = job.get('datePosted')
                    if date_str:
                        try:
                            date_posted = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                        except ValueError:
                            try:
                                # Try alternative format
                                date_posted = datetime.strptime(date_str, "%Y-%m-%d")
                            except ValueError:
                                self.stdout.write(self.style.WARNING(f'Could not parse date: {date_str}'))
                                date_posted = datetime.now()  # Use current time as fallback
                    else:
                        date_posted = datetime.now()  # Use current time if no date provided

                    # Determine time commitment
                    time_commitment = 'full_time'
                    if job.get('partTime', False):
                        time_commitment = 'part_time'
                    elif job.get('contractType', '').lower() == 'contract':
                        time_commitment = 'temporary'
                    elif 'temporary' in job.get('contractType', '').lower():
                        time_commitment = 'temporary'
                    elif 'occasional' in job.get('contractType', '').lower():
                        time_commitment = 'occasional'

                    # Clean and extract job details
                    description = self.cleaner.clean_text(job.get('jobDescription', '').strip())
                    
                    # Get location from town or locationName
                    location_name = job.get('locationName', '')
                    town = job.get('town', '')
                    job_location = self.cleaner.extract_location(location_name) if location_name else self.cleaner.extract_location(town)
                    
                    # Extract job details
                    job_details = self.cleaner.extract_job_details(description)
                    skills_required = job_details.get('skills_required', '')
                    
                    # Create job object
                    job_data = {
                        'employer': employer,
                        'title': job.get('jobTitle', '').strip(),
                        'description': description,
                        'location': job_location,
                        'salary_range': salary_range,
                        'date_posted': date_posted,
                        'mode': self.cleaner.determine_job_mode(
                            job.get('jobTitle', ''),
                            description
                        ),
                        'time_commitment': time_commitment,
                        'source': job.get('jobUrl', ''),
                        'application_url': job.get('jobUrl', ''),
                        'opportunity_type': 'job',
                        'experience_level': self.cleaner.determine_experience_level(
                            job.get('jobTitle', ''),
                            description
                        ),
                        'skills_required': skills_required,
                        'skills_gained': '',
                        'expenses_paid': True,
                        'start_date': None,
                        'end_date': None
                    }
                    
                    # Ensure required fields are not empty
                    if not job_data['title'] or not job_data['description']:
                        self.stdout.write(self.style.WARNING(
                            f'Skipping job with missing required fields: {job_data["title"]}'
                        ))
                        continue

                    job_obj, created = Opportunity.objects.update_or_create(
                        title=job_data['title'],
                        employer=employer,
                        source=job_data['source'],
                        defaults=job_data
                    )
                    
                    if created:
                        self.stdout.write(self.style.SUCCESS(
                            f'Created new job: {job_data["title"]} - {job_data["salary_range"]} ({job_data["experience_level"]})'
                        ))
                    else:
                        self.stdout.write(
                            f'Updated existing job: {job_data["title"]} - {job_data["salary_range"]} ({job_data["experience_level"]})'
                        )
                    
                    # Be nice to the API
                    time.sleep(random.uniform(0.5, 1.0))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error processing job: {str(e)}'))
                    logging.exception("Error processing job")
                    continue
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fetching jobs from Reed: {str(e)}'))
            logging.exception("Error in fetch_reed_jobs")
