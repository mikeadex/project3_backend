from typing import Dict, List, Optional
import os
import logging
import requests
from django.conf import settings
from .models import (
    CvWriter,
    Education,
    Experience,
    ProfessionalSummary,
    Interest,
    Skill,
    Language,
    Certification,
    Reference,
    SocialMedia,
    CVImprovement,
)
from .local_llm import ResilientLLMService  # Corrected import
import time
import re
import traceback
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import httpx

# For local Llama model
try:
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    llama_cpp = None
    LLAMA_CPP_AVAILABLE = False
    logging.getLogger('cv_writer').warning("llama_cpp not available, local Llama model will not be used")

logger = logging.getLogger(__name__)

class DeepSeekAPIService:
    """Service for interacting with DeepSeek API."""
    
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.api_base = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com/v1')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        if not self.api_key:
            logger.warning("DeepSeek API key not found in environment variables")
            raise ValueError("DeepSeek API key is required")

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Optional[str]:
        """
        Generate text using DeepSeek API.
        
        Args:
            prompt: The input prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Controls randomness (0.0-1.0)
            top_p: Controls diversity (0.0-1.0)
            
        Returns:
            Generated text or None if generation failed
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "top_p": top_p
                    },
                    timeout=60.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.warning("No content in DeepSeek API response")
                    return None

        except httpx.TimeoutException:
            logger.error("DeepSeek API request timed out")
            return None
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error generating text with DeepSeek: {str(e)}")
            return None

class MistralAPIService:
    """Service for interacting with the Mistral API"""
    
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        if not self.api_key:
            raise ValueError("Mistral API key not found")
            
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-large-latest"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        logger.info("Mistral API initialized successfully")
        
    def generate_with_system_prompt(self, system_prompt, user_prompt, timeout=30):
        """
        Generate text with a system prompt and user prompt
        
        Args:
            system_prompt (str): System prompt for the LLM
            user_prompt (str): User prompt for the LLM
            timeout (int): Request timeout in seconds
            
        Returns:
            str: Generated text
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                response_json = response.json()
                content = response_json["choices"][0]["message"]["content"]
                return content
            else:
                logger.error(f"Mistral API error: {response.status_code}, {response.text}")
                raise Exception(f"Mistral API error: {response.status_code}, {response.text[:100]}")
                
        except requests.exceptions.Timeout:
            logger.error(f"Mistral API timeout after {timeout} seconds")
            raise TimeoutError(f"Mistral API timeout after {timeout} seconds")
            
        except Exception as e:
            logger.error(f"Mistral API error: {str(e)}")
            raise
        
    def improve_text(self, text, timeout=30):
        """
        Improve text using Mistral API
        
        Args:
            text (str): Text to improve
            timeout (int): Request timeout in seconds
            
        Returns:
            str: Improved text
        """
        # For backwards compatibility, we'll format the prompt ourselves
        return self.generate_with_system_prompt(
            "You are a helpful assistant that improves text.",
            text,
            timeout
        )

class GroqLlamaAPIService:
    """Service for interacting with the Groq API with Llama model"""
    
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("Groq API key not found")
            
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama3-8b-8192"  # Updated model name
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        logger.info("Groq Llama API initialized successfully")
        
    def generate_with_system_prompt(self, system_prompt, user_prompt, timeout=30):
        """
        Generate text with a system prompt and user prompt
        
        Args:
            system_prompt (str): System prompt for the LLM
            user_prompt (str): User prompt for the LLM
            timeout (int): Request timeout in seconds
            
        Returns:
            str: Generated text
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                response_json = response.json()
                content = response_json["choices"][0]["message"]["content"]
                return content
            else:
                logger.error(f"Groq API error: {response.status_code}, {response.text}")
                raise Exception(f"Groq API error: {response.status_code}, {response.text[:100]}")
                
        except requests.exceptions.Timeout:
            logger.error(f"Groq API timeout after {timeout} seconds")
            raise TimeoutError(f"Groq API timeout after {timeout} seconds")
            
        except Exception as e:
            logger.error(f"Groq API error: {str(e)}")
            raise
        
    def improve_text(self, text, timeout=30):
        """
        Improve text using Groq Llama API
        
        Args:
            text (str): Text to improve
            timeout (int): Request timeout in seconds
            
        Returns:
            str: Improved text
        """
        # For backwards compatibility, we'll format the prompt ourselves
        return self.generate_with_system_prompt(
            "You are a helpful assistant that improves text.",
            text,
            timeout
        )

class LocalLlamaAPIService:
    """
    Service for generating text using local Llama model
    """
    
    def __init__(self):
        # Try to get model path from settings or environment
        from django.conf import settings
        self.model_path = getattr(settings, 'LLAMA_MODEL_PATH', None) or os.environ.get('LLAMA_MODEL_PATH')
        
        if not self.model_path:
            raise ValueError("LLAMA_MODEL_PATH not set in settings or environment")
            
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("llama_cpp not installed")
            
        # Check if model file exists
        if not os.path.exists(self.model_path):
            # Try relative path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.model_path = os.path.join(base_dir, self.model_path)
            
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found at {self.model_path}")
        
        try:
            self.model = llama_cpp.Llama(
                model_path=self.model_path,
                n_ctx=2048,  # Context window size
                n_batch=512,  # Batch size
                n_gpu_layers=-1  # Use all GPU layers if available
            )
            logger.info(f"Local Llama model initialized from {self.model_path}")
        except Exception as e:
            logger.error(f"Error initializing local Llama model: {e}")
            logger.debug(traceback.format_exc())
            raise
            
    def generate_with_system_prompt(self, system_prompt, user_prompt, timeout=60):
        """
        Generate a response with a system prompt using the local Llama model
        
        Args:
            system_prompt (str): System instructions
            user_prompt (str): User message
            timeout (int): Maximum time to wait for response
            
        Returns:
            str: Generated text
        """
        try:
            # Check if the text might be too long for the context window
            # A rough estimation: 1 token ≈ 4 characters for English text
            estimated_tokens = (len(system_prompt) + len(user_prompt)) // 4
            logger.info(f"Estimated tokens for request: {estimated_tokens}")
            
            # Check if this is a CV segmentation task
            is_cv_segmentation = False
            if "CV" in system_prompt and "segment" in system_prompt.lower() and "section" in system_prompt.lower():
                is_cv_segmentation = True
                logger.info("CV segmentation task detected")
                
                # For CV segmentation, use a more direct and structured prompt
                system_prompt = """You are an expert CV parser with exceptional attention to detail. Follow these instructions PRECISELY:

