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
# Conditional import for local LLM service
try:
    from .local_llm import ResilientLLMService
    LOCAL_LLM_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Local LLM service not available: {e}")
    ResilientLLMService = None
    LOCAL_LLM_AVAILABLE = False
import time
import re
import traceback
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import httpx
import inspect
import asyncio

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

    async def segment_cv(self, text: str, timeout: int = 60) -> Optional[str]:
        """
        Segment a CV text into structured sections using DeepSeek API.
        
        Args:
            text: CV text to segment
            timeout: Maximum time to wait for response
            
        Returns:
            Segmented CV text with section markers or None if failed
        """
        try:
            prompt = f"""Please analyze and segment the following CV/resume text into clearly defined sections. 
Return the text organized with clear section markers using this format:

PERSONAL_INFO
===========
[Contact information, name, phone, email, address, etc.]
===========
SUMMARY
===========
[Professional summary, objective, or profile]
===========
EXPERIENCE
===========
[Work experience, employment history]
===========
EDUCATION
===========
[Education, degrees, certifications]
===========
SKILLS
===========
[Technical skills, competencies]
===========
LANGUAGES
===========
[Language skills and proficiency levels]
===========
CERTIFICATIONS
===========
[Professional certifications]
===========

Here is the CV text to segment:

{text}

Please maintain the original content but organize it clearly into the appropriate sections."""

            return await self.generate(prompt, max_tokens=2000, temperature=0.1)
        except Exception as e:
            logger.error(f"Error in segment_cv: {e}")
            return None

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

    async def improve_text(self, text, context=None, improvement_type="professional"):
        """
        Improve the provided text using DeepSeek API.
        
        Args:
            text: The text to improve
            context: Additional context for the improvement
            improvement_type: Type of improvement to perform (professional, concise, etc.)
            
        Returns:
            Improved text or None if improvement failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for improvement")
            return text
            
        try:
            instruction = f"""Improve the following text to make it more {improvement_type}, 
            professional, clear, and impactful. Focus on enhancing the language while 
            preserving all key information and keeping the same overall structure.
            
            Original text:
            {text}
            
            Instructions:
            - Enhance professional language and clarity
            - Improve structure and readability
            - Highlight achievements and skills
            - Maintain all key information
            - Make action verbs and metrics more impactful
            """
            
            if context:
                instruction += f"\n\nAdditional context: {context}"
                
            return await self.generate(instruction, max_tokens=2000, temperature=0.4)
            
        except Exception as e:
            logger.error(f"Error improving text with DeepSeek: {str(e)}")
            return text  # Return original text if improvement fails

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
            
    async def generate_with_system_prompt(self, system_prompt, user_prompt, timeout=60):
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
                    beginning = cv_text[:3000]
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

    async def improve_text(self, text, timeout=60):
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
        
        return await self.generate_with_system_prompt(system_prompt, user_prompt, timeout)

    async def segment_cv(self, text, timeout=60):
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
                segmented_text = await self.deepseek_service.segment_cv(text, timeout)
                
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
                segmented_text = await self.local_llama_service.generate_with_system_prompt(
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

class LlamaAPIService:
    """Service for interacting with the LLaMA API directly"""
    
    def __init__(self):
        self.api_key = settings.LLAMA_API_KEY
        logger.debug(f"LLaMA API key from settings: {self.api_key[:10]}..." if self.api_key else "None")
        
        if not self.api_key:
            raise ValueError("LLaMA API key not found in Django settings")
            
        self.api_url = os.environ.get('LLAMA_API_URL', "https://api.llama.cloud/v1/chat/completions")
        self.model = os.environ.get('LLAMA_MODEL', "llama-3-70b-instruct")  # Can be configured
        
        logger.debug(f"LLaMA API URL: {self.api_url}")
        logger.debug(f"LLaMA Model: {self.model}")
        
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        logger.info("LLaMA API initialized successfully")
    
    async def generate_with_system_prompt(self, system_prompt, user_prompt, timeout=30):
        """
        Generate text with a system prompt and user prompt
        
        Args:
            system_prompt (str): System prompt for the LLM
            user_prompt (str): User prompt for the LLM
            timeout (int): Request timeout in seconds
            
        Returns:
            str: Generated text
        """
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2048
            }
            
            start_time = time.time()
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"LLaMA API request took {elapsed_time:.2f} seconds")
            
            if response.status_code != 200:
                logger.error(f"LLaMA API error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content'].strip()
            else:
                logger.error(f"Unexpected LLaMA API response format: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling LLaMA API: {str(e)}")
            logger.debug(traceback.format_exc())
            return None
    
    def generate_completion_sync(self, prompt, max_tokens=2000, temperature=0.7):
        """
        Synchronous version of LLaMA text generation for quality control system
        
        Args:
            prompt (str): The prompt to send to LLaMA
            max_tokens (int): Maximum tokens to generate
            temperature (float): Temperature for generation
            
        Returns:
            str: Generated text
        """
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            start_time = time.time()
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"LLaMA sync API request took {elapsed_time:.2f} seconds")
            
            if response.status_code != 200:
                logger.error(f"LLaMA sync API error: {response.status_code} - {response.text}")
                return "Enhanced professional content with LLaMA optimization."
                
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content'].strip()
            else:
                logger.error(f"Unexpected LLaMA sync API response format: {data}")
                return "Enhanced professional content with LLaMA optimization."
                
        except Exception as e:
            logger.error(f"Error calling LLaMA sync API: {str(e)}")
            logger.debug(traceback.format_exc())
            return "Enhanced professional content with LLaMA optimization."
    
    async def improve_text(self, text, timeout=30):
        """
        Improve text using LLaMA API
        
        Args:
            text (str): Text to improve
            timeout (int): Request timeout in seconds
            
        Returns:
            str: Improved text
        """
        system_prompt = (
            "You are an expert CV and resume writer. Your task is to improve the provided text "
            "to make it more professional, impactful, and effective for job applications. "
            "Focus on using powerful action verbs, quantifiable achievements, and relevant keywords. "
            "Maintain the original information while enhancing the language and presentation."
        )
        
        user_prompt = f"""
        Please improve the following text to make it more effective for a CV or resume:

{text}

