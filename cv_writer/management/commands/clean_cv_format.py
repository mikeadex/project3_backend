from django.core.management.base import BaseCommand
from cv_writer.models import CvWriter, Experience, ProfessionalSummary, Skill
import re
from datetime import datetime

class Command(BaseCommand):
    help = 'Clean up CV formatting by removing markdown and improving structure'

    def format_date(self, date_str):
        """Format date strings consistently."""
        if not date_str or date_str.lower() == 'n/a' or date_str.lower() == 'present':
            return date_str
        try:
            # Try to parse the date string
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            # Format as Month Year
            return date_obj.strftime('%B %Y')
        except:
            return date_str

    def format_experience(self, text):
        """Format experience descriptions with proper bullet points and structure."""
        if not text:
            return text

        # Split into lines and process each one
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        formatted_lines = []
        
        for line in lines:
            # Remove markdown and bullet points
            line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
            line = re.sub(r'^\s*[-•*]\s*', '', line)
            
            # Split long lines at periods that are followed by a space
            sentences = re.split(r'(?<=\.) (?=[A-Z])', line)
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                    
                # Clean up the sentence
                sentence = sentence.strip()
                # Ensure first letter is capitalized
                if sentence and not sentence[0].isupper():
                    sentence = sentence[0].upper() + sentence[1:]
                # Add bullet point if it's not just a period
                if sentence != '.':
                    formatted_lines.append(f"• {sentence}")
        
        # Join lines with proper spacing
        return '\n'.join(formatted_lines)

    def format_job_title(self, title):
        """Format job title with proper capitalization."""
        if not title:
            return title
            
        # Remove any markdown
        title = re.sub(r'\*\*(.*?)\*\*', r'\1', title)
        
        # Capitalize words except articles, conjunctions, and prepositions
        lower_words = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to', 'for', 'with', 'in'}
        words = title.split()
        
        # Always capitalize first and last word
        for i, word in enumerate(words):
            if i == 0 or i == len(words) - 1 or word.lower() not in lower_words:
                words[i] = word.capitalize()
            else:
                words[i] = word.lower()
                
        return ' '.join(words)

    def clean_text(self, text):
        """Remove markdown formatting and clean up text."""
        if not text:
            return text
            
        # Remove markdown bold syntax
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        
        # Remove markdown list markers
        text = re.sub(r'^\s*[-*]\s*', '', text, flags=re.MULTILINE)
        
        # Remove section headers
        text = re.sub(r'^#+\s*.*$', '', text, flags=re.MULTILINE)
        
        # Remove empty lines
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Clean up any remaining whitespace
        text = text.strip()
        
        return text

    def handle(self, *args, **options):
        try:
            # Get all CVs
            cvs = CvWriter.objects.all()
            
            for cv in cvs:
                self.stdout.write(f"\nProcessing CV ID: {cv.id}")
                
                # Clean professional summary
                try:
                    summary = ProfessionalSummary.objects.filter(cv=cv).first()
                    if summary:
                        summary.summary = self.clean_text(summary.summary)
                        summary.save()
                        self.stdout.write("Cleaned professional summary")
                except Exception as e:
                    self.stdout.write(f"Error cleaning professional summary: {str(e)}")
                
                # Clean experiences
                try:
                    experiences = Experience.objects.filter(user=cv.user)
                    for exp in experiences:
                        # Format job title
                        exp.job_title = self.format_job_title(exp.job_title)
                        
                        # Format dates
                        exp.start_date = self.format_date(exp.start_date)
                        exp.end_date = self.format_date(exp.end_date)
                        
                        # Format description and achievements
                        if exp.job_description:
                            exp.job_description = self.format_experience(exp.job_description)
                        if exp.achievements:
                            exp.achievements = self.format_experience(exp.achievements)
                        exp.save()
                    self.stdout.write(f"Cleaned {experiences.count()} experiences")
                except Exception as e:
                    self.stdout.write(f"Error cleaning experiences: {str(e)}")
                
                # Clean skills
                try:
                    skills = Skill.objects.filter(user=cv.user)
                    for skill in skills:
                        if skill.skill_name:
                            skill.skill_name = self.clean_text(skill.skill_name)
                        if skill.skill_level:
                            skill.skill_level = self.clean_text(skill.skill_level)
                        skill.save()
                    self.stdout.write(f"Cleaned {skills.count()} skills")
                except Exception as e:
                    self.stdout.write(f"Error cleaning skills: {str(e)}")
                
                self.stdout.write(self.style.SUCCESS(f"Successfully cleaned CV ID: {cv.id}"))
            
            self.stdout.write(self.style.SUCCESS("\nAll CVs have been cleaned successfully"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error cleaning CVs: {str(e)}"))
            return 