from django.core.management.base import BaseCommand
from jobstract.models import Opportunity, Employer
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import random
import re
import logging
from jobstract.utils.cleaner import Cleaner
   
class Command(BaseCommand):
    """
    Command to extract jobs from DMP website
    """

    help = "scrape Job from DMP website"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaner = Cleaner()
        # common uk cities and regions for validation (lowercase for comparison)
        self.uk_cities = {
            'london', 'manchester', 'birmingham', 'leeds', 'glasgow', 'liverpool',
            'newcastle', 'nottingham', 'sheffield', 'bristol', 'belfast', 'cardiff',
            'edinburgh', 'brighton', 'cambridge', 'oxford', 'york', 'bath', 'exeter',
            'canterbury', 'winchester', 'durham', 'leicester', 'coventry', 'hull',
            'plymouth', 'portsmouth', 'southampton', 'bradford', 'reading', 'derby',
            'wolverhampton', 'plymouth', 'stoke', 'sunderland', 'wembley', 'harrow',
            'croydon', 'watford', 'romford', 'dartford', 'enfield', 'ilford',
            'bromley', 'stratford', 'hounslow', 'kingston', 'richmond', 'barnet',
            'ealing', 'brixton', 'wimbledon', 'walthamstow', 'lewisham', 'hackney',
            'islington', 'camden', 'hammersmith', 'fulham', 'kensington', 'chelsea',
            'westminster', 'paddington', 'shoreditch', 'whitechapel', 'docklands',
            'greenwich', 'woolwich', 'clapham', 'putney', 'wandsworth', 'acton',
            'chiswick', 'hayes', 'uxbridge', 'slough', 'staines', 'woking',
            'guildford', 'crawley', 'luton', 'stevenage', 'harlow', 'chelmsford',
            'southend', 'basildon', 'grays', 'maidstone', 'ashford', 'canterbury',
            'margate', 'dover', 'folkestone', 'hastings', 'eastbourne', 'worthing',
            'chichester', 'horsham', 'redhill', 'guildford', 'farnborough',
            'aldershot', 'basingstoke', 'winchester', 'southampton', 'portsmouth',
            'gosport', 'fareham', 'havant', 'bognor'
        }
    
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
            help='Location to search for jobs (e.g. London, UK)',
        )

        parser.add_argument(
            '--distance',
            type=int,
            default=20,
            help='Distance from location to search (in km). Only use if location is not specified',
        )
    
    def handle(self, *args, **options):
        """
        Handle command execution
        """
        self.search_location = options.get('location')
        self.search_distance = options.get('distance')
        self.debug = options.get('debug', False)

        if self.debug:
            logging.basicConfig(level=logging.DEBUG)
        
        self.stdout.write('Starting DWP scraping..........')
        self.scrape_dwp()
        self.stdout.write(self.style.SUCCESS('Scraping completed.'))

    
    def scrape_dwp(self):
        base_url = 'https://findajob.dwp.gov.uk/search'
        params = {
            'pp': '50' # 50 results per page
        }

        # Only add location parameters if a specific location is requested
        if self.search_location:
            params.update({
                'w': self.search_location,      #location
                'd': str(self.search_distance)   #distance
            })
        
        self.stdout.write(f'Fetching jobs from DWP ...........')

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.9',
            }

            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                job_listings = soup.find_all('div', class_='search-result')
                
                self.stdout.write(f'Found {len(job_listings)} job listings')
                
                for job in job_listings:
                    try:
                        # Get job link and title
                        job_link = job.find('a', class_='govuk-link')
                        if not job_link:
                            continue
                            
                        job_url = job_link['href']
                        if not job_url.startswith('http'):
                            job_url = 'https://findajob.dwp.gov.uk' + job_url
                        title = job_link.text.strip()
                        
                        # Get employer and location
                        details = job.find('ul', class_='govuk-list').find_all('li')
                        location_text = None
                        location = "Unknown"  # Initialize location with default value
                        employer_name = "Unknown Employer"
                        postcode = None
                        salary = "Not specified"
                        
                        # First try to find location and salary from job details list
                        for li in details:
                            text = li.get_text(strip=True)
                            # Also get the raw HTML in case it contains structured data
                            html = str(li)
                            
                            # Try to extract salary if we haven't found it yet
                            if salary == "Not specified" and ('£' in html or 'salary' in text.lower()):
                                extracted_salary = self.cleaner.extract_salary(html)
                                if extracted_salary != "Not specified":
                                    salary = extracted_salary
                            
                            if 'Location:' in text or text.startswith('Based in'):
                                location_text = re.sub(r'^(?:Location:|Based in)\s*', '', text, flags=re.IGNORECASE).strip()
                                # Try to extract city from postcode
                                city, found_postcode = self.cleaner.extract_location_from_text(location_text)
                                if city:
                                    location = city
                                    postcode = found_postcode
                                    break
                                    
                                # If no city found, try with the raw HTML
                                city, found_postcode = self.cleaner.extract_location_from_text(html)
                                if city:
                                    location = city
                                    postcode = found_postcode
                                    break
                        
                        # Try to get employer and location from the details
                        if location == "Unknown":
                            employer_location = next((li for li in details if li.find('strong')), None)
                            if employer_location:
                                employer_name = employer_location.find('strong').text.strip()
                                # Get all text after the employer name, including HTML
                                location_parts = [str(elem) for elem in employer_location.contents 
                                               if elem.name != 'strong' and str(elem).strip()]
                                
                                # Try to extract salary from employer details if we haven't found it yet
                                if salary == "Not specified":
                                    for part in location_parts:
                                        if '£' in part:
                                            extracted_salary = self.cleaner.extract_salary(part)
                                            if extracted_salary != "Not specified":
                                                salary = extracted_salary
                                                break
                                
                                # Try to extract location
                                if location_parts:
                                    for part in location_parts:
                                        city, found_postcode = self.cleaner.extract_location_from_text(part)
                                        if city:
                                            location = city
                                            postcode = found_postcode
                                            location_text = part
                                            break
                        
                        # If still no location, try to find it in the job description page
                        if location == "Unknown":
                            try:
                                job_response = requests.get(job_url, headers=headers)
                                job_soup = BeautifulSoup(job_response.text, 'html.parser')
                                
                                # Try multiple possible location elements
                                location_elements = [
                                    job_soup.find('li', class_='job-profile__location'),
                                    job_soup.find('li', string=re.compile(r'Location:', re.IGNORECASE)),
                                    job_soup.find('li', string=re.compile(r'Based in:', re.IGNORECASE)),
                                    job_soup.find('div', class_='job-profile__header').find('p') if job_soup.find('div', class_='job-profile__header') else None,
                                    job_soup.find('p', string=re.compile(r'Location:', re.IGNORECASE)),
                                    job_soup.find('p', string=re.compile(r'Based in:', re.IGNORECASE))
                                ]
                                
                                for elem in location_elements:
                                    if elem and elem.get_text(strip=True):
                                        text = elem.get_text(strip=True)
                                        # Extract location from text
                                        text = re.sub(r'^(?:Location:|Based in:)\s*', '', text, flags=re.IGNORECASE).strip()
                                        city, found_postcode = self.cleaner.extract_location_from_text(text)
                                        if city:
                                            location = city
                                            postcode = found_postcode
                                            location_text = text
                                            break
                                
                                # If still no location, try to find it in the job description
                                if location == "Unknown":
                                    description_div = job_soup.find('div', {'id': 'job-profile'}) or job_soup.find('div', class_='govuk-body')
                                    if description_div:
                                        desc_text = description_div.get_text()
                                        # Look for location patterns in the first few paragraphs
                                        location_patterns = [
                                            r'(?:location|based|working)\s+(?:is|in|at|from)?\s*:?\s*([^\.]+)(?:\.|$)',
                                            r'position\s+(?:is\s+)?(?:located|based)\s+(?:in|at)\s+([^\.]+)(?:\.|$)',
                                            r'(?:office|workplace|site)\s+(?:is|in|at)\s+([^\.]+)(?:\.|$)',
                                            r'(?:location|area):\s*([^\.]+)(?:\.|$)'
                                        ]
                                        
                                        for pattern in location_patterns:
                                            if match := re.search(pattern, desc_text, re.IGNORECASE):
                                                text = match.group(1).strip()
                                                city, found_postcode = self.cleaner.extract_location_from_text(text)
                                                if city:
                                                    location = city
                                                    postcode = found_postcode
                                                    location_text = text
                                                    break
                            
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f'Could not fetch job details for location: {str(e)}'))
                        
                        # Try to find location in the title if we still don't have one
                        if location == "Unknown":
                            # Extract location from title using common patterns
                            title_location_patterns = [
                                r'\|\s*([^|]+(?:NHS Trust|Council|Borough))',  # Match org names that include location
                                r'(?:in|at)\s+([A-Za-z\s]+)(?:\s*,|\s*$)',    # Match "in/at Location"
                                r'-\s*([A-Za-z\s]+)(?:\s*,|\s*$)',            # Match "- Location"
                                r'\(([^)]+)\)',                               # Match location in parentheses
                            ]
                            
                            for pattern in title_location_patterns:
                                match = re.search(pattern, title)
                                if match:
                                    text = match.group(1).strip()
                                    city, found_postcode = self.cleaner.extract_location_from_text(text)
                                    if city:
                                        location = city
                                        postcode = found_postcode
                                        location_text = text
                                        break
                        
                        # If still no location and we have a search location, use that
                        if location == "Unknown" and self.search_location:
                            location = self.search_location.title()
                        
                        # Debug logging
                        if self.debug:
                            self.stdout.write(f"Location extraction:")
                            self.stdout.write(f"  - Title: {title}")
                            self.stdout.write(f"  - Raw location text: {location_text}")
                            if postcode:
                                self.stdout.write(f"  - Found postcode: {postcode}")
                            self.stdout.write(f"  - Final location: {location}")
                        
                        # Get or create employer
                        employer, _ = Employer.objects.get_or_create(
                            employer_name=employer_name
                        )
                        
                        # Process job URL
                        try:
                            job_response = requests.get(job_url, headers=headers)
                            job_soup = BeautifulSoup(job_response.text, 'html.parser')
                            
                            # Extract job description
                            description = ""
                            description_div = job_soup.find('div', {'id': 'job-profile'}) or job_soup.find('div', class_='govuk-body')
                            if description_div:
                                description = description_div.get_text(separator='\n', strip=True)
                            
                            # Extract job details using the cleaned text
                            job_details = self.cleaner.extract_job_details(description)
                            
                            time.sleep(random.uniform(0.5, 1.5))  # Be nice to the server
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'Could not fetch job details: {str(e)}'))
                            job_details = {}
                            description = ""
                        
                        # Get job mode from tags
                        job_mode = None
                        job_tags = job.find_all('li', class_='govuk-tag')
                        if job_tags:
                            job_mode = self.cleaner.extract_job_mode(str(job_tags))
                        
                        # If no job mode found in tags, try to determine from title/description
                        if not job_mode:
                            job_mode = self.cleaner.determine_job_mode(title, description)
                        
                        # Create job object
                        job_data = {
                            'employer': employer,
                            'title': title,
                            'description': description or job_details.get('description', ''),
                            'location': location,
                            'salary_range': salary,  # Use the extracted salary
                            'date_posted': datetime.now(),
                            'mode': job_mode or 'full_time',  # Default to full_time if not specified
                            'time_commitment': 'full_time',  # Default value
                            'source': job_url,
                            'application_url': job_url,
                            'opportunity_type': 'job',
                            # call function determine_experience_level
                            'experience_level': self.cleaner.determine_experience_level(
                                title,
                                job_details.get('description', '')
                            ),
                            'skills_required': job_details.get('skills_required', ''),  # Default to empty string
                            'skills_gained': '',  # Default to empty string
                            'expenses_paid': True,
                            'start_date': None,
                            'end_date': None
                        }
                        
                        # Try to determine job type from description and title
                        combined_text = (job_data['description'] + ' ' + job_data['title']).lower()
                        if 'part time' in combined_text or 'part-time' in combined_text:
                            job_data['time_commitment'] = 'part_time'
                        elif 'temporary' in combined_text or 'temp' in combined_text:
                            job_data['time_commitment'] = 'temporary'
                        elif 'occasional' in combined_text:
                            job_data['time_commitment'] = 'occasional'
                        else:
                            job_data['time_commitment'] = 'full_time'
                        
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
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing job: {str(e)}'))
                        logging.exception("Error processing job")
                        continue
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error scraping DWP Find a Job: {str(e)}'))
            logging.exception("Error in scrape_dwp")
