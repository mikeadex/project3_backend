"""
3-Layer Quality Control System for CV Rewriter
==============================================

This module implements a comprehensive quality control system with three layers:
1. Writer Algorithm - Initial content generation
2. Reviewer Algorithm - Quality assessment and improvements
3. Approver Algorithm - Standards validation and final approval

Each layer has specific responsibilities and quality thresholds.
"""

import logging
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from django.contrib.auth.models import User
import asyncio

logger = logging.getLogger(__name__)


class QualityScore(Enum):
    """Quality score categories"""

    EXCELLENT = 5
    GOOD = 4
    SATISFACTORY = 3
    NEEDS_IMPROVEMENT = 2
    POOR = 1


@dataclass
class QualityMetrics:
    """Quality metrics for CV content"""

    content_score: int  # 1-5
    language_score: int  # 1-5
    structure_score: int  # 1-5
    ats_score: int  # 1-5
    overall_score: float  # Average
    feedback: List[str]
    passed_standards: bool


@dataclass
class LayerResult:
    """Result from a quality control layer"""

    layer_name: str
    content: Dict[str, Any]
    metrics: QualityMetrics
    passed: bool
    processing_time: float
    recommendations: List[str]


class CVQualityStandards:
    """Defines minimum quality standards for CV content"""

    # Minimum scores (1-5 scale)
    MIN_CONTENT_SCORE = 3
    MIN_LANGUAGE_SCORE = 3
    MIN_STRUCTURE_SCORE = 3
    MIN_ATS_SCORE = 3
    MIN_OVERALL_SCORE = 3.0

    # Content requirements
    MIN_SUMMARY_LENGTH = 100
    MAX_SUMMARY_LENGTH = 800  # Increased to accommodate comprehensive summaries
    MIN_EXPERIENCE_ITEMS = 1
    MIN_SKILLS_COUNT = 5

    # Language quality patterns
    FORBIDDEN_PHRASES = [
        "i am",
        "i have",
        "i was",
        "my role",
        "my responsibility",
        "position at",
        "work at",
        "job at",
    ]

    REQUIRED_ACTION_VERBS = [
        "managed",
        "managing",
        "led",
        "leading",
        "developed",
        "developing",
        "implemented",
        "implementing",
        "created",
        "creating",
        "designed",
        "designing",
        "improved",
        "improving",
        "optimized",
        "optimizing",
        "achieved",
        "achieving",
        "delivered",
        "delivering",
        "analyzed",
        "analyzing",
        "coordinated",
        "coordinating",
    ]

    ATS_KEYWORDS = {
        "technology": [
            "software development",
            "programming",
            "coding",
            "debugging",
            "project management",
            "agile",
            "scrum",
            "testing",
        ],
        "finance": [
            "financial analysis",
            "accounting",
            "financial reporting",
            "budgeting",
            "forecasting",
            "auditing",
            "compliance",
            "tax preparation",
            "reconciliation",
            "accounts payable",
            "accounts receivable",
        ],
        "business": [
            "strategy",
            "analysis",
            "management",
            "leadership",
            "operations",
            "process improvement",
            "stakeholder",
            "revenue",
        ],
        "healthcare": [
            "patient care",
            "clinical",
            "medical",
            "healthcare",
            "treatment",
            "diagnosis",
            "compliance",
            "safety",
        ],
    }


