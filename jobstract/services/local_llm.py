import os
import logging
import traceback
import time
import uuid
from typing import Optional, Dict, Any

# External API imports with robust error handling
MISTRAL_AVAILABLE = False
GROQ_AVAILABLE = False

try:
    import mistralai.client
    MISTRAL_AVAILABLE = True
except ImportError:
    logging.warning("Mistral AI client not available")

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    logging.warning("Groq client not available")

logger = logging.getLogger(__name__)

# Configure a dedicated logger for LLM services
llm_logger = logging.getLogger('llm_service')
llm_logger.setLevel(logging.INFO)

# Create a file handler
try:
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, 'llm_service.log'))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    llm_logger.addHandler(file_handler)
except Exception as e:
    print(f"Could not set up file logging: {e}")

class LLMServiceMonitor:
    @staticmethod
    def log_api_call(
        provider: str, 
        prompt: str, 
        model: str, 
        success: bool, 
        duration: float = 0, 
        error: str = None,
        tokens_used: int = 0
    ) -> Dict[str, Any]:
        """
        Log detailed information about LLM API calls.
        
        Args:
            provider (str): Name of the LLM provider (Mistral/Groq)
            prompt (str): Input prompt
            model (str): Model used
            success (bool): Whether the API call was successful
            duration (float): API call duration in seconds
            error (str, optional): Error message if call failed
            tokens_used (int, optional): Number of tokens used
        
        Returns:
            Dict containing log metadata
        """
        log_entry = {
            'request_id': str(uuid.uuid4()),
            'provider': provider,
            'model': model,
            'timestamp': time.time(),
            'prompt_length': len(prompt),
            'success': success,
            'duration_ms': int(duration * 1000),
            'tokens_used': tokens_used,
            'error': error
        }
        
        log_message = (
            f"LLM API Call: "
            f"provider={log_entry['provider']} "
            f"model={log_entry['model']} "
            f"request_id={log_entry['request_id']} "
            f"prompt_length={log_entry['prompt_length']} "
            f"success={log_entry['success']} "
            f"duration_ms={log_entry['duration_ms']} "
            f"tokens_used={log_entry['tokens_used']}"
        )
        
        if success:
            llm_logger.info(log_message)
        else:
            llm_logger.error(log_message + f" error={error}")
        
        return log_entry

class LLMService:
    def __init__(self):
        self.mistral_api_key = os.getenv('MISTRAL_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.model = self._initialize_model()

    def _initialize_model(self):
        """Initialize the appropriate LLM for production."""
        try:
            # Prioritize Mistral in production
            if MISTRAL_AVAILABLE and self.mistral_api_key:
                llm_logger.info("Using Mistral AI for text generation")
                return mistralai.client.MistralClient(api_key=self.mistral_api_key)
            
            # Fallback to Groq
            if GROQ_AVAILABLE and self.groq_api_key:
                llm_logger.info("Using Groq for text generation")
                return groq.Groq(api_key=self.groq_api_key)
            
            raise ValueError("No LLM service available. Please check your API keys and installed packages.")
        
        except Exception as e:
            llm_logger.error(f"LLM initialization error: {e}")
            llm_logger.debug(traceback.format_exc())
            return None

    def generate_text(self, prompt: str, max_tokens: int = 150) -> str:
        """Generate text using the initialized model."""
        if not self.model:
            llm_logger.error("No model initialized for text generation")
            return "Unable to generate improved summary. No LLM service available."

        start_time = time.time()
        try:
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
                
                # Log Mistral API call
                LLMServiceMonitor.log_api_call(
                    provider='Mistral',
                    prompt=prompt,
                    model='mistral-small',
                    success=True,
                    duration=time.time() - start_time,
                    tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0
                )
                
                return response.choices[0].message.content.strip()
            
            # Groq
            if hasattr(self.model, 'chat') and hasattr(self.model.chat, 'completions'):
                response = self.model.chat.completions.create(
                    model="llama2-70b-4096",
                    messages=[
                        {"role": "system", "content": "You are a professional CV summary improver."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens
                )
                
                # Log Groq API call
                LLMServiceMonitor.log_api_call(
                    provider='Groq',
                    prompt=prompt,
                    model='llama2-70b-4096',
                    success=True,
                    duration=time.time() - start_time,
                    tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0
                )
                
                return response.choices[0].message.content.strip()
            
            raise ValueError("No text generation method available")
        
        except Exception as e:
            # Log API call failure
            LLMServiceMonitor.log_api_call(
                provider='Mistral/Groq',
                prompt=prompt,
                model='unknown',
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            
            llm_logger.error(f"Text generation error: {e}")
            llm_logger.debug(traceback.format_exc())
            return "Unable to generate improved summary. Please try again later."

def improve_summary(summary: str) -> str:
    """Improve CV summary using the appropriate LLM service."""
    llm_service = LLMService()
    
    if not llm_service.model:
        llm_logger.warning("No LLM model available. Returning original summary.")
        return summary
    
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
