import os
import sys
import json
from pathlib import Path

# Add backend dir to path so ai_cv_parser package can be imported
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from ai_cv_parser.fallback_service import FallbackService


def make_prompt(cv_data):
    return f"""
            Analyze this CV and provide feedback in JSON format. Be concise but thorough.
            
            CV Data:
            {json.dumps(cv_data, indent=2)[:4000]}
            
            Return JSON with this exact structure. Do not add any text outside the JSON block:
            {{
                "overall_score": {{
                    "score": "<score_value>",
                    "feedback": "<feedback_message>"
                }},
                "strengths": ["<strength1>", "<strength2>", "<strength3>"],
                "weaknesses": ["<weakness1>", "<weakness2>", "<weakness3>"],
                "improvement_suggestions": ["<suggestion1>", "<suggestion2>", "<suggestion3>"],
                "skills_assessment": {{
                    "hard_skills": [
                        {{"skill": "<skill_name>", "rating": "<rating_value>", "feedback": "<feedback_message>"}}
                    ],
                    "soft_skills": [
                        {{"skill": "<skill_name>", "rating": "<rating_value>", "feedback": "<feedback_message>"}}
                    ],
                    "missing_skills": ["<skill1>", "<skill2>"]
                }},
                "employment_gaps_analysis": {{
                    "has_gaps": "<boolean>",
                    "feedback": "<feedback_message>",
                    "suggestions": ["<suggestion1>", "<suggestion2>"]
                }},
                "section_scores": {{
                    "content_completeness": "<score_value>",
                    "format_structure": "<score_value>",
                    "skills_relevance": "<score_value>",
                    "job_history": "<score_value>",
                    "education": "<score_value>",
                    "overall_impact": "<score_value>"
                }},
                "ats_readiness": {{
                    "score": "<score_value>",
                    "issues": ["<issue1>", "<issue2>"],
                    "suggestions": ["<suggestion1>", "<suggestion2>"]
                }},
                "experience_level": {{
                    "classification": "<junior/mid-level/senior/executive>",
                    "years_experience": "<number>",
                    "career_stage": "<brief_description>"
                }},
                "potential_roles": ["<role1>", "<role2>", "<role3>", "<role4>", "<role5>"]
            }}
            """


def run_tests():
    service = FallbackService()

    samples = []

    # Short CV (minimal)
    samples.append(
        {
            "personal_info": {"name": "Alice Example"},
            "experience": [],
            "education": [],
            "skills": ["Customer Service", "Cash Handling"],
        }
    )

    # Medium CV
    samples.append(
        {
            "personal_info": {"name": "Bob Developer"},
            "experience": [
                {
                    "job_title": "Software Engineer",
                    "company": "Acme",
                    "start_date": "2018-01",
                    "end_date": "2022-06",
                    "description": "Worked on backend services",
                }
            ],
            "education": [
                {"institution": "State University", "degree": "BSc Computer Science"}
            ],
            "skills": [
                {"name": "Python", "level": "Advanced"},
                {"name": "Django", "level": "Advanced"},
            ],
        }
    )

    # Long CV
    samples.append(
        {
            "personal_info": {"name": "Carla Senior"},
            "experience": [
                {
                    "job_title": "Engineering Manager",
                    "company": "BigCorp",
                    "start_date": "2010-01",
                    "end_date": "2024-01",
                    "description": "Led teams, delivered projects",
                }
            ]
            * 8,
            "education": [
                {
                    "institution": "Top University",
                    "degree": "MSc Computer Science",
                    "start_date": "2005",
                    "end_date": "2007",
                }
            ],
            "skills": [
                {"name": "Leadership", "level": "Expert"},
                {"name": "Strategic Planning", "level": "Expert"},
                {"name": "Cloud Architecture", "level": "Advanced"},
            ],
        }
    )

    results = []
    for idx, cv in enumerate(samples, start=1):
        print(f"\n--- Test CV #{idx} ---")
        prompt = make_prompt(cv)
        resp = service.make_custom_request(prompt)
        print("Raw response (first 1000 chars):")
        print(str(resp)[:1000])

        # Save raw to /tmp for inspection
        log_path = f"/tmp/raw_ai_response_test_{idx}.log"
        with open(log_path, "w") as f:
            f.write(str(resp))
        print(f"Saved raw response to {log_path}")
        results.append((idx, resp))

    print("\nDone. Collected responses for all sample CVs.")


if __name__ == "__main__":
    run_tests()
