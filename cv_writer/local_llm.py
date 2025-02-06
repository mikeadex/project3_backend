from llama_cpp import Llama
import os
import logging
import requests
import time
from typing import Dict, Optional, List, Any
from pathlib import Path
import json
from django.conf import settings

logger = logging.getLogger(__name__)

class BaseLLMService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def improve_text(self, section, content):
        raise NotImplementedError()

class LocalLLMService(BaseLLMService):
    def __init__(self, force_init=False):
        super().__init__(settings.CURRENT_LLM_CONFIG)
        self.model = None
        
        # Only initialize in development or if force_init is True
        is_development = not os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production')
        if is_development or force_init:
            self._initialize_model()
        
        self.prompts = {
            'professional_summary': """[INST] You are an expert CV writer. Improve this professional summary to be more impactful. Focus on years of experience, key achievements, core skills, and career objectives. Keep it concise (100-150 words). Use active voice and strong verbs. 

            Original summary:
            {content}

            Return only the improved summary: [/INST]""",
                        'experience': """[INST] You are an expert CV writer. Transform this job description into achievement-focused bullet points. Use strong action verbs, include metrics, and emphasize leadership impact. 

            Original description:
            {content}

            Return only the improved description: [/INST]""",
                        'skills': """[INST] You are an expert CV writer. Organize these skills into clear categories with proficiency levels. Format them as follows:
            Technical Skills: skill1 (Expert), skill2 (Advanced)
            Soft Skills: skill1, skill2
            Domain Knowledge: area1, area2

            Original skills:
            {content}

            Return only the categorized skills: [/INST]"""
                    }

    def _initialize_model(self):
        """Initialize the LLM model with optimized settings."""
        try:
            # Only initialize local model if provider is 'local'
            if self.config['provider'] == 'local':
                model_path = self.config['model_path']
                logger.info(f"Initializing local model from: {model_path}")
                
                # Create models directory if it doesn't exist
                models_dir = os.path.dirname(model_path)
                os.makedirs(models_dir, exist_ok=True)
                
                # Check if model exists
                if not os.path.exists(model_path):
                    error_msg = f"Model file not found at {model_path}. Please download the model."
                    logger.error(error_msg)
                    raise FileNotFoundError(error_msg)
                
                # Initialize with optimized settings
                self.model = Llama(
                    model_path=model_path,
                    n_ctx=4096,          # Increased context window
                    n_batch=1024,        # Larger batch size
                    n_threads=os.cpu_count(),  # Use all available threads
                    n_gpu_layers=-1      # Use all GPU layers if available
                )
                logger.info(f"Local model initialized successfully from {model_path}")
            
        except Exception as e:
            logger.error(f"Error initializing local model: {str(e)}")
            raise

    def _call_mistral_api(self, prompt: str, max_tokens: int = 500) -> str:
        api_key = self.config.get('mistral_api_key')
        if not api_key:
            raise ValueError("Mistral API key not configured")
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    'https://api.mistral.ai/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': 'mistral-medium',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': max_tokens
                    },
                    timeout=30  # 30-second timeout
                )
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
            
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Mistral API attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def _call_groq_llama_api(self, prompt: str, max_tokens: int = 500) -> str:
        """Fallback to Groq Llama API"""
        try:
            response = requests.post(
                'https://api.groq.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.config["fallback_api_key"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama3-70b-8192',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens
                }
            )
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise

    def improve_text(self, section: str, content: str, max_tokens: int = 500) -> Dict[str, str]:
        providers_map = {
            'mistral': self._call_mistral_api,
            'groq': self._call_groq_api,
            'huggingface': self._call_huggingface_api,
            'local': self._call_local_model
        }
        
        # Prepare section-specific prompt templates
        prompt_templates = {
            'professional_summary': """Improve this professional summary...""",
            'experience': """Transform this job description...""",
            'skills': """Organize these skills..."""
        }
        
        formatted_prompt = prompt_templates.get(section, "{content}").format(content=content)
        
        # Try providers in order
        for provider in self.providers:
            try:
                provider_func = providers_map.get(provider)
                if not provider_func:
                    continue
                
                improved_text = provider_func(formatted_prompt, max_tokens)
                
                return {
                    'original': content,
                    'improved': improved_text,
                    'provider': provider
                }
            
            except Exception as e:
                self.logger.warning(f"{provider.upper()} provider failed: {e}")
                continue
        
        raise RuntimeError("All LLM providers failed. Unable to improve text.")

    def _local_model_improve(self, formatted_prompt: str, section: str, max_tokens: int) -> str:
        """Improve text using local Llama model"""
        response = self.model(
            formatted_prompt,
            max_tokens=max_tokens,
            temperature=0.7,
            top_p=0.9,
            repeat_penalty=1.1,
            top_k=40,
            echo=False,
            stop=["</s>", "[INST]", "Return only", "Original", "I hope", "Let me know"]
        )
        
        # Extract text and post-process
        if response and 'choices' in response and len(response['choices']) > 0:
            text = response['choices'][0]['text'].strip()
            return self._post_process_text(text, section)

    def _post_process_text(self, text: str, section: str) -> str:
        """Advanced text post-processing"""
        logger.info(f"Raw LLM response: {text[:100]}...")
        
        # Remove common conversational artifacts
        artifacts = [
            "here's", "Here's", "Sure!", "sure!", 
            "improved version", "summary:", "description:", "skills:",
            "based on their categories:", "organized skills",
            "I hope this helps", "Let me know",
            "for the given information:",
            "bullet point version"
        ]
        
        # Remove everything before the actual content
        for phrase in ["here's", "Here's", "Sure"]:
            if phrase in text and ":" in text:
                text = text.split(":", 1)[1]
        
        # Clean up the text
        text = text.strip()
        for artifact in artifacts:
            text = text.replace(artifact, "")
        
        # Remove quotes if present
        text = text.strip('"').strip("'")
        
        # Format based on section
        if section == 'experience':
            # Split into bullet points if multiple sentences
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            # Remove redundant job title if it appears alone
            if len(sentences) > 1 and len(sentences[0].split()) <= 4:
                sentences = sentences[1:]
            # Clean up and format bullet points
            formatted_points = []
            for sentence in sentences:
                # Remove existing bullet points and asterisks
                point = sentence.lstrip('•').lstrip('*').lstrip('+').strip()
                if point:
                    # Remove "resulting in:" if it's at the end
                    if point.endswith('resulting in:'):
                        continue
                    formatted_points.append(f"• {point}")
            text = "\n".join(formatted_points)
        
        elif section == 'skills':
            categories = ['Technical Skills:', 'Soft Skills:', 'Domain Knowledge:']
            formatted_lines = []
            current_category = None
            
            for line in text.split('\n'):
                line = line.strip()
                # Check for category
                if any(cat.lower() in line.lower() for cat in categories):
                    for cat in categories:
                        if cat.lower() in line.lower():
                            current_category = cat
                            formatted_lines.append(f"\n{current_category}")
                            break
                elif line and current_category:
                    # Clean and add skills
                    skills = [skill.strip() for skill in line.split(',') if skill.strip()]
                    if skills:
                        formatted_lines.append("  " + ", ".join(skills))
            
            text = "\n".join(formatted_lines)
        
        return text
        
    def improve_section(self, section_type, content):
            """Improve a section of the CV with optimized prompting."""
            if not self.model:
                raise ValueError("Model not initialized")

            try:
                # Select appropriate prompt based on section type
                if section_type == 'professional_summary':
                    prompt = f"""As an expert CV writer, improve this professional summary while maintaining complete accuracy of experience and qualifications. Never add years of experience or specific technologies unless they are explicitly mentioned in the original text. Focus on strengthening the language and impact while keeping the facts unchanged.

                    Guidelines:
                    1. Keep all facts and experience levels exactly as stated
                    2. Improve the language and structure
                    3. Focus on potential and eagerness to learn for graduate profiles
                    4. Don't add specific technologies unless mentioned
                    5. Keep it concise and professional

                    Original summary: {content}
                    
                    Improved summary:"""
                    
                elif section_type == 'job_description':
                    prompt = f"""As an expert CV writer, enhance this job description to be more impactful and achievement-oriented. Focus on quantifiable results and specific contributions while maintaining complete accuracy.

                    Guidelines:
                    1. Start each bullet point with a strong action verb
                    2. Include metrics and specific achievements where present
                    3. Focus on impact and results, not just responsibilities
                    4. Highlight technical skills and tools actually used
                    5. Keep descriptions concise and achievement-focused
                    6. Never fabricate numbers or achievements
                    7. Maintain all factual information exactly as provided

                    Original description: {content}
                    
                    Improved description:"""
                    
                elif section_type == 'achievement':
                    prompt = f"""As an expert CV writer, enhance this achievement to be more impactful and results-oriented. Focus on the specific impact and value delivered while maintaining complete accuracy.

                    Guidelines:
                    1. Start with a powerful action verb
                    2. Emphasize quantifiable results where present
                    3. Highlight the specific impact on the business/project
                    4. Include relevant technical skills actually used
                    5. Structure as: Action → Task → Result
                    6. Never fabricate metrics or outcomes
                    7. Keep the achievement concise but detailed

                    Original achievement: {content}
                    
                    Improved achievement:"""
                else:
                    raise ValueError(f"Unsupported section type: {section_type}")

                # Generate with optimized parameters
                logger.info("Generating improvement")
                response = self.model.create_completion(
                    prompt,
                    max_tokens=300,        # Limit output length
                    temperature=0.7,       # Balanced creativity
                    top_p=0.9,            # Focused sampling
                    repeat_penalty=1.1,    # Prevent repetition
                    stop=["Original", "\n\n"],  # Clear stop conditions
                )

                # Extract and clean the response
                improved_text = response['choices'][0]['text'].strip()
                
                # Basic validation
                if len(improved_text) < 10:
                    raise ValueError("Generated text is too short")

                # Validate no fabricated experience is added
                if "years of experience" in improved_text.lower() and "years of experience" not in content.lower():
                    raise ValueError("Generated text contains fabricated experience")

                # Validate no fabricated metrics
                if any(metric in improved_text.lower() and metric not in content.lower() 
                    for metric in ['%', 'percent', 'increased', 'decreased', 'reduced', 'improved by']):
                    raise ValueError("Generated text contains fabricated metrics")

                return {
                    'improved': improved_text,
                    'original': content
                }

            except Exception as e:
                logger.error(f"Error in improve_section: {str(e)}")
                raise

    def rewrite_cv(self, cv_data):
        """Rewrite the entire CV to be more professional and impactful."""
        improved_cv = {}
        for section, content in cv_data.items():
            if section in ['professional_summary', 'experience', 'skills']:
                improved_cv[section] = self.improve_text(section, content)
        return improved_cv
    
    def _format_experiences(self, experiences):
        """Format experiences for the prompt."""
        if not experiences:
            return ""

        formatted = []
        for exp in experiences:
            # Safely extract experience details
            job_title = exp.get('job_title', '')
            company = exp.get('company_name', '')
            position = exp.get('position', '')
            start_date = exp.get('startDate', '')
            end_date = exp.get('endDate', '')
            job_description = exp.get('job_description', '')
            achievements = exp.get('achievements', [])

            formatted_exp = f"{job_title} at {company}"
            if position:
                formatted_exp += f" - {position}"
            formatted_exp += f" ({start_date} - {end_date})"
            if job_description:
                formatted_exp += f"\n{job_description}"
            if achievements:
                formatted_exp += "\n" + "\n".join(f"• {achievement}" for achievement in achievements)
            
            formatted.append(formatted_exp)
        
        return "\n\n".join(formatted)
        

    def _format_education(self, education):
        """Format education for the prompt."""
        if not education:
            return ""
            
        formatted = []
        for edu in education:
            formatted.append(f"""
            Institution: {edu.get('school_name', '')}
            Degree: {edu.get('degree', '')}
            Field_Of_Study: {edu.get('field_of_study', '')}
            Duration: {edu.get('startDate', '')} - {edu.get('endDate', '')}
            Details: {edu.get('details', '')}
            """)
        return "\n".join(formatted)

    def _parse_cv_sections(self, cv_text):
        """Parse the rewritten CV text back into structured sections."""
        sections = {
            'professional_summary': '',
            'experiences': [],
            'skills': {
                'Technical Skills': [],
                'Soft Skills': [],
                'Domain Knowledge': []
            },
            'education': []
        }

        current_section = None
        current_skill_category = None

        for line in cv_text.split('\n'):
            line = line.strip()
            
            # Detect section changes
            if 'professional summary' in line.lower():
                current_section = 'professional_summary'
                continue
            elif 'experience' in line.lower():
                current_section = 'experience'
                continue
            elif 'skills' in line.lower():
                current_section = 'skills'
                continue
            elif 'education' in line.lower():
                current_section = 'education'
                continue

            # Populate sections based on current context
            if current_section == 'professional_summary':
                if line and not line.lower().startswith(('technical skills', 'soft skills', 'domain knowledge')):
                    sections['professional_summary'] += line + ' '

            elif current_section == 'experience':
                if line.startswith('•'):
                    sections['experiences'].append(line.lstrip('•').strip())

            elif current_section == 'skills':
                # Detect skill categories
                if any(cat in line for cat in ['Technical Skills', 'Soft Skills', 'Domain Knowledge']):
                    for cat in ['Technical Skills', 'Soft Skills', 'Domain Knowledge']:
                        if cat in line:
                            current_skill_category = cat
                            break
                elif current_skill_category and line:
                    # Split skills, handling potential proficiency levels
                    skills = [skill.strip() for skill in line.split(',')]
                    sections['skills'][current_skill_category].extend(skills)

            elif current_section == 'education':
                if line:
                    sections['education'].append(line)

        # Post-processing
        sections['professional_summary'] = sections['professional_summary'].strip()
        
        # Clean up skills, removing empty categories
        sections['skills'] = {
            k: list(set(v)) for k, v in sections['skills'].items() if v
        }

        return sections

    def _parse_experience(self, text):
        """Parse an experience section into structured data."""
        lines = text.split('\n')
        exp = {}
        
        for line in lines:
            line = line.strip()
            if 'Company:' in line:
                exp['company'] = line.replace('Company:', '').strip()
            elif 'Position:' in line:
                exp['position'] = line.replace('Position:', '').strip()
            elif 'Duration:' in line:
                duration = line.replace('Duration:', '').strip()
                dates = duration.split('-')
                if len(dates) == 2:
                    exp['startDate'] = dates[0].strip()
                    exp['endDate'] = dates[1].strip()
            elif 'Description:' in line:
                exp['job_description'] = line.replace('Description:', '').strip()
            elif 'Achievements:' in line:
                exp['achievements'] = line.replace('Achievements:', '').strip()
                
        return exp if exp else None

    def _parse_education(self, text):
        """Parse an education section into structured data."""
        lines = text.split('\n')
        edu = {}
        
        for line in lines:
            line = line.strip()
            if 'Institution:' in line:
                edu['institution'] = line.replace('Institution:', '').strip()
            elif 'Degree:' in line:
                edu['degree'] = line.replace('Degree:', '').strip()
            elif 'Duration:' in line:
                duration = line.replace('Duration:', '').strip()
                dates = duration.split('-')
                if len(dates) == 2:
                    edu['startDate'] = dates[0].strip()
                    edu['endDate'] = dates[1].strip()
            elif 'Details:' in line:
                edu['details'] = line.replace('Details:', '').strip()
                
        return edu if edu else None

