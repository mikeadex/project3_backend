import os
import json
import logging
import requests
import re
from typing import Dict, Any, Optional
from django.conf import settings
from docx import Document
from PyPDF2 import PdfReader
from .models import ParsedCV
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import ReadTimeoutError, ConnectTimeoutError

logger = logging.getLogger(__name__)

class DeepSeekService:
    """Service for interacting with DeepSeek API"""
    
    def __init__(self):
        self.api_key = os.environ.get('DEEPSEEK_API_KEY')
        self.api_url = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1')
        self.model = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
        
        # Extended timeout settings for production
        self.connect_timeout = 30  # Increased from 20
        self.read_timeout = 180    # Increased from 120
        
        # Initialize session with retry functionality
        retry_strategy = Retry(
            total=5,  # Increased from 3
            backoff_factor=2,  # Exponential backoff
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def parse_document(self, file_path: str, max_timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Parse a document using DeepSeek API with improved error handling and timeout management.
        
        Args:
            file_path: Path to the document file
            max_timeout: Maximum time to wait for parsing in seconds (overrides settings)
            
        Returns:
            Dict containing parsed data or error information
        """
        try:
            # Use configured timeout or provided timeout
            timeout = max_timeout or settings.DEEPSEEK_TIMEOUT
            
            # Extract text based on file type
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension == '.docx':
                doc = Document(file_path)
                text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            elif file_extension == '.pdf':
                reader = PdfReader(file_path)
                text = '\n'.join([page.extract_text() for page in reader.pages])
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            # Log the size of the text being processed
            text_size = len(text)
            logger.info(f"Processing document with text size: {text_size} characters")
            
            # Adjust timeout based on text size
            if text_size > 5000:
                timeout = min(timeout * 1.5, 90)  # Increase timeout for medium documents
            if text_size > 10000:
                timeout = min(timeout * 2, 120)  # Further increase for large documents
            
            # Before AI extraction, use regex patterns to extract personal information
            contact_info = self._extract_contact_info_with_patterns(text)
                
            # Prepare the prompt for the API
            prompt = f"""Please analyze this CV and extract the following information in JSON format:
            
            1. contact_info: A dictionary containing the following personal details (this is VERY important):
               - name: The full name of the candidate
               - email: The candidate's email address
               - phone: The candidate's phone number with country code if available
               - location: The candidate's location or address
               - linkedin: LinkedIn profile URL if present
               - website: Personal or portfolio website if present
            
            2. professional_summary: A brief summary of the candidate's professional background
            
            3. skills: List of technical and soft skills
               - Each skill should be an object with "name" and "level" (Beginner, Intermediate, Advanced, Expert)
            
            4. experience: List of work experiences, each containing:
               - company: Company name
               - role: Job title
               - start_date: When they started (format: YYYY-MM or YYYY)
               - end_date: When they ended (format: YYYY-MM or YYYY, or "Present" if current)
               - responsibilities: List of key responsibilities and achievements
            
            5. education: List of educational qualifications, each containing:
               - institution: School/University name
               - degree: Type of degree (e.g., Bachelor of Science)
               - field: Field of study
               - graduation_date: When they graduated (format: YYYY-MM or YYYY)
            
            6. certifications: List of professional certifications
            
            7. languages: List of languages known with proficiency level
            
            CV Content:
            {text}
            
            IMPORTANT INSTRUCTIONS:
            1. Pay special attention to extracting ALL contact information correctly
            2. Make sure to extract the full name correctly
            3. Ensure email and phone number are accurately identified
            4. Format dates consistently
            5. Provide the information in a valid JSON format with these exact keys
            6. If you can't find information for a specific field, include it as null or an empty array"""
            
            # Make the API request with improved error handling
            try:
                # Split the request into connect and read timeouts
                logger.info(f"Making API request with connect_timeout={self.connect_timeout}s, read_timeout={self.read_timeout}s")
                
                response = self.session.post(
                    f"{self.api_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "timeout": timeout
                    },
                    timeout=(self.connect_timeout, self.read_timeout)  # (connect timeout, read timeout)
                )
                
                # Check for API errors
                if response.status_code != 200:
                    error_message = f"API returned non-200 status code: {response.status_code}"
                    logger.error(error_message)
                    logger.error(f"API response: {response.text}")
                    return {
                        "error": error_message,
                        "details": response.text
                    }
                
                # Process the API response
                api_response = response.json()
                
                # Check if the API returned valid JSON
                if "choices" not in api_response or not api_response["choices"]:
                    error_message = "API returned unexpected response format"
                    logger.error(error_message)
                    logger.error(f"API response: {api_response}")
                    return {
                        "error": error_message,
                        "details": api_response
                    }
                
                response_content = api_response["choices"][0]["message"]["content"]
                
                # Try to parse the response as JSON
                try:
                    # First, try direct JSON parsing
                    parsed_data = json.loads(response_content)
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON from markdown code blocks
                    try:
                        if "```json" in response_content:
                            json_content = response_content.split("```json")[1].split("```")[0].strip()
                            parsed_data = json.loads(json_content)
                        elif "```" in response_content:
                            json_content = response_content.split("```")[1].split("```")[0].strip()
                            parsed_data = json.loads(json_content)
                        else:
                            # Try to extract JSON object by finding matching braces
                            json_start = response_content.find("{")
                            json_end = response_content.rfind("}") + 1
                            if json_start >= 0 and json_end > json_start:
                                json_content = response_content[json_start:json_end]
                                parsed_data = json.loads(json_content)
                            else:
                                raise ValueError("Could not find JSON content in response")
                    except Exception as e:
                        error_message = f"Failed to extract JSON from API response: {str(e)}"
                        logger.error(error_message)
                        logger.error(f"API response content: {response_content}")
                        return {
                            "error": error_message,
                            "details": response_content
                        }
                
                # Merge pattern-based extraction results with AI-based results to ensure contact info
                if 'contact_info' not in parsed_data:
                    parsed_data['contact_info'] = contact_info
                else:
                    # Update AI-extracted contact info with pattern-based extraction if fields are missing
                    for key, value in contact_info.items():
                        if value and (key not in parsed_data['contact_info'] or not parsed_data['contact_info'][key]):
                            parsed_data['contact_info'][key] = value
                
                return parsed_data
                
            except Exception as e:
                error_message = f"Error parsing document: {str(e)}"
                logger.error(error_message, exc_info=True)
                return {
                    "error": error_message,
                    "details": str(e),
                    "text_size": text_size
                }
                
        except Exception as e:
            logger.error(f"Error parsing document: {str(e)}", exc_info=True)
            return {
                "error": f"An unexpected error occurred: {str(e)}",
                "details": str(e)
            } 
            
    def make_custom_request(self, prompt: str, max_timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Make a custom request to the DeepSeek API with any prompt.
        
        Args:
            prompt: Custom prompt to send to the API
            max_timeout: Maximum time to wait for response in seconds
            
        Returns:
            Dict containing parsed response or error information
        """
        try:
            # Use configured timeout or provided timeout
            timeout = max_timeout or settings.DEEPSEEK_TIMEOUT
            
            # Log the size of the text being processed
            text_size = len(prompt)
            logger.info(f"Processing custom request with text size: {text_size} characters")
            
            # Adjust timeout based on text size
            if text_size > 5000:
                timeout = min(timeout * 1.5, 90)  # Increase timeout for medium requests
            if text_size > 10000:
                timeout = min(timeout * 2, 120)  # Further increase for large requests
            
            # Make the API request with improved error handling
            try:
                # Split the request into connect and read timeouts
                logger.info(f"Making API request with connect_timeout={self.connect_timeout}s, read_timeout={self.read_timeout}s")
                
                response = self.session.post(
                    f"{self.api_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "timeout": timeout
                    },
                    timeout=(self.connect_timeout, self.read_timeout)  # (connect timeout, read timeout)
                )
                
                # Check for API errors
                if response.status_code != 200:
                    error_msg = f"API request failed with status {response.status_code}"
                    logger.error(f"{error_msg}: {response.text}")
                    return {
                        "error": error_msg,
                        "details": response.text,
                        "status_code": response.status_code
                    }
                
                # Parse the response
                try:
                    result = response.json()
                    # Add safeguards for parsing the content
                    if 'choices' not in result or not result['choices'] or 'message' not in result['choices'][0] or 'content' not in result['choices'][0]['message']:
                        logger.error(f"Unexpected API response structure: {json.dumps(result)[:500]}")
                        return {
                            "error": "Invalid API response structure",
                            "details": "The API returned an unexpected response format"
                        }
                    
                    content = result['choices'][0]['message']['content']
                    
                    # Try to extract JSON from the response which might contain markdown or other text
                    try:
                        # First try direct JSON parsing
                        parsed_data = json.loads(content)
                    except json.JSONDecodeError:
                        # If that fails, try to extract JSON from markdown code blocks
                        try:
                            # Look for content between ```json and ``` markers
                            if "```json" in content:
                                json_start = content.find("```json") + 7
                                json_end = content.find("```", json_start)
                                if json_end > json_start:
                                    json_content = content[json_start:json_end].strip()
                                    parsed_data = json.loads(json_content)
                                else:
                                    raise ValueError("Could not find closing JSON code block")
                            # Try to find any JSON-like structure with braces
                            elif "{" in content and "}" in content:
                                json_start = content.find("{")
                                json_end = content.rfind("}") + 1
                                if json_end > json_start:
                                    json_content = content[json_start:json_end].strip()
                                    parsed_data = json.loads(json_content)
                                else:
                                    raise ValueError("Could not extract valid JSON from content")
                            else:
                                raise ValueError("No JSON structure found in the content")
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.error(f"Failed to extract JSON from API response: {e}")
                            # Return a partial result with raw content for debugging
                            return {
                                "error": "Failed to parse JSON from API response",
                                "details": str(e),
                                "raw_content": content[:500] + "..." if len(content) > 500 else content
                            }
                    
                    # Add metadata
                    parsed_data['metadata'] = {
                        'parsing_time': response.elapsed.total_seconds(),
                        'text_size': text_size,
                        'timeout_used': timeout
                    }
                    
                    return parsed_data
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse API response: {e}")
                    return {
                        "error": "Failed to parse API response",
                        "details": str(e)
                    }
                    
            except (ReadTimeoutError, ConnectTimeoutError) as e:
                logger.error(f"Timeout while processing request: {str(e)}")
                return {
                    "error": "Request timed out",
                    "details": f"The request took longer than {timeout} seconds to complete",
                    "timeout": timeout,
                    "text_size": text_size
                }
            except Exception as e:
                logger.error(f"Error during API request: {str(e)}")
                return {
                    "error": "API request failed",
                    "details": str(e)
                }
                
        except Exception as e:
            logger.error(f"Unexpected error in make_custom_request: {str(e)}")
            return {
                "error": "An unexpected error occurred",
                "details": str(e)
            }
            
    def _extract_contact_info_with_patterns(self, text):
        """
        Extract contact information using regex patterns
        """
        contact_info = {
            'name': None,
            'email': None,
            'phone': None,
            'location': None,
            'linkedin': None,
            'website': None
        }
        
        # Email pattern
        email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
        email_matches = re.findall(email_pattern, text)
        if email_matches:
            contact_info['email'] = email_matches[0]
            
        # Phone pattern - matches various formats
        phone_patterns = [
            r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # International format
            r'(?:\+\d{1,3}[-.\s]?)?\d{10,12}',  # Plain digits
            r'\d{3,5}[-.\s]?\d{3}[-.\s]?\d{3,4}',  # Dashed/spaced format
            r'\(\d{3,5}\)[-.\s]?\d{3}[-.\s]?\d{3,4}'  # Parentheses format
        ]
        
        for pattern in phone_patterns:
            phone_matches = re.findall(pattern, text)
            if phone_matches:
                # Clean and format the phone number
                phone = phone_matches[0].strip()
                contact_info['phone'] = phone
                break
                
        # LinkedIn pattern
        linkedin_patterns = [
            r'linkedin\.com/in/[\w-]+',
            r'linked\.in/[\w-]+',
            r'linkedin:?\s*[\w-]+',
        ]
        
        for pattern in linkedin_patterns:
            linkedin_matches = re.findall(pattern, text, re.IGNORECASE)
            if linkedin_matches:
                contact_info['linkedin'] = linkedin_matches[0]
                break
                
        # Website pattern
        website_pattern = r'(https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*))'
        website_matches = re.findall(website_pattern, text)
        if website_matches:
            # Filter out LinkedIn URLs as they're already handled
            non_linkedin_sites = [site for site in website_matches if 'linkedin' not in site.lower()]
            if non_linkedin_sites:
                contact_info['website'] = non_linkedin_sites[0]
                
        # Name extraction strategy - look at first few lines for prominent names
        lines = text.strip().split('\n')
        name_candidates = []
        
        # Check the first 5 lines for potential names
        for i in range(min(5, len(lines))):
            line = lines[i].strip()
            # Skip empty lines, email addresses, and lines with common headers
            if (not line or 
                '@' in line or 
                re.search(r'curriculum\s*vitae|resume|cv', line, re.IGNORECASE) or
                any(p in line.lower() for p in ['address:', 'phone:', 'email:', 'contact:', 'profile'])):
                continue
                
            # Check if line contains only a name (2-3 words, no punctuation except hyphen)
            words = line.split()
            if 1 <= len(words) <= 3 and not re.search(r'[^\w\s-]', line):
                name_candidates.append(line)
        
        # If we have candidates, use the first one as the name
        if name_candidates:
            contact_info['name'] = name_candidates[0]
            
        # Location extraction - look for city/country patterns
        location_patterns = [
            r'(?:located\s+in|based\s+in|from)\s+([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})',
            r'([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})(?:\s*[-,]\s*[A-Z]{2,})',
            r'(?:Address|Location):\s*([^,\n]+(?:,\s*[^,\n]+){0,3})'
        ]
        
        for pattern in location_patterns:
            location_matches = re.findall(pattern, text)
            if location_matches:
                contact_info['location'] = location_matches[0].strip()
                break
                
        return contact_info