"""
Fallback AI service module for CV parsing and analysis.
This file provides a single, well-structured FallbackService implementation with:
- retries and configurable timeouts for provider calls
- a single async `generate` method and a sync `make_custom_request` wrapper
- clearer logging and safe handling of non-JSON responses
"""

import os
import json
import logging
import aiohttp
import asyncio

logger = logging.getLogger("ai_cv_parser")


class FallbackService:
    """Fallback AI service with simple LLaMA -> Mistral -> Groq chain and retries."""

    _working_model_cache = None

    def __init__(self):
        self.current_service = "mock"
        llama_api_key = os.environ.get("LLAMA_API_KEY") or os.environ.get("LLAMA_API")
        if llama_api_key:
            self.current_service = "llama"
            self.api_key = llama_api_key
            self.api_url = "https://api.llama-api.com/chat/completions"
            self.model = self._working_model_cache or "llama3.1-8b"
        elif os.environ.get("MISTRAL_API_KEY"):
            self.current_service = "mistral"
            self.api_key = os.environ.get("MISTRAL_API_KEY")
            self.api_url = "https://api.mistral.ai/v1/chat/completions"
            self.model = "mistral-small-latest"
        elif os.environ.get("GROQ_API_KEY"):
            self.current_service = "groq"
            self.api_key = os.environ.get("GROQ_API_KEY")
            self.api_url = "https://api.groq.com/openai/v1/chat/completions"
            self.model = "llama3-8b-8192"

        logger.info(f"Initialized FallbackService using {self.current_service} backend")

    async def _try_llama_models(self, prompt, max_tokens, temperature):
        retries = int(os.environ.get("AI_REQUEST_RETRIES", "2"))
        timeout_sec = int(os.environ.get("AI_REQUEST_TIMEOUT", "60"))

        if self._working_model_cache:
            models_to_try = [self._working_model_cache] + [
                m
                for m in [
                    "llama-3.1-8b-instruct",
                    "llama3-8b",
                    "llama3-8b-instruct",
                    "llama-3-8b-instruct",
                    "llama-3-8b",
                ]
                if m != self._working_model_cache
            ]
        else:
            models_to_try = [
                "llama-3.1-8b-instruct",
                "llama3-8b",
                "llama3-8b-instruct",
                "llama-3-8b-instruct",
                "llama-3-8b",
            ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for model in models_to_try:
            self.model = model
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            for attempt in range(1, retries + 1):
                try:
                    logger.info(
                        f"LLaMA request attempt {attempt}/{retries} for model {model}"
                    )
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.api_url,
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=timeout_sec),
                        ) as resp:
                            text = await resp.text()
                            if resp.status == 200:
                                try:
                                    data = json.loads(text)
                                    content = None
                                    if "choices" in data and data["choices"]:
                                        content = data["choices"][0]["message"].get(
                                            "content"
                                        )
                                    elif isinstance(data, dict) and "content" in data:
                                        content = data.get("content")
                                    else:
                                        content = text

                                    self.__class__._working_model_cache = model
                                    logger.info(f"Cached working LLaMA model: {model}")
                                    return content
                                except Exception:
                                    logger.info(
                                        "LLaMA returned non-JSON; returning raw text for repair"
                                    )
                                    self.__class__._working_model_cache = model
                                    return text
                            elif resp.status == 404:
                                logger.warning(f"LLaMA model not found: {model}")
                                break
                            else:
                                logger.error(f"LLaMA API error {resp.status}: {text}")

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout calling model {model} (attempt {attempt})")
                    if attempt < retries:
                        await asyncio.sleep(1)
                        continue
                    else:
                        break
                except Exception as e:
                    logger.error(f"Error on LLaMA model {model} attempt {attempt}: {e}")
                    if attempt < retries:
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        break

        logger.error("All LLaMA models exhausted")
        return {"error": "All LLaMA models failed"}

    async def generate(self, prompt, max_tokens=3000, temperature=0.1):
        logger.info(f"FallbackService.generate using {self.current_service}")

        if self.current_service == "mock":
            return self._get_mock_response()

        # Try LLaMA first if configured
        try:
            if self.current_service == "llama":
                res = await self._try_llama_models(prompt, max_tokens, temperature)
                if not (isinstance(res, dict) and "error" in res):
                    return res

            # Try other providers (Mistral / Groq)
            if self.current_service in ["mistral", "groq"] or True:
                # If current_service isn't mistral/groq but LLaMA failed, these blocks will check env keys
                if os.environ.get("MISTRAL_API_KEY"):
                    self.current_service = "mistral"
                    self.api_key = os.environ.get("MISTRAL_API_KEY")
                    self.api_url = "https://api.mistral.ai/v1/chat/completions"
                    self.model = self.model or "mistral-small-latest"
                elif os.environ.get("GROQ_API_KEY"):
                    self.current_service = "groq"
                    self.api_key = os.environ.get("GROQ_API_KEY")
                    self.api_url = "https://api.groq.com/openai/v1/chat/completions"
                    self.model = self.model or "llama3-8b-8192"

                if self.current_service in ["mistral", "groq"]:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    }
                    payload = {
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    }

                    timeout_sec = int(os.environ.get("AI_REQUEST_TIMEOUT", "60"))
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.api_url,
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=timeout_sec),
                        ) as resp:
                            text = await resp.text()
                            if resp.status == 200:
                                try:
                                    data = json.loads(text)
                                    if "choices" in data and data["choices"]:
                                        return data["choices"][0]["message"].get(
                                            "content"
                                        )
                                    return text
                                except Exception:
                                    return text
                            else:
                                logger.error(
                                    f"Provider {self.current_service} error: {text}"
                                )

        except Exception as e:
            logger.error(f"FallbackService.generate encountered error: {e}")

        logger.info("Falling back to mock response")
        return self._get_mock_response()

    def make_custom_request(self, prompt: str, max_tokens: int = 3000) -> str:
        """Synchronous wrapper used by the rest of the codebase."""
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.generate(prompt, max_tokens))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in make_custom_request sync wrapper: {e}")
            return self._get_mock_response()

    def _get_mock_response(self):
        return json.dumps(
            {
                "overall_score": 7,
                "strengths": [
                    "Clear professional experience section",
                    "Well-structured education information",
                    "Good use of action verbs in job descriptions",
                ],
                "weaknesses": [
                    "Skills section could be more comprehensive",
                    "Missing quantifiable achievements",
                    "Professional summary could be more tailored",
                ],
                "improvement_suggestions": [
                    "Add more technical skills relevant to target roles",
                    "Include metrics and achievements to quantify impact",
                    "Strengthen professional summary to highlight key qualifications",
                ],
                "section_scores": {
                    "content_completeness": 6,
                    "format_structure": 8,
                    "skills_relevance": 5,
                    "job_history": 7,
                    "education": 8,
                    "overall_impact": 6,
                },
                "ats_readiness": {
                    "score": 7,
                    "issues": [
                        "Some skills may not match common ATS keywords",
                        "Job titles could be more standardized",
                    ],
                    "suggestions": [
                        "Use industry-standard job titles",
                        "Incorporate more keywords from target job descriptions",
                    ],
                },
                "experience_level": {
                    "classification": "mid-level",
                    "years_experience": 5,
                },
            }
        )
