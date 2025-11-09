"""
Email Template Preview Script
Run this to preview the email templates in your browser
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")
django.setup()

from django.template.loader import render_to_string

# Sample data for preview
context = {
    "name": "Michael",
    "verification_link": "https://ellacv.com/cv-analysis/verify/sample-token-12345/",
    "ats_score": "87",
    "expires_hours": 24,
    "frontend_url": "https://ellacv.com",
}

# Render the template
html_content = render_to_string("emails/cv_verification_email.html", context)

# Save to preview file
preview_path = BASE_DIR / "email_preview.html"
with open(preview_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"✅ Email preview generated!")
print(f"📧 Open this file in your browser to preview:")
print(f"   {preview_path}")
print("\nPreview data used:")
print(f"   Name: {context['name']}")
print(f"   ATS Score: {context['ats_score']}")
print(f"   Link: {context['verification_link']}")
print("\n💡 Tip: Test dark mode by enabling it in your browser/OS")
