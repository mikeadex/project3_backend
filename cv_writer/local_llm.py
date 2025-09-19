import os
import logging
import requests
import time
from typing import Dict, Optional, List, Any
from pathlib import Path
import json
from django.conf import settings

# Conditional import for llama_cpp - fallback gracefully if not available
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("llama_cpp not available. Local LLM functionality will be disabled.")
    Llama = None
    LLAMA_CPP_AVAILABLE = False

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
            'professional_summary': self._improve_professional_summary_prompt,
            'experience': self._improve_experience_prompt,
            'skills': self._improve_skills_prompt
        }

    def _initialize_model(self):
        """Initialize the LLM model with optimized settings."""
        try:
            # Check if llama_cpp is available
            if not LLAMA_CPP_AVAILABLE:
                logger.warning("llama_cpp not available. Local LLM will be disabled.")
                return
            
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
                if LLAMA_CPP_AVAILABLE and Llama:
                    self.model = Llama(
                        model_path=model_path,
                        n_ctx=4096,          # Increased context window
                        n_batch=1024,        # Larger batch size
                        n_threads=os.cpu_count(),  # Use all available threads
                        n_gpu_layers=-1      # Use all GPU layers if available
                    )
                    logger.info(f"Local model initialized successfully from {model_path}")
                else:
                    logger.error("Cannot initialize model: llama_cpp not available")
                    return
            
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
            'professional_summary': self.prompts['professional_summary'],
            'experience': self.prompts['experience'],
            'skills': self.prompts['skills']
        }
        
        formatted_prompt = self.prompts.get(section, "{content}").format(content=content)
        
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
        if not self.model or not LLAMA_CPP_AVAILABLE:
            raise ValueError("Local model not available or llama_cpp not installed")
            
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
                elif current_category and line:
                    # Clean and add skills
                    skills = [skill.strip() for skill in line.split(',') if skill.strip()]
                    if skills:
                        formatted_lines.append("  " + ", ".join(skills))
            
            text = "\n".join(formatted_lines)
        
        return text
        
    def improve_section(self, section_type, content):
        """Improve a section of the CV with optimized prompting."""
        # Pre-processing for professional summary
        if section_type == 'professional_summary':
            # Remove common opening phrases
            content = content.replace('As a ', '', 1)  # Remove first occurrence
            content = content.replace('As an ', '', 1)  # Handle 'As an' case
            content = content.replace('A seasoned ', '', 1)  # Handle 'A seasoned' case
            content = content.strip()  # Remove leading/trailing whitespace

        if not self.model or not LLAMA_CPP_AVAILABLE:
            raise ValueError("Model not initialized or llama_cpp not available")

        try:
            # Select appropriate prompt based on section type
            if section_type == 'professional_summary':
                prompt = self.prompts['professional_summary']
            elif section_type == 'experience':
                prompt = self.prompts['experience']
            elif section_type == 'skills':
                prompt = self.prompts['skills']
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
        """
        Rewrite the entire CV with better structured context integration and awareness
        of different sections to ensure a cohesive result.
        
        Args:
            cv_data (dict): Dictionary containing CV sections and their content
            
        Returns:
            dict: Dictionary with original and rewritten CV data
        """
        try:
            # Extract and structure all relevant information
            structured_cv = {
                "professional_summary": cv_data.get("professional_summary", ""),
                "personal_info": {
                    "name": cv_data.get("name", ""),
                    "title": cv_data.get("title", ""),
                    "email": cv_data.get("email", ""),
                    "phone": cv_data.get("phone", ""),
                    "location": cv_data.get("location", ""),
                    "linkedin": cv_data.get("linkedin", "")
                },
                "experiences": self._format_experiences(cv_data.get("experiences", [])),
                "education": self._format_education(cv_data.get("education", [])),
                "skills": cv_data.get("skills", []),
                "certifications": cv_data.get("certifications", []),
                "languages": cv_data.get("languages", [])
            }
            
            # Process each section independently with appropriate prompts
            improved_sections = {}
            
            # Improve professional summary with awareness of experience and skills
            if structured_cv["professional_summary"]:
                context = f"""
                JOB TITLE/INDUSTRY: {structured_cv["personal_info"]["title"]}
                
                KEY SKILLS: {', '.join(structured_cv["skills"][:10] if isinstance(structured_cv["skills"], list) else [])}
                
                MAIN EXPERIENCE AREAS: {structured_cv["experiences"][:500] if structured_cv["experiences"] else ""}
                """
                
                professional_summary_prompt = f"""[INST] PROFESSIONAL SUMMARY OPTIMIZATION

CANDIDATE CONTEXT:
{context}

ORIGINAL SUMMARY:
{structured_cv["professional_summary"]}

Create a powerful, concise professional summary (3-5 sentences) that:
1. Highlights the most relevant skills and experience
2. Uses strong action verbs and industry-appropriate language
3. Balances technical expertise with transferable skills
4. Avoids clichés and generic language
5. Demonstrates clear value proposition

RETURN ONLY: An optimized professional summary. [/INST]"""

                summary_result = self.improve_text("professional_summary", professional_summary_prompt)
                improved_sections["professional_summary"] = summary_result.get("improved", structured_cv["professional_summary"])
            
            # Improve experience entries with awareness of skills
            if structured_cv["experiences"]:
                skills_context = ', '.join(structured_cv["skills"][:15] if isinstance(structured_cv["skills"], list) else [])
                experience_prompt = f"""[INST] WORK EXPERIENCE OPTIMIZATION

CANDIDATE SKILLS CONTEXT:
{skills_context}

WORK EXPERIENCE TO OPTIMIZE:
{structured_cv["experiences"]}

Transform this work experience into achievement-focused bullet points that:
1. Begin each bullet with strong action verbs
2. Include specific metrics and results where available
3. Highlight relevant skills from the context
4. Focus on business impact and leadership
5. Remove redundancies and passive language

RETURN ONLY: Optimized work experience bullet points organized by position. [/INST]"""

                experience_result = self.improve_text("experience", experience_prompt)
                improved_sections["experiences"] = experience_result.get("improved", structured_cv["experiences"])
            
            # Improve skills with awareness of experience
            if structured_cv["skills"]:
                experience_summary = structured_cv["experiences"][:300] if structured_cv["experiences"] else ""
                skills_prompt = f"""[INST] SKILLS SECTION OPTIMIZATION

EXPERIENCE CONTEXT:
{experience_summary}

SKILLS TO ORGANIZE:
{', '.join(structured_cv["skills"]) if isinstance(structured_cv["skills"], list) else structured_cv["skills"]}

Categorize and enhance these skills into a structured format that:
1. Groups related skills into logical categories (Technical, Soft Skills, Domain Knowledge)
2. Prioritizes skills most relevant to the experience context
3. Adds appropriate proficiency levels (Expert, Advanced, Intermediate)
4. Removes redundant or basic skills
5. Ensures consistency in formatting and capitalization

RETURN ONLY: Organized skills section with clear categories and proficiency levels. [/INST]"""

                skills_result = self.improve_text("skills", skills_prompt)
                improved_sections["skills"] = skills_result.get("improved", structured_cv["skills"])
            
            # Create a cohesive CV with improved sections
            return {
                "original": cv_data,
                "rewritten": improved_sections
            }
        
        except Exception as e:
            logger.error(f"Error rewriting CV: {str(e)}")
            # Return original data if rewriting fails
            return {
                "original": cv_data,
                "rewritten": cv_data,
                "error": str(e)
            }
    
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
                if any(cat in line for cat in ['Technical Skills:', 'Soft Skills:', 'Domain Knowledge:']):
                    for cat in ['Technical Skills:', 'Soft Skills:', 'Domain Knowledge:']:
                        if cat in line:
                            current_skill_category = cat
                            break
                elif current_skill_category and line:
                    # Clean and add skills
                    skills = [skill.strip() for skill in line.split(',') if skill.strip()]
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

    def _improve_professional_summary_prompt(self, content):
        """
        Generate a versatile prompt for improving professional summaries across different career types.
        
        Args:
            content (str): Original professional summary text
        
        Returns:
            str: Improved professional summary prompt
        """
        return f"""[INST] PROFESSIONAL SUMMARY OPTIMIZATION

CORE TRANSFORMATION GOAL:
- Create a concise, impactful professional summary that effectively showcases qualifications
- Target 3-5 sentences maximum (100-150 words)
- Maintain authentic career narrative and professional voice

OPTIMIZATION GUIDELINES:

1. NARRATIVE STRUCTURE
   * Maintain the original professional context and experience level
   * Create a logical flow: skills → experience → value proposition → career goal
   * Balance technical expertise with transferable skills
   * Include appropriate years of experience if mentioned in original

2. LANGUAGE QUALITY
   - Use powerful, precise action verbs appropriate to the profession
   - Avoid clichés and generic language ("team player", "detail-oriented")
   - Convert passive language to active voice
   - Focus on specific achievements rather than general responsibilities
   - Include relevant industry keywords for ATS optimization

3. CONTENT FOCUS
   - Emphasize most relevant skills and achievements for current career trajectory
   - Highlight unique selling points that differentiate from competitors
   - Include measurable impacts and results where available
   - Showcase relevant technical expertise and methodologies
   - Demonstrate soft skills through specific examples rather than generic claims

4. PROFESSIONAL TONE
   - Match writing style to industry expectations
   - Maintain appropriate level of formality
   - Project confidence without arrogance
   - Avoid unnecessary jargon unless standard in the field
   - Ensure proper grammar, syntax, and punctuation

Original Professional Summary:
{content}

RETURN ONLY: An optimized, concise professional summary that maintains the authentic career narrative while enhancing impact and clarity. [/INST]"""


    def _improve_experience_prompt(self, content):
        """
        Generate a versatile prompt for improving work experience descriptions.
        
        Args:
            content (str): Original experience description
            
        Returns:
            str: Improved experience prompt
        """
        return f"""[INST] WORK EXPERIENCE OPTIMIZATION

CORE TRANSFORMATION GOAL:
- Transform job descriptions into achievement-focused bullet points
- Showcase specific contributions, skills, and measurable results
- Create a compelling narrative of professional growth and competence

OPTIMIZATION GUIDELINES:

1. BULLET POINT STRUCTURE
   * Begin each bullet with a strong, relevant action verb
   * Focus on accomplishments rather than just responsibilities
   * Present in order of importance/relevance, not chronologically
   * Keep each bullet to 1-2 lines for readability
   * Ensure each bullet stands alone as a complete thought

2. CONTENT ENHANCEMENT
   - Include specific metrics and quantifiable results where possible (%, $, time saved)
   - Highlight leadership, collaboration, and initiative
   - Demonstrate problem-solving abilities with specific examples
   - Show progression and growth in responsibilities
   - Include relevant technologies, methodologies, and tools used

3. LANGUAGE OPTIMIZATION
   - Eliminate first-person pronouns (I, me, my)
   - Use present tense for current positions, past tense for previous roles
   - Vary action verbs to avoid repetition
   - Remove filler words and unnecessary adverbs
   - Incorporate relevant industry keywords for ATS optimization

4. TECHNICAL PRECISION
   - Use proper terminology for tools, technologies, and methodologies
   - Be specific about technical skills applied in each role
   - Balance technical details with business impact
   - Include certifications or specialized training if relevant
   - Mention specific projects or initiatives by name when appropriate

Original job description:
{content}

RETURN ONLY: A set of 3-5 optimized, achievement-focused bullet points that effectively showcase the value and impact delivered in this role. [/INST]"""


    def _improve_skills_prompt(self, content):
        """
        Generate a versatile prompt for organizing and improving skills sections.
        
        Args:
            content (str): Original skills content
            
        Returns:
            str: Improved skills prompt
        """
        return f"""[INST] SKILLS SECTION OPTIMIZATION

CORE TRANSFORMATION GOAL:
- Organize skills into logical, scannable categories
- Prioritize most relevant and in-demand skills
- Present proficiency levels where appropriate
- Balance technical skills with soft skills and domain knowledge

OPTIMIZATION GUIDELINES:

1. CATEGORIZATION STRUCTURE
   * Group similar skills into meaningful categories
   * Prioritize categories based on relevance to target roles
   * Use standard industry terminology for category names
   * Create 3-5 main categories maximum for readability
   * Place most relevant technical skills first

2. SKILL SELECTION & PRIORITIZATION
   - Focus on current, in-demand skills in the industry
   - Include both technical and transferable skills
   - Remove outdated or overly basic skills
   - Add proficiency levels for technical skills (Expert, Advanced, Intermediate)
   - Ensure skills mentioned align with experience described elsewhere in CV

3. FORMATTING RECOMMENDATIONS
   - Present in clean, scannable format
   - Use consistent format across all categories
   - List most advanced/relevant skills first in each category
   - Group related technologies/tools together
   - Include soft skills that differentiate from competition

4. TECHNICAL PRECISION
   - Use proper capitalization for technologies, languages, and tools
   - Include version numbers only if relevant
   - Specify frameworks and specialized tools within broader categories
   - Use industry-standard terminology and abbreviations
   - Avoid vague skills like "Microsoft Office" in favor of specifics

Original skills:
{content}

RETURN ONLY: An organized skills section with logical categories and proper formatting, optimized for both human readability and ATS scanning. Use this format:

Technical Skills: skill1 (Expert), skill2 (Advanced), skill3 (Intermediate)
Soft Skills: skill1, skill2, skill3
Domain Knowledge: domain1, domain2, domain3 [/INST]"""

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
        
        # Initialize the local service to use its formatting methods
        self.local_service = LocalLLMService(force_init=False)
        
        # Validate API keys or check force_init
        if not force_init:
            missing_keys = [
                provider for provider, details in self.config['providers'].items()
                if not details.get('api_key')
            ]
            
            if missing_keys:
                self.logger.warning(f"Missing API keys for providers: {', '.join(missing_keys)}")

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
        # Enhanced prompt templates for ATS-ready, compelling content
        prompt_templates = {
            'professional_summary': f"""Transform this professional summary into an ATS-optimized, compelling statement that will grab recruiters' attention.

REQUIREMENTS:
- Use powerful action verbs and industry keywords
- Quantify achievements where possible
- Show clear value proposition to employers
- Keep it concise (3-4 sentences)
- Make it sound confident and professional
- Include relevant skills and experience level

Original summary: {content}

Return ONLY the improved professional summary:""",

            'experience': f"""Transform this job experience into compelling, ATS-optimized bullet points that showcase achievements and impact.

REQUIREMENTS:
- Start each bullet point with strong action verbs (Managed, Developed, Implemented, etc.)
- Quantify results where possible (percentages, numbers, timeframes)
- Focus on achievements, not just job duties
- Use industry-relevant keywords
- Show progression and growth
- Make it compelling to recruiters
- Format as clean bullet points

Original experience: {content}

Return ONLY the improved experience bullet points:""",

            'skills': f"""Organize and enhance these skills into professional categories with proper skill levels.

REQUIREMENTS:
- Group related skills into logical categories (Technical, Software, Communication, etc.)
- Use industry-standard skill names
- Assign realistic proficiency levels (Beginner, Intermediate, Advanced, Expert)
- Remove duplicate or redundant skills
- Add relevant skills that are commonly expected
- Make it ATS-friendly with proper keywords

Original skills: {content}

Return ONLY the organized skills in this format:
Category: Skill Name (Proficiency Level)""",

            'education': f"""Enhance this education section with proper professional formatting and relevant details.

REQUIREMENTS:
- Use proper degree titles and formatting
- Include relevant coursework, honors, or achievements if applicable
- Add GPA if it's 3.5 or higher
- Include relevant certifications or training
- Make it concise and professional

Original education: {content}

Return ONLY the improved education section:""",

            'default': f"Improve and professionalize this content: {content}"
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

    def rewrite_cv(self, cv_data):
        """
        Rewrite the entire CV using fallback between different LLM providers to ensure
        the most reliable and high-quality results.
        
        Args:
            cv_data (dict): Dictionary containing CV sections and their content
            
        Returns:
            dict: Dictionary with original and rewritten CV data
        """
        self.logger.info("Starting CV rewrite with resilient service")
        
        try:
            # Use the local service's formatting methods
            formatted_cv = {
                "professional_summary": cv_data.get("professional_summary", ""),
                "personal_info": {
                    "name": cv_data.get("name", ""),
                    "title": cv_data.get("title", ""),
                    "email": cv_data.get("email", ""),
                    "phone": cv_data.get("phone", ""),
                    "location": cv_data.get("location", ""),
                    "linkedin": cv_data.get("linkedin", "")
                },
                "experiences": self.local_service._format_experiences(cv_data.get("experiences", [])),
                "education": self.local_service._format_education(cv_data.get("education", [])),
                "skills": cv_data.get("skills", []),
                "certifications": cv_data.get("certifications", []),
                "languages": cv_data.get("languages", [])
            }
            
            # Process each section independently with provider fallback
            improved_sections = {}
            
            # Track successful providers for telemetry
            providers_used = {}
            
            # Process professional summary
            if formatted_cv["professional_summary"]:
                self.logger.info("Processing professional summary")
                
                # Create context-aware prompt
                skills_str = ', '.join(formatted_cv["skills"][:10] if isinstance(formatted_cv["skills"], list) else [])
                exp_summary = formatted_cv["experiences"][:300] if formatted_cv["experiences"] else ""
                
                context_prompt = f"""Professional Summary Improvement Request

CONTEXT:
- Position: {formatted_cv["personal_info"]["title"] or "Not specified"}
- Key skills: {skills_str}
- Experience summary: {exp_summary}

ORIGINAL SUMMARY:
{formatted_cv["professional_summary"]}

INSTRUCTIONS:
Create a powerful, concise professional summary (3-5 sentences) that highlights relevant skills and experience,
uses strong action verbs, and demonstrates a clear value proposition while avoiding clichés.

IMPROVED SUMMARY:"""
                
                # Try to improve with fallback between providers
                summary_result = self.improve_text("professional_summary", context_prompt)
                if summary_result['status'] == 'success':
                    improved_sections["professional_summary"] = summary_result['response']
                    providers_used["summary"] = summary_result['provider']
                else:
                    improved_sections["professional_summary"] = formatted_cv["professional_summary"]
                    providers_used["summary"] = "original"
            
            # Process experience
            if formatted_cv["experiences"]:
                self.logger.info("Processing work experience")
                
                # Create context-aware prompt
                skills_str = ', '.join(formatted_cv["skills"][:10] if isinstance(formatted_cv["skills"], list) else [])
                
                experience_prompt = f"""Work Experience Improvement Request

CONTEXT:
- Position: {formatted_cv["personal_info"]["title"] or "Not specified"}
- Key skills: {skills_str}

ORIGINAL EXPERIENCE:
{formatted_cv["experiences"]}

INSTRUCTIONS:
Transform this work experience into achievement-focused bullet points that begin with strong action verbs,
include specific metrics where available, highlight relevant skills, and focus on business impact.

IMPROVED EXPERIENCE:"""
                
                # Try to improve with fallback
                experience_result = self.improve_text("experience", experience_prompt)
                if experience_result['status'] == 'success':
                    improved_sections["experiences"] = experience_result['response']
                    providers_used["experience"] = experience_result['provider']
                else:
                    improved_sections["experiences"] = formatted_cv["experiences"]
                    providers_used["experience"] = "original"
            
            # Process skills
            if formatted_cv["skills"]:
                self.logger.info("Processing skills section")
                
                # Create context-aware prompt for skills
                exp_summary = formatted_cv["experiences"][:200] if formatted_cv["experiences"] else ""
                
                skills_list = formatted_cv["skills"]
                if isinstance(skills_list, list):
                    skills_text = ', '.join(skills_list)
                else:
                    skills_text = str(skills_list)
                
                skills_prompt = f"""Skills Section Improvement Request

CONTEXT:
- Position: {formatted_cv["personal_info"]["title"] or "Not specified"}
- Experience summary: {exp_summary}

ORIGINAL SKILLS:
{skills_text}

INSTRUCTIONS:
Organize these skills into logical categories (Technical Skills, Soft Skills, Domain Knowledge),
add appropriate proficiency levels, and ensure consistent formatting.

IMPROVED SKILLS SECTION:"""
                
                # Try to improve with fallback
                skills_result = self.improve_text("skills", skills_prompt)
                if skills_result['status'] == 'success':
                    improved_sections["skills"] = skills_result['response']
                    providers_used["skills"] = skills_result['provider']
                else:
                    improved_sections["skills"] = formatted_cv["skills"]
                    providers_used["skills"] = "original"
            
            # Return comprehensively improved CV
            self.logger.info(f"CV rewrite complete. Providers used: {providers_used}")
            
            return {
                "original": cv_data,
                "rewritten": improved_sections,
                "providers": providers_used
            }
            
        except Exception as e:
            self.logger.error(f"Error in rewrite_cv: {str(e)}", exc_info=True)
            return {
                "original": cv_data,
                "rewritten": cv_data,
                "error": str(e)
            }

# Optional: Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
