import os
import json
import logging
import aiohttp
import asyncio
import time
import traceback
from datetime import datetime

# Configure logging
logger = logging.getLogger("ai_cv_parser")


class DeepSeekService:
    """Service for interacting with DeepSeek API to parse CVs"""

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.api_url = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        self.max_tokens = 4000
        self.temperature = 0.2

        # Don't raise an error here, just log a warning so the application can still function
        if not self.api_key:
            logger.warning(
                "DEEPSEEK_API_KEY environment variable is not set. Some features may not work properly."
            )

        logger.info(f"Initialized DeepSeekService with model: {self.model}")

    async def _call_api(self, prompt, max_tokens=None, temperature=None, model=None, system_content=None, response_format=None):
        """
        Make an async call to the DeepSeek API with the provided prompt
        
        Args:
            prompt: The user prompt
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            model: Override the default model (e.g., 'deepseek-reasoner' for better quality)
            system_content: Override the system message
            response_format: Override response format (None for reasoning model, {"type": "json_object"} for chat)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Use provided model or default
        use_model = model or self.model
        
        # Default system content
        default_system = "You are a professional CV/resume parser. Your task is to extract structured information from CV text and format it as JSON."
        
        data = {
            "model": use_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content or default_system,
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
        }
        
        # Only add response_format if specified (reasoning model doesn't support it)
        if response_format is not None:
            data["response_format"] = response_format
        elif use_model == "deepseek-chat":
            # Default to JSON for chat model
            data["response_format"] = {"type": "json_object"}

        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                attempt += 1
                logger.info(
                    f"Sending request to DeepSeek API with model: {self.model} (attempt {attempt}/{max_retries})"
                )

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=aiohttp.ClientTimeout(
                            total=300
                        ),  # Extended timeout for 3-Layer QC (5 minutes)
                    ) as response:
                        if response.status == 400:
                            error_detail = (
                                (await response.json())
                                .get("error", {})
                                .get("message", "Unknown error")
                            )
                            logger.error(f"Bad request to DeepSeek API: {error_detail}")
                            logger.error(f"Request data: {json.dumps(data, indent=2)}")
                            raise ValueError(
                                f"Bad request to DeepSeek API: {error_detail}"
                            )

                        if response.status >= 500 and attempt < max_retries:
                            # Server error, retry
                            logger.warning(
                                f"Server error from DeepSeek API: {response.status}. Retrying..."
                            )
                            await asyncio.sleep(2 * attempt)  # Exponential backoff
                            continue

                        response.raise_for_status()
                        result = await response.json()

                        if "choices" in result and len(result["choices"]) > 0:
                            content = result["choices"][0]["message"]["content"]
                            logger.info(
                                "Successfully received response from DeepSeek API"
                            )
                            return content
                        else:
                            error_msg = f"Unexpected API response format: {result}"
                            logger.error(error_msg)
                            raise ValueError(error_msg)

            except asyncio.TimeoutError:
                logger.error(
                    f"DeepSeek API request timed out (attempt {attempt}/{max_retries})"
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 * attempt)  # Exponential backoff
                    continue
                raise ValueError(
                    "DeepSeek API request timed out after multiple attempts"
                )

            except aiohttp.ClientError as e:
                logger.error(f"Error calling DeepSeek API: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 * attempt)  # Exponential backoff
                    continue
                raise

            except Exception as e:
                logger.error(f"Unexpected error in _call_api: {str(e)}")
                raise

    async def generate(self, prompt, max_tokens=1000, temperature=0.7, top_p=0.9, model=None):
        """
        Generate text using DeepSeek API
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            top_p: Top-p sampling parameter
            model: Override the default model (e.g., 'deepseek-reasoner' for better quality)
        """
        max_retries = 2
        attempt = 0
        
        # Use provided model or default
        use_model = model or self.model

        while attempt < max_retries:
            try:
                attempt += 1
                logger.info(
                    f"🤖 Sending request to DeepSeek API with model: {use_model} (attempt {attempt}/{max_retries})"
                )

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": use_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            "top_p": top_p,
                        },
                        timeout=aiohttp.ClientTimeout(
                            total=300
                        ),  # Extended timeout for 3-Layer QC (5 minutes)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if "choices" in result and len(result["choices"]) > 0:
                                return result["choices"][0]["message"]["content"]
                            else:
                                raise ValueError(
                                    "Unexpected response format from DeepSeek API"
                                )
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"DeepSeek API error ({response.status}): {error_text}"
                            )

                            # If it's a server error, retry
                            if response.status >= 500 and attempt < max_retries:
                                logger.info(
                                    f"Retrying due to server error ({response.status})"
                                )
                                await asyncio.sleep(2)  # Wait before retry
                                continue

                            raise Exception(
                                f"DeepSeek API error ({response.status}): {error_text}"
                            )

            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout calling DeepSeek API (attempt {attempt}/{max_retries})"
                )
                if attempt < max_retries:
                    await asyncio.sleep(2)  # Wait before retry
                    continue
                raise Exception(
                    "DeepSeek API request timed out after multiple attempts"
                )
            except aiohttp.ClientError as e:
                logger.error(f"Client error calling DeepSeek API: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                raise
            except Exception as e:
                logger.error(f"Error in generate: {str(e)}")
                raise

    async def generate_completion(self, prompt, max_tokens=2000, temperature=0.2, model=None):
        """
        Generate text completion using DeepSeek API.
        For text completion without JSON, use this method instead of generate_json.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            model: Override the default model (e.g., 'deepseek-reasoner' for better quality)
        """
        try:
            result = await self.generate(
                prompt=prompt, max_tokens=max_tokens, temperature=temperature, model=model
            )
            return result
        except Exception as e:
            logger.error(f"Error in generate_completion: {str(e)}")
            return None

    def generate_completion_sync(self, prompt, max_tokens=2000, temperature=0.2, model=None):
        """
        Synchronous version of generate_completion.
        For text completion without JSON, use this method in synchronous contexts.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            model: Override the default model (e.g., 'deepseek-reasoner' for better quality)
        """
        try:
            # Create a new event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the async generate method in the event loop
                result = loop.run_until_complete(
                    self.generate(
                        prompt=prompt, max_tokens=max_tokens, temperature=temperature, model=model
                    )
                )
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
                result = loop.run_until_complete(
                    self.generate(
                        prompt=prompt,
                        max_tokens=max_tokens or self.max_tokens,
                        temperature=temperature or self.temperature,
                    )
                )

                # Try to parse the result as JSON if it's not already
                try:
                    # If it's already valid JSON, return as is
                    json_result = json.loads(result)
                    return json_result
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    if "```json" in result:
                        json_content = (
                            result.split("```json")[1].split("```")[0].strip()
                        )
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
                            "raw_response": result[:500],  # Truncate for logging
                        }
            finally:
                # Always close the loop
                loop.close()

        except Exception as e:
            logger.error(f"Error in make_custom_request: {str(e)}")
            return {
                "error": str(e),
                "message": "Failed to process the request due to an internal error",
            }

    async def parse_cv(self, text, max_retries=2):
        """
        Parse CV text to extract structured information
        """
        logger.info(f"Parsing CV text ({len(text)} chars) with DeepSeek")
        start_time = time.time()

        cv_parsing_prompt = f"""
        Extract structured information from the following CV text. 
        Format the output as a valid JSON object with the following sections:
        
        - personal_info: Object containing name, email, phone, location, linkedin, github, portfolio, website, twitter, instagram, etc.
        - professional_summary: A concise summary of the candidate's background
        - skills: Array of objects with "name" and "level" (Beginner, Intermediate, Advanced, Expert)
        - experience: Array of work experiences, each with:
          * job_title: The specific job title
          * company: Company name
          * location: Work location
          * start_date: Start date
          * end_date: End date
          * description: Brief overview (1-2 sentences)
          * responsibilities: Array of achievement/responsibility bullet points (extract each achievement as a separate item)
        - education: Array of education entries with school, degree, field, start_date, end_date
        - certifications: Array of certifications with name, issuer, and date
        - languages: Array of language proficiencies with language name and level
        
        🚨 CRITICAL INSTRUCTIONS FOR CONTACT INFORMATION:
        - Extract ALL links and URLs from the CV, including:
          * LinkedIn profile (linkedin.com/in/username)
          * GitHub profile (github.com/username)
          * Portfolio websites (Pexels, Behance, Dribbble, ArtStation, personal sites, etc.)
          * Personal websites
          * Twitter/X handles (twitter.com/username or x.com/username)
          * Instagram profiles (instagram.com/username)
        - Store each type of link in its specific field (linkedin, github, portfolio, website, twitter, instagram)
        - Portfolio platforms like Pexels (pexels.com/@username) should go in the "portfolio" field
        - DO NOT skip any URLs you find in the CV
        
        🚨 CRITICAL INSTRUCTIONS FOR WORK EXPERIENCE - FOLLOW EXACTLY:
        - NEVER EVER use "Position", "Role", "Job" as job_title 
        - ALWAYS extract the EXACT job title before "|" or "at"
        - Examples you MUST follow:
          * "Compliance Manager | Furst Management Ltd" → job_title: "Compliance Manager", company: "Furst Management Ltd"
          * "Enterprise Risk Management (ERM) Analyst | Convex Insurance UK Limited" → job_title: "Enterprise Risk Management (ERM) Analyst", company: "Convex Insurance UK Limited"
          * "Senior Developer at Google Inc" → job_title: "Senior Developer", company: "Google Inc"
        - If you see "Manager", "Analyst", "Developer", "Engineer", etc. - use the FULL title
        - FORBIDDEN WORDS for job_title: "Position", "Role", "Job", "Employee", "Worker"
        - Extract job_title as the specific professional title, NOT generic terms
        
        🚨 CRITICAL INSTRUCTIONS FOR RESPONSIBILITIES/ACHIEVEMENTS:
        - Split work experience descriptions into individual bullet points
        - Each achievement/responsibility should be a separate item in the "responsibilities" array
        - Look for sentences that describe achievements, tasks, or results
        - Each item should be a complete, actionable statement
        - Example: If the CV says "Managed team of 10. Increased sales by 50%. Led 3 major projects."
          → responsibilities: ["Managed team of 10", "Increased sales by 50%", "Led 3 major projects"]
        - Extract ALL achievements and responsibilities as separate array items
        - Do NOT combine multiple achievements into one item
        
        🚨 CRITICAL INSTRUCTIONS FOR EDUCATION vs CERTIFICATIONS - FOLLOW EXACTLY:
        
        EDUCATION (Formal Academic Degrees):
        - Use ONLY for formal degrees from universities/colleges: Bachelor's, Master's, PhD, Associate's, Diploma in higher education
        - Must have a school/university name and a recognized degree type
        - Examples that go in EDUCATION:
          * "BSc in Human Nutrition & Sports Science" from a university
          * "Bachelor of Business Administration" from XYZ University
          * "Master of Science in Computer Science" from ABC College
        
        CERTIFICATIONS (Professional Training, Bootcamps, Short Courses):
        - Use for ALL professional certifications, bootcamps, training courses, diplomas below degree level
        - Examples that go in CERTIFICATIONS (NOT EDUCATION):
          * "L3 Diploma in Software Development" - This is a professional certification
          * "Full-Stack Software Development Bootcamp" - This is a bootcamp/training
          * "Python for Data Science Certification" - This is a professional certification
          * "AWS Certified Solutions Architect" - This is a certification
          * "Google Analytics Certification" - This is a certification
          * "PMP Certification" - This is a certification
        
        KEY RULES:
        - If it says "Bootcamp", "Certification", "Certificate", "Training", "Course" → CERTIFICATIONS
        - If it's a "Diploma" or "L3/L4/L5 Diploma" without university context → CERTIFICATIONS
        - If it's from Code Institute, Coursera, Udemy, LinkedIn Learning, etc. → CERTIFICATIONS
        - Only use EDUCATION for traditional academic degrees (BSc, BA, MSc, MA, PhD, etc.) from universities
        
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

                    # 🚨 POST-PROCESS: Fix "Position at Company" format
                    parsed_data = self._fix_position_format(parsed_data)

                    logger.info(
                        f"Successfully parsed CV in {time.time() - start_time:.2f} seconds"
                    )
                    return parsed_data
                except json.JSONDecodeError:
                    # Try to extract JSON if surrounded by markdown code blocks or other text
                    if "```json" in response:
                        json_content = (
                            response.split("```json")[1].split("```")[0].strip()
                        )
                        parsed_data = json.loads(json_content)

                        # 🚨 POST-PROCESS: Fix "Position at Company" format
                        parsed_data = self._fix_position_format(parsed_data)

                        logger.info(
                            f"Successfully parsed CV JSON from markdown in {time.time() - start_time:.2f} seconds"
                        )
                        return parsed_data
                    elif "```" in response:
                        json_content = response.split("```")[1].split("```")[0].strip()
                        parsed_data = json.loads(json_content)

                        # 🚨 POST-PROCESS: Fix "Position at Company" format
                        parsed_data = self._fix_position_format(parsed_data)

                        logger.info(
                            f"Successfully parsed CV from code block in {time.time() - start_time:.2f} seconds"
                        )
                        return parsed_data
                    else:
                        raise ValueError(
                            "Could not extract valid JSON from DeepSeek response"
                        )

            except (ValueError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempts} failed: {last_error}. Retrying...")
                await asyncio.sleep(2)  # Short delay before retry

        # If we get here, all attempts failed
        logger.error(
            f"Failed to parse CV after {max_retries} attempts. Last error: {last_error}"
        )
        raise ValueError(f"Failed to parse CV data. Last error: {last_error}")

    def _fix_position_format(self, parsed_data):
        """
        Post-process parsed data to fix 'Position at Company' format that DeepSeek keeps returning
        """
        if not isinstance(parsed_data, dict) or "experience" not in parsed_data:
            return parsed_data

        if not isinstance(parsed_data["experience"], list):
            return parsed_data

        for exp in parsed_data["experience"]:
            if not isinstance(exp, dict):
                continue

            job_title = exp.get("job_title", "")
            if not isinstance(job_title, str):
                continue

            # Fix "Position at Company" format
            if job_title.startswith("Position at "):
                company_from_title = job_title.replace("Position at ", "").strip()

                # If company field is missing or generic, extract from title
                if not exp.get("company") or exp.get("company") in [
                    "Unknown Company",
                    "",
                ]:
                    exp["company"] = company_from_title

                # Set job title to a placeholder that transfer logic will handle
                exp["job_title"] = f"Professional at {company_from_title}"
                logger.info(
                    f"Fixed 'Position at' format: company='{company_from_title}', title='Professional'"
                )

        return parsed_data

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
                    sections = json.loads(
                        response.split("```json")[1].split("```")[0].strip()
                    )
                elif "```" in response:
                    sections = json.loads(
                        response.split("```")[1].split("```")[0].strip()
                    )
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
        Analyze the following parsed CV data and provide a detailed, SPECIFIC assessment like a professional CV reviewer would.
        
        🎯 CRITICAL INSTRUCTIONS - READ CAREFULLY:
        
        1. **BE SPECIFIC & REFERENCE ACTUAL CV CONTENT**
           - Use actual job titles, company names, skills, and achievements from the CV
           - Example GOOD: "Your role as Senior Developer at TechCorp shows strong leadership with 15+ team management"
           - Example BAD: "Contains work experience" ❌
        
        2. **MATCH ROLE SUGGESTIONS TO EXPERIENCE LEVEL** ⚠️ CRITICAL
           - Calculate total years of experience from work history dates
           - Suggest roles appropriate to that experience level:
             * 0-2 years → Entry-Level: Junior, Associate, Coordinator roles
             * 3-7 years → Mid-Level: Specialist, Manager, Team Lead, Supervisor roles
             * 8-15 years → Senior: Senior Manager, Director, Principal, Head of roles
             * 16+ years → Executive: VP, C-Level, Chief, Executive Director roles
           - Example: 22 years experience = "VP of Operations", "Director of Supply Chain"
           - NEVER suggest "Junior", "Trainee", "Supervisor", or "Specialist" for 16+ years
           - NEVER suggest "Coordinator" or "Assistant" for 8+ years experience
        
        3. **ANALYZE QUANTIFIABLE ACHIEVEMENTS**
           - Count how many achievements include numbers, percentages, or metrics
           - Identify which experiences have strong impact statements vs weak descriptions
           - Note specific achievements that stand out
        
        4. **CHECK FOR WORD REPETITION**
           - Identify words used 3+ times (excluding common words like "the", "and", "to")
           - Focus on action verbs and key skills
           - Suggest specific synonym replacements
        
        5. **EVALUATE ATS COMPATIBILITY**
           - Check for industry-standard keywords based on the roles shown
           - Identify missing technical terms for the candidate's field
           - Assess formatting for ATS parsing (headers, bullets, dates)
        
        Your response must be in this EXACT JSON format:
        
        {{
            "overall_score": <score from 1-10 based on overall quality>,
            
            "section_scores": {{
                "content_completeness": <1-10: Are all major sections present with sufficient detail?>,
                "format_structure": <1-10: Is formatting clean, consistent, and ATS-friendly?>,
                "skills_relevance": <1-10: Are skills relevant and well-demonstrated?>,
                "job_history": <1-10: Quality of experience descriptions and achievements>,
                "education": <1-10: Education section completeness and relevance>,
                "overall_impact": <1-10: Does CV make strong impression and tell compelling story?>
            }},
            
            "strengths": [
                "Example: 'Strong quantified achievement: [Actual achievement from CV with specific numbers]'",
                "Example: 'Demonstrated [specific skill] expertise through [specific project/role from CV]'",
                "Example: 'Clear career progression: [actual role 1] → [actual role 2] showing growth in [specific area]'",
                "Example: '[X]% of your experience bullets include quantifiable metrics - excellent for impact'",
                "Include 4-6 specific strengths referencing actual CV content"
            ],
            
            "weaknesses": [
                "Example: 'Your [specific role] at [company] lacks measurable outcomes - what results did you achieve?'",
                "Example: '[Skill] is listed but not demonstrated in any project or achievement'",
                "Example: 'Missing industry keywords: [specific missing keywords] for [their field/role]'",
                "Example: 'Repeated word: \"[word]\" used [X] times - consider varying with: [synonyms]'",
                "Include 2-4 specific issues found in the CV"
            ],
            
            "improvement_suggestions": [
                "Example: 'Add metrics to [specific role/project]: What was the ROI? Team size? Budget managed?'",
                "Example: 'Strengthen [specific achievement] by adding: timeframe, scope, technologies used'",
                "Example: 'Replace repeated \"[word]\" with alternatives: [specific synonyms] for variety'",
                "Example: 'Add [specific keyword/certification] to match [target role/industry] requirements'",
                "Include 4-6 actionable improvements with specific examples"
            ],
            
            "ats_analysis": {{
                "parse_rate": <percentage 0-100: estimated ATS parsing success>,
                "keyword_match": <percentage 0-100: keyword optimization for their field>,
                "format_score": <percentage 0-100: ATS-friendly formatting>,
                "missing_keywords": ["[specific keyword 1]", "[specific keyword 2]"],
                "repeated_words": [
                    {{"word": "[actual repeated word]", "count": <number>, "suggestions": ["synonym1", "synonym2"]}}
                ],
                "recommendations": [
                    "Specific ATS improvement based on actual CV structure"
                ]
            }},
            
            "quantifiable_achievements": {{
                "total_bullets": <count of all experience bullet points>,
                "quantified_bullets": <count with numbers/metrics>,
                "percentage": <quantified/total * 100>,
                "strong_examples": ["[actual achievement 1 with metrics]", "[actual achievement 2 with metrics]"],
                "needs_metrics": ["[actual bullet point that needs numbers]"]
            }},
            
            "experience_level": {{
                "years_experience": <calculate from actual work history dates>,
                "classification": "<Entry-Level (0-2) | Mid-Level (3-7) | Senior (8-15) | Executive (16+) based on years AND roles>",
                "career_trajectory": "<Describe actual progression shown in CV>"
            }},
            
            "skills_assessment": {{
                "technical_skills": [
                    {{"skill": "<actual skill from CV>", "proficiency_evidence": "<where it's demonstrated>", "level": <1-10>}}
                ],
                "soft_skills_demonstrated": [
                    {{"skill": "<inferred from achievements>", "evidence": "<specific achievement showing it>", "level": <1-10>}}
                ],
                "missing_skills": ["<industry-standard skills not present>"]
            }},
            
            "potential_roles": {{
                "best_matches": [
                    "<IMPORTANT: Suggest roles appropriate to experience level>",
                    "<Entry-Level (0-2 yrs): Junior/Associate/Coordinator roles>",
                    "<Mid-Level (3-7 yrs): Specialist/Manager/Supervisor roles>", 
                    "<Senior (8-15 yrs): Senior Manager/Lead/Director roles>",
                    "<Executive (16+ yrs): VP/Head of/C-Level/Executive Director roles>",
                    "<NEVER suggest Supervisor, Specialist, or Analyst for 16+ years>",
                    "<Example: 22 years = 'VP of Operations', 'Director of Supply Chain', NOT 'Supervisor'>"
                ],
                "match_reasons": ["Based on [specific experience/skill from CV]"],
                "suggested_industries": ["<based on actual work history>"],
                "skill_gaps": ["What skills to add for target roles"]
            }}
        }}
        
        📋 QUALITY CHECKLIST - Every item must be specific to THIS CV:
        ✅ Reference actual job titles, companies, and achievements
        ✅ Include real numbers and metrics from the CV
        ✅ Point to specific sections that need improvement
        ✅ Calculate actual percentages for quantified achievements
        ✅ Identify real repeated words with counts
        ✅ Suggest specific keywords for their industry
        ✅ Provide actionable improvements with examples
        
        ❌ NEVER say generic things like:
        - "Contains contact information" 
        - "Has work experience section"
        - "Includes education"
        - "Professional summary is present"
        
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
                    logger.info(
                        f"Successfully analyzed CV in {time.time() - start_time:.2f} seconds"
                    )
                    return analysis_data
                except json.JSONDecodeError:
                    # Try to extract JSON if surrounded by markdown code blocks or other text
                    if "```json" in response:
                        json_content = (
                            response.split("```json")[1].split("```")[0].strip()
                        )
                        analysis_data = json.loads(json_content)
                        logger.info(
                            f"Successfully analyzed CV from markdown in {time.time() - start_time:.2f} seconds"
                        )
                        return analysis_data
                    elif "```" in response:
                        json_content = response.split("```")[1].split("```")[0].strip()
                        analysis_data = json.loads(json_content)
                        logger.info(
                            f"Successfully analyzed CV from code block in {time.time() - start_time:.2f} seconds"
                        )
                        return analysis_data
                    else:
                        raise ValueError(
                            "Could not extract valid JSON from DeepSeek analysis response"
                        )

            except (ValueError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempts} failed: {last_error}. Retrying...")
                await asyncio.sleep(2)  # Short delay before retry

        # If we get here, all attempts failed
        logger.error(
            f"Failed to analyze CV after {max_retries} attempts. Last error: {last_error}"
        )
        raise ValueError(f"Failed to analyze CV data. Last error: {last_error}")

    async def improve_text(self, text, context=None, improvement_type="professional"):
        """
        Improve the provided text using the DeepSeek model.

        Args:
            text: The text to improve
            context: Additional context for the improvement
            improvement_type: Type of improvement to perform (professional, concise, etc.)

        Returns:
            Improved text
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for improvement")
            return text

        try:
            instruction = f"""Improve the following text to make it more {improvement_type}, 
            professional, clear, and impactful. Focus on enhancing the language while 
            preserving all key information and keeping the same overall structure.
            
            Original text:
            {text}
            
            Instructions:
            - Enhance professional language and clarity
            - Improve structure and readability
            - Highlight achievements and skills
            - Maintain all key information
            - Make action verbs and metrics more impactful
            """

            if context:
                instruction += f"\n\nAdditional context: {context}"

            response = await self._call_api(
                instruction, max_tokens=2000, temperature=0.2
            )

            try:
                # Try to parse as JSON first
                json_response = json.loads(response)
                if isinstance(json_response, dict) and "improved_text" in json_response:
                    return json_response["improved_text"]
                elif isinstance(json_response, dict) and "text" in json_response:
                    return json_response["text"]
            except (json.JSONDecodeError, TypeError):
                # Not a JSON response, use directly
                pass

            return response

        except Exception as e:
            logger.error(f"Error improving text with DeepSeek: {str(e)}")
            logger.error(traceback.format_exc())
            return text  # Return original text if improvement fails

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
                logger.error(
                    "DeepSeek API key is not configured. Please set the DEEPSEEK_API_KEY environment variable."
                )
                return {
                    "error": "DeepSeek API key is not configured",
                    "message": "Please contact the administrator to set up the API key.",
                    "parsed_data_fallback": {
                        "personal_info": {
                            "name": "Could not parse - API not configured",
                            "email": "",
                            "phone": "",
                            "location": "",
                        },
                        "professional_summary": "CV parsing requires API configuration. Please contact the administrator.",
                        "skills": [],
                        "experience": [],
                        "education": [],
                        "certifications": [],
                        "languages": [],
                    },
                }

            # Extract text from file if not provided
            if text is None:
                # Extract text based on file type
                text = ""
                try:
                    file_lower = file_path.lower()

                    if file_lower.endswith(".txt"):
                        # Plain text file
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            text = f.read()
                    elif file_lower.endswith(".pdf"):
                        # PDF file
                        try:
                            import PyPDF2

                            with open(file_path, "rb") as f:
                                pdf_reader = PyPDF2.PdfReader(f)
                                for page_num in range(len(pdf_reader.pages)):
                                    text += (
                                        pdf_reader.pages[page_num].extract_text() + "\n"
                                    )
                        except ImportError:
                            logger.error(
                                "PyPDF2 not installed. Please install it with pip install PyPDF2"
                            )
                            raise ValueError(
                                "PyPDF2 is required for PDF extraction but not installed"
                            )
                    elif file_lower.endswith(".docx"):
                        # DOCX file
                        try:
                            import docx

                            doc = docx.Document(file_path)
                            text = "\n".join([para.text for para in doc.paragraphs])
                        except ImportError:
                            logger.error(
                                "python-docx not installed. Please install it with pip install python-docx"
                            )
                            raise ValueError(
                                "python-docx is required for DOCX extraction but not installed"
                            )
                    elif file_lower.endswith(".doc"):
                        # Legacy DOC file - requires textract
                        try:
                            import textract

                            text = textract.process(file_path).decode("utf-8")
                        except ImportError:
                            logger.error(
                                "textract not installed. Please install it with pip install textract"
                            )
                            raise ValueError(
                                "textract is required for DOC extraction but not installed"
                            )
                    else:
                        raise ValueError(f"Unsupported file type: {file_path}")

                    logger.info(
                        f"Successfully extracted {len(text)} characters of text from {file_path}"
                    )
                except Exception as e:
                    logger.error(f"Error extracting text from file: {str(e)}")
                    raise ValueError(f"Failed to extract text from document: {str(e)}")

            # Check if we have text to parse
            if not text or len(text.strip()) < 10:
                logger.error(f"Extracted text is too short or empty: '{text}'")
                return {
                    "error": "Extracted text is too short or empty",
                    "message": "Could not extract meaningful text from the document",
                }

            # Create a new event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the async parse_cv method in the event loop
                result = loop.run_until_complete(self.parse_cv(text))
                logger.info(
                    f"Document parsing completed in {time.time() - start_time:.2f} seconds"
                )
                return result
            except Exception as e:
                logger.error(f"Error during async CV parsing: {str(e)}")
                # Return a structured fallback response
                return {
                    "error": f"Error during CV parsing: {str(e)}",
                    "message": "Failed to parse CV data with AI service",
                    "extracted_text": (
                        text[:500] + "..." if len(text) > 500 else text
                    ),  # Include truncated text for debugging
                    "parsed_data_fallback": {
                        "personal_info": {
                            "name": "Parsing Error",
                            "email": "",
                            "phone": "",
                            "location": "",
                        },
                        "professional_summary": f"Error parsing CV: {str(e)}",
                        "skills": [],
                        "experience": [],
                        "education": [],
                        "certifications": [],
                        "languages": [],
                    },
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
                        "location": "",
                    },
                    "professional_summary": f"An error occurred while processing this CV: {str(e)}",
                    "skills": [],
                    "experience": [],
                    "education": [],
                    "certifications": [],
                    "languages": [],
                },
            }

    def _calculate_tenure_years(self, start_date: str, end_date: str) -> float:
        """Calculate years between two dates."""
        import re
        from datetime import datetime

        current_year = 2025

        try:
            # Handle "Present" or "Current" as end date
            if end_date and any(
                word in end_date.lower() for word in ["present", "current", "now"]
            ):
                end_date_str = str(current_year)
            else:
                end_date_str = end_date

            # Extract years from dates
            start_years = re.findall(r"\b(20\d{2}|19\d{2})\b", str(start_date))
            end_years = re.findall(r"\b(20\d{2}|19\d{2})\b", str(end_date_str))

            if start_years and end_years:
                start_year = int(start_years[0])
                end_year = int(end_years[-1])

                # Extract months if available for more precision
                months = {
                    "jan": 1,
                    "feb": 2,
                    "mar": 3,
                    "apr": 4,
                    "may": 5,
                    "jun": 6,
                    "jul": 7,
                    "aug": 8,
                    "sep": 9,
                    "oct": 10,
                    "nov": 11,
                    "dec": 12,
                    "january": 1,
                    "february": 2,
                    "march": 3,
                    "april": 4,
                    "june": 6,
                    "july": 7,
                    "august": 8,
                    "september": 9,
                    "october": 10,
                    "november": 11,
                    "december": 12,
                }

                start_month = 6  # Default to middle of year
                end_month = 6

                for month_name, month_num in months.items():
                    if month_name in str(start_date).lower():
                        start_month = month_num
                        break

                for month_name, month_num in months.items():
                    if month_name in str(end_date_str).lower():
                        end_month = month_num
                        break

                # Calculate years with month precision
                years_diff = end_year - start_year
                months_diff = end_month - start_month
                total_years = years_diff + (months_diff / 12.0)

                return max(0, round(total_years, 1))

            elif start_years:
                # Only start date available, assume till now
                start_year = int(start_years[0])
                return max(0, round(current_year - start_year, 1))

            return 0

        except Exception as e:
            logger.warning(
                f"Error calculating tenure from '{start_date}' to '{end_date}': {e}"
            )
            return 0

    def _calculate_average_tenure_and_gaps(self, experience: list) -> dict:
        """Calculate average tenure per role and count employment gaps."""
        if not experience:
            logger.warning("📊 No experience data provided for tenure calculation")
            return {
                "average_tenure": "0 years",
                "total_experience": "0 years",
                "employment_gaps": 0,
                "tenure_list": [],
            }

        tenures = []
        gap_count = 0

        logger.info(f"📊 Calculating tenure for {len(experience)} experience entries")

        for idx, exp in enumerate(experience):
            if isinstance(exp, dict):
                # Try both field formats: start_date/end_date AND dates
                start_date = exp.get("start_date", "")
                end_date = exp.get("end_date", "")
                dates = exp.get("dates", "")

                # Log all available fields for debugging
                logger.debug(
                    f"📊 Experience {idx + 1}: start_date='{start_date}', end_date='{end_date}', dates='{dates}'"
                )

                # Use dates field if start_date is empty
                if not start_date and dates:
                    logger.info(
                        f"📊 Using 'dates' field for experience {idx + 1}: '{dates}'"
                    )
                    # Split dates field (format: "2020 - 2023" or "2020 - Present")
                    date_parts = dates.split("-")
                    if len(date_parts) >= 2:
                        start_date = date_parts[0].strip()
                        end_date = date_parts[1].strip()
                        logger.info(
                            f"📊 Extracted: start='{start_date}', end='{end_date}'"
                        )

                if start_date and start_date.lower() not in ["n/a", "unknown", ""]:
                    years = self._calculate_tenure_years(start_date, end_date)
                    if years > 0:
                        tenures.append(years)
                        logger.debug(
                            f"📊 Calculated {years} years for experience {idx + 1}"
                        )
                    else:
                        logger.warning(
                            f"📊 Experience {idx + 1} calculated 0 years from '{start_date}' to '{end_date}'"
                        )
                else:
                    logger.warning(
                        f"📊 Experience {idx + 1} has invalid start_date: '{start_date}'"
                    )

        if not tenures:
            logger.warning(
                f"📊 No valid tenures calculated from {len(experience)} experiences"
            )
            return {
                "average_tenure": "Unable to calculate",
                "total_experience": "Unable to calculate",
                "employment_gaps": 0,
                "tenure_list": [],
            }

        # Calculate average tenure
        avg_tenure = sum(tenures) / len(tenures)
        total_experience = sum(tenures)

        # Detect gaps (simplified - roles with very short tenure might indicate gaps)
        gap_count = sum(1 for t in tenures if t < 0.5)

        logger.info(
            f"📊 Tenure calculation complete: {len(tenures)} valid roles, avg={avg_tenure:.1f}y, total={total_experience:.1f}y, gaps={gap_count}"
        )

        return {
            "average_tenure": f"{avg_tenure:.1f} years",
            "total_experience": f"{total_experience:.1f} years",
            "employment_gaps": gap_count,
            "tenure_list": [f"{t:.1f} years" for t in tenures],
        }

    async def analyze_career_trajectory(self, cv_data: dict) -> dict:
        """
        Analyze career consistency, role stability, and potential career changes.

        Args:
            cv_data: Parsed CV data containing experience, education, certifications

        Returns:
            Dictionary containing career trajectory analysis with scores and insights
        """
        try:
            # Check if API key is available
            if not self.api_key:
                logger.warning(
                    "DeepSeek API key not available, returning basic career analysis"
                )
                experience = cv_data.get("experience", [])
                tenure_stats = (
                    self._calculate_average_tenure_and_gaps(experience)
                    if experience
                    else {
                        "total_experience": "0 years",
                        "average_tenure": "N/A",
                        "employment_gaps": 0,
                    }
                )

                return {
                    "job_consistency": {
                        "score": 0,
                        "level": "Not Available",
                        "insights": ["AI analysis requires API configuration"],
                        "recommendations": ["Contact support to enable AI features"],
                    },
                    "role_stability": {
                        "score": 0,
                        "level": "Not Available",
                        "average_tenure": tenure_stats["average_tenure"],
                        "total_experience": tenure_stats["total_experience"],
                        "employment_gaps": tenure_stats["employment_gaps"],
                        "insights": ["AI analysis requires API configuration"],
                        "flags": [],
                    },
                    "career_change_potential": {
                        "assessment": "Not Available",
                        "confidence": "Low",
                        "indicators": ["AI analysis requires API configuration"],
                        "potential_directions": [],
                        "recommendations": [],
                    },
                }

            experience = cv_data.get("experience", [])
            education = cv_data.get("education", [])
            certifications = cv_data.get("certifications", [])
            skills = cv_data.get("skills", [])

            if not experience:
                return {
                    "job_consistency": {
                        "score": 0,
                        "level": "Insufficient Data",
                        "insights": ["No work experience provided for analysis"],
                        "recommendations": [],
                    },
                    "role_stability": {
                        "score": 0,
                        "level": "Insufficient Data",
                        "average_tenure": "0 years",
                        "employment_gaps": 0,
                        "insights": ["No work experience provided for analysis"],
                        "flags": [],
                    },
                    "career_change_potential": {
                        "assessment": "Unknown",
                        "confidence": "Low",
                        "indicators": [],
                        "potential_directions": [],
                        "recommendations": [],
                    },
                }

            # Calculate tenure statistics BEFORE sending to AI
            tenure_stats = self._calculate_average_tenure_and_gaps(experience)
            logger.info(f"📊 Calculated tenure statistics: {tenure_stats}")

            # Prepare data for AI analysis
            experience_summary = []
            for exp in experience:
                start_date = exp.get("start_date", "Unknown")
                end_date = exp.get("end_date", "Unknown")
                tenure = self._calculate_tenure_years(start_date, end_date)
                tenure_text = f" [{tenure:.1f} years]" if tenure > 0 else ""
                exp_text = f"- {exp.get('job_title', 'Unknown')} at {exp.get('company', 'Unknown')} ({start_date} - {end_date}){tenure_text}"
                experience_summary.append(exp_text)

            education_summary = []
            for edu in education:
                edu_text = f"- {edu.get('degree', 'Unknown')} in {edu.get('field', 'Unknown')} from {edu.get('school', 'Unknown')} ({edu.get('start_date', '')} - {edu.get('end_date', '')})"
                education_summary.append(edu_text)

            cert_summary = []
            for cert in certifications:
                cert_text = f"- {cert.get('name', 'Unknown')} from {cert.get('issuer', 'Unknown')} ({cert.get('date', 'Unknown')})"
                cert_summary.append(cert_text)

            # Handle skills - can be list of strings or list of dicts
            skills_list = []
            for s in skills[:20]:
                if isinstance(s, dict):
                    skills_list.append(s.get("name", str(s)))
                elif isinstance(s, str):
                    skills_list.append(s)
                else:
                    skills_list.append(str(s))
            skills_text = ", ".join(skills_list)

            prompt = f"""Analyze this candidate's career trajectory and provide insights on job consistency, role stability, and potential career changes.

