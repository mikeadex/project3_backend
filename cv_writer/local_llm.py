from llama_cpp import Llama
import os
import logging
from typing import Dict, Optional
from pathlib import Path
import json
from django.conf import settings

logger = logging.getLogger(__name__)

class LocalLLMService:
    def __init__(self):
        self.model = None
        self._initialize_model()
        
        self.prompts = {
            'professional_summary': """<s>[INST] You are an expert CV writer. Improve this professional summary to be more impactful. Focus on years of experience, key achievements, core skills, and career objectives. Keep it concise (100-150 words). Use active voice and strong verbs. Do not include any explanatory text, just return the improved summary.

Original summary:
{content}

Return only the improved summary: [/INST]""",
            'experience': """<s>[INST] You are an expert CV writer. Transform this job description into achievement-focused bullet points. Use strong action verbs, include metrics, and emphasize leadership impact. Do not include any explanatory text, just return the improved description.

Original description:
{content}

Return only the improved description: [/INST]""",
            'skills': """<s>[INST] You are an expert CV writer. Organize these skills into clear categories with proficiency levels. Format them as follows:
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
            # Get model path from Django settings
            model_path = settings.LLAMA_MODEL_PATH
            logger.info(f"Initializing model from: {model_path}")
            
            # Create models directory if it doesn't exist
            models_dir = os.path.dirname(model_path)
            if not os.path.exists(models_dir):
                logger.info(f"Creating models directory: {models_dir}")
                os.makedirs(models_dir)
            
            # Check if model exists
            if not os.path.exists(model_path):
                error_msg = f"Model file not found at {model_path}. Please download the model and place it in the models directory."
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Initialize with optimized settings
            logger.info("Loading model with optimized settings")
            self.model = Llama(
                model_path=model_path,
                n_ctx=2048,          # Reduced context window for faster processing
                n_batch=512,         # Increased batch size for better throughput
                n_threads=4,         # Use multiple threads
                n_gpu_layers=0       # Adjust based on GPU availability
            )
            logger.info(f"Model initialized successfully from {model_path}")
            
        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}")
            raise

    def improve_text(self, section: str, content: str, max_tokens: int = 500) -> Optional[str]:
        """Improve text using local Llama model."""
        try:
            logger.info(f"Improving text for section: {section}")
            prompt = self.prompts.get(section, "")
            if not prompt:
                logger.error(f"No prompt template found for section: {section}")
                return None
                
            formatted_prompt = prompt.format(content=content)
            logger.debug(f"Generated prompt: {formatted_prompt}")
            
            # Generate improvement
            logger.info("Generating improvement")
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
            
            # Extract and clean generated text
            if response and 'choices' in response and len(response['choices']) > 0:
                text = response['choices'][0]['text'].strip()
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
                    # Format skills into categories
                    categories = ['Technical Skills:', 'Soft Skills:', 'Domain Knowledge:']
                    formatted_lines = []
                    current_category = None
                    
                    for line in text.split('\n'):
                        line = line.strip()
                        # Remove asterisks and other markers
                        line = line.lstrip('•').lstrip('*').strip()
                        
                        if any(cat.lower() in line.lower() for cat in categories):
                            # Find the matching category (case-insensitive)
                            for cat in categories:
                                if cat.lower() in line.lower():
                                    current_category = cat
                                    break
                            formatted_lines.append(f"\n{current_category}")
                        elif line and current_category:
                            # Clean up skill entries
                            skills = []
                            for skill in line.split(','):
                                skill = skill.strip()
                                if all(x.lower() not in skill.lower() for x in ['area', 'none', 'n/a', 'listed']):
                                    skills.append(skill)
                            if skills:
                                formatted_lines.append("  " + ", ".join(skills))
                    
                    # Remove empty categories
                    lines = []
                    current_category = None
                    for line in formatted_lines:
                        if line.strip() in categories:
                            current_category = line
                        elif line.strip():
                            if current_category:
                                lines.append(current_category)
                                current_category = None
                            lines.append(line)
                    
                    text = "\n".join(lines)
                else:
                    # For summary and other sections, just clean up whitespace
                    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
                
                logger.info(f"Cleaned and formatted output: {text[:100]}...")
                return text.strip()
            
            logger.error("No valid response from model")
            return None
            
        except Exception as e:
            logger.error(f"Error in LLM processing: {str(e)}")
            return None

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
        if not self.model:
            raise ValueError("Model not initialized")

        try:
            # Extract CV sections
            professional_summary = cv_data.get('professional_summary', '')
            experiences = cv_data.get('experiences', [])
            education = cv_data.get('education', [])
            skills = cv_data.get('skills', [])
            
            # Create structured prompt for the entire CV
            prompt = f"""As an expert CV writer, rewrite this CV to be more professional, impactful, and achievement-oriented while maintaining complete accuracy of all information. Focus on highlighting the candidate's value proposition and key achievements.

            Guidelines:
            1. Maintain all factual information exactly as provided
            2. Use strong action verbs and professional language
            3. Highlight quantifiable achievements and results
            4. Ensure consistent formatting and style
            5. Focus on impact and value delivered
            6. Keep descriptions concise but detailed
            7. Never add or fabricate information

            Original CV:
            
            Professional Summary:
            {professional_summary}

            Experience:
            {self._format_experiences(experiences)}

            Education:
            {self._format_education(education)}

            Skills:
            {', '.join(skills) if isinstance(skills, list) else skills}

            Please rewrite the entire CV maintaining the same structure but improving the language and impact.
            
            Rewritten CV:"""

            # Generate improved CV
            logger.info("Generating improved CV")
            response = self.model.create_completion(
                prompt,
                max_tokens=2000,       # Increased for full CV
                temperature=0.7,       # Balanced creativity
                top_p=0.9,            # Focused sampling
                repeat_penalty=1.1,    # Prevent repetition
                stop=["Original CV:", "\n\n\n"],
            )

            # Extract and clean the response
            rewritten_cv = response['choices'][0]['text'].strip()
            
            # Validate the output
            if len(rewritten_cv) < 100:
                raise ValueError("Generated CV is too short")

            # Parse the rewritten CV back into sections
            sections = self._parse_cv_sections(rewritten_cv)

            return {
                'original': cv_data,
                'rewritten': sections
            }

        except Exception as e:
            logger.error(f"Error in rewrite_cv: {str(e)}")
            raise

    def _format_experiences(self, experiences):
        """Format experiences for the prompt."""
        formatted = []
        for exp in experiences:
            formatted.append(f"""
            Company: {exp.get('company', '')}
            Position: {exp.get('position', '')}
            Duration: {exp.get('startDate', '')} - {exp.get('endDate', '')}
            Description: {exp.get('job_description', '')}
            Achievements: {exp.get('achievements', '')}
            """)
        return "\n".join(formatted)

    def _format_education(self, education):
        """Format education for the prompt."""
        formatted = []
        for edu in education:
            formatted.append(f"""
            Institution: {edu.get('institution', '')}
            Degree: {edu.get('degree', '')}
            Duration: {edu.get('startDate', '')} - {edu.get('endDate', '')}
            Details: {edu.get('details', '')}
            """)
        return "\n".join(formatted)

    def _parse_cv_sections(self, cv_text):
        """Parse the rewritten CV text back into structured sections."""
        sections = {
            'professional_summary': '',
            'experiences': [],
            'education': [],
            'skills': []
        }

        # Split into sections
        parts = cv_text.split('\n\n')
        current_section = None

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if 'Professional Summary:' in part:
                current_section = 'summary'
                sections['professional_summary'] = part.replace('Professional Summary:', '').strip()
            elif 'Experience:' in part:
                current_section = 'experience'
            elif 'Education:' in part:
                current_section = 'education'
            elif 'Skills:' in part:
                current_section = 'skills'
                skills_text = part.replace('Skills:', '').strip()
                sections['skills'] = [s.strip() for s in skills_text.split(',')]
            elif current_section == 'experience' and 'Company:' in part:
                exp = self._parse_experience(part)
                if exp:
                    sections['experiences'].append(exp)
            elif current_section == 'education' and 'Institution:' in part:
                edu = self._parse_education(part)
                if edu:
                    sections['education'].append(edu)

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
