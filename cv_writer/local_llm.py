from llama_cpp import Llama
import os
import logging
from typing import Dict, Optional
from pathlib import Path
import json
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class BaseLLMService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def improve_text(self, section, content):
        raise NotImplementedError()

class LocalLLMService(BaseLLMService):
    def __init__(self):
        super().__init__(settings.CURRENT_LLM_CONFIG)
        self.model = None
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
        """Call Mistral API for text improvement"""
        try:
            response = requests.post(
                'https://api.mistral.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.config["api_key"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'mistral-medium',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens
                }
            )
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Mistral API call failed: {e}")
            raise

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

    def improve_text(self, section: str, content: str, max_tokens: int = 500) -> Optional[str]:
        """Improve text with advanced provider fallback mechanism"""
        try:
            # validate input
            if not content or not isinstance(content, str):
                logger.info(f"Improving text for section: {section}")
                prompt = self.prompts.get(section, "")
                if not prompt:
                    logger.error(f"No prompt template found for section: {section}")
                    return None
                    
                formatted_prompt = prompt.format(content=content)
                logger.debug(f"Generated prompt: {formatted_prompt}")
                
            formatted_prompt = prompt.format(content=content)
            logger.debug(f"Generated prompt: {formatted_prompt}")
            
            # Local model for development
            if self.config['provider'] == 'local':
                return self._local_model_improve(formatted_prompt, section, max_tokens)
            
            # Production: Try Mistral first
            try:
                mistral_text = self._call_mistral_api(formatted_prompt, max_tokens)
                return self._post_process_text(mistral_text, section)
            except Exception as mistral_error:
                logger.warning(f"Mistral API failed: {mistral_error}")
                
                # Fallback to Groq Llama
                try:
                    groq_text = self._call_groq_llama_api(formatted_prompt, max_tokens)
                    return self._post_process_text(groq_text, section)
                except Exception as groq_error:
                    logger.error(f"Groq API failed: {groq_error}")
                    raise RuntimeError("All LLM providers failed")

        except Exception as e:
            logger.error(f"Comprehensive error in improve_text: {e}", exc_info=True)
            raise

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
