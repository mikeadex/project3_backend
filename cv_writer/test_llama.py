from local_llm import LocalLLMService

def test_llama():
    try:
        # Initialize the service
        print("Initializing LocalLLMService...")
        llm_service = LocalLLMService()
        
        # Test professional summary improvement
        test_summary = """
        Software engineer with 5 years of experience in web development.
        Worked on various projects using Python and JavaScript.
        Good team player with problem-solving skills.
        """
        
        print("\nTesting professional summary improvement...")
        result = llm_service.improve_section('professional_summary', test_summary)
        print("\nOriginal summary:")
        print(result['original'])
        print("\nImproved summary:")
        print(result['improved'])
        
        # Test experience improvement
        test_experience = {
            'job_title': 'Senior Software Engineer',
            'job_description': 'Developed web applications using Django and React. Managed team of 3 developers.',
            'achievements': 'Improved application performance by 40%'
        }
        
        print("\nTesting experience improvement...")
        result = llm_service.improve_section('experience', test_experience)
        print("\nOriginal experience:")
        print(result['original'])
        print("\nImproved experience:")
        print(result['improved'])
        
        # Test skills improvement
        test_skills = {
            'name': 'Python, JavaScript, React, Django, SQL',
            'proficiency': 'Advanced'
        }
        
        print("\nTesting skills improvement...")
        result = llm_service.improve_section('skills', test_skills)
        print("\nOriginal skills:")
        print(result['original'])
        print("\nImproved skills:")
        print(result['improved'])
        
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    test_llama()
