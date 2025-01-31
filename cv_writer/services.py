from typing import Dict, List, Optional
import os
import logging
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

class CVImprovementService:
    def __init__(self):
        try:
            logger.info("Initializing CV Improvement Service")
            self.llm_service = LocalLLMService()
            self.use_local_llm = True
            logger.info("Local LLM initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize local LLM: {str(e)}")
            self.use_local_llm = False
            # Initialize Gemini as fallback if API key exists
            if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
                logger.info("Initializing Gemini as fallback")
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.use_gemini = True
                logger.info("Gemini initialized successfully")
            else:
                logger.warning("No fallback AI service available")
                self.use_gemini = False

        self.improvement_prompts = {
            'professional_summary': {
                'template': """
                You are an expert CV writer. Improve this professional summary while maintaining professionalism and impact.

                Guidelines:
                1. Focus on:
                   - Years of experience in {industry}
                   - Key achievements and impact
                   - Core skills and expertise
                   - Career objectives
                2. Keep it concise (150-200 words)
                3. Use active voice and strong verbs
                4. Include relevant industry keywords
                5. Highlight unique value proposition

                Original summary:
                {content}

                Return only the improved summary without any explanations.
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
                    result = await self._improve_section(
                        'professional_summary',
                        cv.professional_summary.summary
                    )
                    improvements['professional_summary'] = result
                    improvement.improved_content = result['improved']
                    improvement.status = 'completed'
                    improvement.tokens_used = len(result['improved'])
                    logger.info("Professional summary improved successfully")
                except Exception as e:
                    logger.error(f"Error improving professional summary: {str(e)}")
                    improvement.status = 'failed'
                    improvement.error_message = str(e)
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
            if self.use_local_llm:
                try:
                    logger.info(f"Improving section using local LLM: {section}")
                    result = self.llm_service.improve_section(section, content)
                    if not result or not result.get('improved'):
                        raise Exception("No improvement generated")
                    logger.info(f"Section improved successfully using local LLM: {section}")
                    return result
                except Exception as e:
                    logger.error(f"Local LLM failed: {str(e)}")
                    if not self.use_gemini:
                        raise Exception("No fallback service available")
                    
            if self.use_gemini:
                logger.info(f"Improving section using Gemini: {section}")
                # Use existing Gemini implementation
                prompt_data = self.improvement_prompts.get(section)
                if not prompt_data:
                    return {'original': content, 'improved': str(content)}

                formatted_prompt = prompt_data['template'].format(
                    content=str(content),
                    industry=self._detect_industry(content)
                )

                try:
                    response = genai.generate_text(formatted_prompt)
                    if not response:
                        raise Exception("No response from Gemini")
                    logger.info(f"Section improved successfully using Gemini: {section}")
                    return {
                        'original': content,
                        'improved': response.text if hasattr(response, 'text') else str(response)
                    }
                except Exception as e:
                    logger.error(f"Gemini failed: {str(e)}")
                    raise
            else:
                raise Exception("No LLM service available")

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
