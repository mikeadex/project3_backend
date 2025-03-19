import logging
from typing import Dict, Any, Optional
from .models import ParsedCV
from cv_writer.models import CvWriter, ProfessionalSummary, Experience, Education, Skill
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from django.db import close_old_connections, connection, transaction
from functools import wraps
from .deepseek_service import DeepSeekService
import asyncio
import django.db.utils

logger = logging.getLogger(__name__)

@sync_to_async
def create_cv_writer(**kwargs):
    with transaction.atomic():
        return CvWriter.objects.create(**kwargs)

@sync_to_async
def create_professional_summary(**kwargs):
    with transaction.atomic():
        return ProfessionalSummary.objects.create(**kwargs)

@sync_to_async
def create_experience(**kwargs):
    with transaction.atomic():
        return Experience.objects.create(**kwargs)

@sync_to_async
def create_skill(**kwargs):
    with transaction.atomic():
        # Ensure cv_id is included if cv is provided
        if 'cv' in kwargs and 'cv_id' not in kwargs:
            kwargs['cv_id'] = kwargs['cv'].id
            del kwargs['cv']
            
        return Skill.objects.create(**kwargs)

@sync_to_async
def connect_db():
    """Connect to database in a sync context"""
    close_old_connections()
    if connection.connection is None or connection.connection.closed:
        connection.connect()
    return True

