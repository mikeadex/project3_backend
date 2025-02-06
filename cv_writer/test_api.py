import os
import sys
import requests
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class LocalLLMTester:
    def __init__(self, config: Optional[Dict[str, str]] = None):
        """
        Initialize LLM API tester with configurable endpoints
        
        :param config: Dictionary containing API configurations
        """
        # Prioritize passed config, then environment variables, then default
        self.config = {
            'mistral_url': 'https://api.mistral.ai/v1/chat/completions',
            'groq_url': 'https://api.groq.com/openai/v1/chat/completions',
            'mistral_api_key': os.getenv('MISTRAL_API_KEY'),
            'groq_api_key': os.getenv('GROQ_API_KEY'),
            'groq_model': 'llama3-8b-8192'  # Updated to a valid Groq model
        }
        
        # Override with passed config if provided
        if config:
            self.config.update(config)
        
        # Validate API keys
        self._validate_config()
    
    def _validate_config(self):
        """
        Validate presence of API keys and endpoints
        """
        missing_configs = [
            key for key in ['mistral_api_key', 'groq_api_key'] 
            if not self.config.get(key)
        ]
        
        if missing_configs:
            error_msg = f"Missing configuration for: {', '.join(missing_configs)}"
            logger.error(error_msg)
            
            # Provide helpful debugging information
            logger.info("Environment Variables:")
            for key in os.environ:
                if 'API_KEY' in key:
                    logger.info(f"{key}: {'*' * 8 if os.environ[key] else 'EMPTY'}")
            
            raise ValueError(error_msg)
    
    def test_mistral_api(self, prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Test Mistral API with comprehensive logging and error handling
        
        :param prompt: Input text prompt
        :param max_tokens: Maximum tokens to generate
        :return: API response details
        """
        logger.info("🔍 Testing Mistral API...")
        
        try:
            response = requests.post(
                self.config['mistral_url'],
                headers={
                    'Authorization': f'Bearer {self.config["mistral_api_key"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'mistral-medium',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info("✅ Mistral API Test Successful!")
            logger.info(f"Response Tokens: {len(result['choices'][0]['message']['content'].split())}")
            
            return {
                'status': 'success',
                'model': 'mistral-medium',
                'response': result['choices'][0]['message']['content']
            }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Mistral API Error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def test_groq_api(self, prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Test Groq API with comprehensive logging and error handling
        
        :param prompt: Input text prompt
        :param max_tokens: Maximum tokens to generate
        :return: API response details
        """
        logger.info("🔍 Testing Groq API...")
        
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.config["groq_api_key"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.config['groq_model'],  # Use the configured model
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens
                },
                timeout=30
            )
            
            # Parse the response JSON
            response_data = response.json()
            
            if response.status_code != 200:
                logger.error(f"Groq API Error: {response.status_code}")
                logger.error(f"Response Content: {response_data}")
                return {
                    'status': 'error',
                    'message': response_data.get('error', {}).get('message', 'Unknown error'),
                    'details': response_data
                }
            
            logger.info("✅ Groq API Test Successful!")
            response_content = response_data['choices'][0]['message']['content']
            logger.info(f"Response Tokens: {len(response_content.split())}")
            
            return {
                'status': 'success',
                'model': self.config['groq_model'],
                'response': response_content
            }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Groq API Error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"❌ Unexpected Groq API Error: {e}")
            return {
                'status': 'error',
                'message': f'Unexpected error: {e}'
            }
    
    def validate_groq_api_key(self) -> Dict[str, Any]:
        """
        Validate Groq API key by making a simple test request
        
        :return: Validation result dictionary
        """
        logger.info("🔍 Validating Groq API Key...")
        
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.config["groq_api_key"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.config['groq_model'],  # Use the configured model
                    'messages': [{'role': 'user', 'content': 'Hello, can you validate my API key?'}],
                    'max_tokens': 50
                },
                timeout=10
            )
            
            # Parse the response JSON
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info("✅ Groq API Key is valid!")
                return {'status': 'success', 'message': 'API key is valid'}
            else:
                logger.error(f"❌ Groq API Key validation failed: {response.status_code}")
                logger.error(f"Response Content: {response_data}")
                return {
                    'status': 'error', 
                    'message': response_data.get('error', {}).get('message', 'Unknown error'),
                    'details': response_data
                }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Groq API Key Validation Error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"❌ Unexpected Groq API Validation Error: {e}")
            return {
                'status': 'error',
                'message': f'Unexpected error: {e}'
            }

    def list_groq_models(self) -> Dict[str, Any]:
        """
        List available Groq models
        
        :return: Dictionary with model listing results
        """
        logger.info("🔍 Listing Available Groq Models...")
        
        try:
            response = requests.get(
                'https://api.groq.com/openai/v1/models',
                headers={
                    'Authorization': f'Bearer {self.config["groq_api_key"]}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            # Parse the response JSON
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info("✅ Successfully retrieved Groq models!")
                
                # Extract and format model names
                models = [model['id'] for model in response_data.get('data', [])]
                
                return {
                    'status': 'success', 
                    'models': models,
                    'total_models': len(models)
                }
            else:
                logger.error(f"❌ Groq Model Listing failed: {response.status_code}")
                logger.error(f"Response Content: {response_data}")
                return {
                    'status': 'error', 
                    'message': response_data.get('error', {}).get('message', 'Unknown error'),
                    'details': response_data
                }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Groq Model Listing Error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"❌ Unexpected Groq Model Listing Error: {e}")
            return {
                'status': 'error',
                'message': f'Unexpected error: {e}'
            }

    def run_comprehensive_test(self):
        """
        Run comprehensive tests for both Mistral and Groq APIs
        """
        test_prompts = [
            "Write a professional summary for a software engineer with 5 years of experience.",
            "Improve this job description: Senior Python Developer responsible for backend development.",
            "Categorize and rate the following skills: Python, Django, Machine Learning, Communication"
        ]
        
        results = {}
        
        for i, prompt in enumerate(test_prompts, 1):
            logger.info(f"\n🧪 Test Scenario {i}: {prompt}")
            
            # Test Mistral
            mistral_result = self.test_mistral_api(prompt)
            results[f'mistral_test_{i}'] = mistral_result
            
            # Test Groq
            groq_result = self.test_groq_api(prompt)
            results[f'groq_test_{i}'] = groq_result
        
        return results

def main():
    """
    Main execution for API testing
    """
    try:
        # Debug: Print out environment variables
        print("Environment Variables:")
        print(f"GROQ_API_KEY: {'*' * 8 if os.getenv('GROQ_API_KEY') else 'NOT SET'}")
        print(f"MISTRAL_API_KEY: {'*' * 8 if os.getenv('MISTRAL_API_KEY') else 'NOT SET'}")
        
        tester = LocalLLMTester()
        
        # List available Groq models first
        groq_models = tester.list_groq_models()
        if groq_models['status'] == 'success':
            print("\nAvailable Groq Models:")
            for model in groq_models['models']:
                print(f"- {model}")
        else:
            print(f"Failed to list Groq models: {groq_models.get('message', 'Unknown error')}")
        
        # Validate Groq API Key
        groq_validation = tester.validate_groq_api_key()
        if groq_validation['status'] != 'success':
            logger.error("Groq API Key validation failed. Skipping comprehensive tests.")
            print(f"Groq API Validation: {groq_validation['message']}")
            print(f"Groq API Validation Details: {groq_validation.get('details', 'No additional details')}")
            sys.exit(1)
        
        comprehensive_results = tester.run_comprehensive_test()
        
        # Print detailed results
        for test_name, result in comprehensive_results.items():
            print(f"\n{test_name.upper()} Results:")
            print(f"Status: {result.get('status', 'Unknown')}")
            if result.get('status') == 'success':
                print(f"Model: {result.get('model', 'N/A')}")
                print(f"Response Preview: {result.get('response', 'N/A')[:200]}...")
            else:
                print(f"Error: {result.get('message', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback
        sys.exit(1)

if __name__ == '__main__':
    main()
