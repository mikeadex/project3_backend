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
from .local_llm import LocalLLMService

logger = logging.getLogger(__name__)

class MistralAPIService:
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        if not self.api_key:
            raise ValueError("Mistral API Key is not set. Please provide MISTRAL_API_KEY in environment variables.")
        
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-medium"

    def improve_text(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Mistral API Error: {str(e)}")
            return None

class GroqLlamaAPIService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("Groq API Key is not set. Please provide GROQ_API_KEY in environment variables.")
        
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama2-70b-4096"

    def improve_text(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Groq Llama API Error: {str(e)}")
            return None

class CVImprovementService:
    def __init__(self):
        # Determine environment
        is_production = os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production')
        
        try:
            # Local LLM only for development
            if not is_production:
                logger.info("Initializing Local LLM for development")
                self.llm_service = LocalLLMService()
                self.use_local_llm = True
                logger.info("Local LLM initialized successfully")
                return
            
            # Validate API keys for production
            if not settings.MISTRAL_API_KEY and not settings.GROQ_API_KEY:
                raise ValueError("No API keys available for LLM services in production")
            
            # Production primary service: Mistral API
            if settings.MISTRAL_API_KEY:
                logger.info("Initializing Mistral API for production")
                self.primary_service = MistralAPIService()
                self.use_mistral = True
                logger.info("Mistral API initialized successfully")
            else:
                # Fallback to Groq if Mistral key is not set
                logger.info("Initializing Groq Llama API as primary service")
                self.primary_service = GroqLlamaAPIService()
                self.use_groq = True
                logger.info("Groq Llama API initialized successfully")

            # Set up fallback service if both keys are available
            if settings.MISTRAL_API_KEY and settings.GROQ_API_KEY:
                logger.info("Initializing Groq Llama API as fallback")
                self.fallback_service = GroqLlamaAPIService()
                self.use_groq = True
                logger.info("Groq Llama API fallback initialized successfully")
        
        except Exception as primary_error:
            logger.error(f"Failed to initialize primary LLM service: {str(primary_error)}")
            raise RuntimeError(f"No AI service available for CV improvement in production: {str(primary_error)}")

        self.improvement_prompts = {
            'professional_summary': {
                'template': """
                You are an expert CV writer. Improve this professional summary while maintaining professionalism and impact.

                Guidelines:
                1. Focus on:
                   - Years of experience in {industry}
                   - Key achievements and impact
                2. Keep it concise and compelling
                3. Use strong, active language

                Original Summary:
                {content}

                Improved Summary:
                """
            },
            'experience': {
                'template': """
                You are an expert CV writer. Enhance this job description to highlight achievements and impact.

                Guidelines:
                1. Transform responsibilities into achievements
                2. Add specific metrics and numbers
                3. Use strong action verbs
                4. Emphasize leadership and initiative
                5. Focus on business impact

                Original description:
                {content}

                Return only the improved description without any explanations.
                """
            },
            'skills': {
                'template': """
                You are an expert CV writer. Optimize these skills for {industry} roles.

                Guidelines:
                1. Organize skills by category
                2. Add appropriate proficiency levels
                3. Include industry-relevant keywords
                4. Remove outdated technologies
                5. Add emerging skills in the field

                Original skills:
                {content}

                Return the improved skills in this format:
                Technical: skill1 (Expert), skill2 (Advanced)
                Soft Skills: skill1, skill2
                Domain Knowledge: area1, area2
                """
            }
        }

    async def improve_cv(self, cv_id: int) -> Dict:
        """Improves all sections of a CV."""
        try:
            logger.info(f"Starting CV improvement for CV ID: {cv_id}")
            cv = CvWriter.objects.get(id=cv_id)
            improvements = {}
            improvement_records = []
            
            # Determine service based on environment
            is_production = os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production')
            
            if not is_production:
                # Use local LLM in development
                improve_func = self.llm_service.improve_text
            else:
                # Use primary service in production
                improve_func = self.primary_service.improve_text
            
            # Improve professional summary
            if hasattr(cv, 'professional_summary'):
                logger.info("Improving professional summary")
                improvement = CVImprovement.objects.create(
                    cv=cv,
                    section='professional_summary',
                    original_content=cv.professional_summary.summary,
                    improvement_type='full'
                )
                improvement_records.append(improvement)
                
                try:
                    # Attempt improvement with primary service
                    improved_summary = improve_func(
                        self.improvement_prompts['professional_summary']['template'].format(
                            industry=cv.industry or 'general',
                            content=cv.professional_summary.summary
                        )
                    )
                    
                    # Fallback to secondary service if primary fails in production
                    if is_production and not improved_summary and hasattr(self, 'fallback_service'):
                        logger.warning("Primary service failed. Attempting fallback service.")
                        improved_summary = self.fallback_service.improve_text(
                            self.improvement_prompts['professional_summary']['template'].format(
                                industry=cv.industry or 'general',
                                content=cv.professional_summary.summary
                            )
                        )
                    
                    if improved_summary:
                        improvement.improved_content = improved_summary
                        improvement.save()
                        improvements['professional_summary'] = improved_summary
                        cv.professional_summary.summary = improved_summary
                        cv.professional_summary.save()
                    
                except Exception as e:
                    logger.error(f"Error improving professional summary: {str(e)}")
                    improvement.status = 'failed'
                    improvement.save()

            # Improve experiences
            experiences = []
            for exp in cv.experiences.all():
                logger.info(f"Improving experience: {exp.job_title}")
                improvement = CVImprovement.objects.create(
                    cv=cv,
                    section='experience',
                    original_content=str({
                        'job_title': exp.job_title,
                        'job_description': exp.job_description,
                        'achievements': exp.achievements
                    }),
                    improvement_type='full'
                )
                improvement_records.append(improvement)
                
                try:
                    improved_exp = await self._improve_section(
                        'experience',
                        {
                            'job_title': exp.job_title,
                            'job_description': exp.job_description,
                            'achievements': exp.achievements
                        }
                    )
                    experiences.append(improved_exp)
                    improvement.improved_content = str(improved_exp['improved'])
                    improvement.status = 'completed'
                    improvement.tokens_used = len(str(improved_exp['improved']))
                    logger.info(f"Experience improved successfully: {exp.job_title}")
                except Exception as e:
                    logger.error(f"Error improving experience: {str(e)}")
                    improvement.status = 'failed'
                    improvement.error_message = str(e)
                improvement.save()
                
            improvements['experiences'] = experiences

            # Improve skills
            skills = []
            for skill in cv.skills.all():
                logger.info(f"Improving skill: {skill.name}")
                improvement = CVImprovement.objects.create(
                    cv=cv,
                    section='skills',
                    original_content=str({
                        'name': skill.name,
                        'proficiency': skill.proficiency
                    }),
                    improvement_type='full'
                )
                improvement_records.append(improvement)
                
                try:
                    improved_skill = await self._improve_section(
                        'skills',
                        {
                            'name': skill.name,
                            'proficiency': skill.proficiency
                        }
                    )
                    skills.append(improved_skill)
                    improvement.improved_content = str(improved_skill['improved'])
                    improvement.status = 'completed'
                    improvement.tokens_used = len(str(improved_skill['improved']))
                    logger.info(f"Skill improved successfully: {skill.name}")
                except Exception as e:
                    logger.error(f"Error improving skill: {str(e)}")
                    improvement.status = 'failed'
                    improvement.error_message = str(e)
                improvement.save()
                
            improvements['skills'] = skills

            logger.info("CV improvement completed successfully")
            return {
                'status': 'success',
                'improvements': improvements,
                'improvement_ids': [imp.id for imp in improvement_records]
            }

        except CvWriter.DoesNotExist:
            logger.error(f"CV not found: {cv_id}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during CV improvement: {str(e)}")
            raise

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
                mistral_result = self.primary_service.improve_text(formatted_prompt)
                if mistral_result:
                    return {'original': content, 'improved': mistral_result}
            
            if hasattr(self, 'use_groq') and self.use_groq:
                groq_result = self.fallback_service.improve_text(formatted_prompt)
                if groq_result:
                    return {'original': content, 'improved': groq_result}
            
            if not os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production') and hasattr(self, 'use_local_llm') and self.use_local_llm:
                return {'original': content, 'improved': self.primary_service.improve_text(formatted_prompt)}
            
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
