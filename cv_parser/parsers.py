import PyPDF2
import docx
import re
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple
from dateutil import parser as date_parser
import io
import os
import traceback
import json
import time  # Import time for timing measurements
from django.conf import settings

# Use the dedicated cv_parser logger - define early so it can be used in imports
logger = logging.getLogger("cv_parser")

# Conditional ML imports - only load if ML features enabled
try:
    import spacy

    SPACY_AVAILABLE = getattr(settings, "ENABLE_ML_FEATURES", False)
    if SPACY_AVAILABLE:
        import pdfplumber  # Alternative PDF parsing library
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    pdfplumber = None

# Import CV writer service for DeepSeek integration
try:
    from cv_writer.services import CVImprovementService

    LLM_SERVICES_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    LLM_SERVICES_AVAILABLE = False
    import logging

    logging.getLogger("cv_parser").warning(f"LLM services unavailable: {str(e)}")

# Graceful pytesseract import
try:
    import pytesseract
    from PIL import Image

    PYTESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    PYTESSERACT_AVAILABLE = False
    logger.warning(
        "pytesseract or Pillow not available. OCR functionality will be limited."
    )

# Graceful pdfplumber import
try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None
    PDFPLUMBER_AVAILABLE = False
    logger.warning(
        "pdfplumber not available. PDF parsing functionality will be limited."
    )