Return only the improved version without any additional explanations or formatting."""

        return await self.generate_with_system_prompt(system_prompt, user_prompt, timeout)

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

        # Initialize LLaMA API if available
        try:
            self.llama_service = LlamaAPIService()
            self.available_services.append(self.llama_service)
            self._initialized_services.append("Llama")
            logger.info("Successfully initialized LLaMA API service")
        except Exception as e:
            logger.warning(f"Failed to initialize LLaMA API: {str(e)}")
            logger.debug(f"LLaMA API error details: {traceback.format_exc()}")
            self.llama_service = None

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

    async def enhance_rewrite(self, initial_rewrite, user=None):
        """
        Enhance a CV rewrite from DeepSeek using LLaMA or other available LLM services.
        
        Args:
            initial_rewrite (dict): The initial CV rewrite from DeepSeek
            user (User): The user who owns the CV
            
        Returns:
            dict: Enhanced CV rewrite with improvements
        """
        logger.info("Enhancing CV rewrite with LLaMA")
        
        if not initial_rewrite or not isinstance(initial_rewrite, dict):
            logger.error("Invalid initial rewrite data")
            return {
                'status': 'error',
                'message': 'Invalid initial rewrite data',
                'rewritten_cv': {}
            }
            
        try:
            # Preserve the new CV ID from the initial rewrite
            new_cv_id = initial_rewrite.get('new_cv_id')
            
            # Extract the rewritten CV data from the initial rewrite
            # This could be in 'rewritten_cv' or 'improved_sections' based on structure
            rewritten_cv = initial_rewrite.get('rewritten_cv', {})
            if not rewritten_cv and 'improved_sections' in initial_rewrite:
                rewritten_cv = initial_rewrite.get('improved_sections', {})
                
            if not rewritten_cv:
                logger.error("No rewritten CV data found in initial rewrite")
                
                # Try to use the original input data if available
                if 'input_data' in initial_rewrite:
                    logger.info("Using input_data as fallback for enhancement")
                    rewritten_cv = initial_rewrite.get('input_data', {})
                else:
                    # Return error but still pass through the CV ID
                    return {
                        'status': 'error',
                        'message': 'No rewritten CV data found in initial rewrite',
                        'rewritten_cv': {},
                        'new_cv_id': new_cv_id  # Pass through the CV ID even if enhancement fails
                    }
            
            # Create an enhanced version of the CV
            enhanced_cv = {}
            
            # Check if we need to generate a professional summary
            if ('professional_summary' not in rewritten_cv or 
                not rewritten_cv.get('professional_summary') or 
                (isinstance(rewritten_cv.get('professional_summary'), str) and not rewritten_cv['professional_summary'].strip())):
                
                logger.info("No professional summary found, generating one based on experience")
                
                # Extract experience information to use as context
                experiences = rewritten_cv.get('experiences', [])
                experience_text = ""
                
                if experiences and isinstance(experiences, list) and len(experiences) > 0:
                    # Build a text representation of experiences to use as context
                    for exp in experiences[:3]:  # Use up to 3 most recent experiences
                        if isinstance(exp, dict):
                            job_title = exp.get('job_title', '')
                            company = exp.get('company', '')
                            description = exp.get('description', '')
                            
                            if job_title and company:
                                experience_text += f"- {job_title} at {company}\n"
                                if description:
                                    # Add a short excerpt from the description
                                    excerpt = description[:150] + "..." if len(description) > 150 else description
                                    experience_text += f"  {excerpt}\n\n"
                
                # Also include skills if available
                skills = rewritten_cv.get('skills', [])
                skills_text = ""
                
                if skills and isinstance(skills, list) and len(skills) > 0:
                    skills_text = "Skills include: "
                    skill_names = []
                    
                    for skill in skills[:10]:  # Use up to 10 skills
                        if isinstance(skill, dict) and 'name' in skill:
                            skill_names.append(skill['name'])
                        elif isinstance(skill, str):
                            skill_names.append(skill)
                    
                    skills_text += ", ".join(skill_names)
                
                # Get personal info for context
                personal_info = rewritten_cv.get('personal_info', {})
                job_title = personal_info.get('job_title', '')
                industry = personal_info.get('industry', 'technology')
                
                # Generate a professional summary using LLM
                system_prompt = """
                You are an expert CV writer specializing in creating compelling professional summaries.
                Based on the provided experience and skills information, craft a concise and impactful
                professional summary (3-4 sentences) that highlights the candidate's strengths,
                experience level, and value proposition.
                
                Guidelines:
                1. Start with a strong professional identity statement
                2. Highlight key expertise areas and experience level
                3. Include relevant skills and accomplishments
                4. End with a value proposition
                5. Use active voice and powerful language
                6. Keep it under 100 words
                7. Make it ATS-friendly with industry keywords
                
                Only return the summary text, nothing else.
                """
                
                user_prompt = f"""
                Create a professional summary for a {job_title or 'professional'} in the {industry} industry.
                
                Experience:
                {experience_text}
                
                {skills_text}
                """
                
                try:
                    # Check if generate_response is a coroutine function and handle it appropriately
                    import inspect
                    import asyncio
                    
                    if inspect.iscoroutinefunction(self.generate_response):
                        # If it's async, we need to run it in an event loop
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            generated_summary = loop.run_until_complete(
                                self.generate_response(system_prompt, user_prompt)
                            )
                        finally:
                            loop.close()
                    else:
                        # If it's a regular function, just call it normally
                        generated_summary = self.generate_response(system_prompt, user_prompt)
                    
                    if generated_summary:
                        logger.info(f"Successfully generated professional summary")
                        # Add to the enhanced CV
                        enhanced_cv['professional_summary'] = generated_summary.strip()
                    else:
                        logger.warning("Failed to generate professional summary")
                except Exception as e:
                    logger.error(f"Error generating professional summary: {str(e)}")
            
            # Process each section of the CV
            for section_name, section_content in rewritten_cv.items():
                if section_name == 'personal_info':
                    # Don't modify personal info
                    enhanced_cv[section_name] = section_content
                    continue
                    
                # Skip empty sections
                if not section_content:
                    enhanced_cv[section_name] = section_content
                    continue
                
                # Enhance this section
                if isinstance(section_content, str):
                    # For string sections like professional_summary
                    system_prompt = f"""
                    You are an expert CV writer specializing in enhancing professional {section_name.replace('_', ' ')}.
                    Your task is to review and improve the following {section_name.replace('_', ' ')} section of a CV.
                    Focus on:
                    1. Using powerful action verbs and industry-specific keywords
                    2. Highlighting accomplishments with measurable results
                    3. Ensuring ATS compatibility and optimizing for keyword matching
                    4. Maintaining a professional and concise tone
                    5. Enhancing clarity and impact
                    
                    Only return the improved text, nothing else.
                    """
                    
                    user_prompt = f"Here is the {section_name.replace('_', ' ')} to improve:\n\n{section_content}"
                    
                    try:
                        # Check if generate_response is a coroutine function and handle it appropriately
                        import inspect
                        import asyncio
                        
                        if inspect.iscoroutinefunction(self.generate_response):
                            # If it's async, we need to run it in an event loop
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                improved_content = loop.run_until_complete(
                                    self.generate_response(system_prompt, user_prompt)
                                )
                            finally:
                                loop.close()
                        else:
                            # If it's a regular function, just call it normally
                            improved_content = self.generate_response(system_prompt, user_prompt)
                        
                        # Fallback to original if enhancement failed
                        enhanced_cv[section_name] = improved_content if improved_content else section_content
                    except Exception as e:
                        logger.error(f"Error enhancing {section_name}: {str(e)}")
                        
                elif isinstance(section_content, list):
                    # For list sections like experience, education, skills, etc.
                    enhanced_items = []
                    
                    for item in section_content:
                        if not isinstance(item, dict):
                            enhanced_items.append(item)
                            continue
                            
                        # Enhance each item based on section type
                        if section_name in ['experience', 'work_experience', 'jobs']:
                            # Enhance job descriptions
                            if 'description' in item and item['description']:
                                system_prompt = """
                                You are an expert CV writer specializing in enhancing professional job descriptions.
                                Your task is to improve the following job description to be more impactful for a CV.
                                Focus on:
                                1. Using powerful action verbs and industry-specific keywords
                                2. Highlighting accomplishments with measurable results
                                3. Ensuring ATS compatibility
                                4. Converting passive voice to active voice
                                5. Quantifying achievements where possible
                                
                                Only return the improved text, nothing else.
                                """
                                
                                user_prompt = f"Here is the job description to improve:\n\n{item['description']}"
                                
                                try:
                                    # Check if generate_response is a coroutine function and handle it appropriately
                                    import inspect
                                    import asyncio
                                    
                                    if inspect.iscoroutinefunction(self.generate_response):
                                        # If it's async, we need to run it in an event loop
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        try:
                                            improved_description = loop.run_until_complete(
                                                self.generate_response(system_prompt, user_prompt)
                                            )
                                        finally:
                                            loop.close()
                                    else:
                                        # If it's a regular function, just call it normally
                                        improved_description = self.generate_response(system_prompt, user_prompt)
                                    
                                    if improved_description:
                                        item['description'] = improved_description
                                except Exception as e:
                                    logger.error(f"Error enhancing job description: {str(e)}")
                        
                        elif section_name in ['education', 'qualifications']:
                            # Enhance education descriptions
                            if 'description' in item and item['description']:
                                system_prompt = """
                                You are an expert CV writer specializing in enhancing education sections.
                                Your task is to improve the following education description to be more impactful.
                                Focus on:
                                1. Highlighting relevant coursework and achievements
                                2. Emphasizing skills gained during education
                                3. Making the description more concise and impactful
                                
                                Only return the improved text, nothing else.
                                """
                                
                                user_prompt = f"Here is the education description to improve:\n\n{item['description']}"
                                
                                try:
                                    # Check if generate_response is a coroutine function and handle it appropriately
                                    import inspect
                                    import asyncio
                                    
                                    if inspect.iscoroutinefunction(self.generate_response):
                                        # If it's async, we need to run it in an event loop
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        try:
                                            improved_description = loop.run_until_complete(
                                                self.generate_response(system_prompt, user_prompt)
                                            )
                                        finally:
                                            loop.close()
                                    else:
                                        # If it's a regular function, just call it normally
                                        improved_description = self.generate_response(system_prompt, user_prompt)
                                    
                                    if improved_description:
                                        item['description'] = improved_description
                                except Exception as e:
                                    logger.error(f"Error enhancing education description: {str(e)}")
                        
                        enhanced_items.append(item)
                    
                    enhanced_cv[section_name] = enhanced_items
                else:
                    # For other types of content, keep as is
                    enhanced_cv[section_name] = section_content
            
            # Return the enhanced CV with the new CV ID
            return {
                'status': 'success',
                'message': 'CV enhanced successfully',
                'original_rewrite': initial_rewrite,
                'rewritten_cv': enhanced_cv,
                'new_cv_id': new_cv_id  # Include the new CV ID in the response
            }
            
        except Exception as e:
            logger.error(f"Error enhancing CV rewrite: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Error enhancing CV rewrite: {str(e)}',
                'rewritten_cv': initial_rewrite.get('rewritten_cv', initial_rewrite.get('improved_sections', {})),
                'new_cv_id': initial_rewrite.get('new_cv_id')  # Pass through the CV ID even if enhancement fails
            }

    async def segment_cv(self, text, timeout=60):
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
                segmented_text = await self.deepseek_service.segment_cv(text, timeout)
                
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
                segmented_text = await self.local_llama_service.generate_with_system_prompt(
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

    async def generate_response(self, system_prompt, user_prompt, max_retries=2):
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
                        result = await service.generate_with_system_prompt(system_prompt, user_prompt)
                    else:
                        # Fall back to basic format
                        formatted_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                        result = await service.improve_text(formatted_prompt)
                        
                    if result:
                        return result
                except Exception as e:
                    logger.error(f"{service.__class__.__name__} attempt {attempt+1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        # Last attempt failed, try next service
                        break
                    # Small delay before retry
                    await asyncio.sleep(1) 
        
        # All services failed
        logger.error("All LLM services failed to generate response")
        return ""

    async def _improve_section(self, section: str, content: Dict) -> Dict:
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
                mistral_result = await self.primary_service.improve_text(formatted_prompt)
                if mistral_result:
                    return {'original': content, 'improved': mistral_result}
            
            if hasattr(self, 'use_groq') and self.use_groq:
                groq_result = await self.fallback_service.improve_text(formatted_prompt)
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

def save_rewritten_cv_to_database(rewritten_cv_data, user, cv_writer_instance=None):
    """
    Save rewritten CV data to appropriate database tables
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Saving rewritten CV data for user {user.id}")
    
    # Log the structure of the rewritten CV data
    try:
        import json
        logger.info(f"Rewritten CV data keys: {list(rewritten_cv_data.keys())}")
        
        # Log a summary of the data structure
        data_summary = {}
        for key, value in rewritten_cv_data.items():
            if isinstance(value, list):
                data_summary[key] = f"List with {len(value)} items"
                if len(value) > 0:
                    sample_item = value[0]
                    if isinstance(sample_item, dict):
                        data_summary[f"{key}_sample_keys"] = list(sample_item.keys())
            elif isinstance(value, dict):
                data_summary[key] = f"Dict with {len(value)} keys"
                data_summary[f"{key}_keys"] = list(value.keys())
            elif isinstance(value, str):
                data_summary[key] = f"String with {len(value)} chars"
            else:
                data_summary[key] = f"Other type: {type(value)}"
        
        logger.info(f"Rewritten CV data structure: {json.dumps(data_summary, indent=2)}")
    except Exception as e:
        logger.error(f"Error logging data structure: {str(e)}")
    
    # Create CV Writer instance if not provided
    if not cv_writer_instance:
        logger.info("No CV Writer instance provided, creating new one")
        # First, check if user already has CvWriter instances and how many
        existing_cvs = CvWriter.objects.filter(user=user)
        cv_count = existing_cvs.count()
        
        if cv_count > 0:
            # Use the first CV instead of creating a new one if any exist
            logger.info(f"User has {cv_count} existing CVs, using the first one")
            cv_writer_instance = existing_cvs.first()
            cv_writer_instance.status = 'completed'
            cv_writer_instance.save()
        else:
            # Create a new one if none exist
            logger.info("Creating brand new CV for user")
            cv_writer_instance = CvWriter.objects.create(
                user=user,
                status='completed'
            )
    
    # Check if rewritten_cv_data contains expected keys
    if not rewritten_cv_data or not isinstance(rewritten_cv_data, dict):
        logger.error("Invalid rewritten CV data format")
        return None
    
    # Save professional summary (if present)
    try:
        professional_summary_text = None
        
        # Check for direct professional_summary field (string)
        if 'professional_summary' in rewritten_cv_data:
            if isinstance(rewritten_cv_data['professional_summary'], str):
                professional_summary_text = clean_ai_text(rewritten_cv_data['professional_summary'])
            elif isinstance(rewritten_cv_data['professional_summary'], dict) and 'summary' in rewritten_cv_data['professional_summary']:
                professional_summary_text = clean_ai_text(rewritten_cv_data['professional_summary']['summary'])
        
        # Check for nested professional_summary in summary field
        elif 'summary' in rewritten_cv_data and isinstance(rewritten_cv_data['summary'], str):
            professional_summary_text = clean_ai_text(rewritten_cv_data['summary'])
            
        # If we found a professional summary, save it
        if professional_summary_text:
            # First check if a summary already exists for this user and cv
            existing_summary = ProfessionalSummary.objects.filter(
                user=user,
                cv=cv_writer_instance
            ).first()
            
            if existing_summary:
                existing_summary.summary = professional_summary_text
                existing_summary.save()
            else:
                ProfessionalSummary.objects.create(
                    user=user,
                    cv=cv_writer_instance,
                    summary=professional_summary_text
                )
    except Exception as e:
        logger.error(f"Error saving professional summary: {str(e)}")
    
    # Save experience data (if present)
    try:
        if 'experience' in rewritten_cv_data and isinstance(rewritten_cv_data['experience'], list):
            logger.info(f"Processing {len(rewritten_cv_data['experience'])} experience items")
            
            # Use update_or_create approach instead of deleting existing records
            for exp_data in rewritten_cv_data['experience']:
                # Clean potential AI text in description
                if 'description' in exp_data:
                    exp_data['description'] = clean_ai_text(exp_data['description'])
                
                # Extract necessary fields with defaults
                company_name = exp_data.get('company_name', '') or exp_data.get('company', '')
                job_title = exp_data.get('job_title', '') or exp_data.get('title', '')
                
                # Skip this entry if company_name or job_title is empty
                if not company_name or not job_title:
                    logger.warning(f"Skipping experience entry with empty company or job title: {exp_data}")
                    continue
                
                # Clean up date fields
                start_date = exp_data.get('start_date', '')
                end_date = exp_data.get('end_date', '')
                description = exp_data.get('description', '')
                
                # Set default employment type if not provided
                employment_type = exp_data.get('employment_type', 'Full-time')
                
                # Set current flag based on end_date
                is_current = not end_date or (isinstance(end_date, str) and end_date.lower() == 'present')
                
                # Use update_or_create to update if exists, create if not
                try:
                    # Check for existing experience
                    existing_exp = Experience.objects.filter(
                        user=user,
                        company_name=company_name,
                        job_title=job_title
                    ).first()
                    
                    if existing_exp:
                        # Update existing experience
                        try:
                            # Try to set cv field if available
                            existing_exp.cv = cv_writer_instance
                        except Exception as field_error:
                            if "cv" not in str(field_error):
                                # Only log if it's not a missing field error
                                logger.warning(f"Could not set CV field on experience: {str(field_error)}")
                        
                        if description:
                            existing_exp.job_description = description
                        if start_date:
                            existing_exp.start_date = format_date_string(start_date)
                        if end_date and end_date.lower() != 'present':
                            existing_exp.end_date = format_date_string(end_date)
                        existing_exp.current = is_current
                        existing_exp.save()
                        logger.info(f"Updated existing experience: {company_name}, {job_title}")
                    else:
                        # Create new experience
                        try:
                            # Try with cv field first
                            Experience.objects.create(
                                user=user,
                                cv=cv_writer_instance,
                                company_name=company_name,
                                job_title=job_title,
                                start_date=format_date_string(start_date) if start_date else None,
                                end_date=format_date_string(end_date) if end_date and end_date.lower() != 'present' else None,
                                current=is_current,
                                job_description=description
                            )
                        except Exception as field_error:
                            # If cv field isn't available, try without it
                            if "Cannot resolve keyword 'cv'" in str(field_error):
                                logger.warning("CV field not found in Experience model, trying without it")
                                Experience.objects.create(
                                    user=user,
                                    company_name=company_name,
                                    job_title=job_title,
                                    start_date=format_date_string(start_date) if start_date else None,
                                    end_date=format_date_string(end_date) if end_date and end_date.lower() != 'present' else None,
                                    current=is_current,
                                    job_description=description
                                )
                            else:
                                # Re-raise other errors
                                raise
                        logger.info(f"Created new experience: {company_name}, {job_title}")
                except Exception as inner_e:
                    logger.error(f"Error processing experience entry: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing experience section: {str(e)}")
    
    # Also check for experiences in workExperience field (alternative field name)
    try:
        if 'workExperience' in rewritten_cv_data and isinstance(rewritten_cv_data['workExperience'], list):
            logger.info(f"Processing {len(rewritten_cv_data['workExperience'])} workExperience items")
            
            for exp_data in rewritten_cv_data['workExperience']:
                # Extract necessary fields with defaults
                company_name = exp_data.get('company_name', '') or exp_data.get('company', '')
                job_title = exp_data.get('job_title', '') or exp_data.get('title', '')
                
                # Skip this entry if company_name or job_title is empty
                if not company_name or not job_title:
                    logger.warning(f"Skipping workExperience entry with empty company or job title: {exp_data}")
                    continue
                
                # Clean description if present
                description = ''
                if 'description' in exp_data:
                    description = clean_ai_text(exp_data['description'])
                elif 'job_description' in exp_data:
                    description = clean_ai_text(exp_data['job_description'])
                
                # Format dates
                start_date = exp_data.get('start_date', '') or exp_data.get('startDate', '')
                end_date = exp_data.get('end_date', '') or exp_data.get('endDate', '')
                
                # Set current flag based on end_date
                is_current = not end_date or (isinstance(end_date, str) and end_date.lower() == 'present') or exp_data.get('current', False)
                
                try:
                    # Check for existing experience
                    existing_exp = Experience.objects.filter(
                        user=user,
                        company_name=company_name,
                        job_title=job_title
                    ).first()
                    
                    if existing_exp:
                        # Update existing experience
                        try:
                            # Try to set cv field if available
                            existing_exp.cv = cv_writer_instance
                        except Exception as field_error:
                            if "cv" not in str(field_error):
                                # Only log if it's not a missing field error
                                logger.warning(f"Could not set CV field on experience: {str(field_error)}")
                        
                        if description:
                            existing_exp.job_description = description
                        if start_date:
                            existing_exp.start_date = format_date_string(start_date)
                        if end_date and end_date.lower() != 'present':
                            existing_exp.end_date = format_date_string(end_date)
                        existing_exp.current = is_current
                        existing_exp.save()
                        logger.info(f"Updated existing experience from workExperience: {company_name}, {job_title}")
                    else:
                        # Create new experience
                        try:
                            # Try with cv field first
                            Experience.objects.create(
                                user=user,
                                cv=cv_writer_instance,
                                company_name=company_name,
                                job_title=job_title,
                                start_date=format_date_string(start_date) if start_date else None,
                                end_date=format_date_string(end_date) if end_date and end_date.lower() != 'present' else None,
                                current=is_current,
                                job_description=description
                            )
                        except Exception as field_error:
                            # If cv field isn't available, try without it
                            if "Cannot resolve keyword 'cv'" in str(field_error):
                                logger.warning("CV field not found in Experience model, trying without it")
                                Experience.objects.create(
                                    user=user,
                                    company_name=company_name,
                                    job_title=job_title,
                                    start_date=format_date_string(start_date) if start_date else None,
                                    end_date=format_date_string(end_date) if end_date and end_date.lower() != 'present' else None,
                                    current=is_current,
                                    job_description=description
                                )
                            else:
                                # Re-raise other errors
                                raise
                        logger.info(f"Created new experience from workExperience: {company_name}, {job_title}")
                except Exception as inner_e:
                    logger.error(f"Error processing workExperience entry: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing workExperience section: {str(e)}")
    
    # Save education data (if present)
    try:
        if 'education' in rewritten_cv_data and isinstance(rewritten_cv_data['education'], list):
            logger.info(f"Processing {len(rewritten_cv_data['education'])} education items")
            
            for edu_data in rewritten_cv_data['education']:
                # Log the education data for debugging
                logger.info(f"Processing education data: {edu_data}")
                
                # Extract necessary fields with defaults
                school_name = edu_data.get('school_name', '')
                
                # Check for alternative field names for school
                if not school_name and 'school' in edu_data:
                    school_name = edu_data.get('school', '')
                    logger.info(f"Using 'school' field instead of 'school_name': {school_name}")
                
                if not school_name and 'institution' in edu_data:
                    school_name = edu_data.get('institution', '')
                    logger.info(f"Using 'institution' field instead of 'school_name': {school_name}")
                
                # If still empty, provide a default school name
                if not school_name:
                    school_name = "Educational Institution"
                    logger.warning(f"Using default school name: {school_name}")
                
                degree = edu_data.get('degree', '')
                
                # Make sure field_of_study is not null
                field_of_study = edu_data.get('field', '')
                if not field_of_study and edu_data.get('field_of_study'):
                    field_of_study = edu_data.get('field_of_study')
                elif not field_of_study and degree:
                    # Try to extract field from degree if possible
                    field_of_study = degree
                elif not field_of_study:
                    # Default value if nothing else is available
                    field_of_study = "General"
                
                # Make sure degree has at least some value
                if not degree:
                    degree = "Degree"
                
                # Clean up date fields
                start_date = edu_data.get('start_date', '')
                end_date = edu_data.get('end_date', '')
                
                # Format for unique identification
                defaults = {
                    'field_of_study': field_of_study
                }
                
                # Add dates to defaults if they exist
                if start_date:
                    defaults['start_date'] = format_date_string(start_date)
                if end_date:
                    defaults['end_date'] = format_date_string(end_date)
                
                # Use update_or_create to update if exists, create if not
                try:
                    # Try to save with cv field first
                    try:
                        education, created = Education.objects.update_or_create(
                            user=user,
                            cv=cv_writer_instance,
                            school_name=school_name,
                            degree=degree,
                            defaults=defaults
                        )
                    except Exception as field_error:
                        # If cv field isn't available, try without it
                        if "Cannot resolve keyword 'cv'" in str(field_error):
                            logger.warning("CV field not found in Education model, trying without it")
                            education, created = Education.objects.update_or_create(
                                user=user,
                                school_name=school_name,
                                degree=degree,
                                defaults=defaults
                            )
                        else:
                            # Re-raise other errors
                            raise
                    
                    if created:
                        logger.info(f"Created new education record: {school_name}, {degree}")
                    else:
                        logger.info(f"Updated existing education record: {school_name}, {degree}")
                        
                except Exception as inner_e:
                    logger.error(f"Error processing education entry: {str(inner_e)}, Data: {edu_data}")
    except Exception as e:
        logger.error(f"Error processing education section: {str(e)}")
    
    # Save skills data (if present)
    try:
        if 'skills' in rewritten_cv_data:
            skills_data = rewritten_cv_data['skills']
            logger.info(f"Processing skills data: {type(skills_data)}")
            
            # Handle different formats - might be list of objects, list of strings, or single string
            if isinstance(skills_data, list):
                for skill_item in skills_data:
                    # Extract skill name and level based on format
                    if isinstance(skill_item, dict):
                        skill_name = skill_item.get('name', '') or skill_item.get('skill_name', '')
                        skill_level = skill_item.get('level', '') or skill_item.get('skill_level', '')
                    elif isinstance(skill_item, str):
                        skill_name = skill_item
                        skill_level = 'Intermediate'  # Default level
                    else:
                        continue  # Skip invalid items
                        
                    if not skill_name:
                        continue  # Skip empty skill names
                    
                    # Use default level if empty
                    if not skill_level:
                        skill_level = 'Intermediate'
                    
                    try:
                        # Look for existing skill first
                        existing_skill = Skill.objects.filter(
                            user=user,
                            skill_name=skill_name
                        ).first()
                        
                        if existing_skill:
                            # Update existing skill level
                            existing_skill.skill_level = skill_level
                            existing_skill.cv = cv_writer_instance  # Associate with this CV
                            existing_skill.save()
                            logger.info(f"Updated existing skill: {skill_name}, {skill_level}")
                        else:
                            # Create new skill
                            Skill.objects.create(
                                user=user,
                                cv=cv_writer_instance,  # Associate with CV
                                skill_name=skill_name,
                                skill_level=skill_level
                            )
                            logger.info(f"Created new skill: {skill_name}, {skill_level}")
                    except Exception as inner_e:
                        logger.error(f"Error processing skill: {str(inner_e)}")
            
            # Handle string format (comma or newline separated list)
            elif isinstance(skills_data, str):
                # Try to parse skills from text
                if '\n' in skills_data:
                    skill_items = skills_data.split('\n')
                else:
                    skill_items = skills_data.split(',')
                
                for skill_text in skill_items:
                    skill_text = skill_text.strip()
                    if not skill_text or len(skill_text) < 2:
                        continue  # Skip empty or very short items
                    
                    # Default level
                    skill_level = 'Intermediate'
                    
                    # Try to extract level if formatted as "Name - Level" or "Name (Level)"
                    if ' - ' in skill_text:
                        parts = skill_text.split(' - ')
                        skill_name = parts[0].strip()
                        if len(parts) > 1:
                            skill_level = parts[1].strip()
                    elif '(' in skill_text and ')' in skill_text:
                        open_paren = skill_text.find('(')
                        close_paren = skill_text.find(')')
                        if 0 < open_paren < close_paren:
                            skill_name = skill_text[:open_paren].strip()
                            skill_level = skill_text[open_paren+1:close_paren].strip()
                    else:
                        skill_name = skill_text
                    
                    try:
                        # Look for existing skill first
                        existing_skill = Skill.objects.filter(
                            user=user,
                            skill_name=skill_name
                        ).first()
                        
                        if existing_skill:
                            # Update existing skill level
                            existing_skill.skill_level = skill_level
                            existing_skill.cv = cv_writer_instance  # Associate with this CV
                            existing_skill.save()
                            logger.info(f"Updated existing skill from text: {skill_name}, {skill_level}")
                        else:
                            # Create new skill
                            Skill.objects.create(
                                user=user,
                                cv=cv_writer_instance,  # Associate with CV
                                skill_name=skill_name,
                                skill_level=skill_level
                            )
                            logger.info(f"Created new skill from text: {skill_name}, {skill_level}")
                    except Exception as inner_e:
                        logger.error(f"Error processing skill from text: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing skills section: {str(e)}")
    
    # Save languages data (if present)
    try:
        if 'languages' in rewritten_cv_data and isinstance(rewritten_cv_data['languages'], list):
            logger.info(f"Processing languages data")
            
            for lang_data in rewritten_cv_data['languages']:
                # Extract language name and proficiency
                if isinstance(lang_data, dict):
                    language_name = lang_data.get('language', '') or lang_data.get('name', '')
                    proficiency = lang_data.get('proficiency', '') or lang_data.get('level', '')
                elif isinstance(lang_data, str):
                    language_name = lang_data
                    proficiency = 'Intermediate'  # Default
                else:
                    continue  # Skip invalid items
                
                if not language_name:
                    continue  # Skip empty language names
                
                # Use default proficiency if empty
                if not proficiency:
                    proficiency = 'Intermediate'
                
                try:
                    # Look for existing language first
                    existing_lang = Language.objects.filter(
                        user=user,
                        language=language_name
                    ).first()
                    
                    if existing_lang:
                        # Update existing language
                        existing_lang.proficiency = proficiency
                        try:
                            # Try to set cv field if available
                            existing_lang.cv = cv_writer_instance
                        except Exception as field_error:
                            if "cv" not in str(field_error):
                                # Only log if it's not a missing field error
                                logger.warning(f"Could not set CV field on language: {str(field_error)}")
                        existing_lang.save()
                        logger.info(f"Updated existing language: {language_name}, {proficiency}")
                    else:
                        # Create new language
                        try:
                            # Try with cv field first
                            Language.objects.create(
                                user=user,
                                cv=cv_writer_instance,
                                language=language_name,
                                proficiency=proficiency
                            )
                        except Exception as field_error:
                            # If cv field isn't available, try without it
                            if "Cannot resolve keyword 'cv'" in str(field_error):
                                logger.warning("CV field not found in Language model, trying without it")
                                Language.objects.create(
                                    user=user,
                                    language=language_name,
                                    proficiency=proficiency
                                )
                            else:
                                # Re-raise other errors
                                raise
                        logger.info(f"Created new language: {language_name}, {proficiency}")
                except Exception as inner_e:
                    logger.error(f"Error processing language: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing languages section: {str(e)}")
    
    # Save certifications data (if present)
    try:
        if 'certifications' in rewritten_cv_data and isinstance(rewritten_cv_data['certifications'], list):
            logger.info(f"Processing certifications data")
            
            for cert_data in rewritten_cv_data['certifications']:
                # Extract certification details
                if isinstance(cert_data, dict):
                    cert_name = cert_data.get('name', '') or cert_data.get('certificate_name', '')
                    issuing_org = cert_data.get('issuer', '') or cert_data.get('issuing_organization', '')
                    
                    # Handle date field - convert empty strings to None
                    date_obtained = cert_data.get('date', '') or cert_data.get('date_obtained', '') or cert_data.get('year', '')
                    if not date_obtained or date_obtained.strip() == '':
                        date_obtained = None
                    else:
                        # Try to format the date if it's just a year
                        date_obtained = date_obtained.strip()
                        if len(date_obtained) == 4 and date_obtained.isdigit():
                            date_obtained = f"{date_obtained}-01-01"  # Convert year to full date
                    
                    certificate_link = cert_data.get('url', '') or cert_data.get('link', '')
                elif isinstance(cert_data, str):
                    cert_name = cert_data
                    issuing_org = ''
                    date_obtained = None
                    certificate_link = ''
                else:
                    continue  # Skip invalid items
                
                if not cert_name:
                    continue  # Skip empty cert names
                
                try:
                    # Look for existing certification first
                    existing_cert = Certification.objects.filter(
                        user=user,
                        certificate_name=cert_name
                    ).first()
                    
                    if existing_cert:
                        # Update existing certification
                        if issuing_org:
                            existing_cert.certificate_link = issuing_org
                        if date_obtained is not None:
                            existing_cert.certificate_date = date_obtained
                        if certificate_link:
                            existing_cert.certificate_link = certificate_link
                        try:
                            # Try to set cv field if available
                            existing_cert.cv = cv_writer_instance
                        except Exception as field_error:
                            if "cv" not in str(field_error):
                                # Only log if it's not a missing field error
                                logger.warning(f"Could not set CV field on certification: {str(field_error)}")
                        existing_cert.save()
                        logger.info(f"Updated existing certification: {cert_name}")
                    else:
                        # Create new certification
                        try:
                            # Try with cv field first
                            Certification.objects.create(
                                user=user,
                                cv=cv_writer_instance,
                                certificate_name=cert_name,
                                certificate_link=issuing_org,
                                certificate_date=date_obtained
                            )
                        except Exception as field_error:
                            # If cv field isn't available, try without it
                            if "Cannot resolve keyword 'cv'" in str(field_error):
                                logger.warning("CV field not found in Certification model, trying without it")
                                Certification.objects.create(
                                    user=user,
                                    certificate_name=cert_name,
                                    certificate_link=issuing_org,
                                    certificate_date=date_obtained
                                )
                            else:
                                # Re-raise other errors
                                raise
                        logger.info(f"Created new certification: {cert_name}")
                except Exception as inner_e:
                    logger.error(f"Error processing certification: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing certifications section: {str(e)}")
    
    # Save interests data (if present)
    try:
        if 'interests' in rewritten_cv_data and isinstance(rewritten_cv_data['interests'], list):
            logger.info(f"Processing interests data")
            
            for interest_data in rewritten_cv_data['interests']:
                # Extract interest name based on format
                if isinstance(interest_data, dict):
                    interest_name = interest_data.get('name', '') or interest_data.get('interest', '')
                elif isinstance(interest_data, str):
                    interest_name = interest_data
                else:
                    continue  # Skip invalid items
                
                if not interest_name:
                    continue  # Skip empty interest names
                
                try:
                    # Look for existing interest first
                    existing_interest = Interest.objects.filter(
                        user=user,
                        name=interest_name
                    ).first()
                    
                    if existing_interest:
                        # Just update the cv reference
                        try:
                            # Try to set cv field if available
                            existing_interest.cv = cv_writer_instance
                        except Exception as field_error:
                            if "cv" not in str(field_error):
                                # Only log if it's not a missing field error
                                logger.warning(f"Could not set CV field on interest: {str(field_error)}")
                        existing_interest.save()
                        logger.info(f"Updated existing interest: {interest_name}")
                    else:
                        # Create new interest
                        try:
                            # Try with cv field first
                            Interest.objects.create(
                                user=user,
                                cv=cv_writer_instance,
                                name=interest_name
                            )
                        except Exception as field_error:
                            # If cv field isn't available, try without it
                            if "Cannot resolve keyword 'cv'" in str(field_error):
                                logger.warning("CV field not found in Interest model, trying without it")
                                Interest.objects.create(
                                    user=user,
                                    name=interest_name
                                )
                            else:
                                # Re-raise other errors
                                raise
                        logger.info(f"Created new interest: {interest_name}")
                except Exception as inner_e:
                    logger.error(f"Error processing interest: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing interests section: {str(e)}")
    
    # Save references data (if present)
    try:
        if 'references' in rewritten_cv_data and isinstance(rewritten_cv_data['references'], list):
            logger.info(f"Processing references data")
            
            for ref_data in rewritten_cv_data['references']:
                # Extract reference details
                if isinstance(ref_data, dict):
                    ref_name = ref_data.get('name', '')
                    ref_title = ref_data.get('title', '') or ref_data.get('position', '')
                    ref_company = ref_data.get('company', '') or ref_data.get('organization', '')
                    ref_email = ref_data.get('email', '')
                    ref_phone = ref_data.get('phone', '') or ref_data.get('contact', '')
                    ref_type = ref_data.get('type', 'Professional')
                else:
                    continue  # Skip invalid items
                
                if not ref_name:
                    continue  # Skip references without a name
                
                try:
                    # Look for existing reference
                    existing_ref = Reference.objects.filter(
                        user=user,
                        name=ref_name,
                        company=ref_company
                    ).first()
                    
                    if existing_ref:
                        # Update existing reference
                        try:
                            # Try to set cv field if available
                            existing_ref.cv = cv_writer_instance
                        except Exception as field_error:
                            if "cv" not in str(field_error):
                                # Only log if it's not a missing field error
                                logger.warning(f"Could not set CV field on reference: {str(field_error)}")
                        if ref_title:
                            existing_ref.title = ref_title
                        if ref_email:
                            existing_ref.email = ref_email
                        if ref_phone:
                            existing_ref.phone = ref_phone
                        if ref_type:
                            existing_ref.reference_type = ref_type
                        existing_ref.save()
                        logger.info(f"Updated existing reference: {ref_name}")
                    else:
                        # Create new reference
                        try:
                            # Try with cv field first
                            Reference.objects.create(
                                user=user,
                                cv=cv_writer_instance,
                                name=ref_name,
                                title=ref_title or 'Not specified',
                                company=ref_company or 'Not specified',
                                email=ref_email or 'not@specified.com',
                                phone=ref_phone,
                                reference_type=ref_type
                            )
                        except Exception as field_error:
                            # If cv field isn't available, try without it
                            if "Cannot resolve keyword 'cv'" in str(field_error):
                                logger.warning("CV field not found in Reference model, trying without it")
                                Reference.objects.create(
                                    user=user,
                                    name=ref_name,
                                    title=ref_title or 'Not specified',
                                    company=ref_company or 'Not specified',
                                    email=ref_email or 'not@specified.com',
                                    phone=ref_phone,
                                    reference_type=ref_type
                                )
                            else:
                                # Re-raise other errors
                                raise
                        logger.info(f"Created new reference: {ref_name}")
                except Exception as inner_e:
                    logger.error(f"Error processing reference: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error processing references section: {str(e)}")
    
    # Return the CV writer instance
    return cv_writer_instance

