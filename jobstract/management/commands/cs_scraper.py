import re
import json
import time
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

# Import Selenium libraries
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Base URL and starting URL for job listings.
# Note: You might need to update START_URL to point directly to the search results page
# if the homepage does not directly list jobs.
BASE_URL = "https://www.civilservicejobs.service.gov.uk"
START_URL = BASE_URL + "/"  # Consider changing this if a more specific URL exists

def clean_text(text):
    """
    Cleans and formats a text string:
    - Replaces multiple whitespace characters with a single space.
    - Strips leading and trailing spaces.
    """
    if text:
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    return ""

def extract_job_data(job_element):
    """
    Extracts and cleans job fields from a job listing element.
    
    Expected fields (adjust based on the actual HTML):
    - Title (from an <a> element with a class like "job-title")
    - Location (from a <span> with class "job-location")
    - Posted Date (from a <span> with class "job-posted-date")
    - Reference (from a <span> with class "job-reference")
    """
    # Extract title
    title_tag = job_element.find("a", class_="job-title")
    title = clean_text(title_tag.get_text()) if title_tag else "N/A"

    # Extract location
    location_tag = job_element.find("span", class_="job-location")
    location = clean_text(location_tag.get_text()) if location_tag else "N/A"

    # Extract posted date
    date_tag = job_element.find("span", class_="job-posted-date")
    posted_date = clean_text(date_tag.get_text()) if date_tag else "N/A"

    # Extract job reference
    reference_tag = job_element.find("span", class_="job-reference")
    reference = clean_text(reference_tag.get_text()) if reference_tag else "N/A"

    return {
        "title": title,
        "location": location,
        "posted_date": posted_date,
        "reference": reference
    }

def crawl_jobs():
    """
    Crawls job listing pages using Selenium to execute JavaScript, then extracts job data.
    Returns a list of dictionaries representing each job.
    """
    jobs = []

    # Configure Selenium to use headless Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Initialize the Selenium WebDriver (ensure ChromeDriver is installed and in PATH)
    driver = webdriver.Chrome(options=chrome_options)

    page_url = START_URL
    while page_url:
        print(f"Crawling page: {page_url}")
        driver.get(page_url)
        
        # Wait for the page to load and JavaScript to render content
        time.sleep(3)
        
        # Parse the rendered page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Adjust the CSS selector based on the actual structure of job listings.
        # The example below looks for <div class="job-result"> elements.
        job_elements = soup.find_all("div", class_="job-result")
        if not job_elements:
            print("No job listings found on this page.")
            break

        for job in job_elements:
            job_data = extract_job_data(job)
            jobs.append(job_data)

        # Find the pagination link for "Next" page.
        next_link = soup.find("a", string=re.compile(r"Next", re.IGNORECASE))
        if next_link and next_link.get("href"):
            # Build the absolute URL if the href is relative.
            page_url = BASE_URL + next_link["href"]
            time.sleep(1)  # Be polite and wait a moment before the next request.
        else:
            page_url = None

    driver.quit()
    return jobs

class Command(BaseCommand):
    help = "Scrapes job listings from the Civil Service Jobs website using Selenium."

    def handle(self, *args, **options):
        self.stdout.write("Starting the job scraping process using Selenium...")
        job_listings = crawl_jobs()

        output_file = "job_listings.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(job_listings, f, ensure_ascii=False, indent=4)

        self.stdout.write(f"Extraction complete. {len(job_listings)} job listings saved to {output_file}")
