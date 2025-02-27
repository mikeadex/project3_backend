import sys
import os
import re

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from cv_parser.parsers import AdvancedDocumentParser
except ImportError:
    class AdvancedDocumentParser:
        def _extract_skills(self, text: str):
            # Fallback skills extraction without spaCy
            skill_keywords = {
                'technical': [
                    'python', 'java', 'javascript', 'react', 'django', 'sql', 
                    'machine learning', 'data analysis', 'git', 'aws', 'docker',
                    'tensorflow', 'keras', 'pandas', 'numpy', 'scikit-learn',
                    'cloud computing', 'blockchain', 'cybersecurity', 'linux',
                    'c++', 'ruby', 'php', 'swift', 'kotlin', 'scala', 'r',
                    'html', 'css', 'node.js', 'angular', 'vue.js', 'typescript'
                ],
                'soft': [
                    'communication', 'leadership', 'problem solving', 'teamwork', 
                    'critical thinking', 'adaptability', 'creativity', 
                    'emotional intelligence', 'conflict resolution', 'negotiation',
                    'presentation skills', 'time management', 'collaboration'
                ]
            }
            
            text = text.lower()
            skills = set()
            
            # Match predefined keywords
            for category, category_skills in skill_keywords.items():
                for skill in category_skills:
                    if skill in text:
                        skills.add(skill)
            
            # Simple regex-based skill extraction
            skill_patterns = [
                r'\b\w+\s*(?:programming|language|framework|library|tool)\b',
                r'\b(?:expertise|proficient)\s*in\s*(\w+(?:\s+\w+)*)',
                r'\b(?:skilled|experienced)\s*with\s*(\w+(?:\s+\w+)*)'
            ]
            
            for pattern in skill_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                skills.update(match.strip() for match in matches if match)
            
            # Clean and normalize skills
            skills = {
                skill.lower().strip() 
                for skill in skills 
                if len(skill) > 1  # Avoid single-character skills
            }
            
            return list(skills)

def test_skills_extraction():
    parser = AdvancedDocumentParser()
    
    # Test cases with different skill representation styles
    test_texts = [
        # 1. Standard skills list
        "Proficient in Python, JavaScript, and React. Strong communication skills.",
        
        # 2. Skills with context and variations
        "As an experienced software engineer, I have expertise in cloud computing, Docker, and AWS. My leadership and teamwork skills are key to my success.",
        
        # 3. Complex skill descriptions
        "Skilled with machine learning frameworks like TensorFlow and Keras. Experienced in data analysis using Pandas and NumPy. Excellent problem-solving abilities.",
        
        # 4. Technical and soft skills mix
        "Developed blockchain solutions using Solidity. Demonstrated strong client relations and strategic planning skills.",
        
        # 5. Challenging extraction scenario
        "Worked on cutting-edge Angular projects at Tech Innovations Inc. Collaborated with cross-functional teams to deliver high-impact solutions.",
        
        # 6. Single character test
        "c programming language expert with a focus on embedded systems",
        
        # 7. Skill variations and context
        "Proficient in node.js development. Experienced with Vue.js and TypeScript. Strong presentation and time management skills."
    ]
    
    print("Skills Extraction Demonstration\n" + "="*40)
    
    for i, text in enumerate(test_texts, 1):
        print(f"\nTest Case {i}: {text}")
        skills = parser._extract_skills(text)
        print("Extracted Skills:", skills)
        print("-" * 40)

if __name__ == "__main__":
    test_skills_extraction()