class ResilientLLMService:
    def __init__(self, config: Dict[str, Any] = None, force_init: bool = False):
        """
        Initialize a resilient LLM service with multiple providers
        
        :param config: Optional configuration dictionary for LLM providers
        :param force_init: Force initialization even without API keys
        """
        # Default configuration
        self.config = {
            'providers': {
                'mistral': {
                    'url': 'https://api.mistral.ai/v1/chat/completions',
                    'api_key': os.getenv('MISTRAL_API_KEY'),
                    'model': 'mistral-medium'
                },
                'groq': {
                    'url': 'https://api.groq.com/openai/v1/chat/completions',
                    'api_key': os.getenv('GROQ_API_KEY'),
                    'models': [
                        'llama3-8b-8192',     # Default
                        'llama3-70b-8192',    # High-performance option
                        'mixtral-8x7b-32768'  # Alternative model
                    ]
                }
            },
            'max_retries': 3,
            'timeout': 30
        }
        
        # Override default config with provided config
        if config:
            self.config.update(config)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Validate API keys or check force_init
        if not force_init:
            missing_keys = [
                provider for provider, details in self.config['providers'].items()
                if not details.get('api_key')
            ]
            
            if missing_keys:
                raise ValueError(f"Missing API keys for providers: {', '.join(missing_keys)}")

    def _call_mistral_api(self, prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Call Mistral API with robust error handling
        
        :param prompt: Input text prompt
        :param max_tokens: Maximum tokens to generate
        :return: API response dictionary
        """
        provider_config = self.config['providers']['mistral']
        
        for attempt in range(self.config['max_retries']):
            try:
                response = requests.post(
                    provider_config['url'],
                    headers={
                        'Authorization': f'Bearer {provider_config["api_key"]}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': provider_config['model'],
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': max_tokens
                    },
                    timeout=self.config['timeout']
                )
                
                response.raise_for_status()
                result = response.json()
                
                return {
                    'status': 'success',
                    'provider': 'mistral',
                    'model': provider_config['model'],
                    'response': result['choices'][0]['message']['content']
                }
            
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Mistral API attempt {attempt + 1} failed: {e}")
                if attempt == self.config['max_retries'] - 1:
                    return {
                        'status': 'error',
                        'provider': 'mistral',
                        'message': str(e)
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def _call_groq_api(self, prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Call Groq API with model fallback and robust error handling
        
        :param prompt: Input text prompt
        :param max_tokens: Maximum tokens to generate
        :return: API response dictionary
        """
        provider_config = self.config['providers']['groq']
        
        for model in provider_config['models']:
            for attempt in range(self.config['max_retries']):
                try:
                    response = requests.post(
                        provider_config['url'],
                        headers={
                            'Authorization': f'Bearer {provider_config["api_key"]}',
                            'Content-Type': 'application/json'
                        },
                        json={
                            'model': model,
                            'messages': [{'role': 'user', 'content': prompt}],
                            'max_tokens': max_tokens
                        },
                        timeout=self.config['timeout']
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    return {
                        'status': 'success',
                        'provider': 'groq',
                        'model': model,
                        'response': result['choices'][0]['message']['content']
                    }
                
                except requests.exceptions.RequestException as e:
                    self.logger.warning(f"Groq API attempt with {model} failed: {e}")
                    if attempt == self.config['max_retries'] - 1:
                        break
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        return {
            'status': 'error',
            'provider': 'groq',
            'message': 'All Groq models failed'
        }
    
    def improve_text(self, section: str, content: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Improve text using multiple LLM providers with fallback mechanism
        
        :param section: Type of section being improved
        :param content: Text content to improve
        :param max_tokens: Maximum tokens to generate
        :return: Improved text dictionary
        """
        # Prompt templates for different sections
        prompt_templates = {
            'professional_summary': f"Improve this professional summary: {content}",
            'experience': f"Transform this job description: {content}",
            'skills': f"Categorize and enhance these skills: {content}",
            'default': content
        }
        
        # Select appropriate prompt template
        prompt = prompt_templates.get(section, prompt_templates['default'])
        
        # Try Mistral first
        mistral_result = self._call_mistral_api(prompt, max_tokens)
        if mistral_result['status'] == 'success':
            return mistral_result
        
        # Fallback to Groq
        groq_result = self._call_groq_api(prompt, max_tokens)
        if groq_result['status'] == 'success':
            return groq_result
        
        # If all providers fail
        return {
            'status': 'error',
            'message': 'All LLM providers failed to improve text',
            'original_content': content
        }

    def improve_section(self, section: str, content: str, max_tokens: int = 500) -> str:
        """
        Improve a specific section of text, maintaining compatibility with previous implementation
        
        :param section: Type of section being improved
        :param content: Text content to improve
        :param max_tokens: Maximum tokens to generate
        :return: Improved text string
        """
        self.logger.info(f"Attempting to improve {section} section")
        
        # Use improve_text method and return just the response
        result = self.improve_text(section, content, max_tokens)
        
        if result['status'] == 'success':
            # Clean and validate the response
            improved_text = result['response'].strip()
            
            # Remove any leading/trailing quotes or unnecessary prefixes
            if improved_text.startswith('"') and improved_text.endswith('"'):
                improved_text = improved_text[1:-1].strip()
            
            # Remove any "Improved Summary:" or similar prefixes
            for prefix in ['Improved Summary:', 'Improved:', 'Summary:', 'Result:']:
                if improved_text.startswith(prefix):
                    improved_text = improved_text[len(prefix):].strip()
            
            # Validate the improved text
            if len(improved_text) > 10:
                self.logger.info(f"Successfully improved {section} section using {result['provider']} provider")
                return improved_text
        
        # Fallback to original content if improvement fails
        self.logger.warning(f"Failed to improve {section} section: {result.get('message', 'Unknown error')}")
        return content

# Optional: Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