1. Extract EXACT TEXT from the CV for each section - do not generate placeholders or summaries.
2. Structure your output with this exact format:
   ==========SECTION_NAME
   [ACTUAL CV CONTENT GOES HERE - COPIED VERBATIM]
   ==========

3. Use these section names:
   - PERSONAL_INFO - Include name, contact details, location from CV
   - SUMMARY - Include professional summary/profile from CV
   - EXPERIENCE - Include work experience entries from CV  
   - EDUCATION - Include educational background from CV
   - SKILLS - Include technical and soft skills from CV
   - LANGUAGES - Include language proficiencies from CV
   - CERTIFICATIONS - Include professional certifications from CV

4. DO NOT use placeholders like "(content)" or "(Name)" - extract the REAL TEXT from the CV.
5. If a section is not present in the CV, skip it entirely.
6. KEEP THE EXACT PHRASING from the original CV - your task is extraction, not rewriting."""
            
            # Format prompt for Llama 2 Chat models
            prompt = f"""<s>[INST] <<SYS>>
{system_prompt}
<</SYS>>"""
            
            # If estimated tokens is too large, compress the user prompt
            input_too_large = estimated_tokens > 1800  # Leave margin for system prompt and response
            
            if input_too_large:
                logger.warning(f"Input might exceed context window ({estimated_tokens} estimated tokens)")
                
                # For CV segmentation, intelligently extract key parts
                if is_cv_segmentation and len(user_prompt) > 5000:
                    # Track the original CV text for later extraction
                    cv_text_start = user_prompt.find("CV TEXT:")
                    if cv_text_start > 0:
                        cv_text = user_prompt[cv_text_start + 8:].strip()
                        prompt_prefix = user_prompt[:cv_text_start + 8] + "\n"
                    else:
                        cv_text = user_prompt
                        prompt_prefix = ""
                    
                    # Extract important CV sections based on common section headers
                    extracted_parts = []
                    
                    # Always include the beginning (personal info, headers, etc.)
                    beginning = cv_text[:min(3000, len(cv_text))]
                    extracted_parts.append(beginning)
                    
                    # Find important sections using regex
                    section_patterns = {
                        "experience": r"(?i)(EXPERIENCE|WORK HISTORY|EMPLOYMENT|PROFESSIONAL BACKGROUND)",
                        "education": r"(?i)(EDUCATION|ACADEMIC|QUALIFICATIONS|DEGREE)",
                        "skills": r"(?i)(SKILLS|COMPETENCIES|EXPERTISE|PROFICIENCIES)"
                    }
                    
                    # Extract content around important sections
                    for section_name, pattern in section_patterns.items():
                        matches = list(re.finditer(pattern, cv_text))
                        if matches:
                            for match in matches[:1]:  # Take only the first match for each section
                                start_pos = max(0, match.start() - 200)
                                end_pos = min(len(cv_text), match.start() + 2000)
                                section_text = cv_text[start_pos:end_pos]
                                extracted_parts.append(f"\n\n--- {section_name.upper()} SECTION ---\n\n{section_text}")
                    
                    # Add the ending as well (might contain important info like skills, references)
                    if len(cv_text) > 6000:
                        ending = cv_text[-2000:]
                        extracted_parts.append(f"\n\n--- FINAL SECTION ---\n\n{ending}")
                    
                    # Combine all parts
                    compressed_text = "\n".join(extracted_parts)
                    
                    # Create a new prompt with the compressed text
                    user_prompt = f"{prompt_prefix}{compressed_text}\n\nNote: Some parts have been omitted for length. Focus on extracting the content from these key sections."
                    
                    logger.info(f"Compressed CV from {estimated_tokens} tokens to ~{len(user_prompt) // 4} tokens")
            
            # Complete the prompt
            prompt += f"""

