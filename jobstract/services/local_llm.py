import os
import logging
import traceback
from typing import Optional

try:
    import llama_cpp
except ImportError:
    llama_cpp = None

import openai  # Fallback to OpenAI if local model fails

logger = logging.getLogger(__name__)

class LocalLLMService:
    def __init__(self, 
                 model_path: str = '/opt/render/project/src/models/llama-2-7b-chat.gguf',
                 openai_api_key: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        self._initialize_model()

    def _initialize_model(self):
        try:
            if llama_cpp and os.path.exists(self.model_path):
                self.model = llama_cpp.Llama(
                    model_path=self.model_path,
                    n_ctx=2048,  # Context window size
                    n_batch=512,  # Batch size
                    n_gpu_layers=-1  # Use all GPU layers if available
                )
                logger.info(f"Local Llama model initialized from {self.model_path}")
            else:
                logger.warning("Local Llama model not available. Falling back to OpenAI.")
        except Exception as e:
            logger.error(f"Error initializing local model: {e}")
            logger.debug(traceback.format_exc())

    def generate_text(self, prompt: str, max_tokens: int = 150) -> str:
        try:
            # Try local model first
            if self.model:
                response = self.model(
                    prompt, 
                    max_tokens=max_tokens, 
                    stop=["\n"], 
                    echo=False
                )
                return response.get('choices', [{}])[0].get('text', '').strip()
            
            # Fallback to OpenAI
            if not self.openai_api_key:
                raise ValueError("No API key available for text generation")
            
            openai.api_key = self.openai_api_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that helps improve CV summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            logger.debug(traceback.format_exc())
            return "Unable to generate improved summary. Please try again later."

def improve_summary(summary: str) -> str:
    llm_service = LocalLLMService()
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
