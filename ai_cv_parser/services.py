import logging
from typing import Dict, Any, Optional
from .models import ParsedCV, CVRewriteSession
from cv_writer.models import CvWriter, ProfessionalSummary, Experience, Education, Skill, Language, Certification
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
import asyncio
from django.db import connection, transaction, close_old_connections, InterfaceError, OperationalError
from django.utils.decorators import sync_and_async_middleware
import django
from django.conf import settings
from functools import wraps
from .deepseek_service import DeepSeekService

logger = logging.getLogger(__name__)

User = get_user_model()

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
    connection.ensure_connection()
    return True

@sync_to_async
def get_session_user(session):
    """Get user from session in a sync context"""
    return session.user

@sync_to_async
def get_session_input_data(session):
    """Get input data from session in a sync context"""
    return session.input_data

@sync_to_async
def update_session_status(session, status, error_message=None):
    """Update session status in a sync context with thread-safe connection handling"""
    # Close old connections to ensure we're in the right thread
    close_old_connections()
    
    try:
        session.status = status
        if error_message:
            session.error_message = error_message
        session.save()
        return session
    except Exception as e:
        logger.error(f"Error updating session status: {str(e)}")
        # Try one more time after explicit thread-safe reconnect
        close_old_connections()
        
        # Retry with bare minimum updates
        try:
            session.status = status
            session.save(update_fields=['status'])
            return session
        except Exception as retry_e:
            logger.error(f"Failed to update session status even after reconnect: {str(retry_e)}")
            return session

@sync_to_async
def update_session_with_results(session, output_data, new_cv_id):
    """Update session with results in a sync context with thread-safe connection handling"""
    # Close old connections to ensure we're in the right thread
    close_old_connections()
    
    try:
        session.status = 'completed'
        session.output_data = output_data
        session.new_cv_id = new_cv_id
        session.save()
        return session
    except Exception as e:
        logger.error(f"Error updating session with results: {str(e)}")
        # Try one more time with thread-safe reconnect
        close_old_connections()
        
        # Retry with minimal updates
        try:
            session.status = 'completed'
            session.new_cv_id = new_cv_id
            session.save(update_fields=['status', 'new_cv_id'])
            return session
        except Exception as retry_e:
            logger.error(f"Failed to update session with results even after reconnect: {str(retry_e)}")
            return session

