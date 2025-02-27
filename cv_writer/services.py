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
                'template': """EXECUTIVE NARRATIVE ENGINEERING: TECHNOLOGY SECTOR CFO STRATEGIC POSITIONING PROTOCOL

MISSION-CRITICAL OPTIMIZATION FRAMEWORK:
-------------------------------------
OBJECTIVE: Generate a world-class professional summary that:
- Crystallizes 15+ years of technology sector financial leadership
- Communicates strategic value with surgical precision
- Positions the executive as a transformative industry architect

NARRATIVE CONSTRUCTION MANDATES:
1. STRATEGIC LEADERSHIP ESSENCE
   - ABSOLUTE PROHIBITION: Do NOT start with "As a..." or "As an..."
   - Distill 15+ years of financial leadership into 3-4 sentences
   - Highlight unique value proposition transcending traditional financial management
   - Demonstrate strategic vision that eclipses operational excellence

2. QUANTIFIABLE IMPACT ARCHITECTURE
   - MANDATORY: Embed measurable financial transformations
   - Showcase data-driven decision-making with concrete metrics
   - Illustrate leadership's direct organizational growth contribution
   - Quantify impact vectors:
     * Revenue growth percentages
     * Cost optimization metrics
     * Shareholder value enhancement
     * Technology-driven efficiency gains

3. TECHNOLOGICAL INNOVATION POSITIONING
   - Articulate technology-driven financial strategies
   - Demonstrate cutting-edge financial technology proficiency
   - Showcase adaptability in dynamic technology ecosystems
   - Highlight digital transformation leadership capabilities

4. EXECUTIVE COMMUNICATION PRECISION
   - Deploy executive-caliber action verbs EXCLUSIVELY
     Preferred Verbs:
     * Spearhead
     * Engineer
     * Architect
     * Transform
     * Orchestrate
   - Eliminate passive constructions
   - Use language resonating with technology sector leadership
   - Create narrative simultaneously strategic and authentic

5. LEADERSHIP PHILOSOPHY CRYSTALLIZATION
   - Capture leadership approach in a singular, powerful paragraph
   - Balance technical expertise with visionary thinking
   - Communicate cross-functional leadership capabilities
   - Project forward-thinking, innovation-driven mindset

OPTIMIZATION GUARDRAILS:
✓ Zero tolerance for credential inflation
✓ Absolute preservation of original professional narrative
✓ Strict adherence to factual career trajectory
✓ Eliminate redundant executive vernacular

CONTEXTUAL TRANSFORMATION FOCUS:
- Technology sector financial leadership
- Strategic financial planning
- Operational optimization
- Data-driven decision architecture
- Team empowerment and innovation culture
- Shareholder value maximization

ORIGINAL PROFESSIONAL PROFILE:
{content}

EXECUTIVE NARRATIVE GENERATION PROTOCOL:
Produce a world-class technology sector CFO professional summary that:
- Communicates strategic leadership potential
- Demonstrates measurable financial impact
- Positions executive as a transformative technology leader
- Maintains absolute narrative authenticity

CRITICAL CONSTRAINTS:
- Maximum Length: 250 words
- Minimum Sentences: 3
- Maximum Sentences: 4
- MUST reflect original professional experience
- MUST NOT fabricate achievements

RETURN ONLY: Optimized Technology Sector CFO Strategic Narrative"""
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
