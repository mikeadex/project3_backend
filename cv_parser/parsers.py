import PyPDF2
import docx
import re
import nltk
import logging
from dateutil import parser
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class ParserException(Exception):
    """Custom exception for parser errors"""
    pass

class DocumentParser:
    def __init__(self):
        """
        Initializes the parser and downloads NLTK resources
        
        This constructor method is called when an instance of the class is created. It ensures that the 
        required NLTK datasets for tokenization, part-of-speech tagging, named entity recognition, 
        and word lists are available for use in the application.

        The following resources are downloaded:
        - 'punkt': A tokenizer for splitting text into sentences and words.
        - 'average_perceptron_tagger': A part-of-speech tagger for labeling words with their grammatical 
        categories.
        - 'maxent_ne_chunker': A named entity chunker for identifying named entities in text.
        - 'words': A list of words for various NLP tasks.
        """
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('averaged_perceptron_tagger', quiet=True)
            nltk.download('maxent_ne_chunker', quiet=True)
            nltk.download('words', quiet=True)
        except Exception as e:
            logger.error(f"Failed to download NLTK resources: {str(e)}")
            raise ParserException("Failed to initialize parser resources")

    def parse_document(self, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        Main entry point for parsing documents
        
        Args:
            file_path (str): Path to the document
            document_type (str): Type of document ('pdf' or 'docx')
            
        Returns:
            Dict[str, Any]: Parsed CV data
        """
        try:
            logger.info(f"Starting to parse document: {file_path}")
            
            # Extract text based on document type
            if document_type == 'pdf':
                text = self.parse_pdf(file_path)
            elif document_type == 'docx':
                text = self.parse_docx(file_path)
            else:
                raise ParserException(f"Unsupported document type: {document_type}")
            
            if not text:
                raise ParserException("No text could be extracted from document")
            
            # Parse sections
            parsed_data = self.extract_sections(text)
            
            logger.info(f"Successfully parsed document: {file_path}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing document {file_path}: {str(e)}")
            raise ParserException(f"Failed to parse document: {str(e)}")

    def parse_pdf(self, file_path: str) -> str:
        """
        Parses a PDF file and extracts text from all its pages.
        
        Args:
            file_path (str): The path to the PDF file to be parsed.

        Returns:
            str: The extracted text from the PDF file.
        """
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            
            if not text.strip():
                raise ParserException("No text extracted from PDF")
                
            return text
            
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise ParserException(f"Failed to parse PDF: {str(e)}")

    def parse_docx(self, file_path: str) -> str:
        """
        Parses a DOCX file and extracts text from its content.
        
        Args:
            file (str): The path to the DOCX file to be parsed.

        Returns:
            str: The extracted text from the DOCX file.
        """
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            if not text.strip():
                raise ParserException("No text extracted from DOCX")
                
            return text
            
        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {str(e)}")
            raise ParserException(f"Failed to parse DOCX: {str(e)}")

    def extract_sections(self, text: str) -> Dict[str, Any]:
        # Basic structure for extracted data
        data = {
            'personal_info': {},
            'professional_summary': '',
            'education': [],
            'experience': [],
            'skills': [],
            'languages': [],
            'certifications': [],
            'references': [],
            'interests': [],
            'social_media': []
        }

        #  split text into sections
        sections = self._split_into_sections(text)

        # extract information from each section if available
        for section_title, section_content in sections.items():
            if 'education' in section_title.lower():
                data['education'] = self._parse_education(section_content)
            elif 'experience' in section_title.lower():
                data['experience'] = self._parse_experience(section_content)
            elif 'skills' in section_title.lower():
                data['skills'] = self._parse_skills(section_content)
            elif 'professional_summary' in section_title.lower():
                data['professional_summary'] = self._parse_professional_summary(section_content)
            elif 'Language' in section_title.lower():
                data['languages'] = self._parse_languages(section_content)
            elif 'Certification' in section_title.lower():
                data['certifications'] = self._parse_certifications(section_content)
            elif 'reference' in section_title.lower():
                data['references'] = self._parse_references(section_content)
            elif 'interest' in section_title.lower():
                data['interests'] = self._parse_interests(section_content)
            elif 'social_media' in section_title.lower():
                data['social_media'] = self._parse_social_media(section_content)

        return data

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        # Implementation for splitting text into sections
        # This is a placeholder - you'll need to implement proper section detection
        sections = {}
        current_section = ''
        current_content = []

        for line in text.split('\n'):
            if self._is_section_header(line):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.strip()
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _is_section_header(self, line: str) -> bool:
        """
        Determines if a line is a section header.
        
        Args:
            line (str): The line to check
            
        Returns:
            bool: True if the line is a section header, False otherwise
        """
        # Common section headers in CVs
        common_headers = [
            'education', 'academic background', 'academic history',
            'experience', 'work experience', 'employment history', 'professional experience',
            'skills', 'technical skills', 'competencies', 'expertise',
            'languages', 'language proficiency',
            'certifications', 'certificates', 'qualifications',
            'references', 'professional references',
            'summary', 'professional summary', 'profile', 'about me',
            'interests', 'hobbies', 'activities',
            'projects', 'personal projects',
            'publications', 'research',
            'awards', 'achievements',
            'volunteer', 'volunteering',
            'social media', 'online presence'
        ]
        
        # Clean the line
        line = line.strip().lower()
        
        # Check if line matches any common header
        if any(header in line for header in common_headers):
            # Additional checks to ensure it's a header:
            # 1. Length check (headers are usually short)
            if len(line) > 50:
                return False
                
            # 2. Check for common header formatting
            if (line.isupper() or  # ALL CAPS
                line.istitle() or  # Title Case
                line.endswith(':') or  # Ends with colon
                re.match(r'^[A-Z\s]+$', line)):  # All caps with spaces
                return True
                
            # 3. Check for common header patterns
            header_patterns = [
                r'^[\d\.]+ .*',  # Numbered sections (e.g., "1. Experience")
                r'^[A-Z].*:$',   # Capitalized with colon
                r'^[\w\s]{2,30}$'  # Word(s) of reasonable length
            ]
            
            return any(re.match(pattern, line) for pattern in header_patterns)
            
        return False

    def _parse_education(self, text: str) -> list:
        """
        Parses education section text into structured data.
        
        Args:
            text (str): The text content of the education section
            
        Returns:
            list: List of dictionaries containing education information
        """
        education_entries = []
        # Split into entries (usually separated by blank lines)
        entries = [entry.strip() for entry in text.split('\n\n') if entry.strip()]
        
        for entry in entries:
            education_info = {
                'school': '',
                'degree': '',
                'field': '',
                'start_date': None,
                'end_date': None,
                'current': False
            }
            
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
                
            # First line usually contains school name
            education_info['school'] = lines[0]
            
            for line in lines[1:]:
                # Look for degree and field
                if any(degree in line.lower() for degree in ['bachelor', 'master', 'phd', 'diploma', 'certificate']):
                    parts = line.split('in', 1)
                    if len(parts) > 1:
                        education_info['degree'] = parts[0].strip()
                        education_info['field'] = parts[1].strip()
                    else:
                        education_info['degree'] = line.strip()
                
                # Look for dates
                date_match = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})\s*-\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}|Present)', line, re.IGNORECASE)
                if date_match:
                    try:
                        education_info['start_date'] = parser.parse(date_match.group(1)).strftime('%Y-%m-%d')
                        if date_match.group(2).lower() == 'present':
                            education_info['current'] = True
                        else:
                            education_info['end_date'] = parser.parse(date_match.group(2)).strftime('%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue
            
            education_entries.append(education_info)
        
        return education_entries

    def _parse_experience(self, text: str) -> list:
        """
        Parses work experience section text into structured data.
        
        Args:
            text (str): The text content of the experience section
            
        Returns:
            list: List of dictionaries containing experience information
        """
        experience_entries = []
        # Split into entries (usually separated by blank lines)
        entries = [entry.strip() for entry in text.split('\n\n') if entry.strip()]
        
        for entry in entries:
            experience_info = {
                'company': '',
                'title': '',
                'description': '',
                'achievements': '',
                'start_date': None,
                'end_date': None,
                'type': 'Full-time',
                'current': False
            }
            
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
            
            # First line usually contains job title and company
            title_company = lines[0].split('@') if '@' in lines[0] else lines[0].split('at')
            if len(title_company) > 1:
                experience_info['title'] = title_company[0].strip()
                experience_info['company'] = title_company[1].strip()
            else:
                experience_info['title'] = lines[0]
                if len(lines) > 1:
                    experience_info['company'] = lines[1]
            
            description_lines = []
            achievements_started = False
            
            for line in lines[1:]:
                # Look for employment type
                if any(type_word in line.lower() for type_word in ['full-time', 'part-time', 'contract', 'internship', 'freelance']):
                    for type_word in ['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance']:
                        if type_word.lower() in line.lower():
                            experience_info['type'] = type_word
                            break
                    continue
                
                # Look for dates
                date_match = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})\s*-\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}|Present)', line, re.IGNORECASE)
                if date_match:
                    try:
                        experience_info['start_date'] = parser.parse(date_match.group(1)).strftime('%Y-%m-%d')
                        if date_match.group(2).lower() == 'present':
                            experience_info['current'] = True
                        else:
                            experience_info['end_date'] = parser.parse(date_match.group(2)).strftime('%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue
                    continue
                
                # Check for achievements section
                if 'achievement' in line.lower() or 'accomplishment' in line.lower():
                    achievements_started = True
                    continue
                
                # Add line to appropriate section
                if achievements_started:
                    if line.strip():
                        experience_info['achievements'] += line.strip() + '\n'
                else:
                    if line.strip():
                        description_lines.append(line.strip())
            
            experience_info['description'] = '\n'.join(description_lines)
            experience_entries.append(experience_info)
        
        return experience_entries

    def _parse_skills(self, text: str) -> list:
        """
        Parses skills section text into structured data.
        
        Args:
            text (str): The text content of the skills section
            
        Returns:
            list: List of dictionaries containing skill information
        """
        skills = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Common skill level indicators
        level_indicators = {
            'expert': 'Expert',
            'advanced': 'Advanced',
            'intermediate': 'Intermediate',
            'beginner': 'Beginner',
            'basic': 'Beginner',
            'proficient': 'Advanced'
        }
        
        for line in lines:
            # Remove bullet points and other common separators
            line = re.sub(r'^[-•●\*]\s*', '', line)
            
            # Check if skill has level indicator
            skill_level = 'Intermediate'  # default level
            for indicator, level in level_indicators.items():
                if indicator in line.lower():
                    skill_level = level
                    line = re.sub(r'\s*[\(\[\-]\s*' + indicator + r'.*[\)\]]\s*', '', line, flags=re.IGNORECASE)
                    break
            
            # Clean up the skill name
            skill_name = line.strip()
            if skill_name:
                skills.append({
                    'name': skill_name,
                    'level': skill_level
                })
        
        return skills

    def _parse_professional_summary(self, text: str) -> str:
        """
        Parses professional summary section into a clean text.
        
        Args:
            text (str): The text content of the summary section
            
        Returns:
            str: Cleaned and formatted summary text
        """
        # Remove common headers and clean up the text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        summary = ' '.join(lines)
        
        # Remove any remaining headers or labels
        summary = re.sub(r'^(summary|profile|about|about me|professional summary)[\s:]+', '', summary, flags=re.IGNORECASE)
        
        return summary.strip()

    def _parse_languages(self, text: str) -> list:
        """
        Parses languages section into structured data.
        
        Args:
            text (str): The text content of the languages section
            
        Returns:
            list: List of dictionaries containing language information
        """
        languages = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Common language proficiency levels
        proficiency_levels = {
            'native': 'Native',
            'fluent': 'Fluent',
            'proficient': 'Proficient',
            'intermediate': 'Intermediate',
            'basic': 'Basic',
            'beginner': 'Basic',
            'c2': 'Native',
            'c1': 'Fluent',
            'b2': 'Proficient',
            'b1': 'Intermediate',
            'a2': 'Basic',
            'a1': 'Basic'
        }
        
        for line in lines:
            # Remove bullet points and other separators
            line = re.sub(r'^[-•●\*]\s*', '', line)
            
            # Try to split language and level
            parts = [p.strip() for p in re.split(r'[-:,()]', line) if p.strip()]
            
            if parts:
                language_info = {
                    'language_name': parts[0],
                    'language_level': 'Intermediate'  # default level
                }
                
                # Look for proficiency level in remaining parts
                for part in parts[1:]:
                    part_lower = part.lower()
                    for level_key, level_value in proficiency_levels.items():
                        if level_key in part_lower:
                            language_info['language_level'] = level_value
                            break
                
                languages.append(language_info)
        
        return languages

    def _parse_certifications(self, text: str) -> list:
        """
        Parses certifications section into structured data.
        
        Args:
            text (str): The text content of the certifications section
            
        Returns:
            list: List of dictionaries containing certification information
        """
        certifications = []
        entries = [entry.strip() for entry in text.split('\n\n') if entry.strip()]
        
        for entry in entries:
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
            
            cert_info = {
                'certificate_name': lines[0],
                'certificate_date': None,
                'certificate_link': ''
            }
            
            for line in lines[1:]:
                # Look for dates
                date_match = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})', line, re.IGNORECASE)
                if date_match:
                    try:
                        cert_info['certificate_date'] = parser.parse(date_match.group(1)).strftime('%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue
                
                # Look for URLs
                url_match = re.search(r'https?://\S+', line)
                if url_match:
                    cert_info['certificate_link'] = url_match.group(0)
            
            certifications.append(cert_info)
        
        return certifications

    def _parse_references(self, text: str) -> list:
        """
        Parses references section into structured data.
        
        Args:
            text (str): The text content of the references section
            
        Returns:
            list: List of dictionaries containing reference information
        """
        references = []
        entries = [entry.strip() for entry in text.split('\n\n') if entry.strip()]
        
        for entry in entries:
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
            
            ref_info = {
                'name': '',
                'title': '',
                'company': '',
                'email': '',
                'phone': '',
                'reference_type': 'Professional'
            }
            
            # First line usually contains the name
            ref_info['name'] = lines[0]
            
            for line in lines[1:]:
                # Look for email
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                if email_match:
                    ref_info['email'] = email_match.group(0)
                    continue
                
                # Look for phone numbers
                phone_match = re.search(r'\b(?:\+\d{1,3}[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b', line)
                if phone_match:
                    ref_info['phone'] = phone_match.group(0)
                    continue
                
                # Look for title and company
                if '@' in line or 'at' in line.lower():
                    parts = line.split('@') if '@' in line else line.lower().split('at')
                    if len(parts) > 1:
                        ref_info['title'] = parts[0].strip()
                        ref_info['company'] = parts[1].strip()
                
                # Determine reference type
                for ref_type in ['Professional', 'Academic', 'Personal']:
                    if ref_type.lower() in line.lower():
                        ref_info['reference_type'] = ref_type
                        break
            
            references.append(ref_info)
        
        return references

    def _parse_interests(self, text: str) -> list:
        """
        Parses interests section into structured data.
        
        Args:
            text (str): The text content of the interests section
            
        Returns:
            list: List of dictionaries containing interest information
        """
        interests = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            # Remove bullet points and other separators
            line = re.sub(r'^[-•●\*]\s*', '', line)
            
            # Clean up the interest name
            interest_name = line.strip()
            if interest_name:
                interests.append({
                    'name': interest_name
                })
        
        return interests

    def _parse_social_media(self, text: str) -> list:
        """
        Parses social media section into structured data.
        
        Args:
            text (str): The text content of the social media section
            
        Returns:
            list: List of dictionaries containing social media information
        """
        social_media = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Define platform patterns
        platform_patterns = {
            'LinkedIn': r'linkedin\.com',
            'GitHub': r'github\.com',
            'Twitter': r'twitter\.com',
            'Portfolio': r'portfolio|personal.*website',
            'Behance': r'behance\.net',
            'Dribbble': r'dribbble\.com'
        }
        
        for line in lines:
            # Look for URLs and platform names
            url_match = re.search(r'https?://\S+', line)
            if url_match:
                url = url_match.group(0)
                platform = 'Portfolio'  # default
                
                # Determine platform from URL
                for platform_name, pattern in platform_patterns.items():
                    if re.search(pattern, url, re.IGNORECASE):
                        platform = platform_name
                        break
                
                social_media.append({
                    'platform': platform,
                    'url': url
                })
            
        return social_media