def ensure_database_connection(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        try:
            # Close any stale connections before starting
            await sync_to_async(connection.close)()
            
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
            await sync_to_async(connection.close)()
    return wrapper

async def run_in_transaction(func, *args, **kwargs):
    """Run a function in a transaction with proper connection handling."""
    # For sync functions that are decorated with @sync_to_async
    if asyncio.iscoroutinefunction(func):
        # If it's already a coroutine function, just call it directly
        return await func(*args, **kwargs)
    else:
        # Use sync_to_async to handle database operations
        @sync_to_async
        def run_sync_transaction():
            # Always close old connections first to avoid thread issues
            close_old_connections()
            
            try:
                # Execute in transaction - Django will create a new connection in this thread when needed
                with transaction.atomic():
                    return func(*args, **kwargs)
            finally:
                # Close connection when done to avoid leaks
                close_old_connections()
        
        # Run the transaction in a sync context
        return await run_sync_transaction()

@sync_to_async
def refresh_db_connection():
    """Force a new database connection after a long-running operation"""
    # Close any existing connections first
    connection.close_if_unusable_or_obsolete()
    # Ensure we have a fresh connection
    connection.ensure_connection()
    return True

def create_cv_with_sections_sync(user, cv_data, improved_sections):
    """
    Create a complete CV with all sections in a single synchronous transaction.
    This function is NOT decorated with sync_to_async on purpose - it's meant to be
    called directly from synchronous code.
    """
    # Import inside function to avoid circular imports
    from django.db import close_old_connections, connection, transaction
    from cv_writer.models import CvWriter, ProfessionalSummary, Experience, Education, Skill, Language, Certification
    import time
    import random
    
    # Always close connections at the start of this function
    close_old_connections()
    
    # Force a new connection before we start
    try:
        connection.connect()
    except Exception as e:
        logger.warning(f"Connection initial setup error (proceeding anyway): {str(e)}")
    
    max_retries = 5  # Increase max retries
    retry_count = 0
    
    def _create_cv_and_sections():
        """Inner function to create CV and sections in a single transaction"""
        # Extract basic info
        personal_info = cv_data.get('personal_info', {})
        
        # Process name to extract first and last name
        name = personal_info.get('name', '')
        if not name:
            # Try to get first and last name separately
            first_name = personal_info.get('first_name', '')
            last_name = personal_info.get('last_name', '')
        else:
            # Split full name into first and last
            name_parts = name.split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Extract other personal info
        email = personal_info.get('email', '')
        phone = personal_info.get('phone', '') or personal_info.get('contact_number', '')
        address = personal_info.get('address', '')
        city = personal_info.get('city', '')
        country = personal_info.get('country', '')
        
        # Set a default title if none provided
        title = cv_data.get('job_title') or personal_info.get('title', '')
        if not title:
            title = f"Improved CV ({int(time.time())})"
        
        # Create the CV - the model has its own retry logic now
        logger.info("Creating new CV record in database")
        new_cv = CvWriter(
            user=user,
            first_name=first_name or 'First',
            last_name=last_name or 'Last',
            title=title,
            address=address,
            city=city,
            country=country,
            contact_number=phone,
            status='draft',
            visibility='private'
        )
        new_cv.save()
        logger.info(f"CV record created with ID: {new_cv.id}")
        
        # Add professional summary
        if improved_sections.get('professional_summary'):
            try:
                logger.info("Adding professional summary")
                ProfessionalSummary.objects.create(
                    user=user,
                    cv=new_cv,
                    summary=improved_sections['professional_summary']
                )
            except Exception as e:
                logger.error(f"Error adding professional summary: {str(e)}")
        
        # Add experiences - check both singular and plural keys
        experiences = improved_sections.get('experiences') or improved_sections.get('experience') or []
        if experiences and isinstance(experiences, list):
            logger.info(f"Adding {len(experiences)} experience items")
            for exp in experiences:
                try:
                    Experience.objects.create(
                        user=user,
                        cv=new_cv,
                        job_title=exp.get('job_title', ''),
                        company_name=exp.get('company_name', ''),
                        job_description=exp.get('description', ''),
                        achievements='',
                        employment_type=exp.get('employment_type', 'Full-time'),
                        start_date=exp.get('start_date'),
                        end_date=exp.get('end_date'),
                        current=exp.get('current', False)
                    )
                except Exception as e:
                    logger.error(f"Error adding experience: {str(e)}")
        
        # Add education - check for education sections
        education_list = cv_data.get('education', []) or cv_data.get('educations', [])
        if education_list and isinstance(education_list, list):
            logger.info(f"Adding {len(education_list)} education items")
            for edu in education_list:
                try:
                    Education.objects.create(
                        user=user,
                        school_name=edu.get('school_name', '') or edu.get('institution', ''),
                        degree=edu.get('degree', ''),
                        field_of_study=edu.get('field_of_study', '') or edu.get('major', ''),
                        start_date=edu.get('start_date'),
                        end_date=edu.get('end_date'),
                        current=edu.get('current', False)
                    )
                except Exception as e:
                    logger.error(f"Error adding education: {str(e)}")
        
        # Add skills - handle both object format and string format
        skills_data = improved_sections.get('skills')
        if skills_data:
            logger.info("Processing and adding skills")
            try:
                # If skills is a list of objects, use that directly
                if isinstance(skills_data, list):
                    for skill_item in skills_data:
                        try:
                            if isinstance(skill_item, dict):
                                skill_name = skill_item.get('name', '')
                                skill_level = skill_item.get('level', 'Intermediate')
                            else:
                                skill_name = str(skill_item)
                                skill_level = 'Intermediate'
                                
                            if skill_name:
                                Skill.objects.create(
                                    user=user,
                                    skill_name=skill_name[:100],
                                    skill_level=skill_level[:100]
                                )
                        except Exception as e:
                            logger.error(f"Error creating skill from list: {str(e)}")
                
                # If skills is a string, parse it line by line
                elif isinstance(skills_data, str):
                    lines = [line.strip() for line in skills_data.split('\n') if line.strip()]
                    created_skills = set()
                    max_skills = 20
                    skill_count = 0
                    
                    for line in lines:
                        # Skip if we've already added max skills
                        if skill_count >= max_skills:
                            break
                            
                        # Skip markdown formatting lines
                        if (line.startswith('#') or line.startswith('-') or line.startswith('*') or 
                            line.startswith('>') or '---' in line or '###' in line or
                            '```' in line or len(line) < 3 or line.endswith(':')):
                            continue
                        
                        # Clean up the line
                        cleaned_line = line.replace('*', '').replace('#', '').replace('_', '').strip()
                        
                        # Extract skill name and level
                        skill_name = cleaned_line
                        skill_level = "Intermediate"  # Default level
                        
                        # Parse different formats
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
                                skill_name=skill_name[:100],
                                skill_level=skill_level[:100]
                            )
                            created_skills.add(skill_name.lower())
                            skill_count += 1
                        except Exception as e:
                            logger.error(f"Error creating skill '{skill_name}': {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"Error processing skills: {str(e)}")
        
        # Add languages if available
        languages = cv_data.get('languages', []) or cv_data.get('language', [])
        if languages and isinstance(languages, list):
            logger.info(f"Adding {len(languages)} language items")
            for lang in languages:
                try:
                    language_name = lang.get('name', '') or lang.get('language', '')
                    if language_name:
                        Language.objects.create(
                            user=user,
                            cv=new_cv,
                            language=language_name,
                            proficiency=lang.get('proficiency', '') or lang.get('level', 'Intermediate')
                        )
                except Exception as e:
                    logger.error(f"Error adding language: {str(e)}")
        
        # Add certifications if available
        certifications = cv_data.get('certifications', []) or cv_data.get('certification', [])
        if certifications and isinstance(certifications, list):
            logger.info(f"Adding {len(certifications)} certification items")
            for cert in certifications:
                try:
                    name = cert.get('name', '') or cert.get('title', '')
                    if name:
                        Certification.objects.create(
                            user=user,
                            cv=new_cv,
                            certificate_name=name,
                            certificate_link=cert.get('issuer', '') or cert.get('organization', ''),
                            certificate_date=cert.get('issue_date', None) or cert.get('date', None)
                        )
                except Exception as e:
                    logger.error(f"Error adding certification: {str(e)}")
        
        return new_cv.id
    
    # Retry loop with exponential backoff
    last_exception = None
    while retry_count < max_retries:
        # Make sure we have a valid connection
        close_old_connections()
        
        try:
            # Try to connect explicitly
            try:
                connection.ensure_connection()
            except Exception as conn_err:
                logger.warning(f"Could not ensure connection: {conn_err}")
            
            # Execute everything in a transaction
            logger.info(f"Attempt {retry_count + 1}/{max_retries} to create CV with sections")
            with transaction.atomic():
                cv_id = _create_cv_and_sections()
                logger.info(f"Successfully created complete CV with ID {cv_id}")
                
                # Verify the CV was actually created by querying it back
                try:
                    verification_cv = CvWriter.objects.get(id=cv_id)
                    logger.info(f"CV creation verified - CV with ID {cv_id} exists in database")
                    
                    # Additional verification - ensure the CV is properly associated with user
                    if verification_cv.user.id != user.id:
                        logger.error(f"CV creation verification failed - user mismatch: {verification_cv.user.id} != {user.id}")
                        raise ValueError(f"CV created but has wrong user association")
                    
                    # Add a small delay to ensure database operations complete
                    time.sleep(0.5)
                    
                    # Final verification after delay
                    final_check = CvWriter.objects.filter(id=cv_id).exists()
                    if not final_check:
                        logger.error(f"CV {cv_id} failed final verification check")
                        raise ValueError(f"CV {cv_id} missing in final verification")
                        
                    logger.info(f"CV {cv_id} passed all verification checks")
                except CvWriter.DoesNotExist:
                    logger.error(f"CV creation verification failed - cannot find CV with ID {cv_id}")
                    raise ValueError(f"CV {cv_id} created but not retrievable")
                
                return cv_id
                
        except (InterfaceError, OperationalError) as e:
            # Handle database connection errors
            retry_count += 1
            last_exception = e
            
            if retry_count < max_retries:
                # Calculate exponential backoff with jitter
                backoff = min(2 ** retry_count + random.uniform(0, 1), 10)
                logger.warning(f"Database connection error, retrying in {backoff:.2f}s ({retry_count}/{max_retries}): {str(e)}")
                
                # Force all connections to be recycled
                close_old_connections()
                
                # Wait with exponential backoff
                time.sleep(backoff)
                
                # Explicitly try to reconnect
                try:
                    connection.close()
                    connection.connect()
                    logger.info("Successfully reconnected to database")
                except Exception as conn_err:
                    logger.warning(f"Failed to reconnect: {conn_err}")
            else:
                logger.error(f"Failed to create CV after {max_retries} attempts: {str(e)}")
                raise
        except Exception as e:
            # For other errors, retry with shorter backoff
            retry_count += 1
            last_exception = e
            
            if retry_count < 3:  # Fewer retries for non-connection errors
                backoff = 0.5 * retry_count
                logger.warning(f"Error creating CV, retrying in {backoff:.2f}s ({retry_count}/3): {str(e)}")
                time.sleep(backoff)
                close_old_connections()
            else:
                logger.error(f"Error creating CV: {str(e)}")
                raise
    
    # If we got here, we failed after all retries
    if last_exception:
        logger.error(f"All {max_retries} attempts to create CV failed")
        raise last_exception
    else:
        raise Exception("Failed to create CV after multiple attempts")

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
                Rewrite this professional summary to be more impactful and ATS-friendly for the {industry} industry.
                
                Original Summary:
                {content}

                Requirements:
                - Return ONLY the improved summary text
                - NO markdown formatting (no **, ##, •, etc.)
                - NO explanatory text or commentary  
                - NO section headers or labels
                - 3-4 sentences maximum
                - Include metrics and achievements where possible
                - Use active voice and professional language
                - Optimize for ATS keywords

                Improved Summary:"""
            },
            'experience': {
                'template': """
                Rewrite this job experience description with achievement-focused bullet points for the {industry} industry.

                Original Experience:
                {content}

                Requirements:
                - Return ONLY the improved bullet points
                - NO markdown formatting (no **, ##, •, ###, etc.)
                - NO explanatory text, commentary, or section headers
                - NO phrases like "Of course" or "Here are the improved points"
                - Use plain text bullet points with simple dashes (-)
                - Start each point with a strong action verb
                - Include specific metrics and achievements (%, numbers, timelines)
                - Focus on business impact and results
                - Maximum 6 bullet points

                Improved Experience:"""
            },
            'skills': {
                'template': """
                Convert these skills into a simple list format. Each skill should be on its own line in the format: "Skill Name (Proficiency Level)"
                
                Proficiency levels: Expert, Advanced, Intermediate, Beginner
                Prioritize skills relevant to the {industry} industry.

                Original Skills:
                {content}

                Return ONLY the formatted skills list, one per line. Example format:
                Python (Advanced)
                Project Management (Expert)
                Communication (Advanced)

                Formatted Skills:
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
            
            # Extract the actual CV data - check multiple possible locations
            cv_content = None
            
            # Option 1: Frontend sends parsed_cv.parsed_data structure
            if 'parsed_cv' in cv_data and isinstance(cv_data['parsed_cv'], dict):
                parsed_cv = cv_data['parsed_cv']
                if 'parsed_data' in parsed_cv and isinstance(parsed_cv['parsed_data'], dict):
                    cv_content = parsed_cv['parsed_data']
                    logger.info(f"Found parsed_cv.parsed_data with keys: {cv_content.keys()}")
            
            # Option 2: Legacy 'data' key structure  
            elif 'data' in cv_data and isinstance(cv_data['data'], dict):
                cv_content = cv_data['data']
                logger.info(f"Found legacy data structure with keys: {cv_content.keys()}")
            
            # Option 3: Direct top-level structure
            else:
                cv_content = cv_data
                logger.info("Using top-level data structure")
            
            if not cv_content:
                logger.error("Could not extract CV content from input data")
                raise ValueError("Invalid CV data structure")
                
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
                new_cv_id = await self._create_cv_version(cv_content, improved_sections, user)
                
                if not new_cv_id:
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
                        'new_cv_id': new_cv_id
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

    async def process_rewrite_session(self, session):
        """
        Process a CV rewrite session by improving the CV content using DeepSeek.
        This method is designed to be called after a session has already been created,
        solving the connection closed issue by separating database operations.
        
        Args:
            session: CVRewriteSession instance with input data
            
        Returns:
            Dictionary with rewritten content and new CV ID
        """
        try:
            # Ensure database is connected at the start
            await connect_db()
            
            # Update session status to processing
            await update_session_status(session, 'processing')
            
            # Get input data
            cv_data = await get_session_input_data(session)
            
            # Get session user
            user = await get_session_user(session)
            
            # Improve each section
            improved_sections = {}

            try:
                # Process sections in parallel
                industry = cv_data.get('personal_info', {}).get('industry', 'technology')
                
                improvement_tasks = []
                
                # Professional summary section
                if 'professional_summary' in cv_data and 'content' in cv_data['professional_summary']:
                    improvement_tasks.append(
                        self._improve_section(
                            'professional_summary',
                            cv_data['professional_summary']['content'],
                            industry
                        )
                    )
                else:
                    improvement_tasks.append(None)
                
                # Experience sections
                experiences = cv_content.get('experiences') or cv_content.get('experience') or []
                if experiences and len(experiences) > 0:
                    experience_tasks = []
                    for exp in experiences:
                        if 'description' in exp and exp['description']:
                            experience_tasks.append(
                                self._improve_section(
                                    'experience',
                                    exp['description'],
                                    industry
                                )
                            )
                        else:
                            experience_tasks.append(None)
                    improvement_tasks.append(experience_tasks)
                else:
                    improvement_tasks.append([])
                
                # Skills section (treat as a single unit for now)
                skills = cv_content.get('skills', [])
                if skills and len(skills) > 0:
                    # Handle skills as list of objects or strings
                    if isinstance(skills[0], dict):
                        skills_content = "\n".join([skill.get('name', '') for skill in skills])
                    else:
                        skills_content = "\n".join(skills)
                    improvement_tasks.append(
                        self._improve_section(
                            'skills',
                            skills_content,
                            industry
                        )
                    )
                else:
                    improvement_tasks.append(None)
                
                # Execute all improvement tasks
                results = await asyncio.gather(*[
                    task if isinstance(task, asyncio.Future) else 
                    (asyncio.gather(*task) if isinstance(task, list) else asyncio.sleep(0))
                    for task in improvement_tasks if task is not None
                ], return_exceptions=True)
                
                # Process results based on their order in improvement_tasks
                result_index = 0
                
                # Professional summary
                if improvement_tasks[0] is not None:
                    improved_sections['professional_summary'] = results[result_index] if not isinstance(results[result_index], Exception) else None
                    result_index += 1
                
                # Experiences
                if improvement_tasks[1]:
                    experience_results = results[result_index] if not isinstance(results[result_index], Exception) else []
                    result_index += 1
                    
                    if experience_results:
                        improved_experiences = []
                        for i, (exp, result) in enumerate(zip(cv_data['experiences'], experience_results)):
                            improved_exp = exp.copy()
                            if result and not isinstance(result, Exception):
                                improved_exp['description'] = result
                            improved_experiences.append(improved_exp)
                        improved_sections['experiences'] = improved_experiences
                
                # Skills - this would need more work to properly parse and structure
                if improvement_tasks[2] is not None:
                    skill_result = results[result_index] if not isinstance(results[result_index], Exception) else None
                    result_index += 1
                    
                    if skill_result:
                        # Simple parsing of skills into a list
                        skill_lines = skill_result.strip().split('\n')
                        skills = []
                        for line in skill_lines:
                            line = line.strip()
                            if line:
                                # Try to extract name and level, e.g., "Python (Expert)"
                                parts = line.split('(')
                                if len(parts) > 1 and ')' in parts[1]:
                                    name = parts[0].strip()
                                    level = parts[1].split(')')[0].strip()
                                    skills.append({'name': name, 'level': level})
                                else:
                                    skills.append({'name': line})
                        
                        improved_sections['skills'] = skills
                
            except Exception as section_error:
                logger.error(f"Error improving sections: {str(section_error)}")
                # Continue with partial results if we have any
            
            # Create new CV version with improved sections
            new_cv = None
            try:
                # Re-establish database connection before creating new CV
                await connect_db()
                
                # Create new CV using a sync function called through sync_to_async
                new_cv_id = await self._create_cv_version(cv_data, improved_sections, user)
                
                # Update session with results
                await self._safely_update_session_with_results(session, improved_sections, new_cv_id)
                
                return {
                    'status': 'success',
                    'message': 'CV rewritten successfully',
                    'new_cv_id': new_cv_id,
                    'improved_sections': improved_sections
                }
                
            except Exception as cv_error:
                logger.error(f"Error creating new CV version: {str(cv_error)}")
                
                # Update session with error but still return improved sections if available
                await update_session_status(session, 'failed', str(cv_error))
                
                return {
                    'status': 'partial_success' if improved_sections else 'error',
                    'message': 'Failed to create new CV, but section improvements are available' if improved_sections else 'Failed to improve CV',
                    'error': str(cv_error),
                    'improved_sections': improved_sections
                }
                
        except Exception as e:
            logger.error(f"Error in process_rewrite_session: {str(e)}")
            await update_session_status(session, 'failed', str(e))
            
            return {
                'status': 'error',
                'message': 'Failed to process CV rewrite session',
                'error': str(e)
            }

    def rewrite_cv_sync(self, cv_data, user):
        """
        Synchronous version of the rewrite_cv method that doesn't use async/await.
        This method should be used when called from a background task to avoid threading issues.
        
        Args:
            cv_data: CV data to rewrite
            user: User who owns the CV
            
        Returns:
            Dictionary with rewritten content and new CV ID
        """
        try:
            # Ensure clean database connection
            refresh_db_connection()
            
            # Improve each section
            improved_sections = {}
            
            try:
                # Extract the actual CV data - check multiple possible locations
                cv_content = None
                
                # Option 1: Frontend sends parsed_cv.parsed_data structure
                if 'parsed_cv' in cv_data and isinstance(cv_data['parsed_cv'], dict):
                    parsed_cv = cv_data['parsed_cv']
                    if 'parsed_data' in parsed_cv and isinstance(parsed_cv['parsed_data'], dict):
                        cv_content = parsed_cv['parsed_data']
                        logger.info(f"[SYNC] Found parsed_cv.parsed_data with keys: {cv_content.keys()}")
                
                # Option 2: Legacy 'data' key structure  
                elif 'data' in cv_data and isinstance(cv_data['data'], dict):
                    cv_content = cv_data['data']
                    logger.info(f"[SYNC] Found legacy data structure with keys: {cv_content.keys()}")
                
                # Option 3: Direct top-level structure
                else:
                    cv_content = cv_data
                    logger.info("[SYNC] Using top-level data structure")
                
                if not cv_content:
                    logger.error("[SYNC] Could not extract CV content from input data")
                    raise ValueError("Invalid CV data structure")
                
                # Process sections sequentially (no async/await)
                industry = cv_content.get('personal_info', {}).get('industry', 'technology')
                
                # Professional summary section - handle as direct string
                prof_summary = cv_content.get('professional_summary')
                if prof_summary and isinstance(prof_summary, str):
                    prompt = self.improvement_prompts['professional_summary']['template'].format(
                        content=prof_summary,
                        industry=industry
                    )
                    improved_summary = self.deepseek_service.generate_completion_sync(prompt, max_tokens=400)
                    if improved_summary:
                        improved_sections['professional_summary'] = improved_summary
                
                # Experience sections
                experiences = cv_content.get('experiences') or cv_content.get('experience') or []
                if experiences and len(experiences) > 0:
                    improved_experiences = []
                    for exp in experiences:
                        improved_exp = exp.copy()
                        if 'description' in exp and exp['description']:
                            prompt = self.improvement_prompts['experience']['template'].format(
                                content=exp['description'],
                                industry=industry
                            )
                            improved_description = self.deepseek_service.generate_completion_sync(prompt, max_tokens=600)
                            if improved_description:
                                improved_exp['description'] = improved_description
                        improved_experiences.append(improved_exp)
                    improved_sections['experiences'] = improved_experiences
                
                # Skills section
                skills = cv_content.get('skills', [])
                if skills and len(skills) > 0:
                    # Handle skills as list of objects or strings
                    if isinstance(skills[0], dict):
                        skills_content = "\n".join([skill.get('name', '') for skill in skills])
                    else:
                        skills_content = "\n".join(skills)
                    prompt = self.improvement_prompts['skills']['template'].format(
                        content=skills_content,
                        industry=industry
                    )
                    improved_skills_text = self.deepseek_service.generate_completion_sync(prompt, max_tokens=800)
                    
                    if improved_skills_text:
                        # Simple parsing of skills into a list
                        skill_lines = improved_skills_text.strip().split('\n')
                        skills = []
                        for line in skill_lines:
                            line = line.strip()
                            if line:
                                # Try to extract name and level, e.g., "Python (Expert)"
                                parts = line.split('(')
                                if len(parts) > 1 and ')' in parts[1]:
                                    name = parts[0].strip()
                                    level = parts[1].split(')')[0].strip()
                                    skills.append({'name': name, 'level': level})
                                else:
                                    skills.append({'name': line})
                        
                        improved_sections['skills'] = skills
                
            except Exception as section_error:
                logger.error(f"Error improving sections in sync method: {str(section_error)}")
                # Continue with partial results if we have any
            
            # Create new CV version with improved sections
            try:
                # Use the synchronous function directly
                new_cv_id = self._create_cv_version_sync(cv_data, improved_sections, user)
                
                return {
                    'status': 'success',
                    'message': 'CV rewritten successfully',
                    'new_cv_id': new_cv_id,
                    'improved_sections': improved_sections,
                    'rewritten_cv': improved_sections  # Add a rewritten_cv copy of improved_sections
                }
                
            except Exception as cv_error:
                logger.error(f"Error creating new CV version in sync method: {str(cv_error)}")
                
                return {
                    'status': 'partial_success' if improved_sections else 'error',
                    'message': 'Failed to create new CV, but section improvements are available' if improved_sections else 'Failed to improve CV',
                    'error': str(cv_error),
                    'improved_sections': improved_sections,
                    'rewritten_cv': improved_sections  # Add a rewritten_cv copy of improved_sections
                }
                
        except Exception as e:
            logger.error(f"Error in rewrite_cv_sync: {str(e)}")
            
            return {
                'status': 'error',
                'message': 'Failed to rewrite CV',
                'error': str(e),
                'rewritten_cv': cv_data,  # Return original CV data for fallback
                'improved_sections': {}
            }
            
    def _create_cv_version_sync(self, cv_data, improved_sections, user):
        """
        Synchronous version of _create_cv_version to avoid threading issues
        """
        with transaction.atomic():
            return create_cv_with_sections_sync(user, cv_data, improved_sections)

    async def _safely_update_session_with_results(self, session, improved_sections, new_cv_id):
        """Helper method to update session with retry logic"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Reset connections before updating session
                await sync_to_async(close_old_connections)()
                
                # Update session with results
                await update_session_with_results(session, improved_sections, new_cv_id)
                logger.info("Successfully updated session with results")
                return True
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Error updating session (attempt {retry_count}/{max_retries}): {str(e)}")
                    # Exponential backoff
                    await asyncio.sleep(0.5 * (2 ** (retry_count - 1)))
                else:
                    logger.error(f"Failed to update session after {max_retries} attempts: {str(e)}")
                    # We continue without raising since the CV was created successfully
                    return False

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
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Creating CV version (attempt {attempt}/{max_retries})")
                
                # Use direct synchronous approach for database operations
                try:
                    # Call our synchronous function via sync_to_async
                    new_cv_id = await sync_to_async(create_cv_with_sections_sync)(user, cv_data, improved_sections)
                    logger.info(f"Successfully created CV version (ID: {new_cv_id})")
                    return new_cv_id
                except Exception as e:
                    logger.error(f"Error in create_cv_with_sections_sync: {str(e)}")
                    raise
                
            except django.db.utils.OperationalError as e:
                # Handle "connection already closed" errors
                retry_count += 1
                last_exception = e
                
                if retry_count < max_retries:
                    logger.warning(f"Database connection closed, retrying ({retry_count}/{max_retries}): {str(e)}")
                    # Wait before retry
                    time.sleep(1 * retry_count)
                    # Force reset connections
                    close_old_connections()
                    # Try to establish a new connection
                    try:
                        connection.ensure_connection()
                    except Exception as conn_err:
                        logger.warning(f"Error reconnecting: {str(conn_err)}")
                else:
                    logger.error(f"Failed to create CV version after {max_retries} attempts: {str(e)}")
                    raise
            except Exception as e:
                # For other errors, try again but not as many times
                retry_count += 1
                last_exception = e
                
                if retry_count < 2:  # Only retry once for other errors
                    logger.warning(f"Error creating CV version, retrying ({retry_count}/2): {str(e)}")
                    time.sleep(0.5)
                    close_old_connections()
                else:
                    logger.error(f"Error creating CV version: {str(e)}")
                    raise
    
    # Import this at the module level to ensure proper Django settings
    from django.db import close_old_connections