class WriterAlgorithm:
    """
    Layer 1: Writer Algorithm
    Responsible for initial content generation with structured prompts
    """

    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.layer_name = "Writer Algorithm"

    def _sync_generate(self, prompt: str) -> str:
        """Synchronously generate content from LLM service"""
        try:
            # Try to call the LLM service synchronously
            if hasattr(self.llm_service, "generate_completion_sync"):
                logger.info("🔧 Using generate_completion_sync method")
                return self.llm_service.generate_completion_sync(
                    prompt, max_tokens=1000, temperature=0.7
                )
            elif hasattr(self.llm_service, "generate_with_system_prompt"):
                logger.info("🔧 Using generate_with_system_prompt method")
                return self.llm_service.generate_with_system_prompt(prompt)
            elif hasattr(self.llm_service, "generate_response"):
                logger.info("🔧 Using generate_response method")
                return self.llm_service.generate_response(prompt)
            else:
                # Fallback mock response
                logger.warning(
                    f"⚠️ LLM service missing expected methods, using mock response"
                )
                logger.warning(f"🔍 Available methods: {dir(self.llm_service)}")
                return (
                    "Enhanced professional content with industry-specific optimization."
                )
        except Exception as e:
            logger.error(f"❌ LLM service call failed: {str(e)}, using fallback")
            return (
                "Enhanced professional content with improved formatting and keywords."
            )

    def generate_content(
        self, cv_data: Dict[str, Any], industry: str = "technology"
    ) -> LayerResult:
        """Generate initial CV content"""
        import time

        start_time = time.time()

        try:
            logger.info(f"🖊️ {self.layer_name}: Starting content generation")

            generated_content = {}

            # Generate professional summary with full CV context
            if cv_data.get("professional_summary"):
                generated_content["professional_summary"] = self._generate_summary(
                    cv_data["professional_summary"], industry, cv_data
                )

            # Generate experience descriptions
            if cv_data.get("experience"):
                generated_content["experience"] = self._generate_experience(
                    cv_data["experience"], industry
                )

            # Generate skills section
            if cv_data.get("skills"):
                generated_content["skills"] = self._generate_skills(
                    cv_data["skills"], industry
                )

            # Generate education improvements
            if cv_data.get("education"):
                generated_content["education"] = self._generate_education(
                    cv_data["education"]
                )

            # Evaluate initial content quality
            metrics = self._evaluate_content(generated_content, industry)

            processing_time = time.time() - start_time

            result = LayerResult(
                layer_name=self.layer_name,
                content=generated_content,
                metrics=metrics,
                passed=metrics.overall_score >= CVQualityStandards.MIN_OVERALL_SCORE,
                processing_time=processing_time,
                recommendations=metrics.feedback,
            )

            logger.info(
                f"🖊️ {self.layer_name}: Completed in {processing_time:.2f}s, Score: {metrics.overall_score}"
            )
            return result

        except Exception as e:
            logger.error(f"🖊️ {self.layer_name}: Error - {str(e)}")
            raise

    def _generate_summary(self, original_summary: str, industry: str, cv_data: Dict = None) -> str:
        """Generate professional summary with full CV context"""
        logger.info(f"📝 Generating professional summary for {industry} industry")
        logger.info(f"📄 Original summary: {original_summary[:100]}...")
        
        # Extract context from CV data if available
        context_info = ""
        if cv_data:
            # Get job titles from experience
            job_titles = []
            if cv_data.get("experience"):
                for exp in cv_data["experience"][:3]:  # Top 3 most recent
                    title = exp.get("job_title") or exp.get("title", "")
                    if title:
                        job_titles.append(title)
            
            # Get skills
            skills = []
            if cv_data.get("skills"):
                if isinstance(cv_data["skills"], list):
                    skills = [s.get("name", s) if isinstance(s, dict) else str(s) for s in cv_data["skills"][:10]]
                elif isinstance(cv_data["skills"], str):
                    skills = [s.strip() for s in cv_data["skills"].split(",")[:10]]
            
            # Get education
            education = []
            if cv_data.get("education"):
                for edu in cv_data["education"][:2]:
                    degree = edu.get("degree", "")
                    field = edu.get("field_of_study", "")
                    if degree:
                        education.append(f"{degree} in {field}" if field else degree)
            
            # Build context string
            if job_titles:
                context_info += f"\nRecent Job Titles: {', '.join(job_titles)}"
            if skills:
                context_info += f"\nKey Skills: {', '.join(skills)}"
            if education:
                context_info += f"\nEducation: {', '.join(education)}"

        prompt = f"""
        You are an expert CV writer specializing in ATS-optimized professional summaries. Enhance the following professional summary while STRICTLY preserving the candidate's authentic career field and experience context.

        CRITICAL PRESERVATION RULES:
        - PRESERVE the candidate's actual job title, industry, and field (e.g., retail stays retail, finance stays finance, tech stays tech)
        - DO NOT fabricate achievements, metrics, or responsibilities not implied in the original or CV data
        - DO NOT transform them into a different profession or industry
        - MAINTAIN all specific experience areas, company types, and role contexts mentioned
        - USE the candidate's actual job titles, skills, and education to make the summary SPECIFIC to them
        
        ENHANCEMENT GUIDELINES:
        - Strengthen action verbs within their ACTUAL responsibilities and achievements
        - Improve professional language and ATS keyword optimization for their EXISTING field
        - Incorporate their REAL skills and job titles from the CV data below
        - Quantify implied achievements using realistic language ("drive sales growth" vs specific fake numbers)
        - Enhance sentence flow and impact while staying authentic to their experience
        - Use confident, results-driven tone without first person (I, my, me)
        - Keep 4-6 sentences maximum for optimal readability
        
        Original Summary:
        {original_summary}
        {context_info}
        
        Write an enhanced professional summary that is SPECIFICALLY TAILORED to THIS candidate's unique background, making them MORE COMPETITIVE within their EXISTING career field:
        """

        response = self._sync_generate(prompt)
        cleaned_response = self._clean_response(response)

        logger.info(f"✨ Generated summary: {cleaned_response[:100]}...")

        # Check if the response is identical to original (AI might return same text)
        if cleaned_response.strip() == original_summary.strip():
            logger.warning(
                "⚠️ Generated summary is identical to original - AI returned unchanged text"
            )

        return cleaned_response

    def _clean_job_title(self, job_title: str, company_name: str) -> str:
        """Clean job title by removing company information that might be appended"""
        if not job_title or not company_name:
            return job_title

        title_lower = job_title.lower()
        company_lower = company_name.lower()

        # Common separators that might indicate company is appended to title
        separators = [" – ", " - ", " at ", " with ", " for ", " in "]

        for sep in separators:
            if sep in title_lower:
                parts = title_lower.split(sep)
                # Check if the part after separator matches company
                if len(parts) >= 2:
                    potential_company = parts[-1].strip()
                    if (
                        potential_company in company_lower
                        or company_lower in potential_company
                    ):
                        # Remove the company part and preserve original casing
                        original_parts = job_title.split(sep)
                        return sep.join(original_parts[:-1]).strip()

        # If no separator found but company appears at end, try to remove it
        if company_lower in title_lower:
            # Find the position and remove it
            idx = title_lower.find(company_lower)
            if idx > 0:
                return job_title[:idx].strip()

        return job_title

    def _generate_experience(
        self, experiences: List[Dict], industry: str
    ) -> List[Dict]:
        """Generate experience descriptions maintaining data structure"""
        improved_experiences = []

        for exp in experiences:
            # Handle both parsed data format and standard format
            description = (
                exp.get("job_description")
                or exp.get("description")
                or exp.get("job_desc")
                or exp.get("responsibilities")
            )

            if description:
                # Extract fields from both formats
                job_title = (
                    exp.get("job_title")
                    or exp.get("title")
                    or exp.get("position")
                    or "Professional"
                )
                company_name = (
                    exp.get("company_name")
                    or exp.get("company")
                    or exp.get("employer")
                    or "Company"
                )

                # Clean job title to remove company information that might be included
                job_title = self._clean_job_title(job_title, company_name)

                prompt = f"""
                You are an expert CV writer enhancing job experience descriptions. Improve this experience while maintaining absolute authenticity to the candidate's actual role and responsibilities.

                AUTHENTICITY REQUIREMENTS:
                - PRESERVE the exact job function, industry context, and scope of responsibilities
                - DO NOT fabricate achievements, metrics, or duties not evidenced in the original
                - MAINTAIN the authentic nature and level of their role
                - KEEP all industry-specific terminology and context accurate
                
                Job Title: {job_title}
                Company: {company_name}
                Original Description: {description}
                
                ENHANCEMENT OBJECTIVES:
                - Structure as 4-6 clear, impactful bullet points using dashes (-)
                - Strengthen action verbs within their ACTUAL responsibilities
                - Quantify implied achievements using realistic business language
                - Show measurable impact within their AUTHENTIC scope of work
                - Use professional, ATS-optimized language for their field
                - Ensure each bullet shows responsibility + impact/outcome
                
                Return ONLY the enhanced bullet points in this format:
                - [Strong action verb] [responsibility/achievement] [quantifiable outcome where realistic]
                - [Next bullet point]
                """

                improved_desc = self._sync_generate(prompt)
                exp_copy = exp.copy()
                exp_copy["job_description"] = self._clean_response(improved_desc)

                # Standardize field names and preserve all data
                exp_copy["company_name"] = company_name
                exp_copy["job_title"] = job_title

                # Handle dates field conversion
                dates = exp.get("dates") or exp.get("date_range")
                if dates:
                    # Check if dates contain N/A and estimate if needed
                    if "n/a" in dates.lower() or dates.lower().strip() in [
                        "na",
                        "not available",
                    ]:
                        # Estimate dates for N/A cases
                        estimated_dates = self._estimate_dates_for_position(
                            job_title, company_name, description
                        )
                        exp_copy["dates"] = estimated_dates
                        logger.info(
                            f"Estimated dates in _generate_experience for '{job_title}': {estimated_dates}"
                        )
                    else:
                        exp_copy["dates"] = dates

                    # Try to parse start/end dates if they exist
                    if "start_date" in exp:
                        exp_copy["start_date"] = exp.get("start_date")
                    if "end_date" in exp:
                        exp_copy["end_date"] = exp.get("end_date")
                else:
                    exp_copy["start_date"] = exp.get("start_date")
                    exp_copy["end_date"] = exp.get("end_date")

                exp_copy["current"] = exp.get("current", False)

                # Preserve original description field name for frontend compatibility
                if "description" in exp:
                    exp_copy["description"] = exp_copy["job_description"]

                improved_experiences.append(exp_copy)
            else:
                improved_experiences.append(exp)

        return improved_experiences

    def _generate_skills(self, skills, industry: str) -> str:
        """Generate skills section"""
        # Handle both list of strings and list of dictionaries
        if not skills:
            skills_text = "No skills provided"
        elif isinstance(skills[0], str):
            # List of strings: ["Python", "JavaScript"]
            skills_text = ", ".join([skill for skill in skills if skill.strip()])
        elif isinstance(skills[0], dict):
            # List of dictionaries: [{"skill_name": "Python", "skill_level": "Expert"}]
            skills_text = ", ".join(
                [
                    skill.get("skill_name", "")
                    for skill in skills
                    if skill.get("skill_name")
                ]
            )
        else:
            # Fallback for unknown format
            skills_text = str(skills)

        prompt = f"""
        Organize these skills for a {industry} professional into a structured format.
        
        Current Skills: {skills_text}
        
        Requirements:
        - Group by categories (Technical, Soft Skills, Tools, etc.)
        - Include proficiency levels (Expert, Advanced, Intermediate)
        - Add relevant {industry} keywords
        - Use clean formatting with bullet points
        
        Return organized skills list:
        """

        response = self._sync_generate(prompt)
        return self._clean_response(response)

    def _generate_education(self, education: List[Dict]) -> List[Dict]:
        """Generate education descriptions"""
        improved_education = []

        for edu in education:
            # Add relevant coursework or achievements if missing
            if not edu.get("description") or len(edu.get("description", "")) < 20:
                prompt = f"""
                Add relevant details for this education entry:
                
                Degree: {edu.get('degree', 'Degree')}
                School: {edu.get('school_name', 'University')}
                Field: {edu.get('field_of_study', 'Studies')}
                
                Add 1-2 lines about:
                - Relevant coursework
                - Academic achievements
                - Honors or distinctions
                
                Keep it professional and concise:
                """

                description = self._sync_generate(prompt)
                edu_copy = edu.copy()
                edu_copy["description"] = self._clean_response(description)
                improved_education.append(edu_copy)
            else:
                improved_education.append(edu)

        return improved_education

    def _evaluate_content(
        self, content: Dict[str, Any], industry: str
    ) -> QualityMetrics:
        """Evaluate generated content quality"""
        content_score = self._score_content_completeness(content)
        language_score = self._score_language_quality(content)
        structure_score = self._score_structure(content)
        ats_score = self._score_ats_optimization(content, industry)

        overall_score = (
            content_score + language_score + structure_score + ats_score
        ) / 4

        feedback = []
        if content_score < 3:
            feedback.append("Content needs more detail and specificity")
        if language_score < 3:
            feedback.append("Language could be more professional and impactful")
        if structure_score < 3:
            feedback.append("Structure and formatting need improvement")
        if ats_score < 3:
            feedback.append("ATS optimization needs enhancement")

        return QualityMetrics(
            content_score=content_score,
            language_score=language_score,
            structure_score=structure_score,
            ats_score=ats_score,
            overall_score=overall_score,
            feedback=feedback,
            passed_standards=overall_score >= CVQualityStandards.MIN_OVERALL_SCORE,
        )

    def _score_content_completeness(self, content: Dict[str, Any]) -> int:
        """Score content completeness (1-5)"""
        score = 1

        # Check summary length
        summary = content.get("professional_summary", "")
        if len(summary) >= CVQualityStandards.MIN_SUMMARY_LENGTH:
            score += 1

        # Check experience details
        experiences = content.get("experience", [])
        if len(experiences) >= CVQualityStandards.MIN_EXPERIENCE_ITEMS:
            score += 1

        # Check skills count
        skills_text = content.get("skills", "")
        skills_count = len(skills_text.split(",")) if skills_text else 0
        if skills_count >= CVQualityStandards.MIN_SKILLS_COUNT:
            score += 1

        # Check education details
        if content.get("education"):
            score += 1

        return min(score, 5)

    def _score_language_quality(self, content: Dict[str, Any]) -> int:
        """Score language quality (1-5)"""
        score = 3  # Start with average

        text_content = self._extract_all_text(content).lower()

        # Check for forbidden phrases
        forbidden_count = sum(
            1
            for phrase in CVQualityStandards.FORBIDDEN_PHRASES
            if phrase in text_content
        )
        if forbidden_count == 0:
            score += 1
        elif forbidden_count > 3:
            score -= 1

        # Check for action verbs
        action_verb_count = sum(
            1
            for verb in CVQualityStandards.REQUIRED_ACTION_VERBS
            if verb in text_content
        )
        if action_verb_count >= 3:
            score += 1
        elif action_verb_count == 0:
            score -= 1

        return max(1, min(score, 5))

    def _score_structure(self, content: Dict[str, Any]) -> int:
        """Score structure quality (1-5)"""
        score = 2  # Base score

        # Check if all main sections are present
        required_sections = ["professional_summary", "experience", "skills"]
        present_sections = sum(
            1 for section in required_sections if content.get(section)
        )

        if present_sections == len(required_sections):
            score += 2
        elif present_sections >= 2:
            score += 1

        # Check formatting consistency
        if self._has_consistent_formatting(content):
            score += 1

        return min(score, 5)

    def _score_ats_optimization(self, content: Dict[str, Any], industry: str) -> int:
        """Score ATS optimization (1-5)"""
        text_content = self._extract_all_text(content).lower()
        industry_keywords = CVQualityStandards.ATS_KEYWORDS.get(industry, [])

        keyword_matches = sum(
            1 for keyword in industry_keywords if keyword in text_content
        )

        if keyword_matches >= 5:
            return 5
        elif keyword_matches >= 3:
            return 4
        elif keyword_matches >= 2:
            return 3
        elif keyword_matches >= 1:
            return 2
        else:
            return 1

    def _extract_all_text(self, content: Dict[str, Any]) -> str:
        """Extract all text content for analysis"""
        text_parts = []

        if content.get("professional_summary"):
            text_parts.append(content["professional_summary"])

        if content.get("experience"):
            for exp in content["experience"]:
                if exp.get("job_description"):
                    text_parts.append(exp["job_description"])

        if content.get("skills"):
            text_parts.append(content["skills"])

        return " ".join(text_parts)

    def _has_consistent_formatting(self, content: Dict[str, Any]) -> bool:
        """Check if content has consistent formatting"""
        # Simple check for consistent bullet point usage
        text = self._extract_all_text(content)
        return "-" in text or "•" in text  # Has some bullet points

    def _clean_response(self, response: str) -> str:
        """Clean LLM response and ensure proper bullet point formatting"""
        if not response:
            return ""

        # 🚨 CRITICAL: Remove section headers that LLM adds (e.g., "Professional Summary", "Experience")
        # This must be done FIRST before other cleaning to preserve content
        response = re.sub(
            r"^(Professional Summary|Experience|Skills?|Education):?\s*\n*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        # Remove common LLM response prefixes and unwanted text
        response = re.sub(
            r"^(here is|here are|improved|rewritten|enhanced|sure|certainly|absolutely):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(
            r"^(of course|certainly|sure|absolutely|let me|i will|i\'ll):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(
            r"^(the improved|improved|enhanced)\s+(summary|experience|skills):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(
            r"^(here are the|the)\s+(improvements?|improved\s+(summary|experience|skills)):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        # Also remove these patterns anywhere in the text (not just at start)
        response = re.sub(
            r"(here are the|the)\s+(improvements?|improved\s+(summary|experience|skills)):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(
            r"(improved|enhanced)\s+(summary|experience|skills):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        # Remove markdown formatting
        response = re.sub(r"\*\*([^*]+)\*\*", r"\1", response)  # Bold text
        response = re.sub(r"\*([^*]+)\*", r"\1", response)  # Italic text
        response = re.sub(r"#{1,6}\s*", "", response)  # Headers
        response = re.sub(r"`([^`]+)`", r"\1", response)  # Inline code

        # Remove unwanted characters and formatting
        response = re.sub(
            r"[•●○■□▪▫]", "-", response
        )  # Convert all bullet symbols to dashes
        response = re.sub(r"[→⇒⇨➤➜➡]", "-", response)  # Convert arrows to dashes
        response = re.sub(r"[★☆⭐⭐]", "", response)  # Remove stars
        response = re.sub(r"[✓✔✗✘]", "", response)  # Remove checkmarks

        # Remove extra whitespace and normalize line breaks
        response = re.sub(
            r"\n\s*\n\s*\n+", "\n\n", response
        )  # Multiple blank lines to double
        response = re.sub(r"\n\s+", "\n", response)  # Remove trailing spaces on lines

        # Ensure proper bullet point formatting
        lines = response.strip().split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # Skip empty lines or lines that are just punctuation
                if line in [".", "-", "•", ":", ";"]:
                    continue

                # Convert • to - for consistency
                if line.startswith("•"):
                    line = line.replace("•", "-", 1)

                # Add dash if line starts with action verb but no bullet
                elif not line.startswith("-") and any(
                    line.lower().startswith(verb + " ")
                    for verb in [
                        "led",
                        "managed",
                        "developed",
                        "implemented",
                        "achieved",
                        "increased",
                        "reduced",
                        "coordinated",
                        "supervised",
                        "directed",
                        "executed",
                        "delivered",
                        "oversaw",
                        "established",
                        "created",
                        "designed",
                        "improved",
                        "enhanced",
                        "optimized",
                        "collaborated",
                        "organized",
                        "facilitated",
                        "conducted",
                        "performed",
                        "utilized",
                    ]
                ):
                    line = f"- {line}"

                # Clean up any remaining unwanted characters at start of line
                line = re.sub(r"^[^\w-]*", "", line)

                if line:  # Only add non-empty lines
                    cleaned_lines.append(line)

        # Join lines and clean up any remaining issues
        result = "\n".join(cleaned_lines)

        # Remove any trailing punctuation that might be artifacts
        result = re.sub(r"[.,;:]*$", "", result.strip())

        return result if result else response.strip()


class ReviewerAlgorithm:
    """
    Layer 2: Reviewer Algorithm
    Responsible for quality assessment and improvements
    """

    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.layer_name = "Reviewer Algorithm"

    def _sync_generate(self, prompt: str) -> str:
        """Synchronously generate content from LLM service"""
        try:
            # Try to call the LLM service synchronously
            if hasattr(self.llm_service, "generate_completion_sync"):
                return self.llm_service.generate_completion_sync(
                    prompt, max_tokens=1000, temperature=0.7
                )
            elif hasattr(self.llm_service, "generate_with_system_prompt"):
                return self.llm_service.generate_with_system_prompt(prompt)
            elif hasattr(self.llm_service, "generate_response"):
                return self.llm_service.generate_response(prompt)
            else:
                # Fallback mock response
                logger.warning(
                    f"LLM service missing expected methods, using mock response"
                )
                return "Enhanced professional content with improved quality control."
        except Exception as e:
            logger.warning(f"LLM service call failed: {str(e)}, using fallback")
            return "Enhanced professional content with quality improvements."

    def review_content(
        self, writer_result: LayerResult, industry: str = "technology"
    ) -> LayerResult:
        """Review and improve content from Writer Algorithm"""
        import time

        start_time = time.time()

        try:
            logger.info(f"🔍 {self.layer_name}: Starting content review")

            reviewed_content = writer_result.content.copy()

            # Identify areas needing improvement
            improvement_areas = self._identify_improvements(writer_result)

            # Apply targeted improvements
            for area in improvement_areas:
                if area == "summary":
                    reviewed_content["professional_summary"] = self._improve_summary(
                        reviewed_content.get("professional_summary", ""), industry
                    )
                elif area == "experience":
                    reviewed_content["experience"] = self._improve_experience(
                        reviewed_content.get("experience", []), industry
                    )
                elif area == "skills":
                    reviewed_content["skills"] = self._improve_skills(
                        reviewed_content.get("skills", ""), industry
                    )
                elif area == "language":
                    reviewed_content = self._improve_language(reviewed_content)

            # Evaluate reviewed content
            metrics = self._evaluate_improvements(
                reviewed_content, writer_result.metrics, industry
            )

            processing_time = time.time() - start_time

            result = LayerResult(
                layer_name=self.layer_name,
                content=reviewed_content,
                metrics=metrics,
                passed=metrics.overall_score >= CVQualityStandards.MIN_OVERALL_SCORE,
                processing_time=processing_time,
                recommendations=metrics.feedback,
            )

            logger.info(
                f"🔍 {self.layer_name}: Completed in {processing_time:.2f}s, Score improved to: {metrics.overall_score}"
            )
            return result

        except Exception as e:
            logger.error(f"🔍 {self.layer_name}: Error - {str(e)}")
            raise

    def _identify_improvements(self, writer_result: LayerResult) -> List[str]:
        """Identify areas that need improvement"""
        improvements = []
        metrics = writer_result.metrics

        if metrics.content_score < 4:
            improvements.append("summary")
            improvements.append("experience")

        if metrics.language_score < 4:
            improvements.append("language")

        if metrics.ats_score < 4:
            improvements.append("skills")

        if metrics.structure_score < 4:
            improvements.append("structure")

        return improvements

    def _improve_summary(self, summary: str, industry: str) -> str:
        """Improve professional summary"""
        prompt = f"""
        You are a senior CV writer reviewing a professional summary for final polish. Refine this summary to maximize its competitive impact while maintaining absolute authenticity to the candidate's career path.

        AUTHENTICITY REQUIREMENTS:
        - PRESERVE the candidate's actual profession, industry, and career trajectory  
        - DO NOT add achievements, metrics, or responsibilities not evidenced in the original
        - MAINTAIN the authentic scope and level of their experience
        - KEEP all industry-specific terminology and context accurate
        
        REFINEMENT OBJECTIVES:
        - Enhance clarity, flow, and professional impact of existing content
        - Strengthen action verbs and quantifiable language within realistic bounds
        - Optimize ATS keywords relevant to their established field and level
        - Ensure confident, results-driven tone that reflects their actual experience
        - Polish language for maximum recruiter appeal while staying truthful
        
        Current Summary:
        {summary}
        
        Provide a refined version that elevates this candidate's presentation within their authentic career context:
        """

        response = self._sync_generate(prompt)
        return self._clean_response(response)

    def _improve_experience(self, experiences: List[Dict], industry: str) -> List[Dict]:
        """Improve experience descriptions maintaining data structure"""
        improved = []

        for exp in experiences:
            # Handle both parsed data format and standard format
            description = (
                exp.get("job_description")
                or exp.get("description")
                or exp.get("job_desc")
                or exp.get("responsibilities")
            )

            if description:
                # Extract fields from both formats
                job_title = (
                    exp.get("job_title")
                    or exp.get("title")
                    or exp.get("position")
                    or "Position"
                )
                company_name = (
                    exp.get("company_name")
                    or exp.get("company")
                    or exp.get("employer")
                    or "Company"
                )

                # Clean job title to remove company information that might be included
                job_title = self._clean_job_title(job_title, company_name)

                prompt = f"""
                You are a senior CV writer polishing job experience descriptions for maximum competitive impact. Refine this experience while maintaining absolute authenticity to the candidate's career context.

                AUTHENTICITY REQUIREMENTS:
                - PRESERVE the candidate's actual job function, scope, and industry context
                - DO NOT add achievements or metrics not evidenced in the original description
                - MAINTAIN the authentic level and nature of their responsibilities
                - KEEP all role-specific terminology and context accurate
                
                Job: {job_title} at {company_name}
                Current Description: {description}
                
                REFINEMENT OBJECTIVES:
                - Polish language for maximum professional impact and clarity
                - Strengthen action verbs and quantifiable outcomes within realistic bounds
                - Ensure each bullet point shows clear responsibility + measurable result
                - Optimize for ATS keywords relevant to their established role and industry
                - Structure as clean, impactful bullet points using dashes (-)
                - Maintain authentic scope while maximizing competitive presentation
                
                Return polished description maintaining their ORIGINAL role authenticity:
                """

                enhanced = self._sync_generate(prompt)
                exp_copy = exp.copy()
                exp_copy["job_description"] = self._clean_response(enhanced)

                # Standardize field names and preserve all data
                exp_copy["company_name"] = company_name
                exp_copy["job_title"] = job_title

                # Handle dates field conversion
                dates = exp.get("dates") or exp.get("date_range")
                if dates:
                    # Check if dates contain N/A and estimate if needed
                    if "n/a" in dates.lower() or dates.lower().strip() in [
                        "na",
                        "not available",
                    ]:
                        # Estimate dates for N/A cases
                        estimated_dates = self._estimate_dates_for_position(
                            job_title, company_name, description
                        )
                        exp_copy["dates"] = estimated_dates
                        logger.info(
                            f"Estimated dates in _improve_experience for '{job_title}': {estimated_dates}"
                        )
                    else:
                        exp_copy["dates"] = dates

                    # Try to parse start/end dates if they exist
                    if "start_date" in exp:
                        exp_copy["start_date"] = exp.get("start_date")
                    if "end_date" in exp:
                        exp_copy["end_date"] = exp.get("end_date")
                else:
                    exp_copy["start_date"] = exp.get("start_date")
                    exp_copy["end_date"] = exp.get("end_date")

                exp_copy["current"] = exp.get("current", False)

                # Preserve original description field name for frontend compatibility
                if "description" in exp:
                    exp_copy["description"] = exp_copy["job_description"]

                improved.append(exp_copy)
            else:
                improved.append(exp)

        return improved

    def _improve_skills(self, skills: str, industry: str) -> str:
        """Improve skills section"""
        prompt = f"""
        Enhance this skills section with better organization and industry focus:
        
        Current Skills: {skills}
        Industry: {industry}
        
        Improvements:
        - Better categorization
        - Add missing industry-relevant skills
        - Improve proficiency descriptions
        - Optimize for ATS keywords
        
        Return enhanced skills section:
        """

        response = self._sync_generate(prompt)
        return self._clean_response(response)

    def _improve_language(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Improve overall language quality"""
        # This would scan all text and improve language quality
        # For now, return content as-is - can be enhanced later
        return content

    def _evaluate_improvements(
        self, content: Dict[str, Any], previous_metrics: QualityMetrics, industry: str
    ) -> QualityMetrics:
        """Evaluate improvements made during review"""
        # Use the same evaluation logic as Writer but with higher standards
        writer_algo = WriterAlgorithm(self.llm_service)
        new_metrics = writer_algo._evaluate_content(content, industry)

        # Add review-specific feedback
        feedback = new_metrics.feedback.copy()

        # Compare with previous scores
        if new_metrics.overall_score > previous_metrics.overall_score:
            feedback.append("Content quality improved through review process")

        if new_metrics.overall_score >= 4.0:
            feedback.append("Content meets high quality standards")
        elif new_metrics.overall_score >= 3.5:
            feedback.append("Content quality is good with minor improvements possible")
        else:
            feedback.append("Content requires additional refinement")

        new_metrics.feedback = feedback
        return new_metrics

    def _clean_response(self, response: str) -> str:
        """Clean LLM response and ensure proper bullet point formatting"""
        if not response:
            return ""

        # Remove common LLM response prefixes
        response = re.sub(
            r"^(here is|here are|enhanced|improved):?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(
            r"^(of course|certainly):?\s*", "", response, flags=re.IGNORECASE
        )

        # Remove markdown formatting
        response = re.sub(r"\*\*", "", response)  # Bold
        response = re.sub(r"#{1,6}\s*", "", response)  # Headers

        # Ensure proper bullet point formatting
        lines = response.strip().split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # Convert • to - for consistency
                if line.startswith("•"):
                    line = line.replace("•", "-", 1)
                # Add dash if line starts with action verb but no bullet
                elif not line.startswith("-") and any(
                    line.lower().startswith(verb)
                    for verb in [
                        "led",
                        "managed",
                        "developed",
                        "implemented",
                        "achieved",
                        "increased",
                        "reduced",
                        "coordinated",
                        "supervised",
                        "directed",
                        "executed",
                        "delivered",
                        "oversaw",
                        "established",
                        "created",
                        "designed",
                        "improved",
                        "enhanced",
                        "optimized",
                    ]
                ):
                    line = f"- {line}"
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines) if cleaned_lines else response.strip()


class ApproverAlgorithm:
    """
    Layer 3: Approver Algorithm
    Responsible for standards validation and final approval
    """

    def __init__(self):
        self.layer_name = "Approver Algorithm"
        self.standards = CVQualityStandards()

    def approve_content(
        self, reviewer_result: LayerResult, industry: str = "technology"
    ) -> LayerResult:
        """Final approval and standards validation"""
        import time

        start_time = time.time()

        try:
            logger.info(f"✅ {self.layer_name}: Starting final approval process")

            # Perform comprehensive validation
            validation_results = self._validate_standards(
                reviewer_result.content, industry
            )

            # Log validation results for debugging
            logger.info(f"🔍 Approver validation results: {validation_results}")
            failed_checks = [k for k, v in validation_results.items() if not v]
            if failed_checks:
                logger.warning(f"⚠️ Failed validation checks: {failed_checks}")

            # Determine if content passes all standards
            passed = all(validation_results.values())

            # Generate final metrics
            final_metrics = self._generate_final_metrics(
                reviewer_result.content,
                validation_results,
                reviewer_result.metrics,
                industry,
            )

            # Generate final recommendations
            recommendations = self._generate_final_recommendations(
                validation_results, final_metrics
            )

            processing_time = time.time() - start_time

            result = LayerResult(
                layer_name=self.layer_name,
                content=reviewer_result.content,  # Content doesn't change, only validation
                metrics=final_metrics,
                passed=passed,
                processing_time=processing_time,
                recommendations=recommendations,
            )

            status = "APPROVED" if passed else "REJECTED"
            logger.info(
                f"✅ {self.layer_name}: {status} in {processing_time:.2f}s, Final Score: {final_metrics.overall_score}"
            )

            return result

        except Exception as e:
            logger.error(f"✅ {self.layer_name}: Error - {str(e)}")
            raise

    def _validate_standards(
        self, content: Dict[str, Any], industry: str
    ) -> Dict[str, bool]:
        """Validate content against quality standards"""
        results = {}

        # Content length standards
        results["summary_length"] = self._validate_summary_length(
            content.get("professional_summary", "")
        )
        results["experience_count"] = self._validate_experience_count(
            content.get("experience", [])
        )
        results["skills_count"] = self._validate_skills_count(content.get("skills", ""))

        # Language quality standards
        results["no_forbidden_phrases"] = self._validate_no_forbidden_phrases(content)
        results["has_action_verbs"] = self._validate_action_verbs(content)
        results["professional_tone"] = self._validate_professional_tone(content)

        # ATS optimization standards
        results["industry_keywords"] = self._validate_industry_keywords(
            content, industry
        )
        results["structure_consistency"] = self._validate_structure(content)

        # Overall completeness
        results["content_completeness"] = self._validate_completeness(content)

        # Career consistency check
        results["career_consistency"] = self._validate_career_consistency(content)

        return results

    def _validate_summary_length(self, summary: str) -> bool:
        """Validate professional summary length"""
        length = len(summary)
        valid = (
            self.standards.MIN_SUMMARY_LENGTH
            <= length
            <= self.standards.MAX_SUMMARY_LENGTH
        )
        if not valid:
            logger.warning(
                f"⚠️ Summary length validation failed: {length} chars (required: {self.standards.MIN_SUMMARY_LENGTH}-{self.standards.MAX_SUMMARY_LENGTH})"
            )
        return valid

    def _validate_experience_count(self, experiences: List[Dict]) -> bool:
        """Validate minimum experience entries"""
        return len(experiences) >= self.standards.MIN_EXPERIENCE_ITEMS

    def _validate_skills_count(self, skills: str) -> bool:
        """Validate minimum skills count"""
        if not skills:
            return False
        skills_list = [s.strip() for s in skills.split(",") if s.strip()]
        return len(skills_list) >= self.standards.MIN_SKILLS_COUNT

    def _validate_no_forbidden_phrases(self, content: Dict[str, Any]) -> bool:
        """Validate no forbidden phrases are present"""
        text = self._extract_all_text(content).lower()
        return not any(phrase in text for phrase in self.standards.FORBIDDEN_PHRASES)

    def _validate_action_verbs(self, content: Dict[str, Any]) -> bool:
        """Validate presence of strong action verbs"""
        text = self._extract_all_text(content).lower()
        action_verb_count = sum(
            1 for verb in self.standards.REQUIRED_ACTION_VERBS if verb in text
        )
        return action_verb_count >= 2  # At least 2 action verbs

    def _validate_professional_tone(self, content: Dict[str, Any]) -> bool:
        """Validate professional tone (simple heuristic)"""
        text = self._extract_all_text(content).lower()

        # Check for unprofessional phrases
        unprofessional = ["very", "really", "awesome", "cool", "stuff"]
        unprofessional_count = sum(1 for word in unprofessional if word in text)

        return unprofessional_count <= 1  # Allow minimal informal language

    def _validate_industry_keywords(
        self, content: Dict[str, Any], industry: str
    ) -> bool:
        """Validate industry-specific keywords"""
        text = self._extract_all_text(content).lower()
        industry_keywords = self.standards.ATS_KEYWORDS.get(industry, [])

        keyword_matches = sum(1 for keyword in industry_keywords if keyword in text)
        return keyword_matches >= 3  # At least 3 industry keywords

    def _validate_structure(self, content: Dict[str, Any]) -> bool:
        """Validate content structure"""
        required_sections = ["professional_summary", "experience", "skills"]
        return all(content.get(section) for section in required_sections)

    def _validate_completeness(self, content: Dict[str, Any]) -> bool:
        """Validate overall content completeness"""
        scores = []

        # Summary completeness
        summary = content.get("professional_summary", "")
        scores.append(1 if len(summary) >= 100 else 0)

        # Experience completeness
        experiences = content.get("experience", [])
        detailed_exp = sum(
            1
            for exp in experiences
            if exp.get("job_description") and len(exp["job_description"]) >= 50
        )
        scores.append(1 if detailed_exp >= 1 else 0)

        # Skills completeness
        skills = content.get("skills", "")
        scores.append(1 if len(skills) >= 50 else 0)

        return sum(scores) >= 2  # At least 2/3 sections are complete

    def _generate_final_metrics(
        self,
        content: Dict[str, Any],
        validation_results: Dict[str, bool],
        previous_metrics: QualityMetrics,
        industry: str,
    ) -> QualityMetrics:
        """Generate final quality metrics"""

        # Calculate validation score
        validation_score = (
            sum(validation_results.values()) / len(validation_results) * 5
        )

        # Combine with previous metrics (weighted average)
        final_content_score = min(
            5, int((previous_metrics.content_score + validation_score) / 2)
        )
        final_language_score = min(
            5,
            previous_metrics.language_score
            + (1 if validation_results.get("professional_tone") else 0),
        )
        final_structure_score = min(
            5,
            previous_metrics.structure_score
            + (1 if validation_results.get("structure_consistency") else 0),
        )
        final_ats_score = min(
            5,
            previous_metrics.ats_score
            + (1 if validation_results.get("industry_keywords") else 0),
        )

        final_overall_score = (
            final_content_score
            + final_language_score
            + final_structure_score
            + final_ats_score
        ) / 4

        # Generate comprehensive feedback
        feedback = []
        for standard, passed in validation_results.items():
            if not passed:
                feedback.append(
                    f"Failed standard: {standard.replace('_', ' ').title()}"
                )

        if not feedback:
            feedback.append(
                "All quality standards met - content approved for publication"
            )

        return QualityMetrics(
            content_score=final_content_score,
            language_score=final_language_score,
            structure_score=final_structure_score,
            ats_score=final_ats_score,
            overall_score=final_overall_score,
            feedback=feedback,
            passed_standards=all(validation_results.values()),
        )

    def _generate_final_recommendations(
        self, validation_results: Dict[str, bool], metrics: QualityMetrics
    ) -> List[str]:
        """Generate final recommendations"""
        recommendations = []

        if metrics.passed_standards:
            recommendations.append(
                "✅ Content meets all quality standards and is ready for publication"
            )
            recommendations.append("🎯 ATS-optimized for maximum visibility")
            recommendations.append("🏆 Professional language and structure validated")
        else:
            recommendations.append(
                "⚠️ Content requires additional refinement before publication"
            )

            # Specific recommendations based on failed validations
            failed_standards = [
                standard
                for standard, passed in validation_results.items()
                if not passed
            ]

            for standard in failed_standards:
                if standard == "summary_length":
                    recommendations.append(
                        "📝 Adjust professional summary length (100-300 characters)"
                    )
                elif standard == "experience_count":
                    recommendations.append(
                        "💼 Add more detailed work experience entries"
                    )
                elif standard == "skills_count":
                    recommendations.append(
                        "🎯 Expand skills section with more relevant competencies"
                    )
                elif standard == "no_forbidden_phrases":
                    recommendations.append(
                        "✍️ Remove first-person language and informal phrases"
                    )
                elif standard == "has_action_verbs":
                    recommendations.append(
                        "💪 Include more strong action verbs in descriptions"
                    )
                elif standard == "industry_keywords":
                    recommendations.append(
                        "🔍 Add more industry-specific keywords for ATS optimization"
                    )
                elif standard == "structure_consistency":
                    recommendations.append(
                        "📋 Ensure all required sections are present and properly formatted"
                    )
                elif standard == "career_consistency":
                    recommendations.append(
                        "🚨 CRITICAL: Content changes the professional's career field inappropriately - preserve original industry context"
                    )

        return recommendations

    def _extract_all_text(self, content: Dict[str, Any]) -> str:
        """Extract all text content for analysis"""
        text_parts = []

        if content.get("professional_summary"):
            text_parts.append(content["professional_summary"])

        if content.get("experience"):
            for exp in content["experience"]:
                if exp.get("job_description"):
                    text_parts.append(exp["job_description"])

        if content.get("skills"):
            text_parts.append(content["skills"])

        return " ".join(text_parts)

    def _validate_career_consistency(self, content: Dict[str, Any]) -> bool:
        """
        Validate that the content maintains career consistency
        (no inappropriate field changes like retail -> tech)
        """
        text = self._extract_all_text(content).lower()

        # Check for suspicious career field mismatches
        retail_indicators = [
            "retail",
            "store",
            "sales",
            "customer service",
            "merchandising",
            "shop",
        ]
        tech_indicators = [
            "digital transformation",
            "system performance",
            "software",
            "technology leader",
            "it",
            "lifecycle initiatives",
        ]

        healthcare_indicators = [
            "patient",
            "medical",
            "clinical",
            "hospital",
            "healthcare",
            "nursing",
        ]
        finance_indicators = [
            "banking",
            "financial",
            "investment",
            "accounting",
            "audit",
            "credit",
        ]

        # If we find strong retail indicators, tech indicators should be minimal
        retail_count = sum(1 for indicator in retail_indicators if indicator in text)
        tech_count = sum(1 for indicator in tech_indicators if indicator in text)

        # If someone has strong retail background, they shouldn't suddenly be a "technology leader"
        if retail_count >= 3 and tech_count >= 2:
            logger.warning(
                "🚨 Career consistency violation: Retail professional described as technology leader"
            )
            return False

        # Similar checks for other inappropriate field changes
        healthcare_count = sum(
            1 for indicator in healthcare_indicators if indicator in text
        )
        finance_count = sum(1 for indicator in finance_indicators if indicator in text)

        # Healthcare to finance pivot check
        if healthcare_count >= 2 and finance_count >= 2:
            logger.warning(
                "🚨 Career consistency violation: Healthcare to finance field change detected"
            )
            return False

        return True


class ThreeLayerQualityController:
    """
    Main controller for the 3-layer quality control system
    Orchestrates Writer → Reviewer → Approver workflow
    """

    def __init__(self, writer_llm_service, reviewer_llm_service=None):
        """
        Initialize 3-layer quality control with different LLM services for each stage

        Args:
            writer_llm_service: LLM service for Writer Algorithm (Stage 1) - typically DeepSeek
            reviewer_llm_service: LLM service for Reviewer Algorithm (Stage 2) - typically LLaMA
        """
        self.writer = WriterAlgorithm(writer_llm_service)

        # Use LLaMA for reviewer if provided, otherwise fall back to writer service
        review_service = (
            reviewer_llm_service if reviewer_llm_service else writer_llm_service
        )
        self.reviewer = ReviewerAlgorithm(review_service)

        self.approver = ApproverAlgorithm()

        logger.info(
            f"🎯 Initialized 3-Layer QC: Writer({type(writer_llm_service).__name__}), Reviewer({type(review_service).__name__})"
        )

    def _format_experience_for_frontend(self, experiences: List[Dict]) -> str:
        """Format experience list as frontend-friendly string"""
        experience_sections = []

        for exp in experiences:
            # Extract fields
            job_title = exp.get("job_title") or exp.get("title") or "Position"
            company_name = exp.get("company_name") or exp.get("company") or "Company"

            # Clean job title to remove company information that might be included
            job_title = self._clean_job_title(job_title, company_name)
            description = (
                exp.get("job_description")
                or exp.get("description")
                or exp.get("job_desc")
                or exp.get("responsibilities")
                or ""
            )

            # Build date range from start_date and end_date - ENSURE DATES ARE ALWAYS INCLUDED
            start_date = exp.get("start_date", "").strip()
            end_date = exp.get("end_date", "").strip()

            # Handle different date scenarios - be more aggressive about finding dates
            dates = ""
            if start_date and end_date:
                if end_date.lower() in ["present", "current", "now"]:
                    dates = f"{start_date} – Present"
                else:
                    dates = f"{start_date} – {end_date}"
            elif start_date:
                dates = start_date
            elif end_date and end_date.lower() not in ["present", "current", "now"]:
                dates = end_date
            else:
                # Check for legacy dates field or date_range
                dates = exp.get("dates") or exp.get("date_range") or ""

            # ESTIMATE DATES WHEN N/A OR MISSING
            if not dates or dates.lower().strip() in [
                "n/a",
                "n/a - n/a",
                "na",
                "not available",
                "",
            ]:
                # Estimate dates based on job title and seniority
                estimated_dates = self._estimate_dates_for_position(
                    job_title, company_name, description
                )
                dates = estimated_dates
                logger.info(f"Estimated dates for '{job_title}': {dates}")
            elif "n/a" in dates.lower():
                # Handle partial N/A dates like "N/A - PRESENT"
                if "present" in dates.lower() or "current" in dates.lower():
                    # Estimate start date for current roles
                    estimated_start = self._estimate_start_date_for_current_role(
                        job_title, description
                    )
                    dates = f"{estimated_start} – Present"
                    logger.info(
                        f"Estimated start date for current role '{job_title}': {dates}"
                    )
                else:
                    # For other N/A cases, estimate full range
                    estimated_dates = self._estimate_dates_for_position(
                        job_title, company_name, description
                    )
                    dates = estimated_dates
                    logger.info(f"Estimated dates for N/A case '{job_title}': {dates}")

            # If still no dates, try to extract from description or other fields
            if not dates:
                # Look for date patterns in description
                date_patterns = [
                    r"(\w+ \d{4}) – (\w+ \d{4})",  # "Jan 2020 – Dec 2022"
                    r"(\d{4}) – (\d{4})",  # "2020 – 2022"
                    r"(\w+ \d{4}) – Present",  # "Jan 2020 – Present"
                    r"(\d{4}) – Present",  # "2020 – Present"
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, description, re.IGNORECASE)
                    if match:
                        dates = match.group(0)
                        break

            # Clean the description to remove unwanted formatting
            if description:
                # Remove markdown and unwanted characters
                description = re.sub(r"\*\*([^*]+)\*\*", r"\1", description)  # Bold
                description = re.sub(r"\*([^*]+)\*", r"\1", description)  # Italic
                description = re.sub(r"[•●○■□▪▫]", "-", description)  # Convert bullets
                description = re.sub(r"[→⇒⇨➤➜➡]", "-", description)  # Convert arrows
                description = re.sub(
                    r"\n\s*\n\s*\n+", "\n\n", description
                )  # Multiple blank lines

            # Format the section - ALWAYS include dates if available
            header = f"{job_title}"
            company_line = f"{company_name}"
            if dates:
                section = f"{header}\n{company_line}\n{dates}\n{description}"
            else:
                # If no dates found, still include the header and description
                section = f"{header}\n{company_line}\n{description}"
                logger.warning(
                    f"No dates found for experience: {job_title} at {company_name}"
                )

            experience_sections.append(section)

        return "\n\n".join(experience_sections)

    def _estimate_dates_for_position(
        self, job_title: str, company_name: str, description: str
    ) -> str:
        """Estimate realistic dates for a position based on title and description"""
        import datetime

        current_year = datetime.datetime.now().year

        # Analyze job title for seniority level
        title_lower = job_title.lower()
        company_lower = company_name.lower()
        desc_lower = description.lower()

        # Senior/executive roles - longer experience
        senior_keywords = [
            "senior",
            "lead",
            "principal",
            "head",
            "director",
            "vp",
            "chief",
            "executive",
            "manager",
        ]
        executive_keywords = ["director", "vp", "chief", "executive", "head"]

        # Entry/junior roles - shorter experience
        junior_keywords = [
            "junior",
            "entry",
            "graduate",
            "intern",
            "assistant",
            "trainee",
        ]

        # Estimate duration based on role type
        if any(keyword in title_lower for keyword in executive_keywords):
            # Executive roles: 4-7 years
            duration_years = 5.5
        elif any(keyword in title_lower for keyword in senior_keywords):
            # Senior roles: 3-5 years
            duration_years = 4
        elif any(keyword in title_lower for keyword in junior_keywords):
            # Junior roles: 1-2 years
            duration_years = 1.5
        else:
            # Mid-level roles: 2-4 years
            duration_years = 3

        # Adjust based on company type
        if any(
            word in company_lower
            for word in ["google", "microsoft", "amazon", "apple", "meta", "startup"]
        ):
            # Tech companies - slightly shorter tenures
            duration_years *= 0.8
        elif any(
            word in company_lower for word in ["university", "school", "education"]
        ):
            # Education - longer tenures
            duration_years *= 1.2

        # Adjust based on description content
        if "promoted" in desc_lower or "advanced" in desc_lower:
            duration_years *= 1.1  # Slightly longer if mentions promotion
        if "first" in desc_lower and "role" in desc_lower:
            duration_years *= 0.9  # Slightly shorter if mentions first role

        # Calculate start year
        start_year = int(current_year - duration_years)

        # Format as "Month Year – Present" for current roles, or "Month Year – Month Year" for past roles
        # Since we don't know if it's current, assume most recent roles are current
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        # Use a realistic start month (common start months)
        start_month = months[0]  # January as default
        if "summer" in desc_lower:
            start_month = "June"
        elif "fall" in desc_lower or "autumn" in desc_lower:
            start_month = "September"
        elif "spring" in desc_lower:
            start_month = "March"

        return f"{start_month} {start_year} – Present"

    def _estimate_start_date_for_current_role(
        self, job_title: str, description: str
    ) -> str:
        """Estimate start date for current roles with N/A start dates"""
        import datetime

        current_year = datetime.datetime.now().year

        # Similar logic to _estimate_dates_for_position but focused on start date
        title_lower = job_title.lower()
        desc_lower = description.lower()

        # Estimate duration based on role type
        senior_keywords = [
            "senior",
            "lead",
            "principal",
            "head",
            "director",
            "vp",
            "chief",
            "executive",
            "manager",
        ]
        executive_keywords = ["director", "vp", "chief", "executive", "head"]
        junior_keywords = [
            "junior",
            "entry",
            "graduate",
            "intern",
            "assistant",
            "trainee",
        ]

        if any(keyword in title_lower for keyword in executive_keywords):
            duration_years = 5
        elif any(keyword in title_lower for keyword in senior_keywords):
            duration_years = 4
        elif any(keyword in title_lower for keyword in junior_keywords):
            duration_years = 1
        else:
            duration_years = 2.5

        start_year = int(current_year - duration_years)

        # Use realistic start month
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        start_month = months[0]  # January as default
        if "summer" in desc_lower:
            start_month = "June"
        elif "fall" in desc_lower or "autumn" in desc_lower:
            start_month = "September"
        elif "spring" in desc_lower:
            start_month = "March"

        return f"{start_month} {start_year}"

    def _clean_job_title(self, job_title: str, company_name: str) -> str:
        """Clean job title by removing company information that might be appended"""
        if not job_title or not company_name:
            return job_title

        title_lower = job_title.lower()
        company_lower = company_name.lower()

        # Common separators that might indicate company is appended to title
        separators = [" – ", " - ", " at ", " with ", " for ", " in "]

        for sep in separators:
            if sep in title_lower:
                parts = title_lower.split(sep)
                # Check if the part after separator matches company
                if len(parts) >= 2:
                    potential_company = parts[-1].strip()
                    if (
                        potential_company in company_lower
                        or company_lower in potential_company
                    ):
                        # Remove the company part
                        return sep.join(parts[:-1]).strip()

        # If no separator found but company appears at end, try to remove it
        if company_lower in title_lower and title_lower.endswith(company_lower):
            return title_lower.replace(company_lower, "").strip(" –- ".strip())

        return job_title

    def process_cv(
        self, cv_data: Dict[str, Any], user: User, industry: str = "technology"
    ) -> Dict[str, Any]:
        """
        Process CV through all 3 quality control layers
        """
        import time

        start_time = time.time()

        try:
            username = user.username if user else "Anonymous"
            logger.info(f"🚀 Starting 3-Layer Quality Control for user {username}")

            # Layer 1: Writer Algorithm
            logger.info("📝 Layer 1: Writer Algorithm")
            writer_result = self.writer.generate_content(cv_data, industry)

            # Layer 2: Reviewer Algorithm
            logger.info("🔍 Layer 2: Reviewer Algorithm")
            reviewer_result = self.reviewer.review_content(writer_result, industry)

            # Layer 3: Approver Algorithm
            logger.info("✅ Layer 3: Approver Algorithm")
            approver_result = self.approver.approve_content(reviewer_result, industry)

            total_time = time.time() - start_time

            # Format experience data for frontend display
            formatted_content = approver_result.content.copy()
            if "experience" in formatted_content and isinstance(
                formatted_content["experience"], list
            ):
                formatted_content["experience"] = self._format_experience_for_frontend(
                    formatted_content["experience"]
                )

            # Compile final result
            final_result = {
                "status": "success",
                "approved": approver_result.passed,
                "quality_score": approver_result.metrics.overall_score,
                "content": formatted_content,
                "quality_report": {
                    "layer_results": [
                        {
                            "layer": writer_result.layer_name,
                            "score": writer_result.metrics.overall_score,
                            "passed": writer_result.passed,
                            "processing_time": writer_result.processing_time,
                        },
                        {
                            "layer": reviewer_result.layer_name,
                            "score": reviewer_result.metrics.overall_score,
                            "passed": reviewer_result.passed,
                            "processing_time": reviewer_result.processing_time,
                        },
                        {
                            "layer": approver_result.layer_name,
                            "score": approver_result.metrics.overall_score,
                            "passed": approver_result.passed,
                            "processing_time": approver_result.processing_time,
                        },
                    ],
                    "final_metrics": {
                        "content_score": approver_result.metrics.content_score,
                        "language_score": approver_result.metrics.language_score,
                        "structure_score": approver_result.metrics.structure_score,
                        "ats_score": approver_result.metrics.ats_score,
                        "overall_score": approver_result.metrics.overall_score,
                        "standards_met": approver_result.metrics.passed_standards,
                    },
                    "recommendations": approver_result.recommendations,
                    "total_processing_time": total_time,
                },
            }

            status = "APPROVED" if approver_result.passed else "NEEDS_IMPROVEMENT"
            logger.info(
                f"🎯 3-Layer QC Complete: {status} | Score: {approver_result.metrics.overall_score:.2f} | Time: {total_time:.2f}s"
            )

            return final_result

        except Exception as e:
            logger.error(f"❌ 3-Layer Quality Control Error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "approved": False,
                "quality_score": 0.0,
                "content": cv_data,  # Return original data as fallback
                "quality_report": {
                    "recommendations": [f"Quality control processing failed: {str(e)}"],
                    "error": str(e),
                },
            }