{user_prompt} [/INST]"""
            
            start_time = time.time()
            
            # Generate response with appropriate parameters
            response = self.model(
                prompt,
                max_tokens=1024,  # Increased max tokens for fuller response
                temperature=0.1,  # Lower temperature for more deterministic output
                top_p=0.9,
                echo=False,
                stop=["</s>", "[INST]"]  # Stop at end of generation
            )
            
            # Extract text from response
            generated_text = response.get('choices', [{}])[0].get('text', '').strip()
            
            # Post-process to ensure section markers are formatted properly
            if is_cv_segmentation and generated_text:
                # Fix any malformed section markers
                generated_text = re.sub(r'(?<!\n)={9,11}([A-Z_]+)', r'\n==========\1', generated_text)
                generated_text = re.sub(r'([A-Z_]+)={9,11}(?!\n)', r'\1==========\n', generated_text)
                
                # Check if any section markers were actually created
                if "==========" not in generated_text:
                    # Try to identify implied sections and add markers
                    implied_sections = re.findall(r'\n([A-Z_]{5,})\s*\n', generated_text)
                    for section in implied_sections:
                        section_clean = section.strip()
                        if any(key in section_clean for key in ["PERSONAL", "SUMMARY", "EDUCATION", "EXPERIENCE", "SKILLS", "LANGUAGES", "CERTIFICATIONS"]):
                            generated_text = generated_text.replace(f"\n{section}\n", f"\n=========={section_clean}\n")
            
            # Log timing
            elapsed_time = time.time() - start_time
            logger.info(f"Local Llama generation took {elapsed_time:.2f} seconds")
            
            return generated_text
            
        except ValueError as ve:
            if "context window" in str(ve):
                logger.error(f"Context window error: {ve}")
                logger.info("Attempting with reduced prompt size...")
                
                # For CV segmentation, simplify the system prompt and return a basic structure
                if "segment" in system_prompt.lower():
                    logger.warning("Context window exceeded, falling back to basic CV structure")
                    return self._create_basic_cv_segments()
            
            logger.error(f"Error generating text with local Llama: {ve}")
            logger.debug(traceback.format_exc())
            return ""
            
        except Exception as e:
            logger.error(f"Error generating text with local Llama: {e}")
            logger.debug(traceback.format_exc())
            return ""

    def _create_basic_cv_segments(self):
        """Create a basic CV segmentation when the context window is too small"""
        return """PERSONAL_INFO
===========
[Contact information would appear here]
===========
SUMMARY
===========
[Professional summary would appear here]
===========
EXPERIENCE
===========
[Work experience would appear here]
===========
EDUCATION
===========
[Education details would appear here]
===========
SKILLS
===========
[Skills would appear here]
===========
LANGUAGES
===========
[Language proficiencies would appear here]
===========
CERTIFICATIONS
===========
[Certifications would appear here]
==========="""

    def improve_text(self, text, timeout=60):
        """
        Generate an improved version of the provided text
        
        Args:
            text (str): Text to improve
            timeout (int): Maximum time to wait for response
            
        Returns:
            str: Improved text
        """
        system_prompt = "You are a helpful assistant that improves text."
        user_prompt = f"""Please improve the following text to make it more professional, clear, and effective:

{text}

Return only the improved version without any additional explanations."""
        
        return self.generate_with_system_prompt(system_prompt, user_prompt, timeout)

    def segment_cv(self, text, timeout=60):
        """
        Segment a CV text into sections using DeepSeek (preferred) or local Llama model
        
        Args:
            text (str): CV text to segment
            timeout (int): Maximum time to wait for response
            
        Returns:
            str: Segmented CV text
        """
        # Check if DeepSeek should be enabled
        use_deepseek = os.environ.get('USE_DEEPSEEK', 'true').lower() == 'true'
        
        # Try DeepSeek if available and enabled
        if use_deepseek and self.deepseek_service:
            try:
                logger.info("Attempting to segment CV with DeepSeek")
                segmented_text = self.deepseek_service.segment_cv(text, timeout)
                
                # Check if we got a valid response
                if segmented_text and "==========" in segmented_text:
                    logger.info("Successfully segmented CV with DeepSeek")
                    return segmented_text
                else:
                    logger.warning("DeepSeek segmentation returned invalid result")
            except Exception as e:
                logger.warning(f"Failed to segment CV with DeepSeek: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # Try local Llama if available
        use_local_llama = os.environ.get('USE_LOCAL_LLAMA', 'false').lower() == 'true'
        if use_local_llama and hasattr(self, 'local_llama_service') and self.local_llama_service:
            try:
                logger.info("Attempting to segment CV with local Llama model")
                
                # More direct and simplified system prompt
                system_prompt = """You are an expert CV parser. Your task is to extract and organize the content of a CV/resume into clearly defined sections.

DO NOT replace actual content with placeholder text. Extract and organize the EXACT TEXT from the CV.

For each section, follow this format exactly:
==========SECTION_NAME
[Exact content from the CV for this section]
==========

Use these section names:
- PERSONAL_INFO (name, contact details, location)
- SUMMARY (professional summary or profile)
- EXPERIENCE (work history)
- EDUCATION (educational background)
- SKILLS (technical and soft skills)
- LANGUAGES (language proficiencies)
- CERTIFICATIONS (professional certifications)
- PROJECTS (if present)
- INTERESTS (if present)

