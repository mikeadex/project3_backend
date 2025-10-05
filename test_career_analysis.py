"""
Test script for career trajectory analysis feature.
Run this to verify the integration works correctly.
"""

import asyncio
import json
from ai_cv_parser.deepseek_service import DeepSeekService


async def test_career_analysis():
    """Test career trajectory analysis with sample CV data."""

    # Sample parsed CV data (similar to what parser returns)
    sample_cv_data = {
        "personal_info": {
            "name": "John Smith",
            "email": "john.smith@email.com",
            "phone": "+1234567890",
            "location": "New York, NY",
        },
        "professional_summary": "Experienced software engineer with 8 years in web development",
        "skills": [
            {"name": "Python", "category": "Technical"},
            {"name": "JavaScript", "category": "Technical"},
            {"name": "React", "category": "Technical"},
            {"name": "Django", "category": "Technical"},
            {"name": "Team Leadership", "category": "Soft Skills"},
        ],
        "experience": [
            {
                "job_title": "Senior Software Engineer",
                "company": "Tech Corp",
                "start_date": "2020-01",
                "end_date": "Present",
                "description": "Lead development team of 5 engineers",
            },
            {
                "job_title": "Software Engineer",
                "company": "StartupXYZ",
                "start_date": "2017-06",
                "end_date": "2019-12",
                "description": "Full-stack web development",
            },
            {
                "job_title": "Junior Developer",
                "company": "Web Solutions Inc",
                "start_date": "2015-03",
                "end_date": "2017-05",
                "description": "Frontend development and bug fixes",
            },
        ],
        "education": [
            {
                "degree": "Bachelor of Science",
                "field": "Computer Science",
                "school": "State University",
                "start_date": "2011",
                "end_date": "2015",
            }
        ],
        "certifications": [
            {
                "name": "AWS Certified Developer",
                "issuer": "Amazon Web Services",
                "date": "2019-08",
            }
        ],
    }

    print("🚀 Testing Career Trajectory Analysis")
    print("=" * 60)

    try:
        # Initialize DeepSeek service
        service = DeepSeekService()
        print("✅ DeepSeek service initialized")

        # Analyze career trajectory
        print("\n🔍 Analyzing career trajectory...")
        analysis = await service.analyze_career_trajectory(sample_cv_data)

        print("\n📊 Analysis Results:")
        print("=" * 60)
        print(json.dumps(analysis, indent=2))

        # Validate structure
        print("\n🔍 Validating response structure...")
        required_keys = ["job_consistency", "role_stability", "career_change_potential"]

        for key in required_keys:
            if key in analysis:
                print(f"✅ {key}: Present")
                if key == "job_consistency":
                    print(f"   - Score: {analysis[key].get('score', 'N/A')}")
                    print(f"   - Level: {analysis[key].get('level', 'N/A')}")
                elif key == "role_stability":
                    print(f"   - Score: {analysis[key].get('score', 'N/A')}")
                    print(
                        f"   - Average Tenure: {analysis[key].get('average_tenure', 'N/A')}"
                    )
                elif key == "career_change_potential":
                    print(f"   - Assessment: {analysis[key].get('assessment', 'N/A')}")
                    print(f"   - Confidence: {analysis[key].get('confidence', 'N/A')}")
            else:
                print(f"❌ {key}: Missing")

        print("\n✅ Career trajectory analysis test completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def test_empty_experience():
    """Test with empty experience data."""
    print("\n\n🚀 Testing with Empty Experience")
    print("=" * 60)

    empty_cv_data = {
        "personal_info": {"name": "Jane Doe"},
        "experience": [],
        "education": [],
        "certifications": [],
        "skills": [],
    }

    try:
        service = DeepSeekService()
        analysis = await service.analyze_career_trajectory(empty_cv_data)

        print("\n📊 Analysis Results (Empty Data):")
        print(json.dumps(analysis, indent=2))

        if analysis["job_consistency"]["level"] == "Insufficient Data":
            print("\n✅ Correctly handled empty experience data")
            return True
        else:
            print("\n⚠️ Expected 'Insufficient Data' response")
            return False

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("Career Trajectory Analysis - Integration Test")
    print("=" * 60)

    # Run tests
    loop = asyncio.get_event_loop()

    result1 = loop.run_until_complete(test_career_analysis())
    result2 = loop.run_until_complete(test_empty_experience())

    print("\n" + "=" * 60)
    if result1 and result2:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