WORK EXPERIENCE (with calculated tenure):
{chr(10).join(experience_summary)}

CALCULATED STATISTICS:
- Total Experience: {tenure_stats['total_experience']}
- Average Tenure per Role: {tenure_stats['average_tenure']}
- Number of Roles: {len(experience)}
- Employment Gaps/Short Stints: {tenure_stats['employment_gaps']}

EDUCATION:
{chr(10).join(education_summary) if education_summary else "Not provided"}

CERTIFICATIONS:
{chr(10).join(cert_summary) if cert_summary else "Not provided"}

SKILLS:
{skills_text}

IMPORTANT: Use the pre-calculated statistics above for role stability metrics. Do NOT recalculate tenure.

Provide a comprehensive career trajectory analysis in the following JSON format:

{{
  "job_consistency": {{
    "score": <number 1-10>,
    "level": "<High/Moderate/Low>",
    "insights": [
      "<specific observation about career path>",
      "<pattern in industry/role alignment>",
      "<skill continuity assessment>"
    ],
    "recommendations": [
      "<actionable suggestion for CV presentation>",
      "<advice for highlighting career progression>"
    ]
  }},
  "role_stability": {{
    "score": <number 1-10>,
    "level": "<Stable/Moderate/Unstable>",
    "average_tenure": "<calculated average time per role>",
    "employment_gaps": <number>,
    "insights": [
      "<observation about tenure lengths>",
      "<pattern in job changes>",
      "<assessment of commitment>"
    ],
    "flags": [
      "<potential concern if any, otherwise empty array>"
    ]
  }},
  "career_change_potential": {{
    "assessment": "<Active Career Change/Career Exploration/Career Growth/Career Stability>",
    "confidence": "<High/Medium/Low>",
    "indicators": [
      "<evidence of career pivot>",
      "<new skills or certifications>",
      "<educational shifts>"
    ],
    "potential_directions": [
      "<possible new career path based on skills/education>",
      "<related field opportunities>"
    ],
    "recommendations": [
      "<advice for career transition if applicable>",
      "<suggestions for skill development>",
      "<CV positioning recommendations>"
    ]
  }}
}}

