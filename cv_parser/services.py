import os
import json
import logging
import requests
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
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Configure retry strategy with longer timeouts
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=2,  # wait 2, 4, 8 seconds between retries
            status_forcelist=[500, 502, 503, 504, 429],  # Added 429 for rate limiting
        )
        
        # Create a session with retry strategy
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
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
            
            # Prepare the prompt for the API
            prompt = f"""Please analyze this CV and extract the following information in JSON format:
            - professional_summary: A brief summary of the candidate's professional background
            - skills: List of technical and soft skills
            - experience: List of work experiences with company, role, duration, and responsibilities
            - education: List of educational qualifications
            - certifications: List of professional certifications
            - languages: List of languages known
            - contact_info: Contact information including email, phone, location
            
            CV Content:
            {text}
            
            Please provide the information in a structured JSON format with these exact keys."""
            
            # Make the API request with improved error handling
            try:
                # Split the request into connect and read timeouts
                connect_timeout = 10  # 10 seconds to establish connection
                read_timeout = timeout - connect_timeout  # Remaining time for reading response
                
                logger.info(f"Making API request with connect_timeout={connect_timeout}s, read_timeout={read_timeout}s")
                
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "timeout": timeout
                    },
                    timeout=(connect_timeout, read_timeout)  # (connect timeout, read timeout)
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
                    parsed_data = json.loads(result['choices'][0]['message']['content'])
                    
                    # Add metadata
                    parsed_data['metadata'] = {
                        'filename': os.path.basename(file_path),
                        'size': os.path.getsize(file_path),
                        'mime_type': f'application/{file_extension[1:]}',
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
                logger.error(f"Timeout while processing document: {str(e)}")
                return {
                    "error": "Request timed out",
                    "details": f"The request took longer than {timeout} seconds to complete",
                    "timeout": timeout,
                    "text_size": text_size
                }
                
        except Exception as e:
            logger.error(f"Error parsing document: {str(e)}", exc_info=True)
            return {
                "error": f"An unexpected error occurred: {str(e)}",
                "details": str(e)
            } 