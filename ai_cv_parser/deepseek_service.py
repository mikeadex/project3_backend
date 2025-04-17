import os
import json
import logging
import aiohttp
import asyncio
import time
import traceback
from datetime import datetime

# Configure logging
logger = logging.getLogger('ai_cv_parser')

class DeepSeekService:
    """Service for interacting with DeepSeek API to parse CVs"""
    
    def __init__(self):
        self.api_key = os.environ.get('DEEPSEEK_API_KEY')
        self.api_url = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1')
        self.model = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
        self.max_tokens = 4000
        self.temperature = 0.2
        self.is_available = bool(self.api_key)
        
        # Don't raise an error here, just log a warning so the application can still function
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY environment variable is not set. Using fallback mechanisms.")
            
        logger.info(f"Initialized DeepSeekService with model: {self.model}, available: {self.is_available}")
    
    async def _call_api(self, prompt, max_tokens=None, temperature=None):
        """
        Make an async call to the DeepSeek API with the provided prompt
        """
        # If API key is not available, use fallback immediately
        if not self.is_available:
            logger.warning("DeepSeek API key not available. Using fallback approach.")
            return self._generate_fallback_response(prompt)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional CV/resume parser. Your task is to extract structured information from CV text and format it as JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "response_format": {"type": "json_object"}
        }
        
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                attempt += 1
                logger.info(f"Sending request to DeepSeek API with model: {self.model} (attempt {attempt}/{max_retries})")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=aiohttp.ClientTimeout(total=120)  # Longer timeout (2 minutes)
                    ) as response:
                        if response.status == 400:
                            error_detail = (await response.json()).get('error', {}).get('message', 'Unknown error')
                            logger.error(f"Bad request to DeepSeek API: {error_detail}")
                            logger.error(f"Request data: {json.dumps(data, indent=2)}")
                            raise ValueError(f"Bad request to DeepSeek API: {error_detail}")
                        
                        if response.status >= 500 and attempt < max_retries:
                            # Server error, retry
                            logger.warning(f"Server error from DeepSeek API: {response.status}. Retrying...")
                            await asyncio.sleep(2 * attempt)  # Exponential backoff
                            continue
                        
                        response.raise_for_status()
                        result = await response.json()
                        
                        if 'choices' in result and len(result['choices']) > 0:
                            content = result['choices'][0]['message']['content']
                            logger.info("Successfully received response from DeepSeek API")
                            return content
                        else:
                            error_msg = f"Unexpected API response format: {result}"
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                    
            except asyncio.TimeoutError:
                logger.error(f"DeepSeek API request timed out (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(2 * attempt)  # Exponential backoff
                    continue
                raise ValueError("DeepSeek API request timed out after multiple attempts")
                
            except aiohttp.ClientError as e:
                logger.error(f"Error calling DeepSeek API: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 * attempt)  # Exponential backoff
                    continue
                raise
                
            except Exception as e:
                logger.error(f"Unexpected error in _call_api: {str(e)}")
                raise
    
    def _generate_fallback_response(self, prompt):
        """
        Generate a fallback response when the API key is missing
        """
        logger.info("Generating fallback response")
        return {
            "error": "DeepSeek API key is not configured",
            "message": "Please contact the administrator to set up the API key.",
            "parsed_data_fallback": {
                "personal_info": {
                    "name": "Could not parse - API not configured",
                    "email": "",
                    "phone": "",
                    "location": ""
                },
                "professional_summary": "CV parsing requires API configuration. Please contact the administrator.",
                "skills": [],
                "experience": [],
                "education": [],
                "certifications": [],
                "languages": []
            }
        }
    
    async def generate(self, prompt, max_tokens=1000, temperature=0.7, top_p=0.9):
        """Generate text using DeepSeek API"""
        max_retries = 2
        attempt = 0
        
        while attempt < max_retries:
            try:
                attempt += 1
                logger.info(f"Sending request to DeepSeek API with model: {self.model} (attempt {attempt}/{max_retries})")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            "top_p": top_p
                        },
                        timeout=aiohttp.ClientTimeout(total=120)  # Increase timeout to 2 minutes
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if 'choices' in result and len(result['choices']) > 0:
                                return result['choices'][0]['message']['content']
                            else:
                                raise ValueError("Unexpected response format from DeepSeek API")
                        else:
                            error_text = await response.text()
                            logger.error(f"DeepSeek API error ({response.status}): {error_text}")
                            
                            # If it's a server error, retry
                            if response.status >= 500 and attempt < max_retries:
                                logger.info(f"Retrying due to server error ({response.status})")
                                await asyncio.sleep(2)  # Wait before retry
                                continue
                                
                            raise Exception(f"DeepSeek API error ({response.status}): {error_text}")
                        
            except asyncio.TimeoutError:
                logger.error(f"Timeout calling DeepSeek API (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(2)  # Wait before retry
                    continue
                raise Exception("DeepSeek API request timed out after multiple attempts")
            except aiohttp.ClientError as e:
                logger.error(f"Client error calling DeepSeek API: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                raise
            except Exception as e:
                logger.error(f"Error in generate: {str(e)}")
                raise
    
    async def generate_completion(self, prompt, max_tokens=2000, temperature=0.2):
        """
        Generate text completion using DeepSeek API.
        For text completion without JSON, use this method instead of generate_json.
        """
        try:
            result = await self.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return result
        except Exception as e:
            logger.error(f"Error in generate_completion: {str(e)}")
            return None
            
    def generate_completion_sync(self, prompt, max_tokens=2000, temperature=0.2):
        """
        Synchronous version of generate_completion.
        For text completion without JSON, use this method in synchronous contexts.
        """
        try:
            # Create a new event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async generate method in the event loop
                result = loop.run_until_complete(self.generate(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                ))
                return result
            finally:
                # Always close the loop
                loop.close()
                
        except Exception as e:
            logger.error(f"Error in generate_completion_sync: {str(e)}")
            return None
    
    def make_custom_request(self, prompt, max_tokens=None, temperature=None):
        """
        Synchronous wrapper for making requests to the DeepSeek API
        
        This method is designed to be used in non-async contexts like Django views
        """
        logger.info("Making custom synchronous request to DeepSeek API")
        
        try:
            # Create a new event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async generate method in the event loop
                result = loop.run_until_complete(self.generate(
                    prompt=prompt,
                    max_tokens=max_tokens or self.max_tokens,
                    temperature=temperature or self.temperature
                ))
                
                # Try to parse the result as JSON if it's not already
                try:
                    # If it's already valid JSON, return as is
                    json_result = json.loads(result)
                    return json_result
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    if "```json" in result:
                        json_content = result.split("```json")[1].split("```")[0].strip()
                        json_result = json.loads(json_content)
                        return json_result
                    elif "```" in result:
                        # Try to extract from any code block
                        json_content = result.split("```")[1].split("```")[0].strip()
                        json_result = json.loads(json_content)
                        return json_result
                    else:
                        # If no JSON can be extracted, return a fallback response
                        logger.error("Could not extract JSON from DeepSeek response")
                        return {
                            "error": "Could not parse AI response as JSON",
                            "raw_response": result[:500]  # Truncate for logging
                        }
            finally:
                # Always close the loop
                loop.close()
                
        except Exception as e:
            logger.error(f"Error in make_custom_request: {str(e)}")
            return {
                "error": str(e),
                "message": "Failed to process the request due to an internal error"
            }
    
    async def parse_cv(self, cv_text, extract_sections=True):
        """
        Parse a CV text into structured data
        
        Args:
            cv_text: The raw CV text to parse
            extract_sections: Whether to extract sections as well
            
        Returns:
            Structured CV data in JSON format
        """
        if not self.is_available:
            logger.warning("DeepSeek API key not available. Using fallback approach for CV parsing.")
            return self._generate_fallback_cv_parse(cv_text)
            
        logger.info(f"Parsing CV text ({len(cv_text)} chars) with DeepSeek")
        start_time = time.time()
        
        cv_parsing_prompt = f"""
        Extract structured information from the following CV text. 
        Format the output as a valid JSON object with the following sections:
        
        - personal_info: Object containing name, email, phone, location, etc.
        - professional_summary: A concise summary of the candidate's background
        - skills: Array of objects with "name" and "level" (Beginner, Intermediate, Advanced, Expert)
        - experience: Array of work experiences, each with job_title, company, location, start_date, end_date, and description
        - education: Array of education entries with school, degree, field, start_date, end_date
        - certifications: Array of certifications with name, issuer, and date
        - languages: Array of language proficiencies with language name and level
        
        If a section has no information, include it as an empty array or object.
        If dates are unclear, make reasonable estimates based on the context.
        Focus on accuracy and completeness while maintaining the JSON structure.
        
        CV TEXT:
        {cv_text}
        """
        
        attempts = 0
        last_error = None
        
        while attempts < 3:
            try:
                attempts += 1
                logger.info(f"Attempt {attempts} to parse CV")
                response = await self._call_api(cv_parsing_prompt)
                
                # Try to extract JSON from the response
                try:
                    # First try to parse directly
                    parsed_data = json.loads(response)
                    logger.info(f"Successfully parsed CV in {time.time() - start_time:.2f} seconds")
                    return parsed_data
                except json.JSONDecodeError:
                    # Try to extract JSON if surrounded by markdown code blocks or other text
                    if "```json" in response:
                        json_content = response.split("```json")[1].split("```")[0].strip()
                        parsed_data = json.loads(json_content)
                        logger.info(f"Successfully parsed CV JSON from markdown in {time.time() - start_time:.2f} seconds")
                        return parsed_data
                    elif "```" in response:
                        json_content = response.split("```")[1].split("```")[0].strip()
                        parsed_data = json.loads(json_content)
                        logger.info(f"Successfully parsed CV from code block in {time.time() - start_time:.2f} seconds")
                        return parsed_data
                    else:
                        raise ValueError("Could not extract valid JSON from DeepSeek response")
                        
            except (ValueError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempts} failed: {last_error}. Retrying...")
                await asyncio.sleep(2)  # Short delay before retry
        
        # If we get here, all attempts failed
        logger.error(f"Failed to parse CV after {3} attempts. Last error: {last_error}")
        raise ValueError(f"Failed to parse CV data. Last error: {last_error}")
    
    def _generate_fallback_cv_parse(self, cv_text):
        """
        Generate a fallback parsed CV when the API key is missing
        """
        logger.info("Generating fallback parsed CV")
        # Extract some basic information from the CV text to provide minimal functionality
        lines = cv_text.split("\n")
        name = next((line for line in lines[:10] if len(line) > 0 and len(line) < 40), "Name Not Found")
        
        return {
            "personal_info": {
                "name": name,
                "email": "email@example.com",
                "phone": "",
                "location": ""
            },
            "sections": {
                "summary": "",
                "experience": [],
                "education": [],
                "skills": [],
                "certifications": [],
                "languages": []
            },
            "raw_text": cv_text[:100] + "..." if len(cv_text) > 100 else cv_text,
            "note": "This is a fallback parse as the DeepSeek API is not configured. Please contact the administrator."
        }
    
    async def rewrite_cv_section(self, section_name, content, industry="technology"):
        """
        Rewrite a specific CV section with improvements
        
        Args:
            section_name: Name of the section (summary, experience, etc.)
            content: Original content to improve
            industry: Target industry for optimization
            
        Returns:
            Improved section content
        """
        if not self.is_available:
            logger.warning("DeepSeek API key not available. Using fallback approach for section rewrite.")
            return self._generate_fallback_section_rewrite(section_name, content)
            
        logger.info(f"Rewriting CV section: {section_name}")
        start_time = time.time()
        
        section_rewrite_prompt = f"""
        Improve the following CV section to make it more effective and engaging for the {industry} industry.
        
        Section: {section_name}
        Content:
        {content}
        
        Focus on clarity, impact, and relevance to the industry. Use specific examples and metrics where possible.
        """
        
        attempts = 0
        last_error = None
        
        while attempts < 3:
            try:
                attempts += 1
                logger.info(f"Attempt {attempts} to rewrite CV section")
                response = await self._call_api(section_rewrite_prompt)
                
                try:
                    # First try to parse directly
                    rewritten_section = response.strip()
                    logger.info(f"Successfully rewrote CV section in {time.time() - start_time:.2f} seconds")
                    return rewritten_section
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Attempt {attempts} failed: {last_error}. Retrying...")
                    await asyncio.sleep(2)  # Short delay before retry
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempts} failed: {last_error}. Retrying...")
                await asyncio.sleep(2)  # Short delay before retry
        
        # If we get here, all attempts failed
        logger.error(f"Failed to rewrite CV section after {3} attempts. Last error: {last_error}")
        raise ValueError(f"Failed to rewrite CV section. Last error: {last_error}")
    
    def _generate_fallback_section_rewrite(self, section_name, content):
        """
        Generate a fallback improved section when the API key is missing
        """
        logger.info(f"Generating fallback improved section for {section_name}")
        sample_improvements = {
            "summary": "As a dedicated professional with experience in this field, I bring a strong combination of technical skills and business knowledge. I have consistently delivered results while working collaboratively with cross-functional teams.",
            "experience": "• Led development of key projects, improving efficiency by 20%\n• Collaborated with cross-functional teams to deliver strategic initiatives\n• Implemented innovative solutions to complex business problems",
            "skills": "• Technical: Programming, Data Analysis, Project Management\n• Soft Skills: Communication, Leadership, Problem-solving\n• Industry Knowledge: Business Analysis, Market Research"
        }
        
        return sample_improvements.get(section_name.lower(), content) + "\n\n(Note: Using sample content as the CV improvement API is not configured)"
    
    async def extract_sections(self, text):
        """
        Extract main sections from a CV without full parsing
        """
        section_prompt = f"""
        Extract the main section headings from this CV/resume text. Return just a JSON array of section names.
        
        CV TEXT:
        {text[:2000]}...
        """
        
        try:
            response = await self._call_api(section_prompt, max_tokens=500)
            
            # Try to extract JSON
            try:
                if "```json" in response:
                    sections = json.loads(response.split("```json")[1].split("```")[0].strip())
                elif "```" in response:
                    sections = json.loads(response.split("```")[1].split("```")[0].strip())
                else:
                    sections = json.loads(response)
                
                return sections
            except json.JSONDecodeError:
                logger.error("Could not decode JSON from section extraction response")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting sections: {str(e)}")
            return [] 
    
    async def analyze_cv(self, parsed_data, max_retries=2):
        """
        Analyze parsed CV data to provide detailed analysis, feedback, and suggestions for improvement
        
        Returns a structured JSON with analysis metrics, scores, and recommendations
        """
        logger.info("Analyzing parsed CV data with DeepSeek")
        start_time = time.time()
        
        # Convert parsed data to a string for the prompt
        parsed_data_str = json.dumps(parsed_data, indent=2)
        
        analysis_prompt = f"""
        Analyze the following parsed CV data and provide a detailed assessment. 
        
        Your task is to evaluate this CV and provide structured feedback in the following JSON format:
        
        {{
            "overall_score": <score from 1-10>,
            "section_scores": {{
                "professional_summary": <score from 1-10>,
                "experience": <score from 1-10>,
                "education": <score from 1-10>,
                "skills": <score from 1-10>
            }},
            "strengths": [<list of CV strengths>],
            "weaknesses": [<list of CV weaknesses>],
            "improvement_suggestions": [<list of specific suggestions>],
            "ats_readiness": {{
                "score": <score from 1-10>,
                "issues": [<list of ATS issues>],
                "recommendations": [<list of recommendations>]
            }},
            "experience_level": {{
                "years_experience": <estimated years>,
                "classification": <"Entry-Level", "Mid-Level", "Senior", or "Executive">
            }},
            "skills_assessment": {{
                "technical_skills": [
                    {{"skill": <skill name>, "level": <score from 1-10>}}
                ],
                "soft_skills": [
                    {{"skill": <skill name>, "level": <score from 1-10>}}
                ]
            }},
            "potential_roles": {{
                "best_matches": [<list of suitable job roles>],
                "match_reasons": [<list of reasons why these roles match>],
                "suggested_industries": [<list of suitable industries>]
            }}
        }}
        
        Focus on providing actionable insights and specific suggestions for improvement.
        Evaluate whether keywords are effectively used for ATS systems.
        Analyze the clarity, impact, and quantification of achievements.
        Assess whether the CV effectively showcases relevant skills and experience.
        
        PARSED CV DATA:
        {parsed_data_str}
        """
        
        attempts = 0
        last_error = None
        
        while attempts < max_retries:
            try:
                attempts += 1
                logger.info(f"Attempt {attempts} to analyze CV")
                response = await self._call_api(analysis_prompt)
                
                # Try to extract JSON from the response
                try:
                    # First try to parse directly
                    analysis_data = json.loads(response)
                    logger.info(f"Successfully analyzed CV in {time.time() - start_time:.2f} seconds")
                    return analysis_data
                except json.JSONDecodeError:
                    # Try to extract JSON if surrounded by markdown code blocks or other text
                    if "```json" in response:
                        json_content = response.split("```json")[1].split("```")[0].strip()
                        analysis_data = json.loads(json_content)
                        logger.info(f"Successfully analyzed CV from markdown in {time.time() - start_time:.2f} seconds")
                        return analysis_data
                    elif "```" in response:
                        json_content = response.split("```")[1].split("```")[0].strip()
                        analysis_data = json.loads(json_content)
                        logger.info(f"Successfully analyzed CV from code block in {time.time() - start_time:.2f} seconds")
                        return analysis_data
                    else:
                        raise ValueError("Could not extract valid JSON from DeepSeek analysis response")
                        
            except (ValueError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempts} failed: {last_error}. Retrying...")
                await asyncio.sleep(2)  # Short delay before retry
        
        # If we get here, all attempts failed
        logger.error(f"Failed to analyze CV after {max_retries} attempts. Last error: {last_error}")
        raise ValueError(f"Failed to analyze CV data. Last error: {last_error}")
    
    def parse_document(self, file_path, text=None):
        """
        Synchronous method to parse a document file and extract structured CV data.
        
        This method is designed to be called directly from views without needing to handle async code.
        
        Args:
            file_path (str): Path to the document file to parse
            text (str, optional): Pre-extracted text from the document. If None, text will be extracted from file_path
            
        Returns:
            dict: Parsed CV data structure
        """
        logger.info(f"Parsing document at: {file_path}")
        start_time = time.time()
        
        try:
            # Check if API key is available
            if not self.api_key:
                logger.error("DeepSeek API key is not configured. Please set the DEEPSEEK_API_KEY environment variable.")
                return {
                    "error": "DeepSeek API key is not configured",
                    "message": "Please contact the administrator to set up the API key.",
                    "parsed_data_fallback": {
                        "personal_info": {
                            "name": "Could not parse - API not configured",
                            "email": "",
                            "phone": "",
                            "location": ""
                        },
                        "professional_summary": "CV parsing requires API configuration. Please contact the administrator.",
                        "skills": [],
                        "experience": [],
                        "education": [],
                        "certifications": [],
                        "languages": []
                    }
                }
            
            # Extract text from file if not provided
            if text is None:
                # Extract text based on file type
                text = ""
                try:
                    file_lower = file_path.lower()
                    
                    if file_lower.endswith('.txt'):
                        # Plain text file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                    elif file_lower.endswith('.pdf'):
                        # PDF file
                        try:
                            import PyPDF2
                            with open(file_path, 'rb') as f:
                                pdf_reader = PyPDF2.PdfReader(f)
                                for page_num in range(len(pdf_reader.pages)):
                                    text += pdf_reader.pages[page_num].extract_text() + '\n'
                        except ImportError:
                            logger.error("PyPDF2 not installed. Please install it with pip install PyPDF2")
                            raise ValueError("PyPDF2 is required for PDF extraction but not installed")
                    elif file_lower.endswith('.docx'):
                        # DOCX file
                        try:
                            import docx
                            doc = docx.Document(file_path)
                            text = '\n'.join([para.text for para in doc.paragraphs])
                        except ImportError:
                            logger.error("python-docx not installed. Please install it with pip install python-docx")
                            raise ValueError("python-docx is required for DOCX extraction but not installed")
                    elif file_lower.endswith('.doc'):
                        # Legacy DOC file - requires textract
                        try:
                            import textract
                            text = textract.process(file_path).decode('utf-8')
                        except ImportError:
                            logger.error("textract not installed. Please install it with pip install textract")
                            raise ValueError("textract is required for DOC extraction but not installed")
                    else:
                        raise ValueError(f"Unsupported file type: {file_path}")
                    
                    logger.info(f"Successfully extracted {len(text)} characters of text from {file_path}")
                except Exception as e:
                    logger.error(f"Error extracting text from file: {str(e)}")
                    raise ValueError(f"Failed to extract text from document: {str(e)}")
            
            # Check if we have text to parse
            if not text or len(text.strip()) < 10:
                logger.error(f"Extracted text is too short or empty: '{text}'")
                return {
                    "error": "Extracted text is too short or empty",
                    "message": "Could not extract meaningful text from the document"
                }
            
            # Create a new event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async parse_cv method in the event loop
                result = loop.run_until_complete(self.parse_cv(text))
                logger.info(f"Document parsing completed in {time.time() - start_time:.2f} seconds")
                return result
            except Exception as e:
                logger.error(f"Error during async CV parsing: {str(e)}")
                # Return a structured fallback response
                return {
                    "error": f"Error during CV parsing: {str(e)}",
                    "message": "Failed to parse CV data with AI service",
                    "extracted_text": text[:500] + "..." if len(text) > 500 else text,  # Include truncated text for debugging
                    "parsed_data_fallback": {
                        "personal_info": {
                            "name": "Parsing Error",
                            "email": "",
                            "phone": "",
                            "location": ""
                        },
                        "professional_summary": f"Error parsing CV: {str(e)}",
                        "skills": [],
                        "experience": [],
                        "education": [],
                        "certifications": [],
                        "languages": []
                    }
                }
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error in parse_document: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "error": str(e),
                "message": "Failed to parse document",
                "parsed_data_fallback": {
                    "personal_info": {
                        "name": "Processing Error",
                        "email": "",
                        "phone": "",
                        "location": ""
                    },
                    "professional_summary": f"An error occurred while processing this CV: {str(e)}",
                    "skills": [],
                    "experience": [],
                    "education": [],
                    "certifications": [],
                    "languages": []
                }
            }