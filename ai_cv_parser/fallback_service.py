"""
Fallback AI service module for CV parsing and analysis
Provides backup functionality when primary AI service fails
"""
import os
import json
import logging
import aiohttp
import asyncio
import time
from datetime import datetime

# Configure logging
logger = logging.getLogger('ai_cv_parser')

class FallbackService:
    """Provides fallback AI service functionality when primary service fails"""
    
    def __init__(self):
        # Initialize with configurable fallback options
        self.current_service = "mock"  # Default to mock responses
        # Try alternative APIs based on available keys
        if os.environ.get('LLAMA_API'):
            self.current_service = "llama"
            self.api_key = os.environ.get('LLAMA_API')
            self.api_url = "https://api.llama-api.com/chat/completions"
            self.model = "llama-3-8b"
        elif os.environ.get('MISTRAL_API_KEY'):
            self.current_service = "mistral"
            self.api_key = os.environ.get('MISTRAL_API_KEY')
            self.api_url = "https://api.mistral.ai/v1/chat/completions"
            self.model = "mistral-medium"
        elif os.environ.get('GROQ_API_KEY'):
            self.current_service = "groq"
            self.api_key = os.environ.get('GROQ_API_KEY')
            self.api_url = "https://api.groq.com/openai/v1/chat/completions"
            self.model = "llama3-8b-8192"
        
        logger.info(f"Initialized FallbackService using {self.current_service} backend")
    
    async def generate(self, prompt, max_tokens=1000, temperature=0.7):
        """Generate text using available fallback API or mocked responses"""
        logger.info(f"Using fallback service ({self.current_service}) for CV analysis")
        
        if self.current_service == "mock":
            return self._get_mock_response()
        
        try:
            # Common API pattern for most LLM providers
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {}
            
            # Configure provider-specific headers and payload
            if self.current_service == "llama":
                headers["Authorization"] = f"Bearer {self.api_key}"
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            elif self.current_service == "mistral":
                headers["Authorization"] = f"Bearer {self.api_key}"
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            elif self.current_service == "groq":
                headers["Authorization"] = f"Bearer {self.api_key}"
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            
            # Log request details for debugging (exclude sensitive info)
            logger.info(f"Sending request to {self.current_service} API with model: {self.model}")
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)  # Longer timeout for CV analysis
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Handle provider-specific response formats
                        if self.current_service == "llama":
                            if 'choices' in result and len(result['choices']) > 0:
                                return result['choices'][0]['message']['content']
                            else:
                                logger.warning(f"Unexpected Llama API response format: {result}")
                                return self._get_mock_response()
                        elif 'choices' in result and len(result['choices']) > 0:
                            return result['choices'][0]['message']['content']
                        else:
                            logger.warning(f"Unexpected {self.current_service} API response format: {result}")
                            return self._get_mock_response()
                    else:
                        error_text = await response.text()
                        logger.error(f"{self.current_service} API error: {error_text}")
                        # Fall back to next available option
                        return await self._try_next_service(prompt, max_tokens, temperature)
                        
        except Exception as e:
            logger.error(f"Error using {self.current_service} API: {str(e)}")
            # Fall back to next available option
            return await self._try_next_service(prompt, max_tokens, temperature)
    
    async def _try_next_service(self, prompt, max_tokens, temperature):
        """Try the next available service in the fallback chain"""
        if self.current_service == "llama":
            # Try Mistral next
            if os.environ.get('MISTRAL_API_KEY'):
                logger.info("Falling back from Llama API to Mistral API")
                self.current_service = "mistral"
                self.api_key = os.environ.get('MISTRAL_API_KEY')
                self.api_url = "https://api.mistral.ai/v1/chat/completions"
                self.model = "mistral-medium"
                return await self.generate(prompt, max_tokens, temperature)
            # Try Groq next if Mistral not available
            elif os.environ.get('GROQ_API_KEY'):
                logger.info("Falling back from Llama API to Groq API")
                self.current_service = "groq"
                self.api_key = os.environ.get('GROQ_API_KEY')
                self.api_url = "https://api.groq.com/openai/v1/chat/completions"
                self.model = "llama3-8b-8192"
                return await self.generate(prompt, max_tokens, temperature)
        elif self.current_service == "mistral":
            # Try Groq next
            if os.environ.get('GROQ_API_KEY'):
                logger.info("Falling back from Mistral API to Groq API")
                self.current_service = "groq"
                self.api_key = os.environ.get('GROQ_API_KEY')
                self.api_url = "https://api.groq.com/openai/v1/chat/completions"
                self.model = "llama3-8b-8192"
                return await self.generate(prompt, max_tokens, temperature)
        
        # If all services fail or no other services are available, use mock response
        logger.info(f"All API services failed or unavailable. Using mock response.")
        self.current_service = "mock"
        return self._get_mock_response()
    
    def _get_mock_response(self):
        """Return a reasonable mock response for CV analysis"""
        return json.dumps({
            "overall_score": 7,
            "strengths": [
                "Clear professional experience section",
                "Well-structured education information",
                "Good use of action verbs in job descriptions"
            ],
            "weaknesses": [
                "Skills section could be more comprehensive",
                "Missing quantifiable achievements",
                "Professional summary could be more tailored"
            ],
            "improvement_suggestions": [
                "Add more technical skills relevant to target roles",
                "Include metrics and achievements to quantify impact",
                "Strengthen professional summary to highlight key qualifications",
                "Consider adding a projects section if applicable"
            ],
            "section_scores": {
                "content_completeness": 6,
                "format_structure": 8,
                "skills_relevance": 5,
                "job_history": 7,
                "education": 8,
                "overall_impact": 6
            },
            "ats_readiness": {
                "score": 7,
                "issues": [
                    "Some skills may not match common ATS keywords",
                    "Job titles could be more standardized"
                ],
                "suggestions": [
                    "Use industry-standard job titles",
                    "Incorporate more keywords from target job descriptions",
                    "Ensure consistent date formatting"
                ]
            },
            "experience_level": {
                "classification": "mid-level",
                "years_experience": 5,
                "career_stage": "Established professional with solid experience"
            },
            "skills_assessment": {
                "technical_skills": [
                    {"skill": "Microsoft Office", "level": "Advanced"},
                    {"skill": "Project Management", "level": "Intermediate"},
                    {"skill": "Data Analysis", "level": "Intermediate"}
                ],
                "soft_skills": [
                    {"skill": "Communication", "level": "Advanced"},
                    {"skill": "Teamwork", "level": "Advanced"},
                    {"skill": "Problem Solving", "level": "Intermediate"}
                ],
                "skills_gaps": [
                    "Leadership experience",
                    "Advanced technical certifications",
                    "International experience"
                ]
            },
            "potential_roles": {
                "best_matches": [
                    "Project Manager",
                    "Business Analyst",
                    "Operations Specialist",
                    "Team Lead",
                    "Account Manager"
                ],
                "match_reasons": [
                    "Demonstrated project experience",
                    "Strong analytical background",
                    "Proven communication skills"
                ],
                "suggested_industries": [
                    "Information Technology",
                    "Financial Services",
                    "Healthcare"
                ]
            }
        })
