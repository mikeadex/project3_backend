"""
Professional Job Keywords Configuration
Target high-quality professional positions across multiple categories
"""

# Primary professional job categories with targeted keywords
PROFESSIONAL_KEYWORDS = {
    "technology": [
        "software developer",
        "software engineer",
        "python developer",
        "javascript developer",
        "full stack developer",
        "frontend developer",
        "backend developer",
        "data scientist",
        "data analyst",
        "devops engineer",
        "cloud engineer",
        "machine learning",
        "cybersecurity",
        "IT support",
        "system administrator",
        "network engineer",
        "UX designer",
        "UI designer",
        "product manager",
        "scrum master",
    ],
    "finance": [
        "accountant",
        "financial analyst",
        "financial controller",
        "auditor",
        "tax advisor",
        "investment analyst",
        "risk analyst",
        "compliance officer",
        "credit analyst",
        "payroll specialist",
    ],
    "business": [
        "business analyst",
        "project manager",
        "operations manager",
        "account manager",
        "sales manager",
        "marketing manager",
        "HR manager",
        "office manager",
        "business development",
        "consultant",
    ],
    "healthcare": [
        "nurse",
        "pharmacist",
        "healthcare assistant",
        "medical secretary",
        "physiotherapist",
        "occupational therapist",
        "radiographer",
        "dental nurse",
    ],
    "engineering": [
        "mechanical engineer",
        "electrical engineer",
        "civil engineer",
        "design engineer",
        "quality engineer",
        "manufacturing engineer",
        "process engineer",
    ],
    "education": [
        "teacher",
        "lecturer",
        "teaching assistant",
        "tutor",
        "education coordinator",
    ],
    "legal": [
        "solicitor",
        "legal advisor",
        "paralegal",
        "legal secretary",
    ],
    "creative": [
        "graphic designer",
        "content writer",
        "copywriter",
        "video editor",
        "photographer",
    ],
}

# Combine all keywords for broad search
ALL_PROFESSIONAL_KEYWORDS = []
for category, keywords in PROFESSIONAL_KEYWORDS.items():
    ALL_PROFESSIONAL_KEYWORDS.extend(keywords)

# Job titles to EXCLUDE (manual/low-skill positions)
EXCLUDED_KEYWORDS = [
    "warehouse",
    "driver",
    "delivery driver",
    "picker",
    "packer",
    "cleaner",
    "kitchen assistant",
    "laundry",
    "porter",
    "security guard",
    "fork lift",
    "forklift",
    "hgv",
    "van driver",
    "courier",
]


def get_keywords_for_category(category):
    """Get keywords for a specific category"""
    return PROFESSIONAL_KEYWORDS.get(category, [])


def get_all_keywords():
    """Get all professional keywords combined"""
    return ALL_PROFESSIONAL_KEYWORDS


def should_exclude_job(title, description=""):
    """Check if job should be excluded based on keywords"""
    title_lower = title.lower()
    description_lower = description.lower()

    for excluded in EXCLUDED_KEYWORDS:
        if excluded in title_lower or excluded in description_lower:
            return True

    return False
