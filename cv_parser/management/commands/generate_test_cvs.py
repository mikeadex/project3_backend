import os
import json
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO
import random

class Command(BaseCommand):
    help = 'Generate test CV files in various formats for testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='generated_test_cvs',
            help='Directory to save generated CVs'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of CVs to generate'
        )
        parser.add_argument(
            '--include-problematic',
            action='store_true',
            help='Include intentionally problematic CVs for testing'
        )
        
    def handle(self, *args, **options):
        self.output_dir = options['output_dir']
        self.count = options['count']
        self.include_problematic = options['include_problematic']
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.stdout.write(
            self.style.SUCCESS(f'Generating {self.count} test CVs in {self.output_dir}')
        )
        
        # Generate CVs
        self.generate_test_cvs()
        
        # Generate metadata file
        self.generate_metadata()
        
        self.stdout.write(
            self.style.SUCCESS(f'Generated {self.count} test CVs successfully!')
        )
        
    def generate_test_cvs(self):
        """Generate diverse test CVs"""
        
        # CV templates with different characteristics
        cv_templates = [
            # Tech CVs
            {
                'category': 'tech',
                'roles': ['Software Engineer', 'Data Scientist', 'DevOps Engineer', 'Full Stack Developer'],
                'skills': ['Python', 'JavaScript', 'React', 'AWS', 'Docker', 'SQL', 'Git'],
                'experience_levels': ['Junior', 'Mid-Level', 'Senior', 'Lead']
            },
            # Business CVs
            {
                'category': 'business',
                'roles': ['Project Manager', 'Business Analyst', 'Marketing Manager', 'Sales Director'],
                'skills': ['Project Management', 'Excel', 'PowerPoint', 'Salesforce', 'Analytics'],
                'experience_levels': ['Associate', 'Manager', 'Senior Manager', 'Director']
            },
            # Creative CVs
            {
                'category': 'creative',
                'roles': ['Graphic Designer', 'UX Designer', 'Content Writer', 'Marketing Specialist'],
                'skills': ['Adobe Creative Suite', 'Figma', 'Content Creation', 'Branding', 'Social Media'],
                'experience_levels': ['Junior', 'Mid-Level', 'Senior', 'Creative Director']
            },
            # Healthcare CVs
            {
                'category': 'healthcare',
                'roles': ['Nurse', 'Medical Assistant', 'Healthcare Administrator', 'Physical Therapist'],
                'skills': ['Patient Care', 'Medical Records', 'HIPAA Compliance', 'EMR Systems'],
                'experience_levels': ['New Graduate', 'Experienced', 'Charge Nurse', 'Manager']
            }
        ]
        
        generated_count = 0
        
        for i in range(self.count):
            # Select random template
            template = random.choice(cv_templates)
            
            # Generate CV data
            cv_data = self.generate_cv_data(template, i)
            
            # Generate in multiple formats
            if i % 3 == 0:
                # PDF format
                self.generate_pdf_cv(cv_data, f"{template['category']}_cv_{i:03d}.pdf")
            elif i % 3 == 1:
                # Word format (simulated as text for now)
                self.generate_text_cv(cv_data, f"{template['category']}_cv_{i:03d}.txt")
            else:
                # Another PDF with different formatting
                self.generate_simple_pdf_cv(cv_data, f"{template['category']}_cv_{i:03d}_simple.pdf")
                
            generated_count += 1
            
            if generated_count % 10 == 0:
                self.stdout.write(f"Generated {generated_count}/{self.count} CVs...")
                
        # Generate problematic CVs if requested
        if self.include_problematic:
            self.generate_problematic_cvs()
            
    def generate_cv_data(self, template, index):
        """Generate realistic CV data"""
        
        # Names database
        first_names = [
            'James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
            'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica',
            'Sarah', 'Ahmed', 'Priya', 'Carlos', 'Wei', 'Fatima', 'Olumide', 'Raj'
        ]
        
        last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
            'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
            'Chen', 'Patel', 'Kim', 'Singh', 'Ahmed', 'Hassan', 'Ali', 'Okafor', 'Sharma'
        ]
        
        # Generate personal info
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        
        personal_info = {
            'first_name': first_name,
            'last_name': last_name,
            'email': f"{first_name.lower()}.{last_name.lower()}@email.com",
            'phone': f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
            'location': random.choice(['New York, NY', 'San Francisco, CA', 'London, UK', 'Toronto, ON', 'Sydney, AU']),
            'linkedin': f"linkedin.com/in/{first_name.lower()}{last_name.lower()}"
        }
        
        # Generate professional summary
        role = random.choice(template['roles'])
        experience_level = random.choice(template['experience_levels'])
        years_exp = random.randint(1, 15)
        
        professional_summary = f"{experience_level} {role} with {years_exp} years of experience in {template['category']} industry. Proven track record of delivering high-quality results and collaborating effectively with cross-functional teams."
        
        # Generate experience
        experience = []
        num_jobs = random.randint(2, 5)
        
        for job_idx in range(num_jobs):
            company_suffixes = ['Corp', 'Inc', 'LLC', 'Technologies', 'Solutions', 'Systems', 'Group']
            company_prefixes = ['Alpha', 'Beta', 'Global', 'Advanced', 'Premier', 'Elite', 'Dynamic', 'Innovative']
            
            company = f"{random.choice(company_prefixes)} {random.choice(company_suffixes)}"
            
            start_date = datetime.now() - timedelta(days=random.randint(365*job_idx, 365*(job_idx+3)))
            end_date = datetime.now() - timedelta(days=random.randint(0, 365*job_idx)) if job_idx > 0 else datetime.now()
            
            # Generate job responsibilities
            responsibilities = [
                f"Led development of {random.choice(['software solutions', 'marketing campaigns', 'process improvements', 'strategic initiatives'])}",
                f"Collaborated with {random.randint(5, 20)} team members to achieve {random.choice(['project goals', 'business objectives', 'quality standards'])}",
                f"Improved {random.choice(['efficiency', 'productivity', 'customer satisfaction', 'revenue'])} by {random.randint(10, 50)}%",
                f"Managed {random.choice(['client relationships', 'project timelines', 'team performance', 'budget allocation'])} effectively"
            ]
            
            experience.append({
                'company': company,
                'title': role if job_idx == 0 else f"{random.choice(['Junior', 'Associate', 'Senior'])} {role}",
                'start_date': start_date.strftime('%Y-%m'),
                'end_date': end_date.strftime('%Y-%m') if job_idx > 0 else 'Present',
                'responsibilities': random.sample(responsibilities, random.randint(2, 4))
            })
            
        # Generate education
        universities = [
            'University of California', 'Harvard University', 'MIT', 'Stanford University',
            'University of Toronto', 'Oxford University', 'State University', 'Community College'
        ]
        
        degrees = ['Bachelor of Science', 'Master of Science', 'Bachelor of Arts', 'Master of Business Administration']
        
        education = [{
            'institution': random.choice(universities),
            'degree': random.choice(degrees),
            'major': template['category'].title() if template['category'] != 'tech' else 'Computer Science',
            'graduation_year': random.randint(2010, 2023)
        }]
        
        # Generate skills
        skills = random.sample(template['skills'], random.randint(3, len(template['skills'])))
        
        return {
            'personal_info': personal_info,
            'professional_summary': professional_summary,
            'experience': experience,
            'education': education,
            'skills': skills,
            'template_category': template['category']
        }
        
    def generate_pdf_cv(self, cv_data, filename):
        """Generate a well-formatted PDF CV"""
        filepath = os.path.join(self.output_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Header
        personal = cv_data['personal_info']
        header_text = f"{personal['first_name']} {personal['last_name']}"
        story.append(Paragraph(header_text, styles['Title']))
        
        contact_info = f"{personal['email']} | {personal['phone']} | {personal['location']}"
        story.append(Paragraph(contact_info, styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Professional Summary
        story.append(Paragraph("PROFESSIONAL SUMMARY", styles['Heading2']))
        story.append(Paragraph(cv_data['professional_summary'], styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Experience
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", styles['Heading2']))
        for exp in cv_data['experience']:
            exp_header = f"{exp['title']} | {exp['company']} | {exp['start_date']} - {exp['end_date']}"
            story.append(Paragraph(exp_header, styles['Heading3']))
            
            for resp in exp['responsibilities']:
                story.append(Paragraph(f"• {resp}", styles['Normal']))
            story.append(Spacer(1, 6))
            
        # Education
        story.append(Paragraph("EDUCATION", styles['Heading2']))
        for edu in cv_data['education']:
            edu_text = f"{edu['degree']} in {edu['major']}, {edu['institution']} ({edu['graduation_year']})"
            story.append(Paragraph(edu_text, styles['Normal']))
            
        # Skills
        story.append(Spacer(1, 12))
        story.append(Paragraph("SKILLS", styles['Heading2']))
        skills_text = " • ".join(cv_data['skills'])
        story.append(Paragraph(skills_text, styles['Normal']))
        
        doc.build(story)
        
    def generate_simple_pdf_cv(self, cv_data, filename):
        """Generate a simple PDF CV using canvas (different format)"""
        filepath = os.path.join(self.output_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        
        y_position = height - 50
        
        # Header
        personal = cv_data['personal_info']
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y_position, f"{personal['first_name']} {personal['last_name']}")
        y_position -= 20
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y_position, f"{personal['email']} | {personal['phone']} | {personal['location']}")
        y_position -= 30
        
        # Professional Summary
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y_position, "PROFESSIONAL SUMMARY")
        y_position -= 15
        
        c.setFont("Helvetica", 10)
        # Wrap text
        summary_lines = self.wrap_text(cv_data['professional_summary'], 70)
        for line in summary_lines:
            c.drawString(50, y_position, line)
            y_position -= 12
            
        y_position -= 10
        
        # Experience (simplified)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y_position, "EXPERIENCE")
        y_position -= 15
        
        for exp in cv_data['experience'][:2]:  # Limit to 2 jobs for space
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y_position, f"{exp['title']} - {exp['company']}")
            y_position -= 12
            
            c.setFont("Helvetica", 9)
            c.drawString(50, y_position, f"{exp['start_date']} to {exp['end_date']}")
            y_position -= 15
            
            if y_position < 100:  # Check if we're running out of space
                break
                
        c.save()
        
    def generate_text_cv(self, cv_data, filename):
        """Generate a plain text CV"""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            personal = cv_data['personal_info']
            
            # Header
            f.write(f"{personal['first_name']} {personal['last_name']}\n")
            f.write(f"{personal['email']} | {personal['phone']} | {personal['location']}\n")
            f.write(f"LinkedIn: {personal['linkedin']}\n\n")
            
            # Professional Summary
            f.write("PROFESSIONAL SUMMARY\n")
            f.write("-" * 20 + "\n")
            f.write(f"{cv_data['professional_summary']}\n\n")
            
            # Experience
            f.write("PROFESSIONAL EXPERIENCE\n")
            f.write("-" * 23 + "\n")
            for exp in cv_data['experience']:
                f.write(f"{exp['title']} | {exp['company']}\n")
                f.write(f"{exp['start_date']} - {exp['end_date']}\n")
                for resp in exp['responsibilities']:
                    f.write(f"• {resp}\n")
                f.write("\n")
                
            # Education
            f.write("EDUCATION\n")
            f.write("-" * 9 + "\n")
            for edu in cv_data['education']:
                f.write(f"{edu['degree']} in {edu['major']}\n")
                f.write(f"{edu['institution']} ({edu['graduation_year']})\n\n")
                
            # Skills
            f.write("SKILLS\n")
            f.write("-" * 6 + "\n")
            f.write(" • ".join(cv_data['skills']) + "\n")
            
    def generate_problematic_cvs(self):
        """Generate intentionally problematic CVs for testing edge cases"""
        problematic_cases = [
            # Very large file
            {'type': 'large_file', 'description': 'CV with excessive content'},
            # Minimal content
            {'type': 'minimal', 'description': 'CV with very little content'},
            # Special characters
            {'type': 'special_chars', 'description': 'CV with special characters and unicode'},
            # Poor formatting
            {'type': 'poor_format', 'description': 'CV with inconsistent formatting'},
            # Missing sections
            {'type': 'incomplete', 'description': 'CV missing key sections'}
        ]
        
        for case in problematic_cases:
            if case['type'] == 'large_file':
                self.generate_large_cv(f"problematic_large_{case['type']}.txt")
            elif case['type'] == 'minimal':
                self.generate_minimal_cv(f"problematic_minimal_{case['type']}.txt")
            elif case['type'] == 'special_chars':
                self.generate_special_chars_cv(f"problematic_chars_{case['type']}.txt")
            elif case['type'] == 'poor_format':
                self.generate_poor_format_cv(f"problematic_format_{case['type']}.txt")
            elif case['type'] == 'incomplete':
                self.generate_incomplete_cv(f"problematic_incomplete_{case['type']}.txt")
                
    def generate_large_cv(self, filename):
        """Generate an unusually large CV"""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write("JOHN DOE - SENIOR SOFTWARE ENGINEER\n")
            f.write("john.doe@email.com | 555-123-4567\n\n")
            
            # Generate excessive content
            f.write("PROFESSIONAL SUMMARY\n")
            for i in range(50):  # 50 paragraphs of summary
                f.write(f"Paragraph {i+1}: " + "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 20 + "\n")
                
            f.write("\nEXPERIENE (DETAILED)\n")
            for i in range(20):  # 20 jobs
                f.write(f"Job {i+1}: Software Engineer at Company {i+1}\n")
                for j in range(100):  # 100 responsibilities per job
                    f.write(f"• Responsibility {j+1}: " + "Detailed description. " * 10 + "\n")
                    
    def generate_minimal_cv(self, filename):
        """Generate a minimal CV"""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write("Jane Smith\n")
            f.write("jane@email.com\n")
            f.write("Engineer\n")
            
    def generate_special_chars_cv(self, filename):
        """Generate CV with special characters"""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("Àlex Müller-Pérez 王伟\n")
            f.write("alex.müller@email.com | +1-555-123-4567\n")
            f.write("São Paulo, Brasil 🇧🇷\n\n")
            
            f.write("RÉSUMÉ PROFESSIONNEL\n")
            f.write("Ingénieur logiciel avec 5+ années d'expérience...\n\n")
            
            f.write("EXPÉRIENCE PROFESSIONNELLE\n")
            f.write("• Développement d'applications web 💻\n")
            f.write("• Collaboration avec équipes internationales 🌍\n")
            f.write("• Amélioration de la performance de 25% 📈\n")
            
    def generate_poor_format_cv(self, filename):
        """Generate poorly formatted CV"""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write("bob    johnson\n")
            f.write("email:bob@email.com phone:555-123-4567 location:somewhere\n")
            f.write("SUMMARY:experienced developer\n")
            f.write("experience:\n")
            f.write("companyABC developer 2020-2023 did stuff\n")
            f.write("companyXYZ developer 2018-2020 did more stuff\n")
            f.write("education:university degree computer science\n")
            f.write("skills:python,java,sql,etc\n")
            
    def generate_incomplete_cv(self, filename):
        """Generate incomplete CV missing key sections"""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write("Sarah Wilson\n")
            f.write("sarah.wilson@email.com\n\n")
            
            f.write("SKILLS\n")
            f.write("• Python\n")
            f.write("• JavaScript\n")
            f.write("• SQL\n")
            # Missing experience, education, summary
            
    def wrap_text(self, text, width):
        """Simple text wrapping function"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
                
        if current_line:
            lines.append(' '.join(current_line))
            
        return lines
        
    def generate_metadata(self):
        """Generate metadata file describing the test CVs"""
        metadata = {
            'generation_info': {
                'timestamp': datetime.now().isoformat(),
                'total_cvs_generated': self.count,
                'include_problematic': self.include_problematic
            },
            'categories': [
                'tech', 'business', 'creative', 'healthcare'
            ],
            'formats': [
                'PDF (formatted)', 'PDF (simple)', 'Text'
            ],
            'test_scenarios': [
                'Standard CVs with good formatting',
                'CVs with different experience levels',
                'CVs from different industries',
                'CVs with varying amounts of content'
            ]
        }
        
        if self.include_problematic:
            metadata['problematic_cases'] = [
                'Large file (excessive content)',
                'Minimal content',
                'Special characters and unicode',
                'Poor formatting',
                'Incomplete (missing sections)'
            ]
            
        metadata_file = os.path.join(self.output_dir, 'test_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