def ensure_database_connection(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        try:
            # Close any stale connections before starting
            await sync_to_async(close_old_connections)()
            
            # Execute the function
            result = await f(*args, **kwargs)
            
            return result
        except Exception as e:
            # If there's a connection error, try to reconnect
            if 'connection already closed' in str(e) or 'InterfaceError' in str(e):
                # Use sync_to_async to reconnect
                logger.info("Database connection closed, attempting to reconnect...")
                await connect_db()
                
                # Retry the operation
                try:
                    logger.info("Retrying operation after reconnection...")
                    return await f(*args, **kwargs)
                except Exception as retry_error:
                    logger.error(f"Retry failed: {str(retry_error)}")
                    raise Exception(f"Operation failed after reconnection attempt: {str(retry_error)}")
            raise
        finally:
            # Always close connections after the operation
            await sync_to_async(close_old_connections)()
    return wrapper

@sync_to_async
def run_in_transaction(func, *args, **kwargs):
    """Run a function in a transaction with proper connection handling."""
    # Close any existing connections first
    close_old_connections()
    
    # Create a fresh connection
    connection.ensure_connection()
    
    try:
        # Execute in transaction
        with transaction.atomic():
            return func(*args, **kwargs)
    finally:
        # Always close connection when done
        close_old_connections()

@sync_to_async
def create_cv_with_sections(user, cv_data, improved_sections):
    """Create a complete CV with all sections in a single transaction."""
    # Close any existing connections first
    close_old_connections()
    
    # Make sure we have a fresh connection
    connection.ensure_connection()
    
    try:
        with transaction.atomic():
            # Extract basic info
            personal_info = cv_data.get('personal_info', {})
            name_parts = personal_info.get('name', '').split(' ', 1) if personal_info.get('name') else ['', '']
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Create the CV
            new_cv = CvWriter.objects.create(
                user=user,
                first_name=first_name or 'First',
                last_name=last_name or 'Last',
                title=cv_data.get('job_title', 'Improved CV'),
                address='',
                city='',
                country='',
                contact_number='',
                status='draft',
                visibility='private'
            )
            
            # Add professional summary
            if improved_sections.get('professional_summary'):
                ProfessionalSummary.objects.create(
                    user=user,
                    cv=new_cv,
                    summary=improved_sections['professional_summary']
                )
            
            # Add experiences
            if improved_sections.get('experience') and isinstance(improved_sections['experience'], list):
                for exp in improved_sections['experience']:
                    Experience.objects.create(
                        user=user,
                        cv=new_cv,
                        job_title=exp.get('job_title', ''),
                        company_name=exp.get('company_name', ''),
                        job_description=exp.get('description', ''),
                        achievements='',
                        employment_type='Full-time',
                        start_date=exp.get('start_date'),
                        end_date=exp.get('end_date'),
                        current=False
                    )
            
            # Add skills
            if improved_sections.get('skills'):
                skills_text = improved_sections['skills']
                # Process skills - extracting individual skills from the text
                lines = [line.strip() for line in skills_text.split('\n') if line.strip()]
                created_skills = set()
                max_skills = 20
                skill_count = 0
                
                for line in lines:
                    # Skip if we've already added max skills
                    if skill_count >= max_skills:
                        break
                        
                    # Skip markdown formatting lines, headers, etc.
                    if (line.startswith('#') or 
                        line.startswith('-') or 
                        line.startswith('*') or 
                        line.startswith('>') or
                        '---' in line or 
                        '###' in line or
                        '```' in line or
                        len(line) < 3 or
                        line.endswith(':')):
                        continue
                    
                    # Clean up the line
                    cleaned_line = line.replace('*', '').replace('#', '').replace('_', '').strip()
                    
                    # Try to extract skill name and level
                    skill_name = cleaned_line
                    skill_level = "Intermediate"  # Default level
                    
                    # Look for patterns
                    if '(' in cleaned_line and ')' in cleaned_line:
                        parts = cleaned_line.split('(')
                        skill_name = parts[0].strip()
                        skill_level = parts[1].replace(')', '').strip()
                    elif ' - ' in cleaned_line:
                        parts = cleaned_line.split(' - ')
                        skill_name = parts[0].strip()
                        if len(parts) > 1:
                            skill_level = parts[1].strip()
                    elif ':' in cleaned_line:
                        parts = cleaned_line.split(':')
                        skill_name = parts[0].strip()
                        if len(parts) > 1:
                            skill_level = parts[1].strip()
                    
                    # Skip if empty or duplicate
                    if not skill_name or skill_name.lower() in created_skills:
                        continue
                        
                    # Create skill
                    try:
                        Skill.objects.create(
                            user=user,
                            cv=new_cv,
                            skill_name=skill_name[:100],
                            skill_level=skill_level[:100]
                        )
                        created_skills.add(skill_name.lower())
                        skill_count += 1
                    except Exception:
                        # Continue even if one skill fails
                        continue
            
            return new_cv
    finally:
        # Always close connection when done
        close_old_connections()

class CVRewriteService:
    """Service for rewriting and improving CV content using DeepSeek."""

    def __init__(self, deepseek_service=None):
        try:
            self.deepseek_service = deepseek_service if deepseek_service is not None else DeepSeekService()
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeekService: {str(e)}")
            raise Exception("Failed to initialize CV rewrite service. Please try again later.")

        self.improvement_prompts = {
            'professional_summary': {
                'template': """
                
                As an expert CV writer, improve this professional summary to be more impactful and ATS-friendly.
                Make it concise (3-4 sentences), achievement-focused, and tailored for the {industry} industry.

                Original Summary:
                {content}

                Guidelines:
                1. Start with a strong professional identity statement
                2. Highlight key achievements with metrics when possible
                3. Showcase relevant skills and expertise
                4. End with a clear value proposition
                5. Use active voice and power verbs
                6. Optimize for ATS keywords
                7. Keep it under 200 words

                Improved Summary:
                
                """
            },
            'experience': {
                'template': """
                
                Transform this job experience into powerful, achievement-focused bullet points.
                Focus on quantifiable results and impactful contributions.

                Original Experience:
                {content}

                Guidelines:
                1. Start each bullet with a strong action verb
                2. Include metrics and specific achievements (%, $, numbers)
                3. Show impact on business/organization
                4. Highlight leadership and initiative
                5. Include relevant technical skills
                6. Focus on results over responsibilities
                7. Use industry-specific keywords

                Improved Experience:
                
                """
            },
            'skills': {
                'template': """
                
                Organize and enhance these skills for maximum impact in the {industry} industry.
                Create clear categories and indicate proficiency levels.

                Original Skills:
                {content}

                Guidelines:
                1. Group into categories (Technical, Soft Skills, Domain Knowledge)
                2. Add proficiency levels (Expert, Advanced, Intermediate)
                3. Prioritize most relevant skills first
                4. Use industry-standard terminology
                5. Include both hard and soft skills
                6. Remove outdated or basic skills
                7. Ensure ATS compatibility

                Improved Skills:
                
                """
            }
        }

    @ensure_database_connection
    async def rewrite_cv(self, cv_data: Dict[str, Any], user: User) -> Dict[str, Any]:
        """
        Rewrite and improve CV content using DeepSeek.
        """
        try:
            logger.info(f"Starting CV rewrite for user {user.username}")
            logger.info(f"CV data structure: {cv_data.keys()}")
            
            # Extract the actual CV data - it's nested inside a 'data' key
            if 'data' in cv_data and isinstance(cv_data['data'], dict):
                cv_content = cv_data['data']
                logger.info(f"Found nested data with keys: {cv_content.keys()}")
            else:
                cv_content = cv_data
                logger.info("Using top-level data structure")
                
            improved_sections = {}

            # Process professional summary
            if cv_content.get('professional_summary'):
                logger.info("Improving professional summary")
                improved_summary = await self._improve_section(
                    'professional_summary',
                    cv_content['professional_summary'],
                    industry=cv_content.get('industry', 'technology')
                )
                if improved_summary:
                    improved_sections['professional_summary'] = improved_summary

            # Process experience entries
            if cv_content.get('experience'):
                logger.info("Improving experience sections")
                improved_experiences = []
                for exp in cv_content['experience']:
                    if exp.get('description'):
                        improved_desc = await self._improve_section(
                            'experience',
                            exp['description']
                        )
                        if improved_desc:
                            exp_copy = exp.copy()
                            exp_copy['description'] = improved_desc
                            improved_experiences.append(exp_copy)
                    else:
                        improved_experiences.append(exp)
                improved_sections['experience'] = improved_experiences

            # Process skills
            if cv_content.get('skills'):
                logger.info("Improving skills section")
                skills_text = (
                    cv_content['skills'] if isinstance(cv_content['skills'], str)
                    else ', '.join(cv_content['skills'])
                )
                improved_skills = await self._improve_section(
                    'skills',
                    skills_text,
                    industry=cv_content.get('industry', 'technology')
                )
                if improved_skills:
                    improved_sections['skills'] = improved_skills

            # At this point we have improved content - try to save but don't fail if saving fails
            try:
                # Create new CV version
                new_cv = await self._create_cv_version(cv_content, improved_sections, user)
                
                if not new_cv:
                    logger.error("Failed to create new CV version")
                    # Return partial success - improved content but no database save
                    return {
                        'status': 'partial_success',
                        'message': 'CV content improved but could not be saved',
                        'improved_sections': improved_sections
                    }
                
                # Full success - improved content and database save
                response = {
                    'status': 'success',
                    'message': 'CV rewritten successfully',
                    'data': {
                        'improved_sections': improved_sections,
                        'new_cv_id': new_cv.id
                    }
                }
                logger.info(f"CV rewrite returning: {response}")
                return response
                
            except Exception as save_error:
                # Log saving error but return improved content as partial success
                logger.error(f"Error saving CV: {str(save_error)}")
                return {
                    'status': 'partial_success',
                    'message': 'CV content improved but could not be saved',
                    'improved_sections': improved_sections,
                    'error': str(save_error)
                }

        except Exception as e:
            logger.error(f"Error in CV rewrite: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }

    async def _improve_section(
        self,
        section_type: str,
        content: str,
        industry: str = 'technology'
    ) -> Optional[str]:
        """
        Improve a specific section of the CV using DeepSeek.
        
        Args:
            section_type: Type of section to improve
            content: Original content
            industry: Industry context for improvements
            
        Returns:
            Improved content or None if improvement failed
        """
        try:
            if not content or not self.deepseek_service:
                return None

            prompt_template = self.improvement_prompts.get(section_type, {}).get('template')
            if not prompt_template:
                logger.warning(f"No improvement template for section: {section_type}")
                return None

            # Format prompt with context
            prompt = prompt_template.format(
                industry=industry,
                content=content
            )

            # Get improvement from DeepSeek
            response = await self.deepseek_service.generate(
                prompt,
                max_tokens=1000,
                temperature=0.7,
                top_p=0.9
            )

            if not response:
                logger.warning(f"No response from DeepSeek for {section_type}")
                return None

            return response.strip()

        except Exception as e:
            logger.error(f"Error improving {section_type}: {str(e)}", exc_info=True)
            return None

    @ensure_database_connection
    async def _create_cv_version(self, cv_data: Dict[str, Any], improved_sections: Dict[str, Any], user: User) -> Optional[CvWriter]:
        """
        Create a new CV version with improved content.
        """
        max_retries = 5
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Creating CV version (attempt {attempt}/{max_retries})")
                
                # Use a new approach - create everything in a single transaction
                try:
                    new_cv = await create_cv_with_sections(user, cv_data, improved_sections)
                    logger.info(f"Successfully created CV version (ID: {new_cv.id})")
                    return new_cv
                except Exception as e:
                    logger.error(f"Error in create_cv_with_sections: {str(e)}")
                    raise
                
            except django.db.utils.OperationalError as e:
                logger.error(f"Database connection error creating CV version (attempt {attempt}/{max_retries}): {str(e)}")
                
                # Close any broken connections
                await sync_to_async(close_old_connections)()
                
                if attempt < max_retries:
                    # Wait before retrying (exponential backoff)
                    retry_time = retry_delay * (2 ** (attempt - 1))
                    logger.info(f"Waiting {retry_time}s before retry...")
                    await asyncio.sleep(retry_time)
                else:
                    logger.error(f"Failed to create CV version after {max_retries} attempts")
                    raise Exception(f"Failed to create CV version after {max_retries} attempts: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error creating CV version: {str(e)}")
                raise Exception(f"Failed to create CV version: {str(e)}")