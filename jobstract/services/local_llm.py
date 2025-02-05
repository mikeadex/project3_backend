import os
import logging
import traceback
from typing import Optional

# Local imports
import socket

try:
    import llama_cpp
except ImportError:
    llama_cpp = None

# External API imports
import mistralai.client
import groq

logger = logging.getLogger(__name__)

def is_localhost():
    """Check if the code is running on localhost."""
    hostname = socket.gethostname()
    return hostname in ['localhost', '127.0.0.1'] or 'local' in hostname.lower()

class LLMService:
    def __init__(self):
        self.mistral_api_key = os.getenv('MISTRAL_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.model = self._initialize_model()

    def _initialize_model(self):
        """Initialize the appropriate LLM based on environment."""
        try:
            # Prioritize local Llama on localhost
            if is_localhost():
                model_path = '/opt/render/project/src/models/llama-2-7b-chat.gguf'
                if llama_cpp and os.path.exists(model_path):
                    logger.info("Initializing local Llama model")
                    return llama_cpp.Llama(
                        model_path=model_path,
                        n_ctx=2048,
                        n_batch=512,
                        n_gpu_layers=-1
                    )
                else:
                    logger.warning("Local Llama model not available")
            
            # Fallback to Mistral in production
            if self.mistral_api_key:
                logger.info("Using Mistral AI for text generation")
                return mistralai.client.MistralClient(api_key=self.mistral_api_key)
            
            # Secondary fallback to Groq
            if self.groq_api_key:
                logger.info("Using Groq for text generation")
                return groq.Groq(api_key=self.groq_api_key)
            
            raise ValueError("No LLM service available")
        
        except Exception as e:
            logger.error(f"LLM initialization error: {e}")
            logger.debug(traceback.format_exc())
            return None

    def generate_text(self, prompt: str, max_tokens: int = 150) -> str:
        """Generate text using the initialized model."""
        try:
            # Local Llama model
            if isinstance(self.model, llama_cpp.Llama):
                response = self.model(
                    prompt, 
                    max_tokens=max_tokens, 
                    stop=["\n"], 
                    echo=False
                )
                return response.get('choices', [{}])[0].get('text', '').strip()
            
            # Mistral AI
            if hasattr(self.model, 'chat'):
                response = self.model.chat(
                    model="mistral-small",
                    messages=[
                        {"role": "system", "content": "You are a professional CV summary improver."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content.strip()
            
            # Groq
            if hasattr(self.model, 'chat'):
                response = self.model.chat.completions.create(
                    model="llama2-70b-4096",
                    messages=[
                        {"role": "system", "content": "You are a professional CV summary improver."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content.strip()
            
            raise ValueError("No text generation method available")
        
        except Exception as e:
            logger.error(f"Text generation error: {e}")
            logger.debug(traceback.format_exc())
            return "Unable to generate improved summary. Please try again later."

def improve_summary(summary: str) -> str:
    """Improve CV summary using the appropriate LLM service."""
    llm_service = LLMService()
    
    if not llm_service.model:
        return summary  # Return original if no service available
    
    prompt = f"""
    Improve the following CV summary, making it more professional, concise, and impactful:

    Original Summary: {summary}

    Guidelines:
    - Highlight key achievements and skills
    - Use action verbs
    - Avoid generic statements
    - Keep it under 150 words
    - Focus on unique professional strengths

    Improved Summary:
    """
    
    return llm_service.generate_text(prompt).strip()
