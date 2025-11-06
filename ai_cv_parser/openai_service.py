import os
import json
import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger("ai_cv_parser")


class OpenAIService:
    """Service for interacting with OpenAI API (GPT-4, GPT-4-turbo, etc.)"""

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.api_url = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4-turbo-preview")  # or "gpt-4", "gpt-4o"
        self.max_tokens = 4000
        self.temperature = 0.7

        # Don't raise an error here, just log a warning
        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY environment variable is not set. OpenAI features will not work."
            )

        logger.info(f"✅ Initialized OpenAIService with model: {self.model}")

    async def generate(self, prompt: str, max_tokens: Optional[int] = None, 
                      temperature: Optional[float] = None, model: Optional[str] = None,
                      system_message: Optional[str] = None) -> Optional[str]:
        """
        Generate text using OpenAI API
        
        Args:
            prompt: The user prompt
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation (0-2)
            model: Override the default model (e.g., 'gpt-4', 'gpt-4-turbo-preview')
            system_message: Optional system message to guide the model
        
        Returns:
            Generated text or None if failed
        """
        if not self.api_key:
            logger.error("OpenAI API key not configured")
            return None

        use_model = model or self.model
        use_max_tokens = max_tokens or self.max_tokens
        use_temperature = temperature if temperature is not None else self.temperature

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": use_model,
            "messages": messages,
            "max_tokens": use_max_tokens,
            "temperature": use_temperature,
        }

        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                attempt += 1
                logger.info(
                    f"🤖 Sending request to OpenAI API with model: {use_model} (attempt {attempt}/{max_retries})"
                )

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if "choices" in result and len(result["choices"]) > 0:
                                content = result["choices"][0]["message"]["content"]
                                logger.info("✅ Successfully received response from OpenAI API")
                                return content.strip()
                            else:
                                logger.error("No choices in OpenAI response")
                                return None

                        elif response.status == 429:  # Rate limit
                            if attempt < max_retries:
                                wait_time = 2 ** attempt  # Exponential backoff
                                logger.warning(
                                    f"Rate limit hit, waiting {wait_time}s before retry..."
                                )
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.error("Max retries reached for rate limit")
                                return None

                        elif response.status >= 500:  # Server error
                            if attempt < max_retries:
                                logger.warning(
                                    f"Server error from OpenAI: {response.status}. Retrying..."
                                )
                                await asyncio.sleep(2 * attempt)
                                continue
                            else:
                                logger.error("Max retries reached for server error")
                                return None

                        else:
                            error_detail = await response.text()
                            logger.error(
                                f"OpenAI API error ({response.status}): {error_detail}"
                            )
                            return None

            except asyncio.TimeoutError:
                logger.error(f"Timeout on attempt {attempt}/{max_retries}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return None

            except Exception as e:
                logger.error(f"Error in OpenAI API call (attempt {attempt}): {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return None

        logger.error("All retries exhausted")
        return None

    def generate_sync(self, prompt: str, max_tokens: Optional[int] = None,
                     temperature: Optional[float] = None, model: Optional[str] = None,
                     system_message: Optional[str] = None) -> Optional[str]:
        """
        Synchronous version of generate() for use in non-async contexts
        
        Args:
            prompt: The user prompt
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            model: Override the default model
            system_message: Optional system message
        
        Returns:
            Generated text or None if failed
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self.generate(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        model=model,
                        system_message=system_message,
                    )
                )
                return result
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error in generate_sync: {str(e)}")
            return None

    def generate_completion_sync(self, prompt: str, max_tokens: Optional[int] = 1000,
                                 temperature: Optional[float] = 0.7, model: Optional[str] = None) -> Optional[str]:
        """
        Alias for generate_sync() to match the interface expected by quality control system
        
        Args:
            prompt: The user prompt
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            model: Override the default model
        
        Returns:
            Generated text or None if failed
        """
        return self.generate_sync(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
        )

    async def generate_with_json(self, prompt: str, max_tokens: Optional[int] = None,
                                 temperature: Optional[float] = None, 
                                 model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Generate JSON response using OpenAI API
        
        Args:
            prompt: The user prompt (should ask for JSON output)
            max_tokens: Maximum tokens for response
            temperature: Temperature for generation
            model: Override the default model
        
        Returns:
            Parsed JSON dict or None if failed
        """
        system_message = "You are a professional CV/resume assistant. Always respond with valid JSON."
        
        response_text = await self.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            system_message=system_message,
        )

        if not response_text:
            return None

        try:
            # Try to parse as JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON from markdown block")
                    return None
            else:
                logger.error("Response is not valid JSON")
                return None

