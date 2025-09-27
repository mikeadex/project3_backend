"""
Test script for 3-Layer Quality Control System
============================================

This script tests the comprehensive quality control system to ensure
all layers are working correctly.
"""

import asyncio
import logging
from typing import Dict, Any
from django.contrib.auth.models import User
from quality_control import ThreeLayerQualityController
from ai_cv_parser.deepseek_service import DeepSeekService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockLLMService:
    """Mock LLM service for testing without API calls"""
    
    async def generate_content(self, prompt: str) -> str:
        """Generate mock content based on prompt type"""
        if "professional summary" in prompt.lower():
            return "Experienced software developer with 5+ years in full-stack development. Proven track record of delivering high-quality applications and leading cross-functional teams. Expertise in Python, Django, JavaScript, and modern web technologies."
        
        elif "experience" in prompt.lower() or "job" in prompt.lower():
            return """- Led development of scalable web applications serving 10,000+ users
- Improved application performance by 40% through code optimization
- Mentored junior developers and conducted code reviews
- Implemented CI/CD pipelines reducing deployment time by 60%"""
        
        elif "skills" in prompt.lower():
            return """Technical Skills:
• Python (Expert)
• Django (Advanced) 
• JavaScript (Advanced)
• React (Intermediate)
• SQL (Advanced)

Soft Skills:
• Leadership (Advanced)
• Communication (Expert)
• Problem Solving (Expert)"""
        
        elif "education" in prompt.lower():
            return "Relevant coursework in software engineering, algorithms, and database systems. Graduated magna cum laude with strong foundation in computer science principles."
        
        else:
            return "Enhanced professional content with industry-specific optimization and ATS-friendly formatting."

async def test_quality_control_system():
    """Test the complete 3-layer quality control system"""
    
    print("🚀 Starting 3-Layer Quality Control System Test")
    print("=" * 60)
    
    # Sample CV data for testing
    test_cv_data = {
        'professional_summary': 'I am a software developer with some experience.',
        'experience': [
            {
                'job_title': 'Developer',
                'company_name': 'Tech Company',
                'job_description': 'I worked on websites and fixed bugs.',
                'start_date': '2022-01-01',
                'end_date': '2024-01-01'
            }
        ],
        'skills': [
            {'skill_name': 'Python', 'skill_level': 'Intermediate'},
            {'skill_name': 'JavaScript', 'skill_level': 'Beginner'},
            {'skill_name': 'HTML', 'skill_level': 'Intermediate'}
        ],
        'education': [
            {
                'degree': 'BSc Computer Science',
                'school_name': 'University',
                'field_of_study': 'Computer Science'
            }
        ]
    }
    
    # Create mock user
    class MockUser:
        username = "test_user"
        id = 1
    
    user = MockUser()
    
    try:
        # Initialize quality controller with mock services
        mock_writer_llm = MockLLMService()
        mock_reviewer_llm = MockLLMService()
        quality_controller = ThreeLayerQualityController(
            writer_llm_service=mock_writer_llm,
            reviewer_llm_service=mock_reviewer_llm
        )
        
        print("✅ Quality Controller initialized successfully")
        
        # Test different industries
        industries = ['technology', 'business', 'healthcare']
        
        for industry in industries:
            print(f"\n🎯 Testing {industry.upper()} industry optimization")
            print("-" * 40)
            
            # Process CV through quality control
            result = await quality_controller.process_cv(test_cv_data, user, industry)
            
            # Display results
            print(f"📊 Status: {result['status']}")
            print(f"✅ Approved: {result['approved']}")
            print(f"🏆 Quality Score: {result['quality_score']:.2f}/5.0")
            
            # Show layer performance
            if 'quality_report' in result:
                report = result['quality_report']
                print(f"\n📈 Layer Performance:")
                
                for layer_result in report['layer_results']:
                    layer_name = layer_result['layer']
                    score = layer_result['score']
                    passed = layer_result['passed']
                    time_taken = layer_result['processing_time']
                    
                    status_icon = "✅" if passed else "⚠️"
                    print(f"  {status_icon} {layer_name}: {score:.2f}/5.0 ({time_taken:.3f}s)")
                
                print(f"\n📊 Final Metrics:")
                metrics = report['final_metrics']
                print(f"  📝 Content Score: {metrics['content_score']}/5")
                print(f"  🎯 Language Score: {metrics['language_score']}/5") 
                print(f"  📋 Structure Score: {metrics['structure_score']}/5")
                print(f"  🔍 ATS Score: {metrics['ats_score']}/5")
                print(f"  🏆 Overall Score: {metrics['overall_score']:.2f}/5")
                print(f"  ⭐ Standards Met: {metrics['standards_met']}")
                
                print(f"\n💡 Recommendations:")
                for i, rec in enumerate(report['recommendations'][:3], 1):
                    print(f"  {i}. {rec}")
                
                print(f"\n⏱️ Total Processing Time: {report['total_processing_time']:.2f}s")
            
            print(f"\n{'='*60}")
        
        print(f"\n🎉 All tests completed successfully!")
        
        # Test edge cases
        print(f"\n🧪 Testing Edge Cases")
        print("-" * 40)
        
        # Test with minimal data
        minimal_cv = {
            'professional_summary': 'Developer.',
            'experience': [],
            'skills': []
        }
        
        result = await quality_controller.process_cv(minimal_cv, user, 'technology')
        print(f"📊 Minimal CV - Approved: {result['approved']}, Score: {result['quality_score']:.2f}")
        
        # Test with excellent data
        excellent_cv = {
            'professional_summary': 'Senior Software Engineer with 8+ years of experience developing scalable web applications. Led teams of 5+ developers and delivered projects worth $2M+ in revenue. Expert in Python, Django, React, and cloud technologies.',
            'experience': [
                {
                    'job_title': 'Senior Software Engineer',
                    'company_name': 'Tech Innovations Inc.',
                    'job_description': 'Led development of microservices architecture serving 100,000+ users daily. Improved system performance by 60% and reduced deployment time by 80%. Mentored 5 junior developers and established coding standards.',
                    'start_date': '2020-01-01',
                    'end_date': '2024-01-01'
                }
            ],
            'skills': [
                {'skill_name': 'Python', 'skill_level': 'Expert'},
                {'skill_name': 'Django', 'skill_level': 'Expert'},
                {'skill_name': 'React', 'skill_level': 'Advanced'},
                {'skill_name': 'AWS', 'skill_level': 'Advanced'},
                {'skill_name': 'Docker', 'skill_level': 'Advanced'},
                {'skill_name': 'PostgreSQL', 'skill_level': 'Advanced'}
            ]
        }
        
        result = await quality_controller.process_cv(excellent_cv, user, 'technology')
        print(f"📊 Excellent CV - Approved: {result['approved']}, Score: {result['quality_score']:.2f}")
        
        print(f"\n✅ Edge case testing completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

def run_test():
    """Run the async test"""
    asyncio.run(test_quality_control_system())

if __name__ == "__main__":
    run_test()