If a section doesn't have clear content in the CV, skip that section entirely."""

                # Clear and focused user prompt
                user_prompt = f"""Extract and organize the following CV into the required sections using the EXACT TEXT from the document.

DO NOT generate placeholders or summaries - extract the actual content as is.

CV TEXT:
{text}"""
                
                # First, check if the text is too long and potentially compress it
                estimated_tokens = (len(system_prompt) + len(user_prompt)) // 4
                if estimated_tokens > 1800:
                    # Text is too long, optimize it - but preserve more real content
                    logger.info(f"Original CV text is too long ({estimated_tokens} tokens). Optimizing...")
                    
                    # For each major section, try to find key indicators to preserve those sections
                    # Identify personal info section (usually at the top)
                    personal_info_part = text[:3000]
                    
                    # Look for experience indicators - most important part of CV
                    experience_match = re.search(r'(?i)(EXPERIENCE|EMPLOYMENT|WORK HISTORY|PROFESSIONAL BACKGROUND)', text)
                    experience_part = ""
                    if experience_match:
                        start_idx = max(0, experience_match.start() - 200)
                        experience_part = text[start_idx:start_idx + 3000]
                    
                    # Look for education
                    education_match = re.search(r'(?i)(EDUCATION|ACADEMIC|QUALIFICATIONS|DEGREE)', text)
                    education_part = ""
                    if education_match:
                        start_idx = max(0, education_match.start() - 100)
                        education_part = text[start_idx:start_idx + 1000]
                    
                    # Look for skills
                    skills_match = re.search(r'(?i)(SKILLS|COMPETENCIES|EXPERTISE|PROFICIENCIES)', text)
                    skills_part = ""
                    if skills_match:
                        start_idx = max(0, skills_match.start() - 100)
                        skills_part = text[start_idx:start_idx + 1000]
                    
                    # If we couldn't find specific sections, fall back to a general approach
                    if not (experience_part or education_part or skills_part):
                        # Extract beginning (likely has personal info)
                        first_part = text[:3000]
                        
                        # Extract middle (likely has experience)
                        middle_start = len(text) // 2 - 1500
                        middle_part = text[middle_start:middle_start + 3000]
                        
                        # Extract end (likely has education, skills)
                        last_part = text[-2000:] if len(text) > 2000 else ""
                        
                        optimized_text = (
                            f"{first_part}\n\n"
                            f"[...content omitted for length...]\n\n"
                            f"{middle_part}\n\n"
                            f"[...content omitted for length...]\n\n"
                            f"{last_part}"
                        )
                    else:
                        # Combine the identified sections with markers
                        optimized_text = personal_info_part
                        
                        if experience_part:
                            optimized_text += "\n\n[...content omitted for length...]\n\n" + experience_part
                            
                        if education_part:
                            optimized_text += "\n\n[...content omitted for length...]\n\n" + education_part
                            
                        if skills_part:
                            optimized_text += "\n\n[...content omitted for length...]\n\n" + skills_part
                    
                    logger.info(f"Compressed CV from {len(text)} to {len(optimized_text)} characters")
                    user_prompt = f"""Extract and organize the following CV into the required sections using the EXACT TEXT from the document.

DO NOT generate placeholders or summaries - extract the actual content as is.

Note: Some parts of the CV have been omitted for length, but the main sections are preserved.

CV TEXT:
{optimized_text}"""
                
                # Generate segmented text
                segmented_text = self.local_llama_service.generate_with_system_prompt(
                    system_prompt, user_prompt, timeout=timeout
                )
                
                # Check if we got a valid response
                if segmented_text and "==========" in segmented_text:
                    # Check if the response contains actual content, not just placeholders
                    placeholders = ["(content)", "(Name", "(Personal", "(Professional", "(Work", "(Educational", 
                                   "(Technical", "(Language", "(Professional certifications)"]
                    
                    placeholder_count = sum(1 for p in placeholders if p in segmented_text)
                    
                    # If too many placeholders, it's probably not extracting actual content
                    if placeholder_count > 3:
                        logger.warning("Local Llama segmentation returned too many placeholders")
                        # Try with a simpler approach - just the section markers
                        return self._create_segmented_cv_from_text(text)
                    
                    logger.info("Successfully segmented CV with local Llama model")
                    return segmented_text
                else:
                    logger.warning("Local Llama segmentation returned invalid result")
                    # Fall back to basic segmentation
                    return self._create_segmented_cv_from_text(text)
            except Exception as e:
                logger.warning(f"Failed to segment CV with local Llama: {str(e)}")
                logger.debug(traceback.format_exc())
                # Fall back to basic segmentation
                return self._create_segmented_cv_from_text(text)
        
        # If all segmentation attempts fail, log warning and return empty string
        logger.warning("All services failed to segment CV")
        return ""

    def _create_segmented_cv_from_text(self, text):
        """
        Create a segmented CV by attempting to identify sections in the text
        
        Args:
            text (str): CV text
            
        Returns:
            str: Segmented CV with basic markers
        """
        # Define patterns to identify common CV sections
        section_patterns = {
            'PERSONAL_INFO': [
                r'(?i)(PERSONAL\s+INFORMATION|CONTACT|PROFILE)',
                r'(?i)\b(EMAIL|PHONE|ADDRESS|MOBILE)\b'
            ],
            'SUMMARY': [
                r'(?i)(SUMMARY|PROFILE|OBJECTIVE|ABOUT\s+ME)',
                r'(?i)(PROFESSIONAL\s+SUMMARY|CAREER\s+OBJECTIVE)'
            ],
            'EXPERIENCE': [
                r'(?i)(EXPERIENCE|EMPLOYMENT|WORK\s+HISTORY|PROFESSIONAL\s+BACKGROUND)',
                r'(?i)(CAREER\s+HISTORY|POSITIONS\s+HELD)'
            ],
            'EDUCATION': [
                r'(?i)(EDUCATION|ACADEMIC|QUALIFICATIONS|DEGREE)',
                r'(?i)(UNIVERSITY|COLLEGE|SCHOOL)'
            ],
            'SKILLS': [
                r'(?i)(SKILLS|COMPETENCIES|EXPERTISE|PROFICIENCIES)',
                r'(?i)(TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES)'
            ],
            'LANGUAGES': [
                r'(?i)(LANGUAGES|LANGUAGE\s+PROFICIENCY)',
            ],
            'CERTIFICATIONS': [
                r'(?i)(CERTIFICATIONS|CERTIFICATES|LICENSES|ACCREDITATIONS)',
            ]
        }
        
        lines = text.split('\n')
        result = []
        current_section = None
        section_content = []
        
        # Find potential section headers and their content
        for line in lines:
            found_section = False
            
            for section, patterns in section_patterns.items():
                if any(re.search(pattern, line) for pattern in patterns):
                    # If we already have a section, add it to result
                    if current_section and section_content:
                        result.append(f"=========={current_section}")
                        result.append('\n'.join(section_content))
                        result.append("===========")
                    
                    # Start new section
                    current_section = section
                    section_content = []
                    found_section = True
                    break
            
            if not found_section and current_section:
                # Add line to current section
                section_content.append(line)
        
        # Add the last section if exists
        if current_section and section_content:
            result.append(f"=========={current_section}")
            result.append('\n'.join(section_content))
            result.append("===========")
        
        # If no sections were found, create a basic structure
        if not result:
            # Look for personal info at the beginning
            personal_info = text[:500]
            rest_of_text = text[500:]
            
            result.append("==========PERSONAL_INFO")
            result.append(personal_info)
            result.append("===========")
            
            # Add experience section with the rest
            result.append("==========EXPERIENCE")
            result.append(rest_of_text)
            result.append("===========")
        
        return '\n'.join(result)

