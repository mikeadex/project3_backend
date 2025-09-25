import sys
sys.path.append('.')

from cv_parser.parsers import AdvancedDocumentParser
import logging

# Set up minimal logging
logging.basicConfig(level=logging.INFO)

# Sample PDF text that was hanging
text = '''Michael Rodriguez
michael.rodriguez@email.com | +1-694-810-9664 | New York, NY
PROFESSIONAL SUMMARY
Mid-Level Data Scientist with 1 years of experience in tech industry. Proven track record of delivering
high-quality results and collaborating effectively with cross-functional teams.
PROFESSIONAL EXPERIENCE
Data Scientist | Dynamic LLC | 2023-02 - Present
(cid:127) Improved efficiency by 16%
(cid:127) Collaborated with 18 team members to achieve quality standards
Junior Data Scientist | Advanced Inc | 2023-02 - 2025-01
(cid:127) Improved productivity by 45%
(cid:127) Managed project timelines effectively
EDUCATION
Bachelor of Arts in Computer Science, Stanford University (2015)
SKILLS
JavaScript (cid:127) SQL (cid:127) Python (cid:127) Docker (cid:127) React (cid:127) Git
'''

print("=" * 60)
print("TESTING INDIVIDUAL EXTRACTION METHODS")
print("=" * 60)

try:
    parser = AdvancedDocumentParser()
    
    print("1. Testing extract_personal_info...")
    personal_info = parser.extract_personal_info(text)
    print(f"   ✓ Personal info: {len(personal_info)} fields")
    
    print("2. Testing extract_experience...")
    experiences = parser.extract_experience(text)
    print(f"   ✓ Experience: {len(experiences)} entries")
    
    print("3. Testing extract_skills...")
    skills = parser.extract_skills(text)
    print(f"   ✓ Skills: {len(skills)} skills")
    
    print("4. Testing extract_education...")
    education = parser.extract_education(text)
    print(f"   ✓ Education: {len(education)} entries")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
