import os
import sys
import django

# Setup Django environment
sys.path.append('/Users/michaeladeleye/Documents/Coding/ella/Ella-backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

from cv_writer.local_llm import ResilientLLMService

def test_resilient_llm_service():
    print("Testing ResilientLLMService...")
    
    # Test with force_init
    try:
        llm_service = ResilientLLMService(force_init=True)
        print("✅ Service initialized successfully with force_init")
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return
    
    # Test improve_text method
    try:
        test_sections = [
            ('professional_summary', 'Experienced software engineer with 5 years of experience'),
            ('experience', 'Worked on web development projects'),
            ('skills', 'Python, Django, React')
        ]
        
        for section, content in test_sections:
            print(f"\nTesting section: {section}")
            result = llm_service.improve_text(section, content)
            
            if result['status'] == 'success':
                print(f"✅ Successfully improved {section}")
                print(f"Provider: {result['provider']}")
                print(f"Model: {result['model']}")
                print(f"Original: {content}")
                print(f"Improved: {result['response']}")
            else:
                print(f"❌ Failed to improve {section}: {result.get('message', 'Unknown error')}")
    
    except Exception as e:
        print(f"❌ Error during text improvement: {e}")

if __name__ == '__main__':
    test_resilient_llm_service()