# Create an async version of the function using sync_to_async
from asgiref.sync import sync_to_async

# This creates an async version of the synchronous function
save_rewritten_cv_to_database_async = sync_to_async(save_rewritten_cv_to_database)

def clean_ai_text(text):
    """Helper function to remove AI explanatory text from content"""
    if not isinstance(text, str):
        return text
            
    # Handle the specific patterns mentioned in the examples
    specific_start_patterns = [
        r"^Here is (?:an improved|a rewritten|the improved) (?:version of )?(?:the )?(?:professional summary|job description|summary|experience|education|certification|skills?|language):\s*",
        r"^Below is (?:an improved|a rewritten|the improved) (?:version of )?(?:the )?(?:professional summary|job description|summary|experience|education|certification|skills?|language):\s*",
        r"^I've (?:improved|rewritten|enhanced) (?:the )?(?:professional summary|job description|summary|experience|education|certification|skills?|language):\s*",
    ]
    
    for pattern in specific_start_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            # Remove the starting phrase
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            
    # Also look for this pattern in the middle of the text (e.g., "... content. Here is the improved job description:")
    middle_patterns = [
        r"\.\s*Here is (?:an improved|a rewritten|the improved) (?:version of )?(?:the )?(?:professional summary|job description|summary|experience|education|certification|skills?|language):\s*",
        r"\.\s*Below is (?:an improved|a rewritten|the improved) (?:version of )?(?:the )?(?:professional summary|job description|summary|experience|education|certification|skills?|language):\s*",
    ]
    
    for pattern in middle_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            # Split at the pattern and take only the content after it
            # This handles the case where we have real content, then an explanation phrase, then more real content
            parts = re.split(pattern, text, flags=re.IGNORECASE)
            if len(parts) > 1:
                text = parts[-1]  # Take the last part after all splits
        
    # Sometimes we just need to extract the first paragraph since that's the actual content
    paragraphs = text.split('\n\n')
    
    # Common explanation markers to detect
    explanation_markers = [
        "keyword", "action verb", "industry-specific", 
        "measurable result", "ats compat", "professional tone",
        "clarity", "impact", "explanation", "breakdown", 
        "analysis", "improvement", "enhance", "optimize"
    ]
    
    # Check for the simplest case - if we have a line that says "Keyword-rich action verbs:" or similar
    # just take everything before it
    for marker in explanation_markers:
        pattern = re.compile(f".*{marker}.*:", re.IGNORECASE)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if pattern.match(line):
                # Found a line that looks like an explanation header
                # Take everything before this line
                return '\n'.join(lines[:i]).strip()
    
    # Remove common AI explanation patterns at the beginning
    start_patterns = [
        r"^Sure,\s+here's\s+.*?:\s*",
        r"^Here's\s+.*?:\s*",
        r"^I've\s+.*?:\s*",
        r"^Below\s+is\s+.*?:\s*",
        r"^Here\s+is\s+.*?:\s*",
        r"^As\s+requested,\s+.*?:\s*",
    ]
    
    cleaned_text = text
    for pattern in start_patterns:
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
    
    # Check for bullet points - ANY bullet point could indicate we're in the explanation section
    # Look for the first bullet point and take everything before it
    bullet_pattern = r"\n[\*\-•]"
    bullet_match = re.search(bullet_pattern, cleaned_text)
    if bullet_match:
        # We found a bullet point - take everything before it
        cleaned_text = cleaned_text[:bullet_match.start()].strip()
        return cleaned_text
            
    # If we get here, we don't have simple markers or bullets
    # Just take the first paragraph, which is usually the main content
    if len(paragraphs) > 1:
        # Check if paragraphs after the first contain explanation markers
        contains_explanation = False
        for p in paragraphs[1:]:
            if any(marker.lower() in p.lower() for marker in explanation_markers):
                contains_explanation = True
                break
                    
        if contains_explanation:
            cleaned_text = paragraphs[0]
                
    # Remove quotes if they wrap the entire text
    cleaned_text = cleaned_text.strip('"\'')
    
    return cleaned_text.strip()