ANALYSIS GUIDELINES:
1. Job Consistency Score (1-10):
   - 8-10: Clear progression in same field with aligned skills
   - 5-7: Related fields with transferable skills
   - 1-4: Multiple unrelated career changes

2. Role Stability Score (1-10):
   - 8-10: 2-5 years per role, minimal gaps
   - 5-7: 1-2 years per role, some gaps
   - 1-4: Less than 1 year per role, frequent gaps

3. Career Change Assessment:
   - Active Career Change: Recent certifications + new skills + education in different field
   - Career Exploration: Some new skills, exploratory certifications
   - Career Growth: New skills within same industry
   - Career Stability: Consistent skill development in current field

Return ONLY the JSON object, no additional text."""

            logger.info("🔍 Analyzing career trajectory with DeepSeek")

            response = await self.generate(
                prompt,
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for more consistent analysis
            )

            # Parse the JSON response
            try:
                # Clean the response - remove markdown code blocks if present
                cleaned_response = response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()

                analysis = json.loads(cleaned_response)

                # Override AI's average_tenure calculation with our accurate calculation
                if "role_stability" in analysis:
                    analysis["role_stability"]["average_tenure"] = tenure_stats[
                        "average_tenure"
                    ]
                    analysis["role_stability"]["employment_gaps"] = tenure_stats[
                        "employment_gaps"
                    ]
                    # Add total experience as additional info
                    analysis["role_stability"]["total_experience"] = tenure_stats[
                        "total_experience"
                    ]

                logger.info("✅ Career trajectory analysis completed successfully")
                logger.info(
                    f"📊 Final tenure data: avg={tenure_stats['average_tenure']}, total={tenure_stats['total_experience']}"
                )
                return analysis

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse career trajectory JSON: {str(e)}")
                logger.error(f"Response was: {response[:500]}")

                # Return a fallback structure with our calculated values
                return {
                    "job_consistency": {
                        "score": 5,
                        "level": "Moderate",
                        "insights": [
                            "Analysis completed but formatting issue occurred"
                        ],
                        "recommendations": ["Review your career progression manually"],
                    },
                    "role_stability": {
                        "score": 5,
                        "level": "Moderate",
                        "average_tenure": tenure_stats["average_tenure"],
                        "total_experience": tenure_stats["total_experience"],
                        "employment_gaps": tenure_stats["employment_gaps"],
                        "insights": ["Unable to fully analyze role stability"],
                        "flags": [],
                    },
                    "career_change_potential": {
                        "assessment": "Unknown",
                        "confidence": "Low",
                        "indicators": ["Analysis formatting issue"],
                        "potential_directions": [],
                        "recommendations": ["Manual review recommended"],
                    },
                }

        except Exception as e:
            logger.error(f"Error analyzing career trajectory: {str(e)}")
            logger.error(traceback.format_exc())

            # Try to calculate basic stats even on error
            experience = cv_data.get("experience", [])
            tenure_stats = (
                self._calculate_average_tenure_and_gaps(experience)
                if experience
                else {
                    "total_experience": "0 years",
                    "average_tenure": "N/A",
                    "employment_gaps": 0,
                }
            )

            return {
                "error": str(e),
                "job_consistency": {
                    "score": 0,
                    "level": "Error",
                    "insights": [f"Analysis failed: {str(e)}"],
                    "recommendations": ["Please contact support"],
                },
                "role_stability": {
                    "score": 0,
                    "level": "Error",
                    "average_tenure": tenure_stats["average_tenure"],
                    "total_experience": tenure_stats["total_experience"],
                    "employment_gaps": tenure_stats["employment_gaps"],
                    "insights": [f"Analysis failed: {str(e)}"],
                    "flags": [],
                },
                "career_change_potential": {
                    "assessment": "Error",
                    "confidence": "Low",
                    "indicators": [f"Analysis failed: {str(e)}"],
                    "potential_directions": [],
                    "recommendations": [],
                },
            }