class CVImprovementService:
    """
    Service for improving CV text using various LLM services
    """
    
    def __init__(self):
        # Try to initialize all available services
        self.available_services = []
        
        # For debugging/fallback
        self._initialized_services = []
        
        # Check environment variables for disabled services
        disable_mistral = os.environ.get('DISABLE_MISTRAL', 'false').lower() == 'true'
        disable_groq = os.environ.get('DISABLE_GROQ', 'false').lower() == 'true' 
        use_local_llama = os.environ.get('USE_LOCAL_LLAMA', 'false').lower() == 'true'
        use_deepseek = os.environ.get('USE_DEEPSEEK', 'true').lower() == 'true'
        
        # Try to initialize local Llama first if enabled
        if use_local_llama:
            try:
                self.local_llama_service = LocalLlamaAPIService()
                self.available_services.append(self.local_llama_service)
                self._initialized_services.append("LocalLlama")
                # Set as primary service
                self.primary_service = self.local_llama_service
                logger.info("Using local Llama model as primary service")
            except Exception as e:
                logger.warning(f"Failed to initialize local Llama model: {str(e)}")
                self.local_llama_service = None
        else:
            self.local_llama_service = None
        
        # Initialize Mistral if not disabled and we don't have a primary service yet
        if not disable_mistral and not hasattr(self, 'primary_service'):
            try:
                self.mistral_service = MistralAPIService()
                self.available_services.append(self.mistral_service)
                self._initialized_services.append("Mistral")
                # Set as primary if we don't have one yet
                if not hasattr(self, 'primary_service'):
                    self.primary_service = self.mistral_service
            except Exception as e:
                logger.warning(f"Failed to initialize Mistral API: {str(e)}")
                self.mistral_service = None

        # Initialize Groq if not disabled
        if not disable_groq:
            try:
                self.groq_service = GroqLlamaAPIService()
                self.available_services.append(self.groq_service)
                self._initialized_services.append("Groq")
                # Set as fallback
                self.fallback_service = self.groq_service
            except Exception as e:
                logger.warning(f"Failed to initialize Groq API: {str(e)}")
                self.groq_service = None
        else:
            self.groq_service = None

        # Initialize DeepSeek for segmentation if enabled
        if use_deepseek:
            try:
                self.deepseek_service = DeepSeekAPIService()
                self.available_services.append(self.deepseek_service)
                self._initialized_services.append("DeepSeek")
            except Exception as e:
                logger.warning(f"Failed to initialize DeepSeek API: {str(e)}")
                self.deepseek_service = None
        else:
            self.deepseek_service = None
            
        # Make sure we have at least one service
        if not self.available_services:
            raise ValueError("No LLM services available")
            
        # Make sure we have a primary service
        if not hasattr(self, 'primary_service'):
            self.primary_service = self.available_services[0]
            
        # Make sure we have a fallback service
        if not hasattr(self, 'fallback_service') and len(self.available_services) > 1:
            # Use something other than primary as fallback
            for service in self.available_services:
                if service is not self.primary_service:
                    self.fallback_service = service
                    break
        else:
            # If we only have one service, it's both primary and fallback
            self.fallback_service = self.primary_service
            
        logger.info(f"Initialized CV Improvement Service with services: {', '.join(self._initialized_services)}")
        
    def generate_improved_text(self, text, system_prompt=None, timeout=60):
        """
        Generate an improved version of the provided text
        
        Args:
            text (str): Text to improve
            system_prompt (str, optional): System instructions
            timeout (int): Maximum time to wait for response
            
        Returns:
            str: Improved text
        """
        # Default system prompt if not provided
        if not system_prompt:
            system_prompt = (
                "You are a helpful assistant that improves text. "
                "Make text clearer, more professional, and more effective, "
                "while keeping the same information and tone."
            )
        
        # Try primary service first
        try:
            logger.info(f"Attempting to improve text using primary service ({self.primary_service.__class__.__name__})")
            
            # For local Llama service, use its method
            if isinstance(self.primary_service, LocalLlamaAPIService):
                improved_text = self.primary_service.improve_text(text, timeout=timeout)
            else:
                # For API services, use the standard method
                user_prompt = f"""Please improve the following text:

{text}

Return only the improved version without any additional explanations."""
                improved_text = self.primary_service.generate_with_system_prompt(
                    system_prompt, user_prompt, timeout=timeout
                )
                
            # Check if we got a valid response
            if improved_text and len(improved_text) > 0:
                return improved_text
                
        except Exception as e:
            logger.warning(f"Failed to improve text with primary service: {str(e)}")
            logger.debug(traceback.format_exc())
        
        # If primary service failed and we have a different fallback, try that
        if self.fallback_service and self.fallback_service is not self.primary_service:
            try:
                logger.info(f"Attempting to improve text using fallback service ({self.fallback_service.__class__.__name__})")
                
                # For local Llama service, use its method
                if isinstance(self.fallback_service, LocalLlamaAPIService):
                    improved_text = self.fallback_service.improve_text(text, timeout=timeout)
                else:
                    # For API services, use the standard method
                    user_prompt = f"""Please improve the following text:

{text}

Return only the improved version without any additional explanations."""
                    improved_text = self.fallback_service.generate_with_system_prompt(
                        system_prompt, user_prompt, timeout=timeout
                    )
                
                # Check if we got a valid response
                if improved_text and len(improved_text) > 0:
                    return improved_text
                    
            except Exception as e:
                logger.warning(f"Failed to improve text with fallback service: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # If all services failed, return original text
        logger.warning("All services failed to improve text, returning original")
        return text
        
    def improve_text(self, text):
        """
        Improves CV text using available LLM service
        
        Args:
            text (str): Text to improve
            
        Returns:
            str: Improved text or empty string if all services fail
        """
        # Try each service in order until one works
        for service in self.available_services:
            try:
                result = service.improve_text(text)
                if result:
                    return result
            except Exception as e:
                logger.error(f"{service.__class__.__name__} failed: {str(e)}")
                continue
                
        # All services failed
        logger.error("All LLM services failed")
        return ""
        
    def generate_response(self, system_prompt, user_prompt, max_retries=2):
        """
        Generate a response using available LLM services with a system prompt
        and user prompt, which is the prefered format for LLM services.
        
        Args:
            system_prompt (str): System prompt for the LLM
            user_prompt (str): User prompt for the LLM
            max_retries (int): Maximum number of retries
            
        Returns:
            str: Response from LLM service or empty string if all services fail
        """
        # Try each service in order until one works
        for service in self.available_services:
            for attempt in range(max_retries):
                try:
                    # Check if service has a dedicated method for system/user prompts
                    if hasattr(service, 'generate_with_system_prompt'):
                        result = service.generate_with_system_prompt(system_prompt, user_prompt)
                    else:
                        # Fall back to basic format
                        formatted_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                        result = service.improve_text(formatted_prompt)
                        
                    if result:
                        return result
                except Exception as e:
                    logger.error(f"{service.__class__.__name__} attempt {attempt+1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        # Last attempt failed, try next service
                        break
                    # Small delay before retry
                    time.sleep(1) 
        
        # All services failed
        logger.error("All LLM services failed to generate response")
        return ""

    def improve_cv(self, cv_id):
        """
        Improve different sections of a CV using the ResilientLLMService.
        
        Args:
            cv_id (int): ID of the CV to improve
        """
        try:
            # Retrieve CV
            cv = CvWriter.objects.get(id=cv_id)
            
            # Improvement tracking
            improvement_record = CVImprovement.objects.create(cv=cv)
            
            # Pre-process sections
            sections_to_improve = {
                'professional_summary': cv.professional_summary,
                'experience': cv.experience_description,
                'skills': cv.skills
            }
            
            # Pre-processing function to remove generic phrases
            def preprocess_content(content, section_type):
                if not content:
                    return content
                
                # Remove "As a" and "As an" for professional summary
                if section_type == 'professional_summary':
                    content = content.replace('As a ', '', 1)
                    content = content.replace('As an ', '', 1)
                    content = content.strip()
                
                return content
            
            # Improve each section
            for section_type, content in sections_to_improve.items():
                if not content:
                    continue
                
                # Pre-process content
                preprocessed_content = preprocess_content(content, section_type)
                
                # Prepare prompt
                prompt_template = self.improvement_prompts.get(section_type, {}).get('template')
                if not prompt_template:
                    logger.warning(f"No improvement template for section: {section_type}")
                    continue
                
                # Format prompt with industry and content
                prompt = prompt_template.format(
                    industry='technology',  # Default to technology, can be dynamic
                    content=preprocessed_content
                )
                
                # Attempt improvement with primary service
                try:
                    improved_text = self.primary_service.improve_text(prompt)
                    
                    # Fallback to secondary service if primary fails
                    if not improved_text and hasattr(self, 'fallback_service'):
                        improved_text = self.fallback_service.improve_text(prompt)
                    
                    if not improved_text:
                        logger.error(f"Failed to improve {section_type}")
                        continue
                    
                    # Update CV section
                    if section_type == 'professional_summary':
                        cv.professional_summary = improved_text
                    elif section_type == 'experience':
                        cv.experience_description = improved_text
                    elif section_type == 'skills':
                        cv.skills = improved_text
                    
                    # Log improvement
                    logger.info(f"Successfully improved {section_type}")
                
                except Exception as e:
                    logger.error(f"Error improving {section_type}: {str(e)}")
            
            # Save updated CV
            cv.save()
            
            # Update improvement record
            improvement_record.status = 'success'
            improvement_record.save()
            
            return {
                'status': 'success',
                'cv_id': cv_id,
                'sections_improved': list(sections_to_improve.keys())
            }
        
        except Exception as e:
            logger.error(f"CV Improvement Error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _improve_section(self, section: str, content: Dict) -> Dict:
        """Improves a specific section using available LLM."""
        try:
            prompt_data = self.improvement_prompts.get(section)
            if not prompt_data:
                return {'original': content, 'improved': str(content)}

            formatted_prompt = prompt_data['template'].format(
                content=str(content),
                industry=self._detect_industry(content)
            )

            # Fallback logic
            if hasattr(self, 'use_mistral') and self.use_mistral:
                mistral_result = self.primary_service.improve_text(formatted_prompt)
                if mistral_result:
                    return {'original': content, 'improved': mistral_result}
            
            if hasattr(self, 'use_groq') and self.use_groq:
                groq_result = self.fallback_service.improve_text(formatted_prompt)
                if groq_result:
                    return {'original': content, 'improved': groq_result}
            
            if not os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production') and hasattr(self, 'llm_service'):
                return {'original': content, 'improved': self.llm_service.improve_section(section, content)}
            
            logger.warning("No AI service available for improvement")
            return {'original': content, 'improved': str(content)}

        except Exception as e:
            logger.error(f"Error improving section: {str(e)}")
            return {'original': content, 'improved': str(content)}

    def _detect_industry(self, content: Dict) -> str:
        """Detects industry from CV content."""
        industries = {
            'technology': ['software', 'developer', 'engineering', 'IT', 'tech'],
            'finance': ['banking', 'financial', 'accounting', 'investment'],
            'healthcare': ['medical', 'healthcare', 'clinical', 'patient'],
            'marketing': ['marketing', 'advertising', 'brand', 'digital'],
            'education': ['teaching', 'education', 'academic', 'instructor']
        }

        content_str = str(content).lower()
        
        # Count industry keyword matches
        matches = {
            industry: sum(1 for keyword in keywords if keyword in content_str)
            for industry, keywords in industries.items()
        }
        
        # Return industry with most matches, default to technology
        return max(matches.items(), key=lambda x: x[1])[0] if any(matches.values()) else "technology"

    def segment_cv(self, text, timeout=60):
        """
        Segment a CV text into sections using DeepSeek (preferred) or local Llama model
        
        Args:
            text (str): CV text to segment
            timeout (int): Maximum time to wait for response
            
        Returns:
            str: Segmented CV text
        """
        # Check if DeepSeek should be enabled
        use_deepseek = os.environ.get('USE_DEEPSEEK', 'true').lower() == 'true'
        
        # Try DeepSeek if available and enabled
        if use_deepseek and self.deepseek_service:
            try:
                logger.info("Attempting to segment CV with DeepSeek")
                segmented_text = self.deepseek_service.segment_cv(text, timeout)
                
                # Check if we got a valid response
                if segmented_text and "==========" in segmented_text:
                    logger.info("Successfully segmented CV with DeepSeek")
                    return segmented_text
                else:
                    logger.warning("DeepSeek segmentation returned invalid result")
            except Exception as e:
                logger.warning(f"Failed to segment CV with DeepSeek: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # Try local Llama if available
        use_local_llama = os.environ.get('USE_LOCAL_LLAMA', 'false').lower() == 'true'
        if use_local_llama and hasattr(self, 'local_llama_service') and self.local_llama_service:
            try:
                logger.info("Attempting to segment CV with local Llama model")
                
                # More direct and simplified system prompt
                system_prompt = """You are an expert CV parser. Your task is to extract and organize the content of a CV/resume into clearly defined sections.

DO NOT replace actual content with placeholder text. Extract and organize the EXACT TEXT from the CV.

For each section, follow this format exactly:
==========SECTION_NAME
[Exact content from the CV for this section]
==========

Use these section names:
- PERSONAL_INFO (name, contact details, location)
- SUMMARY (professional summary or profile)
- EXPERIENCE (work history)
- EDUCATION (educational background)
- SKILLS (technical and soft skills)
- LANGUAGES (language proficiencies)
- CERTIFICATIONS (professional certifications)
- PROJECTS (if present)
- INTERESTS (if present)

If a section doesn't have clear content in the CV, skip that section entirely."""

                # Clear and focused user prompt
                user_prompt = f"""Extract and organize the following CV into the required sections using the EXACT TEXT from the document.

DO NOT generate placeholders or summaries - extract the actual content as is.

CV TEXT:
{text}"""
                
                # First, check if the text is too long and potentially compress it
                estimated_tokens = (len(system_prompt) + len(user_prompt)) // 4
                if estimated_tokens > 1800:
                    # Text is too long, optimize it - but preserve more real content
                    logger.info(f"Original CV text is too long ({estimated_tokens} tokens). Optimizing...")
                    
                    # For each major section, try to find key indicators to preserve those sections
                    # Identify personal info section (usually at the top)
                    personal_info_part = text[:3000]
                    
                    # Look for experience indicators - most important part of CV
                    experience_match = re.search(r'(?i)(EXPERIENCE|EMPLOYMENT|WORK HISTORY|PROFESSIONAL BACKGROUND)', text)
                    experience_part = ""
                    if experience_match:
                        start_idx = max(0, experience_match.start() - 200)
                        experience_part = text[start_idx:start_idx + 3000]
                    
                    # Look for education
                    education_match = re.search(r'(?i)(EDUCATION|ACADEMIC|QUALIFICATIONS|DEGREE)', text)
                    education_part = ""
                    if education_match:
                        start_idx = max(0, education_match.start() - 100)
                        education_part = text[start_idx:start_idx + 1000]
                    
                    # Look for skills
                    skills_match = re.search(r'(?i)(SKILLS|COMPETENCIES|EXPERTISE|PROFICIENCIES)', text)
                    skills_part = ""
                    if skills_match:
                        start_idx = max(0, skills_match.start() - 100)
                        skills_part = text[start_idx:start_idx + 1000]
                    
                    # If we couldn't find specific sections, fall back to a general approach
                    if not (experience_part or education_part or skills_part):
                        # Extract beginning (likely has personal info)
                        first_part = text[:3000]
                        
                        # Extract middle (likely has experience)
                        middle_start = len(text) // 2 - 1500
                        middle_part = text[middle_start:middle_start + 3000]
                        
                        # Extract end (likely has education, skills)
                        last_part = text[-2000:] if len(text) > 2000 else ""
                        
                        optimized_text = (
                            f"{first_part}\n\n"
                            f"[...content omitted for length...]\n\n"
                            f"{middle_part}\n\n"
                            f"[...content omitted for length...]\n\n"
                            f"{last_part}"
                        )
                    else:
                        # Combine the identified sections with markers
                        optimized_text = personal_info_part
                        
                        if experience_part:
                            optimized_text += "\n\n[...content omitted for length...]\n\n" + experience_part
                            
                        if education_part:
                            optimized_text += "\n\n[...content omitted for length...]\n\n" + education_part
                            
                        if skills_part:
                            optimized_text += "\n\n[...content omitted for length...]\n\n" + skills_part
                    
                    logger.info(f"Compressed CV from {len(text)} to {len(optimized_text)} characters")
                    user_prompt = f"""Extract and organize the following CV into the required sections using the EXACT TEXT from the document.

DO NOT generate placeholders or summaries - extract the actual content as is.

Note: Some parts of the CV have been omitted for length, but the main sections are preserved.

CV TEXT:
{optimized_text}"""
                
                # Generate segmented text
                segmented_text = self.local_llama_service.generate_with_system_prompt(
                    system_prompt, user_prompt, timeout=timeout
                )
                
                # Check if we got a valid response
                if segmented_text and "==========" in segmented_text:
                    # Check if the response contains actual content, not just placeholders
                    placeholders = ["(content)", "(Name", "(Personal", "(Professional", "(Work", "(Educational", 
                                   "(Technical", "(Language", "(Professional certifications)"]
                    
                    placeholder_count = sum(1 for p in placeholders if p in segmented_text)
                    
                    # If too many placeholders, it's probably not extracting actual content
                    if placeholder_count > 3:
                        logger.warning("Local Llama segmentation returned too many placeholders")
                        # Try with a simpler approach - just the section markers
                        return self._create_segmented_cv_from_text(text)
                    
                    logger.info("Successfully segmented CV with local Llama model")
                    return segmented_text
                else:
                    logger.warning("Local Llama segmentation returned invalid result")
                    # Fall back to basic segmentation
                    return self._create_segmented_cv_from_text(text)
            except Exception as e:
                logger.warning(f"Failed to segment CV with local Llama: {str(e)}")
                logger.debug(traceback.format_exc())
                # Fall back to basic segmentation
                return self._create_segmented_cv_from_text(text)
        
        # If all segmentation attempts fail, log warning and return empty string
        logger.warning("All services failed to segment CV")
        return ""

    def _create_segmented_cv_from_text(self, text):
        """
        Create a segmented CV by attempting to identify sections in the text
        
        Args:
            text (str): CV text
            
        Returns:
            str: Segmented CV with basic markers
        """
        # Define patterns to identify common CV sections
        section_patterns = {
            'PERSONAL_INFO': [
                r'(?i)(PERSONAL\s+INFORMATION|CONTACT|PROFILE)',
                r'(?i)\b(EMAIL|PHONE|ADDRESS|MOBILE)\b'
            ],
            'SUMMARY': [
                r'(?i)(SUMMARY|PROFILE|OBJECTIVE|ABOUT\s+ME)',
                r'(?i)(PROFESSIONAL\s+SUMMARY|CAREER\s+OBJECTIVE)'
            ],
            'EXPERIENCE': [
                r'(?i)(EXPERIENCE|EMPLOYMENT|WORK\s+HISTORY|PROFESSIONAL\s+BACKGROUND)',
                r'(?i)(CAREER\s+HISTORY|POSITIONS\s+HELD)'
            ],
            'EDUCATION': [
                r'(?i)(EDUCATION|ACADEMIC|QUALIFICATIONS|DEGREE)',
                r'(?i)(UNIVERSITY|COLLEGE|SCHOOL)'
            ],
            'SKILLS': [
                r'(?i)(SKILLS|COMPETENCIES|EXPERTISE|PROFICIENCIES)',
                r'(?i)(TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES)'
            ],
            'LANGUAGES': [
                r'(?i)(LANGUAGES|LANGUAGE\s+PROFICIENCY)',
            ],
            'CERTIFICATIONS': [
                r'(?i)(CERTIFICATIONS|CERTIFICATES|LICENSES|ACCREDITATIONS)',
            ]
        }
        
        lines = text.split('\n')
        result = []
        current_section = None
        section_content = []
        
        # Find potential section headers and their content
        for line in lines:
            found_section = False
            
            for section, patterns in section_patterns.items():
                if any(re.search(pattern, line) for pattern in patterns):
                    # If we already have a section, add it to result
                    if current_section and section_content:
                        result.append(f"=========={current_section}")
                        result.append('\n'.join(section_content))
                        result.append("===========")
                    
                    # Start new section
                    current_section = section
                    section_content = []
                    found_section = True
                    break
            
            if not found_section and current_section:
                # Add line to current section
                section_content.append(line)
        
        # Add the last section if exists
        if current_section and section_content:
            result.append(f"=========={current_section}")
            result.append('\n'.join(section_content))
            result.append("===========")
        
        # If no sections were found, create a basic structure
        if not result:
            # Look for personal info at the beginning
            personal_info = text[:500]
            rest_of_text = text[500:]
            
            result.append("==========PERSONAL_INFO")
            result.append(personal_info)
            result.append("===========")
            
            # Add experience section with the rest
            result.append("==========EXPERIENCE")
            result.append(rest_of_text)
            result.append("===========")
        
        return '\n'.join(result)
