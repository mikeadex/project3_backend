import re

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
print("TESTING CURRENT PATTERNS")
print("=" * 60)

# Test experience section pattern
experience_section_pattern = r'(?:PROFESSIONAL\s+EXPERIENCE|EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT|PROFESSIONAL\s+EXPERIENCE|EMPLOYMENT\s+HISTORY|WORK\s+HISTORY)[\s\n]*(?:[-=]+\s*\n)?(.*?)(?=\n\s*(?:EDUCATION|SKILLS|QUALIFICATIONS|CERTIFICATIONS|LANGUAGES|REFERENCES|ADDITIONAL\s+INFORMATION|\Z))'

exp_match = re.search(experience_section_pattern, text, re.IGNORECASE | re.DOTALL)
if exp_match:
    print("✅ EXPERIENCE SECTION FOUND:")
    print(repr(exp_match.group(1)))
    print("Formatted:")
    print(exp_match.group(1))
else:
    print("❌ EXPERIENCE SECTION NOT FOUND")

print("\n" + "=" * 60)

# Test skills pattern with current approach
skills_text = "JavaScript (cid:127) SQL (cid:127) Python (cid:127) Docker (cid:127) React (cid:127) Git"
print("SKILLS TEXT:", repr(skills_text))

# Current comma pattern
comma_skills = skills_text.split(',')
print("Comma split:", comma_skills)

# Test (cid:127) pattern
unicode_skills = skills_text.split('(cid:127)')
print("Unicode (cid:127) split:", [s.strip() for s in unicode_skills])

