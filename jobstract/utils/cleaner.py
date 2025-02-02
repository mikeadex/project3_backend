import re
import logging
from bs4 import BeautifulSoup

class Cleaner:
    def __init__(self):
        # Initialize uk_cities set
        self.uk_cities = {
            'london', 'manchester', 'birmingham', 'leeds', 'glasgow', 'liverpool',
            'sheffield', 'bristol', 'newcastle', 'nottingham', 'cardiff', 'belfast',
            'leicester', 'edinburgh', 'reading', 'blackpool', 'oxford', 'cambridge',
            'plymouth', 'southampton', 'portsmouth', 'bradford', 'coventry', 'hull',
            'stoke', 'sunderland', 'brighton', 'norwich', 'derby', 'swansea',
            'middlesbrough', 'milton keynes', 'wolverhampton', 'aberdeen', 'dundee'
        }
        # Pre-compute lowercase and sorted versions
        self._uk_cities_lower = {city.lower() for city in self.uk_cities}
        self._uk_cities_sorted = sorted(self.uk_cities, key=len, reverse=True)

        # Compile regex patterns once for better performance
        self.SKILLS_PATTERNS = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in [
                r'(?:key skills|skills needed|skills required|essential skills|requirements)[:\s]+(.*?)(?=\n\n|\Z)',
                r'(?:you will need|you should have|you must have|we are looking for)[:\s]+(.*?)(?=\n\n|\Z)',
                r'(?:qualifications|experience)[:\s]+(.*?)(?=\n\n|\Z)',
            ]
        ]
        
        # UK Postcode regex (both full and outward code)
        self.POSTCODE_PATTERN = re.compile(
            r'([A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}|[A-Z]{1,2}[0-9][A-Z0-9]?)',
            re.IGNORECASE
        )
        
        # Mapping of postcode areas to cities/regions
        self.POSTCODE_AREAS = {
            'AB': 'Aberdeen', 'AL': 'St Albans', 'B': 'Birmingham', 'BA': 'Bath', 
            'BB': 'Blackburn', 'BD': 'Bradford', 'BH': 'Bournemouth', 'BL': 'Bolton',
            'BN': 'Brighton', 'BR': 'Bromley', 'BS': 'Bristol', 'BT': 'Belfast',
            'CA': 'Carlisle', 'CB': 'Cambridge', 'CF': 'Cardiff', 'CH': 'Chester',
            'CM': 'Chelmsford', 'CO': 'Colchester', 'CR': 'Croydon', 'CT': 'Canterbury',
            'CV': 'Coventry', 'CW': 'Crewe', 'DA': 'Dartford', 'DD': 'Dundee',
            'DE': 'Derby', 'DG': 'Dumfries', 'DH': 'Durham', 'DL': 'Darlington',
            'DN': 'Doncaster', 'DT': 'Dorchester', 'DY': 'Dudley', 'E': 'London',
            'EC': 'London', 'EH': 'Edinburgh', 'EN': 'Enfield', 'EX': 'Exeter',
            'FK': 'Falkirk', 'FY': 'Blackpool', 'G': 'Glasgow', 'GL': 'Gloucester',
            'GU': 'Guildford', 'HA': 'Harrow', 'HD': 'Huddersfield', 'HG': 'Harrogate',
            'HP': 'Hemel Hempstead', 'HR': 'Hereford', 'HS': 'Hebrides', 'HU': 'Hull',
            'HX': 'Halifax', 'IG': 'Ilford', 'IP': 'Ipswich', 'IV': 'Inverness',
            'KA': 'Kilmarnock', 'KT': 'Kingston upon Thames', 'KW': 'Kirkwall',
            'KY': 'Kirkcaldy', 'L': 'Liverpool', 'LA': 'Lancaster', 'LD': 'Llandrindod Wells',
            'LE': 'Leicester', 'LL': 'Llandudno', 'LN': 'Lincoln', 'LS': 'Leeds',
            'LU': 'Luton', 'M': 'Manchester', 'ME': 'Medway', 'MK': 'Milton Keynes',
            'ML': 'Motherwell', 'N': 'London', 'NE': 'Newcastle upon Tyne',
            'NG': 'Nottingham', 'NN': 'Northampton', 'NP': 'Newport', 'NR': 'Norwich',
            'NW': 'London', 'OL': 'Oldham', 'OX': 'Oxford', 'PA': 'Paisley',
            'PE': 'Peterborough', 'PH': 'Perth', 'PL': 'Plymouth', 'PO': 'Portsmouth',
            'PR': 'Preston', 'RG': 'Reading', 'RH': 'Redhill', 'RM': 'Romford',
            'S': 'Sheffield', 'SA': 'Swansea', 'SE': 'London', 'SG': 'Stevenage',
            'SK': 'Stockport', 'SL': 'Slough', 'SM': 'Sutton', 'SN': 'Swindon',
            'SO': 'Southampton', 'SP': 'Salisbury', 'SR': 'Sunderland', 'SS': 'Southend-on-Sea',
            'ST': 'Stoke-on-Trent', 'SW': 'London', 'SY': 'Shrewsbury', 'TA': 'Taunton',
            'TD': 'Galashiels', 'TF': 'Telford', 'TN': 'Tonbridge', 'TQ': 'Torquay',
            'TR': 'Truro', 'TS': 'Cleveland', 'TW': 'Twickenham', 'UB': 'Southall',
            'W': 'London', 'WA': 'Warrington', 'WC': 'London', 'WD': 'Watford',
            'WF': 'Wakefield', 'WN': 'Wigan', 'WR': 'Worcester', 'WS': 'Walsall',
            'WV': 'Wolverhampton', 'YO': 'York', 'ZE': 'Lerwick'
        }
        
        self.LOCATION_CLEANERS = [
            (re.compile(r'\s*,\s*$'), ''),  # Remove trailing comma
            (re.compile(r'^(?:location|based in|in|at|near)\s*:?\s*', re.IGNORECASE), ''),  # Remove common prefixes
            (re.compile(r'\s*(?:area|region|county|district)$', re.IGNORECASE), ''),  # Remove common suffixes
            (re.compile(r'\s+'), ' '),  # Normalize spaces
        ]
        self.LOCATION_PREFIX_PATTERN = re.compile(r'^(?:location|based in|in|at|near)\s*:?\s*', re.IGNORECASE)
        self.LOCATION_SUFFIX_PATTERN = re.compile(r'\s*(?:area|region|county|district)$', re.IGNORECASE)
        self.LOCATION_SPLIT_PATTERN = re.compile(r'[,\-/]|\s+(?:and|or)\s+|\s+')
        self.NOISE_WORDS = {
            'uk', 'united', 'kingdom', 'england', 'wales', 'scotland', 
            'northern', 'ireland', 'greater', 'city', 'county', 'area',
            'north', 'south', 'east', 'west', 'central', 'town', 'village',
            'borough', 'district', 'region', 'metropolitan'
        }
        self.SENIOR_INDICATORS = {
            'senior', 'lead', 'head', 'director', 'chief', 'principal', 'manager',
            'architect', 'staff', 'expert', 'specialist', 'vp', 'vice president',
            'executive', 'tech lead', 'team lead'
        }
        self.MID_LEVEL_INDICATORS = {
            'mid', 'intermediate', 'experienced', 'mid-level', 'associate',
            'professional', 'qualified', '3+ years', '4+ years', '5+ years'
        }
        self.JUNIOR_INDICATORS = {
            'junior', 'entry', 'graduate', 'trainee', 'apprentice', 'intern',
            'entry-level', 'fresh', 'beginner', 'student', 'new grad',
            '0-2 years', '1-2 years', 'no experience'
        }
        self.SALARY_PATTERNS = [
            # Pattern for salary ranges with period
            re.compile(r'Salary:?\s*(£[\d,.]+(?:\.\d{2})?\s*(?:to|-)\s*£?[\d,.]+(?:\.\d{2})?\s*(?:per|a|p\.a\.|/|p/h|p/d)?\s*(?:year|annum|month|hour|hr|p/h|day|diem)?)', re.IGNORECASE),
            # Pattern for single salaries with period
            re.compile(r'Salary:?\s*(£[\d,.]+(?:\.\d{2})?\s*(?:per|a|p\.a\.|/|p/h|p/d)?\s*(?:year|annum|month|hour|hr|p/h|day|diem)?)', re.IGNORECASE),
            # Pattern for daily rates
            re.compile(r'(£[\d,.]+(?:\.\d{2})?\s*(?:per|a|/|p/d)?\s*(?:day|diem|daily))', re.IGNORECASE),
            re.compile(r'(£[\d,.]+(?:\.\d{2})?\s*(?:day\s*rate|daily\s*rate))', re.IGNORECASE),
            # Pattern for any text containing salary info
            re.compile(r'Salary:?\s*([^\n]+(?:per|a|p\.a\.|/|p/h|p/d)\s*(?:year|annum|month|hour|hr|p/h|day|diem))', re.IGNORECASE),
        ]
        self.DESCRIPTION_SECTIONS = [
            ('Job description', re.compile(r'Job description:?\s*(.+?)(?=Requirements|Skills|About|Benefits|Apply|$)', re.DOTALL | re.IGNORECASE)),
            ('Requirements', re.compile(r'Requirements:?\s*(.+?)(?=About|Benefits|Apply|$)', re.DOTALL | re.IGNORECASE)),
            ('Skills', re.compile(r'Skills:?\s*(.+?)(?=About|Benefits|Apply|$)', re.DOTALL | re.IGNORECASE)),
            ('Benefits', re.compile(r'Benefits:?\s*(.+?)(?=About|Apply|$)', re.DOTALL | re.IGNORECASE)),
        ]

    def clean_text(self, text):
        """
        Clean a text by removing special characters and converting to lowercase.
        
        Args:
            text (str): The text to be cleaned
        
        Returns:
            str: The cleaned text
        """
        if not text:
            return ""
            
        # Remove html tags using REGEX
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Replace literal \n with actual newlines
        text = text.replace('\\n', '\n')
        
        # Replace multiple newlines with a single newline
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Clean HTML entities
        html_entities = {
            '&nbsp;': ' ',
            '\\nbsp': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
        
        return text.strip()

    def clean_location(self, location_text, town=None):
        """
        Clean and format location text.
        
        Args:
            location_text (str): Raw location text to clean
            town (str, optional): Fallback town name if location is invalid
            
        Returns:
            str: Cleaned location or "Unknown" if invalid
        """
        if not location_text:
            return "Unknown"
        
        # Initial cleaning
        location = location_text.strip()
        
        # Return town or Unknown for postcodes
        if self.POSTCODE_PATTERN.match(location):
            return town if town else "Unknown"
        
        # Apply all cleaning rules
        for pattern, replacement in self.LOCATION_CLEANERS:
            location = pattern.sub(replacement, location)
        
        # Additional validation
        if len(location) < 2 or location.lower() in {'uk', 'gb', 'united kingdom', 'great britain'}:
            return town if town else "Unknown"
            
        return location.strip()

    def extract_location(self, location_text):
        """
        Extract city from location text, filtering out postcodes and noise words.
        
        Args:
            location_text (str): Raw location text to process
            
        Returns:
            str: Extracted city name or "Unknown" if no valid city found
        """
        if not location_text:
            return "Unknown"
        
        # Convert to lowercase once
        location_text = location_text.lower()
        
        # Apply prefix and suffix cleaning
        location_text = self.LOCATION_PREFIX_PATTERN.sub('', location_text)
        location_text = self.LOCATION_SUFFIX_PATTERN.sub('', location_text)
        
        # Split and clean parts
        parts = []
        for part in self.LOCATION_SPLIT_PATTERN.split(location_text):
            part = part.strip(' .,()-/')
            if part and not self.POSTCODE_PATTERN.match(part) and part not in self.NOISE_WORDS:
                parts.append(part)
        
        # Try exact matches first (O(1) lookup with set)
        for part in parts:
            if part in self._uk_cities_lower:
                return part.title()
        
        # Try partial matches with original text
        for city in self._uk_cities_sorted:
            if city.lower() in location_text:
                return city.title()
        
        # Return first valid part if no city match
        return parts[0].title() if parts else "Unknown"

    def extract_location_from_text(self, text):
        """
        Extract location from text, handling postcodes and converting them to city names.
        
        Args:
            text (str): Text to extract location from
            
        Returns:
            tuple: (location, postcode) or (None, None) if not found
        """
        if not text:
            return None, None
            
        # Clean HTML tags and normalize text
        text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags
        text = re.sub(r'\s+', ' ', text)      # Normalize whitespace
        text = text.strip()
        
        # First try to find a postcode - prioritize full postcodes
        postcode_matches = list(self.POSTCODE_PATTERN.finditer(text))
        for match in postcode_matches:
            postcode = match.group(1).strip().upper()
            # Try full postcode first
            if ' ' in postcode or len(postcode) > 4:
                area_code = postcode[:2].upper()
                if area_code in self.POSTCODE_AREAS:
                    return self.POSTCODE_AREAS[area_code], postcode
            
            # Then try outward code
            area_code = postcode[:2].upper()
            if area_code in self.POSTCODE_AREAS:
                return self.POSTCODE_AREAS[area_code], postcode
            
            # Handle single letter postcodes
            area_code = postcode[0].upper()
            if area_code in self.POSTCODE_AREAS:
                return self.POSTCODE_AREAS[area_code], postcode
        
        # If no postcode found, try to find a city name
        text_lower = text.lower()
        
        # First check for exact city matches
        text_parts = re.split(r'[,\s]+', text_lower)
        for part in text_parts:
            part = part.strip(' .,()-/')
            if part in self._uk_cities_lower:
                return part.title(), None
        
        # Then try partial matches
        for city in self._uk_cities_sorted:
            if city.lower() in text_lower:
                return city.title(), None
        
        # If we have a county name in the text, try to map it to a major city
        counties = {
            'suffolk': 'Ipswich',
            'norfolk': 'Norwich',
            'essex': 'Chelmsford',
            'kent': 'Maidstone',
            'surrey': 'Guildford',
            'sussex': 'Brighton',
            'hampshire': 'Winchester',
            'devon': 'Exeter',
            'cornwall': 'Truro',
            'wiltshire': 'Salisbury',
            'dorset': 'Dorchester',
            'somerset': 'Taunton',
            'gloucestershire': 'Gloucester',
            'oxfordshire': 'Oxford',
            'berkshire': 'Reading',
            'buckinghamshire': 'Aylesbury',
            'hertfordshire': 'Hertford',
            'bedfordshire': 'Bedford',
            'cambridgeshire': 'Cambridge',
            'northamptonshire': 'Northampton',
            'warwickshire': 'Warwick',
            'worcestershire': 'Worcester',
            'herefordshire': 'Hereford',
            'shropshire': 'Shrewsbury',
            'staffordshire': 'Stafford',
            'derbyshire': 'Derby',
            'nottinghamshire': 'Nottingham',
            'lincolnshire': 'Lincoln',
            'leicestershire': 'Leicester',
            'rutland': 'Oakham',
            'yorkshire': 'York'
        }
        
        for county, city in counties.items():
            if county in text_lower:
                return city, None
                
        return None, None

    def determine_experience_level(self, title, description):
        """
        Determine experience level based on job title and description.
        
        Args:
            title (str): Job title
            description (str): Job description, can be None
            
        Returns:
            str: Experience level ('senior', 'mid_level', 'junior', or 'not_specified')
        """
        # Handle None values
        if not title:
            return 'not_specified'
        
        # Convert to lowercase once and combine texts
        title_lower = title.lower()
        desc_lower = description.lower() if description else ""
        
        # Use regex to extract years of experience if present
        years_match = re.search(r'(\d+)\+?\s*(?:year|yr)s?(?:\s+experience)?', desc_lower)
        if years_match:
            years = int(years_match.group(1))
            if years >= 5:
                return 'senior'
            elif years >= 2:
                return 'mid_level'
            else:
                return 'junior'
        
        # Check for experience level indicators in both title and description
        combined_text = f"{title_lower} {desc_lower}"
        
        # Use generator expressions for short-circuit evaluation
        if any(indicator in combined_text for indicator in self.SENIOR_INDICATORS):
            return 'senior'
        
        if any(indicator in combined_text for indicator in self.MID_LEVEL_INDICATORS):
            return 'mid_level'
        
        if any(indicator in combined_text for indicator in self.JUNIOR_INDICATORS):
            return 'junior'
        
        return 'not_specified'

    def determine_job_mode(self, title, description):
        """
        Determine job mode (remote, onsite, hybrid) based on job title and description.
        
        Args:
            title (str): Job title
            description (str): Job description
            
        Returns:
            str: Job mode ('remote', 'onsite', 'hybrid', or 'both')
        """
        text = f"{title} {description}".lower()
        
        # Remote indicators
        remote_indicators = {
            'remote', 'work from home', 'wfh', 'virtual', 'telecommute', 'telework',
            'home based', 'home-based', 'working from home', 'remote-first',
            'fully remote', '100% remote', 'remote working', 'remote work'
        }
        
        # Onsite indicators
        onsite_indicators = {
            'onsite', 'on-site', 'on site', 'in office', 'in-office', 'office based',
            'office-based', 'on location', 'on-location', 'in person', 'in-person',
            'physical presence', 'must be present', 'must attend', 'site based'
        }
        
        # Hybrid indicators
        hybrid_indicators = {
            'hybrid', 'flexible', 'mix of remote', 'mix of office', 'partially remote',
            'part remote', 'remote/office', 'office/remote', 'work from home/office',
            'split between', 'combination of', 'blend of', '2-3 days', '3-2 days',
            'days per week in office', 'days a week in office'
        }
        
        # Check for explicit indicators
        is_remote = any(indicator in text for indicator in remote_indicators)
        is_onsite = any(indicator in text for indicator in onsite_indicators)
        is_hybrid = any(indicator in text for indicator in hybrid_indicators)
        
        if is_hybrid or (is_remote and is_onsite):
            return 'hybrid'
        elif is_remote:
            return 'remote'
        elif is_onsite:
            return 'onsite'
        
        return 'both'  # Default if no clear indicators found

    def extract_job_details(self, text, raw_html=None):
        """
        Extract detailed job information from job description text.
        
        Args:
            text (str): Job description text
            raw_html (str, optional): Raw HTML for debugging purposes
            
        Returns:
            dict: Dictionary containing extracted job details
        """
        details = {}
        
        try:
            if not text or not isinstance(text, str):
                logging.warning("Invalid text input for extract_job_details")
                return details
            
            # Extract skills using compiled patterns
            for pattern in self.SKILLS_PATTERNS:
                if skills_match := pattern.search(text):
                    details['skills_required'] = self.clean_text(skills_match.group(1))
                    break
            
            # If no skills found, try to extract from bullet points
            if 'skills_required' not in details:
                # Look for bullet points after common headers
                skills_headers = ['required skills', 'skills required', 'essential skills', 'requirements']
                text_lower = text.lower()
                
                for header in skills_headers:
                    if header in text_lower:
                        start_idx = text_lower.index(header) + len(header)
                        # Find the end of the skills section (next double newline)
                        end_idx = text_lower.find('\n\n', start_idx)
                        if end_idx == -1:
                            end_idx = len(text_lower)
                        
                        skills_section = text[start_idx:end_idx].strip()
                        if skills_section:
                            details['skills_required'] = skills_section
                            break
            
            # Extract salary using compiled patterns
            for pattern in self.SALARY_PATTERNS:
                if salary_match := pattern.search(text):
                    salary = salary_match.group(1).strip()
                    # Clean up salary format
                    salary = re.sub(r'\s+per\s*$', '', salary)
                    if re.search(r'day|diem|daily', salary, re.IGNORECASE) and 'per' not in salary.lower():
                        salary = re.sub(r'(£[\d,.]+(?:\.\d{2})?)\s*(?:day|diem|daily)', 
                                     r'\1 per day', salary, flags=re.IGNORECASE)
                    details['salary'] = salary
                    break
            
            # Extract description sections
            description_parts = []
            for section_name, pattern in self.DESCRIPTION_SECTIONS:
                if match := pattern.search(text):
                    if section_text := self.clean_text(match.group(1)):
                        description_parts.append(f"{section_name}:\n{section_text}")
            
            if description_parts:
                details['description'] = '\n\n'.join(description_parts)
            else:
                details['description'] = self.clean_text(text)
        
        except Exception as e:
            logging.exception("Error in extract_job_details")
            logging.warning(f'Error extracting job details: {str(e)}')
        
        return details

    def extract_salary(self, text):
        """
        Extract salary information from text, handling both HTML and plain text.
        
        Args:
            text (str): Text containing salary information
            
        Returns:
            str: Formatted salary string or "Not specified"
        """
        if not text:
            return "Not specified"
            
        # Clean HTML tags and normalize text
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Common salary patterns
        salary_patterns = [
            # Hourly rate (e.g. "£15 per hour", "£12.50/hour", "£11.50 p/h")
            r'£([\d,]+(?:\.\d{2})?)\s*(?:per|an?|/|p/h|ph|p\.h\.|per\s+hr)\s*(?:hour|hr|h|p/h|ph)',
            # Daily rate (e.g. "£300 per day", "£250/day")
            r'£([\d,]+(?:\.\d{2})?)\s*(?:per|an?|/|p/d|pd|p\.d\.|per)\s*(?:day|diem|daily|d)',
            # Range with period (e.g. "£30,000 to £40,000 per year", "£30k-£40k per annum")
            r'£([\d,k]+(?:\.\d{2})?)\s*(?:to|-)\s*£?([\d,k]+(?:\.\d{2})?)\s*(?:per|an?|p\.a\.|pa|/|p/h|p/d)?\s*(?:year|annum|pa|p\.a\.|month|hour|hr|h|p/h|day|d|week|wk|w)',
            # Single value with period (e.g. "£35,000 per annum", "£35k p.a.")
            r'£([\d,k]+(?:\.\d{2})?)\s*(?:per|an?|p\.a\.|pa|/|p/h|p/d)?\s*(?:year|annum|pa|p\.a\.|month|hour|hr|h|p/h|day|d|week|wk|w)',
        ]
        
        def convert_to_number(value):
            """Convert salary string to number, handling k suffix"""
            value = value.replace(',', '')
            if 'k' in value.lower():
                value = float(value.lower().replace('k', '')) * 1000
            return float(value)
        
        def is_reasonable_salary(amount, period):
            """Check if salary amount is reasonable for the given period"""
            if period in ['hour', 'hr', 'h', 'p/h', 'ph']:
                return 5 <= amount <= 200  # £5 to £200 per hour
            elif period in ['day', 'diem', 'd', 'daily']:
                return 40 <= amount <= 2000  # £40 to £2000 per day
            elif period in ['week', 'wk', 'w']:
                return 200 <= amount <= 10000  # £200 to £10000 per week
            elif period in ['month']:
                return 800 <= amount <= 50000  # £800 to £50000 per month
            else:  # year/annum
                return 10000 <= amount <= 500000  # £10k to £500k per year
        
        for pattern in salary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                # Find the period (hour/day/week/month/year)
                period_match = re.search(r'(?:per|an?|p\.a\.|pa|/|p/h|p/d)?\s*(year|annum|pa|p\.a\.|month|hour|hr|h|p/h|day|d|week|wk|w)', text, re.IGNORECASE)
                period = period_match.group(1).lower() if period_match else 'year'
                
                # Normalize period
                if period in ['annum', 'pa', 'p.a.', 'year']:
                    period = 'year'
                elif period in ['hr', 'h', 'p/h', 'ph']:
                    period = 'hour'
                elif period in ['d', 'diem']:
                    period = 'day'
                elif period in ['wk', 'w']:
                    period = 'week'
                
                if len(groups) == 2:  # Salary range
                    min_salary = convert_to_number(groups[0])
                    max_salary = convert_to_number(groups[1])
                    
                    # Check if the range is reasonable for the period
                    if not is_reasonable_salary(min_salary, period) or not is_reasonable_salary(max_salary, period):
                        continue
                    
                    # Convert to yearly if needed
                    if period == 'hour':
                        min_yearly = min_salary * 37.5 * 52
                        max_yearly = max_salary * 37.5 * 52
                        return f"£{min_salary:.2f} to £{max_salary:.2f} per hour (£{int(min_yearly):,} to £{int(max_yearly):,} per year)"
                    elif period == 'day':
                        min_yearly = min_salary * 260
                        max_yearly = max_salary * 260
                        return f"£{int(min_salary):,} to £{int(max_salary):,} per day (£{int(min_yearly):,} to £{int(max_yearly):,} per year)"
                    elif period == 'week':
                        min_yearly = min_salary * 52
                        max_yearly = max_salary * 52
                        return f"£{int(min_salary):,} to £{int(max_salary):,} per week (£{int(min_yearly):,} to £{int(max_yearly):,} per year)"
                    elif period == 'month':
                        min_yearly = min_salary * 12
                        max_yearly = max_salary * 12
                        return f"£{int(min_salary):,} to £{int(max_salary):,} per month (£{int(min_yearly):,} to £{int(max_yearly):,} per year)"
                    else:  # year
                        if min_salary == max_salary:
                            return f"£{int(min_salary):,} per year"
                        return f"£{int(min_salary):,} to £{int(max_salary):,} per year"
                        
                elif len(groups) == 1:  # Single salary
                    salary = convert_to_number(groups[0])
                    
                    # Check if the salary is reasonable for the period
                    if not is_reasonable_salary(salary, period):
                        continue
                    
                    # Convert to yearly equivalent
                    if period == 'hour':
                        yearly = salary * 37.5 * 52  # Assuming 37.5 hour week
                        return f"£{salary:.2f} per hour (£{int(yearly):,} per year)"
                    elif period == 'day':
                        yearly = salary * 260  # Assuming 260 working days
                        return f"£{int(salary):,} per day (£{int(yearly):,} per year)"
                    elif period == 'week':
                        yearly = salary * 52
                        return f"£{int(salary):,} per week (£{int(yearly):,} per year)"
                    elif period == 'month':
                        yearly = salary * 12
                        return f"£{int(salary):,} per month (£{int(yearly):,} per year)"
                    else:  # year
                        return f"£{int(salary):,} per year"
                        
        return "Not specified"

    def extract_job_mode(self, html_content):
        """
        Extract job mode (full time, part time, etc.) from HTML content.
        
        Args:
            html_content (str): HTML content containing job mode tags
            
        Returns:
            str: Job mode (full_time, part_time, etc.) or None if not found
        """
        if not html_content:
            return None
            
        # Try to find job mode in govuk tags
        soup = BeautifulSoup(html_content, 'html.parser')
        mode_tags = soup.find_all('li', class_='govuk-tag')
        
        for tag in mode_tags:
            text = tag.get_text(strip=True).lower()
            # Map common job mode texts to standardized values
            if 'full time' in text or 'full-time' in text:
                return 'full_time'
            elif 'part time' in text or 'part-time' in text:
                return 'part_time'
            elif 'permanent' in text:
                return 'permanent'
            elif 'temporary' in text or 'temp' in text:
                return 'temporary'
            elif 'contract' in text:
                return 'contract'
            elif 'freelance' in text:
                return 'freelance'
            elif 'internship' in text:
                return 'internship'
            elif 'apprenticeship' in text:
                return 'apprenticeship'
                
        return None
