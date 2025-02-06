# Resilient LLM Service

## Overview
The `ResilientLLMService` provides a robust, multi-provider text improvement service for CV generation.

## Features
- Multiple LLM provider support
- Automatic provider and model fallback
- Configurable retry mechanisms
- Detailed logging

## Configuration

### Environment Variables
- `MISTRAL_API_KEY`: Mistral API key
- `GROQ_API_KEY`: Groq API key

### Usage Example
```python
from cv_writer.local_llm import ResilientLLMService

# Initialize the service
llm_service = ResilientLLMService()

# Improve a professional summary
result = llm_service.improve_text(
    section='professional_summary', 
    content='Experienced software developer...'
)

# Check the result
if result['status'] == 'success':
    improved_text = result['response']
    print(f"Provider: {result['provider']}")
    print(f"Model: {result['model']}")
    print(f"Improved Text: {improved_text}")
else:
    print(f"Error: {result['message']}")
```

## Supported Sections
- `professional_summary`
- `experience`
- `skills`

## Providers
1. Mistral (Primary)
2. Groq (Fallback)
   - Models: 
     * `llama3-8b-8192`
     * `llama3-70b-8192`
     * `mixtral-8x7b-32768`

## Customization
You can pass a custom configuration when initializing:

```python
custom_config = {
    'providers': {
        'mistral': {'model': 'custom-model'},
        'groq': {'models': ['custom-model-1', 'custom-model-2']}
    },
    'max_retries': 5,
    'timeout': 45
}
llm_service = ResilientLLMService(config=custom_config)
```

## Troubleshooting
- Ensure API keys are set in environment variables
- Check network connectivity
- Verify API endpoint URLs
