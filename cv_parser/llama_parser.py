"""
LLaMA-based CV Parser - Reliable and Simple
Built to replace the broken DeepSeek/traditional parsing system
"""

import json
import logging
import re
from typing import Dict, Any, List
from cv_writer.services import CVImprovementService

logger = logging.getLogger('cv_parser')


class LLaMAcvParser:
    """Simple, reliable CV parser using LLaMA API"""
    
    def __init__(self):
        """Initialize LLaMA parser"""
        self.llama_service = None
        try:
            # Use the existing CV improvement service which has LLaMA
            cv_service = CVImprovementService()
            self.llama_service = cv_service.llama_service
            logger.info("LLaMA CV parser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLaMA service: {e}")
            self.llama_service = None
    
    def parse_cv(self, cv_text: str) -> Dict[str, Any]:
        """
        Parse CV text using LLaMA API
        
        Args:
            cv_text: Raw CV text content
            
        Returns:
            Structured CV data dictionary
        """
        if not self.llama_service:
            logger.error("LLaMA service not available")
            return self._empty_result()
        
        try:
            # Create a focused prompt for CV parsing
            prompt = self._create_parsing_prompt(cv_text)
            
            # Get response from LLaMA using async method
            import asyncio
            
            # Create system and user prompts
            system_prompt = "You are a CV parsing expert. Extract structured information from CVs and return only valid JSON."
            user_prompt = prompt
            
            # Call LLaMA API asynchronously
            try:
                loop = asyncio.get_event_loop()
                response = loop.run_until_complete(
                    self.llama_service.generate_with_system_prompt(system_prompt, user_prompt, timeout=60)
                )
            except RuntimeError:
                # If no event loop exists, create one
                response = asyncio.run(
                    self.llama_service.generate_with_system_prompt(system_prompt, user_prompt, timeout=60)
                )
            
            if not response:
                logger.error("Empty response from LLaMA API")
                return self._fallback_parse(cv_text)
            
            # Parse JSON response
            try:
                parsed_data = json.loads(response)
                logger.info("Successfully parsed CV with LLaMA")
                return self._validate_and_clean(parsed_data)
            except json.JSONDecodeError:
                logger.warning("LLaMA response not valid JSON, trying to extract JSON")
                return self._extract_json_from_response(response, cv_text)
                
        except Exception as e:
            logger.error(f"LLaMA parsing failed: {e}")
            return self._fallback_parse(cv_text)
    
    def _create_parsing_prompt(self, cv_text: str) -> str:
        """Create an optimized prompt for LLaMA CV parsing"""
        return f"""Extract structured information from this CV text and return ONLY a valid JSON object.

CV TEXT:
{cv_text}

Return ONLY this JSON structure with NO additional text:
{{
  "personal_info": {{
    "first_name": "extracted first name",
    "last_name": "extracted last name", 
    "email": "extracted email address",
    "phone": "extracted phone number",
    "location": "extracted location/address",
    "linkedin": "extracted LinkedIn URL if present"
  }},
  "professional_summary": "extract the professional summary or profile section",
  "experience": [
    {{
      "job_title": "exact job title",
      "company": "company name", 
      "start_date": "start date",
      "end_date": "end date or Present",
      "description": "job description and achievements"
    }}
  ],
  "education": [
    {{
      "degree": "degree name",
      "school": "institution name",
      "field": "field of study",
      "start_date": "start year",
      "end_date": "end year"
    }}
  ],
  "skills": [
    {{
      "name": "skill name",
      "level": "Beginner/Intermediate/Advanced/Expert"
    }}
  ],
  "certifications": [
    {{
      "name": "certification name",
      "issuer": "issuing organization",
      "date": "issue date"
    }}
  ],
  "languages": [
    {{
      "language": "language name", 
      "level": "proficiency level"
    }}
  ]
}}

IMPORTANT: Return ONLY the JSON object, no explanations, no markdown formatting."""

    def _extract_json_from_response(self, response: str, cv_text: str) -> Dict[str, Any]:
        """Extract JSON from LLaMA response that might have extra text"""
        try:
            # Try to find JSON in the response
            json_patterns = [
                r'\{.*\}',  # Simple JSON pattern
                r'```json\s*(\{.*?\})\s*```',  # Markdown code block
                r'```\s*(\{.*?\})\s*```',  # Code block without json
            ]
            
            for pattern in json_patterns:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    json_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    try:
                        parsed_data = json.loads(json_str)
                        logger.info("Extracted JSON from LLaMA response")
                        return self._validate_and_clean(parsed_data)
                    except json.JSONDecodeError:
                        continue
            
            logger.warning("Could not extract valid JSON from LLaMA response")
            return self._fallback_parse(cv_text)
            
        except Exception as e:
            logger.error(f"Error extracting JSON: {e}")
            return self._fallback_parse(cv_text)
    
    def _validate_and_clean(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean the parsed data"""
        if not isinstance(parsed_data, dict):
            logger.warning("Parsed data is not a dictionary")
            return self._empty_result()
        
        # Ensure all required keys exist
        result = {
            "personal_info": parsed_data.get("personal_info", {}),
            "professional_summary": parsed_data.get("professional_summary", ""),
            "experience": parsed_data.get("experience", []),
            "education": parsed_data.get("education", []),
            "skills": parsed_data.get("skills", []),
            "certifications": parsed_data.get("certifications", []),
            "languages": parsed_data.get("languages", []),
            "projects": parsed_data.get("projects", []),
            "interests": parsed_data.get("interests", [])
        }
        
        # Validate personal_info structure
        if not isinstance(result["personal_info"], dict):
            result["personal_info"] = {}
        
        personal_info = result["personal_info"]
        personal_info.setdefault("first_name", "")
        personal_info.setdefault("last_name", "")
        personal_info.setdefault("email", "")
        personal_info.setdefault("phone", "")
        personal_info.setdefault("location", "")
        personal_info.setdefault("linkedin", "")
        
        # Ensure arrays are actually arrays
        for key in ["experience", "education", "skills", "certifications", "languages", "projects", "interests"]:
            if not isinstance(result[key], list):
                result[key] = []
        
        logger.info(f"Validated CV data: {len(result['experience'])} experience, {len(result['skills'])} skills, {len(result['education'])} education")
        return result
    
    def _fallback_parse(self, cv_text: str) -> Dict[str, Any]:
        """Simple fallback parsing using basic patterns"""
        logger.info("Using fallback parsing with basic patterns")
        
        result = self._empty_result()
        
        # Enhanced email extraction - search entire CV
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'email\s*:?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
            r'e-mail\s*:?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
        ]
        for pattern in email_patterns:
            email_match = re.search(pattern, cv_text, re.IGNORECASE)
            if email_match:
                email = email_match.group(1) if email_match.groups() else email_match.group(0)
                result["personal_info"]["email"] = email
                logger.info(f"Extracted email: {email}")
                break
        
        # Enhanced phone extraction - search entire CV with comprehensive patterns
        phone_patterns = [
            r'(?:phone|tel|mobile|cell)\s*:?\s*(\+?[\d\s\-\(\)]{10,15})',  # With label
            r'\+44\s?[\d\s\-]{10,}',  # UK format
            r'\+1\s?[\d\s\-\(\)]{10,}',  # US format  
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Standard format
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (xxx) xxx-xxxx
            r'\b\d{4}\s?\d{3}\s?\d{3}\b',  # UK mobile format
            r'\b07\d{3}\s?\d{6}\b',  # UK mobile starting with 07
            r'\+\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}'  # International
        ]
        for pattern in phone_patterns:
            phone_match = re.search(pattern, cv_text, re.IGNORECASE)
            if phone_match:
                phone_number = phone_match.group(1) if phone_match.groups() else phone_match.group(0)
                # Clean up the phone number
                clean_phone = re.sub(r'[^\d\+\-\(\)\s]', '', phone_number).strip()
                if len(clean_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) >= 10:  # Valid phone length
                    result["personal_info"]["phone"] = clean_phone
                    logger.info(f"Extracted phone: {clean_phone}")
                    break
        
        # Enhanced name extraction - search entire CV systematically
        lines = cv_text.split('\n')
        
        # Strategy 1: Look for CONTACT section or similar headers
        for i, line in enumerate(lines):
            line = line.strip()
            if line.upper() in ['CONTACT', 'CONTACT DETAILS', 'PERSONAL DETAILS', 'CONTACT INFORMATION']:
                # Check the next few lines after CONTACT header
                for j in range(i + 1, min(i + 6, len(lines))):
                    candidate_line = lines[j].strip()
                    if candidate_line and self._is_likely_name(candidate_line):
                        parts = candidate_line.split()
                        result["personal_info"]["first_name"] = parts[0]
                        result["personal_info"]["last_name"] = ' '.join(parts[1:])
                        logger.info(f"Extracted name from CONTACT section: {result['personal_info']['first_name']} {result['personal_info']['last_name']}")
                        break
                if result["personal_info"]["first_name"]:
                    break
        
        # Strategy 2: Look at the very beginning (before any section headers)
        if not result["personal_info"]["first_name"]:
            for i, line in enumerate(lines[:10]):
                line = line.strip()
                # Stop if we hit a section header
                if line.upper() in ['PROFILE', 'SUMMARY', 'EXPERIENCE', 'EDUCATION', 'SKILLS', 'CV', 'RESUME', 'CONTACT', 'OBJECTIVE']:
                    break
                
                if line and self._is_likely_name(line):
                    parts = line.split()
                    result["personal_info"]["first_name"] = parts[0]
                    result["personal_info"]["last_name"] = ' '.join(parts[1:])
                    logger.info(f"Extracted name from beginning: {result['personal_info']['first_name']} {result['personal_info']['last_name']}")
                    break
        
        # Strategy 3: Look for names near contact information
        if not result["personal_info"]["first_name"]:
            for i, line in enumerate(lines):
                line = line.strip()
                # If this line has contact info, check nearby lines for names
                if '@' in line or any(pattern in line for pattern in ['+44', '+1', '07', 'phone', 'mobile', 'tel']):
                    # Check lines before and after
                    for offset in [-2, -1, 1, 2]:
                        check_index = i + offset
                        if 0 <= check_index < len(lines):
                            candidate_line = lines[check_index].strip()
                            if candidate_line and self._is_likely_name(candidate_line):
                                parts = candidate_line.split()
                                result["personal_info"]["first_name"] = parts[0]
                                result["personal_info"]["last_name"] = ' '.join(parts[1:])
                                logger.info(f"Extracted name near contact info: {result['personal_info']['first_name']} {result['personal_info']['last_name']}")
                                break
                    if result["personal_info"]["first_name"]:
                        break
        
        # Extract professional summary (look for PROFILE, SUMMARY, etc.)
        summary_patterns = [
            r'(?:PROFILE|SUMMARY|OBJECTIVE|ABOUT)\s*\n(.*?)(?=\n[A-Z]{3,}|\n\n|\Z)',
            r'(?:Professional Summary|Career Summary)\s*\n(.*?)(?=\n[A-Z]{3,}|\n\n|\Z)'
        ]
        for pattern in summary_patterns:
            match = re.search(pattern, cv_text, re.IGNORECASE | re.DOTALL)
            if match:
                result["professional_summary"] = match.group(1).strip()
                break
        
        # Basic skills extraction
        skills_patterns = [
            r'(?:SKILLS|TECHNICAL SKILLS|CORE COMPETENCIES)\s*\n(.*?)(?=\n[A-Z]{3,}|\n\n|\Z)',
        ]
        for pattern in skills_patterns:
            match = re.search(pattern, cv_text, re.IGNORECASE | re.DOTALL)
            if match:
                skills_text = match.group(1)
                # Split skills by common separators
                skills = re.split(r'[,|•\n-]', skills_text)
                for skill in skills:
                    skill = skill.strip()
                    if skill and len(skill) > 2 and len(skill) < 30:
                        result["skills"].append({"name": skill, "level": "Intermediate"})
                break
        
        # Enhanced experience extraction with full details
        experience_patterns = [
            r'(?:EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT|PROFESSIONAL EXPERIENCE)\s*\n(.*?)(?=\n(?:EDUCATION|SKILLS|CERTIFICATIONS|QUALIFICATIONS)|\Z)',
        ]
        for pattern in experience_patterns:
            match = re.search(pattern, cv_text, re.IGNORECASE | re.DOTALL)
            if match:
                exp_text = match.group(1)
                
                # Split experience section into individual job blocks
                # Look for patterns like "Title | Company" followed by dates and description
                job_blocks = re.split(r'\n(?=[A-Z][A-Za-z\s&.,()]+ \| [A-Z][A-Za-z\s&.,()]+)', exp_text)
                
                for block in job_blocks:
                    if not block.strip():
                        continue
                    
                    lines = block.strip().split('\n')
                    if not lines:
                        continue
                    
                    # Parse the first line for title and company
                    first_line = lines[0].strip()
                    
                    # Enhanced parsing for "Title | Company        Date" format
                    title_company_match = re.match(r'^(.+?)\s*\|\s*(.+?)(?:\s{2,}(.+?))?$', first_line)
                    if title_company_match:
                        job_title = title_company_match.group(1).strip()
                        company_info = title_company_match.group(2).strip()
                        date_info = title_company_match.group(3).strip() if title_company_match.group(3) else ""
                        
                        # Clean up company name (remove trailing dates if any)
                        company = re.sub(r'\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|\d{1,2}/).*$', '', company_info).strip()
                        
                        # Extract dates from date_info or subsequent lines
                        start_date = ""
                        end_date = ""
                        if date_info:
                            # Parse date range like "Jan 2024 – Present" or "2022 - 2024"
                            date_match = re.search(r'(\w+\s+\d{4}|\d{4})\s*[-–]\s*(\w+\s+\d{4}|\d{4}|Present)', date_info)
                            if date_match:
                                start_date = date_match.group(1)
                                end_date = date_match.group(2)
                        
                        # If no dates in first line, check second line
                        if not start_date and len(lines) > 1:
                            date_line = lines[1].strip()
                            date_match = re.search(r'(\w+\s+\d{4}|\d{4})\s*[-–]\s*(\w+\s+\d{4}|\d{4}|Present)', date_line)
                            if date_match:
                                start_date = date_match.group(1)
                                end_date = date_match.group(2)
                        
                        # Extract job description (everything after title/company/dates)
                        description_lines = []
                        start_desc = 1 if not start_date else 2  # Skip date line if found
                        
                        for i in range(start_desc, len(lines)):
                            line = lines[i].strip()
                            if line and not re.match(r'^[A-Z][A-Za-z\s&.,()]+ \| [A-Z]', line):  # Not another job entry
                                description_lines.append(line)
                        
                        job_description = ' '.join(description_lines).strip()
                        
                        # Only add if we have meaningful content
                        if job_title and company and len(company) > 2:
                            # Avoid "Position at Company" format
                            if not job_title.startswith('Position at'):
                                result["experience"].append({
                                    "job_title": job_title,
                                    "company": company,
                                    "start_date": start_date,
                                    "end_date": end_date,
                                    "description": job_description[:500],  # Limit description length
                                    "location": "",
                                    "current": end_date.lower() in ['present', 'current']
                                })
                                logger.info(f"Extracted job: {job_title} at {company} ({start_date} - {end_date})")
                break
        
        # Enhanced education extraction with full details
        education_patterns = [
            r'(?:EDUCATION|QUALIFICATIONS|ACADEMIC|CREDENTIALS)\s*\n(.*?)(?=\n(?:EXPERIENCE|SKILLS|CERTIFICATIONS)|\Z)',
        ]
        for pattern in education_patterns:
            match = re.search(pattern, cv_text, re.IGNORECASE | re.DOTALL)
            if match:
                edu_text = match.group(1)
                
                # Split education section into individual entries
                edu_blocks = re.split(r'\n(?=[A-Z][A-Za-z\s&.,()])', edu_text)
                
                for block in edu_blocks:
                    if not block.strip():
                        continue
                    
                    lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
                    if not lines:
                        continue
                    
                    # Try different parsing approaches for education entries
                    degree = ""
                    school = ""
                    field_of_study = ""
                    start_date = ""
                    end_date = ""
                    location = ""
                    
                    # Pattern 1: "Degree in Field | University Name        Year"
                    first_line = lines[0]
                    degree_school_match = re.match(r'^(.+?)\s*\|\s*(.+?)(?:\s{2,}(.+?))?$', first_line)
                    
                    if degree_school_match:
                        degree_info = degree_school_match.group(1).strip()
                        school_info = degree_school_match.group(2).strip()
                        date_info = degree_school_match.group(3).strip() if degree_school_match.group(3) else ""
                        
                        # Parse degree and field from degree_info
                        # Examples: "BSc Human Nutrition & Sports Science", "Diploma in Software Development"
                        degree_field_match = re.match(r'^(BSc|MSc|BA|MA|PhD|Diploma|Certificate|Degree)\s+(?:in\s+)?(.+)', degree_info)
                        if degree_field_match:
                            degree = degree_field_match.group(1)
                            field_of_study = degree_field_match.group(2).strip()
                        else:
                            degree = degree_info
                            
                        school = school_info
                        
                        # Extract graduation year/dates
                        if date_info:
                            year_match = re.search(r'(\d{4})', date_info)
                            if year_match:
                                end_date = year_match.group(1)
                    
                    # Pattern 2: Simple degree then school on separate lines
                    elif len(lines) >= 2:
                        # First line might be degree, second line school
                        if any(keyword in lines[0] for keyword in ['BSc', 'MSc', 'BA', 'MA', 'PhD', 'Diploma', 'Certificate']):
                            degree_info = lines[0]
                            school = lines[1]
                            
                            # Parse degree and field
                            degree_field_match = re.match(r'^(BSc|MSc|BA|MA|PhD|Diploma|Certificate|Degree)\s+(?:in\s+)?(.+)', degree_info)
                            if degree_field_match:
                                degree = degree_field_match.group(1)
                                field_of_study = degree_field_match.group(2).strip()
                            else:
                                degree = degree_info
                    
                    # Extract additional details from remaining lines
                    for line in lines[1:]:
                        # Look for graduation years
                        if not end_date:
                            year_match = re.search(r'(\d{4})', line)
                            if year_match:
                                end_date = year_match.group(1)
                        
                        # Look for location
                        if not location and any(keyword in line.lower() for keyword in ['london', 'uk', 'university', 'college']):
                            location = line
                    
                    # Clean up extracted data
                    if degree and school:
                        clean_degree = re.sub(r'\s+', ' ', degree).strip()
                        clean_school = re.sub(r'\s+', ' ', school).strip()
                        clean_field = re.sub(r'\s+', ' ', field_of_study).strip() if field_of_study else ""
                        
                        # Remove common prefixes/suffixes
                        clean_school = re.sub(r'^(University of |College of )', '', clean_school)
                        clean_school = re.sub(r'( University| College)$', '', clean_school) + (' University' if 'University' in school else '')
                        
                        if len(clean_degree) > 2 and len(clean_school) > 2:
                            result["education"].append({
                                "degree": clean_degree,
                                "school": clean_school,
                                "field_of_study": clean_field,
                                "start_date": "",
                                "end_date": end_date,
                                "location": location[:100] if location else "",
                                "grade": ""
                            })
                            logger.info(f"Extracted education: {clean_degree} in {clean_field} from {clean_school} ({end_date})")
                break
        
        logger.info(f"Fallback parsing extracted: email={bool(result['personal_info']['email'])}, phone={bool(result['personal_info']['phone'])}, name={bool(result['personal_info']['first_name'])}, experience={len(result['experience'])}, education={len(result['education'])}")
        return result
    
    def _is_likely_name(self, line: str) -> bool:
        """Check if a line looks like a person's name"""
        if not line or not line.strip():
            return False
        
        line = line.strip()
        words = line.split()
        
        # Must be 2-4 words
        if not (2 <= len(words) <= 4):
            return False
        
        # Length constraints
        if not (10 <= len(line) <= 60):
            return False
            
        # Should not contain these indicators
        if any(indicator in line for indicator in ['@', 'www', '.com', 'http', '©', '|', ':', '+44', '+1']):
            return False
            
        # Should not contain numbers
        if any(char.isdigit() for char in line):
            return False
            
        # Should not be job titles or company words
        job_indicators = ['manager', 'analyst', 'director', 'specialist', 'coordinator', 'officer', 
                         'lead', 'head', 'chief', 'consultant', 'limited', 'ltd', 'inc', 'corp', 
                         'company', 'university', 'college', 'school', 'institute']
        if any(indicator in line.lower() for indicator in job_indicators):
            return False
            
        # Should not be descriptive text
        descriptive_words = ['highly', 'analytical', 'detail-oriented', 'experienced', 'skilled', 
                           'proven', 'strong', 'background', 'expertise', 'adept', 'track', 'record']
        if any(word in line.lower() for word in descriptive_words):
            return False
            
        # Check if words look like proper names (first letter capitalized, rest lowercase)
        for word in words:
            if len(word) > 1:
                if not (word[0].isupper() and word[1:].islower()):
                    return False
            elif len(word) == 1:
                if not word.isupper():
                    return False
        
        # All words should be alphabetic
        if not all(word.replace("'", "").replace("-", "").isalpha() for word in words):
            return False
            
        return True
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty but properly structured result"""
        return {
            "personal_info": {
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone": "",
                "location": "",
                "linkedin": ""
            },
            "professional_summary": "",
            "experience": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "languages": [],
            "projects": [],
            "interests": []
        }
