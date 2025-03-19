import os
import json
import logging
import aiohttp
import time
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
        
        if not self.api_key:
            logger.error("DEEPSEEK_API_KEY environment variable is not set")
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")
            
        logger.info(f"Initialized DeepSeekService with model: {self.model}")
    
    async def _call_api(self, prompt, max_tokens=None, temperature=None):
        """
        Make an async call to the DeepSeek API with the provided prompt
        """
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
        
        try:
            logger.info(f"Sending request to DeepSeek API with model: {self.model}")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=90)  # Longer timeout for CV parsing
                ) as response:
                    if response.status == 400:
                        error_detail = (await response.json()).get('error', {}).get('message', 'Unknown error')
                        logger.error(f"Bad request to DeepSeek API: {error_detail}")
                        logger.error(f"Request data: {json.dumps(data, indent=2)}")
                        raise ValueError(f"Bad request to DeepSeek API: {error_detail}")
                    
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
                
        except aiohttp.ClientError as e:
            logger.error(f"Error calling DeepSeek API: {str(e)}")
            raise
    
    async def generate(self, prompt, max_tokens=1000, temperature=0.7, top_p=0.9):
        """Generate text using DeepSeek API"""
        try:
            logger.info(f"Sending request to DeepSeek API with model: {self.model}")
            
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
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            return result['choices'][0]['message']['content']
                        else:
                            raise ValueError("Unexpected response format from DeepSeek API")
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error: {error_text}")
                        raise Exception(f"DeepSeek API error: {error_text}")
                        
        except Exception as e:
            logger.error(f"Error in generate: {str(e)}")
            raise
    
    async def parse_cv(self, text, max_retries=2):
        """
        Parse CV text to extract structured information
        """
        logger.info(f"Parsing CV text ({len(text)} chars) with DeepSeek")
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
        {text}
        """
        
        attempts = 0
        last_error = None
        
        while attempts < max_retries:
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
        logger.error(f"Failed to parse CV after {max_retries} attempts. Last error: {last_error}")
        raise ValueError(f"Failed to parse CV data. Last error: {last_error}")
    
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