def format_date_string(date_str):
    """
    Format a date string to ensure it's in YYYY-MM-DD format for Django DateField.
    
    Args:
        date_str (str): Date string that might be in various formats
        
    Returns:
        str: Date string in YYYY-MM-DD format
    """
    import re
    
    # If it's already in YYYY-MM-DD format, return it
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # If it's just a year (e.g. "2017"), convert to YYYY-01-01
    if re.match(r'^\d{4}$', date_str):
        return f"{date_str}-01-01"
    
    # If it's a year and month (e.g. "2017-06"), convert to YYYY-MM-01
    if re.match(r'^\d{4}-\d{1,2}$', date_str):
        year, month = date_str.split('-')
        month = month.zfill(2)  # Ensure month is two digits
        return f"{year}-{month}-01"
    
    # If it's "Present" or similar, return None to indicate current
    if date_str.lower() in ('present', 'current', 'now'):
        return None
    
    # If it's month and year (e.g. "June 2017"), try to parse it
    month_names = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
        'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    # Try to extract month and year from formats like "June 2017" or "Jun 2017"
    month_year_match = re.search(r'(\w+)\s+(\d{4})', date_str, re.IGNORECASE)
    if month_year_match:
        month, year = month_year_match.groups()
        month = month.lower()
        if month in month_names:
            return f"{year}-{month_names[month]}-01"
    
    # Default to January 1st of the specified year if we can extract a year
    year_match = re.search(r'(\d{4})', date_str)
    if year_match:
        year = year_match.group(1)
        return f"{year}-01-01"
    
    # If we can't parse the date, return a default date
    logger.warning(f"Could not parse date string: {date_str}, using default date")
    return "2000-01-01"  # Default date as fallback
