import PyPDF2
import docx
import re
import spacy
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from dateutil import parser as date_parser
import io
import pdfplumber  # Alternative PDF parsing library
import os

# Graceful pytesseract import
try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    PYTESSERACT_AVAILABLE = False
    print("Warning: pytesseract or Pillow not available. OCR functionality will be limited.")

# Graceful pdfplumber import
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None
    PDFPLUMBER_AVAILABLE = False
    print("Warning: pdfplumber not available. PDF parsing functionality will be limited.")

logger = logging.getLogger(__name__)

class AdvancedDocumentParser:
    def __init__(self):
        try:
            # Load spaCy model for advanced NLP
            self.nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {e}")
            self.nlp = None

    def parse_pdf(self, file_path: str) -> str:
        """
        Advanced PDF parsing using multiple techniques
        
        Args:
            file_path (str): Path to PDF file
        
        Returns:
            str: Extracted text
        """
        try:
            # Try pdfplumber first if available
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(file_path) as pdf:
                    text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
                    if text.strip():
                        return text
            
            # Fallback to PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = " ".join(page.extract_text() for page in pdf_reader.pages)
                if text.strip():
                    return text
            
            # OCR fallback for scanned PDFs
            return self._ocr_pdf(file_path)
        
        except Exception as e:
            logger.error(f"PDF parsing failed: {e}")
            return ""

    def _ocr_pdf(self, file_path: str) -> str:
        """
        Perform OCR on PDF pages
        
        Args:
            file_path (str): Path to PDF file
        
        Returns:
            str: Extracted text using OCR
        """
        # Use pdfplumber to convert PDF to images
        full_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # Convert page to image
                img = page.to_image()
                
                # Perform OCR
                page_text = pytesseract.image_to_string(img)
                full_text += page_text + "\n"
        
        return full_text

    def parse_docx(self, file_path: str) -> str:
        """
        Advanced DOCX parsing
        
        Args:
            file_path (str): Path to DOCX file
        
        Returns:
            str: Extracted text
        """
        try:
            return self.extract_text_from_docx(file_path)
        
        except Exception as e:
            logger.error(f"DOCX parsing error: {e}")
            return ""

    def extract_text_from_docx(self, docx_path):
        """Extract text from DOCX file using multiple XML parsing strategies"""
        try:
            with zipfile.ZipFile(docx_path) as zf:
                # Try document.xml first
                try:
                    xml_content = zf.read('word/document.xml')
                    tree = ET.fromstring(xml_content)
                    
                    # XML namespace
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    
                    # Find all text elements
                    text_elements = tree.findall('.//w:t', ns)
                    
                    # Extract text
                    texts = [elem.text for elem in text_elements if elem.text and elem.text.strip()]
                    
                    # Join texts
                    text = ' '.join(texts)
                    
                    if text.strip():
                        return text
                except Exception as doc_xml_error:
                    print(f"Error parsing document.xml: {doc_xml_error}")
                
                # Fallback: list all XML files and try parsing
                xml_files = [f for f in zf.namelist() if f.endswith('.xml')]
                
                for xml_file in xml_files:
                    try:
                        xml_content = zf.read(xml_file)
                        tree = ET.fromstring(xml_content)
                        
                        # Try different text extraction strategies
                        text_elements = tree.findall('.//text()')
                        texts = [elem for elem in text_elements if elem and elem.strip()]
                        
                        text = ' '.join(texts)
                        
                        if text.strip():
                            print(f"Text extracted from {xml_file}")
                            return text
                    except Exception as xml_error:
                        print(f"Error parsing {xml_file}: {xml_error}")
                
                print(f"WARNING: No text extracted from {docx_path}")
                return ''
        
        except Exception as e:
            print(f"CRITICAL ERROR extracting text from DOCX {docx_path}: {type(e).__name__} - {e}")
            return ''

    def extract_personal_info(self, text: str) -> Dict[str, str]:
        """
        Extract personal information using advanced NLP and regex techniques
        
        Args:
            text (str): Document text
        
        Returns:
            Dict[str, str]: Extracted personal info
        """
        personal_info = {
            'first_name': '',
            'last_name': '',
            'email': '',
            'phone': '',
            'location': ''
        }

        # Preprocess text
        text = text.replace('\n', ' ')

        # Email extraction with more comprehensive pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        personal_info['email'] = emails[0] if emails else ''

        # Phone number extraction (multiple international formats)
        phone_patterns = [
            r'\b(\+?1\s*)?(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})\b',  # US format
            r'\b0\d{9,10}\b',  # UK/EU format
            r'\b\d{10}\b'  # Generic 10-digit
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                # Format the phone number
                phone = ''.join(phones[0])
                personal_info['phone'] = phone
                break

        # Advanced name extraction
        name_patterns = [
            # Look for name at the top of the document
            r'^([A-Z][a-z]+)\s+([A-Z][a-z]+)',
            # Look for name in signature or header
            r'Name:\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)',
            # Fallback to spaCy name detection
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                personal_info['first_name'] = name_match.group(1)
                personal_info['last_name'] = name_match.group(2)
                break

        # Fallback to spaCy name extraction if regex fails
        if (not personal_info['first_name'] or not personal_info['last_name']) and self.nlp:
            doc = self.nlp(text)
            person_entities = [ent for ent in doc.ents if ent.label_ == 'PERSON']
            if person_entities:
                names = person_entities[0].text.split()
                if len(names) >= 2:
                    personal_info['first_name'] = names[0]
                    personal_info['last_name'] = ' '.join(names[1:])

        # Location extraction with more context
        location_patterns = [
            r'(?:located\s*in|based\s*in|from)\s*([A-Za-z\s]+(?:,\s*[A-Z]{2})?)',
            r'([A-Za-z\s]+(?:,\s*[A-Z]{2})?\s*\d{5})',
            # Extract city and state from work experience
            r'(?:City|Location)[\s:]+([A-Za-z\s]+(?:,\s*[A-Z]{2})?)'
        ]
        for pattern in location_patterns:
            locations = re.findall(pattern, text, re.IGNORECASE)
            if locations:
                personal_info['location'] = locations[0]
                break

        return personal_info

    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract education details with improved accuracy
        
        Args:
            text (str): Document text
        
        Returns:
            List[Dict[str, Any]]: List of education entries
        """
        education_entries = []
        
        # Comprehensive education patterns
        education_patterns = [
            # Detailed pattern with degree, field, school, and year
            r'([A-Z][a-z]+\s+(?:State|University))\s+(\d{4})\s+([A-Z][a-z]+(?:\s+of)?)\s+([A-Z][a-z\s]+)',
            
            # Degree, Field, and School
            r'(Bachelor(?:\'s)?|Master(?:\'s)?|PhD|Doctorate|Associate)\s+(?:of|in)\s+([A-Za-z\s]+)\s+(?:at|from)\s+([A-Za-z\s]+(?:\s+University)?)',
            
            # Alternative pattern
            r'Graduated\s+(?:with|from)\s+([A-Za-z\s]+)\s+with\s+a\s+(Bachelor(?:\'s)?|Master(?:\'s)?|PhD)\s+in\s+([A-Za-z\s]+)',
            
            # Simplified pattern
            r'(Bachelor(?:\'s)?|Master(?:\'s)?|PhD)\s+in\s+([A-Za-z\s]+)'
        ]

        # Preprocess text
        text = text.replace('\n', ' ')

        for pattern in education_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Handle different match group configurations
                if len(match.groups()) == 4:
                    entry = {
                        'school': match.group(1),
                        'graduation_year': match.group(2),
                        'degree': match.group(3),
                        'field': match.group(4)
                    }
                elif len(match.groups()) == 3:
                    entry = {
                        'degree': match.group(1),
                        'field': match.group(2),
                        'school': match.group(3),
                        'graduation_year': ''
                    }
                elif len(match.groups()) == 2:
                    entry = {
                        'degree': match.group(1),
                        'field': match.group(2),
                        'school': '',
                        'graduation_year': ''
                    }
                else:
                    continue
                
                education_entries.append(entry)

        return education_entries

    def _extract_skills(self, text: str) -> List[Dict[str, str]]:
        """
        Extract skills from text using comprehensive, domain-aware techniques
        
        Args:
            text (str): Document text
        
        Returns:
            List[Dict[str, str]]: List of extracted skills with name and level
        """
        # Domain-specific skill categories
        skill_keywords = {
            'arts_technical': [
                'photography', 'serigraphy', 'ceramics', 'mural painting', 
                'mask making', 'glass mosaics', 'commercial graphic arts', 
                'claymation', 'silk screening', 'drawing', 'painting',
                'visual arts', 'digital media', 'art techniques'
            ],
            'education_skills': [
                'curriculum development', 'lesson planning', 'student engagement',
                'instructional techniques', 'assessment', 'differentiated instruction',
                'classroom management', 'creative lesson planning'
            ],
            'soft_skills': [
                'communication', 'leadership', 'problem solving', 'creativity', 
                'adaptability', 'student-centered innovation', 'collaborative skills',
                'interpersonal skills', 'empathy', 'organizational skills'
            ]
        }
        
        # Preprocess text
        text = text.lower()
        
        # Extract skills using multiple strategies
        skills = set()
        
        # 1. Section-based skill extraction
        sections = {
            'skills': r'skills?:?\s*(.*?)(?:\n\n|\n|$)',
            'highlights': r'highlights?:?\s*(.*?)(?:\n\n|\n|$)',
            'interests': r'interests?:?\s*(.*?)(?:\n\n|\n|$)',
            'additional information': r'additional\s*information:?\s*(.*?)(?:\n\n|\n|$)'
        }
        
        for section_name, section_pattern in sections.items():
            section_match = re.search(section_pattern, text, re.IGNORECASE | re.DOTALL)
            if section_match:
                section_text = section_match.group(1)
                # Extract skills from section text
                for category, category_skills in skill_keywords.items():
                    for skill in category_skills:
                        if skill in section_text:
                            skills.add({
                                'name': skill.title(),
                                'level': 'Advanced' if category == 'arts_technical' else 'Proficient'
                            })
        
        # 2. Experience-based skill extraction
        experience_sections = [
            r'experience:?\s*(.*?)(?:\n\n|\n|$)',
            r'work\s*experience:?\s*(.*?)(?:\n\n|\n|$)'
        ]
        
        for exp_pattern in experience_sections:
            exp_match = re.search(exp_pattern, text, re.IGNORECASE | re.DOTALL)
            if exp_match:
                exp_text = exp_match.group(1)
                for category, category_skills in skill_keywords.items():
                    for skill in category_skills:
                        if skill in exp_text:
                            skills.add({
                                'name': skill.title(),
                                'level': 'Advanced' if category in ['arts_technical', 'education_skills'] else 'Intermediate'
                            })
        
        # 3. Regex-based skill extraction
        skill_patterns = [
            r'\b(?:expertise|proficient|skilled|experienced)\s*in\s*([a-z\s]+)',
            r'\b([a-z\s]+)\s*(?:skills?|proficiency|knowledge)',
            r'\b(?:strong\s+)?([a-z\s]+)\s*(?:background|experience|techniques)'
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if 2 <= len(match.split()) <= 5:
                    # Check against predefined skill categories
                    level = 'Intermediate'
                    for category, category_skills in skill_keywords.items():
                        if any(skill in match.lower() for skill in category_skills):
                            level = 'Advanced' if category in ['arts_technical', 'education_skills'] else 'Proficient'
                    
                    skills.add({
                        'name': match.title(),
                        'level': level
                    })
        
        # 4. Filter and clean skills
        final_skills = []
        seen_skills = set()
        for skill in skills:
            skill_name = skill['name']
            normalized_name = skill_name.lower().strip()
            
            # Remove duplicates and very short skills
            if (normalized_name not in seen_skills and 
                len(normalized_name) > 2 and 
                not any(char.isdigit() for char in normalized_name)):
                
                final_skills.append({
                    'name': skill_name,
                    'level': skill.get('level', 'Intermediate')
                })
                seen_skills.add(normalized_name)
        
        return final_skills

    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract work experience with improved pattern matching
        
        Args:
            text (str): Document text
        
        Returns:
            List[Dict[str, Any]]: Work experience entries
        """
        experiences = []
        
        # Comprehensive experience patterns
        experience_patterns = [
            # Detailed pattern with job title, company, location, dates, and responsibilities
            r'([A-Za-z\s]+)\s*,?\s*([A-Za-z\s]+)\s*,?\s*([A-Za-z\s,]+)?\s*(?:from|@)\s*(\d{4})\s*(?:to|-)?\s*(\d{4}|Present)',
            
            # Pattern: Job Title | Company | Duration
            r'([A-Za-z\s]+)\s*\|\s*([A-Za-z\s]+)\s*\|\s*(\d{4}\s*-\s*(?:\d{4}|Present))',
            
            # Pattern: Job Title at Company from Start to End
            r'([A-Za-z\s]+)\s+at\s+([A-Za-z\s]+)\s+from\s+(\d{4}\s+to\s+(?:\d{4}|Present))'
        ]

        # Preprocess text
        text = text.replace('\n', ' ')

        for pattern in experience_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Handle different match group configurations
                if len(match.groups()) == 5:
                    exp = {
                        'job_title': match.group(1).strip(),
                        'company': match.group(2).strip(),
                        'location': match.group(3).strip() if match.group(3) else '',
                        'start_date': match.group(4).strip(),
                        'end_date': match.group(5).strip()
                    }
                elif len(match.groups()) == 3:
                    exp = {
                        'job_title': match.group(1).strip(),
                        'company': match.group(2).strip(),
                        'duration': match.group(3).strip(),
                        'location': '',
                        'start_date': '',
                        'end_date': ''
                    }
                else:
                    continue
                
                experiences.append(exp)

        return experiences

    def _extract_summary(self, text: str) -> str:
        """
        Extract professional summary with improved detection and multiple strategies
        
        Args:
            text (str): Document text
        
        Returns:
            str: Professional summary
        """
        # Enhanced summary detection patterns with multiple variations
        summary_headers = [
            # Primary headers
            r'professional\s+summary',
            r'career\s+summary',
            r'professional\s+profile',
            r'qualifications\s+summary',
            r'skills?\s+overview',
            r'career\s+highlights',
            r'about\s+me',
            r'profile',
            r'summary',
            
            # Alternative phrasings
            r'professional\s+objective',
            r'career\s+goal',
            r'professional\s+statement',
            r'executive\s+summary'
        ]
        
        # Preprocess text
        text = text.replace('\n', ' ')
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        # Strategy 1: Exact header match with following text
        for header in summary_headers:
            # Look for header followed by text up to next potential section
            pattern = rf'(?:{header})[:.]?\s*(.+?)(?=education|experience|skills|$)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                summary = match.group(1).strip()
                # Basic cleaning and length check
                if 10 <= len(summary) <= 500:
                    return summary
        
        # Strategy 2: Paragraph-based extraction
        # Look for first paragraph after summary headers
        paragraph_patterns = [
            r'(?:professional\s+summary|career\s+summary|profile)[:.]?\s*(.+?\.)\s',
            r'((?:[A-Z][a-z]+\s+){3,}[a-z]+\.)'  # Paragraph starting with capitalized words
        ]
        
        for pattern in paragraph_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                summary = match.group(1).strip()
                # Basic cleaning and length check
                if 10 <= len(summary) <= 500:
                    return summary
        
        # Strategy 3: First few sentences near top of document
        first_sentences_pattern = r'^(.{50,500}?(?:\.|;))'
        match = re.search(first_sentences_pattern, text, re.MULTILINE | re.DOTALL)
        if match:
            summary = match.group(1).strip()
            if 10 <= len(summary) <= 500:
                return summary
        
        # Fallback: Generic text extraction near top of document
        generic_pattern = r'^(.{50,300})'
        match = re.search(generic_pattern, text, re.MULTILINE | re.DOTALL)
        if match:
            summary = match.group(1).strip()
            return summary
        
        return ""  # No summary found

    @classmethod
    def test_summary_extraction(cls, text: str) -> None:
        """
        Test method to demonstrate summary extraction capabilities
        
        Args:
            text (str): CV text to extract summary from
        """
        parser = cls()
        summary = parser._extract_summary(text)
        
        print("Summary Extraction Test:")
        print("-" * 50)
        print("Extracted Summary:")
        print(summary)
        print("-" * 50)
        
        # Detailed diagnostic information
        print("Extraction Diagnostics:")
        print(f"Summary Length: {len(summary)} characters")
        print(f"First 100 characters: {summary[:100]}...")

    @classmethod
    def test_summary_extraction_batch(cls, directory_path: str) -> None:
        """
        Batch test summary extraction across multiple CV documents
        
        Args:
            directory_path (str): Path to directory containing CV documents
        """
        def extract_text_from_pdf(pdf_path):
            """Extract text from PDF using multiple fallback methods"""
            try:
                # Try pdfplumber first
                with pdfplumber.open(pdf_path) as pdf:
                    text = ' '.join([page.extract_text() or '' for page in pdf.pages])
                    if text.strip():
                        return text.strip()
                
                # Fallback to PyPDF2
                import PyPDF2
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ' '.join([page.extract_text() or '' for page in reader.pages])
                    if text.strip():
                        return text.strip()
                
                print(f"WARNING: No text extracted from PDF {pdf_path}")
                return ''
            
            except Exception as e:
                print(f"CRITICAL ERROR extracting text from PDF {pdf_path}: {type(e).__name__} - {e}")
                return ''

        def extract_text_from_docx(docx_path):
            """Extract text from DOCX file with multiple extraction methods and detailed logging"""
            try:
                # Method 1: python-docx with detailed logging
                doc = docx.Document(docx_path)
                
                # Log document details
                print(f"Extracting DOCX: {docx_path}")
                print(f"Total paragraphs: {len(doc.paragraphs)}")
                
                # Extract non-empty paragraphs
                paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
                
                print(f"Non-empty paragraphs: {len(paragraphs)}")
                for i, para in enumerate(paragraphs, 1):
                    print(f"Paragraph {i}: {para[:100]}...")
                
                # Final text processing
                text = ' '.join(paragraphs)
                
                if not text.strip():
                    print(f"WARNING: No text extracted from {docx_path}")
                
                return text
            
            except Exception as e:
                print(f"CRITICAL ERROR extracting text from DOCX {docx_path}: {type(e).__name__} - {e}")
                return ''
        
        # Supported file extensions
        supported_extensions = ['.pdf', '.docx']
        
        # Prepare results tracking with more detailed error logging
        results = {
            'total_documents': 0,
            'processed_documents': 0,
            'summary_extracted': 0,
            'no_summary_found': 0,
            'extraction_failures': 0,
            'failed_documents': []
        }

        # Batch processing
        print("Summary Extraction Batch Test")
        print("=" * 50)

        for filename in os.listdir(directory_path):
            # Check file extension
            if not any(filename.lower().endswith(ext) for ext in supported_extensions):
                continue

            filepath = os.path.join(directory_path, filename)
            results['total_documents'] += 1

            try:
                # Extract text based on file type
                if filename.lower().endswith('.pdf'):
                    text = extract_text_from_pdf(filepath)
                elif filename.lower().endswith('.docx'):
                    text = extract_text_from_docx(filepath)
                else:
                    continue

                # Detailed text extraction diagnostics
                if not text.strip():
                    print(f"FAILURE: No extractable text in {filename}")
                    results['extraction_failures'] += 1
                    results['failed_documents'].append({
                        'filename': filename,
                        'reason': 'No extractable text'
                    })
                    continue

                # Extract summary
                parser = cls()
                summary = parser._extract_summary(text)

                # Print results
                print(f"\nDocument: {filename}")
                print("-" * 30)
                if summary:
                    results['summary_extracted'] += 1
                    print(f"Summary ({len(summary)} chars): {summary}")
                else:
                    results['no_summary_found'] += 1
                    print("No summary found")
                    results['failed_documents'].append({
                        'filename': filename,
                        'reason': 'No summary extracted'
                    })

                results['processed_documents'] += 1

            except Exception as e:
                print(f"UNHANDLED ERROR processing {filename}: {type(e).__name__} - {e}")
                results['extraction_failures'] += 1
                results['failed_documents'].append({
                    'filename': filename,
                    'reason': f'{type(e).__name__}: {e}'
                })

        # Print summary statistics
        print("\n\nBatch Test Summary")
        print("=" * 50)
        for key, value in results.items():
            if key != 'failed_documents':
                print(f"{key.replace('_', ' ').title()}: {value}")
        
        # Detailed failure report
        print("\nFailed Documents Details:")
        for failure in results['failed_documents']:
            print(f"- {failure['filename']}: {failure['reason']}")

    def parse_document(self, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        Main document parsing method
        
        Args:
            file_path (str): Path to document
            document_type (str): Type of document
        
        Returns:
            Dict[str, Any]: Parsed document data
        """
        # Extract text based on document type
        text = (
            self.parse_pdf(file_path) if document_type == 'pdf' 
            else self.parse_docx(file_path)
        )

        # Extract structured data
        parsed_data = {
            'personal_info': self.extract_personal_info(text),
            'education': self.extract_education(text),
            'professional_summary': self._extract_summary(text),
            'experience': self._extract_experience(text),
            'skills': self._extract_skills(text)
        }

        return parsed_data

class DocumentParser(AdvancedDocumentParser):
    def __init__(self, ml_predictor=None):
        """
        Maintains backwards compatibility with the old DocumentParser
        
        Args:
            ml_predictor: Optional ML predictor (not used in new implementation)
        """
        super().__init__()
        # Ignore ml_predictor for now, can be extended later if needed
    
    def parse_document(self, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        Wrapper method to maintain old interface
        
        Args:
            file_path (str): Path to the document
            document_type (str): Type of document ('pdf' or 'docx')
            
        Returns:
            Dict[str, Any]: Parsed CV data
        """
        try:
            # Extract text from document
            text = self._extract_text(file_path, document_type)
            
            # Return parsed data
            return super().parse_document(file_path, document_type)
        except Exception as e:
            logger.error(f"Failed to parse document: {str(e)}")
            return {
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
    
    def _extract_text(self, file_path: str, document_type: str) -> str:
        """
        Extracts text from a document
        
        Args:
            file_path (str): Path to the document
            document_type (str): Type of document ('pdf' or 'docx')
            
        Returns:
            str: Extracted text
        """
        if document_type == 'pdf':
            return self.parse_pdf(file_path)
        elif document_type == 'docx':
            return self.parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported document type: {document_type}")

class ParserException(Exception):
    """Custom exception for parser errors"""
    pass

# Batch test execution
if __name__ == '__main__':
    cv_directory = '/Users/michaeladeleye/Documents/Coding/ella/Ella-backend/cv_documents'
    AdvancedDocumentParser.test_summary_extraction_batch(cv_directory)
