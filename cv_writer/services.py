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

    def improve_cv(self, cv_id):
        """
        Improve different sections of a CV using the ResilientLLMService.
        
        Args:
            cv_id (int): ID of the CV to improve
        
        Returns:
            dict: Improvements for different sections of the CV
        """
        try:
            # Retrieve the CV
            cv = CvWriter.objects.get(id=cv_id)
            
            # Find the professional summary for this user, handling multiple summaries
            professional_summaries = ProfessionalSummary.objects.filter(user=cv.user)
            
            # If multiple summaries exist, use the most recently created one
            if professional_summaries.count() > 1:
                professional_summary_obj = professional_summaries.order_by('-created_at').first()
            elif professional_summaries.count() == 1:
                professional_summary_obj = professional_summaries.first()
            else:
                # If no professional summary exists, create a default
                professional_summary_obj = ProfessionalSummary.objects.create(
                    user=cv.user,
                    summary="Professional summary not found."
                )
            
            original_summary = professional_summary_obj.summary
            
            # Use ResilientLLMService to improve the summary
            llm_service = ResilientLLMService()
            
            # Improve professional summary
            improved_summary = llm_service.improve_section(
                section='professional_summary', 
                content=original_summary
            )
            
            # Update the professional summary
            professional_summary_obj.summary = improved_summary
            professional_summary_obj.save()
            
            # Create improvement record
            CVImprovement.objects.create(
                cv=cv,
                section='professional_summary',
                original_content=original_summary,
                improved_content=improved_summary,
                improvement_type='full',
                tokens_used=0,  # You might want to track actual tokens used
                status='completed'
            )
            
            return {
                'professional_summary': improved_summary
            }
        
        except CvWriter.DoesNotExist:
            logger.error(f"CV with ID {cv_id} not found")
            raise
        
        except Exception as e:
            logger.error(f"Error improving CV: {str(e)}")
            raise

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