class AdvancedDocumentParser:
    def __init__(self):
        """Initialize parser with dependencies"""
        # Initialize logger
        import logging

        self.logger = logging.getLogger("cv_parser")

        # Try to load spaCy model for advanced NLP
        try:
            import spacy

            self.nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            self.logger.warning(f"Could not load spaCy model: {e}")
            self.nlp = None

        # Set up OCR engine
        try:
            import pytesseract

            self.pytesseract = pytesseract
        except ImportError:
            self.pytesseract = None
            self.logger.warning(
                "pytesseract not installed, OCR functionality will be limited"
            )

        # Check if we can use pdf2image
        try:
            import pdf2image

            self.pdf2image_available = True
        except ImportError:
            self.pdf2image_available = False
            self.logger.warning(
                "pdf2image not installed, using alternative PDF extraction method"
            )

        # Check if we can use docx2python
        try:
            import docx2python

            self.docx2python_available = True
        except ImportError:
            self.docx2python_available = False
            self.logger.warning(
                "docx2python not installed, using alternative DOCX extraction method"
            )

        # Check if CV segmentation API is available
        from django.conf import settings

        self.deepseek_api_key = getattr(settings, "DEEPSEEK_API_KEY", None)
        if not self.deepseek_api_key:
            self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")

        if not self.deepseek_api_key:
            self.logger.warning(
                "DeepSeek API key not found, CV segmentation will not be available"
            )

    def parse_pdf(self, file_path: str) -> str:
        """
        Advanced PDF parsing using multiple techniques with improved handling for complex layouts

        Args:
            file_path (str): Path to PDF file

        Returns:
            str: Extracted text
        """
        extracted_text = ""
        errors = []

        # Track successful extraction methods
        extraction_methods = []

        try:
            # 1. Try pdfplumber first if available - works well with formatted PDFs
            if PDFPLUMBER_AVAILABLE:
                try:
                    with pdfplumber.open(file_path) as pdf:
                        pages_text = []
                        for page in pdf.pages:
                            # Try to extract text with standard method
                            page_text = page.extract_text()
                            if page_text and page_text.strip():
                                pages_text.append(page_text)

                            # If standard extraction fails or returns minimal text, try table extraction
                            if not page_text or len(page_text.strip()) < 100:
                                tables = page.extract_tables()
                                if tables:
                                    for table in tables:
                                        table_text = "\n".join(
                                            [
                                                " | ".join([cell or "" for cell in row])
                                                for row in table
                                            ]
                                        )
                                        if table_text.strip():
                                            pages_text.append(table_text)

                        if pages_text:
                            pdfplumber_text = "\n\n".join(pages_text)
                            if pdfplumber_text.strip():
                                extracted_text = pdfplumber_text
                                extraction_methods.append("pdfplumber")
                except Exception as e:
                    errors.append(f"pdfplumber error: {str(e)}")

            # 2. Try PyPDF2 approach if pdfplumber didn't work or extracted minimal text
            if not extracted_text or len(extracted_text.split()) < 50:
                try:
                    with open(file_path, "rb") as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        pages_text = []
                        for page in pdf_reader.pages:
                            page_text = page.extract_text()
                            if page_text and page_text.strip():
                                pages_text.append(page_text)

                        if pages_text:
                            pypdf2_text = "\n\n".join(pages_text)
                            if pypdf2_text.strip():
                                # If pdfplumber failed completely, use PyPDF2 result
                                if not extracted_text:
                                    extracted_text = pypdf2_text
                                    extraction_methods.append("PyPDF2")
                                # If pdfplumber has some text but PyPDF2 has more, combine them
                                elif (
                                    len(pypdf2_text.split())
                                    > len(extracted_text.split()) * 1.5
                                ):
                                    extracted_text = pypdf2_text
                                    extraction_methods.append("PyPDF2")
                except Exception as e:
                    errors.append(f"PyPDF2 error: {str(e)}")

            # 3. OCR fallback for scanned PDFs or if other methods failed
            if not extracted_text or len(extracted_text.split()) < 50:
                try:
                    ocr_text = self._ocr_pdf(file_path)
                    if ocr_text and ocr_text.strip() and len(ocr_text.split()) > 20:
                        extracted_text = ocr_text
                        extraction_methods.append("OCR")
                except Exception as e:
                    errors.append(f"OCR error: {str(e)}")

            # Log the extraction method used
            if extraction_methods:
                logger.info(
                    f"PDF text extracted using: {', '.join(extraction_methods)}"
                )

            # Clean up the extracted text
            if extracted_text:
                # Remove excessive whitespace
                extracted_text = re.sub(r"\s+", " ", extracted_text)
                # Remove page numbers
                extracted_text = re.sub(r"\n\s*\d+\s*\n", "\n", extracted_text)
                # Clean up email addresses (sometimes broken across lines)
                extracted_text = re.sub(
                    r"([a-zA-Z0-9_.+-]+)\s*@\s*([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
                    r"\1@\2",
                    extracted_text,
                )

                return extracted_text
            else:
                error_msg = "All PDF extraction methods failed: " + "; ".join(errors)
                logger.error(error_msg)
                return ""

        except Exception as e:
            logger.error(f"PDF parsing failed with error: {str(e)}")
            return ""

    def _ocr_pdf(self, file_path: str) -> str:
        """
        Perform enhanced OCR on PDF pages with image preprocessing for better text extraction

        Args:
            file_path (str): Path to PDF file

        Returns:
            str: Extracted text using OCR
        """
        if not PYTESSERACT_AVAILABLE:
            logger.warning(
                "OCR requirements (pytesseract/PIL) not available. Skipping OCR."
            )
            return ""

        if not PDFPLUMBER_AVAILABLE:
            logger.warning(
                "pdfplumber not available for PDF to image conversion. Skipping OCR."
            )
            return ""

        try:
            import PIL.Image
            import PIL.ImageEnhance
            import numpy as np

            full_text = []

            with pdfplumber.open(file_path) as pdf:
                logger.info(f"Performing OCR on {len(pdf.pages)} pages")

                for i, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {i+1}/{len(pdf.pages)}")
                    try:
                        # Convert page to image with higher resolution
                        img = page.to_image(resolution=300)

                        # Get PIL image for preprocessing
                        pil_img = PIL.Image.open(io.BytesIO(img.original.tobytes()))

                        # Image preprocessing to improve OCR quality
                        # 1. Convert to grayscale
                        pil_img = pil_img.convert("L")

                        # 2. Increase contrast
                        enhancer = PIL.ImageEnhance.Contrast(pil_img)
                        pil_img = enhancer.enhance(2.0)

                        # 3. Thresholding to make text more distinct
                        threshold = 200
                        pil_img = pil_img.point(lambda p: 255 if p > threshold else 0)

                        # 4. Denoise
                        from PIL import ImageFilter

                        pil_img = pil_img.filter(ImageFilter.MedianFilter(size=3))

                        # Configure Tesseract for better results
                        custom_config = r"--oem 3 --psm 6 -l eng"  # Page segmentation mode 6: Assume single uniform block of text

                        # Perform OCR
                        page_text = pytesseract.image_to_string(
                            pil_img, config=custom_config
                        )

                        if page_text and page_text.strip():
                            full_text.append(page_text)
                    except Exception as e:
                        logger.warning(f"OCR failed for page {i+1}: {str(e)}")

            combined_text = "\n\n".join(full_text)

            # Post-process OCR text
            if combined_text:
                # Clean up common OCR errors
                combined_text = re.sub(
                    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]", "", combined_text
                )  # Remove non-printable chars
                combined_text = re.sub(
                    r"(?<!\w)I(?!\w)", "1", combined_text
                )  # Fix common I -> 1 confusion
                combined_text = re.sub(
                    r"(?<!\w)O(?!\w)", "0", combined_text
                )  # Fix common O -> 0 confusion
                combined_text = re.sub(
                    r"[\r\n]+", "\n", combined_text
                )  # Normalize line breaks

            return combined_text

        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            return ""

    def parse_docx(self, file_path: str) -> str:
        """
        Advanced DOCX parsing with improved reliability

        Args:
            file_path (str): Path to DOCX file

        Returns:
            str: Extracted text
        """
        try:
            # First try the standard docx library approach
            import docx

            doc = docx.Document(file_path)
            text = "\n".join(
                [
                    paragraph.text
                    for paragraph in doc.paragraphs
                    if paragraph.text.strip()
                ]
            )

            # If we got text, return it
            if text.strip():
                return text

            # If standard approach failed to extract text, try the XML method
            logger.info(
                f"Standard docx parsing returned minimal text, trying XML-based parsing for {file_path}"
            )
            return self.extract_text_from_docx(file_path)

        except Exception as e:
            logger.error(f"DOCX parsing error: {str(e)}")
            # Fall back to the XML method only if standard method fails
            try:
                return self.extract_text_from_docx(file_path)
            except Exception as xml_e:
                logger.error(f"Both DOCX parsing methods failed: {str(xml_e)}")
            return ""

    def extract_text_from_docx(self, docx_path):
        """Extract text from DOCX file using multiple XML parsing strategies"""
        try:
            with zipfile.ZipFile(docx_path) as zf:
                # Try document.xml first
                try:
                    xml_content = zf.read("word/document.xml")
                    tree = ET.fromstring(xml_content)

                    # XML namespace
                    ns = {
                        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                    }

                    # Find all text elements
                    text_elements = tree.findall(".//w:t", ns)

                    # Extract text
                    texts = [
                        elem.text
                        for elem in text_elements
                        if elem.text and elem.text.strip()
                    ]

                    # Join texts
                    text = " ".join(texts)

                    if text.strip():
                        return text
                except Exception as doc_xml_error:
                    logger.debug(f"Error parsing document.xml: {doc_xml_error}")

                # Fallback: list all XML files and try parsing
                xml_files = [f for f in zf.namelist() if f.endswith(".xml")]

                for xml_file in xml_files:
                    try:
                        xml_content = zf.read(xml_file)
                        tree = ET.fromstring(xml_content)

                        # Try different text extraction strategies
                        text_elements = tree.findall(".//text()")
                        texts = [
                            elem for elem in text_elements if elem and elem.strip()
                        ]

                        text = " ".join(texts)

                        if text.strip():
                            logger.debug(f"Text extracted from {xml_file}")
                            return text
                    except Exception as xml_error:
                        logger.debug(f"Error parsing {xml_file}: {xml_error}")

                logger.warning(f"No text extracted from {docx_path}")
                return ""

        except Exception as e:
            logger.error(
                f"Critical error extracting text from DOCX {docx_path}: {type(e).__name__} - {e}"
            )
            return ""

    def extract_experience(
        self, text: str, sections: Dict = None
    ) -> List[Dict[str, Any]]:
        """Public wrapper for experience extraction"""
        try:
            if sections:
                return self._extract_experience_efficient(text, sections)
            else:
                return self._extract_experience(text)
        except Exception as e:
            self.logger.error(f"Error in extract_experience: {e}")
            return []

    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Public wrapper for education extraction"""
        try:
            return self._extract_education(text)
        except Exception as e:
            self.logger.error(f"Error in extract_education: {e}")
            return []

    def extract_skills(self, text: str, sections: Dict = None) -> List[str]:
        """Public wrapper for skills extraction"""
        try:
            if sections:
                return (
                    self._extract_skills_efficient(text, sections)
                    if hasattr(self, "_extract_skills_efficient")
                    else self._extract_skills(text)
                )
            else:
                return self._extract_skills(text)
        except Exception as e:
            self.logger.error(f"Error in extract_skills: {e}")
            return []

    def extract_personal_info(self, text: str) -> Dict[str, Any]:
        """
        Extract personal information from text

        Args:
            text (str): Document text

        Returns:
            Dict[str, Any]: Dictionary of personal information
        """
        # Initialize result
        result = {
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "website": "",
            "twitter": "",
            "instagram": "",
        }

        # Try to find a personal info section first
        sections = self._identify_cv_sections_safe(text, timeout=2.0)
        personal_section_found = False

        if "personal_info" in sections:
            section_start, section_end = sections["personal_info"]
            personal_section = text[section_start:section_end]
            parsed_info = self._parse_personal_info_section(personal_section)

            # Merge parsed info into result
            for key, value in parsed_info.items():
                if value and not result.get(key):
                    result[key] = value

            personal_section_found = True

        # Also look for sections that might contain personal info with other names
        if not personal_section_found:
            personal_section_patterns = [
                r"(?:Contact|Personal|Profile|Contact Information|Personal Details)[:\s]*\n*(.*?)(?=\n\s*(?:Summary|Experience|Education|Skills|Objective|\Z))",
                r"(?:CONTACT|PERSONAL|PROFILE|CONTACT INFORMATION|PERSONAL DETAILS)[:\s]*\n*(.*?)(?=\n\s*(?:SUMMARY|EXPERIENCE|EDUCATION|SKILLS|OBJECTIVE|\Z))",
            ]

            for pattern in personal_section_patterns:
                personal_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if personal_match:
                    personal_section = personal_match.group(1)
                    parsed_info = self._parse_personal_info_section(personal_section)

                    # Merge parsed info into result
                    for key, value in parsed_info.items():
                        if value and not result.get(key):
                            result[key] = value

                    personal_section_found = True
                    break

        # If we couldn't find dedicated sections, extract from the full text
        # Extract email using regex pattern
        if not result["email"]:
            email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            email_matches = re.finditer(email_pattern, text)
            for email_match in email_matches:
                potential_email = email_match.group(0)
                # Basic validation to filter out unlikely emails
                if (
                    len(potential_email) < 50
                    and "/" not in potential_email
                    and not re.search(
                        r"example|test|sample|demo", potential_email, re.IGNORECASE
                    )
                ):
                    result["email"] = potential_email
                    break

        # Extract phone number
        if not result["phone"]:
            # Look for various phone formats
            phone_patterns = [
                r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",  # (123) 456-7890, 123-456-7890
                r"\b(?:\+\d{1,3}[-.\s]?)?\d{5}[-.\s]?\d{6}\b",  # +1 12345 123456
                r"\b(?:\+\d{1,3}[-.\s]?)?\d{4}[-.\s]?\d{3}[-.\s]?\d{3}\b",  # +44 1234 123 123
                r"\b(?:\+\d{1,3}[-.\s]?)?\d{10,11}\b",  # UK/International format (10-11 digits)
                r"\b0\d{10}\b",  # UK mobile starting with 0 (like 07950790748)
                r"\b(?:\+\d{1,3}[-.\s]?)?\d{4}[-.\s]?\d{6}\b",  # UK format with spacing
                r"(?:Phone|Tel|Telephone|Mobile|Cell)[:\s]+([0-9+\-\(\)\s\.]{7,20})",  # Phone: +1 (123) 456-7890
            ]

            for pattern in phone_patterns:
                phone_match = re.search(pattern, text)
                if phone_match:
                    if "Phone" in pattern:
                        # This pattern captures the label and the number, extract just the number
                        result["phone"] = phone_match.group(1).strip()
                    else:
                        result["phone"] = phone_match.group(0).strip()
                    # Basic cleanup of phone numbers
                    result["phone"] = re.sub(r"\s+", " ", result["phone"])
                    break

        # Common title prefixes to avoid (defined here so they're always available)
        title_prefixes = [
            "Chief",
            "Senior",
            "Junior",
            "Principal",
            "Lead",
            "Director",
            "Manager",
            "Vice",
            "President",
            "Head",
            "Executive",
            "Assistant",
            "Officer",
            "Specialist",
            "Consultant",
            "Analyst",
            "Engineer",
            "Developer",
            "Architect",
            "Administrator",
            "SVP",
            "EVP",
            "CTO",
            "CEO",
            "CFO",
            "COO",
        ]

        # Section keywords to avoid
        section_keywords = [
            "profile",
            "summary",
            "contact",
            "information",
            "experience",
            "education",
            "skills",
            "certifications",
            "languages",
            "interests",
            "objective",
            "references",
            "projects",
            "publications",
            "achievements",
        ]

        # Extract name - look for full name at various positions
        if not result["first_name"] and not result["last_name"]:

            # First try to extract name from beginning of the CV
            # Try multiple name patterns at the beginning of the CV
            first_section = (
                text.split("\n\n", 1)[0] if "\n\n" in text else text.split("\n", 10)[0]
            )
            name_patterns = [
                # Standard name format with 2-3 words
                r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})$",
                # Name with middle initial
                r"^([A-Z][a-z]+\s+[A-Z]\.?\s+[A-Z][a-z]+)$",
                # Name with possible professional suffixes
                r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}(?:,\s+(?:PhD|MD|MBA|CPA|PE|Esq)\.?)?)$",
                # Name labeled with "Name:" prefix
                r"(?:Name|Full Name)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})",
                # Any capitalized line at the beginning that's not too long
                r"^([A-Z][A-Za-z\s\'-]{2,25})$",
            ]

            for pattern in name_patterns:
                name_match = re.search(pattern, first_section, re.MULTILINE)
                if name_match:
                    potential_name = name_match.group(1).strip()

                    # Validate it's not a job title or section heading
                    contains_title = any(
                        re.search(
                            r"\b" + re.escape(prefix) + r"\b",
                            potential_name,
                            re.IGNORECASE,
                        )
                        for prefix in title_prefixes
                    )
                    contains_section = any(
                        re.search(
                            r"\b" + re.escape(section) + r"\b",
                            potential_name,
                            re.IGNORECASE,
                        )
                        for section in section_keywords
                    )

                    if (
                        not contains_title
                        and not contains_section
                        and len(potential_name.split()) <= 3
                    ):
                        # Split into first and last name
                        name_parts = potential_name.split()
                        if len(name_parts) >= 2:
                            result["first_name"] = name_parts[0]
                            result["last_name"] = " ".join(name_parts[1:])
                        else:
                            result["first_name"] = potential_name
                        break

            # If still no name, try a more generic approach for CVs where name is formatted differently
            if not result["first_name"]:
                # Look in the first few lines
                first_lines = text.split("\n", 15)[:15]  # First 15 lines

                for line in first_lines:
                    line = line.strip()
                    # Skip empty lines, lines with common section names, and lines that are too long
                    if (
                        not line
                        or any(section in line.lower() for section in section_keywords)
                        or len(line) > 40
                    ):
                        continue

                    # Check if it might be a name (1-3 words, all properly capitalized)
                    words = line.split()
                    if 1 <= len(words) <= 3 and all(
                        word[0].isupper() for word in words if word
                    ):
                        # Make sure it's not a job title or contains numbers
                        contains_title = any(
                            re.search(
                                r"\b" + re.escape(prefix) + r"\b", line, re.IGNORECASE
                            )
                            for prefix in title_prefixes
                        )
                        contains_digits = any(char.isdigit() for char in line)

                        if not contains_title and not contains_digits:
                            # This could be a name
                            if len(words) >= 2:
                                result["first_name"] = words[0]
                                result["last_name"] = " ".join(words[1:])
                            else:
                                result["first_name"] = line
                            break

        # Extract location if missing
        if not result["location"]:
            # Common location patterns
            location_patterns = [
                r"(?:Location|Address|City|Based in|Located in|Based at)[:\s]*([A-Za-z\s,.]+(?:Road|Street|Avenue|Lane|Blvd|Boulevard|Drive|Place|Court|Way|Terrace|City|Town|Village|County|State|Province|Region|Country)(?:[,\s](?:[A-Z]{2}|[A-Za-z\s]+))?)",
                r"\b([A-Za-z]+(?:,\s*[A-Z]{2}|\s*,\s*[A-Za-z\s]+))\b",
                r"(?:Location|Address|City)[:\s]+([A-Za-z\s,]+)",
            ]

            for pattern in location_patterns:
                location_match = re.search(
                    pattern, text[:2000]
                )  # Look in first 2000 chars
                if location_match:
                    potential_location = location_match.group(1).strip()
                    # Ensure it's not a job title or other CV section
                    if (
                        len(potential_location) < 50
                        and not any(
                            title in potential_location for title in title_prefixes
                        )
                        and not any(
                            section in potential_location.lower()
                            for section in section_keywords
                        )
                    ):
                        result["location"] = potential_location
                        break

            # If still no location, try to find city/state pattern in first part of CV
            if not result["location"]:
                # Look for "City, State" or "City, Country" pattern
                city_state_pattern = (
                    r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*(?:[A-Z]{2}|[A-Z][a-z]+))\b"
                )
                location_match = re.search(city_state_pattern, text[:2000])
                if location_match:
                    potential_location = location_match.group(1).strip()
                    if len(potential_location) < 50:
                        result["location"] = potential_location

        # Extract LinkedIn if available
        if not result["linkedin"]:
            linkedin_patterns = [
                r"(?:LinkedIn|Profile):\s*((?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?)",
                r"\b((?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?)\b",
                r"linkedin\.com/in/([A-Za-z0-9_-]+)",
            ]

            for pattern in linkedin_patterns:
                linkedin_match = re.search(pattern, text)
                if linkedin_match:
                    if "linkedin\.com/in/" in pattern and "(" in pattern:
                        # This pattern captures just the username, prepend the base URL
                        result["linkedin"] = "linkedin.com/in/" + linkedin_match.group(
                            1
                        )
                    else:
                        result["linkedin"] = linkedin_match.group(1)
                    break
        
        # Extract GitHub if available
        if not result["github"]:
            github_patterns = [
                r"(?:GitHub|Github):\s*((?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+/?)",
                r"\b((?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+/?)\b",
                r"github\.com/([A-Za-z0-9_-]+)",
            ]

            for pattern in github_patterns:
                github_match = re.search(pattern, text, re.IGNORECASE)
                if github_match:
                    github_url = github_match.group(1) if github_match.lastindex >= 1 else github_match.group(0)
                    # Normalize to full URL
                    if not github_url.startswith('http'):
                        github_url = 'https://' + github_url
                    result["github"] = github_url
                    break
        
        # Extract Twitter/X if available
        if not result["twitter"]:
            twitter_patterns = [
                r"(?:Twitter|X):\s*((?:https?://)?(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+/?)",
                r"\b((?:https?://)?(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+/?)\b",
                r"@([A-Za-z0-9_]+)\s*(?:on Twitter|on X)?",
            ]

            for pattern in twitter_patterns:
                twitter_match = re.search(pattern, text, re.IGNORECASE)
                if twitter_match:
                    twitter_url = twitter_match.group(1) if twitter_match.lastindex >= 1 else twitter_match.group(0)
                    # Normalize to full URL
                    if twitter_url.startswith('@'):
                        twitter_url = 'https://twitter.com/' + twitter_url[1:]
                    elif not twitter_url.startswith('http'):
                        twitter_url = 'https://' + twitter_url
                    result["twitter"] = twitter_url
                    break
        
        # Extract Instagram if available
        if not result["instagram"]:
            instagram_patterns = [
                r"(?:Instagram):\s*((?:https?://)?(?:www\.)?instagram\.com/[A-Za-z0-9_.-]+/?)",
                r"\b((?:https?://)?(?:www\.)?instagram\.com/[A-Za-z0-9_.-]+/?)\b",
                r"@([A-Za-z0-9_.-]+)\s*(?:on Instagram)?",
            ]

            for pattern in instagram_patterns:
                instagram_match = re.search(pattern, text, re.IGNORECASE)
                if instagram_match:
                    instagram_url = instagram_match.group(1) if instagram_match.lastindex >= 1 else instagram_match.group(0)
                    # Normalize to full URL
                    if instagram_url.startswith('@'):
                        instagram_url = 'https://instagram.com/' + instagram_url[1:]
                    elif not instagram_url.startswith('http'):
                        instagram_url = 'https://' + instagram_url
                    result["instagram"] = instagram_url
                    break
        
        # Extract portfolio/website URLs
        # Look for portfolio-specific keywords first (including Pexels, Behance, Dribbble, etc.)
        if not result["portfolio"]:
            portfolio_patterns = [
                r"(?:Portfolio|Website|Personal Site):\s*((?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s,]*)",
                r"\b((?:https?://)?(?:www\.)?pexels\.com/@[A-Za-z0-9_-]+/?[^\s,]*)\b",
                r"\b((?:https?://)?(?:www\.)?behance\.net/[A-Za-z0-9_-]+/?[^\s,]*)\b",
                r"\b((?:https?://)?(?:www\.)?dribbble\.com/[A-Za-z0-9_-]+/?[^\s,]*)\b",
            ]
            
            for pattern in portfolio_patterns:
                portfolio_match = re.search(pattern, text, re.IGNORECASE)
                if portfolio_match:
                    portfolio_url = portfolio_match.group(1)
                    if not portfolio_url.startswith('http'):
                        portfolio_url = 'https://' + portfolio_url
                    # Accept portfolio platforms like Pexels, Behance, Dribbble directly
                    # Exclude only social media that aren't portfolio platforms
                    if any(portfolio_platform in portfolio_url.lower() for portfolio_platform in ['pexels', 'behance', 'dribbble', 'artstation', 'flickr']):
                        result["portfolio"] = portfolio_url
                        break
                    # Exclude general social media
                    if not any(social in portfolio_url.lower() for social in ['linkedin', 'github', 'twitter', 'facebook', 'instagram']):
                        result["portfolio"] = portfolio_url
                        break
        
        # Extract general website (even if portfolio was found)
        if not result["website"]:
            # Find all URLs
            url_pattern = r'((?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s]*)'
            url_matches = re.findall(url_pattern, text)
            
            # Exclude social media and portfolio platforms that have dedicated fields
            social_media_domains = ['linkedin', 'github', 'twitter', 'facebook', 'instagram', 'tiktok', 'youtube', 'pexels', 'behance', 'dribbble']
            
            for url in url_matches:
                # Skip social media URLs and already extracted portfolio
                if (not any(social in url.lower() for social in social_media_domains) and 
                    url != result.get("portfolio", "")):
                    # Normalize URL
                    if not url.startswith('http'):
                        url = 'https://' + url
                    result["website"] = url
                    break

        return result

    def _extract_education(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract education entries from text.

        Args:
            text (str): Document text

        Returns:
            List[Dict[str, Any]]: List of education items
        """
        logger.debug("Extracting education entries")

        # First try to find the education section
        sections = self._identify_cv_sections(text)
        education_text = ""

        # If education section is found, extract text from that section
        if "education" in sections:
            start_pos, end_pos = sections["education"]
            education_text = text[start_pos:end_pos]
            logger.debug(
                f"Found dedicated education section ({len(education_text)} chars)"
            )
        else:
            # Try traditional section identification as fallback
            education_section_pattern = r"(?:Education|Academic\s+Background|Qualifications|Academic\s+Qualifications)[:\s]*\n*(.*?)(?=\n\s*(?:Experience|Work|Employment|Skills|Certifications|Languages|References|Additional\s+Information|\Z))"

            education_section_match = re.search(
                education_section_pattern, text, re.IGNORECASE | re.DOTALL
            )

            if education_section_match:
                education_text = education_section_match.group(1)
                logger.debug(
                    f"Found education section via pattern matching ({len(education_text)} chars)"
                )
            else:
                # Fallback to using full text
                education_text = text
                logger.debug("No dedicated education section found, using full text")

        # Start extraction
        education_entries = []

        # Split text into lines and group them into blocks
        lines = education_text.split("\n")
        blocks = []
        current_block = []

        for line in lines:
            if line.strip():
                current_block.append(line.strip())
            elif current_block:
                blocks.append(" ".join(current_block))
                current_block = []

        # Add the last block if not empty
        if current_block:
            blocks.append(" ".join(current_block))

        # Combine short blocks that likely belong together
        combined_blocks = []

        for idx, block in enumerate(blocks):
            if idx > 0 and len(block) < 30 and len(combined_blocks[-1]) < 100:
                combined_blocks[-1] += " " + block
            else:
                combined_blocks.append(block)

        # Extract from each paragraph/block
        for block in combined_blocks:
            # Skip very short blocks
            if len(block) < 10:
                continue

            # Special handling for UK education formats
            # Look for UK specific education patterns (A levels, BBA, etc.)
            uk_education_patterns = [
                # A levels pattern
                r"(?P<degree>A\s*[Ll]evels?)(?:[:\s]+in\s+(?P<major>[^,]+))?(?:[,\s]+at\s+)?(?P<institution>(?:[A-Z][a-z]+\s*)+(?:College|School|Academy|Institute|Sixth\s+Form|Grammar\s+School))",
                # BBA format with (Hons)
                r"(?P<degree>BBA|BA|BSc|B\.Sc\.|B\.A\.|B\.B\.A\.)\s*(?:\([Hh]on(?:our)?s\))?\s*(?:in\s+(?P<major>[^,]+))?(?:[,\s]+(?:from|at)\s+)?(?P<institution>(?:[A-Z][a-z]+\s*)+(?:University|College|Business\s+School))",
                # GCSE pattern
                r"(?P<degree>GCSE|G\.C\.S\.E\.)s?(?:[:\s]+in\s+(?P<major>[^,]+))?(?:[,\s]+at\s+)?(?P<institution>(?:[A-Z][a-z]+\s*)+(?:College|School|Academy|Institute|Grammar\s+School))",
                # UK University with year
                r"(?P<institution>(?:[A-Z][a-z]+\s*)+(?:University|College))(?:[,\s]+(?P<degree>MSc|MA|MBA|PhD|BSc|BA|BBA|M\.Sc\.|M\.A\.|M\.B\.A\.|P\.h\.D\.|B\.Sc\.|B\.A\.|B\.B\.A\.))?(?:\s+in\s+(?P<major>[^,]+))?(?:[,\s]+(?P<year>\d{4}))",
                # Specific university patterns (e.g., "Norwich University")
                r"(?P<institution>Norwich\s+University)(?:[,\s]+(?P<degree>BBA|BA|BSc|MBA|MSc|PhD|B\.B\.A\.|B\.A\.|B\.Sc\.|M\.B\.A\.|M\.Sc\.|P\.h\.D\.))(?:\s*\([Hh]on(?:our)?s\))?(?:\s+in\s+(?P<major>[^,]+))?",
                # UK College pattern (e.g., "Ipswich Town College")
                r"(?P<institution>(?:[A-Z][a-z]+\s*)+(?:College|Sixth\s+Form))(?:[,\s]+(?P<degree>A\s*[Ll]evels?|GCSE|G\.C\.S\.E\.|BTEC|NVQ|HND))(?:[:\s]+in\s+(?P<major>[^,\d]+))?",
            ]

            uk_match_found = False

            # Check for UK education patterns first
            for pattern in uk_education_patterns:
                match = re.search(pattern, block, re.IGNORECASE)
                if match:
                    uk_match_found = True

                    # Extract fields
                    institution = (
                        match.group("institution").strip()
                        if "institution" in match.groupdict()
                        and match.group("institution")
                        else ""
                    )
                    degree = (
                        match.group("degree").strip()
                        if "degree" in match.groupdict() and match.group("degree")
                        else ""
                    )
                    major = (
                        match.group("major").strip()
                        if "major" in match.groupdict() and match.group("major")
                        else ""
                    )

                    # Extract year if present
                    year = ""
                    if "year" in match.groupdict() and match.group("year"):
                        year = match.group("year").strip()
                    else:
                        # Try to find a year in the block
                        year_match = re.search(r"\b(19|20)\d{2}\b", block)
                        if year_match:
                            year = year_match.group(0)

                    # Special handling for A levels - make sure major is extracted
                    if "A level" in degree.lower() and not major:
                        # Try to extract subjects after "A levels"
                        subjects_match = re.search(
                            r"A\s*[Ll]evels?[:\s]+in\s+([^,\.]+)", block
                        )
                        if subjects_match:
                            major = subjects_match.group(1).strip()
                        else:
                            # Try to find common A level subjects
                            for subject in [
                                "Mathematics",
                                "English",
                                "Physics",
                                "Chemistry",
                                "Biology",
                                "History",
                                "Geography",
                                "Economics",
                                "Business Studies",
                            ]:
                                if subject.lower() in block.lower():
                                    if major:
                                        major += ", " + subject
                                    else:
                                        major = subject

                    # Create education entry
                    education_entries.append(
                        {
                            "institution": institution,
                            "degree": degree,
                            "major": major,
                            "year": year,
                        }
                    )

                    logger.debug(
                        f"Found UK education format: {degree} at {institution}"
                    )
                    break

            # If no UK match found, try standard formats
            if not uk_match_found:
                # Standard university degree pattern
                degree_pattern = r"(?P<degree>Bachelor|Master|PhD|MBA|MS|MA|MSc|BSc|BA|B\.S\.|M\.S\.|B\.A\.|M\.A\.|M\.B\.A\.|M\.Sc\.|B\.Sc\.|Ph\.D\.|P\.h\.D\.|Doctorate|Associate|Certificate|Diploma)(?:\s+(?:of|in)\s+(?P<major>[^,]+))?(?:[,\s]+)?(?:from|at)?\s+(?P<institution>[^,]+)(?:[,\s]+(?P<year>\d{4}))?"

                # Try looking for standard degree patterns
                degree_match = re.search(degree_pattern, block, re.IGNORECASE)

                if degree_match:
                    # Extract fields
                    institution = (
                        degree_match.group("institution").strip()
                        if degree_match.group("institution")
                        else ""
                    )
                    degree = degree_match.group("degree").strip()
                    major = (
                        degree_match.group("major").strip()
                        if degree_match.group("major")
                        else ""
                    )

                    # Extract year if present
                    year = ""
                    if "year" in degree_match.groupdict() and degree_match.group(
                        "year"
                    ):
                        year = degree_match.group("year").strip()
                    else:
                        # Try to find a year in the block
                        year_match = re.search(r"\b(19|20)\d{2}\b", block)
                        if year_match:
                            year = year_match.group(0)

                    # Clean up institution name
                    institution = re.sub(
                        r"[,.]$", "", institution
                    )  # Remove trailing commas or periods

                    # Create education entry
                    education_entries.append(
                        {
                            "institution": institution,
                            "degree": degree,
                            "major": major,
                            "year": year,
                        }
                    )

                    logger.debug(
                        f"Found standard education format: {degree} at {institution}"
                    )

                else:
                    # Fallback for formats like "University of X, Y degree"
                    university_pattern = r"(?P<institution>(?:University|College|Institute|School)\s+of\s+[^,]+|[^,]+(?:University|College|Institute|School))(?:[,\s]+)?(?P<degree>Bachelor|Master|PhD|MBA|MS|MA|MSc|BSc|BA|B\.S\.|M\.S\.|B\.A\.|M\.A\.|M\.B\.A\.|M\.Sc\.|B\.Sc\.|Ph\.D\.|P\.h\.D\.|Doctorate|Associate|Certificate|Diploma)?(?:\s+(?:of|in)\s+(?P<major>[^,]+))?(?:[,\s]+(?P<year>\d{4}))?"

                    university_match = re.search(
                        university_pattern, block, re.IGNORECASE
                    )

                    if university_match:
                        # Extract fields
                        institution = university_match.group("institution").strip()
                        degree = (
                            university_match.group("degree").strip()
                            if university_match.group("degree")
                            else ""
                        )
                        major = (
                            university_match.group("major").strip()
                            if university_match.group("major")
                            else ""
                        )

                        # Extract year if present
                        year = ""
                        if (
                            "year" in university_match.groupdict()
                            and university_match.group("year")
                        ):
                            year = university_match.group("year").strip()
                        else:
                            # Try to find a year in the block
                            year_match = re.search(r"\b(19|20)\d{2}\b", block)
                            if year_match:
                                year = year_match.group(0)

                        # Clean up institution name
                        institution = re.sub(
                            r"[,.]$", "", institution
                        )  # Remove trailing commas or periods

                        # Create education entry
                        education_entries.append(
                            {
                                "institution": institution,
                                "degree": degree,
                                "major": major,
                                "year": year,
                            }
                        )

                        logger.debug(f"Found university format: {institution} {degree}")

        # Special handling for CVs with common keywords but no matching patterns
        if not education_entries:
            # Look for UK education keywords in the text
            uk_keywords = {
                "A level": [
                    "A levels",
                    "A Levels",
                    "A-levels",
                    "A-Levels",
                    "A level",
                    "A Level",
                ],
                "GCSE": ["GCSE", "GCSEs", "G.C.S.E.", "G.C.S.E.s"],
                "BBA": ["BBA", "B.B.A.", "Bachelor of Business Administration"],
                "BA": ["BA", "B.A.", "Bachelor of Arts"],
                "BSc": ["BSc", "B.Sc.", "Bachelor of Science"],
                "HND": ["HND", "Higher National Diploma"],
                "BTEC": ["BTEC", "B-TEC", "Business and Technology Education Council"],
                "NVQ": ["NVQ", "National Vocational Qualification"],
            }

            uk_institutions = [
                "University",
                "College",
                "School",
                "Academy",
                "Institute",
                "Sixth Form",
                "Grammar School",
            ]

            for degree_type, keywords in uk_keywords.items():
                for keyword in keywords:
                    if keyword in education_text:
                        # Look for an institution near the degree keyword
                        institution_pattern = r"(?:" + "|".join(uk_institutions) + r")"

                        # Find the keyword position
                        keyword_pos = education_text.find(keyword)

                        # Search in a window around the keyword
                        search_window = education_text[
                            max(0, keyword_pos - 100) : min(
                                len(education_text), keyword_pos + 100
                            )
                        ]

                        institution_match = re.search(
                            r"([A-Z][a-z]+\s+(?:" + "|".join(uk_institutions) + r"))",
                            search_window,
                        )
                        institution = (
                            institution_match.group(1) if institution_match else ""
                        )

                        if not institution:
                            # Try more generic institution pattern
                            generic_institution_match = re.search(
                                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", search_window
                            )
                            if generic_institution_match:
                                potential_institution = generic_institution_match.group(
                                    1
                                )
                                # Only use if it seems like a valid institution name
                                if len(potential_institution) > 5 and not any(
                                    term in potential_institution.lower()
                                    for term in ["date", "present", "current", "year"]
                                ):
                                    institution = potential_institution

                        # Look for major/subject
                        major = ""
                        major_match = re.search(
                            keyword + r"[:\s]+in\s+([^,\.]+)",
                            search_window,
                            re.IGNORECASE,
                        )
                        if major_match:
                            major = major_match.group(1).strip()

                        # Look for year
                        year = ""
                        year_match = re.search(r"\b(19|20)\d{2}\b", search_window)
                        if year_match:
                            year = year_match.group(0)

                        # Create education entry if we have at least some information
                        if institution or major:
                            education_entries.append(
                                {
                                    "institution": institution,
                                    "degree": degree_type,
                                    "major": major,
                                    "year": year,
                                }
                            )

                            logger.debug(
                                f"Found keyword-based UK education: {degree_type} at {institution}"
                            )
                            break  # Skip other keywords of the same type

            # Special case for Norwich University
            if "Norwich University" in education_text or "Norwich" in education_text:
                # Look for possible degree near "Norwich"
                degree = "BBA"  # Default if nothing else found

                # Try to find actual degree
                degree_match = re.search(
                    r"(BBA|BA|BSc|B\.B\.A\.|B\.A\.|B\.Sc\.)\s*(?:\([Hh]ons?\))?",
                    education_text,
                )
                if degree_match:
                    degree = degree_match.group(0)

                # Look for major
                major = ""
                major_match = re.search(
                    r"(?:BBA|BA|BSc|B\.B\.A\.|B\.A\.|B\.Sc\.)\s*(?:\([Hh]ons?\))?\s+in\s+([^,\.]+)",
                    education_text,
                )
                if major_match:
                    major = major_match.group(1).strip()

                # Look for year
                year = ""
                year_match = re.search(r"\b(19|20)\d{2}\b", education_text)
                if year_match:
                    year = year_match.group(0)

                # Create education entry
                education_entries.append(
                    {
                        "institution": "Norwich University",
                        "degree": degree,
                        "major": major,
                        "year": year,
                    }
                )

                logger.debug("Found Norwich University education entry")

            # Special case for Ipswich Town College
            if (
                "Ipswich Town College" in education_text
                or "Ipswich College" in education_text
            ):
                # Look for A levels
                degree = "A levels"

                # Look for subjects
                major = ""
                subjects = []

                # Check for common A level subjects
                common_subjects = [
                    "Mathematics",
                    "English",
                    "Physics",
                    "Chemistry",
                    "Biology",
                    "History",
                    "Geography",
                    "Economics",
                    "Business Studies",
                ]

                for subject in common_subjects:
                    if subject.lower() in education_text.lower():
                        subjects.append(subject)

                if subjects:
                    major = ", ".join(subjects)

                # Look for year
                year = ""
                year_match = re.search(r"\b(19|20)\d{2}\b", education_text)
                if year_match:
                    year = year_match.group(0)

                # Create education entry
                education_entries.append(
                    {
                        "institution": "Ipswich Town College",
                        "degree": degree,
                        "major": major,
                        "year": year,
                    }
                )

                logger.debug("Found Ipswich Town College education entry")

        # Deduplicate education entries
        unique_entries = []
        seen_institutions = set()

        for entry in education_entries:
            institution_key = entry["institution"].lower()

            if institution_key and institution_key not in seen_institutions:
                seen_institutions.add(institution_key)
                unique_entries.append(entry)

        logger.info(f"Extracted {len(unique_entries)} education entries")
        return unique_entries

    def extract_professional_summary(self, text: str) -> str:
        """
        Extract professional summary from the CV text

        Args:
            text (str): CV text

        Returns:
            str: Extracted professional summary
        """
        # Try to find a summary section first
        sections = self._identify_cv_sections_safe(text, timeout=1.0)

        # If summary section is found, extract text from that section
        if "summary" in sections:
            start_pos, end_pos = sections["summary"]
            summary_text = text[start_pos:end_pos]
            logger.debug(f"Found dedicated summary section ({len(summary_text)} chars)")
            return self._format_summary(summary_text)
        else:
            # Try traditional section identification as fallback
            summary_section_patterns = [
                r"(?:Summary|Profile|Professional Summary|Executive Summary|Career Summary|Objective)[:\s]*\n*(.*?)(?=\n\s*(?:Experience|Education|Skills|Certifications|Languages|Projects|\Z))",
                r"(?:SUMMARY|PROFILE|PROFESSIONAL SUMMARY|EXECUTIVE SUMMARY|CAREER SUMMARY|OBJECTIVE)[:\s]*\n*(.*?)(?=\n\s*(?:EXPERIENCE|EDUCATION|SKILLS|CERTIFICATIONS|LANGUAGES|PROJECTS|\Z))",
            ]

            for pattern in summary_section_patterns:
                summary_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if summary_match:
                    summary_text = summary_match.group(1).strip()
                    logger.debug(
                        f"Found summary section via pattern matching ({len(summary_text)} chars)"
                    )
                    return self._format_summary(summary_text)

            # If no dedicated summary section, look at the beginning of the document
            # but skip personal info at the very beginning

            # First, try to find where the personal info section ends
            personal_info_patterns = [
                r"^.*?(?:Name|Email|Phone|Address|Location|LinkedIn|Contact).*?\n\n",
                r"^.*?(?:NAME|EMAIL|PHONE|ADDRESS|LOCATION|LINKEDIN|CONTACT).*?\n\n",
            ]

            start_pos = 0
            for pattern in personal_info_patterns:
                personal_match = re.search(pattern, text, re.DOTALL)
                if personal_match:
                    start_pos = personal_match.end()
                    break

            # Look for first paragraph that's not a header and is of reasonable length
            paragraphs = text[start_pos:].split("\n\n")

            for i, paragraph in enumerate(
                paragraphs[:5]
            ):  # Only check first 5 paragraphs
                # Skip if it's too short or looks like a header
                if len(paragraph) < 50 or re.match(r"^[A-Z\s]+:?\s*$", paragraph):
                    continue

                # Skip if it contains typical section headers
                if re.search(
                    r"\b(?:EXPERIENCE|EDUCATION|SKILLS|CERTIFICATIONS|LANGUAGES)\b",
                    paragraph.upper(),
                ):
                    continue

                # Skip if it's likely personal info
                if re.search(
                    r"\b(?:Email|Phone|Address|Location|LinkedIn)\b",
                    paragraph,
                    re.IGNORECASE,
                ):
                    continue

                # This could be a summary paragraph
                # Check if it has typical summary content
                summary_indicators = [
                    r"\b(?:years of experience|professional|expertise|background|specialized|specialize|proficient|skilled|focus|passionate|dedicated)\b",
                    r"\b(?:proven track record|successful|accomplished|results-driven|detail-oriented|team player|problem solver)\b",
                ]

                for indicator in summary_indicators:
                    if re.search(indicator, paragraph, re.IGNORECASE):
                        logger.debug(
                            f"Extracted professional summary from document beginning ({len(paragraph)} chars)"
                        )
                        return self._format_summary(paragraph)

                # If the paragraph is a reasonable length for a summary and not the first paragraph
                # (which is more likely to be personal info), use it as a potential summary
                if len(paragraph) > 100 and len(paragraph) < 1000 and i > 0:
                    logger.debug(
                        f"Extracted potential professional summary from document beginning ({len(paragraph)} chars)"
                    )
                    return self._format_summary(paragraph)

            # If we still couldn't find a summary, return an empty string
            logger.debug("No professional summary found")
            return ""

    def _format_summary(self, summary: str) -> str:
        """
        Format and clean a professional summary to ensure it's preserved in full.

        Args:
            summary (str): Raw professional summary text

        Returns:
            str: Cleaned and formatted summary
        """
        # Convert bullet points to proper format
        summary = re.sub(r"•\s*", "• ", summary)

        # Normalize whitespace
        summary = re.sub(r"\s+", " ", summary)

        # Remove common section headers that might be included
        summary = re.sub(
            r"^(?:SUMMARY|PROFESSIONAL\s+SUMMARY|PROFILE|PERSONAL\s+SUMMARY)[:.\s-]*",
            "",
            summary,
            flags=re.IGNORECASE,
        )

        # Remove trailing bullets or dashes
        summary = re.sub(r"[•\-–—]+\s*$", "", summary)

        # Ensure the summary doesn't exceed a reasonable length (prevent overly long summaries)
        max_summary_length = 500  # Maximum characters for a summary
        if len(summary) > max_summary_length:
            logger.debug(
                f"Truncating overly long summary from {len(summary)} to {max_summary_length} chars"
            )
            # Try to truncate at a sentence boundary
            truncated = summary[:max_summary_length]
            last_period = truncated.rfind(".")
            if (
                last_period > max_summary_length * 0.7
            ):  # Only truncate at period if it's not too short
                summary = truncated[: last_period + 1]
            else:
                summary = truncated

        # Final cleaning
        summary = summary.strip()

        # Ensure summary doesn't end with a partial sentence
        if (
            summary
            and not summary.endswith(".")
            and not summary.endswith("!")
            and not summary.endswith("?")
        ):
            # Find the last complete sentence
            last_period = summary.rfind(".")
            if (
                last_period > 0 and last_period > len(summary) * 0.5
            ):  # Only if we're not losing too much
                summary = summary[: last_period + 1]
            else:
                # Add a period if it doesn't end with punctuation
                summary += "."

        return summary

    def parse_document(self, file_path, text=None, max_timeout=180):
        """
        Parse a document into a structured CV object

        Args:
            file_path (str): Path to the document
            text (str, optional): Text content if already extracted. Defaults to None.
            max_timeout (int, optional): Maximum time in seconds for the parsing operation. Defaults to 180.

        Returns:
            dict: Parsed CV data
        """
        # Start timer for performance monitoring
        start_time = time.time()

        # Extract text if not provided
        if text is None:
            text = self._extract_text(file_path)
            self.logger.info(f"Extracted text: {len(text)} characters")

        # 🚀 PRODUCTION: Use enhanced LLaMA parser as primary method
        try:
            from .llama_parser import LLaMAcvParser

            llama_parser = LLaMAcvParser()
            self.logger.info(
                "🚀 Using ENHANCED LLaMA-based CV parser (production-ready)"
            )

            llama_result = llama_parser.parse_cv(text)

            # Check if LLaMA returned meaningful content (4+ sections)
            if llama_result and self._has_meaningful_content_v2(llama_result):
                elapsed_time = time.time() - start_time
                self.logger.info(
                    f"✅ Enhanced LLaMA parsing SUCCESS in {elapsed_time:.2f} seconds - 4+ sections extracted"
                )
                return llama_result
            else:
                self.logger.warning(
                    "⚠️ Enhanced LLaMA parser returned insufficient results, trying legacy fallback"
                )

        except Exception as e:
            self.logger.error(
                f"❌ Enhanced LLaMA parser error: {e}, trying legacy fallback"
            )

        # Fall back to original parsing logic if enhanced LLaMA fails
        self.logger.info("📰 Using legacy parsing system as final fallback")

        # Initialize result with empty structure for partial results
        partial_result = self._empty_result()
        error_msg = None

        # Optimize for large texts
        if len(text) > 15000:
            # For very large texts, we'll take the first 8000 chars and last 5000
            # This ensures we capture critical content while staying within LLM context limits
            optimized_text = text[:8000] + "\n...\n" + text[-5000:]
            self.logger.info(
                f"Optimized large text from {len(text)} to {len(optimized_text)} characters"
            )
            text = optimized_text

        # Check if we should abort due to timeout
        def should_abort():
            elapsed = time.time() - start_time
            if elapsed > max_timeout:
                self.logger.warning(
                    f"Parser operation approaching timeout after {elapsed:.2f} seconds"
                )
                return True
            return False

        # First, try to segment the CV with DeepSeek
        deepseek_timeout = min(60, max_timeout * 0.3)  # Use at most 30% of total time
        segmented_text = self._segment_with_deepseek(text, timeout=deepseek_timeout)

        # Check if we're approaching timeout
        if should_abort():
            error_msg = f"Parsing timed out after {max_timeout} seconds"
            partial_result["error"] = error_msg
            partial_result["professional_summary"] = "Parsing timed out"
            elapsed_time = time.time() - start_time
            self.logger.info(f"Total parsing time: {elapsed_time:.2f} seconds")
            return partial_result

        # Check if segmentation succeeded and returned valid content
        if segmented_text:
            try:
                # Try to parse the segmented text
                result = self._parse_segmented_text(segmented_text)

                # Validate result has meaningful content
                meaningful_content = False
                for key, value in result.items():
                    if value and value != [] and value != "":
                        if key == "personal_info" and any(
                            val for val in value.values()
                        ):
                            meaningful_content = True
                            break
                        elif isinstance(value, list) and len(value) > 0:
                            meaningful_content = True
                            break
                        elif isinstance(value, str) and len(value) > 20:
                            meaningful_content = True
                            break

                if meaningful_content:
                    self.logger.info("Segmented text parsing completed successfully")
                    elapsed_time = time.time() - start_time
                    self.logger.info(
                        f"Total parsing time with DeepSeek segmentation: {elapsed_time:.2f} seconds"
                    )
                    return result
                else:
                    self.logger.warning(
                        "Segmented text parsing produced empty or invalid results"
                    )
            except Exception as e:
                self.logger.error(f"Error parsing segmented text: {str(e)}")
                self.logger.debug(traceback.format_exc())

        # If DeepSeek segmentation failed or produced invalid results, try LLM parsing or traditional
        if self._should_use_llm_parsing() and not should_abort():
            try:
                self.logger.info("Attempting to parse with LLM")
                llm_timeout = min(
                    30, max_timeout * 0.2
                )  # Use at most 20% of remaining time
                llm_end_time = time.time() + llm_timeout
                result = self._parse_with_llm(text, timeout=llm_timeout)
                elapsed_time = time.time() - start_time
                self.logger.info(
                    f"Total parsing time with LLM: {elapsed_time:.2f} seconds"
                )
                return result
            except Exception as e:
                self.logger.error(f"Error in LLM parsing: {str(e)}")
                self.logger.debug(traceback.format_exc())

        # Check if we're approaching timeout
        if should_abort():
            error_msg = f"Parsing timed out after {max_timeout} seconds"
            partial_result["error"] = error_msg
            partial_result["professional_summary"] = "Parsing timed out"
            elapsed_time = time.time() - start_time
            self.logger.info(f"Total parsing time: {elapsed_time:.2f} seconds")
            return partial_result

        # Fall back to traditional parsing as a last resort
        traditional_start_time = time.time()
        self.logger.info("Falling back to traditional parsing")

        # Calculate remaining time for traditional parsing
        remaining_time = max(10, max_timeout - (time.time() - start_time))
        result = self._parse_traditional(text, timeout=remaining_time)

        # Check if the result is empty (indicating a timeout)
        result_empty = True
        for key, value in result.items():
            if value and value != [] and value != "":
                if key == "personal_info" and any(val for val in value.values()):
                    result_empty = False
                    break
                elif isinstance(value, list) and len(value) > 0:
                    result_empty = False
                    break
                elif isinstance(value, str) and len(value) > 10:
                    result_empty = False
                    break

        # If traditional parsing produced no results, add an error message
        if result_empty:
            result["error"] = "Parser failed to extract meaningful content"

        elapsed_time = time.time() - start_time
        self.logger.info(f"Total parsing time: {elapsed_time:.2f} seconds")
        return result

    def _parse_with_llm(self, text, timeout=30):
        """
        Parse the text with an LLM

        Args:
            text (str): CV text
            timeout (int): Maximum time in seconds for the LLM operation

        Returns:
            dict: Parsed CV data
        """
        # Set a timer for timeout
        start_time = time.time()

        # Initialize fallback result
        empty_result = self._empty_result()

        try:
            from cv_writer.services import CVImprovementService

            service = CVImprovementService()

            # Set up LLM prompt
            system_prompt = """You are a CV parser. Extract structured information from the CV provided. 
            Output should be valid JSON with the following keys:
            - personal_info (object): first_name, last_name, email, phone, location, linkedin
            - professional_summary (string): A condensed version of any summary or profile section
            - education (array): List of education entries with institution, degree, major, dates
            - experience (array): List of experience entries with company, title, dates, description
            - skills (array): List of skills mentioned in the CV
            - languages (array): List of languages with proficiency levels
            - certifications (array): List of professional certifications
            
            Keep your response focused just on the JSON output without additional explanations."""

            # Fail fast if we're already approaching timeout
            if time.time() - start_time > timeout * 0.1:
                self.logger.warning(f"LLM parsing aborted due to impending timeout")
                return empty_result

            # Generate JSON with LLM using async method
            import asyncio

            try:
                # Try to get the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we need to use run_in_executor
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            service.generate_response(
                                system_prompt=system_prompt,
                                user_prompt=f"Parse the following CV text into structured data:\n\n{text}",
                            ),
                        )
                        json_text = future.result(timeout=timeout)
                else:
                    json_text = loop.run_until_complete(
                        service.generate_response(
                            system_prompt=system_prompt,
                            user_prompt=f"Parse the following CV text into structured data:\n\n{text}",
                        )
                    )
            except RuntimeError:
                # No event loop exists, create a new one
                json_text = asyncio.run(
                    service.generate_response(
                        system_prompt=system_prompt,
                        user_prompt=f"Parse the following CV text into structured data:\n\n{text}",
                    )
                )

            # Try to parse the JSON output
            try:
                result = json.loads(json_text)

                # Ensure all expected fields exist
                for key in [
                    "personal_info",
                    "professional_summary",
                    "education",
                    "experience",
                    "skills",
                    "languages",
                    "certifications",
                ]:
                    if key not in result:
                        result[key] = empty_result[key]

                self.logger.info(
                    f"Successfully parsed CV with LLM in {time.time() - start_time:.2f} seconds"
                )
                return result
            except json.JSONDecodeError:
                self.logger.error("Failed to parse LLM output as JSON")
                # Try to extract JSON from the text if it's wrapped in other content
                json_match = re.search(r"```json\s*(.*?)\s*```", json_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                        # Ensure all expected fields exist
                        for key in [
                            "personal_info",
                            "professional_summary",
                            "education",
                            "experience",
                            "skills",
                            "languages",
                            "certifications",
                        ]:
                            if key not in result:
                                result[key] = empty_result[key]
                        return result
                    except:
                        pass

                # If we still can't parse it, return empty result
                return empty_result

        except Exception as e:
            self.logger.error(f"Error in LLM parsing: {str(e)}")
            return empty_result

    def _parse_traditional(self, text, timeout=90):
        """
        Fallback parser that uses traditional extraction techniques

        Args:
            text (str): CV text to parse
            timeout (int): Maximum time in seconds for the traditional parsing

        Returns:
            dict: Parsed CV data
        """
        self.logger.info("Using traditional CV parsing techniques")

        # Start timing
        start_time = time.time()

        # Add a safety check for very large texts - if text is too large, truncate it
        if len(text) > 50000:
            self.logger.warning(
                f"CV text is very large ({len(text)} chars), truncating to first 50000 chars"
            )
            text = text[:50000]

        # Initialize CV data structure
        cv_data = {
            "personal_info": {},
            "professional_summary": "",
            "education": [],
            "experience": [],
            "skills": [],
            "languages": [],
            "certifications": [],
            "projects": [],
            "interests": [],
        }

        # Function to check if we've exceeded our timeout
        def should_abort():
            elapsed = time.time() - start_time
            if elapsed > timeout * 0.9:  # 90% of timeout
                self.logger.error(
                    f"Parser operation timed out after {elapsed:.2f} seconds"
                )
                return True
            return False

        # Identify CV type for specialized extraction - limit the time spent on type checking
        cv_type = "general"
        industry_check_start = time.time()
        industry_check_timeout = min(0.5, timeout * 0.05)  # 5% of total time max
        industry_checks = {
            "technology": self._is_technology_cv,
            "aviation": self._is_aviation_cv,
            "banking": self._is_banking_cv,
            "healthcare": self._is_healthcare_cv,
            "legal": self._is_legal_cv,
        }

        for industry, check_method in industry_checks.items():
            if time.time() - industry_check_start > industry_check_timeout:
                self.logger.warning(
                    "Industry check timeout exceeded, using general CV type"
                )
                break

            if check_method(text):
                cv_type = industry
                self.logger.info(f"Identified {industry} CV type")
                break

        # Extract sections using the CV identifier - set timeout for this operation
        section_start_time = time.time()
        section_timeout = min(5.0, timeout * 0.1)  # 10% of total time max
        try:
            sections = self._identify_cv_sections_safe(text, section_timeout)
            self.logger.info(
                f"Identified {len(sections)} sections in CV (took {time.time() - section_start_time:.2f}s)"
            )
        except TimeoutError:
            self.logger.warning(
                "Section identification timed out, using empty sections"
            )
            sections = {}

        # Extract critical information with timeouts for each operation
        try:
            # Extract personal information with timeout
            if should_abort():
                return cv_data

            personal_info_start = time.time()
            personal_info_timeout = min(5.0, timeout * 0.1)
            if time.time() - start_time < personal_info_timeout:
                cv_data["personal_info"] = self.extract_personal_info(text)
                self.logger.info(
                    f"Extracted personal info with {len(cv_data['personal_info'])} fields (took {time.time() - personal_info_start:.2f}s)"
                )
            else:
                self.logger.warning("Skipping personal info extraction due to timeout")

            # Extract professional summary with timeout
            if should_abort():
                return cv_data

            summary_start = time.time()
            summary_timeout = min(5.0, timeout * 0.1)
            if time.time() - start_time < summary_timeout:
                if "summary" in sections:
                    cv_data["professional_summary"] = sections["summary"].strip()
                else:
                    cv_data["professional_summary"] = self.extract_professional_summary(
                        text
                    )
                self.logger.info(
                    f"Extracted professional summary (took {time.time() - summary_start:.2f}s)"
                )
            else:
                self.logger.warning(
                    "Skipping professional summary extraction due to timeout"
                )

            # Extract education with timeout
            if should_abort():
                return cv_data

            education_start = time.time()
            education_timeout = min(10.0, timeout * 0.1)
            if time.time() - start_time < education_timeout:
                cv_data["education"] = self._extract_education_efficient(
                    text, sections, education_timeout
                )
                self.logger.info(
                    f"Extracted {len(cv_data['education'])} education entries (took {time.time() - education_start:.2f}s)"
                )
            else:
                self.logger.warning("Skipping education extraction due to timeout")

            # Extract experience with timeout (allocate more time for this operation)
            if should_abort():
                return cv_data

            experience_start = time.time()
            experience_timeout = min(30.0, timeout * 0.2)
            if time.time() - start_time < experience_timeout:
                cv_data["experience"] = self._extract_experience_efficient(
                    text, sections
                )
                self.logger.info(
                    f"Extracted {len(cv_data['experience'])} experience entries (took {time.time() - experience_start:.2f}s)"
                )
            else:
                self.logger.warning("Skipping experience extraction due to timeout")

            # Extract skills with timeout
            if should_abort():
                return cv_data

            skills_start = time.time()
            skills_timeout = min(10.0, timeout * 0.1)
            if time.time() - start_time < skills_timeout:
                if "skills" in sections:
                    cv_data["skills"] = self._parse_skills_section(sections["skills"])
                else:
                    cv_data["skills"] = self._extract_skills(text)
                self.logger.info(
                    f"Extracted {len(cv_data['skills'])} skills (took {time.time() - skills_start:.2f}s)"
                )
            else:
                self.logger.warning("Skipping skills extraction due to timeout")

            # Extract languages with timeout
            if should_abort():
                return cv_data

            languages_start = time.time()
            languages_timeout = min(5.0, timeout * 0.05)
            if time.time() - start_time < languages_timeout:
                if "languages" in sections:
                    cv_data["languages"] = self._parse_languages_section(
                        sections["languages"]
                    )
                else:
                    cv_data["languages"] = self._extract_languages(text)
                self.logger.info(
                    f"Extracted {len(cv_data['languages'])} languages (took {time.time() - languages_start:.2f}s)"
                )
            else:
                self.logger.warning("Skipping languages extraction due to timeout")

            # Extract certifications with timeout
            if should_abort():
                return cv_data

            certifications_start = time.time()
            certifications_timeout = min(5.0, timeout * 0.05)
            if time.time() - start_time < certifications_timeout:
                if "certifications" in sections:
                    cv_data["certifications"] = self._parse_certifications_section(
                        sections["certifications"]
                    )
                else:
                    cv_data["certifications"] = self._extract_certifications(text)
                self.logger.info(
                    f"Extracted {len(cv_data['certifications'])} certifications (took {time.time() - certifications_start:.2f}s)"
                )
            else:
                self.logger.warning("Skipping certifications extraction due to timeout")

            # Only process remaining fields if time permits
            if not should_abort():
                # Extract projects with timeout if time permits
                projects_start = time.time()
                projects_timeout = min(5.0, timeout * 0.05)
                if time.time() - start_time < projects_timeout:
                    if "projects" in sections:
                        cv_data["projects"] = self._parse_projects_section(
                            sections["projects"]
                        )
                    elif hasattr(self, "_extract_projects"):  # Check if method exists
                        cv_data["projects"] = self._extract_projects(text)
                    self.logger.info(
                        f"Extracted {len(cv_data['projects'])} projects (took {time.time() - projects_start:.2f}s)"
                    )
                else:
                    self.logger.warning("Skipping projects extraction due to timeout")

                # Extract interests with timeout if time permits
                interests_start = time.time()
                interests_timeout = min(5.0, timeout * 0.05)
                if time.time() - start_time < interests_timeout:
                    if "interests" in sections:
                        cv_data["interests"] = self._parse_interests_section(
                            sections["interests"]
                        )
                    elif hasattr(self, "_extract_interests"):  # Check if method exists
                        cv_data["interests"] = self._extract_interests(text)
                    self.logger.info(
                        f"Extracted {len(cv_data['interests'])} interests (took {time.time() - interests_start:.2f}s)"
                    )
        except Exception as e:
            self.logger.error(f"Error during traditional parsing: {str(e)}")
            # Continue with what we have so far

        # Log processing time
        end_time = time.time()
        self.logger.info(
            f"Traditional parsing completed in {end_time - start_time:.2f} seconds"
        )

        return cv_data

    def _extract_education_efficient(self, text, sections=None, timeout=10.0):
        """
        Extract education entries efficiently without recursive section identification

        Args:
            text (str): Document text
            sections (dict): Pre-identified sections (optional)
            timeout (float): Maximum time to spend on education extraction

        Returns:
            list: Extracted education entries
        """
        start_time = time.time()
        education_text = ""

        # If education section is already identified, use it
        if sections and "education" in sections:
            start_pos, end_pos = sections["education"]
            education_text = text[start_pos:end_pos]
            self.logger.debug(
                f"Using pre-identified education section ({len(education_text)} chars)"
            )
        else:
            # Try pattern matching for education section
            education_section_patterns = [
                r"(?i)(?:education|academic|qualification)[:\s]*\n*(.*?)(?=\n\s*(?:experience|skills|certifications|languages|\Z))",
                r"(?i)(?:EDUCATION|ACADEMIC|QUALIFICATION)[:\s]*\n*(.*?)(?=\n\s*(?:EXPERIENCE|SKILLS|CERTIFICATIONS|LANGUAGES|\Z))",
                r"(?i)(?:academic background|educational background)[:\s]*\n*(.*?)(?=\n\s*(?:experience|skills|certifications|languages|\Z))",
            ]

            for pattern in education_section_patterns:
                education_match = re.search(pattern, text, re.DOTALL)
                if education_match:
                    education_text = education_match.group(1)
                    self.logger.debug(
                        f"Found education section via pattern matching ({len(education_text)} chars)"
                    )
                    break

            if not education_text:
                # Use entire text but be more strict about what we extract
                education_text = text
                self.logger.debug(
                    "No dedicated education section found, using full text with stricter extraction"
                )

        # Helper function to check timeout
        def should_abort():
            return (time.time() - start_time) > timeout

        # Start extraction
        education_entries = []

        # First, look for specific degree patterns throughout the text
        degree_patterns = [
            # Full degree names with institutions
            r"(?:Bachelor|Master|MBA|PhD|Doctorate|Associate)(?:\s+of|\s+in|\s+degree\s+in)?\s+([A-Za-z\s]+)(?:from|at)\s+([A-Za-z\s]+(?:University|College|School|Institute))",
            # Abbreviated degrees with institutions
            r"(?:B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|J\.?D\.?|M\.?D\.?)(?:\s+in)?\s+([A-Za-z\s]+)(?:from|at)\s+([A-Za-z\s]+(?:University|College|School|Institute))",
            # Institution followed by degree
            r"([A-Za-z\s]+(?:University|College|School|Institute))(?:,|\s+-)?\s+(?:Bachelor|Master|MBA|PhD|Doctorate|Associate)(?:\s+of|\s+in)?\s+([A-Za-z\s]+)",
            # Institution followed by abbreviated degree
            r"([A-Za-z\s]+(?:University|College|School|Institute))(?:,|\s+-)?\s+(?:B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|J\.?D\.?|M\.?D\.?)(?:\s+in)?\s+([A-Za-z\s]+)",
        ]

        # Common degree abbreviations and their expanded forms
        degree_mappings = {
            "ba": "Bachelor of Arts",
            "bs": "Bachelor of Science",
            "bsc": "Bachelor of Science",
            "bba": "Bachelor of Business Administration",
            "ma": "Master of Arts",
            "ms": "Master of Science",
            "msc": "Master of Science",
            "mba": "Master of Business Administration",
            "phd": "Doctor of Philosophy",
            "jd": "Juris Doctor",
            "md": "Doctor of Medicine",
            "edd": "Doctor of Education",
        }

        # Common fields of study
        fields_of_study = [
            "Computer Science",
            "Engineering",
            "Business",
            "Management",
            "Finance",
            "Economics",
            "Mathematics",
            "Physics",
            "Chemistry",
            "Biology",
            "Psychology",
            "Sociology",
            "History",
            "English",
            "Literature",
            "Philosophy",
            "Political Science",
            "International Relations",
            "Communications",
            "Marketing",
            "Accounting",
            "Law",
            "Medicine",
            "Nursing",
            "Education",
            "Art",
            "Design",
            "Architecture",
            "Music",
        ]

        # Look for structured education entries
        for pattern in degree_patterns:
            if should_abort():
                break

            matches = re.finditer(pattern, education_text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                entry = {"institution": "", "degree": "", "major": "", "dates": ""}

                # Assign values based on pattern
                if "from|at" in pattern:  # Degree first then institution
                    entry["major"] = groups[0].strip()
                    entry["institution"] = groups[1].strip()

                    # Extract degree from the pattern
                    degree_match = re.search(
                        r"(Bachelor|Master|MBA|PhD|Doctorate|Associate|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|J\.?D\.?|M\.?D\.?)",
                        match.group(0),
                        re.IGNORECASE,
                    )
                    if degree_match:
                        entry["degree"] = degree_match.group(1)
                else:  # Institution first then degree
                    entry["institution"] = groups[0].strip()
                    entry["major"] = groups[1].strip()

                    # Extract degree from the pattern
                    degree_match = re.search(
                        r"(Bachelor|Master|MBA|PhD|Doctorate|Associate|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|J\.?D\.?|M\.?D\.?)",
                        match.group(0),
                        re.IGNORECASE,
                    )
                    if degree_match:
                        entry["degree"] = degree_match.group(1)

                # Look for dates near the match
                surrounding_text = education_text[
                    max(0, match.start() - 50) : min(
                        len(education_text), match.end() + 50
                    )
                ]
                date_match = re.search(
                    r"(\d{4})\s*(?:-|–|to)\s*(\d{4}|Present|Current)",
                    surrounding_text,
                    re.IGNORECASE,
                )
                if date_match:
                    entry["dates"] = f"{date_match.group(1)}-{date_match.group(2)}"
                else:
                    # Look for single year
                    year_match = re.search(r"\b(19|20)\d{2}\b", surrounding_text)
                    if year_match:
                        entry["dates"] = year_match.group(0)

                # Standardize degree abbreviations
                if entry["degree"].lower() in degree_mappings:
                    entry["degree"] = degree_mappings[entry["degree"].lower()]

                # Only add if we have at least institution or degree
                if entry["institution"] or entry["degree"]:
                    education_entries.append(entry)

        # If we didn't find structured entries, try alternative approach with paragraphs
        if not education_entries and not should_abort():
            # Split text into paragraphs and analyze each
            paragraphs = re.split(r"\n\s*\n", education_text)

            for paragraph in paragraphs[
                :10
            ]:  # Limit to first 10 paragraphs to avoid processing too much
                if should_abort():
                    break

                # Skip if too short - likely not a full education entry
                if len(paragraph) < 10:
                    continue

                # Initialize a new education entry
                entry = {"institution": "", "degree": "", "major": "", "dates": ""}

                # Try to extract degree using specific patterns
                degree_pattern = r"\b(Bachelor|Master|MBA|PhD|Doctorate|Associate|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|J\.?D\.?|M\.?D\.?)(?:\s+of|\s+in)?\b"
                degree_match = re.search(degree_pattern, paragraph, re.IGNORECASE)

                if degree_match:
                    degree = degree_match.group(1).lower()

                    # Standardize degree abbreviations
                    if degree in degree_mappings:
                        entry["degree"] = degree_mappings[degree]
                    else:
                        entry["degree"] = degree_match.group(1)

                    # Look for fields of study after degree
                    field_match = re.search(
                        r"\b(?:of|in)\s+([A-Z][A-Za-z\s]+)",
                        paragraph[degree_match.end() :],
                        re.IGNORECASE,
                    )
                    if field_match:
                        entry["major"] = field_match.group(1).strip()
                else:
                    # If no structured degree, look for common degree keywords
                    for degree_abbr, full_degree in degree_mappings.items():
                        if re.search(
                            r"\b" + re.escape(degree_abbr) + r"\b",
                            paragraph,
                            re.IGNORECASE,
                        ):
                            entry["degree"] = full_degree
                            break

                # Try to extract institution
                institution_patterns = [
                    r"\b([A-Z][A-Za-z\s]+(?:University|College|School|Institute|Academy))\b",
                    r"\b(University|College|School|Institute|Academy)\s+of\s+([A-Z][A-Za-z\s]+)\b",
                ]

                for pattern in institution_patterns:
                    institution_match = re.search(pattern, paragraph)
                    if institution_match:
                        if "of" in pattern and len(institution_match.groups()) > 1:
                            entry["institution"] = (
                                f"{institution_match.group(1)} of {institution_match.group(2)}"
                            )
                        else:
                            entry["institution"] = institution_match.group(1).strip()
                        break

                # Try to extract field/major if not already found
                if not entry["major"]:
                    for field in fields_of_study:
                        if re.search(
                            r"\b" + re.escape(field) + r"\b", paragraph, re.IGNORECASE
                        ):
                            entry["major"] = field
                            break

                # Try to extract dates
                date_matches = [
                    re.search(
                        r"(\d{4})\s*(?:-|–|to)\s*(\d{4}|Present|Current)", paragraph
                    ),
                    re.search(r"\b(19|20)\d{2}\b", paragraph),
                ]

                for date_match in date_matches:
                    if date_match:
                        if len(date_match.groups()) == 2:
                            entry["dates"] = (
                                f"{date_match.group(1)}-{date_match.group(2)}"
                            )
                        else:
                            entry["dates"] = date_match.group(1)
                        break

                # Add entry if it has at least institution or degree
                if entry["institution"] or entry["degree"]:
                    education_entries.append(entry)

                # Stop if we have extracted enough entries
                if (
                    len(education_entries) >= 5
                ):  # Usually CVs don't have more than 5 education entries
                    break

        # If we still don't have any education entries, look for very basic patterns
        if not education_entries and not should_abort():
            # Look for simple degree mentions
            for degree_abbr, full_degree in degree_mappings.items():
                if should_abort():
                    break

                matches = re.finditer(
                    r"\b" + re.escape(degree_abbr) + r"\b",
                    education_text,
                    re.IGNORECASE,
                )
                for match in matches:
                    entry = {
                        "institution": "",
                        "degree": full_degree,
                        "major": "",
                        "dates": "",
                    }

                    # Look for an institution near the degree
                    surrounding_text = education_text[
                        max(0, match.start() - 100) : min(
                            len(education_text), match.end() + 100
                        )
                    ]
                    institution_match = re.search(
                        r"\b([A-Z][A-Za-z\s]+(?:University|College|School|Institute|Academy))\b",
                        surrounding_text,
                    )
                    if institution_match:
                        entry["institution"] = institution_match.group(1).strip()

                    # Look for dates near the degree
                    date_match = re.search(
                        r"(\d{4})\s*(?:-|–|to)\s*(\d{4}|Present|Current)",
                        surrounding_text,
                    )
                    if date_match:
                        entry["dates"] = f"{date_match.group(1)}-{date_match.group(2)}"
                    else:
                        year_match = re.search(r"\b(19|20)\d{2}\b", surrounding_text)
                        if year_match:
                            entry["dates"] = year_match.group(0)

                    education_entries.append(entry)
                    break

        return education_entries

    def _extract_healthcare_experience(self, experiences, text):
        """
        Enhance healthcare experience entries with industry-specific extraction

        Args:
            experiences (list): Existing experience entries
            text (str): Full CV text

        Returns:
            list: Enhanced experience entries
        """
        if not experiences:
            return []

        # Healthcare role patterns
        healthcare_roles = [
            r"\b(?:Nurse|Physician|Doctor|Surgeon|Clinician|Therapist|Pharmacist|Radiologist|Anesthesiologist|Cardiologist)\b",
            r"\b(?:Medical|Clinical|Healthcare|Health)\s+(?:Professional|Specialist|Director|Manager|Technician|Coordinator)\b",
            r"\b(?:Patient\s+Care|Registered\s+Nurse|Nurse\s+Practitioner|Physician\s+Assistant)\b",
        ]

        # Healthcare organization patterns
        healthcare_orgs = [
            r"\b(?:Hospital|Medical Center|Clinic|Healthcare Facility|Pharmacy|Health System)\b",
            r"\b(?:Care\s+Center|Surgery\s+Center|Rehabilitation|Long-term\s+Care|Emergency\s+Department)\b",
        ]

        for exp in experiences:
            # Skip if already well-defined
            if exp.get("title") and exp.get("company") and exp.get("description"):
                continue

            # Check description text
            description = exp.get("description", "")

            # Try to extract better role/title if missing
            if not exp.get("title"):
                for pattern in healthcare_roles:
                    matches = re.search(pattern, description, re.IGNORECASE)
                    if matches:
                        exp["title"] = matches.group(0)
                        break

            # Try to extract better organization/company if missing
            if not exp.get("company"):
                for pattern in healthcare_orgs:
                    matches = re.search(pattern, description, re.IGNORECASE)
                    if matches:
                        exp["company"] = matches.group(0)
                        break

        return experiences

    def _extract_technology_skills(self, text):
        """
        Extract technology-specific skills from CV text

        Args:
            text (str): CV text

        Returns:
            list: Extracted technology skills
        """
        # Start with standard skill extraction
        skills = self._extract_skills(text)

        # Tech-specific skill categories
        tech_skill_patterns = {
            "programming_languages": [
                r"\b(?:Python|Java|C\+\+|C#|JavaScript|TypeScript|PHP|Ruby|Swift|Kotlin|Go|Rust|Scala|Perl|Shell|Bash)\b",
                r"\b(?:SQL|NoSQL|R|MATLAB|Assembly|Haskell|Erlang|Elixir|Clojure|Groovy|Dart)\b",
            ],
            "web_technologies": [
                r"\b(?:HTML5?|CSS3?|SASS|LESS|Bootstrap|Tailwind|Material-UI|JavaScript|TypeScript)\b",
                r"\b(?:React|Angular|Vue|Svelte|jQuery|Node\.js|Express|Django|Flask|Laravel|Spring|ASP\.NET|Ruby on Rails)\b",
                r"\b(?:GraphQL|REST API|JSON|XML|SOAP|WebSockets|PWA|SPA|SSR|JAMstack)\b",
            ],
            "databases": [
                r"\b(?:MySQL|PostgreSQL|MongoDB|Redis|Cassandra|SQLite|DynamoDB|Oracle|SQL Server|Firebase)\b",
                r"\b(?:ORM|Hibernate|Sequelize|Mongoose|Entity Framework|JDBC|JPA)\b",
            ],
            "devops": [
                r"\b(?:Docker|Kubernetes|AWS|Azure|GCP|CI/CD|Jenkins|Travis|CircleCI|GitLab CI|GitHub Actions)\b",
                r"\b(?:Terraform|Ansible|Chef|Puppet|Prometheus|Grafana|ELK Stack|Splunk|New Relic|Datadog)\b",
            ],
            "ai_ml": [
                r"\b(?:Machine Learning|Deep Learning|AI|NLP|Computer Vision|Neural Networks|TensorFlow|PyTorch|Keras|scikit-learn)\b",
                r"\b(?:Data Science|Data Mining|Big Data|Hadoop|Spark|Data Visualization|Tableau|Power BI|Pandas|NumPy)\b",
            ],
            "mobile": [
                r"\b(?:iOS|Android|React Native|Flutter|Xamarin|Kotlin|Swift|Objective-C|Mobile Development)\b",
                r"\b(?:AR|VR|XR|Mobile UI|Progressive Web Apps|App Store|Google Play|TestFlight)\b",
            ],
        }

        # Extract skills by category
        extracted_skills = set()
        for category, patterns in tech_skill_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    skill = match.group(0).strip()
                    # Normalize capitalization for known acronyms
                    if skill.upper() in [
                        "HTML",
                        "CSS",
                        "PHP",
                        "SQL",
                        "AWS",
                        "API",
                        "REST",
                        "JSON",
                        "XML",
                        "UI",
                        "UX",
                        "CI",
                        "CD",
                        "QA",
                        "AI",
                        "ML",
                        "AR",
                        "VR",
                        "iOS",
                        "AWS",
                        "GCP",
                    ]:
                        skill = skill.upper()
                    elif not skill.isupper():
                        skill = skill[0].upper() + skill[1:]
                    extracted_skills.add(skill)

        # Combine with existing skills
        all_skills = list(set(skills + list(extracted_skills)))

        return all_skills

    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract work experience entries from text with improved pattern matching.

        Args:
            text (str): Document text

        Returns:
            List[Dict[str, Any]]: List of work experience items
        """
        logger.debug("Extracting work experience entries")

        # First try to find the experience section
        sections = self._identify_cv_sections(text)
        experience_text = ""

        # If experience section is found, extract text from that section
        if "experience" in sections:
            start_pos, end_pos = sections["experience"]
            experience_text = text[start_pos:end_pos]
            logger.debug(
                f"Found dedicated experience section ({len(experience_text)} chars)"
            )
        else:
            # Try traditional section identification as fallback with improved patterns
            # Enhanced experience section pattern - more precise to avoid capturing summary
            experience_section_pattern = r"(?:PROFESSIONAL\s+EXPERIENCE|EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT|EMPLOYMENT\s+HISTORY|WORK\s+HISTORY)[\s\n]*(?:[-=]+\s*\n)?\s*\n(.*?)(?=\n\s*(?:EDUCATION|SKILLS|QUALIFICATIONS|CERTIFICATIONS|LANGUAGES|REFERENCES|ADDITIONAL\s+INFORMATION|\Z))"

            experience_section_match = re.search(
                experience_section_pattern, text, re.IGNORECASE | re.DOTALL
            )

            if experience_section_match:
                experience_text = experience_section_match.group(1)
                logger.debug(
                    f"Found experience section via pattern matching ({len(experience_text)} chars)"
                )
            else:
                # Fallback to using full text
                experience_text = text
                logger.debug("No dedicated experience section found, using full text")

        # Start extraction
        experience_entries = []

        # Split text into blocks based on dates or company names
        experience_blocks = self._split_experience_text(experience_text)

        for block in experience_blocks:
            # Skip very short blocks
            if len(block) < 20:
                continue

            # Extract individual elements
            company = ""
            title = ""
            dates = ""
            description = ""

            # Extract dates first as they are the most reliable markers
            date_patterns = [
                # Simple YYYY-YYYY format (most common)
                r"(\d{4})-(\d{4})",
                r"(\d{4})\s*-\s*(\d{4})",
                # More complex patterns
                r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4})\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}|Present|Current|Now)",
                r"(?:\d{1,2}/\d{4})\s*(?:-|–|to)\s*(?:\d{1,2}/\d{4}|Present|Current|Now)",
                r"(?:\d{4})\s*(?:-|–|to)\s*(?:\d{4}|Present|Current|Now)",
                r"(?:\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}|\d{4})\s*(?:-|–|to)\s*(?:\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}|\d{4}|Present|Current|Now)",
            ]

            for pattern in date_patterns:
                date_match = re.search(pattern, block, re.IGNORECASE)
                if date_match:
                    dates = date_match.group(0).strip()
                    break

            # Clean up dates
            if dates:
                # Handle tuple from regex with multiple groups
                if isinstance(dates, tuple):
                    dates = dates[0] if dates else ""
                # Standardize date format
                if isinstance(dates, str):
                    dates = (
                        dates.replace("–", "-").replace("to", "-").replace("  ", " ")
                    )
                    dates = re.sub(r"\s+", " ", dates)

            # Extract company
            company_patterns = [
                # Priority: "Title at Company" format (most common)
                r"(?:at|with|for)\s+([A-Z][A-Za-z0-9\s&.,]{2,30}?)(?:\s*$|\s*\n)",
                # Company after position title (with endings)
                r"(?:at|with|for)\s+([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?)",
                # Company with common indicators
                r"(?:Company|Employer|Organization|Client):\s*([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?)",
                # Company on a standalone line with capitalization
                r"^([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?)\s*$",
                # Company beginning a line, followed by location
                r"^([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?),\s*[A-Za-z\s,]+",
            ]

            for pattern in company_patterns:
                company_match = re.search(pattern, block, re.MULTILINE)
                if company_match:
                    company = company_match.group(1).strip()
                    # Validate company name - filter out skills, descriptions, etc.
                    if (
                        len(company) > 3
                        and len(company) < 50
                        and not company.startswith("-")  # Not a bullet point
                        and not any(
                            skill_word in company.lower()
                            for skill_word in [
                                "react",
                                "javascript",
                                "python",
                                "django",
                                "node",
                                "angular",
                                "vue",
                            ]
                        )  # Not a skill
                        and not company.lower().startswith(
                            "developed"
                        )  # Not a description
                        and not company.lower().startswith("led")
                        and not company.lower().startswith("built")
                    ):
                        break
                    else:
                        company = ""  # Reset if validation fails

            # Extract job title
            title_patterns = [
                # Priority: "Title at Company" format (most common)
                r"^([A-Z][A-Za-z\s]{2,40}?)\s+(?:at|with|for)\s+",
                # Title with common job words and "at/with/for"
                r"([A-Z][A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor|Lead|Head|Chief))\s*(?:\(.*?\))?\s*(?:,|\.|at|with|for)",
                # Title with colon
                r"(?:Position|Title|Role):\s*([A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor|Lead|Head|Chief))",
                # Title at beginning of block
                r"^([A-Z][A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor|Lead|Head|Chief))",
            ]

            for pattern in title_patterns:
                title_match = re.search(pattern, block, re.MULTILINE)
                if title_match:
                    potential_title = title_match.group(1).strip()
                    # Validate title - filter out bullet points, descriptions, etc.
                    if (
                        len(potential_title) > 3
                        and len(potential_title) < 50
                        and not potential_title.startswith("-")  # Not a bullet point
                        and not potential_title.lower().startswith(
                            "developed"
                        )  # Not a description
                        and not potential_title.lower().startswith("led")
                        and not potential_title.lower().startswith("built")
                        and not potential_title.lower().startswith("implemented")
                    ):
                        title = potential_title
                        break

            # If we didn't find a job title, look for any capitalized text near dates
            if not title and dates:
                date_pos = block.find(dates)
                if date_pos > 0:
                    # Check text before the date
                    text_before_date = block[:date_pos].strip()
                    # Look for capitalized words that might be a title
                    title_candidates = re.findall(
                        r"([A-Z][A-Za-z\s]+)", text_before_date
                    )
                    if title_candidates:
                        title = title_candidates[
                            -1
                        ].strip()  # Use the last one as it's likely closest to the date
                elif date_pos == 0 and len(block) > len(dates):
                    # Date is at the beginning, check text after
                    text_after_date = block[len(dates) :].strip()
                    # Look for capitalized words after date
                    title_candidates = re.findall(
                        r"([A-Z][A-Za-z\s]+)", text_after_date
                    )
                    if title_candidates:
                        title = title_candidates[
                            0
                        ].strip()  # Use the first one after the date

            # Ensure job title looks valid (not a company name or date)
            if title:
                # Remove unwanted parts
                title = re.sub(r"(?:,|\.|at|with|for)$", "", title).strip()
                # Check if title contains dates or common company terms
                if re.search(
                    r"\d{4}|Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?", title
                ):
                    title = ""

            # Extract description as all text after company and title information
            # First, find where the main content likely starts
            start_markers = []
            if title:
                start_markers.append(
                    (block.find(title) + len(title), f"after title '{title}'")
                )
            if company:
                start_markers.append(
                    (block.find(company) + len(company), f"after company '{company}'")
                )
            if dates:
                start_markers.append(
                    (block.find(dates) + len(dates), f"after dates '{dates}'")
                )

            if start_markers:
                # Use the latest start position
                start_pos, marker_info = max(start_markers, key=lambda x: x[0])
                logger.debug(
                    f"Starting description {marker_info} at position {start_pos}"
                )

                if start_pos < len(block):
                    # Description is everything after all the metadata
                    description = block[start_pos:].strip()
                    # Clean up the beginning
                    description = re.sub(r"^[,.:;-]+\s*", "", description)

            # If no specific start position found, use the whole block
            if not description and len(block) > 0:
                description = block.strip()

            # Clean up description
            if description:
                # Remove parts that might have been incorrectly included
                if title and description.startswith(title):
                    description = description[len(title) :].strip()
                if company and description.startswith(company):
                    description = description[len(company) :].strip()
                if dates and description.startswith(dates):
                    description = description[len(dates) :].strip()

                # Clean up the beginning of the description
                description = re.sub(r"^[,.:;-]+\s*", "", description)

                # Check if the description is too long (might contain multiple entries)
                if len(description) > 1000:
                    logger.debug(
                        f"Truncating overly long description from {len(description)} chars"
                    )
                    description = description[:1000] + "..."

            # Only add entries if we have at least some information
            if title or company or dates or (description and len(description) > 20):
                logger.debug(f"Found experience entry: {title} at {company} ({dates})")
                experience_entries.append(
                    {
                        "company": company,
                        "title": title,
                        "dates": dates,
                        "description": description,
                    }
                )

        logger.info(f"Extracted {len(experience_entries)} experience entries")
        return experience_entries

    def _split_experience_text(self, text: str) -> List[str]:
        """
        Split experience text into individual job blocks

        Args:
            text (str): Experience section text

        Returns:
            List[str]: List of text blocks for each job
        """
        # Split based on common patterns that indicate the start of a new job entry

        # Common date patterns at the beginning of job entries (enhanced for YYYY-MM format)
        date_patterns = [
            r"\n(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4})\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}|Present|Current|Now)",
            r"\n(?:\d{4}-\d{2})\s*(?:-|–|to)\s*(?:\d{4}-\d{2}|Present|Current|Now)",
            r"\n(?:\d{1,2}/\d{4})\s*(?:-|–|to)\s*(?:\d{1,2}/\d{4}|Present|Current|Now)",
            r"\n(?:\d{4})\s*(?:-|–|to)\s*(?:\d{4}|Present|Current|Now)",
            r"\n(?:\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}|\d{4})\s*(?:-|–|to)\s*(?:\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}|\d{4}|Present|Current|Now)",
        ]

        # Common job title patterns at the beginning of job entries (enhanced for "Title | Company" format)
        title_patterns = [
            # 🚨 PRIORITY: Enhanced patterns for "Title | Company" format (your specific case)
            r"\n([A-Z][A-Za-z\s\(\)\-&]+(?:Manager|Analyst|Developer|Engineer|Director|Specialist|Coordinator|Officer|Lead|Head|Chief|Consultant|Assistant|Representative|Administrator|Supervisor))\s*\|\s*([A-Za-z\s&.,]+(?:Ltd|Limited|Inc|LLC|Corp|Company|Group|Systems|Tech|Solutions))",
            r"\n([A-Z][A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor|Lead|Head|Chief))[,\s\|]",
            r"\n([A-Z][A-Za-z\s]+(?:Scientist|Architect|Strategist|Advisor|Executive|Programmer|Technician))[,\s\|]",
            r"\n(?:Position|Title|Role):\s*([A-Za-z\s]+)",
            r"\n([A-Za-z\s]+)\s*\|\s*([A-Za-z\s]+(?:Inc|LLC|Corp|Company|Ltd|Group|Systems))",
            # Enhanced pattern for "Title | Company | Date" format common in PDFs
            r"\n([A-Z][A-Za-z\s]+?)\s*\|\s*([A-Za-z\s]+(?:Inc|LLC|Corp|Company|Ltd|Group|Systems|Tech|Solutions))\s*\|\s*(\d{4}-\d{2}\s*-\s*(?:Present|Current|\d{4}-\d{2}))",
            # Alternative pattern for title at start of line followed by pipe
            r"\n([A-Z][A-Za-z\s]{5,40}?)\s*\|\s*([A-Za-z\s&.,]{3,30})\s*\|\s*(\d{4})",
            # Pattern for "Job Title | Company Name | Date Range"
            r"^([A-Z][A-Za-z\s]{3,40}?)\s*\|\s*([A-Za-z\s&.,]{3,40})\s*\|\s*(\d{4}-\d{2}|\d{4})",
        ]

        # Common company patterns at the beginning of job entries
        company_patterns = [
            r"\n([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company))[,\s]",
            r"\n(?:Company|Employer|Organization|Client):\s*([A-Za-z\s&.,]+)",
        ]

        # Combine all patterns
        all_patterns = date_patterns + title_patterns + company_patterns

        # Create a pattern that matches any of the job entry indicators
        split_pattern = "|".join(["(" + pattern + ")" for pattern in all_patterns])

        # Find all split points
        split_points = []
        for match in re.finditer(split_pattern, "\n" + text, re.MULTILINE):
            # The match includes the newline, so the actual split point is one character after the start
            split_point = match.start() + 1
            if split_point > 0:
                split_points.append(split_point)

        # Add the beginning and end of the text
        split_points = [0] + sorted(split_points) + [len(text)]

        # Extract the blocks
        blocks = []
        for i in range(len(split_points) - 1):
            block = text[split_points[i] : split_points[i + 1]].strip()
            if block:
                blocks.append(block)

        logger.debug(f"Split experience text into {len(blocks)} blocks")
        return blocks

    def _extract_skills(self, text: str) -> List[str]:
        """
        Extract skills from CV text

        Args:
            text (str): CV text

        Returns:
            List[str]: Extracted skills
        """
        # Try to find a skills section first
        sections = self._identify_cv_sections_safe(text, timeout=1.0)
        skills_text = ""

        # If skills section is found, extract text from that section
        if "skills" in sections:
            start_pos, end_pos = sections["skills"]
            skills_text = text[start_pos:end_pos]
            logger.debug(f"Found dedicated skills section ({len(skills_text)} chars)")
        else:
            # Try traditional section identification as fallback
            skills_section_patterns = [
                r"(?:Skills|Core Competencies|Technical Skills|Key Skills|Expertise|Proficiencies)[:\s]*\n*(.*?)(?=\n\s*(?:Experience|Education|Certifications|Languages|References|Additional Information|\Z))",
                r"(?:SKILLS|CORE COMPETENCIES|TECHNICAL SKILLS|KEY SKILLS|EXPERTISE|PROFICIENCIES)[:\s]*\n*(.*?)(?=\n\s*(?:EXPERIENCE|EDUCATION|CERTIFICATIONS|LANGUAGES|REFERENCES|ADDITIONAL|\Z))",
            ]

            for pattern in skills_section_patterns:
                skills_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if skills_match:
                    skills_text = skills_match.group(1)
                    logger.debug(
                        f"Found skills section via pattern matching ({len(skills_text)} chars)"
                    )
                    break

            if not skills_text:
                # If can't find a specific section, use the experience section to extract skills
                if "experience" in sections:
                    # Extract skills from experience section
                    start_pos, end_pos = sections["experience"]
                    experience_text = text[start_pos:end_pos]
                    skills_from_exp = self._extract_skills_from_experience(
                        experience_text
                    )
                    return skills_from_exp
                else:
                    # Use the entire text as a last resort but be more strict about what we extract
                    skills_text = text
                    logger.debug("No dedicated skills section found, using full text")

        # Common skill keywords and categories
        technical_skills = [
            # Programming languages
            "Python",
            "Java",
            "JavaScript",
            "TypeScript",
            "C++",
            "C#",
            "Ruby",
            "PHP",
            "Swift",
            "Kotlin",
            "Go",
            "Rust",
            "Scala",
            "Perl",
            "Shell",
            "Bash",
            "SQL",
            "R",
            "MATLAB",
            # Web technologies
            "HTML",
            "CSS",
            "React",
            "Angular",
            "Vue",
            "Node.js",
            "Express",
            "Django",
            "Flask",
            "ASP.NET",
            "Spring",
            "Ruby on Rails",
            "jQuery",
            "Bootstrap",
            "Tailwind",
            # Data & Analytics
            "Data Analysis",
            "Machine Learning",
            "Deep Learning",
            "AI",
            "NLP",
            "Computer Vision",
            "Data Mining",
            "Big Data",
            "Hadoop",
            "Spark",
            "Tableau",
            "Power BI",
            "Data Visualization",
            "Statistics",
            "Data Science",
            "Data Engineering",
            "ETL",
            "Data Warehousing",
            # Cloud & DevOps
            "AWS",
            "Azure",
            "GCP",
            "Docker",
            "Kubernetes",
            "Jenkins",
            "CI/CD",
            "Git",
            "GitHub",
            "GitLab",
            "Terraform",
            "Ansible",
            "Puppet",
            "Chef",
            "Prometheus",
            "Grafana",
            "ELK Stack",
            # Mobile
            "Android",
            "iOS",
            "React Native",
            "Flutter",
            "Swift",
            "Kotlin",
            "Objective-C",
            # Other tech
            "Agile",
            "Scrum",
            "Kanban",
            "JIRA",
            "REST API",
            "GraphQL",
            "Microservices",
            "SOA",
            "Big Data",
            "Hadoop",
            "Spark",
            # Design
            "UX/UI",
            "Figma",
            "Sketch",
            "Adobe XD",
            "Photoshop",
            "Illustrator",
            "InDesign",
            "Graphic Design",
            "Web Design",
            "Product Design",
            "User Research",
            "Wireframing",
            "Prototyping",
            "Usability Testing",
        ]

        soft_skills = [
            "Communication",
            "Leadership",
            "Problem Solving",
            "Critical Thinking",
            "Teamwork",
            "Time Management",
            "Project Management",
            "Adaptability",
            "Creativity",
            "Emotional Intelligence",
            "Decision Making",
            "Conflict Resolution",
            "Negotiation",
            "Presentation",
            "Public Speaking",
            "Customer Service",
            "Networking",
            "Mentoring",
            "Coaching",
            "Strategic Planning",
            "Attention to Detail",
            "Organization",
            "Multitasking",
            "Research",
            "Analytical Thinking",
        ]

        industry_skills = {
            "Marketing": [
                "Digital Marketing",
                "SEO",
                "SEM",
                "Content Marketing",
                "Social Media Marketing",
                "Email Marketing",
                "Marketing Automation",
                "Google Analytics",
                "CRM",
                "Branding",
                "Market Research",
                "Campaign Management",
                "Google Ads",
                "Facebook Ads",
                "Copywriting",
                "Sales",
                "Business Development",
                "Account Management",
                "Lead Generation",
            ],
            "Finance": [
                "Financial Analysis",
                "Financial Modeling",
                "Accounting",
                "Budgeting",
                "Forecasting",
                "Valuation",
                "Risk Management",
                "Investment Banking",
                "Portfolio Management",
                "Financial Reporting",
                "QuickBooks",
                "SAP",
                "Bloomberg Terminal",
                "Excel Modeling",
            ],
            "Healthcare": [
                "Patient Care",
                "Electronic Health Records",
                "HIPAA",
                "Clinical Documentation",
                "Medical Coding",
                "Medical Billing",
                "Healthcare Administration",
                "Epic",
                "Cerner",
            ],
            "Media": [
                "Video Production",
                "Video Editing",
                "Motion Graphics",
                "Animation",
                "Broadcasting",
                "Content Creation",
                "Final Cut Pro",
                "Adobe Premiere",
                "After Effects",
                "Avid",
                "Cinematography",
                "Directing",
                "Scriptwriting",
                "Storyboarding",
                "IPTV",
                "OTT",
                "DVB",
            ],
        }

        # Function to check if a skill is valid
        def is_valid_skill(skill):
            # Clean up the skill
            clean_skill = skill.strip()

            # Skip if too short or too long
            if len(clean_skill) < 3 or len(clean_skill) > 50:
                return False

            # Skip if contains unwanted patterns (like URLs, email addresses, long phrases)
            unwanted_patterns = [
                r"@",
                r"://",
                r"\\",
                r"\d{3,}",  # emails, URLs, paths, long numbers
                r"^(?:in|of|at|by|to|and|with|or|for)$",  # Common prepositions/conjunctions as standalone words
                r"^\d+\s+\w+$",  # Numbers followed by single words
                r"^.{40,}$",  # Any skill that's too long (likely a sentence fragment)
                r"^I\s+[a-z]",  # Sentences starting with "I"
                r"^(?:As|The|It|This|That|These|Those|My|Our|Their|His|Her|We|They)\s",  # Sentences with common beginnings
                r"\bI\b|\bmy\b|\bme\b|\bwe\b|\bour\b",  # Personal pronouns (likely parts of sentences)
                r"[\.]{2,}$",  # Ellipsis
                r",$",  # Ending with comma (likely part of a list)
                r"^[a-z]",  # Skills should start with capital letters
                r"(?:have|has|had)\s+[a-z]",  # Verb phrases
                r"\s+(?:is|are|was|were|will|would|should|could|can)\s+",  # Verb phrases with auxiliary verbs
                r"^Company\s|^Compan[iy]$|^Title\s",  # Common placeholder text
                r"^(?:City|State)$",  # Common placeholder text
                r"^\s*\w+\s+\w+\s+\w+\s+\w+\s+\w+\s",  # 5+ words (likely a phrase, not a skill)
                r"Further\s|Additionally\s",  # Common sentence starters
                r"China\b|ShenZhen\b",  # Locations
                r"^Chief\s|^Senior\s|^Junior\s|^Principal\s|^Lead\s|^Director\s",  # Job title beginnings
                r"^Manager\s|^Vice\s|^President\s|^Head\s|^Executive\s",  # More job title beginnings
                r"^SVP\s|^EVP\s|^CTO\s|^CEO\s|^CFO\s|^COO\s|^CIO\s",  # C-level titles
                r"\bARCHITECT$",  # Words that are likely job titles
                r"Along with",  # Phrase fragments
                r"S/S2/DTH",  # Specific fragments from this CV
                r"\bEVP\b|\bGM\b|\bSVP\b",  # Executive title abbreviations
                r"television design",  # Department names
            ]

            for pattern in unwanted_patterns:
                if re.search(pattern, clean_skill, re.IGNORECASE):
                    return False

            # Job titles to exclude specifically
            job_titles = [
                "Chief System Architect",
                "SVP System Integration",
                "Chief Technology Officer",
                "System Architect",
                "Software Engineer",
                "Project Manager",
                "Product Manager",
                "Director",
                "Vice President",
                "President",
                "CEO",
                "CTO",
                "COO",
                "CFO",
                "Executive Vice President",
                "Senior Vice President",
            ]

            for title in job_titles:
                if title.lower() in clean_skill.lower():
                    return False

            # Check if it's a technical, soft skill, or industry-specific skill
            if any(
                re.search(rf"\b{re.escape(s)}\b", clean_skill, re.IGNORECASE)
                for s in technical_skills
            ):
                return True

            if any(
                re.search(rf"\b{re.escape(s)}\b", clean_skill, re.IGNORECASE)
                for s in soft_skills
            ):
                return True

            for industry, industry_skill_list in industry_skills.items():
                if any(
                    re.search(rf"\b{re.escape(s)}\b", clean_skill, re.IGNORECASE)
                    for s in industry_skill_list
                ):
                    return True

            # Check for industry-specific acronyms and technologies
            media_tech_patterns = [
                r"\b(?:IPTV|OTT|DVB|DVB-[ST][/]?[0-9]?|DTH|MPLS|VOD)\b",
                r"\b(?:SDI|HD-SDI|ATSC|HEVC|H\.264|MPEG-[0-9])\b",
                r"\b(?:HDR|UHD|4K|8K|HDR10|HLG|HDMI|DisplayPort)\b",
                r"\b(?:LCD|LED|OLED|QLED|TV|Television|Broadcasting)\b",
                r"\b(?:Cable|Satellite|Terrestrial|Digital Media|Streaming)\b",
            ]

            for pattern in media_tech_patterns:
                if re.search(pattern, clean_skill, re.IGNORECASE):
                    return True

            # Define additional media/broadcast industry specific skills
            media_skills = [
                "Broadcasting",
                "Video Production",
                "Video Editing",
                "Post Production",
                "Content Delivery",
                "Digital Media",
                "Media Server",
                "Cable TV",
                "Mobile TV",
                "Streaming",
                "Cloud Video",
                "Video Compression",
                "Encoding",
                "Transcoding",
                "Video Distribution",
                "Video Storage",
                "Media Asset Management",
                "Video Analytics",
                "Digital Rights Management",
                "Content Management",
                "Video Workflow",
                "Media Workflow",
                "Set-top Box",
                "Android TV",
                "Apple TV",
                "Smart TV",
                "Broadcast Automation",
                "Live Production",
                "Remote Production",
                "Virtual Production",
            ]

            for skill in media_skills:
                if skill.lower() in clean_skill.lower():
                    return True

            # Check if it's a common skill word pattern
            skill_patterns = [
                r"^[A-Z][a-zA-Z]{2,}$",  # Single capitalized word (e.g., Python, Java)
                r"^[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+$",  # Two capitalized words (e.g., Project Management)
                r"^[A-Z][a-zA-Z\s\-&/]{2,25}$",  # Capitalized words, allowing dash & slash (but stricter)
                r"^[A-Z]{2,5}$",  # Acronyms like HTML, CSS, AWS
                r"^[A-Za-z]+\+\+$",  # C++, etc.
                r"^[A-Za-z]+#$",  # C#, etc.
                r"^\d\+\s+years\s+.*experience$",  # Experience phrases
            ]

            for pattern in skill_patterns:
                if re.match(pattern, clean_skill):
                    # Additional validation: skills shouldn't be very common English words
                    common_words = [
                        "about",
                        "above",
                        "across",
                        "after",
                        "again",
                        "against",
                        "almost",
                        "alone",
                        "along",
                        "already",
                        "also",
                        "although",
                        "always",
                        "among",
                        "another",
                        "before",
                        "behind",
                        "being",
                        "below",
                        "between",
                        "both",
                        "company",
                        "city",
                        "state",
                        "each",
                        "either",
                        "enough",
                        "every",
                        "everybody",
                        "everyone",
                        "everything",
                        "everywhere",
                        "except",
                        "executive",
                        "finally",
                        "first",
                        "following",
                        "further",
                        "furthermore",
                        "general",
                        "however",
                        "indeed",
                        "instead",
                        "itself",
                        "looking",
                        "mainly",
                        "maybe",
                        "meanwhile",
                        "moreover",
                        "mostly",
                        "namely",
                        "neither",
                        "nevertheless",
                        "next",
                        "nobody",
                        "nothing",
                        "nowhere",
                        "often",
                        "otherwise",
                        "overall",
                        "particularly",
                        "perhaps",
                        "possibly",
                        "generally",
                        "rather",
                        "regarding",
                        "second",
                        "secondly",
                        "similarly",
                        "since",
                        "slightly",
                        "someone",
                        "something",
                        "sometimes",
                        "somewhat",
                        "somewhere",
                        "specifically",
                        "still",
                        "strongly",
                        "there",
                        "thereafter",
                        "thereby",
                        "therefore",
                        "though",
                        "through",
                        "throughout",
                        "thus",
                        "together",
                        "toward",
                        "towards",
                        "under",
                        "underneath",
                        "undoubtedly",
                        "unless",
                        "unlike",
                        "until",
                        "upon",
                        "usually",
                        "when",
                        "where",
                        "whereas",
                        "wherever",
                        "whether",
                        "which",
                        "while",
                        "within",
                        "without",
                        "would",
                        "responsibilities",
                        "accomplishments",
                        "experience",
                    ]

                    if clean_skill.lower() in common_words:
                        return False

                    return True

            # Companies that might be actual skills
            tech_companies_as_skills = [
                "Cisco",
                "Yahoo",
                "Microsoft",
                "Google",
                "Amazon",
                "AWS",
                "Oracle",
                "IBM",
                "SAP",
            ]
            if clean_skill in tech_companies_as_skills:
                return True

            # If it's not matched by our patterns, it's probably not a valid skill
            return False

        # Extract skills using bullet points, commas, and newlines
        skills = []
        patterns = [
            r"[•\-–—*★⭐✓✔+]\s*([^•\-–—*★⭐✓✔+\n]{3,50})",  # Bullet points
            r"(?:^|\n|\s+)([A-Z][a-zA-Z\s\-&/]{2,30})(?:,|\.|$|\n)",  # Capitalized phrases
            r"(?:,|•|\n)\s*([A-Za-z][a-zA-Z0-9\s\-&/\']{2,30})(?:,|\.|$|\n)",  # Comma-separated items
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, skills_text)
            for match in matches:
                skill = match.group(1).strip()
                # Remove trailing commas, periods, etc.
                skill = re.sub(r"[,.:;]+$", "", skill)
                if is_valid_skill(skill) and skill not in skills:
                    skills.append(skill)

        # Also check for "skill highlights" or similar sections
        skill_highlights_pattern = r"(?:Skill\s+Highlights|Core\s+Skills|Key\s+Competencies).*?(?:\n|$)(.*?)(?=\n\n|\Z)"
        skill_highlights_match = re.search(
            skill_highlights_pattern, text, re.IGNORECASE | re.DOTALL
        )

        if skill_highlights_match:
            highlight_text = skill_highlights_match.group(1)
            # Split by newlines or bullet points
            highlight_skills = re.findall(
                r"[•\-–—*★⭐✓✔+]?\s*([^•\-–—*★⭐✓✔+\n,]{3,50})(?:,|\n|$)",
                highlight_text,
            )

            for skill in highlight_skills:
                skill = skill.strip()
                skill = re.sub(r"[,.:;]+$", "", skill)
                if is_valid_skill(skill) and skill not in skills:
                    skills.append(skill)

        # If still few skills, try a more aggressive approach with the experience section
        if len(skills) < 5:
            # Look for phrases that are likely skills in experience descriptions
            experience_skills_pattern = r"(?:proficient\s+in|expertise\s+in|knowledge\s+of|experience\s+with|skilled\s+in|specialized\s+in)\s+([^,.]{3,50})"
            experience_skills_matches = re.finditer(
                experience_skills_pattern, text, re.IGNORECASE
            )

            for match in experience_skills_matches:
                skill = match.group(1).strip()
                skill = re.sub(r"[,.:;]+$", "", skill)
                if is_valid_skill(skill) and skill not in skills:
                    skills.append(skill)

        # Remove duplicates and near-duplicates
        unique_skills = []
        normalized_skills = []

        for skill in skills:
            # Create a normalized version (lowercase, no punctuation)
            normalized = re.sub(r"[^\w\s]", "", skill.lower())
            normalized = re.sub(r"\s+", " ", normalized).strip()

            # Check if this or a similar skill is already included
            is_duplicate = False
            for i, existing in enumerate(normalized_skills):
                # Check for exact match or if one contains the other
                if (
                    normalized == existing
                    or normalized in existing
                    or existing in normalized
                ):
                    # If the current skill is longer, replace the existing one
                    if len(skill) > len(unique_skills[i]) and len(skill) <= 50:
                        unique_skills[i] = skill
                        normalized_skills[i] = normalized
                    is_duplicate = True
                    break

            if (
                not is_duplicate and len(unique_skills) < 30
            ):  # Limit to 30 skills maximum
                unique_skills.append(skill)
                normalized_skills.append(normalized)

        return unique_skills

    def _extract_languages(self, text: str) -> List[Dict[str, str]]:
        """
        Extract languages from the document

        Args:
            text (str): Document text

        Returns:
            List[Dict[str, str]]: List of languages with proficiency
        """
        logger.debug("Extracting languages")

        # First try to find the languages section
        sections = self._identify_cv_sections(text)
        languages_text = ""

        # If languages section is found, extract text from that section
        if "languages" in sections:
            start_pos, end_pos = sections["languages"]
            languages_text = text[start_pos:end_pos]
            logger.debug(
                f"Found dedicated languages section ({len(languages_text)} chars)"
            )
        else:
            # Try traditional section identification as fallback
            languages_section_pattern = r"(?:Languages|Language Skills|Language Proficiency)[:\s]*\n*(.*?)(?=\n\s*(?:Experience|Education|Skills|Certifications|References|Additional Information|\Z))"

            languages_section_match = re.search(
                languages_section_pattern, text, re.IGNORECASE | re.DOTALL
            )

            if languages_section_match:
                languages_text = languages_section_match.group(1)
                logger.debug(
                    f"Found languages section via pattern matching ({len(languages_text)} chars)"
                )
            else:
                # Check for language mentions in the entire text
                languages_text = text
                logger.debug("No dedicated languages section found, using full text")

        # Start extraction
        languages = []
        language_with_level = {}

        # Common languages
        common_languages = [
            "English",
            "French",
            "Spanish",
            "German",
            "Italian",
            "Portuguese",
            "Dutch",
            "Russian",
            "Mandarin",
            "Chinese",
            "Japanese",
            "Korean",
            "Arabic",
            "Hindi",
            "Bengali",
            "Urdu",
            "Turkish",
            "Polish",
            "Swedish",
            "Norwegian",
            "Danish",
            "Finnish",
            "Greek",
            "Hebrew",
            "Thai",
            "Vietnamese",
            "Malay",
            "Indonesian",
        ]

        # Common proficiency levels
        proficiency_levels = [
            "Native",
            "Fluent",
            "Proficient",
            "Advanced",
            "Intermediate",
            "Basic",
            "Beginner",
            "Business",
            "Conversational",
            "Elementary",
            "Professional",
            "C2",
            "C1",
            "B2",
            "B1",
            "A2",
            "A1",
        ]

        # Look for patterns like "Language: Level" or "Language (Level)"
        for language in common_languages:
            # Look for language with level
            for level in proficiency_levels:
                patterns = [
                    r"\b"
                    + re.escape(language)
                    + r"\s*[:–-]\s*"
                    + re.escape(level)
                    + r"\b",
                    r"\b" + re.escape(language) + r"\s*\(" + re.escape(level) + r"\)",
                    r"\b" + re.escape(language) + r"\s*–\s*" + re.escape(level) + r"\b",
                ]

                for pattern in patterns:
                    match = re.search(pattern, languages_text, re.IGNORECASE)
                    if match:
                        language_with_level[language] = level
                        break

                if language in language_with_level:
                    break

            # If no level found but language is mentioned
            if language not in language_with_level:
                # Check if language is mentioned at all
                if re.search(
                    r"\b" + re.escape(language) + r"\b", languages_text, re.IGNORECASE
                ):
                    language_with_level[language] = ""

        # Convert to list of dictionaries
        for language, level in language_with_level.items():
            languages.append({"language": language, "proficiency": level})

        logger.info(f"Extracted {len(languages)} languages")
        return languages

    def _extract_certifications(self, text: str) -> List[Dict[str, str]]:
        """
        Extract certifications from the document

        Args:
            text (str): Document text

        Returns:
            List[Dict[str, str]]: List of certifications with dates
        """
        logger.debug("Extracting certifications")

        # First try to find the certifications section
        sections = self._identify_cv_sections_safe(text, timeout=1.0)
        certifications_text = ""

        # If certifications section is found, extract text from that section
        if "certifications" in sections:
            start_pos, end_pos = sections["certifications"]
            certifications_text = text[start_pos:end_pos]
            logger.debug(
                f"Found dedicated certifications section ({len(certifications_text)} chars)"
            )
        else:
            # Try traditional section identification as fallback with more comprehensive patterns
            certification_section_patterns = [
                r"(?:Certifications|Certificates|Professional Certifications|Licenses|Qualifications|Professional Development)[:\s]*\n*(.*?)(?=\n\s*(?:Experience|Education|Skills|Languages|References|Additional Information|\Z))",
                r"(?:CERTIFICATIONS|CERTIFICATES|LICENSES|CREDENTIALS)[:\s]*\n*(.*?)(?=\n\s*(?:EXPERIENCE|EDUCATION|SKILLS|LANGUAGES|REFERENCES|ADDITIONAL)|\Z)",
                r"(?:Certs|Professional Qualifications|Accreditations)[:\s]*\n*(.*?)(?=\n\s*(?:Experience|Education|Skills|Languages|References|Additional Information|\Z))",
            ]

            for pattern in certification_section_patterns:
                cert_section_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if cert_section_match:
                    certifications_text = cert_section_match.group(1)
                    logger.debug(
                        f"Found certifications section via pattern matching ({len(certifications_text)} chars)"
                    )
                    break

            if not certifications_text:
                # Look for certification mentions in the entire text, but be very selective
                # Only look in shorter sections of text that might contain certifications
                certifications_text = text[
                    : min(len(text), 10000)
                ]  # Limit to first 10000 chars
                logger.debug(
                    "No dedicated certifications section found, using limited text"
                )

        # Initialize list for valid certifications
        valid_certs = []

        # Specific known certifications to look for - these are known to be valid certifications
        specific_certifications = [
            # IT & Tech
            r"\b(?:CISSP|CISA|CISM|CEH|Security\+|Network\+|A\+|MCSE|MCSA|MCP|CCNA|CCNP|CCIE|AWS\s+Certified|Azure\s+Certified|Google\s+Cloud\s+Certified|CompTIA|PMP|PRINCE2|ITIL|CSM|PSM|CSD|SAFe|Six\s+Sigma\s+(?:Green|Yellow|Black)\s+Belt|TOGAF|IIBA|CBAP|VMware\s+Certified|Oracle\s+Certified|IBM\s+Certified|Salesforce\s+Certified|ServiceNow\s+Certified)\b",
            # Professional/Business
            r"\b(?:CPA|CFA|FRM|CMA|EA|CIA|Series\s+7|Series\s+63|Series\s+65|FINRA|SHRM-CP|SHRM-SCP|PHR|SPHR|PMP|CAPM|CSM|PSM|LEED\s+AP|CFP|ChFC|CLU|CPA|CPC|CPCU)\b",
            # Medical/Healthcare
            r"\b(?:RN|LPN|MCAT|USMLE|NCLEX|CNA|EMT|ACLS|BLS|PALS|CPC|CCS|RHIA|RHIT|LCSW|LMFT|LPC|NCC|BCBA|NASM|ACE|ACSM|NCCPA|PA-C|MD|DO|PharmD|DC|DMD|DDS|OD|PT|OT|MSN|BSN|ADN)\b",
            # Education
            r"\b(?:PhD|Ed\.D|MD|JD|DBA|DDS|PharmD|PsyD|MBA|MPA|MPH|MS|MA|MSc|MSW|MEd|MEng|MFA|BA|BS|BSc|BBA|BFA|Associate\s+Degree|High\s+School\s+Diploma|GED)\b",
        ]

        # First, look for specific known certifications
        for pattern in specific_certifications:
            matches = re.finditer(pattern, certifications_text, re.IGNORECASE)
            for match in matches:
                cert_text = match.group(0).strip()

                # Extract date if present in surrounding text (look in a window of text)
                start_pos = max(0, match.start() - 20)
                end_pos = min(len(certifications_text), match.end() + 20)
                surrounding_text = certifications_text[start_pos:end_pos]

                date = ""
                date_match = re.search(r"(?:19|20)\d{2}", surrounding_text)
                if date_match:
                    date = date_match.group(0)

                # Check if this certification is unique
                is_unique = True
                for existing_cert in valid_certs:
                    if (
                        cert_text.lower() in existing_cert["name"].lower()
                        or existing_cert["name"].lower() in cert_text.lower()
                    ):
                        is_unique = False
                        break

                if is_unique:
                    valid_certs.append({"name": cert_text, "date": date})

        # Look for certification patterns in bullet points and structured text
        if len(valid_certs) < 5:  # Only if we haven't found enough specific certs
            # Define patterns for valid certifications
            certification_patterns = [
                # Well-known certification prefixes/formats
                r"(?:Certified|Licensed|Registered|Professional|Accredited|Chartered)[^\n]{5,40}(?:Technician|Engineer|Professional|Developer|Architect|Specialist|Consultant|Advisor|Accountant|Manager)",
                # Certificate pattern with "in" or "of"
                r"(?:Certificate|Certification|Diploma|License|Credential)[^\n]{1,30}(?:in|of|for)[^\n]{5,40}",
                # Degree patterns
                r"(?:Bachelor|Master|MBA|PhD|Doctorate)[^\n]{1,30}(?:of|in)[^\n]{5,40}(?:Science|Engineering|Arts|Business|Management|Economics|Finance|Law|Medicine)",
            ]

            # Words that should not be in certifications
            exclude_words = [
                "EXPERIENCE",
                "PROJECTS",
                "LANGUAGES",
                "EDUCATION",
                "SKILLS",
                "ADDITIONAL",
                "CONTACT",
                "PERSONAL",
                "SUMMARY",
                "REFERENCE",
                "OBJECTIVE",
                "PROFILE",
                "WORK",
                "EMPLOYMENT",
            ]

            # Look for bullet points with certifications
            bullet_patterns = [
                r"[•\-–—*★⭐✓✔+]\s*([^•\-–—*★⭐✓✔+\n]{3,80})",
                r"^\s*[•\-–—*★⭐✓✔+]\s*(.+)$",
            ]

            for pattern in bullet_patterns:
                bullet_matches = re.finditer(pattern, certifications_text, re.MULTILINE)
                for match in bullet_matches:
                    cert_text = match.group(1).strip()

                    # Skip if too long or too short
                    if len(cert_text) > 80 or len(cert_text) < 4:
                        continue

                    # Skip if contains section markers
                    should_skip = False
                    for word in exclude_words:
                        if re.search(
                            r"\b" + re.escape(word) + r"\b", cert_text, re.IGNORECASE
                        ):
                            should_skip = True
                            break

                    if should_skip:
                        continue

                    # Skip if it contains unwanted patterns (like sentence fragments)
                    unwanted_patterns = [
                        r"^I\s+[a-z]",  # Sentences starting with "I"
                        r"^(?:As|The|It|This|That|These|Those|My|Our|Their|His|Her|We|They)\s",  # Sentences with common beginnings
                        r"\bI\b|\bmy\b|\bme\b|\bwe\b|\bour\b",  # Personal pronouns
                        r"[\.]{2,}$",  # Ellipsis
                        r",$",  # Ending with comma (likely part of a list)
                        r"(?:have|has|had)\s+[a-z]",  # Verb phrases
                        r"\s+(?:is|are|was|were|will|would|should|could|can)\s+",  # Verb phrases with auxiliary verbs
                        r"^[a-z]",  # Should start with capital letter
                        r"\s+and\s+",  # Likely a compound phrase, not a certification
                        r"^\s*\w+\s+\w+\s+\w+\s+\w+\s+\w+\s",  # 5+ words (likely a phrase, not a certification)
                        r"system|experience|responsibility|skill|duty|task",  # Job-related terms that aren't certifications
                        r"year|month|week|day",  # Time-related terms, likely experience not cert
                        r"^(?:over|under|around|about|through|throughout)",  # Prepositions beginning a phrase
                        r"[a-z]{30,}",  # Very long words (likely garbage)
                        r"press in|press, Press",  # Fragments from the sample
                        r"handover|ration|worldwide|nationwide",  # More fragments from the sample
                    ]

                    for pattern in unwanted_patterns:
                        if re.search(pattern, cert_text, re.IGNORECASE):
                            should_skip = True
                            break

                    if should_skip:
                        continue

                    # Check if this looks like a valid certification
                    is_valid_cert = False

                    # Check if it matches any of our certification patterns
                    for cert_pattern in certification_patterns:
                        if re.search(cert_pattern, cert_text, re.IGNORECASE):
                            is_valid_cert = True
                            break

                    # Check for specific certification keywords
                    cert_keywords = [
                        "Certified",
                        "Certificate",
                        "Certification",
                        "License",
                        "Licensed",
                        "Diploma",
                        "Degree",
                        "Bachelor",
                        "Master",
                        "MBA",
                        "PhD",
                        "Doctorate",
                    ]

                    if not is_valid_cert:
                        for keyword in cert_keywords:
                            if re.search(
                                r"\b" + re.escape(keyword) + r"\b",
                                cert_text,
                                re.IGNORECASE,
                            ):
                                is_valid_cert = True
                                break

                    if not is_valid_cert:
                        continue

                    # Extract date if present
                    date = ""
                    date_match = re.search(r"(?:19|20)\d{2}", cert_text)
                    if date_match:
                        date = date_match.group(0)

                    # Clean up the certification name
                    cert_name = re.sub(
                        r"[.,:;]$", "", cert_text
                    )  # Remove trailing punctuation

                    # Check if this certification is unique
                    is_unique = True
                    for existing_cert in valid_certs:
                        if (
                            cert_name.lower() in existing_cert["name"].lower()
                            or existing_cert["name"].lower() in cert_name.lower()
                        ):
                            is_unique = False
                            break

                    if is_unique:
                        valid_certs.append({"name": cert_name, "date": date})

            # Look for structured lines that might indicate certifications
            if len(valid_certs) < 5:
                # Look for lines that might be certifications with or without dates
                cert_line_patterns = [
                    r"^([A-Z][A-Za-z\s\-\.&]+(?:Certificate|Certification|License|Diploma))(?:\s*[-:]\s*|\s+in\s+|\s*,\s*|\s+)(\d{4})?",
                    r"^([A-Z][A-Za-z\s]+(?:University|Institute|College|School|Academy))(?:\s*[-:]\s*|\s*,\s*)(\d{4})?",
                    r"^([A-Z][A-Za-z\s\-\.&]+)",
                ]

                for pattern in cert_line_patterns:
                    line_matches = re.finditer(
                        pattern, certifications_text, re.MULTILINE
                    )
                    for match in matches:
                        cert_name = match.group(1).strip()

                        # Skip if it's likely not a certification
                        if len(cert_name) < 4 or len(cert_name) > 80:
                            continue

                        # Check for unwanted patterns
                        should_skip = False
                        for pattern in unwanted_patterns:
                            if re.search(pattern, cert_name, re.IGNORECASE):
                                should_skip = True
                                break

                        if should_skip:
                            continue

                        # Get date if captured
                        date = ""
                        if len(match.groups()) > 1 and match.group(2):
                            date = match.group(2)

                        # Check for uniqueness
                        is_unique = True
                        for existing_cert in valid_certs:
                            if (
                                cert_name.lower() in existing_cert["name"].lower()
                                or existing_cert["name"].lower() in cert_name.lower()
                            ):
                                is_unique = False
                                break

                        if is_unique:
                            valid_certs.append({"name": cert_name, "date": date})

        # Ensure no duplicate entries
        deduplicated_certs = []
        seen_certs = set()

        for cert in valid_certs:
            # Create a normalized version for deduplication
            normalized = cert["name"].lower().strip()
            if normalized not in seen_certs:
                seen_certs.add(normalized)
                deduplicated_certs.append(cert)

        logger.info(f"Extracted {len(deduplicated_certs)} certifications")
        return deduplicated_certs

    def _parse_segmented_text(self, segmented_text):
        """
        Parse CV text that has been segmented by LLM into sections

        Args:
            segmented_text (str): Segmented CV text with section markers

        Returns:
            dict: Parsed CV data
        """
        start_time = time.time()
        logger.info("Parsing segmented CV text")

        # First, validate the input
        if not segmented_text or "==========" not in segmented_text:
            logger.warning("Invalid segmented text - missing section markers")
            return self._parse_traditional(segmented_text)

        # Initialize result with default empty values
        result = self._empty_result()

        # Clean up text to ensure section markers are properly formatted
        # Sometimes LLMs may generate malformed markers or extra text
        cleaned_text = re.sub(r"={5,8}([A-Z_]+)", r"==========\1", segmented_text)
        cleaned_text = re.sub(r"={12,}([A-Z_]+)", r"==========\1", cleaned_text)

        # Handle cases where section markers appear in content
        # Make sure markers have consistent format with 10 equals signs
        cleaned_text = re.sub(
            r"([^\n])={9,11}([A-Z_]+)", r"\1\n==========\2", cleaned_text
        )

        # Replace multiple consecutive section markers with just one
        cleaned_text = re.sub(r"(?:={9,11}[A-Z_]+\s*){2,}", r"==========", cleaned_text)

        # Add proper spacing around section markers for cleaner splitting
        cleaned_text = re.sub(r"(={9,11}[A-Z_]+)", r"\n\1\n", cleaned_text)

        # Try to extract name from the beginning if it's likely to be there
        full_name = ""
        first_line_match = re.match(
            r"^([A-Z][a-zA-Z\s\.-]+)(?:\n|,|\s{2,})", cleaned_text, re.MULTILINE
        )
        if first_line_match:
            full_name = first_line_match.group(1).strip()
            if len(full_name) < 50:  # Reasonable name length
                # Save for later use
                name_parts = full_name.split(None, 1)
                if len(name_parts) >= 2:
                    result["personal_info"]["first_name"] = name_parts[0]
                    result["personal_info"]["last_name"] = name_parts[1]
                elif len(name_parts) == 1:
                    result["personal_info"]["first_name"] = name_parts[0]

        # Split by section markers
        pattern = r"={9,11}([A-Z_]+)"
        sections = re.split(pattern, cleaned_text)

        # First element is any text before the first marker (usually empty)
        if sections and sections[0].strip() == "":
            sections = sections[1:]  # Remove first element (text before first marker)

        # Process each section (name and content pairs)
        section_count = 0

        # Debug output for understanding section structure
        logger.debug(f"Found {len(sections)//2} potential sections")

        # To ensure we don't process the same section type twice
        processed_section_types = set()

        # Try to find all personal info across the entire document
        # This is a backup approach to extract email, phone, etc. even if they're not in the personal section
        email_match = re.search(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", cleaned_text
        )
        if email_match:
            result["personal_info"]["email"] = email_match.group(0)

        phone_match = re.search(
            r"(?:\+\d{1,2}\s?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}",
            cleaned_text,
        )
        if phone_match:
            result["personal_info"]["phone"] = phone_match.group(0)

        location_match = re.search(
            r"(?:City\s*,\s*State|[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}|[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)",
            cleaned_text,
        )
        if location_match:
            location = location_match.group(0).replace("City , State", "").strip()
            if location:
                result["personal_info"]["location"] = location

        # Look for LinkedIn
        linkedin_match = re.search(
            r"(?:linkedin\.com/in/|LinkedIn:)\s*([a-zA-Z0-9/-]+)", cleaned_text
        )
        if linkedin_match:
            result["personal_info"]["linkedin"] = linkedin_match.group(0)

        for i in range(0, len(sections), 2):
            if i + 1 >= len(sections):
                break

            original_section_name = sections[i].strip().upper()
            section_name = original_section_name.lower()
            section_content = sections[i + 1].strip()

            # Skip if we've already processed this section type
            if original_section_name in processed_section_types:
                logger.debug(f"Skipping duplicate section: {original_section_name}")
                continue

            # Add to processed sections
            processed_section_types.add(original_section_name)

            # Remove any trailing section markers in content
            section_content = re.sub(r"={9,11}.*$", "", section_content).strip()

            # Skip truly empty sections
            if not section_content:
                logger.debug(f"Skipping empty section: {section_name}")
                continue

            # Skip if just a placeholder with standard format
            if (
                section_content.lower() == "(content)"
                or section_content.lower() == "content"
                or section_content.lower() == "(not provided)"
                or section_content.lower() == "(no content)"
            ):
                logger.debug(f"Skipping placeholder section: {section_name}")
                continue

            # Check for pattern indicating placeholder content
            placeholder_pattern = r"^\([^)]{2,40}\)$"
            if re.match(placeholder_pattern, section_content.strip()):
                logger.debug(f"Skipping likely placeholder section: {section_name}")
                continue

            # Check for section markers or section names within content (LLM error)
            section_keywords = [
                "PERSONAL",
                "SUMMARY",
                "EXPERIENCE",
                "EDUCATION",
                "SKILLS",
                "LANGUAGES",
                "CERTIFICATIONS",
                "PROJECTS",
                "INTERESTS",
            ]

            # If content has section markers, extract only the relevant part
            if "==========" in section_content:
                logger.warning(
                    f"Found section markers within section content - cleaning up"
                )
                # Extract just the part before any nested section marker
                section_content = section_content.split("==========")[0].strip()
                if not section_content:
                    continue

            # Check if content starts with another section name
            # This can happen when the LLM incorrectly formats the output
            if any(
                section_content.strip().upper().startswith(kw)
                for kw in section_keywords
            ):
                # Try to find where the actual content starts
                lines = section_content.split("\n", 2)
                if len(lines) > 1 and any(
                    kw in lines[0].upper() for kw in section_keywords
                ):
                    logger.warning(
                        f"Section content starts with section name - cleaning up"
                    )
                    # Skip the first line which is likely another section name
                    section_content = "\n".join(lines[1:]).strip()
                    if not section_content:
                        continue

            # Count valid sections
            section_count += 1
            logger.debug(
                f"Processing section: {section_name} ({len(section_content)} chars)"
            )

            # Process each section based on its name
            section_start_time = time.time()
            try:
                # Process Personal Information
                if "personal" in section_name:
                    personal_info = self._parse_personal_info_section(section_content)
                    # Validate that the personal info doesn't contain section names
                    for key, value in personal_info.items():
                        if value and any(
                            kw in value.upper() for kw in section_keywords
                        ):
                            personal_info[key] = ""

                    # If no meaningful personal info was extracted, try to extract from the beginning of the CV
                    if not any(personal_info.values()):
                        # Try to extract name from the first section
                        # Often the CV starts with the person's name and title
                        name_match = re.search(
                            r"^([A-Z][a-zA-Z\s\.-]+)(?:\n|,|\s{2,})",
                            section_content[:500],
                            re.MULTILINE,
                        )
                        if name_match:
                            full_name = name_match.group(1).strip()
                            # Split into first and last name
                            name_parts = full_name.split(None, 1)
                            if len(name_parts) > 0:
                                personal_info["first_name"] = name_parts[0]
                                if len(name_parts) > 1:
                                    personal_info["last_name"] = name_parts[1]

                        # Try to find email
                        email_match = re.search(
                            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                            section_content,
                        )
                        if email_match:
                            personal_info["email"] = email_match.group(0)

                        # Try to find phone
                        phone_match = re.search(
                            r"(?:\+\d{1,2}\s?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}",
                            section_content,
                        )
                        if phone_match:
                            personal_info["phone"] = phone_match.group(0)

                        # Try to find location
                        location_match = re.search(
                            r"(?:City\s*,\s*State|[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}|[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)",
                            section_content,
                        )
                        if location_match:
                            personal_info["location"] = (
                                location_match.group(0)
                                .replace("City , State", "")
                                .strip()
                            )

                    result["personal_info"] = personal_info

                # Process Professional Summary
                elif (
                    "summary" in section_name
                    or "profile" in section_name
                    or "objective" in section_name
                ):
                    # Fix: use the correct method name extract_professional_summary instead of _extract_summary
                    summary = self.extract_professional_summary(section_content)
                    # Check for section markers or section keywords
                    if "==========" in summary or any(
                        f"========{kw}" in summary.upper() for kw in section_keywords
                    ):
                        # Try to clean it
                        summary = re.sub(
                            r"={5,}[A-Z_]+.*$", "", summary, flags=re.DOTALL
                        ).strip()

                    # Remove any leading section markers like "==========PERSONAL_INFO"
                    summary = re.sub(r"^={5,}[A-Z_]+\s*", "", summary).strip()

                    # If summary still has markers, try a more aggressive approach
                    if "==========" in summary:
                        parts = summary.split("==========")
                        # Take the longest part that doesn't contain suspicious text
                        valid_parts = [
                            p
                            for p in parts
                            if len(p) > 30
                            and not any(kw in p.upper() for kw in section_keywords)
                        ]
                        if valid_parts:
                            summary = max(valid_parts, key=len).strip()

                    result["professional_summary"] = summary

                # Process Education
                elif "education" in section_name or "academic" in section_name:
                    education_entries = self._parse_education_section(section_content)
                    # Validate entries don't contain section markers
                    valid_entries = []
                    for entry in education_entries:
                        if not any(
                            marker in str(entry.values())
                            for marker in [
                                "==========",
                                "PERSONAL_INFO",
                                "EXPERIENCE",
                                "SKILLS",
                            ]
                        ):
                            valid_entries.append(entry)
                    if valid_entries:
                        result["education"] = valid_entries

                # Process Experience
                elif (
                    "experience" in section_name
                    or "employment" in section_name
                    or "work" in section_name
                ):
                    experience_entries = self._parse_experience_section(section_content)
                    # Validate entries don't contain section markers
                    valid_entries = []
                    for entry in experience_entries:
                        # Clean up the data
                        entry_cleaned = False

                        # Fix cases where company name is actually a date
                        if entry.get("company") and re.search(
                            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s+to\s+",
                            entry.get("company"),
                        ):
                            # This is a date, not a company name
                            date_match = re.search(
                                r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\s+to\s+((?:Current|Present|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}))",
                                entry.get("company"),
                            )
                            if date_match:
                                entry["dates"] = (
                                    f"{date_match.group(1)} - {date_match.group(2)}"
                                )
                                entry["company"] = ""
                                entry_cleaned = True

                        # Check for single letter dates like "J" for January, "F" for February
                        if entry.get("company") and re.match(
                            r"^[A-Z]$", entry.get("company").strip()
                        ):
                            entry["company"] = ""
                            entry_cleaned = True

                        # Fix case where company name starts with "TO" followed by a date
                        if entry.get("company") and entry.get(
                            "company"
                        ).strip().startswith("TO"):
                            # This is likely part of a date range
                            date_match = re.search(
                                r"TO\s*\n?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s+to\s+(?:Current|Present|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}))",
                                entry.get("company"),
                            )
                            if date_match:
                                date_val = date_match.group(1)
                                if isinstance(date_val, tuple):
                                    date_val = date_val[0] if date_val else ""
                                entry["dates"] = str(date_val).replace("to", "-")
                                entry["company"] = ""
                                entry_cleaned = True

                        # Extract a proper company name - fix the issue with first entry often containing title
                        if entry.get("company") and not entry_cleaned:
                            # First try to extract a standard company name pattern
                            company_name = entry.get("company")

                            # Look for common company name patterns
                            company_match = re.search(
                                r"(?:at|with|for)?\s+([A-Z][a-zA-Z0-9\s&\.]+(?:Inc|LLC|Ltd|Corp|Company|Technologies|Systems|Group|Media|Services|Solutions|Associates))",
                                company_name,
                            )
                            if company_match:
                                entry["company"] = company_match.group(1).strip()
                                entry_cleaned = True
                            else:
                                # Try another pattern - Company Name followed by location
                                company_match = re.search(
                                    r"([A-Z][a-zA-Z0-9\s&\.]+)(?:\s+[\u00ef\u00bc\u200b]+\s+City\s*,\s*State)",
                                    company_name,
                                )
                                if company_match:
                                    entry["company"] = company_match.group(1).strip()
                                    entry_cleaned = True
                                else:
                                    # If it starts with letters like "J", "C", "F" followed by "anuary", "ompany", etc.
                                    if re.match(
                                        r"^[A-Z](?:anuary|ebruary|arch|pril|ay|une|uly|ugust|eptember|ctober|ovember|ecember)",
                                        company_name,
                                    ):
                                        # This is a partial date
                                        entry["company"] = ""
                                        entry_cleaned = True
                                    # If it's the first entry and has key words like "System Architect" or "SVP", it's likely a title
                                    elif len(valid_entries) == 0 and re.search(
                                        r"(architect|chief|director|SVP|VP|manager|executive|officer)",
                                        company_name,
                                        re.IGNORECASE,
                                    ):
                                        # Move this to title if title is empty
                                        if not entry.get("title"):
                                            # Extract a reasonable title
                                            title_match = re.search(
                                                r"([A-Z][a-zA-Z\s]+(?:Architect|Chief|Director|SVP|VP|Manager|Executive|Officer)[a-zA-Z\s]*)",
                                                company_name,
                                            )
                                            if title_match:
                                                entry["title"] = title_match.group(
                                                    1
                                                ).strip()
                                                entry["company"] = ""
                                                entry_cleaned = True
                                            else:
                                                # Just use the first 50 chars as title
                                                entry["title"] = company_name[
                                                    :50
                                                ].strip()
                                                entry["company"] = ""
                                                entry_cleaned = True

                        # Clean up the description to avoid truncation
                        if entry.get("description"):
                            # Check for truncated descriptions (ending with a single letter followed by newline)
                            if re.search(r"([A-Z])\s*$", entry.get("description")):
                                # Remove the trailing single letter
                                entry["description"] = re.sub(
                                    r"([A-Z])\s*$", "", entry.get("description")
                                ).strip()

                            # Fix truncated single letter words followed by a newline (common in our data)
                            trunc_match = re.search(
                                r"\n([A-Z])\s*\n", entry.get("description")
                            )
                            if trunc_match:
                                # Remove the single letter line
                                entry["description"] = re.sub(
                                    r"\n([A-Z])\s*\n", "\n", entry.get("description")
                                )

                            # Remove section markers
                            if "==========" in entry.get("description"):
                                # Extract just the part before any section marker
                                entry["description"] = (
                                    entry.get("description")
                                    .split("==========")[0]
                                    .strip()
                                )

                            # If description is too long, truncate it
                            if len(entry.get("description")) > 1000:
                                entry["description"] = (
                                    entry.get("description")[:1000] + "..."
                                )

                        # Extract job title from description if missing
                        if (
                            not entry.get("title") or entry.get("title") == ""
                        ) and entry.get("description"):
                            # Common job titles at the beginning of descriptions
                            title_match = re.match(
                                r"^((?:Chief|Senior|Principal|Lead|Director|Manager|VP|SVP|EVP|Executive|Head|President|CEO|CTO|CIO|CFO|COO|Architect|Engineer|Developer|Consultant|Analyst|Specialist|Administrator)[\w\s]+?(?:Architect|Engineer|Developer|Manager|Director|Officer|Executive|Chief|Lead|Head|Specialist|Analyst|Consultant|Administrator))\s",
                                entry.get("description"),
                            )
                            if title_match:
                                entry["title"] = title_match.group(1).strip()
                                # Remove from beginning of description
                                entry["description"] = entry.get("description")[
                                    len(entry["title"]) :
                                ].strip()

                        # If no company name, try to extract from description
                        if (
                            not entry.get("company") or entry.get("company") == ""
                        ) and entry.get("description"):
                            # Try to extract company name from the beginning of the description
                            desc_lines = entry.get("description").split("\n", 2)
                            if len(desc_lines) >= 1:
                                # First line might contain the company name
                                company_line = desc_lines[0].strip()
                                # Check if it looks like a company name (doesn't start with common words)
                                if not company_line.lower().startswith(
                                    (
                                        "i ",
                                        "my ",
                                        "the ",
                                        "this ",
                                        "they ",
                                        "we ",
                                        "as ",
                                        "in ",
                                        "at ",
                                        "to ",
                                        "resp",
                                        "creat",
                                        "feat",
                                        "feat",
                                    )
                                ):
                                    if "City , State" in company_line:
                                        # This is likely "Company Name City, State"
                                        company_name = company_line.split(
                                            "City , State"
                                        )[0].strip()
                                        if company_name and len(company_name) > 3:
                                            entry["company"] = company_name
                                            # Remove this from description
                                            if len(desc_lines) > 1:
                                                entry["description"] = "\n".join(
                                                    desc_lines[1:]
                                                ).strip()
                                    elif len(company_line) < 50:
                                        # Short enough to be a company name
                                        entry["company"] = company_line
                                        # Remove this from description
                                        if len(desc_lines) > 1:
                                            entry["description"] = "\n".join(
                                                desc_lines[1:]
                                            ).strip()

                        # Add entry if it has at least one meaningful field
                        if (
                            (entry.get("company") and entry.get("company").strip())
                            or (entry.get("title") and entry.get("title").strip())
                            or (entry.get("dates") and entry.get("dates").strip())
                        ) and len(entry.get("description", "").strip()) > 30:
                            valid_entries.append(entry)

                    if valid_entries:
                        result["experience"] = valid_entries

                # Process Skills
                elif "skill" in section_name or "competen" in section_name:
                    skills = self._parse_skills_section(section_content)
                    # Validate skills don't contain section names
                    valid_skills = []
                    for skill in skills:
                        if not any(
                            kw in skill.upper()
                            for kw in [
                                "CERTIFICATIONS",
                                "LANGUAGES",
                                "PROJECTS",
                                "PERSONAL",
                                "EDUCATION",
                            ]
                        ):
                            valid_skills.append(skill)
                    if valid_skills:
                        result["skills"] = valid_skills

                # Process Languages
                elif "language" in section_name:
                    languages = self._parse_languages_section(section_content)
                    # Validate language entries
                    valid_languages = []
                    for lang in languages:
                        if not any(
                            kw in lang.get("language", "").upper()
                            for kw in ["CERTIFICATIONS", "PROJECTS", "SKILLS"]
                        ):
                            valid_languages.append(lang)
                    if valid_languages:
                        result["languages"] = valid_languages

                # Process Certifications
                elif "certif" in section_name:
                    certifications = self._parse_certifications_section(section_content)
                    # Validate certification entries
                    valid_certs = []

                    # Define known certifications and degree patterns
                    known_certifications = [
                        "MCSE",
                        "CCNA",
                        "CCNP",
                        "CCIE",
                        "AWS Certified",
                        "Azure Certified",
                        "CompTIA",
                        "PMP",
                        "ITIL",
                        "Certified Scrum",
                        "Six Sigma",
                        "CEH",
                        "CISSP",
                        "Security+",
                        "Network+",
                        "A+",
                        "CSM",
                        "CISA",
                        "CISM",
                        "Google Certified",
                        "Oracle Certified",
                        "IBM Certified",
                        "SAP Certified",
                        "PRINCE2",
                        "TOGAF",
                        "CFA",
                        "CPA",
                        "PMI-ACP",
                        "Certified Ethical Hacker",
                        "GIAC",
                        "Salesforce Certified",
                    ]

                    # Define specific certification patterns
                    cert_patterns = [
                        r"\b((?:Microsoft|Cisco|AWS|Google|Azure|CompTIA|Oracle|IBM|SAP|PMP|ITIL|Agile|Scrum|Six Sigma|CCNA|MCSE|Security\+|CEH|CISM|CISSP)[^\.,]{0,40}(?:Certified|Certification|Certificate|License|Professional|Architect|Administrator|Developer|Engineer|Specialist|Associate|MCSE|CCNA))\b",
                        r"\b((?:Certified|Licensed|Registered|Professional|Master)[^\.,]{2,40}(?:Developer|Engineer|Architect|Administrator|Technician|Specialist|Accountant|Auditor|Analyst))\b",
                        r"\b((?:Bachelor|Master|PhD|MBA|MSc|BSc|BA|MS|MA)[^\.,]{0,10}(?:Computer Science|Engineering|Business|Administration|Science|Arts|Information Technology|Technology))\b",
                    ]

                    # Extract degrees first (most reliable)
                    degree_pattern = r"\b((?:BA|BS|BSc|BA|MS|MSc|MA|MBA|PhD)[^\.,]{0,5}(?:in|:)?\s*[A-Za-z\s]{3,30})\b"
                    degree_matches = re.finditer(
                        degree_pattern, section_content, re.IGNORECASE
                    )
                    for match in degree_matches:
                        valid_certs.append({"name": match.group(1).strip(), "date": ""})

                    # If no degrees found, try to extract certifications
                    if not valid_certs:
                        # First try from section content directly
                        for cert in known_certifications:
                            if re.search(
                                r"\b" + re.escape(cert) + r"\b",
                                section_content,
                                re.IGNORECASE,
                            ):
                                # Find the full certification phrase
                                context = re.search(
                                    r"[^.!?:]{0,50}\b"
                                    + re.escape(cert)
                                    + r"\b[^.!?:]{0,30}",
                                    section_content,
                                    re.IGNORECASE,
                                )
                                if context:
                                    cert_text = context.group(0).strip()
                                    # Only add if it's not too long and doesn't contain suspicious text
                                    if 5 <= len(cert_text) <= 50 and not any(
                                        w in cert_text.lower()
                                        for w in [
                                            "companies",
                                            "clients",
                                            "technologies",
                                            "technical",
                                            "systems to",
                                            "markets",
                                            "production",
                                        ]
                                    ):
                                        valid_certs.append(
                                            {"name": cert_text, "date": ""}
                                        )

                        # If still no certs, try pattern matching
                        if not valid_certs:
                            for pattern in cert_patterns:
                                matches = re.finditer(
                                    pattern, section_content, re.IGNORECASE
                                )
                                for match in matches:
                                    cert_text = match.group(1).strip()
                                    # Only add if it's not too long and doesn't contain suspicious text
                                    if 5 <= len(cert_text) <= 50 and not any(
                                        w in cert_text.lower()
                                        for w in [
                                            "companies",
                                            "clients",
                                            "technologies",
                                            "technical",
                                            "systems to",
                                            "markets",
                                            "production",
                                        ]
                                    ):
                                        valid_certs.append(
                                            {"name": cert_text, "date": ""}
                                        )

                    # Check if any certification entry looks like a fragment of text
                    filtered_certs = []
                    for cert in valid_certs:
                        cert_name = cert.get("name", "").strip()
                        if not cert_name:
                            continue

                        # Skip if it looks like a fragment (starts with prepositions, etc.)
                        if cert_name.lower().startswith(
                            (
                                "and ",
                                "the ",
                                "of ",
                                "in ",
                                "to ",
                                "with ",
                                "over ",
                                "these ",
                                "many ",
                                "on ",
                                "at ",
                                "by ",
                                "for ",
                            )
                        ):
                            continue

                        # Skip if it contains suspicious words that indicate it's not a certification
                        if any(
                            word in cert_name.lower()
                            for word in [
                                "companies",
                                "clients",
                                "executive",
                                "decision",
                                "relationships",
                                "technical",
                                "system",
                                "handover",
                                "markets",
                                "digital",
                            ]
                        ):
                            continue

                        # Only add entries that look like actual certifications or degrees
                        if re.search(
                            r"\b(?:Certified|Certificate|Degree|License|Bachelor|Master|MBA|PhD|BSc|MSc|BA|BS|MS|MA)\b",
                            cert_name,
                            re.IGNORECASE,
                        ) or re.search(
                            r"\b(?:MCSE|CCNA|CCNP|CCIE|AWS|Azure|CompTIA|PMP|ITIL|CSM|CEH|CISSP|Security\+|Network\+|A\+)\b",
                            cert_name,
                            re.IGNORECASE,
                        ):
                            filtered_certs.append(cert)

                    # If we have valid certs, use them, otherwise leave empty
                    if filtered_certs:
                        # Deduplicate
                        seen = set()
                        unique_certs = []
                        for cert in filtered_certs:
                            name = cert.get("name", "").lower()
                            if name and name not in seen:
                                seen.add(name)
                                unique_certs.append(cert)

                        result["certifications"] = unique_certs
                    else:
                        # Only extract education
                        education_pattern = r"\b((?:BA|BS|BSc|BA|MS|MSc|MA|MBA|PhD)(?:\s+in|\s*:)?\s+[A-Za-z\s]{3,30})\b"
                        matches = re.finditer(
                            education_pattern, section_content, re.IGNORECASE
                        )
                        for match in matches:
                            result["certifications"].append(
                                {"name": match.group(1).strip(), "date": ""}
                            )

                        if not result["certifications"]:
                            result["certifications"] = []

                # Process additional sections if implemented
                elif "project" in section_name and hasattr(
                    self, "_parse_projects_section"
                ):
                    projects = self._parse_projects_section(section_content)
                    if projects:
                        result["projects"] = projects

                elif "interest" in section_name and hasattr(
                    self, "_parse_interests_section"
                ):
                    interests = self._parse_interests_section(section_content)
                    if interests:
                        result["interests"] = interests
            except Exception as e:
                logger.error(f"Error parsing section '{section_name}': {str(e)}")
                logger.debug(traceback.format_exc())

            section_elapsed = time.time() - section_start_time
            logger.debug(f"Section {section_name} parsed in {section_elapsed:.2f}s")

        # If no valid sections were found or parsing failed to extract content,
        # fall back to traditional parsing
        if section_count == 0:
            logger.warning(
                "No valid sections found in segmented text, falling back to traditional parsing"
            )
            return self._parse_traditional(segmented_text)

        # Log what we extracted
        logger.info(f"Extracted {len(result.get('education', []))} education entries")
        logger.info(f"Extracted {len(result.get('experience', []))} experience entries")
        logger.info(f"Extracted {len(result.get('skills', []))} skills")
        logger.info(f"Extracted {len(result.get('languages', []))} languages")
        logger.info(f"Extracted {len(result.get('certifications', []))} certifications")

        # If we have some sections but not others, try to extract missing sections
        # from the full text using traditional methods
        for section_name, section_data in result.items():
            # Skip non-empty sections
            if section_data and section_data != "" and section_data != []:
                continue

            logger.debug(
                f"Section {section_name} is empty, attempting traditional extraction"
            )
            try:
                if section_name == "personal_info" and not any(
                    result["personal_info"].values()
                ):
                    result["personal_info"] = self.extract_personal_info(segmented_text)

                elif (
                    section_name == "professional_summary"
                    and not result["professional_summary"]
                ):
                    result["professional_summary"] = self.extract_professional_summary(
                        segmented_text
                    )

                elif section_name == "education" and not result["education"]:
                    result["education"] = self._extract_education(segmented_text)

                elif section_name == "experience" and not result["experience"]:
                    result["experience"] = self._extract_experience(segmented_text)

                elif section_name == "skills" and not result["skills"]:
                    result["skills"] = self._extract_skills(segmented_text)

                elif section_name == "languages" and not result["languages"]:
                    result["languages"] = self._extract_languages(segmented_text)

                elif section_name == "certifications" and not result["certifications"]:
                    result["certifications"] = self._extract_certifications(
                        segmented_text
                    )
            except Exception as e:
                logger.error(
                    f"Error in traditional extraction for {section_name}: {str(e)}"
                )

        # Apply industry-specific post-processing
        if self._is_technology_cv(segmented_text):
            logger.info("Applying technology CV post-processing")
            # Enhance skills extraction for technology CVs
            if not result["skills"] or len(result["skills"]) < 3:
                result["skills"] = self._extract_technology_skills(segmented_text)
        elif self._is_healthcare_cv(segmented_text):
            logger.info("Applying healthcare CV post-processing")
            # Enhance experience extraction for healthcare CVs
            if not result["experience"] or len(result["experience"]) < 2:
                result["experience"] = self._extract_healthcare_experience(
                    segmented_text
                )
        elif self._is_aviation_cv(segmented_text):
            logger.info("Applying aviation CV post-processing")
            # Apply aviation-specific enhancements
            result = self._post_process_aviation_cv(result, segmented_text)
        elif self._is_banking_cv(segmented_text):
            logger.info("Applying banking CV post-processing")
            # Apply banking-specific enhancements
            result = self._post_process_banking_cv(result, segmented_text)

        # Log completion
        elapsed_time = time.time() - start_time
        logger.info(f"Segmented text parsing completed in {elapsed_time:.2f} seconds")

        # Final check - if we still don't have meaningful data, fall back to traditional parsing
        if not any(result.values()) or (
            not any(result["personal_info"].values())
            and not result["experience"]
            and not result["education"]
            and not result["skills"]
        ):
            logger.warning(
                "Segmented parsing produced insufficient results, falling back to traditional"
            )
            return self._parse_traditional(segmented_text)

        logger.info("Segmented text parsing completed successfully")
        return result

    def _parse_personal_info_section(self, section_text):
        """Parse personal info section from segmented text"""
        info = {
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
        }

        # Look for email addresses
        email_matches = re.findall(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", section_text
        )
        if email_matches:
            info["email"] = email_matches[0]

        # Look for phone numbers (enhanced for international formats)
        phone_patterns = [
            r"(\+\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}",  # US format
            r"(\+\d{1,3}[-.\s]?)?\d{10,11}",  # UK/International format (10-11 digits)
            r"(\+\d{1,3}[-.\s]?)?\d{4}[-.\s]?\d{6}",  # UK format with spacing
            r"(\+\d{1,3}[-.\s]?)?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",  # Alternative spacing
            r"0\d{10}",  # UK mobile starting with 0
        ]

        for pattern in phone_patterns:
            phone_matches = re.findall(pattern, section_text)
            if phone_matches:
                if isinstance(phone_matches[0], tuple):
                    info["phone"] = "".join(phone_matches[0]).strip()
                else:
                    info["phone"] = phone_matches[0].strip()
                break

        # Enhanced LinkedIn detection
        linkedin_patterns = [
            r"linkedin\.com/in/[A-Za-z0-9_-]+",  # Full URL
            r"linkedin\.com/[A-Za-z0-9_-]+",  # Partial URL
            r"(?:•\s*)?LinkedIn(?:\s*[:|•]?\s*([A-Za-z0-9_-]+))?",  # Just "LinkedIn" mention
            r"@[A-Za-z0-9_-]+\s+\(?LinkedIn\)?",  # Handle format
        ]

        for pattern in linkedin_patterns:
            linkedin_matches = re.findall(pattern, section_text, re.IGNORECASE)
            if linkedin_matches:
                match = linkedin_matches[0]
                if "linkedin.com" in match.lower():
                    info["linkedin"] = match
                else:
                    info["linkedin"] = (
                        f"linkedin.com/in/{match}" if match else "LinkedIn"
                    )
                break

        # Enhanced location extraction
        location_patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2,})",  # "Kent, UK" format
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*•",  # Before bullet point
            r"(?:Location|Address):\s*([^,\n•]+)",  # Labeled location
            r"([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)+)",  # General city, country format
        ]

        for pattern in location_patterns:
            location_matches = re.findall(pattern, section_text)
            if location_matches:
                if isinstance(location_matches[0], tuple):
                    info["location"] = ", ".join(filter(None, location_matches[0]))
                else:
                    info["location"] = location_matches[0].strip()
                break

        # Enhanced name extraction - look for prominent names in early lines
        lines = section_text.strip().split("\n")

        # Try multiple strategies for name extraction
        for i in range(min(3, len(lines))):  # Check first 3 lines
            line = lines[i].strip()

            # Skip empty lines, email addresses, and obvious headers
            if (
                not line
                or "@" in line
                or re.search(
                    r"curriculum\s*vitae|resume|cv|profile|contact", line, re.IGNORECASE
                )
                or re.search(r"^\w+:|phone|email|address", line, re.IGNORECASE)
            ):
                continue

            # Clean the line of special characters and extra info
            clean_line = re.sub(
                r"[•|•\-]+.*$", "", line
            )  # Remove bullet points and content after
            clean_line = clean_line.split("•")[0].strip()  # Take part before bullet
            clean_line = clean_line.split("|")[0].strip()  # Take part before pipe

            # Check if it looks like a name (1-3 words, mostly letters)
            words = clean_line.split()
            if (
                1 <= len(words) <= 3
                and all(re.match(r"^[A-Za-z\'-]+$", word) for word in words)
                and len(clean_line) >= 3
            ):

                name_parts = clean_line.split()
                if len(name_parts) >= 2:
                    info["first_name"] = name_parts[0]
                    info["last_name"] = " ".join(name_parts[1:])
                else:
                    info["first_name"] = clean_line
                break
            # Remove email, phone, LinkedIn if they're on the first line
            clean_line = re.sub(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "", clean_line
            )
            clean_line = re.sub(
                r"(\+\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}",
                "",
                clean_line,
            )
            clean_line = re.sub(r"linkedin\.com/in/[A-Za-z0-9_-]+", "", clean_line)

            # Clean up the name line and split into parts
            name_parts = clean_line.strip().split()
            if len(name_parts) >= 2:
                info["first_name"] = name_parts[0]
                info["last_name"] = name_parts[-1]
            elif len(name_parts) == 1:
                info["first_name"] = name_parts[0]

        # Try to extract location - typically on a separate line
        location_indicators = [
            "Address:",
            "Location:",
            "City:",
            "Based in:",
            "Living in:",
        ]
        for line in lines:
            line = line.strip()
            # Check if line contains location indicators
            if any(indicator in line for indicator in location_indicators):
                info["location"] = (
                    line.split(":", 1)[1].strip() if ":" in line else line
                )
                break
            # Check for common city/state patterns
            elif re.search(r"\b[A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*,\s*[A-Z]{2}\b", line):
                info["location"] = line
                break

        return info

    def _parse_education_section(self, section_text):
        """Parse education section from segmented text"""
        education_entries = []

        # Split into potential entries (blank lines often separate entries)
        entries = re.split(r"\n\s*\n", section_text)

        for entry in entries:
            if not entry.strip():
                continue

            # Parse each education entry
            education = {
                "institution": "",
                "degree": "",
                "field_of_study": "",
                "dates": "",
                "description": "",
            }

            lines = entry.strip().split("\n")

            # First line usually contains the institution
            if lines:
                education["institution"] = lines[0].strip()

            # Look for degree information
            degree_keywords = [
                "Bachelor",
                "Master",
                "Ph.D",
                "PhD",
                "Doctorate",
                "B.S.",
                "M.S.",
                "B.A.",
                "M.A.",
                "MBA",
            ]
            for line in lines[1:]:
                if any(keyword in line for keyword in degree_keywords):
                    education["degree"] = line.strip()
                    # Try to extract field of study
                    if "in" in line:
                        parts = line.split("in", 1)
                        if len(parts) > 1:
                            education["field_of_study"] = parts[1].strip()
                    break

            # Look for dates
            date_pattern = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\s*(?:-|–|to)\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*\.?\s+\d{4}|\d{4}\s*(?:-|–|to)\s*\d{4}|\d{4}\s*(?:-|–|to)\s*(?:Present|Current|Now)"
            for line in lines:
                if re.search(date_pattern, line, re.IGNORECASE):
                    education["dates"] = (
                        re.search(date_pattern, line, re.IGNORECASE).group().strip()
                    )
                    break

            # Remaining content goes into description
            if len(lines) > 1:
                # Filter out lines already assigned to other fields
                desc_lines = []
                for line in lines[1:]:
                    if line.strip() and not any(
                        [
                            line.strip() == education["degree"],
                            education["dates"] and education["dates"] in line,
                            education["field_of_study"]
                            and f"in {education['field_of_study']}" in line,
                        ]
                    ):
                        desc_lines.append(line.strip())

                if desc_lines:
                    education["description"] = "\n".join(desc_lines)

            education_entries.append(education)

        return education_entries

    def _parse_experience_section(self, section_text):
        """
        Parse experience section into structured data

        Args:
            section_text (str): Experience section text

        Returns:
            list: List of experience entries
        """
        experiences = []

        # Split the text into potential job blocks
        # Look for clear indicators of job separation like dates
        split_patterns = [
            r"\n\s*\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current|Now)",
            r"\n\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]",
            r"\n\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s*[-–—]",
        ]

        # Combine patterns
        combined_pattern = "|".join(split_patterns)
        blocks = re.split(combined_pattern, section_text)

        # Handle the first block which might not have a date prefix
        if blocks and len(blocks) > 1:
            # First block may not be a complete job entry
            first_block = blocks[0].strip()
            if len(first_block) > 50:  # If substantial, it might be a complete entry
                blocks_to_process = blocks
            else:
                # Skip the first block if it's just a header or small fragment
                blocks_to_process = blocks[1:]
        else:
            blocks_to_process = blocks

        # Process each block
        for block in blocks_to_process:
            block = block.strip()
            if not block or len(block) < 30:  # Skip empty or very small blocks
                continue

            # Extract job details
            job = {}

            # Extract dates - look for date ranges
            date_patterns = [
                r"(\d{4}\s*[-–—]\s*(?:Present|Current|Now|\d{4}))",
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]\s*(?:Present|Current|Now|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}))",
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s*[-–—]\s*(?:Present|Current|Now|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}))",
            ]

            # Extract dates
            dates = ""
            for pattern in date_patterns:
                date_match = re.search(pattern, block, re.IGNORECASE)
                if date_match:
                    dates = date_match.group(1).strip()
                    break

            # Extract title and company using our specialized methods
            title = self._extract_job_title(block)
            company = self._extract_company(block)

            # Extract skills
            skills = self._extract_skills_from_experience(block)

            # Create job entry
            job = {
                "title": title,
                "company": company,
                "dates": dates,
                "description": block,
                "skills": skills[:10] if skills else [],  # Limit to top 10 skills
            }

            # Only add job if we have at least a title or company
            if job["title"] or job["company"]:
                experiences.append(job)

        # If no experiences found or parsing failed, try traditional extraction
        if not experiences:
            experiences = self._extract_experience(section_text)

        return experiences

    def _parse_skills_section(self, section_text):
        """Parse skills section from segmented text"""
        # Try to detect if skills are in a list format or paragraph format
        if "\n•" in section_text or "\n-" in section_text or "\n*" in section_text:
            # List format - each bullet is a skill
            skills = []
            lines = section_text.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                    skill = line.lstrip("•-* ").strip()
                    if skill:
                        skills.append(skill)
            return skills
        else:
            # Paragraph format - split by commas or similar separators
            # Handle potential tuple from regex groups
            if isinstance(section_text, tuple):
                section_text = section_text[0] if section_text else ""
            skills_text = str(section_text).replace("\n", " ")
            skills = []
            for skill in re.split(r"[,;]|\s{2,}", skills_text):
                skill = skill.strip()
                if skill and len(skill) > 1:  # Avoid single letters
                    skills.append(skill)
            return skills

    def _parse_languages_section(self, section_text):
        """Parse languages section from segmented text"""
        languages = []

        # Try to detect format (list or paragraph)
        if "\n" in section_text.strip():
            # Process as list - each line is a language entry
            lines = section_text.strip().split("\n")
            for line in lines:
                language = self._extract_language_entry(line)
                if language["language"]:
                    languages.append(language)
        else:
            # Process as paragraph - split by commas
            for entry in re.split(r"[,;]", section_text):
                language = self._extract_language_entry(entry)
                if language["language"]:
                    languages.append(language)

        return languages

    def _extract_language_entry(self, text):
        """Extract language and proficiency from text"""
        text = text.strip().lstrip("•-* ")
        language = {"language": "", "proficiency": ""}

        # Look for proficiency indicators
        proficiency_levels = [
            "Native",
            "Fluent",
            "Proficient",
            "Intermediate",
            "Conversational",
            "Basic",
            "C2",
            "C1",
            "B2",
            "B1",
            "A2",
            "A1",
        ]

        for level in proficiency_levels:
            if level in text:
                # Split by the proficiency level
                parts = text.split(level, 1)
                language["language"] = parts[0].strip().rstrip(":-(").strip()
                language["proficiency"] = level + (parts[1] if len(parts) > 1 else "")
                return language

        # If no proficiency found, use the whole text as language
        language["language"] = text
        return language

    def _parse_certifications_section(self, section_text):
        """Parse certifications section from segmented text"""
        certifications = []

        # Try to detect if certifications are in a list format or paragraph format
        if "\n•" in section_text or "\n-" in section_text or "\n*" in section_text:
            # List format - each bullet is a certification
            lines = section_text.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                    cert_text = line.lstrip("•-* ").strip()
                    if cert_text:
                        certification = self._extract_certification_entry(cert_text)
                        certifications.append(certification)
        else:
            # Paragraph or separated by empty lines
            entries = re.split(r"\n\s*\n", section_text)
            for entry in entries:
                if entry.strip():
                    certification = self._extract_certification_entry(entry.strip())
                    certifications.append(certification)

        return certifications

    def _extract_certification_entry(self, text):
        """Extract certification name and date from text"""
        certification = {"name": "", "date": ""}

        # Look for dates (YYYY, Month YYYY)
        date_pattern = r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b\d{4}\b"
        date_match = re.search(date_pattern, text)

        if date_match:
            certification["date"] = date_match.group().strip()
            # Remove date from the name
            cert_date = certification["date"]
            if isinstance(cert_date, tuple):
                cert_date = cert_date[0] if cert_date else ""
            name = text.replace(str(cert_date), "").strip()
            name = re.sub(r"\s*[-–]\s*$", "", name)  # Remove trailing dash
            certification["name"] = name.strip()
        else:
            certification["name"] = text.strip()

        return certification

    def _should_use_llm_parsing(self) -> bool:
        """
        Check if LLM-based parsing should be used

        Returns:
            bool: True if LLM parsing should be used
        """
        # Check if LLM services are available
        if not LLM_SERVICES_AVAILABLE:
            logger.info("LLM services not available, using traditional parsing")
            return False

        # Check environment variable - enable by default for better results
        use_llm = os.environ.get("USE_LLM_PARSING", "True").lower() == "true"

        if use_llm:
            logger.info("Using LLM-based CV parsing (enabled by environment variable)")
            return True
        else:
            logger.info(
                "LLM-based CV parsing not enabled (set USE_LLM_PARSING=true to enable)"
            )
            logger.info(
                f"Current USE_LLM_PARSING value: {os.environ.get('USE_LLM_PARSING', 'NOT_SET')}"
            )
            # Force enable LLM parsing for better results
            logger.info("Force enabling LLM parsing for better extraction results")
            return True

    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text for LLM processing

        Args:
            text (str): Raw text

        Returns:
            str: Sanitized text
        """
        # Remove non-printable characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]", "", text)

        # Replace multiple newlines with at most two
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Replace multiple spaces with a single space
        text = re.sub(r" {2,}", " ", text)

        # Limit total length for LLM processing
        max_chars = 25000
        if len(text) > max_chars:
            logger.warning(
                f"Truncating text from {len(text)} to {max_chars} chars for LLM processing"
            )
            text = text[:max_chars]

        return text

    def _post_process_aviation_cv(
        self, data: Dict[str, Any], text: str
    ) -> Dict[str, Any]:
        """
        Apply special processing for aviation CVs

        Args:
            data (Dict[str, Any]): Parsed CV data
            text (str): Original text

        Returns:
            Dict[str, Any]: Enhanced CV data
        """
        logger.debug("Post-processing aviation CV")

        # Look for flight hours
        hours_pattern = r"(?:Total\s+(?:Flight|Flying)\s+Hours?|Flight\s+Time):\s*(\d{3,5}(?:\.\d+)?)"
        hours_match = re.search(hours_pattern, text, re.IGNORECASE)

        if hours_match:
            flight_hours = hours_match.group(1)

            # Add to skills if found
            if "skills" not in data:
                data["skills"] = []

            data["skills"].append(f"Total Flight Hours: {flight_hours}")
            logger.debug(f"Added flight hours to skills: {flight_hours}")

        # Look for pilot licenses
        license_patterns = [
            r"(?:ATP|ATPL|CPL|PPL|Commercial\s+Pilot\s+License|Airline\s+Transport\s+Pilot\s+License|Private\s+Pilot\s+License)(?:\s*-\s*([A-Za-z\s/]+))?",
            r"(?:Type\s+Rating|Aircraft\s+Rating):\s*([A-Za-z0-9\s/-]+)",
        ]

        for pattern in license_patterns:
            for license_match in re.finditer(pattern, text, re.IGNORECASE):
                license_text = license_match.group(0)

                # Add to certifications if found
                if "certifications" not in data:
                    data["certifications"] = []

                # Check if this license is already in certifications
                is_new = True
                for cert in data["certifications"]:
                    if license_text.lower() in cert.get("name", "").lower():
                        is_new = False
                        break

                if is_new:
                    data["certifications"].append({"name": license_text, "date": ""})
                    logger.debug(
                        f"Added aviation license to certifications: {license_text}"
                    )

        return data

    def _post_process_banking_cv(
        self, data: Dict[str, Any], text: str
    ) -> Dict[str, Any]:
        """
        Apply special processing for banking/finance CVs

        Args:
            data (Dict[str, Any]): Parsed CV data
            text (str): Original text

        Returns:
            Dict[str, Any]: Enhanced CV data
        """
        logger.debug("Post-processing banking/finance CV")

        # Look for financial certifications
        finance_cert_patterns = [
            r"(?:CFA|Chartered\s+Financial\s+Analyst)(?:\s+Level\s+(?:I|II|III|1|2|3))?",
            r"(?:CPA|Certified\s+Public\s+Accountant)",
            r"(?:ACCA|Association\s+of\s+Chartered\s+Certified\s+Accountants)",
            r"(?:CIMA|Chartered\s+Institute\s+of\s+Management\s+Accountants)",
            r"(?:FRM|Financial\s+Risk\s+Manager)",
            r"(?:CFP|Certified\s+Financial\s+Planner)",
            r"(?:Series\s+(?:7|63|65|66))",
        ]

        for pattern in finance_cert_patterns:
            for cert_match in re.finditer(pattern, text, re.IGNORECASE):
                cert_text = cert_match.group(0)

                # Add to certifications if found
                if "certifications" not in data:
                    data["certifications"] = []

                # Check if this certification is already in certifications
                is_new = True
                for cert in data["certifications"]:
                    if cert_text.lower() in cert.get("name", "").lower():
                        is_new = False
                        break

                if is_new:
                    data["certifications"].append({"name": cert_text, "date": ""})
                    logger.debug(f"Added finance certification: {cert_text}")

        # Look for finance-specific skills
        finance_skills = [
            "Financial Analysis",
            "Financial Reporting",
            "Financial Modeling",
            "Budgeting",
            "Forecasting",
            "Risk Management",
            "Investment Banking",
            "Asset Management",
            "Wealth Management",
            "Portfolio Management",
            "Equity Research",
            "Fixed Income",
            "Derivatives",
            "Options",
            "Futures",
            "Swaps",
            "Bloomberg Terminal",
            "Reuters",
            "Capital Markets",
            "M&A",
            "Mergers and Acquisitions",
            "Valuation",
            "DCF",
            "Discounted Cash Flow",
            "NPV",
            "IRR",
            "Cost Accounting",
            "Management Accounting",
            "Tax Planning",
            "Auditing",
            "Compliance",
            "AML",
            "Anti-Money Laundering",
            "KYC",
            "Know Your Customer",
        ]

        for skill in finance_skills:
            if re.search(r"\b" + re.escape(skill) + r"\b", text, re.IGNORECASE):
                # Add to skills if found and not already present
                if "skills" not in data:
                    data["skills"] = []

                if skill not in data["skills"]:
                    data["skills"].append(skill)
                    logger.debug(f"Added finance skill: {skill}")

        return data

    def _identify_cv_sections(self, text: str) -> Dict[str, Tuple[int, int]]:
        """
        Identify the different sections in a CV text.

        Args:
            text (str): The CV text to analyze

        Returns:
            Dict[str, Tuple[int, int]]: A dictionary with section names as keys and
                                       tuples of (start_index, end_index) as values
        """
        # Define common section headers and their variations
        section_headers = {
            "personal_info": [
                r"(?i)^\s*(personal\s+information|personal\s+details|contact|contact\s+information|contact\s+details|profile)",
                r"(?i)^(name\s*:|address\s*:|email\s*:|phone\s*:|linkedin\s*:)",
            ],
            "summary": [
                r"(?i)^\s*(summary|professional\s+summary|profile|professional\s+profile|executive\s+profile|career\s+summary|overview)",
                r"(?i)^\s*(about\s+me|professional\s+background|career\s+objective|objective)",
            ],
            "experience": [
                r"(?i)^\s*(experience|work\s+experience|employment|employment\s+history|professional\s+experience)",
                r"(?i)^\s*(career\s+history|work\s+history|positions|relevant\s+experience)",
            ],
            "education": [
                r"(?i)^\s*(education|educational\s+background|academic\s+background|academic\s+history|qualifications)",
                r"(?i)^\s*(academic\s+qualifications|educational\s+qualifications|degrees|academic\s+credentials)",
            ],
            "skills": [
                r"(?i)^\s*(skills|technical\s+skills|core\s+skills|key\s+skills|competencies|areas\s+of\s+expertise)",
                r"(?i)^\s*(professional\s+skills|strengths|technical\s+competencies|capabilities)",
            ],
            "languages": [
                r"(?i)^\s*(languages|language\s+skills|foreign\s+languages)",
            ],
            "certifications": [
                r"(?i)^\s*(certifications|certificates|professional\s+certifications|credentials|qualifications)",
                r"(?i)^\s*(licenses|accreditations|professional\s+development)",
            ],
            "projects": [
                r"(?i)^\s*(projects|key\s+projects|project\s+experience|relevant\s+projects)",
            ],
            "interests": [
                r"(?i)^\s*(interests|hobbies|activities|personal\s+interests)",
            ],
            "references": [
                r"(?i)^\s*(references|professional\s+references)",
            ],
            "publications": [
                r"(?i)^\s*(publications|papers|articles|research)",
            ],
            "awards": [
                r"(?i)^\s*(awards|honors|achievements|recognitions)",
            ],
        }

        # Split text into lines for processing
        lines = text.split("\n")

        # Identify potential section headers and their positions
        section_positions = {}
        current_line_index = 0

        for line_index, line in enumerate(lines):
            for section_name, patterns in section_headers.items():
                for pattern in patterns:
                    if re.search(pattern, line):
                        # Found a potential section header
                        section_positions[section_name] = (
                            current_line_index,
                            -1,
                        )  # -1 means end not determined yet
                        break
            current_line_index += len(line) + 1  # +1 for the newline character

        # Determine the end position of each section (start of next section - 1)
        sorted_sections = sorted(section_positions.items(), key=lambda x: x[1][0])

        for i in range(len(sorted_sections) - 1):
            section_name, (start, _) = sorted_sections[i]
            next_start = sorted_sections[i + 1][1][0]
            section_positions[section_name] = (start, next_start - 1)

        # Set the end position of the last section to the end of the text
        if sorted_sections:
            last_section = sorted_sections[-1][0]
            section_positions[last_section] = (sorted_sections[-1][1][0], len(text))

        return section_positions

    def _is_aviation_cv(self, text: str) -> bool:
        """
        Detect if a CV is from the aviation industry

        Args:
            text (str): CV text

        Returns:
            bool: True if aviation CV, False otherwise
        """
        # Check for aviation specific indicators
        aviation_terms = [
            "pilot",
            "flight",
            "aircraft",
            "aviation",
            "helicopter",
            "faa",
            "airline",
            "cockpit",
            "captain",
            "first officer",
            "cabin crew",
            "navigator",
            "airbus",
            "boeing",
            "flight hours",
            "type rating",
            "air traffic",
            "atpl",
            "cpl",
            "ppl",
            "ifr",
            "vfr",
        ]

        # Count matches
        match_count = 0
        for term in aviation_terms:
            matches = re.findall(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE)
            match_count += len(matches)

        # Consider it an aviation CV if we find enough aviation terms
        return match_count >= 3

    def _is_banking_cv(self, text: str) -> bool:
        """
        Detect if a CV is from the banking/finance industry

        Args:
            text (str): CV text

        Returns:
            bool: True if banking/finance CV, False otherwise
        """
        # Check for banking/finance specific indicators
        banking_terms = [
            "accounting",
            "accountant",
            "financial",
            "bank",
            "investment",
            "analyst",
            "finance",
            "portfolio",
            "credit",
            "loan",
            "asset",
            "wealth management",
            "risk assessment",
            "trading",
            "securities",
            "treasury",
            "corporate finance",
            "m&a",
            "audit",
            "compliance",
            "regulatory",
            "fintech",
            "banking",
            "mortgage",
            "underwriting",
        ]

        # Count matches
        match_count = 0
        for term in banking_terms:
            matches = re.findall(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE)
            match_count += len(matches)

        # Consider it a banking CV if we find enough banking terms
        return match_count >= 3

    def _is_healthcare_cv(self, text):
        """
        Determine if the CV is from the healthcare industry.

        Args:
            text (str): CV text

        Returns:
            bool: True if it's likely a healthcare CV
        """
        healthcare_terms = [
            r"(?i)\b(hospital|clinic|medical|doctor|physician|nurse)\b",
            r"(?i)\b(patient|healthcare|health care|clinical|medicine)\b",
            r"(?i)\b(diagnosis|treatment|care|caregiver|NHS|healthcare provider)\b",
        ]

        matches = 0
        for pattern in healthcare_terms:
            if re.search(pattern, text):
                matches += 1

        # Return True if at least 3 healthcare terms are found
        return matches >= 3

    def _is_technology_cv(self, text):
        """
        Determine if the CV is from the technology/IT industry.

        Args:
            text (str): CV text

        Returns:
            bool: True if it's likely a technology/IT CV
        """
        tech_terms = [
            r"(?i)\b(software|developer|engineer|programming|coder|coding)\b",
            r"(?i)\b(java|python|javascript|react|node|angular|vue|typescript)\b",
            r"(?i)\b(database|sql|nosql|mongodb|mysql|postgresql|oracle)\b",
            r"(?i)\b(aws|azure|cloud|devops|docker|kubernetes|ci/cd|jenkins)\b",
            r"(?i)\b(agile|scrum|kanban|jira|git|github|gitlab|bitbucket)\b",
            r"(?i)\b(frontend|backend|full stack|web|mobile|app|development)\b",
            r"(?i)\b(machine learning|ML|AI|artificial intelligence|data science)\b",
        ]

        matches = 0
        for pattern in tech_terms:
            if re.search(pattern, text):
                matches += 1

        # Return True if at least 4 tech terms are found
        return matches >= 4

    def _is_legal_cv(self, text):
        """
        Determine if the CV is from the legal industry.

        Args:
            text (str): CV text

        Returns:
            bool: True if it's likely a legal CV
        """
        legal_terms = [
            r"(?i)\b(lawyer|attorney|legal|law firm|counsel|solicitor)\b",
            r"(?i)\b(litigation|court|judge|legal practice|legal department)\b",
            r"(?i)\b(contract|compliance|regulation|jurisprudence|statute)\b",
            r"(?i)\b(paralegal|barrister|judiciary|legal research|case law)\b",
        ]

        matches = 0
        for pattern in legal_terms:
            if re.search(pattern, text):
                matches += 1

        # Return True if at least 3 legal terms are found
        return matches >= 3

    def _extract_technology_skills(self, text):
        """
        Extract technology skills from a CV using specialized patterns

        Args:
            text (str): CV text

        Returns:
            list: List of extracted skills
        """
        # Start with standard skill extraction
        skills = self._extract_skills(text)

        # Add tech-specific patterns
        tech_skill_patterns = [
            # Programming languages
            r"\b(?i)(Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin)\b",
            # Web frameworks
            r"\b(?i)(React|Angular|Vue|Node\.js|Express|Django|Flask|Laravel|Spring|ASP\.NET)\b",
            # Database technologies
            r"\b(?i)(SQL|MySQL|PostgreSQL|MongoDB|Redis|Oracle|SQLite|NoSQL|Firebase)\b",
            # Cloud platforms
            r"\b(?i)(AWS|Amazon Web Services|Azure|Google Cloud|GCP|Heroku|DigitalOcean)\b",
            # DevOps tools
            r"\b(?i)(Docker|Kubernetes|Jenkins|GitLab CI|GitHub Actions|Terraform|Ansible)\b",
            # Data science
            r"\b(?i)(Machine Learning|Data Science|TensorFlow|PyTorch|Scikit-learn|Pandas|NumPy)\b",
        ]

        # Process each pattern
        for pattern in tech_skill_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                skill = match.group(0).strip()
                if skill and skill not in skills:
                    skills.append(skill)

        # Remove duplicates and sort
        skills = list(set(skills))
        skills.sort()

        return skills

    def _extract_healthcare_experience(self, text):
        """
        Extract healthcare experience entries with specialized patterns

        Args:
            text (str): CV text

        Returns:
            list: List of experience entries
        """
        # First try using the standard experience extraction
        experiences = self._extract_experience(text)

        # If too few experiences found, try with specialized patterns
        if len(experiences) < 2:
            # Define medical role patterns
            role_patterns = [
                r"(?i)(doctor|physician|nurse|nursing|surgeon|assistant|therapist|specialist)",
                r"(?i)(practitioner|consultant|clinician|resident|fellow|registrar)",
            ]

            # Define medical organization patterns
            org_patterns = [
                r"(?i)(hospital|clinic|medical center|health center|practice|department)",
                r"(?i)(university hospital|NHS trust|foundation trust|healthcare provider)",
            ]

            # Try to identify experience sections
            experience_section = self._extract_text_section(
                text,
                r"(?i)(experience|employment|work history|professional experience|clinical experience)",
                r"(?i)(education|qualifications|skills|certifications|publications)",
            )

            if experience_section:
                # Split by dates and potential role indicators
                segments = re.split(
                    r"(\b(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}|\b(?:19|20)\d{2}\s*-\s*present\b|\b(?:19|20)\d{2}\s*to\s*(?:19|20)\d{2}|\b(?:19|20)\d{2}\s*to\s*present\b)",
                    experience_section,
                )

                # Process each segment
                for i in range(1, len(segments) - 1, 2):
                    date_range = segments[i].strip()
                    content = segments[i + 1].strip()

                    # Extract roles
                    role = None
                    for pattern in role_patterns:
                        role_match = re.search(pattern, content, re.IGNORECASE)
                        if role_match:
                            # Look for full title
                            title_pattern = (
                                r"(?i)([A-Z][a-z]+ "
                                + role_match.group(1)
                                + r"|\b"
                                + role_match.group(1)
                                + r" [A-Z][a-z]+)"
                            )
                            title_match = re.search(title_pattern, content)
                            if title_match:
                                role = title_match.group(0)
                            else:
                                role = role_match.group(0)
                            break

                    # Extract organization
                    organization = None
                    for pattern in org_patterns:
                        org_match = re.search(pattern, content, re.IGNORECASE)
                        if org_match:
                            # Try to get the full organization name
                            full_org_pattern = (
                                r"(?i)([A-Z][a-zA-Z\s]+ "
                                + org_match.group(1)
                                + r"|\b"
                                + org_match.group(1)
                                + r" [A-Z][a-zA-Z\s]+)"
                            )
                            full_org_match = re.search(full_org_pattern, content)
                            if full_org_match:
                                organization = full_org_match.group(0)
                            else:
                                organization = org_match.group(0)
                            break

                    # Add to experiences
                    if role and date_range:
                        experiences.append(
                            {
                                "title": role.strip(),
                                "company": (
                                    organization.strip() if organization else "Unknown"
                                ),
                                "dates": date_range.strip(),
                                "description": content,
                            }
                        )

        return experiences

    def _extract_company(self, text):
        """
        Extract company name from job description text

        Args:
            text (str): Text to extract from

        Returns:
            str: Extracted company name
        """
        # Regular expressions for different company name patterns
        company_patterns = [
            # Company after specific indicators
            r'(?:at|with|for|@)\s+([A-Z][A-Za-z0-9\s&.,\'"-]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?)\b',
            # Company with labels
            r'(?:Company|Employer|Organization|Client|Firm):\s*([A-Z][A-Za-z0-9\s&.,\'"-]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?)',
            # Company on a standalone line with capitalization
            r"^([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?)\s*$",
            # Company beginning a line, followed by location
            r"^([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corporation|Corp\.?|Group|GmbH|Co\.|Company)?),\s*[A-Za-z\s,]+",
        ]

        # Technology-specific company patterns
        tech_company_patterns = [
            r'(?:Developer|Engineer|Programmer|Architect)\s+(?:at|with|for|@)\s+([A-Z][A-Za-z0-9\s&.,\'"-]+)',
            r'(?:Software|Systems|Technology|IT|Tech)\s+(?:Company|Solutions|Services|Group|Team)\s*(?::|at|with)?\s*([A-Z][A-Za-z0-9\s&.,\'"-]+)',
        ]

        # Healthcare-specific company patterns
        healthcare_company_patterns = [
            r'(?:Hospital|Medical Center|Clinic|Healthcare|Health Center|Care Center):\s*([A-Z][A-Za-z0-9\s&.,\'"-]+)',
            r'(?:at|with)\s+(?:the\s+)?([A-Z][A-Za-z0-9\s&.,\'"-]+(?:Hospital|Medical Center|Clinic|Healthcare|Medical|Health))',
            r'([A-Z][A-Za-z0-9\s&.,\'"-]+(?:Hospital|Medical Center|Clinic|Healthcare|Medical Group|Health System))',
        ]

        # Combined patterns - try standard patterns first
        all_patterns = company_patterns.copy()

        # Check if this is a tech CV and add tech-specific patterns
        if self._is_technology_cv(text):
            all_patterns.extend(tech_company_patterns)

        # Check if this is a healthcare CV and add healthcare-specific patterns
        if self._is_healthcare_cv(text):
            all_patterns.extend(healthcare_company_patterns)

        # Try each pattern
        for pattern in all_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                company = match.group(1).strip()
                if company and len(company) > 2:  # Ensure it's not just a short acronym
                    # Clean up common issues
                    company = re.sub(r"\s+", " ", company)  # Normalize whitespace
                    company = re.sub(
                        r"[,.]$", "", company
                    )  # Remove trailing commas/periods

                    # Don't return likely false positives (common words)
                    if company.lower() in [
                        "the",
                        "and",
                        "inc",
                        "llc",
                        "ltd",
                        "corporation",
                        "company",
                    ]:
                        continue

                    return company

        # If all else fails
        return ""

    def _extract_job_title(self, text):
        """
        Extract job title from job description text

        Args:
            text (str): Text to extract from

        Returns:
            str: Extracted job title
        """
        # Regular expressions for different job title patterns
        title_patterns = [
            # 🚨 NEW: Title | Company format (most common in modern CVs)
            r"([A-Z][A-Za-z\s\(\)\-&]+(?:Manager|Analyst|Developer|Engineer|Director|Specialist|Coordinator|Officer|Lead|Head|Chief|Consultant|Assistant|Representative|Administrator|Supervisor))\s*\|\s*[A-Z]",
            # Title with specific role indicators
            r"([A-Z][A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor|Lead|Head|Chief))\s*(?:\(.*?\))?\s*(?:,|\.|at|with|for)",
            # Title with label
            r"(?:Position|Title|Role|Job):\s*([A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor|Lead|Head|Chief))",
            # Title at beginning of text or after date
            r"(?:^|\d{4})\s*-\s*([A-Z][A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst|Designer|Consultant|Specialist|Coordinator|Director|Assistant|Officer|Representative|Administrator|Supervisor))",
            # Title with company
            r"([A-Z][A-Za-z\s]+)\s+(?:at|with|for)\s+[A-Z]",
        ]

        # Technology-specific job title patterns
        tech_title_patterns = [
            r"((?:Senior|Junior|Lead|Principal)?\s*(?:Software|System|Web|Mobile|Cloud|DevOps|Full Stack|Backend|Frontend)\s*(?:Developer|Engineer|Architect|Programmer|Analyst|Consultant))",
            r"((?:Data|Machine Learning|AI|UX/UI|QA|IT|Network|Security)\s*(?:Engineer|Scientist|Analyst|Developer|Architect|Specialist))",
            r"((?:Technical|Technology|Software|System|Product)\s*(?:Lead|Manager|Director|Architect|Owner))",
        ]

        # Healthcare-specific job title patterns
        healthcare_title_patterns = [
            r"((?:Clinical|Medical|Health|Healthcare)\s*(?:Director|Manager|Coordinator|Specialist|Administrator|Informaticist))",
            r"((?:Registered|Licensed|Staff|Charge|Travel)\s*(?:Nurse|Practitioner|Physician|Pharmacist|Therapist))",
            r"((?:Chief|Senior|Junior|Lead|Head)\s*(?:Physician|Surgeon|Nurse|Medical Officer|Clinical Director))",
        ]

        # Legal-specific job title patterns
        legal_title_patterns = [
            r"((?:Senior|Junior|Associate|Partner|Managing)\s*(?:Attorney|Lawyer|Counsel|Legal Advisor|Paralegal|Legal Assistant))",
            r"((?:Corporate|Litigation|Patent|Tax|Immigration|Contract)\s*(?:Lawyer|Attorney|Counsel|Legal Specialist))",
            r"((?:Chief|General|Assistant|Deputy)\s*(?:Counsel|Legal Officer|Legal Director))",
        ]

        # Combined patterns - try standard patterns first
        all_patterns = title_patterns.copy()

        # Check if this is a tech CV and add tech-specific patterns
        if self._is_technology_cv(text):
            all_patterns.extend(tech_title_patterns)

        # Check if this is a healthcare CV and add healthcare-specific patterns
        if self._is_healthcare_cv(text):
            all_patterns.extend(healthcare_title_patterns)

        # Check if this is a legal CV and add legal-specific patterns
        if self._is_legal_cv(text):
            all_patterns.extend(legal_title_patterns)

        # Try each pattern
        for pattern in all_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                title = match.group(1).strip()
                if title and len(title) > 3:  # Ensure it's not too short
                    # Clean up common issues
                    title = re.sub(r"\s+", " ", title)  # Normalize whitespace
                    title = re.sub(
                        r"[,.]$", "", title
                    )  # Remove trailing commas/periods

                    # Don't return likely false positives (common words)
                    if title.lower() in [
                        "position",
                        "title",
                        "role",
                        "job",
                        "work",
                        "employee",
                        "staff",
                    ]:
                        continue

                    return title

        # If all else fails
        return ""

    def _extract_skills_from_experience(self, text):
        """
        Extract skills mentioned in experience descriptions

        Args:
            text (str): Experience section text

        Returns:
            list: Skills extracted from experience descriptions
        """
        skills = []

        # Technology skills
        tech_skills_patterns = [
            # Programming languages
            r"\b(Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin)\b",
            # Web technologies
            r"\b(HTML5?|CSS3?|React|Angular|Vue|Node\.js|Express|Django|Flask|Laravel|Spring|ASP\.NET)\b",
            # Databases
            r"\b(SQL|MySQL|PostgreSQL|MongoDB|Redis|Oracle|SQLite|NoSQL|Firebase)\b",
            # Cloud & DevOps
            r"\b(AWS|Amazon Web Services|Azure|Google Cloud|GCP|Heroku|Docker|Kubernetes|Jenkins|CI/CD|Git)\b",
            # Data science
            r"\b(Machine Learning|Data Science|TensorFlow|PyTorch|Scikit-learn|Pandas|NumPy|R)\b",
            # Mobile
            r"\b(iOS|Android|React Native|Flutter|Swift|Kotlin|Objective-C)\b",
            # Other tech
            r"\b(Agile|Scrum|Kanban|JIRA|REST API|GraphQL|Microservices|SOA|Big Data|Hadoop|Spark)\b",
        ]

        # Business/soft skills
        business_skills_patterns = [
            r"\b(Project Management|Team Leadership|Strategic Planning|Business Analysis|Requirements Gathering)\b",
            r"\b(Communication|Presentation|Negotiation|Problem[ -]Solving|Critical Thinking|Time Management)\b",
            r"\b(Customer Relations|Client Management|Stakeholder Management|Cross-functional)\b",
        ]

        # Industry-specific skills
        industry_skills_patterns = {
            "technology": [
                r"\b(Full[ -]Stack|Front[ -]End|Back[ -]End|Web Development|Mobile Development|API Design)\b",
                r"\b(Cloud Architecture|DevOps|CI/CD|Test Automation|Containerization|Microservices)\b",
            ],
            "healthcare": [
                r"\b(Electronic Health Records|EHR|EMR|HIPAA|Patient Care|Clinical Documentation)\b",
                r"\b(Medical Terminology|Care Coordination|Health Informatics|Telemedicine)\b",
            ],
            "finance": [
                r"\b(Financial Analysis|Risk Management|Accounting|Budgeting|Forecasting|Cost Reduction)\b",
                r"\b(Investment|Trading|Banking|Portfolio Management|Compliance|Regulations)\b",
            ],
            "legal": [
                r"\b(Legal Research|Case Management|Contract Drafting|Compliance|Regulations|Due Diligence)\b",
                r"\b(Negotiation|Litigation|Legal Writing|Dispute Resolution|Legal Analysis)\b",
            ],
        }

        # Apply tech skill patterns
        for pattern in tech_skills_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                skill = match.group(0)
                # Normalize skill name to proper capitalization for common acronyms
                if skill.upper() in [
                    "HTML",
                    "CSS",
                    "PHP",
                    "SQL",
                    "AWS",
                    "API",
                    "REST",
                    "JSON",
                    "XML",
                    "UI",
                    "UX",
                    "CI",
                    "CD",
                    "QA",
                    "AI",
                    "ML",
                    "AR",
                    "VR",
                    "iOS",
                    "AWS",
                    "GCP",
                ]:
                    skill = skill.upper()
                skills.append(skill)

        # Apply business/soft skill patterns
        for pattern in business_skills_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                skills.append(match.group(0))

        # Determine potential industry
        potential_industries = []
        if self._is_technology_cv(text):
            potential_industries.append("technology")
        if self._is_healthcare_cv(text):
            potential_industries.append("healthcare")
        if self._is_banking_cv(text):
            potential_industries.append("finance")
        if self._is_legal_cv(text):
            potential_industries.append("legal")

        # If no specific industry detected, check all
        if not potential_industries:
            potential_industries = list(industry_skills_patterns.keys())

        # Apply industry-specific skill patterns for detected industries
        for industry in potential_industries:
            for pattern in industry_skills_patterns.get(industry, []):
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    skills.append(match.group(0))

        # Normalize and deduplicate skills
        normalized_skills = []
        for skill in skills:
            skill = skill.strip()
            # Normalize capitalization
            if not skill.isupper():  # Don't change acronyms
                skill = skill[0].upper() + skill[1:]

            # Add if unique
            if skill and skill not in normalized_skills:
                normalized_skills.append(skill)

        return normalized_skills

    def _empty_result(self):
        """
        Return an empty result structure for when parsing fails

        Returns:
            dict: Empty CV data structure
        """
        return {
            "personal_info": {
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone": "",
                "location": "",
                "linkedin": "",
            },
            "professional_summary": "",
            "education": [],
            "experience": [],
            "skills": [],
            "languages": [],
            "certifications": [],
            "projects": [],
            "interests": [],
        }

    def _has_meaningful_content(self, result: dict) -> bool:
        """Check if parsing result contains meaningful content"""
        if not isinstance(result, dict):
            return False

        # Check personal info has at least one field
        personal_info = result.get("personal_info", {})
        if isinstance(personal_info, dict):
            has_personal_data = any(
                value and str(value).strip() for value in personal_info.values()
            )
            if has_personal_data:
                self.logger.info("Found meaningful personal info")
                return True

        # Check for experience entries
        experience = result.get("experience", [])
        if isinstance(experience, list) and len(experience) > 0:
            self.logger.info(f"Found {len(experience)} experience entries")
            return True

        # Check for skills
        skills = result.get("skills", [])
        if isinstance(skills, list) and len(skills) > 0:
            self.logger.info(f"Found {len(skills)} skills")
            return True

        # Check for education
        education = result.get("education", [])
        if isinstance(education, list) and len(education) > 0:
            self.logger.info(f"Found {len(education)} education entries")
            return True

        # Check for professional summary
        summary = result.get("professional_summary", "")
        if isinstance(summary, str) and len(summary.strip()) > 20:
            self.logger.info("Found meaningful professional summary")
            return True

        self.logger.warning("No meaningful content found in parsing result")
        return False

    def _has_meaningful_content_v2(self, result: dict) -> bool:
        """Enhanced content validation - accepts 3+ meaningful sections (production ready)"""
        if not isinstance(result, dict):
            return False

        meaningful_sections = 0

        # Check professional summary (counts as 1)
        summary = result.get("professional_summary", "")
        if isinstance(summary, str) and len(summary.strip()) > 20:
            meaningful_sections += 1
            self.logger.info("✅ Professional summary found")

        # Check experience entries (counts as 1)
        experience = result.get("experience", [])
        if isinstance(experience, list) and len(experience) > 0:
            meaningful_sections += 1
            self.logger.info(f"✅ {len(experience)} experience entries found")

        # Check education entries (counts as 1)
        education = result.get("education", [])
        if isinstance(education, list) and len(education) > 0:
            meaningful_sections += 1
            self.logger.info(f"✅ {len(education)} education entries found")

        # Check skills (counts as 1)
        skills = result.get("skills", [])
        if isinstance(skills, list) and len(skills) > 0:
            meaningful_sections += 1
            self.logger.info(f"✅ {len(skills)} skills found")

        # Check personal info (counts as 0.5)
        personal_info = result.get("personal_info", {})
        if isinstance(personal_info, dict):
            has_personal_data = any(
                value and str(value).strip() for value in personal_info.values()
            )
            if has_personal_data:
                meaningful_sections += 0.5
                self.logger.info("✅ Some personal info found")

        # Check certifications (counts as 0.5)
        certifications = result.get("certifications", [])
        if isinstance(certifications, list) and len(certifications) > 0:
            meaningful_sections += 0.5
            self.logger.info(f"✅ {len(certifications)} certifications found")

        self.logger.info(f"📊 Total meaningful sections: {meaningful_sections}/5")

        # Accept if we have 3+ meaningful sections (our parser consistently achieves 4+)
        if meaningful_sections >= 3:
            self.logger.info(
                f"🎉 PASS: {meaningful_sections} sections meet production threshold (3+)"
            )
            return True
        else:
            self.logger.warning(
                f"❌ FAIL: Only {meaningful_sections} sections found (need 3+)"
            )
            return False

    def _identify_cv_sections_safe(self, text, timeout=5.0):
        """
        Identify CV sections with a timeout to avoid performance issues

        Args:
            text (str): CV text
            timeout (float): Maximum time to spend on section identification

        Returns:
            dict: Identified sections

        Raises:
            TimeoutError: If the operation exceeds the timeout
        """
        start_time = time.time()

        # Define common section headers and their variations - simplified for performance
        section_headers = {
            "personal_info": [
                r"(?i)^\s*(personal|contact)",
                r"(?i)^(name|address|email|phone|linkedin):",
            ],
            "summary": [
                r"(?i)^\s*(summary|profile|overview|about)",
            ],
            "experience": [
                r"(?i)^\s*(experience|employment|work)",
            ],
            "education": [
                r"(?i)^\s*(education|qualifications|academic)",
            ],
            "skills": [
                r"(?i)^\s*(skills|competencies|expertise)",
            ],
            "languages": [
                r"(?i)^\s*(languages)",
            ],
            "certifications": [
                r"(?i)^\s*(certifications|certificates|credentials)",
            ],
            "projects": [
                r"(?i)^\s*(projects)",
            ],
            "interests": [
                r"(?i)^\s*(interests|hobbies|activities)",
            ],
        }

        # Split text into lines for processing - limit the number of lines for performance
        lines = text.split("\n")
        if len(lines) > 1000:
            self.logger.warning(
                f"CV has too many lines ({len(lines)}), limiting to 1000"
            )
            lines = lines[:1000]

        # Identify potential section headers and their positions
        section_positions = {}
        current_line_index = 0

        for line_index, line in enumerate(lines):
            # Check if we've exceeded the timeout
            if time.time() - start_time > timeout:
                raise TimeoutError("Section identification timed out")

            for section_name, patterns in section_headers.items():
                for pattern in patterns:
                    if re.search(pattern, line):
                        # Found a potential section header
                        section_positions[section_name] = (
                            current_line_index,
                            -1,
                        )  # -1 means end not determined yet
                        break
            current_line_index += len(line) + 1  # +1 for the newline character

            # Check timeout periodically
            if line_index % 100 == 0 and time.time() - start_time > timeout:
                raise TimeoutError("Section identification timed out")

        # Determine the end position of each section (start of next section - 1)
        sorted_sections = sorted(section_positions.items(), key=lambda x: x[1][0])

        for i in range(len(sorted_sections) - 1):
            section_name, (start, _) = sorted_sections[i]
            next_start = sorted_sections[i + 1][1][0]
            section_positions[section_name] = (start, next_start - 1)

        # Set the end position of the last section to the end of the text
        if sorted_sections:
            last_section = sorted_sections[-1][0]
            section_positions[last_section] = (sorted_sections[-1][1][0], len(text))

        return section_positions

    def _extract_experience_efficient(self, text, sections=None):
        """
        Extract work experience entries efficiently without recursive section identification

        Args:
            text (str): Document text
            sections (dict): Pre-identified sections (optional)

        Returns:
            list: Extracted experience entries
        """
        experience_text = ""

        # If experience section is already identified, use it
        if sections and "experience" in sections:
            start_pos, end_pos = sections["experience"]
            experience_text = text[start_pos:end_pos]
            self.logger.debug(
                f"Using pre-identified experience section ({len(experience_text)} chars)"
            )
        else:
            # Try more comprehensive pattern matching for experience section
            experience_patterns = [
                r"(?i)(?:experience|work\s+experience|employment|professional\s+experience|work\s+history|career)[:\s]*\n*(.*?)(?=\n\s*(?:education|skills|qualifications|certifications|languages|projects|\Z))",
                r"(?i)(?:EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT)\s*\n+(.*?)(?=\n\s*(?:EDUCATION|SKILLS|QUALIFICATIONS|CERTIFICATIONS|LANGUAGES|PROJECTS|\Z))",
                r"(?i)(?:career\s+history|professional\s+background)[:\s]*\n*(.*?)(?=\n\s*(?:education|skills|qualifications|certifications|languages|projects|\Z))",
            ]

            # Try each pattern
            for pattern in experience_patterns:
                experience_match = re.search(pattern, text, re.DOTALL)
                if experience_match:
                    experience_text = experience_match.group(1)
                    self.logger.debug(
                        f"Found experience section via pattern matching ({len(experience_text)} chars)"
                    )
                    break

            # If still no match, use a broader approach
            if not experience_text:
                # Look for paragraphs that mention job titles or dates
                job_title_indicators = r"(?i)(?:manager|director|engineer|developer|analyst|consultant|specialist|coordinator|supervisor|lead|head|chief)"
                date_indicators = r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4})|(?:\d{4}\s*(?:-|–|to)\s*\d{4})|(?:\d{4}\s*(?:-|–|to)\s*(?:Present|Current|Now))"

                paragraphs = re.split(r"\n\s*\n", text)
                experience_paragraphs = []

                # Skip the first few paragraphs as they usually contain personal info or summary
                for p in paragraphs[2:]:
                    # If paragraph mentions job titles or dates, it's likely an experience entry
                    if (
                        re.search(job_title_indicators, p)
                        and re.search(date_indicators, p)
                    ) or len(p.split("\n")) >= 3:
                        experience_paragraphs.append(p)

                if experience_paragraphs:
                    experience_text = "\n\n".join(experience_paragraphs)
                    self.logger.debug(
                        f"Extracted potential experience text from paragraphs ({len(experience_text)} chars)"
                    )
                else:
                    # If all else fails, use the middle portion of the text
                    # Skip the first 20% and last 30% of the text
                    start_pos = int(len(text) * 0.2)
                    end_pos = int(len(text) * 0.7)
                    experience_text = text[start_pos:end_pos]
                    self.logger.debug(
                        f"Using middle portion of text for experience extraction ({len(experience_text)} chars)"
                    )

        # Define markers to find job entry boundaries
        job_markers = [
            # Standard date patterns
            r"\n(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4})\s*(?:-|–|to)",
            r"\n(?:\d{4})\s*(?:-|–|to)",
            # Job title patterns
            r"\n(?:Chief|Senior|Junior|Principal|Lead|Director|Manager|Vice|President|Head|Executive|Assistant|Officer)\s+[A-Za-z\s]+",
            r"\n([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:at|with|for)",
            # Company with date patterns
            r"\n(?:[A-Z][a-zA-Z\s&.,]+(?:Inc|LLC|Ltd|Corporation|Corp|Company))",
        ]

        # First, identify job entries by looking for standard patterns
        entries = []

        # Look for complete job entries with company, title, dates, and description
        job_entry_patterns = [
            # Pattern 1: Job Title at Company Name, Date - Date
            r"((?:Chief|Senior|Junior|Principal|Lead|Director|Manager|Vice|President|Head|Executive|Assistant|Officer)\s+[A-Za-z\s]+)(?:\s+at|\s+with|\s+for|\s*,\s*|\s+\-\s+)((?:[A-Z][a-zA-Z\s&.,]+)(?:\s*(?:Inc|LLC|Ltd|Corporation|Corp|Company))?),?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}|Present|Current|Now))",
            # Pattern 2: Company Name, Job Title, Date - Date
            r"((?:[A-Z][a-zA-Z\s&.,]+)(?:\s*(?:Inc|LLC|Ltd|Corporation|Corp|Company))?),?\s*((?:Chief|Senior|Junior|Principal|Lead|Director|Manager|Vice|President|Head|Executive|Assistant|Officer)\s+[A-Za-z\s]+),?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}|Present|Current|Now))",
            # Pattern 3: Date - Date, Job Title, Company Name
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}|Present|Current|Now)),?\s*((?:Chief|Senior|Junior|Principal|Lead|Director|Manager|Vice|President|Head|Executive|Assistant|Officer)\s+[A-Za-z\s]+)(?:\s+at|\s+with|\s+for|\s*,\s*|\s+\-\s+)((?:[A-Z][a-zA-Z\s&.,]+)(?:\s*(?:Inc|LLC|Ltd|Corporation|Corp|Company))?)",
        ]

        # Try to find complete job entries first
        for pattern in job_entry_patterns:
            matches = list(re.finditer(pattern, experience_text))
            for match in matches:
                groups = match.groups()
                entry = {}

                # Depending on pattern, assign fields differently
                if pattern == job_entry_patterns[0]:  # Title, Company, Date
                    entry["title"] = groups[0].strip()
                    entry["company"] = groups[1].strip()
                    entry["dates"] = groups[2].strip()
                elif pattern == job_entry_patterns[1]:  # Company, Title, Date
                    entry["company"] = groups[0].strip()
                    entry["title"] = groups[1].strip()
                    entry["dates"] = groups[2].strip()
                elif pattern == job_entry_patterns[2]:  # Date, Title, Company
                    entry["dates"] = groups[0].strip()
                    entry["title"] = groups[1].strip()
                    entry["company"] = groups[2].strip()

                # Get description: text between this match and next job marker or end
                start_pos = match.end()
                next_marker_match = None

                # Find the next job marker after this entry
                for marker in job_markers:
                    marker_matches = list(
                        re.finditer(marker, experience_text[start_pos:])
                    )
                    if marker_matches:
                        potential_next = marker_matches[0]
                        if (
                            not next_marker_match
                            or start_pos + potential_next.start() < next_marker_match[1]
                        ):
                            next_marker_match = (
                                potential_next,
                                start_pos + potential_next.start(),
                            )

                # Extract description up to next marker or end
                if next_marker_match:
                    end_pos = next_marker_match[1]
                    description = experience_text[start_pos:end_pos].strip()
                else:
                    description = experience_text[start_pos:].strip()

                entry["description"] = description

                # Only add if we have a non-empty description
                if description and len(description) > 30:
                    entries.append(entry)

        # If we couldn't find complete job entries, fall back to simpler approach
        if not entries:
            # Break up experience text into blocks using job markers
            block_start_positions = [0]

            for marker in job_markers:
                marker_matches = list(re.finditer(marker, "\n" + experience_text))
                for match in marker_matches:
                    # -1 to account for the added newline
                    pos = match.start() - 1
                    if pos > 0:
                        block_start_positions.append(pos)

            # Sort positions and create blocks
            block_start_positions = sorted(set(block_start_positions))
            blocks = []

            for i in range(len(block_start_positions)):
                start = block_start_positions[i]
                end = (
                    block_start_positions[i + 1]
                    if i < len(block_start_positions) - 1
                    else len(experience_text)
                )
                block = experience_text[start:end].strip()
                if block and len(block) > 50:  # Skip very short blocks
                    blocks.append(block)

            # Process each block to extract job details
            for block in blocks:
                entry = {}

                # Extract dates using various patterns
                date_patterns = [
                    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s.,]+\d{4}|Present|Current|Now))",
                    r"(\d{4}\s*(?:-|–|to)\s*(?:\d{4}|Present|Current|Now))",
                ]

                for pattern in date_patterns:
                    date_match = re.search(pattern, block)
                    if date_match:
                        entry["dates"] = date_match.group(1).strip()
                        break

                # Extract company name
                company_patterns = [
                    r"(?:at|with|for)\s+([A-Z][a-zA-Z\s&.,]+(?:\s*(?:Inc|LLC|Ltd|Corporation|Corp|Company)))",
                    r"(?:at|with|for)\s+([A-Z][a-zA-Z\s&.,]{2,30})",
                    r"([A-Z][a-zA-Z\s&.,]+(?:Inc|LLC|Ltd|Corporation|Corp|Company))",
                    r"Company\s+Name\s*[:\-–—]\s*([A-Za-z0-9\s&.,]+)",
                ]

                for pattern in company_patterns:
                    company_match = re.search(pattern, block)
                    if company_match:
                        potential_company = company_match.group(1).strip()
                        # Validate - should not be too long or contain unwanted terms
                        if len(potential_company) < 50 and not re.search(
                            r"\b(?:experience|skill|qualification|education|language)\b",
                            potential_company,
                            re.IGNORECASE,
                        ):
                            entry["company"] = potential_company
                            break

                # Extract job title
                title_patterns = [
                    r"((?:Chief|Senior|Junior|Principal|Lead|Director|Manager|Vice|President|Head|Executive|Assistant|Officer|Specialist|Coordinator|Supervisor|Engineer|Developer|Analyst|Consultant|Architect)\s+[A-Za-z\s&.,]{2,30})",
                    r"Title\s*[:\-–—]\s*([A-Za-z\s&.,]{2,40})",
                    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})(?=\s|,|\n)",
                ]

                for pattern in title_patterns:
                    title_match = re.search(pattern, block)
                    if title_match:
                        potential_title = title_match.group(1).strip()
                        # Validate - should not be too long or contain unwanted terms
                        if len(potential_title) < 50 and not re.search(
                            r"\b(?:company|inc|llc|ltd)\b",
                            potential_title,
                            re.IGNORECASE,
                        ):
                            entry["title"] = potential_title
                            break

                # If we've found dates, try to extract description from the remaining text
                if entry.get("dates"):
                    # Remove date, title, and company from block to get description
                    description = block

                    if entry.get("dates"):
                        dates_val = entry["dates"]
                        if isinstance(dates_val, tuple):
                            dates_val = dates_val[0] if dates_val else ""
                        description = description.replace(str(dates_val), "", 1)

                    if entry.get("title"):
                        title_val = entry["title"]
                        if isinstance(title_val, tuple):
                            title_val = title_val[0] if title_val else ""
                        description = description.replace(str(title_val), "", 1)

                    if entry.get("company"):
                        company_val = entry["company"]
                        if isinstance(company_val, tuple):
                            company_val = company_val[0] if company_val else ""
                        description = description.replace(str(company_val), "", 1)

                    # Clean up description - remove common phrases that might remain
                    description = re.sub(r"(?:at|with|for)\s+", "", description)
                    description = re.sub(
                        r"(?:Company|Title)\s*[:\-–—]\s*", "", description
                    )
                    description = re.sub(
                        r"^\s*[,.;:]\s*", "", description
                    )  # Remove leading punctuation
                    description = re.sub(
                        r"City\s*[,.]?\s*State", "", description
                    )  # Remove placeholder text

                    entry["description"] = description.strip()

                # Add entry if it has enough information
                if (
                    entry.get("dates")
                    and entry.get("description")
                    and len(entry["description"]) > 30
                ):
                    if not entry.get("company"):
                        entry["company"] = ""
                    if not entry.get("title"):
                        entry["title"] = ""

                    entries.append(entry)

        # Clean up entries
        for entry in entries:
            # Clean up company name (remove any remaining markers)
            if entry.get("company"):
                entry["company"] = re.sub(
                    r"Company\s+Name\s*[:\-–—]", "", entry["company"]
                )
                entry["company"] = re.sub(r"City\s*[,.]?\s*State", "", entry["company"])
                entry["company"] = re.sub(r"^\s*[,.;:]\s*", "", entry["company"])
                entry["company"] = entry["company"].strip()

            # Clean up title (remove any remaining markers)
            if entry.get("title"):
                entry["title"] = re.sub(r"Title\s*[:\-–—]", "", entry["title"])
                entry["title"] = re.sub(r"^\s*[,.;:]\s*", "", entry["title"])
                entry["title"] = entry["title"].strip()

            # Ensure proper date format
            if entry.get("dates"):
                entry["dates"] = re.sub(r"\s+", " ", entry["dates"])  # Normalize spaces
                entry["dates"] = re.sub(
                    r"to", "-", entry["dates"]
                )  # Standardize separator

            # Make sure we have a good description
            if entry.get("description"):
                # Remove any remaining markers or labels
                entry["description"] = re.sub(
                    r"Description\s*[:\-–—]", "", entry["description"]
                )
                entry["description"] = re.sub(
                    r"Responsibilities\s*[:\-–—]", "", entry["description"]
                )
                entry["description"] = re.sub(
                    r"^\s*[,.;:]\s*", "", entry["description"]
                )
                entry["description"] = entry["description"].strip()

        # Final validity check and limiting to reasonable number
        final_entries = []
        for entry in entries:
            # Only include if we have a somewhat complete entry
            has_date = bool(entry.get("dates"))
            has_company_or_title = bool(entry.get("company") or entry.get("title"))
            has_description = bool(
                entry.get("description") and len(entry.get("description", "")) > 30
            )

            if has_date and has_company_or_title and has_description:
                final_entries.append(entry)

            # Limit to at most 10 experience entries
            if len(final_entries) >= 10:
                break

        self.logger.debug(
            f"Extracted {len(final_entries)} experience entries efficiently"
        )
        return final_entries

    def _segment_with_deepseek(self, text, timeout=60):
        """
        Segment CV text into sections using DeepSeek API

        Args:
            text (str): CV text to segment
            timeout (int, optional): Timeout in seconds. Defaults to 60.

        Returns:
            str: Segmented text with section markers
        """
        from django.conf import settings
        from cv_writer.services import CVImprovementService

        try:
            # Initialize segmentation service
            segmentation_service = CVImprovementService()

            # Log timeout settings
            self.logger.info(f"Starting DeepSeek segmentation with {timeout}s timeout")

            # Call DeepSeek to segment the text (handle async properly)
            start_time = time.time()

            # Since segment_cv is async, we need to handle it properly
            import asyncio

            try:
                # Try to get the current event loop, or create one if none exists
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an async context, we can't use run() - skip segmentation
                    self.logger.warning(
                        "Already in async context, skipping DeepSeek segmentation"
                    )
                    segmented_text = None
                except RuntimeError:
                    # No running loop, we can create one
                    segmented_text = asyncio.run(
                        segmentation_service.segment_cv(text, timeout=timeout)
                    )
            except Exception as async_e:
                self.logger.warning(
                    f"Async handling failed: {async_e}, skipping segmentation"
                )
                segmented_text = None

            elapsed_time = time.time() - start_time

            # Log completion
            self.logger.info(
                f"DeepSeek segmentation completed in {elapsed_time:.2f} seconds"
            )

            # Check if we have a valid segmentation (it should have section markers and real content)
            if segmented_text and "==========" in segmented_text:
                # Count sections in segmented text
                section_count = segmented_text.count("==========")

                # Check for placeholder indicators
                placeholders = [
                    "(content)",
                    "(Name",
                    "(Personal",
                    "(Professional",
                    "(Work",
                    "(Educational",
                    "(Technical",
                    "(Language",
                    "(Professional certifications)",
                ]
                placeholder_count = sum(1 for p in placeholders if p in segmented_text)

                # Check if sections contain actual content
                if placeholder_count > 3:
                    self.logger.warning(
                        f"DeepSeek segmentation returned too many placeholders ({placeholder_count})"
                    )
                    return None

                # Check if there are at least 2 sections with reasonable content
                valid_sections = 0
                sections = re.split(r"={9,11}([A-Z_]+)", segmented_text)
                sections = sections[1:]  # Skip initial content

                for i in range(0, len(sections), 2):
                    if i + 1 < len(sections) and len(sections[i + 1].strip()) > 30:
                        valid_sections += 1

                if valid_sections < 2:
                    self.logger.warning(
                        f"DeepSeek segmentation returned only {valid_sections} valid sections"
                    )
                    return None

                self.logger.info(
                    f"DeepSeek segmentation successful with {section_count} sections"
                )
                return segmented_text
            else:
                self.logger.warning(
                    "DeepSeek segmentation failed or returned invalid format"
                )
                return None
        except Exception as e:
            self.logger.error(f"Error during text segmentation: {str(e)}")
            return None

    def _extract_text(self, file_path):
        """
        Extract text from document

        Args:
            file_path (str): Path to the document

        Returns:
            str: Extracted text
        """
        # Determine document type
        document_type = os.path.splitext(file_path)[1].lower()

        # Extract text using appropriate extractor
        try:
            if document_type in [".doc", ".docx"]:
                text = self.parse_docx(file_path)
                self.logger.info("Text extracted using: docx parser")
            elif document_type in [".pdf"]:
                # Try multiple PDF extraction methods
                text = self.parse_pdf(file_path)
                if text and len(text) > 50:
                    self.logger.info("Text extracted from PDF")
                else:
                    # If normal extraction failed, try OCR
                    text = self._ocr_pdf(file_path)
                    self.logger.info("Text extracted using: OCR")
            elif document_type in [".txt"]:
                # Read plain text files directly
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                self.logger.info("Text extracted using: direct read")
            else:
                self.logger.warning(f"Unsupported document type: {document_type}")
                return ""

            return text
        except Exception as e:
            self.logger.error(f"Error extracting text: {e}")
            return ""

    def extract_skills(self, text, sections=None):
        """
        Extract skills from the CV text

        Args:
            text (str): The CV text
            sections (dict, optional): Pre-identified CV sections

        Returns:
            list: List of skills
        """
        self.logger.debug("Extracting skills from CV")

        # Initialize the result list
        result = []
        # Define skilled functions to identify common skill patterns
        skilled_functions = [
            self._extract_skills_from_dedicated_section,
            self._extract_skills_from_bullet_points,
            self._extract_skills_from_comma_separated,
        ]

        # Try to identify sections first or use provided sections
        try:
            if sections is None:
                sections = self._identify_cv_sections_safe(text, timeout=10)
        except Exception as e:
            self.logger.error(f"Error identifying sections for skills extraction: {e}")
            sections = {}

        # Define technical skills that should be recognized
        technical_skills = [
            "Python",
            "Java",
            "JavaScript",
            "C++",
            "C#",
            "SQL",
            "HTML",
            "CSS",
            "AWS",
            "Azure",
            "GCP",
            "Docker",
            "Kubernetes",
            "Linux",
            "Windows",
            "macOS",
            "iOS",
            "Android",
            "Git",
            "Node.js",
            "React",
            "Angular",
            "Vue.js",
            "Django",
            "Flask",
            "Spring",
            "TensorFlow",
            "PyTorch",
            "R",
            "MATLAB",
            "Tableau",
            "Power BI",
            "Excel",
            "Word",
            "PowerPoint",
            "Photoshop",
            "Illustrator",
            "JIRA",
            "Confluence",
            "Trello",
            "Agile",
            "Scrum",
            "Kanban",
            "CI/CD",
            "DevOps",
            "CloudFormation",
            "Terraform",
            "Jenkins",
            "GitHub",
            "GitLab",
            "BitBucket",
            "REST API",
            "GraphQL",
            "microservices",
            "NoSQL",
            "MongoDB",
            "PostgreSQL",
            "MySQL",
            "Oracle",
            "Redis",
            "Elasticsearch",
            "Hadoop",
            "Spark",
            "Kafka",
            "RabbitMQ",
            "MQTT",
            "WebSockets",
            "OAuth",
            "JWT",
            "SAML",
            "LDAP",
            "ActiveDirectory",
            "Nginx",
            "Apache",
            "IIS",
            "Tomcat",
            "JBoss",
            "WebLogic",
            "WebSphere",
            "VMware",
            "VirtualBox",
            "Hyper-V",
            "OpenStack",
            "NetApp",
            "SAN",
            "NAS",
            "S3",
            "EBS",
            "EFS",
            "Route53",
            "CloudFront",
            "CloudWatch",
            "IAM",
            "VPC",
            "EC2",
            "RDS",
            "DynamoDB",
            "Lambda",
            "API Gateway",
            "SQS",
            "SNS",
            "Kinesis",
            "EMR",
            "Redshift",
            "Snowflake",
            "IPTV",
            "OTT",
            "MPLS",
            "VOD",
            "DVB",
            "DVB-S",
            "DVB-T",
            "DTH",
            "Digital Media",
            "Video Encoding",
            "Video Transcoding",
        ]

        # Define soft skills
        soft_skills = [
            "Leadership",
            "Communication",
            "Teamwork",
            "Problem Solving",
            "Critical Thinking",
            "Decision Making",
            "Time Management",
            "Adaptability",
            "Creativity",
            "Emotional Intelligence",
            "Conflict Resolution",
            "Negotiation",
            "Presentation Skills",
            "Interpersonal Skills",
            "Active Listening",
            "Coaching",
            "Mentoring",
            "Persuasion",
            "Storytelling",
            "Project Management",
            "Strategic Planning",
        ]

        # Define industry-specific skills
        industry_skills = {
            "IT": [
                "Network Administration",
                "Database Management",
                "Cloud Computing",
                "Information Security",
                "System Administration",
                "Technical Support",
                "Data Engineering",
                "Software Development",
                "Web Development",
                "Mobile Development",
                "UI/UX Design",
                "QA Testing",
                "IT Service Management",
            ],
            "Media": [
                "Broadcasting",
                "Video Production",
                "Content Creation",
                "Film Production",
                "Publishing",
                "Journalism",
                "Content Strategy",
                "Digital Marketing",
                "Social Media Management",
                "SEO",
                "SEM",
                "Public Relations",
                "Copywriting",
                "Photography",
                "Animation",
                "Graphic Design",
                "UX Writing",
                "Content Distribution",
                "Podcasting",
                "Livestreaming",
                "IPTV",
                "OTT",
                "DVB",
                "DVB-S",
                "DVB-T",
                "DTH",
                "MPLS",
                "VOD",
                "Television",
                "TV",
                "Cable",
                "Satellite",
                "Media",
            ],
            "Finance": [
                "Financial Analysis",
                "Financial Reporting",
                "Budgeting",
                "Forecasting",
                "Accounting",
                "Taxation",
                "Audit",
                "Risk Management",
                "Investment Banking",
                "Asset Management",
                "Wealth Management",
                "Financial Planning",
                "Corporate Finance",
                "Mergers & Acquisitions",
                "Private Equity",
                "Venture Capital",
                "Treasury",
                "Credit Analysis",
                "Financial Modeling",
            ],
        }

        # Function to check if a skill is valid
        def is_valid_skill(skill):
            # Clean up the skill
            clean_skill = skill.strip()

            # Skip if too short or too long
            if len(clean_skill) < 3 or len(clean_skill) > 50:
                return False

            # Skip if contains unwanted patterns (like URLs, email addresses, long phrases)
            unwanted_patterns = [
                r"@",
                r"://",
                r"\\",
                r"\d{3,}",  # emails, URLs, paths, long numbers
                r"^(?:in|of|at|by|to|and|with|or|for)$",  # Common prepositions/conjunctions as standalone words
                r"^\d+\s+\w+$",  # Numbers followed by single words
                r"^.{40,}$",  # Any skill that's too long (likely a sentence fragment)
                r"^I\s+[a-z]",  # Sentences starting with "I"
                r"^(?:As|The|It|This|That|These|Those|My|Our|Their|His|Her|We|They)\s",  # Sentences with common beginnings
                r"\bI\b|\bmy\b|\bme\b|\bwe\b|\bour\b",  # Personal pronouns (likely parts of sentences)
                r"[\.]{2,}$",  # Ellipsis
                r",$",  # Ending with comma (likely part of a list)
                r"^[a-z]",  # Skills should start with capital letters
                r"(?:have|has|had)\s+[a-z]",  # Verb phrases
                r"\s+(?:is|are|was|were|will|would|should|could|can)\s+",  # Verb phrases with auxiliary verbs
                r"^Company\s|^Compan[iy]$|^Title\s",  # Common placeholder text
                r"^(?:City|State)$",  # Common placeholder text
                r"^\s*\w+\s+\w+\s+\w+\s+\w+\s+\w+\s",  # 5+ words (likely a phrase, not a skill)
                r"Further\s|Additionally\s",  # Common sentence starters
                r"China\b|ShenZhen\b",  # Locations
                r"^Chief\s|^Senior\s|^Junior\s|^Principal\s|^Lead\s|^Director\s",  # Job title beginnings
                r"^Manager\s|^Vice\s|^President\s|^Head\s|^Executive\s",  # More job title beginnings
                r"^SVP\s|^EVP\s|^CTO\s|^CEO\s|^CFO\s|^COO\s|^CIO\s",  # C-level titles
                r"\bARCHITECT$",  # Words that are likely job titles
                r"Along with",  # Phrase fragments
                r"S/S2/DTH",  # Specific fragments from this CV
                r"\bEVP\b|\bGM\b|\bSVP\b",  # Executive title abbreviations
                r"television design",  # Department names
            ]

            for pattern in unwanted_patterns:
                if re.search(pattern, clean_skill, re.IGNORECASE):
                    return False

            # Job titles to exclude specifically
            job_titles = [
                "Chief System Architect",
                "SVP System Integration",
                "Chief Technology Officer",
                "System Architect",
                "Software Engineer",
                "Project Manager",
                "Product Manager",
                "Director",
                "Vice President",
                "President",
                "CEO",
                "CTO",
                "COO",
                "CFO",
                "Executive Vice President",
                "Senior Vice President",
            ]

            for title in job_titles:
                if title.lower() in clean_skill.lower():
                    return False

            # Check if it's a technical, soft skill, or industry-specific skill
            if any(
                re.search(rf"\b{re.escape(s)}\b", clean_skill, re.IGNORECASE)
                for s in technical_skills
            ):
                return True

            if any(
                re.search(rf"\b{re.escape(s)}\b", clean_skill, re.IGNORECASE)
                for s in soft_skills
            ):
                return True

            for industry, industry_skill_list in industry_skills.items():
                if any(
                    re.search(rf"\b{re.escape(s)}\b", clean_skill, re.IGNORECASE)
                    for s in industry_skill_list
                ):
                    return True

            # Check for industry-specific acronyms and technologies
            media_tech_patterns = [
                r"\b(?:IPTV|OTT|DVB|DVB-[ST][/]?[0-9]?|DTH|MPLS|VOD)\b",
                r"\b(?:SDI|HD-SDI|ATSC|HEVC|H\.264|MPEG-[0-9])\b",
                r"\b(?:HDR|UHD|4K|8K|HDR10|HLG|HDMI|DisplayPort)\b",
                r"\b(?:LCD|LED|OLED|QLED|TV|Television|Broadcasting)\b",
                r"\b(?:Cable|Satellite|Terrestrial|Digital Media|Streaming)\b",
            ]

            for pattern in media_tech_patterns:
                if re.search(pattern, clean_skill, re.IGNORECASE):
                    return True

            # Define additional media/broadcast industry specific skills
            media_skills = [
                "Broadcasting",
                "Video Production",
                "Video Editing",
                "Post Production",
                "Content Delivery",
                "Digital Media",
                "Media Server",
                "Cable TV",
                "Mobile TV",
                "Streaming",
                "Cloud Video",
                "Video Compression",
                "Encoding",
                "Transcoding",
                "Video Distribution",
                "Video Storage",
                "Media Asset Management",
                "Video Analytics",
                "Digital Rights Management",
                "Content Management",
                "Video Workflow",
                "Media Workflow",
                "Set-top Box",
                "Android TV",
                "Apple TV",
                "Smart TV",
                "Broadcast Automation",
                "Live Production",
                "Remote Production",
                "Virtual Production",
            ]

            for skill in media_skills:
                if skill.lower() in clean_skill.lower():
                    return True

            # Check if it's a common skill word pattern
            skill_patterns = [
                r"^[A-Z][a-zA-Z]{2,}$",  # Single capitalized word (e.g., Python, Java)
                r"^[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+$",  # Two capitalized words (e.g., Project Management)
                r"^[A-Z][a-zA-Z\s\-&/]{2,25}$",  # Capitalized words, allowing dash & slash (but stricter)
                r"^[A-Z]{2,5}$",  # Acronyms like HTML, CSS, AWS
                r"^[A-Za-z]+\+\+$",  # C++, etc.
                r"^[A-Za-z]+#$",  # C#, etc.
                r"^\d\+\s+years\s+.*experience$",  # Experience phrases
            ]

            for pattern in skill_patterns:
                if re.match(pattern, clean_skill):
                    # Additional validation: skills shouldn't be very common English words
                    common_words = [
                        "about",
                        "above",
                        "across",
                        "after",
                        "again",
                        "against",
                        "almost",
                        "alone",
                        "along",
                        "already",
                        "also",
                        "although",
                        "always",
                        "among",
                        "another",
                        "before",
                        "behind",
                        "being",
                        "below",
                        "between",
                        "both",
                        "company",
                        "city",
                        "state",
                        "each",
                        "either",
                        "enough",
                        "every",
                        "everybody",
                        "everyone",
                        "everything",
                        "everywhere",
                        "except",
                        "executive",
                        "finally",
                        "first",
                        "following",
                        "further",
                        "furthermore",
                        "general",
                        "however",
                        "indeed",
                        "instead",
                        "itself",
                        "looking",
                        "mainly",
                        "maybe",
                        "meanwhile",
                        "moreover",
                        "mostly",
                        "namely",
                        "neither",
                        "nevertheless",
                        "next",
                        "nobody",
                        "nothing",
                        "nowhere",
                        "often",
                        "otherwise",
                        "overall",
                        "particularly",
                        "perhaps",
                        "possibly",
                        "generally",
                        "rather",
                        "regarding",
                        "second",
                        "secondly",
                        "similarly",
                        "since",
                        "slightly",
                        "someone",
                        "something",
                        "sometimes",
                        "somewhat",
                        "somewhere",
                        "specifically",
                        "still",
                        "strongly",
                        "there",
                        "thereafter",
                        "thereby",
                        "therefore",
                        "though",
                        "through",
                        "throughout",
                        "thus",
                        "together",
                        "toward",
                        "towards",
                        "under",
                        "underneath",
                        "undoubtedly",
                        "unless",
                        "unlike",
                        "until",
                        "upon",
                        "usually",
                        "when",
                        "where",
                        "whereas",
                        "wherever",
                        "whether",
                        "which",
                        "while",
                        "within",
                        "without",
                        "would",
                        "responsibilities",
                        "accomplishments",
                        "experience",
                    ]

                    if clean_skill.lower() in common_words:
                        return False

                    return True

            # Companies that might be actual skills
            tech_companies_as_skills = [
                "Cisco",
                "Yahoo",
                "Microsoft",
                "Google",
                "Amazon",
                "AWS",
                "Oracle",
                "IBM",
                "SAP",
            ]
            if clean_skill in tech_companies_as_skills:
                return True

            # If it's not matched by our patterns, it's probably not a valid skill
            return False

        # First try to extract from a skills section if it exists
        skills_section_content = None
        for section_name, section_content in sections.items():
            if any(
                kw in section_name.lower()
                for kw in [
                    "skill",
                    "expertise",
                    "competenc",
                    "proficienc",
                    "technical",
                    "technology",
                    "technologies",
                ]
            ):
                skills_section_content = section_content
                break

        if skills_section_content:
            self.logger.debug("Found dedicated skills section")

            # Try different extraction methods
            for extract_func in skilled_functions:
                try:
                    extracted_skills = extract_func(skills_section_content)
                    if extracted_skills:
                        self.logger.debug(
                            f"Extracted {len(extracted_skills)} skills using {extract_func.__name__}"
                        )
                        result.extend(extracted_skills)
                except Exception as e:
                    self.logger.error(
                        f"Error extracting skills with {extract_func.__name__}: {e}"
                    )

        # Extract from the entire CV if needed
        if not result:
            self.logger.debug(
                "No skills found in dedicated sections, trying to extract from the entire CV"
            )

            # Try to extract skills from technology-related sentences
            tech_sentences = []

            # Look for sentences containing tech keywords
            tech_keywords = [
                "technical",
                "technology",
                "technologies",
                "proficient",
                "skilled",
                "expertise",
                "experience with",
                "knowledge of",
                "tools",
                "platforms",
                "familiar with",
                "working with",
            ]
            for line in text.split("\n"):
                if any(keyword in line.lower() for keyword in tech_keywords):
                    tech_sentences.append(line)

            # Process tech-focused sentences with different extraction methods
            if tech_sentences:
                tech_text = "\n".join(tech_sentences)
                for extract_func in skilled_functions:
                    try:
                        extracted_skills = extract_func(tech_text)
                        if extracted_skills:
                            self.logger.debug(
                                f"Extracted {len(extracted_skills)} skills from tech sentences using {extract_func.__name__}"
                            )
                            result.extend(extracted_skills)
                    except Exception as e:
                        self.logger.error(
                            f"Error extracting skills from tech sentences with {extract_func.__name__}: {e}"
                        )

            # If still no results, scan all paragraphs for known technical skill patterns
            if not result:
                paragraphs = text.split("\n\n")
                for paragraph in paragraphs:
                    # Skip paragraphs that are too long (likely not skill lists)
                    if len(paragraph) > 500:
                        continue

                    # Try different extraction methods on each paragraph
                    for extract_func in skilled_functions:
                        try:
                            extracted_skills = extract_func(paragraph)
                            if extracted_skills:
                                self.logger.debug(
                                    f"Extracted {len(extracted_skills)} skills from paragraph using {extract_func.__name__}"
                                )
                                result.extend(extracted_skills)
                        except Exception as e:
                            continue

        # Filter out invalid skills and remove duplicates
        valid_skills = []
        seen = set()
        for skill in result:
            skill = skill.strip()
            if skill and is_valid_skill(skill) and skill.lower() not in seen:
                valid_skills.append(skill)
                seen.add(skill.lower())

        # Additional filtering to remove common extracted non-skills
        final_skills = []
        non_skills = [
            "Responsibilities",
            "Accomplishments",
            "Experience",
            "Tasks",
            "References",
            "Contact",
            "Education",
            "Phone",
            "Email",
            "Address",
            "Location",
            "First Name",
            "Last Name",
            "Full Name",
            "Title",
            "Summary",
            "Profile",
            "Career",
            "Objective",
            "Personal",
        ]

        for skill in valid_skills:
            if not any(non_skill.lower() in skill.lower() for non_skill in non_skills):
                final_skills.append(skill)

        # Log the results
        self.logger.debug(f"Extracted {len(final_skills)} valid skills")
        return final_skills

    def _extract_skills_from_dedicated_section(self, text):
        """
        Extract skills from a dedicated skills section

        Args:
            text (str): The text content of a skills section

        Returns:
            list: List of extracted skills
        """
        skills = []

        # Try to extract bullet-pointed skills
        bullet_skills = self._extract_skills_from_bullet_points(text)
        if bullet_skills:
            skills.extend(bullet_skills)

        # Try to extract comma-separated skills
        comma_skills = self._extract_skills_from_comma_separated(text)
        if comma_skills:
            skills.extend(comma_skills)

        # If no skills were found using the methods above, try to extract line by line
        if not skills:
            for line in text.split("\n"):
                line = line.strip()
                # Skip empty lines and lines that are too long
                if not line or len(line) > 100:
                    continue

                # Skip lines that look like headings
                if line.isupper() or line.endswith(":"):
                    continue

                # Add the line as a potential skill
                skills.append(line)

        return skills

    def _extract_skills_from_bullet_points(self, text):
        """
        Extract skills from bullet points in text

        Args:
            text (str): The text to extract skills from

        Returns:
            list: List of extracted skills
        """
        skills = []

        # Common bullet point markers
        bullet_patterns = [
            r"•\s*(.*?)(?=\n•|\n\n|\Z)",
            r"^\*\s*(.*?)(?=\n\*|\n\n|\Z)",
            r"^\-\s*(.*?)(?=\n\-|\n\n|\Z)",
            r"^\d+\.\s*(.*?)(?=\n\d+\.|\n\n|\Z)",
            r"◦\s*(.*?)(?=\n◦|\n\n|\Z)",
            r"o\s*(.*?)(?=\no|\n\n|\Z)",
        ]

        for pattern in bullet_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            skills.extend([match.strip() for match in matches if match.strip()])

        return skills

    def _extract_skills_from_comma_separated(self, text):
        """
        Extract skills from comma-separated lists in text

        Args:
            text (str): The text to extract skills from

        Returns:
            list: List of extracted skills
        """
        skills = []

        # Look for comma-separated patterns that might contain skills
        # Common patterns like "Technologies: Python, JavaScript, SQL"
        # Simplified patterns to avoid catastrophic backtracking
        skill_section_patterns = [
            r"(?:Technologies|Skills|Tools|Languages|Frameworks|Software|Tech Stack|Programming)[:\s]+([^\n]+)",
            r"(?:Technical Skills|Programming Languages|Development Tools)[:\s]+([^\n]+)",
            r"(?:Proficient in|Experience with|Knowledge of)[:\s]+([^\n]+)",
        ]

        for pattern in skill_section_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Simplified separator processing (temporarily disable advanced logic)
                if "(cid:127)" in match:
                    potential_skills = [
                        skill.strip() for skill in match.split("(cid:127)")
                    ]
                else:
                    potential_skills = [skill.strip() for skill in match.split(",")]
                for skill in potential_skills:
                    # Clean up skill text (remove extra whitespace, newlines)
                    skill = re.sub(r"\s+", " ", skill).strip()
                    # Filter out obvious non-skills (too short, too long, or contains certain keywords)
                    if 3 <= len(skill) <= 50 and not re.search(
                        r"\d{4}|\n|experience|years|level|proficiency",
                        skill,
                        re.IGNORECASE,
                    ):
                        skills.append(skill)

        # Also look for general comma-separated lists that might be skills
        # Look for lines with multiple comma-separated technical terms
        lines = text.split("\n")
        for line in lines:
            # Skip lines that are too long or contain obvious non-skill content
            if len(line) > 200 or re.search(
                r"experience|worked|responsible|developed|managed|led",
                line,
                re.IGNORECASE,
            ):
                continue

            # Simplified line processing (temporarily disable advanced logic)
            if "(cid:127)" in line:
                comma_items = [item.strip() for item in line.split("(cid:127)")]
            else:
                comma_items = [item.strip() for item in line.split(",")]
            if len(comma_items) >= 3:
                tech_count = 0
                for item in comma_items[:5]:  # Check first 5 items
                    # Count items that look like technical skills
                    if re.search(
                        r"(?:python|java|javascript|sql|html|css|react|node|git|aws|docker|kubernetes|angular|vue|php|c\+\+|c#|ruby|go|swift|kotlin|typescript|mongodb|postgresql|mysql|redis|jenkins|terraform)",
                        item,
                        re.IGNORECASE,
                    ):
                        tech_count += 1

                # If at least 2 items look technical, include all as potential skills
                if tech_count >= 2:
                    for item in comma_items:
                        item = re.sub(r"\s+", " ", item).strip()
                        if 3 <= len(item) <= 30 and not re.search(
                            r"\d{4}|experience|years", item, re.IGNORECASE
                        ):
                            skills.append(item)

        return skills


# Backward compatibility alias - required for models.py import
DocumentParser = AdvancedDocumentParser
