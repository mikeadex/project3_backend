from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import logging
import asyncio
import tempfile
import time
from datetime import datetime
from django.utils import timezone
import traceback
import json
from docx import Document
from PyPDF2 import PdfReader
from asgiref.sync import sync_to_async
from django.db import close_old_connections
from .models import ParsedCV, CVRewriteSession
from .deepseek_service import DeepSeekService
from .serializers import ParsedCVSerializer
from .services import CVRewriteService

# Import CV Writer models for transfer functionality
from cv_writer.models import (
    CvWriter,
    ProfessionalSummary,
    Experience,
    Education,
    Skill,
    Language,
    Certification,
)

# Configure logging
logger = logging.getLogger("ai_cv_parser")


def repair_truncated_json(json_str):
    """
    Attempt to repair truncated JSON by completing incomplete structures
    """
    try:
        # First, try to parse as-is
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.info(f"Initial JSON parse failed: {e}")

        # Handle "Extra data" error - this means valid JSON + extra content
        if "Extra data" in str(e):
            try:
                # Find the position where valid JSON ends
                error_msg = str(e)
                # Extract character position from error message like "Extra data: line 37 column 1 (char 1121)"
                import re

                char_match = re.search(r"char (\d+)", error_msg)
                if char_match:
                    char_pos = int(char_match.group(1))
                    # Try to parse just the valid JSON part
                    valid_json = json_str[:char_pos].strip()
                    logger.info(
                        f"Trying to parse first {char_pos} characters as valid JSON"
                    )
                    parsed = json.loads(valid_json)
                    logger.info(
                        "✅ Successfully extracted valid JSON from truncated response"
                    )
                    return parsed
            except Exception as extra_error:
                logger.warning(f"Extra data handling failed: {extra_error}")
            # If the error isn't 'Extra data', it may be leading text before JSON
            # e.g., "Here is the analysis:\n\n{...}"
            try:
                first_brace = json_str.find("{")
                first_bracket = json_str.find("[")
                # choose earliest non-negative index
                idxs = [i for i in (first_brace, first_bracket) if i != -1]
                if idxs:
                    start = min(idxs)
                    candidate = json_str[start:]
                    logger.info(f"Attempting to parse JSON starting at pos {start}")
                    return json.loads(candidate)
            except Exception:
                logger.debug("Leading-text JSON extraction attempt failed")

    # Count braces to detect truncation
    open_braces = json_str.count("{")
    close_braces = json_str.count("}")
    open_brackets = json_str.count("[")
    close_brackets = json_str.count("]")

    # If we have unbalanced braces/brackets, try to close them
    if open_braces > close_braces or open_brackets > close_brackets:
        repaired = json_str.strip()

        # Handle incomplete strings (most common truncation issue)
        quote_count = repaired.count('"')
        if quote_count % 2 != 0:
            # Find the last incomplete string and close it properly
            last_quote_pos = repaired.rfind('"')
            if last_quote_pos > 0:
                # Check if this looks like an incomplete value
                after_quote = repaired[last_quote_pos + 1 :].strip()
                if (
                    after_quote
                    and not after_quote.startswith(",")
                    and not after_quote.startswith("]")
                    and not after_quote.startswith("}")
                ):
                    # This looks like a truncated string value, close it
                    repaired = repaired[: last_quote_pos + 1] + '"'
                else:
                    repaired += '"'

        # Remove any trailing incomplete content that might cause issues
        # Look for patterns like incomplete arrays or objects at the end
        import re

        # Remove trailing incomplete content after the last complete structure
        repaired = re.sub(r",\s*$", "", repaired)  # Remove trailing comma
        repaired = re.sub(
            r'["\']\s*$', '""', repaired
        )  # Close incomplete string at end

        # Close incomplete arrays
        missing_brackets = open_brackets - close_brackets
        if missing_brackets > 0:
            repaired += "]" * missing_brackets

        # Close incomplete objects
        missing_braces = open_braces - close_braces
        if missing_braces > 0:
            repaired += "}" * missing_braces

        try:
            parsed = json.loads(repaired)
            logger.info(f"✅ Successfully repaired truncated JSON")

            # Check if this looks like a clearly truncated response
            # If we had to add braces/brackets, or if the response is suspiciously short, force fallback
            if missing_braces > 0 or missing_brackets > 0 or len(json_str) < 1000:
                logger.warning(
                    f"⚠️  Repaired JSON appears truncated (added {missing_braces} braces, {missing_brackets} brackets, length {len(json_str)}), using fallback"
                )
                raise Exception("Response appears truncated")

            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️  JSON repair attempt failed: {e}")
            # Try more aggressive repair for specific patterns
            try:
                # Handle incomplete section_scores specifically
                if '"section_scores"' in repaired and '"skills_relevance":' in repaired:
                    # Complete the truncated skills_relevance value
                    repaired = re.sub(
                        r'"skills_relevance":\s*[\'"]?[^,}\]]*$',
                        '"skills_relevance": 8',
                        repaired,
                    )
                    repaired = re.sub(
                        r'"skills_relevance":\s*$', '"skills_relevance": 8', repaired
                    )

                # Handle other incomplete numeric values in section_scores
                section_pattern = r'"(\w+)":\s*$'
                match = re.search(section_pattern, repaired)
                if match:
                    field_name = match.group(1)
                    repaired = re.sub(section_pattern, f'"{field_name}": 7', repaired)

                # Remove incomplete trailing content
                repaired = re.sub(r',\s*"[^"]*":\s*[^,}\]]*$', "", repaired)

                # Balance braces again after cleanup
                missing_braces = repaired.count("{") - repaired.count("}")
                if missing_braces > 0:
                    repaired += "}" * missing_braces

                parsed = json.loads(repaired)
                logger.info(f"✅ Successfully repaired JSON with aggressive cleanup")

                # Again check for truncation indicators
                if len(json_str) < 1500 or missing_braces > 0:
                    logger.warning(
                        f"⚠️  Aggressively repaired JSON appears truncated (length {len(json_str)}), using fallback"
                    )
                    raise Exception("Response appears truncated")

                return parsed
            except:
                logger.warning("Aggressive JSON repair also failed")

    # If repair failed OR we detected truncation, return a rich default structure with skills
    logger.info("🔄 Using enhanced fallback JSON structure with skills")
    return {
        "overall_score": {
            "score": 8.5,
            "feedback": "Strong CV with excellent professional experience and relevant skills",
        },
        "strengths": [
            "Extensive retail management experience",
            "Strong leadership and team development skills",
            "Excellent operational and financial management",
            "Proven track record in store operations and customer service",
        ],
        "weaknesses": [
            "Could benefit from more digital marketing experience",
            "Limited international experience mentioned",
        ],
        "improvement_suggestions": [
            "Consider obtaining digital marketing certifications",
            "Highlight international experience if applicable",
            "Add more quantifiable achievements with specific metrics",
        ],
        "potential_roles": [
            "Retail Operations Manager",
            "Store Manager",
            "Regional Manager",
            "Operations Director",
        ],
        "section_scores": {
            "content_completeness": 8,
            "format_structure": 9,
            "skills_relevance": 8,
            "job_history": 9,
            "education": 8,
            "overall_impact": 8,
        },
        "ats_readiness": {
            "score": 85,
            "issues": [],
            "suggestions": [
                "Consider adding more industry-specific keywords",
                "Ensure consistent formatting throughout",
            ],
        },
        "experience_level": {
            "classification": "senior",
            "years_experience": 15,
            "career_stage": "Experienced professional with extensive management experience",
        },
        "skills_assessment": {
            "hard_skills": [
                {
                    "skill": "Retail Operations & Management",
                    "rating": 9,
                    "feedback": "Extensive experience in retail operations and management",
                },
                {
                    "skill": "Team Leadership & Development",
                    "rating": 9,
                    "feedback": "Strong leadership and team development skills demonstrated",
                },
                {
                    "skill": "Budgeting & Financial Reporting",
                    "rating": 8,
                    "feedback": "Proven financial management and budgeting experience",
                },
                {
                    "skill": "Sales & Inventory Analysis",
                    "rating": 8,
                    "feedback": "Strong analytical skills in sales and inventory management",
                },
                {
                    "skill": "Visual Merchandising & Store Presentation",
                    "rating": 8,
                    "feedback": "Excellent skills in store presentation and merchandising",
                },
                {
                    "skill": "Customer Service Excellence",
                    "rating": 9,
                    "feedback": "Outstanding customer service skills and experience",
                },
            ],
            "soft_skills": [
                {
                    "skill": "Leadership & Coaching",
                    "rating": 9,
                    "feedback": "Excellent leadership and coaching abilities",
                },
                {
                    "skill": "Communication",
                    "rating": 8,
                    "feedback": "Strong communication skills demonstrated",
                },
                {
                    "skill": "Problem Solving",
                    "rating": 8,
                    "feedback": "Effective problem-solving capabilities",
                },
                {
                    "skill": "Team Management",
                    "rating": 9,
                    "feedback": "Proven team management and development skills",
                },
            ],
            "missing_skills": [
                "Digital Marketing & E-Commerce Platforms",
                "Advanced Data Analytics",
                "International Business Experience",
            ],
        },
        "employment_gaps_analysis": {
            "has_gaps": "false",
            "feedback": "No significant employment gaps detected. Career progression shows consistent professional development.",
            "suggestions": [],
        },
        "error": "Analysis response was truncated - enhanced fallback data provided with comprehensive assessment",
    }


class AICVParserViewSet(viewsets.ModelViewSet):
    queryset = ParsedCV.objects.all()
    serializer_class = ParsedCVSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset to only show the authenticated user's CVs"""
        return ParsedCV.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single CV and auto-generate analysis if missing"""
        instance = self.get_object()

        # If analysis_data is missing, generate it from parsed_data
        if not instance.analysis_data and instance.parsed_data:
            logger.info(f"Auto-generating analysis for CV {instance.id} in retrieve")
            max_retries = 2
            retry_delay = 5  # seconds

            for attempt in range(max_retries + 1):
                try:
                    # Import service for analysis - use DeepSeek as primary
                    try:
                        from .deepseek_service import DeepSeekService

                        service = DeepSeekService()
                        logger.info(
                            f"Using DeepSeekService for auto-analysis (attempt {attempt + 1})"
                        )
                    except ImportError:
                        logger.warning(
                            "DeepSeekService not available, using FallbackService"
                        )
                        from .fallback_service import FallbackService

                        service = FallbackService()

                    # Generate analysis directly from parsed data
                    analysis_result = self._analyze_cv_chunked(
                        instance.parsed_data, service
                    )

                    # Ensure overall score is properly calculated
                    if "overall_score" in analysis_result:
                        score_value = analysis_result["overall_score"].get("score", 0)
                        # Recalculate if score is invalid (0, 0.0, or less than 1)
                        if score_value <= 0 or score_value < 1:
                            # Recalculate from dynamic section scores
                            section_scores = analysis_result.get("section_scores", {})
                            if section_scores:
                                dynamic_scores = [
                                    section_scores.get("content_completeness", 7),
                                    section_scores.get("format_structure", 8),
                                    section_scores.get("skills_relevance", 7),
                                    section_scores.get("job_history", 7),
                                    section_scores.get("education", 7),
                                    section_scores.get("overall_impact", 8),
                                ]
                                avg_score = sum(dynamic_scores) / len(dynamic_scores)
                                analysis_result["overall_score"] = {
                                    "score": round(avg_score, 1),
                                    "feedback": f"Overall CV score of {round(avg_score, 1)}/10 based on content quality analysis",
                                }
                                logger.info(
                                    f"Recalculated overall score to {round(avg_score, 1)} for CV {instance.id} from dynamic section scores: {dynamic_scores}"
                                )

                    # Save the analysis
                    instance.analysis_data = analysis_result
                    instance.analysis_date = timezone.now()
                    instance.save(update_fields=["analysis_data", "analysis_date"])

                    logger.info(
                        f"Auto-generated and saved analysis for CV {instance.id} in retrieve (attempt {attempt + 1})"
                    )
                    break  # Success, exit retry loop

                except Exception as analysis_error:
                    logger.warning(
                        f"Analysis attempt {attempt + 1}/{max_retries + 1} failed for CV {instance.id}: {analysis_error}"
                    )
                    if attempt < max_retries:
                        logger.info(
                            f"Retrying analysis for CV {instance.id} in {retry_delay} seconds..."
                        )
                        import time

                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(
                            f"All analysis attempts failed for CV {instance.id}, continuing without analysis"
                        )
                        # Create minimal fallback analysis data so it doesn't keep retrying
                        fallback_analysis = {
                            "error": "Analysis generation failed after multiple attempts",
                            "overall_score": {
                                "score": 6.0,
                                "feedback": "Analysis temporarily unavailable - please try again later",
                            },
                            "strengths": ["CV uploaded successfully"],
                            "weaknesses": ["Analysis not yet available"],
                            "improvement_suggestions": [
                                "Please wait and try viewing analysis again"
                            ],
                            "potential_roles": ["Analysis pending"],
                            "skills_assessment": {
                                "hard_skills": [],
                                "soft_skills": [],
                                "missing_skills": [],
                            },
                        }
                        instance.analysis_data = fallback_analysis
                        instance.analysis_date = timezone.now()
                        instance.save(update_fields=["analysis_data", "analysis_date"])
                        logger.info(f"Saved fallback analysis for CV {instance.id}")

        # If analysis_data has errors or is incomplete, try to regenerate it
        elif instance.analysis_data and instance.parsed_data:
            analysis_data = instance.analysis_data
            needs_regeneration = False

            # Check if analysis has errors or is incomplete
            has_error = "error" in analysis_data
            has_minimal_data = (
                "overall_score" in analysis_data
                and len(analysis_data.get("strengths", [])) == 0
                and len(analysis_data.get("weaknesses", [])) == 0
                and len(analysis_data.get("improvement_suggestions", [])) == 0
            )

            # Check if enough time has passed since last analysis attempt (at least 10 minutes)
            time_since_analysis = timezone.now() - (
                instance.analysis_date or instance.uploaded_at
            )
            enough_time_passed = time_since_analysis.total_seconds() > 600  # 10 minutes

            if (has_error or has_minimal_data) and enough_time_passed:
                logger.info(
                    f"Retrying analysis for CV {instance.id} (error={has_error}, minimal={has_minimal_data}, time_passed={time_since_analysis})"
                )
                needs_regeneration = True

            if needs_regeneration:
                max_retries = 1  # Single retry for regeneration
                retry_delay = 3

                for attempt in range(max_retries + 1):
                    try:
                        # Use DeepSeek as primary service
                        try:
                            from .deepseek_service import DeepSeekService

                            service = DeepSeekService()
                            logger.info(
                                f"Using DeepSeekService for analysis regeneration (attempt {attempt + 1})"
                            )
                        except ImportError:
                            logger.warning(
                                "DeepSeekService not available, using FallbackService"
                            )
                            from .fallback_service import FallbackService

                            service = FallbackService()

                        new_analysis = self._analyze_cv_chunked(
                            instance.parsed_data, service
                        )

                        # Validate the new analysis is better than the old one
                        if new_analysis and "overall_score" in new_analysis:
                            # Update analysis data
                            instance.analysis_data = new_analysis
                            instance.analysis_date = timezone.now()
                            instance.save(
                                update_fields=["analysis_data", "analysis_date"]
                            )

                            logger.info(
                                f"Successfully regenerated analysis for CV {instance.id}"
                            )
                            break

                    except Exception as regen_error:
                        logger.warning(
                            f"Regeneration attempt {attempt + 1} failed for CV {instance.id}: {regen_error}"
                        )
                        if attempt < max_retries:
                            import time

                            time.sleep(retry_delay)
            analysis_data = instance.analysis_data
            needs_update = False

            # Check and fix overall score
            if "overall_score" in analysis_data:
                overall_score = analysis_data["overall_score"]
                if isinstance(overall_score, dict):
                    score_value = overall_score.get("score", 0)
                elif isinstance(overall_score, (int, float)):
                    score_value = overall_score
                else:
                    score_value = 0

                # Recalculate if score is invalid
                if score_value <= 0 or score_value < 1:
                    section_scores = analysis_data.get("section_scores", {})
                    if section_scores:
                        dynamic_scores = [
                            section_scores.get("content_completeness", 7),
                            section_scores.get("format_structure", 8),
                            section_scores.get("skills_relevance", 7),
                            section_scores.get("job_history", 7),
                            section_scores.get("education", 7),
                            section_scores.get("overall_impact", 8),
                        ]
                        avg_score = sum(dynamic_scores) / len(dynamic_scores)
                        analysis_data["overall_score"] = {
                            "score": round(avg_score, 1),
                            "feedback": f"Overall CV score of {round(avg_score, 1)}/10 based on content quality analysis",
                        }
                        needs_update = True
                        logger.info(
                            f"Fixed invalid overall score to {round(avg_score, 1)} for existing CV {instance.id}"
                        )
                    else:
                        # No section scores available, provide a reasonable default based on available data
                        has_content = bool(
                            analysis_data.get("strengths")
                            or analysis_data.get("weaknesses")
                        )
                        has_improvements = bool(
                            analysis_data.get("improvement_suggestions")
                        )

                        if has_content and has_improvements:
                            default_score = 6.5
                        elif has_content:
                            default_score = 7.0
                        else:
                            default_score = 5.5

                        analysis_data["overall_score"] = {
                            "score": default_score,
                            "feedback": f"Overall CV score of {default_score}/10 based on available analysis data",
                        }
                        needs_update = True
                        logger.info(
                            f"Fixed invalid overall score to {default_score} for CV {instance.id} (no section scores available)"
                        )

            # Save if updated
            if needs_update:
                instance.analysis_data = analysis_data
                instance.save(update_fields=["analysis_data"])

        return super().retrieve(request, *args, **kwargs)

    def _analyze_cv_chunked(self, cv_data, service):
        """
        Analyze CV in chunks to prevent truncation and improve quality.
        Returns combined analysis result.
        """
        logger.info("🔄 Starting chunked CV analysis")

        # Split CV data into logical sections
        sections = self._split_cv_into_sections(cv_data)

        # Analyze each section separately
        section_analyses = {}
        for section_name, section_data in sections.items():
            logger.info(f"📊 Analyzing section: {section_name}")
            try:
                analysis = self._analyze_single_section(
                    section_name, section_data, service
                )
                section_analyses[section_name] = analysis
            except Exception as e:
                logger.warning(f"Failed to analyze section {section_name}: {e}")
                section_analyses[section_name] = None

        # Combine section analyses into final result
        combined_result = self._combine_section_analyses(section_analyses, cv_data)

        logger.info("✅ Chunked analysis completed")
        return combined_result

    def _split_cv_into_sections(self, cv_data):
        """Split CV data into logical sections for separate analysis."""
        sections = {}

        # Personal info section
        if cv_data.get("personal_info"):
            sections["personal"] = {"personal_info": cv_data["personal_info"]}

        # Experience section (limit to prevent token overflow)
        if cv_data.get("experience"):
            # Take only the most recent 5 experiences to keep within limits
            experiences = (
                cv_data["experience"][:5]
                if len(cv_data["experience"]) > 5
                else cv_data["experience"]
            )
            sections["experience"] = {"experience": experiences}

        # Education section
        if cv_data.get("education"):
            sections["education"] = {"education": cv_data["education"]}

        # Skills section
        if cv_data.get("skills"):
            sections["skills"] = {"skills": cv_data["skills"]}

        # If no sections, put everything in one
        if not sections:
            sections["full"] = cv_data

        return sections

    def _analyze_single_section(self, section_name, section_data, service):
        """Analyze a single CV section."""
        prompts = {
            "personal": """
            Analyze the personal information section of this CV. Focus on completeness and professionalism.
            Return JSON with personal info assessment.
            """,
            "experience": """
            Analyze the work experience section of this CV. Focus on career progression, achievements, and job relevance.
            Return JSON with experience assessment.
            """,
            "education": """
            Analyze the education section of this CV. Focus on qualifications and relevance to career goals.
            Return JSON with education assessment.
            """,
            "skills": """
            Analyze the provided skills list from the CV. Categorize each skill into technical/hard skills and soft skills.
            For each skill, determine if it's technical (tools, software, methodologies, specific expertise) or soft (interpersonal, leadership, communication).
            Return JSON with skills assessment based on the provided skills.
            """,
            "full": """
            Provide a comprehensive analysis of this CV.
            Return JSON with overall assessment.
            """,
        }

        prompt = f"""
        {prompts.get(section_name, prompts['full'])}

        Section Data:
        {json.dumps(section_data, indent=2)}

        Return ONLY valid JSON with no additional text. For skills section, categorize the provided skills into technical and soft skills:

        {{
            "assessment": "<brief_assessment>",
            "score": "<score_1-10>",
            "strengths": ["<strength1>", "<strength2>"],
            "issues": ["<issue1>", "<issue2>"],
            "suggestions": ["<suggestion1>", "<suggestion2>"],
            "identified_skills": {{
                "technical": ["<specific_technical_skill_1>", "<specific_technical_skill_2>"],
                "soft": ["<specific_soft_skill_1>", "<specific_soft_skill_2>"]
            }}
        }}
        """

        response = service.make_custom_request(prompt, max_tokens=2000)

        # Handle response - could be dict (already parsed) or string
        if isinstance(response, dict):
            # Already parsed - return as is
            return response
        elif isinstance(response, str):
            # String response - needs parsing
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse {section_name} analysis response: {response[:200]}..."
                )
                return {
                    "assessment": f"Analysis of {section_name} section",
                    "score": 7,
                    "strengths": [f"Contains {section_name} information"],
                    "issues": ["Analysis response parsing failed"],
                    "suggestions": ["Review section manually"],
                }
        else:
            # Unexpected type
            logger.error(f"Unexpected response type from service: {type(response)}")
            return {
                "assessment": f"Analysis of {section_name} section",
                "score": 7,
                "strengths": [f"Contains {section_name} information"],
                "issues": ["Unexpected response format"],
                "suggestions": ["Review section manually"],
            }

    def _combine_section_analyses(self, section_analyses, original_cv_data):
        """Combine section analyses into final comprehensive result."""
        logger.info("🔀 Combining section analyses")

        # Start with fallback structure
        result = {
            "overall_score": {
                "score": 7.5,
                "feedback": "Comprehensive CV analysis completed",
            },
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [],
            "potential_roles": [],  # Will be filled below
            "section_scores": {
                "content_completeness": 8,  # Will be calculated dynamically
                "format_structure": 8,
                "skills_relevance": 7,  # Will be calculated dynamically
                "job_history": 8,
                "education": 8,
                "overall_impact": 8,
            },
            "ats_readiness": {
                "score": 80,
                "issues": [],
                "suggestions": [
                    "Ensure consistent formatting",
                    "Use standard section headers",
                ],
            },
            "experience_level": {
                "classification": "mid-level",
                "years_experience": 5,
                "career_stage": "Established professional",
            },
            "skills_assessment": {
                "hard_skills": [],
                "soft_skills": [],
                "missing_skills": [],
            },
            "employment_gaps_analysis": {
                "has_gaps": "false",
                "feedback": "No significant employment gaps detected",
                "suggestions": [],
            },
        }

        # Calculate dynamic experience level based on CV data
        experience_years = self._calculate_experience_years(original_cv_data)
        experience_level = self._determine_experience_level(
            experience_years, original_cv_data
        )
        result["experience_level"] = experience_level

        # Calculate dynamic section scores based on CV content
        self._calculate_dynamic_section_scores(result, original_cv_data)

        # Extract skills from skills section analysis if available
        if section_analyses.get("skills") and section_analyses["skills"]:
            skills_analysis = section_analyses["skills"]
            # Always use categorization from parsed data for accuracy
            if original_cv_data.get("skills"):
                skills_list = original_cv_data["skills"]
                if isinstance(skills_list, list) and skills_list:
                    # Categorize skills into technical and soft
                    technical_skills, soft_skills = self._categorize_skills(skills_list)
                    result["skills_assessment"]["hard_skills"].extend(technical_skills)
                    result["skills_assessment"]["soft_skills"].extend(soft_skills)
            # Fallback to AI analysis if no parsed skills
            elif skills_analysis.get("identified_skills"):
                identified = skills_analysis["identified_skills"]
                if identified.get("technical"):
                    for skill in identified["technical"][:8]:
                        result["skills_assessment"]["hard_skills"].append(
                            {
                                "skill": skill,
                                "rating": 8,
                                "feedback": "Identified as technical skill",
                            }
                        )
                if identified.get("soft"):
                    for skill in identified["soft"][:6]:
                        result["skills_assessment"]["soft_skills"].append(
                            {
                                "skill": skill,
                                "rating": 8,
                                "feedback": "Identified as soft skill",
                            }
                        )
        # If no skills found, try experience section to infer skills
        elif section_analyses.get("experience") and original_cv_data.get("experience"):
            # Infer skills from job titles and descriptions
            inferred_skills = self._infer_skills_from_experience(
                original_cv_data["experience"]
            )
            result["skills_assessment"]["hard_skills"].extend(inferred_skills)

        # Generate realistic potential roles based on experience and skills (now that skills are populated)
        result["potential_roles"] = self._generate_potential_roles(
            original_cv_data,
            result["skills_assessment"]["hard_skills"],
            result["experience_level"],
        )

        # Add some default soft skills if none found
        if not result["skills_assessment"]["soft_skills"]:
            result["skills_assessment"]["soft_skills"] = [
                {
                    "skill": "Communication",
                    "rating": 8,
                    "feedback": "Demonstrated through experience",
                },
                {
                    "skill": "Problem Solving",
                    "rating": 7,
                    "feedback": "Required in professional roles",
                },
                {
                    "skill": "Teamwork",
                    "rating": 8,
                    "feedback": "Essential for workplace success",
                },
            ]

        # Combine strengths from all sections
        for section_name, analysis in section_analyses.items():
            if analysis and analysis.get("strengths"):
                result["strengths"].extend(
                    analysis["strengths"][:2]
                )  # Limit per section

        # Limit strengths to 6 total
        result["strengths"] = result["strengths"][:6]

        # Add some default weaknesses and suggestions if needed
        if not result["weaknesses"]:
            result["weaknesses"] = [
                "Could benefit from more quantifiable achievements",
                "Consider adding industry certifications",
            ]

        if not result["improvement_suggestions"]:
            result["improvement_suggestions"] = [
                "Add specific metrics to achievements",
                "Include relevant certifications",
                "Tailor content for target roles",
            ]

        # Calculate overall score as average of dynamic section scores
        section_scores = result["section_scores"]
        # Include all section scores in the average
        dynamic_scores = [
            section_scores.get("content_completeness", 7),
            section_scores.get("format_structure", 8),
            section_scores.get("skills_relevance", 7),
            section_scores.get("job_history", 7),
            section_scores.get("education", 7),
            section_scores.get("overall_impact", 8),
        ]
        overall_score = sum(dynamic_scores) / len(dynamic_scores)
        result["overall_score"]["score"] = round(overall_score, 1)
        result["overall_score"][
            "feedback"
        ] = f"Overall score calculated from CV content quality (average of {len(dynamic_scores)} sections)"

        logger.info(
            f"📊 Overall score calculated: {overall_score} from section scores: {dynamic_scores}"
        )
        return result

    def _infer_skills_from_experience(self, experience_data):
        """Infer skills from job experience data."""
        inferred_skills = []
        skill_keywords = {
            "management": [
                "Team Leadership",
                "Operations Management",
                "Staff Development",
            ],
            "retail": [
                "Customer Service",
                "Sales",
                "Inventory Management",
                "POS Systems",
            ],
            "sales": [
                "Sales Analytics",
                "Customer Relationship Management",
                "Negotiation",
            ],
            "supervisor": ["Team Supervision", "Performance Management", "Training"],
            "store": ["Store Operations", "Visual Merchandising", "Loss Prevention"],
            "financial": ["Budgeting", "Financial Reporting", "Cost Control"],
            "training": ["Employee Training", "Coaching", "Mentoring"],
        }

        for exp in experience_data[:3]:  # Check first 3 experiences
            if isinstance(exp, dict):
                title = exp.get("position", "").lower()
                company = exp.get("company", "").lower()
                description = exp.get("description", "").lower()

                for keyword, skills in skill_keywords.items():
                    if keyword in title or keyword in company or keyword in description:
                        for skill in skills[:2]:  # Limit to 2 skills per keyword match
                            if not any(s["skill"] == skill for s in inferred_skills):
                                inferred_skills.append(
                                    {
                                        "skill": skill,
                                        "rating": 7,
                                        "feedback": f"Inferred from {exp.get('position', 'experience')}",
                                    }
                                )

        return inferred_skills[:8]  # Limit to 8 inferred skills

    def _categorize_skills(self, skills_list):
        """Categorize a list of skills into technical and soft skills."""
        technical_keywords = [
            "software",
            "system",
            "tool",
            "platform",
            "analytics",
            "data",
            "inventory",
            "management",
            "reporting",
            "excel",
            "pos",
            "crm",
            "e-commerce",
            "digital",
            "operations",
            "logistics",
            "supply chain",
            "financial",
            "budgeting",
            "merchandising",
            "retail",
            "store",
            "presentation",
            "process improvement",
            "lean management",
            "visual",
            "sales",
            "marketing",
            # Creative and media production keywords
            "photography",
            "videography",
            "video",
            "audio",
            "editing",
            "production",
            "creative",
            "adobe",
            "premiere",
            "photoshop",
            "lightroom",
            "davinci",
            "resolve",
            "drone",
            "camera",
            "lighting",
            "studio",
            "retouching",
            "social media",
            "content",
            "multimedia",
            "podcast",
            "insta360",
            "action camera",
            "licensed",
            "piloting",
            "high-end",
            "fine art",
        ]

        soft_keywords = [
            "leadership",
            "communication",
            "team",
            "customer service",
            "problem solving",
            "coaching",
            "mentoring",
            "training",
            "relationship",
            "collaboration",
            "strategic",
            "planning",
            "execution",
            "development",
            "supervision",
            "interpersonal",
            "emotional intelligence",
            "conflict resolution",
            # Creative and professional skills
            "creative",
            "artistic",
            "independent",
            "project management",
            "conceptualization",
            "professional",
            "specializing",
            "proven track record",
            "full-scale",
            "high-quality",
            "content producer",
            "multimedia",
        ]

        technical_skills = []
        soft_skills = []

        for skill in skills_list:
            # Handle both string skills and parsed skill objects
            if isinstance(skill, str):
                skill_name = skill
            elif isinstance(skill, dict) and "name" in skill:
                skill_name = skill["name"]
            else:
                # Skip invalid skill format
                continue

            skill_lower = skill_name.lower()
            is_technical = any(keyword in skill_lower for keyword in technical_keywords)
            is_soft = any(keyword in skill_lower for keyword in soft_keywords)

            # Prioritize technical for retail context, then check soft skills
            if is_technical:
                technical_skills.append(
                    {
                        "skill": skill_name,
                        "rating": 8,
                        "feedback": "Identified as technical skill from CV",
                    }
                )
            elif is_soft:
                soft_skills.append(
                    {
                        "skill": skill_name,
                        "rating": 8,
                        "feedback": "Identified as soft skill from CV",
                    }
                )
            else:
                # Default to technical for retail context
                technical_skills.append(
                    {
                        "skill": skill_name,
                        "rating": 8,
                        "feedback": "Defaulted to technical skill from CV",
                    }
                )

        return technical_skills[:10], soft_skills[:8]  # Reasonable limits

    def _calculate_dynamic_section_scores(self, result, cv_data):
        """Calculate dynamic section scores based on CV content quality."""
        section_scores = result["section_scores"]

        # Content completeness - based on presence of key sections
        completeness_score = 6  # Base score
        if cv_data.get("personal_info"):
            completeness_score += 1
        if cv_data.get("experience") and len(cv_data["experience"]) > 0:
            completeness_score += 1
        if cv_data.get("education") and len(cv_data["education"]) > 0:
            completeness_score += 1
        if cv_data.get("skills") and len(cv_data["skills"]) > 0:
            completeness_score += 1
        section_scores["content_completeness"] = min(10, completeness_score)

        # Skills relevance - based on number and quality of skills
        skills_score = 5  # Base score
        if cv_data.get("skills"):
            num_skills = len(cv_data["skills"])
            if num_skills > 15:
                skills_score = 9
            elif num_skills > 10:
                skills_score = 8
            elif num_skills > 5:
                skills_score = 7
            else:
                skills_score = 6
        section_scores["skills_relevance"] = skills_score

        # Job history - based on experience length and number of roles
        job_history_score = 6  # Base score
        if cv_data.get("experience"):
            num_roles = len(cv_data["experience"])
            experience_years = self._calculate_experience_years(cv_data)

            if experience_years > 10 and num_roles >= 3:
                job_history_score = 9
            elif experience_years > 5 and num_roles >= 2:
                job_history_score = 8
            elif experience_years > 2:
                job_history_score = 7
        section_scores["job_history"] = job_history_score

        # Education - based on highest qualification level
        education_score = 6  # Base score
        if cv_data.get("education"):
            for edu in cv_data["education"]:
                degree = edu.get("degree", "").lower()
                if "phd" in degree or "doctorate" in degree:
                    education_score = 9
                    break
                elif "master" in degree or "mba" in degree:
                    education_score = 8
                elif "bachelor" in degree:
                    education_score = 7
        section_scores["education"] = education_score

        logger.info(f"Calculated dynamic section scores: {section_scores}")

    def _calculate_experience_years(self, cv_data):
        """Calculate total years of experience from CV data."""
        experience = cv_data.get("experience", [])
        if not experience:
            return 0

        total_years = 0
        current_year = 2025  # Current year

        for exp in experience:
            if isinstance(exp, dict):
                # Try both 'dates' field and 'start_date'/'end_date' fields
                dates = exp.get("dates", "")
                start_date = exp.get("start_date", "")
                end_date = exp.get("end_date", "")

                if dates:
                    # Try to extract years from date ranges
                    years = self._extract_years_from_dates(dates, current_year)
                    total_years += years
                elif start_date:
                    # Use start_date and end_date if available
                    combined_dates = (
                        f"{start_date} - {end_date if end_date else 'Present'}"
                    )
                    years = self._extract_years_from_dates(combined_dates, current_year)
                    total_years += years

        return min(total_years, 50)  # Cap at 50 years

    def _extract_years_from_dates(self, dates_str, current_year):
        """Extract years from date string like 'January 2016 – Present'."""
        try:
            dates_str = dates_str.lower().strip()

            # Handle cases with N/A or missing dates
            if not dates_str or dates_str in [
                "n/a",
                "n/a - n/a",
                "na",
                "not available",
                "",
            ]:
                return 0

            # Handle "present" or "current" - look for start year even with N/A
            if "present" in dates_str or "current" in dates_str:
                # Find the start year - could be in various formats
                import re

                # Look for years in 20XX format
                year_match = re.search(r"\b(20\d{2})\b", dates_str)
                if year_match:
                    start_year = int(year_match.group(1))
                    return max(0, current_year - start_year)

                # Look for years in XX format (like '16 for 2016)
                short_year_match = re.search(r"\b(1[0-9]|2[0-5])\b", dates_str)
                if short_year_match:
                    short_year = int(short_year_match.group(1))
                    # Convert to full year (assuming 2000s)
                    if short_year >= 10:
                        start_year = 2000 + short_year
                        return max(0, current_year - start_year)

            # Handle "N/A - PRESENT" case - assume some reasonable experience
            if "n/a" in dates_str and (
                "present" in dates_str or "current" in dates_str
            ):
                # For current roles with N/A start dates, assume 2-3 years experience
                return 2.5

            # Handle date ranges like "2016 - 2020" or "Jan 2016 - Dec 2020"
            import re

            years = re.findall(r"\b(20\d{2})\b", dates_str)
            if len(years) >= 2:
                start_year = int(years[0])
                end_year = int(years[-1])
                return max(0, end_year - start_year)
            elif len(years) == 1:
                start_year = int(years[0])
                # If only one year found and it's not current year, assume it's the start year
                if start_year < current_year:
                    return max(0, current_year - start_year)
                else:
                    # If the year is current year or future, assume 1 year
                    return 1

            # Look for month-year patterns like "Jan 2016"
            month_year_pattern = re.findall(
                r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})",
                dates_str,
                re.IGNORECASE,
            )
            if len(month_year_pattern) >= 2:
                start_year = int(month_year_pattern[0])
                end_year = int(month_year_pattern[-1])
                return max(0, end_year - start_year)
            elif len(month_year_pattern) == 1:
                start_year = int(month_year_pattern[0])
                return max(0, current_year - start_year)

            # If no years found but has date-like structure, assume some experience
            if any(
                word in dates_str
                for word in [
                    "jan",
                    "feb",
                    "mar",
                    "apr",
                    "may",
                    "jun",
                    "jul",
                    "aug",
                    "sep",
                    "oct",
                    "nov",
                    "dec",
                    "present",
                    "current",
                ]
            ):
                return 1  # Assume at least 1 year if date-like words are present

            return 0
        except Exception as e:
            logger.warning(f"Error parsing dates '{dates_str}': {e}")
            return 0

    def _determine_experience_level(self, years_experience, cv_data):
        """Determine experience level classification based on years and job titles."""
        # Get the most recent job title
        experience = cv_data.get("experience", [])
        recent_title = ""
        management_keywords = [
            "manager",
            "director",
            "supervisor",
            "lead",
            "head",
            "chief",
            "vp",
            "executive",
        ]
        senior_keywords = ["senior", "principal", "lead", "advanced"]

        if experience and isinstance(experience[0], dict):
            recent_title = experience[0].get("title", "").lower()
            company = experience[0].get("company", "").lower()

        # If years_experience is 0 but we have experience data, try to estimate
        if years_experience == 0 and experience:
            # Check for current roles (present/current in dates or end_date)
            current_roles = 0
            for exp in experience[:3]:  # Check first 3 experiences
                if isinstance(exp, dict):
                    dates = exp.get("dates", "").lower()
                    end_date = exp.get("end_date", "").lower()

                    # Check both 'dates' field and 'end_date' field
                    check_string = f"{dates} {end_date}".lower()
                    if (
                        "present" in check_string
                        or "current" in check_string
                        or "n/a - present" in check_string
                        or "now" in check_string
                    ):
                        current_roles += 1

            # Estimate experience based on number of roles and titles
            if current_roles > 0:
                years_experience = max(
                    2, len(experience) * 2.0
                )  # Estimate 2 years per role minimum
            elif len(experience) >= 3:
                years_experience = max(
                    6, len(experience) * 2.0
                )  # At least 6 years with multiple roles
            elif len(experience) >= 2:
                years_experience = 4  # At least 4 years with 2 roles
            else:
                years_experience = 2  # At least 2 years with 1 role

        # Determine level based on years and titles
        if years_experience >= 15 or any(
            keyword in recent_title
            for keyword in ["director", "vp", "chief", "head", "executive"]
        ):
            classification = "senior"
            career_stage = "Executive/Director level"
        elif years_experience >= 10 or any(
            keyword in recent_title
            for keyword in ["senior", "principal", "manager"] + management_keywords
        ):
            classification = "senior"
            career_stage = "Senior Management"
        elif years_experience >= 7 or any(
            keyword in recent_title for keyword in management_keywords
        ):
            classification = "mid-level"
            career_stage = "Management/Supervisory"
        elif years_experience >= 3 or any(
            keyword in recent_title for keyword in senior_keywords
        ):
            classification = "mid-level"
            career_stage = "Experienced Professional"
        else:
            classification = "entry-level"
            career_stage = "Early Career"

        return {
            "classification": classification,
            "years_experience": years_experience,
            "career_stage": career_stage,
        }

    def _generate_potential_roles(self, cv_data, hard_skills, experience_level):
        """Generate realistic potential roles based on CV data, skills, and experience level."""

        roles = []
        classification = experience_level.get("classification", "mid-level")
        years_experience = experience_level.get("years_experience", 5)

        # Get experience data
        experience = cv_data.get("experience", [])
        if experience:
            # Use the most recent job title as a base
            recent_job = experience[0] if isinstance(experience[0], dict) else {}
            job_title = recent_job.get("title", recent_job.get("position", "")).lower()
        else:
            job_title = ""

        # --- CAREER CHANGER LOGIC ---
        # If most experience is in a non-software/IT field, but hard_skills include software/IT, restrict to junior/entry-level
        software_keywords = [
            "software",
            "developer",
            "engineer",
            "programmer",
            "web",
            "python",
            "javascript",
            "react",
            "django",
            "html",
            "css",
            "full stack",
            "backend",
            "frontend",
            "it",
            "technology",
        ]
        # Count number of experiences in software/IT
        software_exp_count = 0
        for exp in experience:
            exp_title = (exp.get("title") or exp.get("position") or "").lower()
            if any(kw in exp_title for kw in software_keywords):
                software_exp_count += 1
        # If less than half of roles are software/IT, but hard_skills include software/IT, treat as career changer
        is_career_changer = False
        if experience and software_exp_count < max(1, len(experience) // 2):
            # Check if hard_skills include software/IT
            for skill_obj in hard_skills:
                skill_name = (
                    skill_obj.get("skill", "")
                    if isinstance(skill_obj, dict)
                    else str(skill_obj)
                ).lower()
                if any(kw in skill_name for kw in software_keywords):
                    is_career_changer = True
                    break

        # If career changer, force classification to entry-level for software/IT
        if is_career_changer:
            logger.info(
                f"🔄 Career changer detected: {software_exp_count}/{len(experience)} software roles. "
                f"Adjusting classification from '{experience_level.get('classification')}' to 'entry-level' for accurate role suggestions."
            )
            classification = "entry-level"

        # Map job titles to potential career progression based on experience level
        role_mappings = {
            "executive": {
                "senior retail operations manager": [
                    "Retail Operations Director",
                    "Chief Operations Officer",
                    "VP of Retail Operations",
                    "Head of Retail Operations",
                ],
                "retail operations manager": [
                    "Senior Retail Operations Manager",
                    "Retail Operations Director",
                    "Chief Operations Officer",
                    "VP of Retail Operations",
                ],
                "store manager": [
                    "Regional Operations Manager",
                    "Retail Operations Director",
                    "Chief Operations Officer",
                    "VP of Retail Operations",
                ],
                "operations manager": [
                    "Senior Operations Manager",
                    "Operations Director",
                    "Chief Operations Officer",
                    "VP of Operations",
                ],
                # Creative job titles
                "creative director": [
                    "Chief Creative Officer",
                    "VP of Creative Services",
                    "Executive Creative Director",
                    "Chief Content Officer",
                ],
                "photographer": [
                    "Director of Photography",
                    "Creative Director",
                    "Media Director",
                    "Photography Studio Director",
                ],
                "videographer": [
                    "Director of Videography",
                    "Media Production Director",
                    "Content Director",
                    "Video Production Director",
                ],
                "media producer": [
                    "Chief Content Officer",
                    "VP of Media Production",
                    "Media Director",
                    "Production Director",
                ],
                "content creator": [
                    "Chief Content Officer",
                    "VP of Content",
                    "Content Director",
                    "Digital Media Director",
                ],
            },
            "senior": {
                "senior retail operations manager": [
                    "Retail Operations Director",
                    "Regional Operations Manager",
                    "Head of Retail Operations",
                    "Senior Retail Operations Manager",
                ],
                "retail operations manager": [
                    "Senior Retail Operations Manager",
                    "Retail Operations Director",
                    "Regional Operations Manager",
                    "Operations Director",
                ],
                "store manager": [
                    "Regional Manager",
                    "Retail Operations Manager",
                    "Operations Director",
                    "Area Director",
                ],
                "operations manager": [
                    "Senior Operations Manager",
                    "Operations Director",
                    "Regional Operations Manager",
                    "Chief Operations Officer",
                ],
                # Creative job titles
                "creative director": [
                    "Senior Creative Director",
                    "VP of Creative Services",
                    "Executive Creative Director",
                    "Creative Services Director",
                ],
                "senior photographer": [
                    "Photography Director",
                    "Senior Creative Director",
                    "Media Production Director",
                    "Lead Photographer",
                ],
                "senior videographer": [
                    "Video Production Director",
                    "Senior Media Producer",
                    "Creative Director",
                    "Lead Videographer",
                ],
                "media producer": [
                    "Senior Media Producer",
                    "Media Production Director",
                    "Content Strategy Director",
                    "Digital Media Director",
                ],
                "content creator": [
                    "Senior Content Creator",
                    "Content Strategy Director",
                    "Digital Media Director",
                    "Social Media Director",
                ],
                "freelance photographer": [
                    "Photography Studio Owner",
                    "Senior Photographer",
                    "Photography Business Owner",
                    "Creative Entrepreneur",
                ],
            },
            "mid-level": {
                "senior retail operations manager": [
                    "Senior Retail Operations Manager",
                    "Retail Operations Director",
                    "Regional Operations Manager",
                    "Head of Retail Operations",
                ],
                "retail operations manager": [
                    "Senior Retail Operations Manager",
                    "Retail Operations Director",
                    "Regional Operations Manager",
                    "Operations Director",
                ],
                "store manager": [
                    "Retail Operations Manager",
                    "Regional Manager",
                    "Operations Manager",
                    "Area Manager",
                ],
                "retail manager": [
                    "Retail Operations Manager",
                    "Store Manager",
                    "Area Manager",
                    "Regional Manager",
                ],
                "operations manager": [
                    "Senior Operations Manager",
                    "Operations Director",
                    "Regional Operations Manager",
                    "Department Manager",
                ],
                "supervisor": [
                    "Store Manager",
                    "Operations Supervisor",
                    "Assistant Manager",
                    "Team Lead",
                ],
                "assistant manager": [
                    "Store Manager",
                    "Deputy Manager",
                    "Operations Supervisor",
                    "Team Leader",
                ],
                # Creative job titles
                "photographer": [
                    "Senior Photographer",
                    "Photography Specialist",
                    "Photo Editor",
                    "Digital Photographer",
                ],
                "videographer": [
                    "Senior Videographer",
                    "Video Production Specialist",
                    "Video Editor",
                    "Multimedia Producer",
                ],
                "creative specialist": [
                    "Creative Manager",
                    "Art Director",
                    "Creative Coordinator",
                    "Design Specialist",
                ],
                "media producer": [
                    "Media Production Manager",
                    "Content Producer",
                    "Digital Media Specialist",
                    "Production Coordinator",
                ],
                "content creator": [
                    "Content Marketing Manager",
                    "Social Media Manager",
                    "Digital Content Specialist",
                    "Content Coordinator",
                ],
                "freelance photographer": [
                    "Photography Studio Manager",
                    "Freelance Photography Business Owner",
                    "Creative Entrepreneur",
                    "Photography Consultant",
                ],
                "freelance videographer": [
                    "Video Production Studio Owner",
                    "Freelance Video Producer",
                    "Media Production Consultant",
                    "Content Creation Entrepreneur",
                ],
            },
            "entry-level": {
                "sales associate": [
                    "Senior Sales Associate",
                    "Sales Supervisor",
                    "Customer Service Lead",
                    "Team Leader",
                ],
                "team leader": [
                    "Supervisor",
                    "Assistant Manager",
                    "Store Manager",
                    "Operations Coordinator",
                ],
                "supervisor": [
                    "Assistant Manager",
                    "Store Manager",
                    "Operations Supervisor",
                    "Team Leader",
                ],
                "assistant manager": [
                    "Store Manager",
                    "Deputy Manager",
                    "Operations Supervisor",
                    "Team Leader",
                ],
                # Creative job titles
                "junior photographer": [
                    "Photographer",
                    "Photography Assistant",
                    "Photo Production Assistant",
                    "Digital Imaging Specialist",
                ],
                "junior videographer": [
                    "Videographer",
                    "Video Production Assistant",
                    "Camera Operator",
                    "Media Production Assistant",
                ],
                "creative assistant": [
                    "Creative Specialist",
                    "Design Assistant",
                    "Creative Coordinator",
                    "Graphic Design Assistant",
                ],
                "media production assistant": [
                    "Media Producer",
                    "Content Production Assistant",
                    "Digital Media Assistant",
                    "Production Assistant",
                ],
                "content assistant": [
                    "Content Creator",
                    "Social Media Assistant",
                    "Digital Content Assistant",
                    "Content Creation Assistant",
                ],
            },
        }

        # Get appropriate role mappings for experience level
        level_mappings = role_mappings.get(classification, role_mappings["mid-level"])

        # Find matching roles
        for key, potential_roles in level_mappings.items():
            if key in job_title:
                roles.extend(potential_roles)
                break

        # If no specific mapping found, use skills to infer roles based on experience level
        if not roles and hard_skills:
            skill_based_roles = {
                "executive": {
                    "management": [
                        "Chief Operations Officer",
                        "VP of Operations",
                        "Director of Operations",
                        "Head of Department",
                    ],
                    "leadership": [
                        "Executive Director",
                        "Chief Executive",
                        "VP of Leadership",
                    ],
                    "retail": [
                        "Chief Retail Officer",
                        "VP of Retail",
                        "Retail Director",
                    ],
                    "sales": [
                        "Chief Sales Officer",
                        "VP of Sales",
                        "Director of Sales",
                    ],
                    "customer service": [
                        "Chief Customer Officer",
                        "VP of Customer Experience",
                        "Director of Customer Service",
                    ],
                    "inventory": [
                        "Chief Supply Chain Officer",
                        "VP of Supply Chain",
                        "Director of Logistics",
                    ],
                    "training": [
                        "Chief Learning Officer",
                        "VP of Talent Development",
                        "Director of HR",
                    ],
                    # Creative and media roles
                    "photography": [
                        "Chief Creative Officer",
                        "VP of Creative Services",
                        "Director of Photography",
                        "Creative Director",
                    ],
                    "videography": [
                        "Chief Content Officer",
                        "VP of Media Production",
                        "Director of Videography",
                        "Media Director",
                    ],
                    "creative": [
                        "Chief Creative Officer",
                        "VP of Creative",
                        "Creative Director",
                        "Art Director",
                    ],
                    "adobe": [
                        "Senior Creative Technologist",
                        "Digital Media Director",
                        "Creative Technology Lead",
                        "Multimedia Director",
                    ],
                    "production": [
                        "Chief Production Officer",
                        "VP of Production",
                        "Production Director",
                        "Media Production Director",
                    ],
                    "content": [
                        "Chief Content Officer",
                        "VP of Content",
                        "Content Director",
                        "Digital Content Director",
                    ],
                },
                "senior": {
                    "management": [
                        "Senior Operations Manager",
                        "Operations Director",
                        "Regional Manager",
                        "Department Head",
                    ],
                    "leadership": ["Senior Manager", "Director", "Senior Director"],
                    "retail": [
                        "Senior Retail Manager",
                        "Retail Director",
                        "Regional Retail Manager",
                    ],
                    "sales": [
                        "Senior Sales Manager",
                        "Sales Director",
                        "Business Development Director",
                    ],
                    "customer service": [
                        "Senior Customer Service Manager",
                        "Customer Experience Director",
                        "Client Relations Director",
                    ],
                    "inventory": [
                        "Senior Inventory Manager",
                        "Supply Chain Director",
                        "Logistics Director",
                    ],
                    "training": [
                        "Senior Training Manager",
                        "Talent Development Director",
                        "HR Director",
                    ],
                    # Software development skills
                    "django": [
                        "Senior Django Developer",
                        "Python Architect",
                        "Lead Backend Developer",
                        "Senior Full Stack Developer",
                        "Technical Lead",
                    ],
                    "javascript": [
                        "Senior JavaScript Developer",
                        "Lead Frontend Developer",
                        "Senior Full Stack Developer",
                        "JavaScript Architect",
                        "Technical Lead",
                    ],
                    "html": [
                        "Senior Frontend Developer",
                        "Lead Web Developer",
                        "Senior UI Developer",
                        "Frontend Architect",
                        "Web Development Lead",
                    ],
                    "css": [
                        "Senior Frontend Developer",
                        "Lead Web Developer",
                        "Senior UI Developer",
                        "Frontend Architect",
                        "Web Development Lead",
                    ],
                    "python": [
                        "Senior Python Developer",
                        "Lead Backend Developer",
                        "Python Architect",
                        "Senior Software Engineer",
                        "Technical Architect",
                    ],
                    "react": [
                        "Senior React Developer",
                        "Lead Frontend Developer",
                        "React Architect",
                        "Senior JavaScript Developer",
                        "Frontend Technical Lead",
                    ],
                    "software": [
                        "Senior Software Engineer",
                        "Software Architect",
                        "Lead Developer",
                        "Principal Engineer",
                        "Engineering Manager",
                    ],
                    "programming": [
                        "Senior Software Engineer",
                        "Lead Programmer",
                        "Principal Developer",
                        "Engineering Manager",
                        "Technical Architect",
                    ],
                    "web development": [
                        "Senior Web Developer",
                        "Lead Web Developer",
                        "Web Architect",
                        "Senior Full Stack Developer",
                        "Web Development Director",
                    ],
                    # Creative and media roles
                    "photography": [
                        "Senior Photographer",
                        "Photography Director",
                        "Lead Photographer",
                        "Senior Photo Editor",
                    ],
                    "videography": [
                        "Senior Videographer",
                        "Video Production Director",
                        "Lead Videographer",
                        "Senior Video Editor",
                    ],
                    "creative": [
                        "Senior Creative",
                        "Creative Director",
                        "Senior Art Director",
                        "Creative Lead",
                    ],
                    "adobe": [
                        "Senior Creative Technologist",
                        "Adobe Creative Lead",
                        "Digital Media Specialist",
                        "Senior Multimedia Designer",
                    ],
                    "production": [
                        "Senior Producer",
                        "Production Manager",
                        "Media Production Lead",
                        "Content Producer",
                    ],
                    "content": [
                        "Senior Content Creator",
                        "Content Strategy Director",
                        "Digital Content Manager",
                        "Social Media Director",
                    ],
                    "drone": [
                        "Senior Drone Operator",
                        "Aerial Photography Director",
                        "Drone Services Lead",
                        "Aerial Cinematographer",
                    ],
                    "studio": [
                        "Studio Manager",
                        "Photography Studio Director",
                        "Media Studio Lead",
                        "Production Studio Manager",
                    ],
                },
                "mid-level": {
                    "management": [
                        "Operations Manager",
                        "Team Manager",
                        "Department Manager",
                        "Project Manager",
                    ],
                    "leadership": ["Manager", "Supervisor", "Team Lead", "Coordinator"],
                    "retail": [
                        "Retail Manager",
                        "Store Manager",
                        "Area Manager",
                        "Sales Manager",
                    ],
                    "sales": [
                        "Sales Manager",
                        "Business Development Manager",
                        "Account Manager",
                        "Sales Coordinator",
                    ],
                    "customer service": [
                        "Customer Service Manager",
                        "Client Relations Manager",
                        "Service Coordinator",
                    ],
                    "inventory": [
                        "Inventory Manager",
                        "Operations Coordinator",
                        "Supply Chain Coordinator",
                        "Warehouse Manager",
                    ],
                    "training": [
                        "Training Manager",
                        "HR Coordinator",
                        "Learning and Development Coordinator",
                        "Training Coordinator",
                    ],
                    # Software development skills
                    "django": [
                        "Django Developer",
                        "Python Developer",
                        "Backend Developer",
                        "Full Stack Developer",
                        "Web Application Developer",
                    ],
                    "javascript": [
                        "JavaScript Developer",
                        "Frontend Developer",
                        "Web Developer",
                        "Full Stack Developer",
                        "React Developer",
                    ],
                    "html": [
                        "Frontend Developer",
                        "Web Developer",
                        "UI Developer",
                        "Full Stack Developer",
                        "Web Designer",
                    ],
                    "css": [
                        "Frontend Developer",
                        "Web Developer",
                        "UI Developer",
                        "Full Stack Developer",
                        "Web Designer",
                    ],
                    "python": [
                        "Python Developer",
                        "Backend Developer",
                        "Software Engineer",
                        "Data Engineer",
                        "Full Stack Developer",
                    ],
                    "react": [
                        "React Developer",
                        "Frontend Developer",
                        "JavaScript Developer",
                        "Full Stack Developer",
                        "Web Application Developer",
                    ],
                    "software": [
                        "Software Engineer",
                        "Software Developer",
                        "Application Developer",
                        "Systems Developer",
                        "Technology Specialist",
                    ],
                    "programming": [
                        "Software Engineer",
                        "Programmer",
                        "Developer",
                        "Software Developer",
                        "Application Developer",
                    ],
                    "web development": [
                        "Web Developer",
                        "Frontend Developer",
                        "Backend Developer",
                        "Full Stack Developer",
                        "Web Application Developer",
                    ],
                    # Creative and media roles
                    "photography": [
                        "Photographer",
                        "Photo Editor",
                        "Photography Specialist",
                        "Digital Photographer",
                    ],
                    "videography": [
                        "Videographer",
                        "Video Editor",
                        "Video Production Specialist",
                        "Multimedia Producer",
                    ],
                    "creative": [
                        "Creative Specialist",
                        "Graphic Designer",
                        "Art Director",
                        "Creative Coordinator",
                    ],
                    "adobe": [
                        "Adobe Creative Specialist",
                        "Digital Media Designer",
                        "Multimedia Designer",
                        "Creative Technologist",
                    ],
                    "production": [
                        "Production Coordinator",
                        "Media Producer",
                        "Content Producer",
                        "Production Assistant",
                    ],
                    "content": [
                        "Content Creator",
                        "Social Media Manager",
                        "Digital Content Specialist",
                        "Content Coordinator",
                    ],
                    "drone": [
                        "Drone Operator",
                        "Aerial Photographer",
                        "Drone Pilot",
                        "Aerial Cinematographer",
                    ],
                    "studio": [
                        "Studio Assistant",
                        "Photography Assistant",
                        "Studio Coordinator",
                        "Media Production Assistant",
                    ],
                    "editing": [
                        "Video Editor",
                        "Photo Editor",
                        "Media Editor",
                        "Post-Production Specialist",
                    ],
                    "social media": [
                        "Social Media Manager",
                        "Digital Marketing Specialist",
                        "Content Marketing Coordinator",
                        "Social Media Coordinator",
                    ],
                },
                "entry-level": {
                    "management": [
                        "Assistant Manager",
                        "Junior Manager",
                        "Management Trainee",
                        "Supervisor",
                    ],
                    "leadership": [
                        "Team Leader",
                        "Assistant",
                        "Coordinator",
                        "Support",
                    ],
                    "retail": [
                        "Retail Associate",
                        "Store Associate",
                        "Sales Associate",
                        "Customer Service Rep",
                    ],
                    "sales": [
                        "Sales Associate",
                        "Junior Sales Rep",
                        "Business Development Assistant",
                        "Sales Support",
                    ],
                    "customer service": [
                        "Customer Service Representative",
                        "Client Support Specialist",
                        "Service Assistant",
                    ],
                    "inventory": [
                        "Inventory Assistant",
                        "Operations Assistant",
                        "Warehouse Associate",
                        "Stock Clerk",
                    ],
                    "training": [
                        "Training Assistant",
                        "HR Assistant",
                        "Learning Support",
                        "Training Support",
                    ],
                    # Software development skills
                    "django": [
                        "Junior Django Developer",
                        "Python Developer",
                        "Backend Developer",
                        "Web Developer",
                        "Full Stack Developer",
                    ],
                    "javascript": [
                        "Junior JavaScript Developer",
                        "Frontend Developer",
                        "Web Developer",
                        "Full Stack Developer",
                        "React Developer",
                    ],
                    "html": [
                        "Junior Frontend Developer",
                        "Web Developer",
                        "UI Developer",
                        "Full Stack Developer",
                        "Web Designer",
                    ],
                    "css": [
                        "Junior Frontend Developer",
                        "Web Developer",
                        "UI Developer",
                        "Full Stack Developer",
                        "Web Designer",
                    ],
                    "python": [
                        "Junior Python Developer",
                        "Backend Developer",
                        "Software Engineer",
                        "Full Stack Developer",
                        "Web Developer",
                    ],
                    "react": [
                        "Junior React Developer",
                        "Frontend Developer",
                        "JavaScript Developer",
                        "Full Stack Developer",
                        "Web Developer",
                    ],
                    "software": [
                        "Junior Software Engineer",
                        "Software Developer",
                        "Application Developer",
                        "Junior Developer",
                        "Technology Specialist",
                    ],
                    "programming": [
                        "Junior Software Engineer",
                        "Programmer",
                        "Developer",
                        "Software Developer",
                        "Application Developer",
                    ],
                    "web development": [
                        "Junior Web Developer",
                        "Frontend Developer",
                        "Backend Developer",
                        "Full Stack Developer",
                        "Web Application Developer",
                    ],
                    # Software development skills
                    "django": [
                        "Django Developer",
                        "Python Developer",
                        "Web Developer",
                        "Backend Developer",
                        "Full Stack Developer",
                    ],
                    "javascript": [
                        "JavaScript Developer",
                        "Frontend Developer",
                        "Web Developer",
                        "Full Stack Developer",
                        "React Developer",
                    ],
                    "html": [
                        "Frontend Developer",
                        "Web Developer",
                        "UI Developer",
                        "Full Stack Developer",
                        "Web Designer",
                    ],
                    "css": [
                        "Frontend Developer",
                        "Web Developer",
                        "UI Developer",
                        "Full Stack Developer",
                        "Web Designer",
                    ],
                    "python": [
                        "Python Developer",
                        "Backend Developer",
                        "Data Engineer",
                        "Software Engineer",
                        "Full Stack Developer",
                    ],
                    "react": [
                        "React Developer",
                        "Frontend Developer",
                        "JavaScript Developer",
                        "Full Stack Developer",
                        "Web Developer",
                    ],
                    "software": [
                        "Software Engineer",
                        "Software Developer",
                        "Application Developer",
                        "Systems Developer",
                        "Technology Specialist",
                    ],
                    "programming": [
                        "Software Engineer",
                        "Programmer",
                        "Developer",
                        "Software Developer",
                        "Application Developer",
                    ],
                    "web development": [
                        "Web Developer",
                        "Frontend Developer",
                        "Backend Developer",
                        "Full Stack Developer",
                        "Web Application Developer",
                    ],
                    # Creative and media roles
                    "photography": [
                        "Junior Photographer",
                        "Photography Assistant",
                        "Photo Production Assistant",
                        "Digital Imaging Assistant",
                    ],
                    "videography": [
                        "Junior Videographer",
                        "Video Production Assistant",
                        "Camera Operator Assistant",
                        "Media Production Assistant",
                    ],
                    "creative": [
                        "Junior Creative",
                        "Design Assistant",
                        "Creative Assistant",
                        "Graphic Design Intern",
                    ],
                    "adobe": [
                        "Adobe Creative Assistant",
                        "Digital Media Assistant",
                        "Multimedia Assistant",
                        "Design Software Specialist",
                    ],
                    "production": [
                        "Production Assistant",
                        "Media Production Assistant",
                        "Content Production Assistant",
                        "Junior Producer",
                    ],
                    "content": [
                        "Content Assistant",
                        "Social Media Assistant",
                        "Digital Content Assistant",
                        "Content Creation Assistant",
                    ],
                    "drone": [
                        "Drone Operator Assistant",
                        "Aerial Photography Assistant",
                        "Junior Drone Pilot",
                        "Drone Operations Assistant",
                    ],
                    "studio": [
                        "Studio Assistant",
                        "Photography Studio Assistant",
                        "Media Studio Assistant",
                        "Production Studio Assistant",
                    ],
                    "editing": [
                        "Video Editing Assistant",
                        "Photo Editing Assistant",
                        "Media Editing Assistant",
                        "Post-Production Assistant",
                    ],
                    "social media": [
                        "Social Media Assistant",
                        "Digital Marketing Assistant",
                        "Content Marketing Assistant",
                        "Social Media Intern",
                    ],
                },
            }

            # Get appropriate skill-based roles for experience level
            level_skill_roles = skill_based_roles.get(
                classification, skill_based_roles["mid-level"]
            )

            for skill_obj in hard_skills[:5]:  # Check first 5 skills
                skill_name = (
                    skill_obj.get("skill", "").lower()
                    if isinstance(skill_obj, dict)
                    else str(skill_obj).lower()
                )
                for skill_key, potential_roles in level_skill_roles.items():
                    if skill_key in skill_name:
                        roles.extend(potential_roles)
                        break

        # Remove duplicates and limit to 5 roles
        seen = set()
        unique_roles = []
        for role in roles:
            if role not in seen:
                unique_roles.append(role)
                seen.add(role)

        # If still no roles, provide generic roles based on experience level
        if not unique_roles:
            fallback_roles = {
                "executive": [
                    "Chief Operations Officer",
                    "VP of Operations",
                    "Director of Operations",
                    "Executive Director",
                    "Chief Executive Officer",
                    # Creative fallbacks
                    "Chief Creative Officer",
                    "VP of Creative Services",
                    "Creative Director",
                    "Media Director",
                ],
                "senior": [
                    "Senior Operations Manager",
                    "Operations Director",
                    "Regional Manager",
                    "Senior Manager",
                    "Department Head",
                    # Creative fallbacks
                    "Senior Creative Director",
                    "Media Production Director",
                    "Creative Services Director",
                    "Digital Media Director",
                ],
                "mid-level": [
                    "Operations Manager",
                    "Store Manager",
                    "Retail Supervisor",
                    "Sales Manager",
                    "Team Manager",
                    # Creative fallbacks
                    "Creative Manager",
                    "Media Producer",
                    "Content Creator",
                    "Digital Media Specialist",
                    "Photography Studio Manager",
                ],
                "entry-level": [
                    "Store Associate",
                    "Retail Supervisor",
                    "Sales Associate",
                    "Customer Service Representative",
                    "Team Leader",
                    # Creative fallbacks
                    "Junior Photographer",
                    "Video Production Assistant",
                    "Creative Assistant",
                    "Media Production Assistant",
                    "Content Creation Assistant",
                    # Software development fallbacks
                    "Junior Web Developer",
                    "Junior Software Engineer",
                    "Frontend Developer",
                    "Backend Developer",
                    "Full Stack Developer",
                ],
            }
            unique_roles = fallback_roles.get(
                classification, fallback_roles["mid-level"]
            )

        return unique_roles[:5]
        """Save uploaded file to a temporary location and return the path"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.name)[1]
        ) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            return temp_file.name

    def extract_text_from_file(self, file_path):
        """Extract text from PDF or DOCX file"""
        file_extension = os.path.splitext(file_path)[1].lower()

        try:
            if file_extension == ".docx":
                doc = Document(file_path)
                text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            elif file_extension == ".pdf":
                reader = PdfReader(file_path)
                text = "\n".join([page.extract_text() for page in reader.pages])
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")

            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from {file_extension} file: {str(e)}")
            raise

    def save_uploaded_file(self, file):
        """Save uploaded file to a temporary location and return the path"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.name)[1]
        ) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            return temp_file.name

    @action(detail=False, methods=["POST"], url_path="parse-cv")
    def parse_cv(self, request):
        """
        Parse a CV document and replace any existing parsed CV for this user.
        """
        try:
            logger.info(
                f"CV parsing request from user {request.user.username} (ID: {request.user.id})"
            )

            # Validate request data
            if "file" not in request.FILES:
                return Response(
                    {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
                )

            file = request.FILES["file"]
            logger.info(f"Received file: {file.name} (size: {file.size} bytes)")

            # Check if user has confirmed overwrite if they have an existing CV
            force_overwrite = (
                request.data.get("force_overwrite", "false").lower() == "true"
            )

            # Check if user already has a parsed CV
            existing_cv = ParsedCV.objects.filter(user=request.user).first()
            logger.info(
                f"CV existence check: user={request.user.username}, existing_cv={existing_cv}, force_overwrite={force_overwrite}"
            )

            if existing_cv and not force_overwrite:
                # User has an existing CV but hasn't confirmed overwrite
                return Response(
                    {
                        "error": "Existing CV found",
                        "requires_confirmation": True,
                        "message": "You already have a parsed CV. Parsing a new CV will replace your existing one. Do you want to continue?",
                        "existing_cv_id": existing_cv.id,
                        "existing_cv_name": existing_cv.file_name,
                        "existing_cv_date": existing_cv.uploaded_at,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # If we're here, either:
            # 1. User doesn't have an existing CV

            # Delete any existing parsed CVs for this user
            if existing_cv:
                # Clean up temporary file if it exists
                if existing_cv.temp_file_path and os.path.exists(
                    existing_cv.temp_file_path
                ):
                    try:
                        os.remove(existing_cv.temp_file_path)
                        logger.info(
                            f"Removed temporary file of existing CV: {existing_cv.temp_file_path}"
                        )
                    except Exception as file_e:
                        logger.error(f"Error removing temporary file: {str(file_e)}")

                # Delete the existing CV
                existing_cv.delete()
                logger.info(
                    f"Deleted existing ParsedCV record for user {request.user.username}"
                )

            # Create a new ParsedCV record
            parsed_cv = ParsedCV.objects.create(
                user=request.user,
                file_name=file.name,
                file_size=file.size,
                mime_type=file.content_type,
                status="queued",
            )
            logger.info(f"Created new ParsedCV record with ID: {parsed_cv.id}")

            # Save uploaded file to temporary location
            temp_path = self.save_uploaded_file(file)
            logger.info(f"Saved uploaded file to temporary location: {temp_path}")

            # Update the ParsedCV record with the temporary file path
            parsed_cv.temp_file_path = temp_path
            parsed_cv.save(update_fields=["temp_file_path"])

            # Start processing the file asynchronously
            # This will need to be adjusted based on your actual processing logic
            # Here we're using a placeholder for the async processing
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor() as executor:
                executor.submit(self._process_cv_file, parsed_cv.id, temp_path)

            return Response(
                {
                    "id": parsed_cv.id,
                    "message": "CV upload successful. Processing has begun.",
                    "status": "queued",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            logger.error(f"Error in CV parsing: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _process_cv_file(self, cv_id, file_path):
        """
        Process a CV file asynchronously

        Args:
            cv_id (int): The ID of the ParsedCV record
            file_path (str): Path to the temporary file
        """
        try:
            # Helper to safely save using queryset.update to avoid stale-object save errors
            def safe_save(instance, update_fields=None):
                try:
                    if update_fields:
                        qs = ParsedCV.objects.filter(id=instance.id)
                        update_data = {f: getattr(instance, f) for f in update_fields}
                        updated = qs.update(**update_data)
                        if updated:
                            return True
                    # Fallback to full save
                    instance.save()
                    return True
                except Exception as e:
                    logger.exception(f"safe_save failed: {e}")
                    try:
                        instance.save()
                        return True
                    except Exception:
                        return False

            # Get the ParsedCV record
            parsed_cv = ParsedCV.objects.get(id=cv_id)

            # Update status to processing
            parsed_cv.status = "processing"
            safe_save(parsed_cv, update_fields=["status"])
            logger.info(f"Processing ParsedCV {cv_id} - Status updated to processing")

            start_time = time.time()

            # Extract text from the file
            try:
                extracted_text = self.extract_text_from_file(file_path)
                parsed_cv.extracted_text = extracted_text
                safe_save(parsed_cv, update_fields=["extracted_text"])
                logger.info(f"Extracted text from CV file for ParsedCV {cv_id}")
            except Exception as text_error:
                logger.error(f"Error extracting text from file: {str(text_error)}")
                parsed_cv.status = "failed"
                parsed_cv.error_message = f"Error extracting text: {str(text_error)}"
                safe_save(parsed_cv, update_fields=["status", "error_message"])
                return

            # Parse the CV using ENHANCED intelligent service selection (LLaMA → DeepSeek → Traditional)
            try:
                # Use AdvancedDocumentParser which includes our ENHANCED LLaMA parser
                from cv_parser.parsers import AdvancedDocumentParser

                parser = AdvancedDocumentParser()

                logger.info(
                    f"🚀 USING ENHANCED PARSER with LLaMA primary method for CV {cv_id}"
                )
                parsed_data = parser.parse_document(file_path)
                logger.info(f"✅ Enhanced parsing completed for CV {cv_id}")

                # Check if we got an error response with fallback data
                if "error" in parsed_data:
                    logger.warning(
                        f"CV parsing returned an error: {parsed_data.get('error')}"
                    )

                    # If we have fallback data, use it instead of failing
                    if "parsed_data_fallback" in parsed_data:
                        logger.info("Using fallback parsed data")
                        parsed_cv.status = "completed_with_errors"
                        parsed_cv.error_message = (
                            parsed_data.get("error", "")
                            + ": "
                            + parsed_data.get("message", "")
                        )
                        parsed_cv.parsed_data = parsed_data.get(
                            "parsed_data_fallback", {}
                        )
                        parsed_cv.processed_at = timezone.now()
                        parsed_cv.processing_time = time.time() - start_time

                        # Clear cached analysis data when new CV data is parsed
                        parsed_cv.analysis_data = None
                        parsed_cv.analysis_date = None

                        safe_save(
                            parsed_cv,
                            update_fields=[
                                "parsed_data",
                                "status",
                                "processed_at",
                                "processing_time",
                                "error_message",
                                "analysis_data",
                                "analysis_date",
                            ],
                        )
                        logger.info(
                            f"ParsedCV {cv_id} processing completed with errors in {parsed_cv.processing_time:.2f} seconds"
                        )
                        return
                    else:
                        # No fallback data, mark as failed
                        raise ValueError(parsed_data.get("error", "Unknown error"))

                # Save the parsed data
                parsed_cv.parsed_data = parsed_data
                parsed_cv.status = "completed"
                parsed_cv.processed_at = timezone.now()
                parsed_cv.processing_time = time.time() - start_time

                # Clear cached analysis data when new CV data is parsed
                parsed_cv.analysis_data = None
                parsed_cv.analysis_date = None

                safe_save(
                    parsed_cv,
                    update_fields=[
                        "parsed_data",
                        "status",
                        "processed_at",
                        "processing_time",
                        "analysis_data",
                        "analysis_date",
                    ],
                )
                logger.info(
                    f"ParsedCV {cv_id} processing completed successfully in {parsed_cv.processing_time:.2f} seconds"
                )

                # Add career trajectory analysis
                try:
                    logger.info(
                        f"🔍 Starting career trajectory analysis for CV {cv_id}"
                    )
                    deepseek_service = DeepSeekService()

                    # Check if DeepSeek is available
                    if not deepseek_service.api_key:
                        logger.warning(
                            f"⚠️ DeepSeek API key not configured - skipping career trajectory analysis for CV {cv_id}"
                        )
                        # Don't fail, just skip the analysis
                        parsed_cv.parsed_data["career_trajectory"] = {
                            "job_consistency": {
                                "score": 0,
                                "level": "Not Available",
                                "insights": [
                                    "AI analysis requires API key configuration"
                                ],
                                "recommendations": [],
                            },
                            "role_stability": {
                                "score": 0,
                                "level": "Not Available",
                                "average_tenure": "N/A",
                                "employment_gaps": 0,
                                "insights": [
                                    "AI analysis requires API key configuration"
                                ],
                                "flags": [],
                            },
                            "career_change_potential": {
                                "assessment": "Not Available",
                                "confidence": "Low",
                                "indicators": [],
                                "potential_directions": [],
                                "recommendations": [],
                            },
                        }
                        safe_save(parsed_cv, update_fields=["parsed_data"])
                    else:
                        # Run career analysis asynchronously
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            career_analysis = loop.run_until_complete(
                                deepseek_service.analyze_career_trajectory(parsed_data)
                            )

                            # Add career analysis to parsed_data
                            if "error" not in career_analysis:
                                parsed_cv.parsed_data["career_trajectory"] = (
                                    career_analysis
                                )

                                # Update experience_level with accurate total_experience from career trajectory
                                if career_analysis.get("role_stability", {}).get(
                                    "total_experience"
                                ):
                                    total_exp_str = career_analysis["role_stability"][
                                        "total_experience"
                                    ]
                                    # Extract number from string like "16.9 years"
                                    import re

                                    exp_match = re.search(r"(\d+\.?\d*)", total_exp_str)
                                    if exp_match:
                                        accurate_years = float(exp_match.group(1))
                                        # Update the years_experience in parsed_data
                                        if "experience_level" in parsed_cv.parsed_data:
                                            parsed_cv.parsed_data["experience_level"][
                                                "years_experience"
                                            ] = int(round(accurate_years))
                                            logger.info(
                                                f"✅ Updated years_experience to {int(round(accurate_years))} from career trajectory"
                                            )

                                safe_save(parsed_cv, update_fields=["parsed_data"])
                                logger.info(
                                    f"✅ Career trajectory analysis completed for CV {cv_id}"
                                )
                            else:
                                logger.error(
                                    f"❌ Career analysis returned error: {career_analysis.get('error')}"
                                )
                                # Still save it so we can see the error message
                                parsed_cv.parsed_data["career_trajectory"] = (
                                    career_analysis
                                )
                                safe_save(parsed_cv, update_fields=["parsed_data"])
                        finally:
                            loop.close()

                except Exception as career_error:
                    logger.error(
                        f"❌ Error in career trajectory analysis: {str(career_error)}"
                    )
                    logger.error(traceback.format_exc())
                    # Don't fail the entire parsing if career analysis fails
            except Exception as parse_error:
                logger.error(f"Error parsing CV: {str(parse_error)}")
                parsed_cv.status = "failed"
                parsed_cv.error_message = f"Error parsing CV: {str(parse_error)}"
                safe_save(parsed_cv, update_fields=["status", "error_message"])

        except ParsedCV.DoesNotExist:
            logger.error(f"ParsedCV with ID {cv_id} not found")
        except Exception as e:
            logger.error(f"Error in CV processing: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                parsed_cv = ParsedCV.objects.get(id=cv_id)
                parsed_cv.status = "failed"
                parsed_cv.error_message = f"Unexpected error: {str(e)}"
                parsed_cv.save(update_fields=["status", "error_message"])
            except:
                pass
        finally:
            # Clean up temporary file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Removed temporary file: {file_path}")
                except Exception as file_e:
                    logger.error(f"Error removing temporary file: {str(file_e)}")

    def _process_parsed_cv_background(self, parsed_cv_id):
        """
        Background task to process a CV.
        This runs in a separate thread to prevent worker timeouts.
        """
        # Set up a new database connection for this thread
        close_old_connections()

        try:
            # Get the ParsedCV object
            parsed_cv = ParsedCV.objects.get(id=parsed_cv_id)
            logger.info(
                f"Starting background processing for ParsedCV ID {parsed_cv_id}"
            )

            text = parsed_cv.extracted_text
            temp_path = parsed_cv.temp_file_path

            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Parse CV with DeepSeek - this is the slow operation
                parser = DeepSeekService()
                parsed_data = loop.run_until_complete(parser.parse_cv(text))
                logger.info(
                    f"Successfully parsed CV with DeepSeek for ParsedCV ID {parsed_cv_id}"
                )

                # Add career trajectory analysis
                try:
                    logger.info(
                        f"🔍 Starting career trajectory analysis for ParsedCV {parsed_cv_id}"
                    )
                    career_analysis = loop.run_until_complete(
                        parser.analyze_career_trajectory(parsed_data)
                    )

                    # Add career analysis to parsed_data
                    if "error" not in career_analysis:
                        parsed_data["career_trajectory"] = career_analysis

                        # Update experience_level with accurate total_experience from career trajectory
                        if career_analysis.get("role_stability", {}).get(
                            "total_experience"
                        ):
                            total_exp_str = career_analysis["role_stability"][
                                "total_experience"
                            ]
                            # Extract number from string like "16.9 years"
                            import re

                            exp_match = re.search(r"(\d+\.?\d*)", total_exp_str)
                            if exp_match:
                                accurate_years = float(exp_match.group(1))
                                # Update the years_experience in parsed_data
                                if "experience_level" in parsed_data:
                                    parsed_data["experience_level"][
                                        "years_experience"
                                    ] = int(round(accurate_years))
                                    logger.info(
                                        f"✅ Updated years_experience to {int(round(accurate_years))} from career trajectory"
                                    )

                        logger.info(
                            f"✅ Career trajectory analysis completed for ParsedCV {parsed_cv_id}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Career analysis returned error: {career_analysis.get('error')}"
                        )

                except Exception as career_error:
                    logger.error(
                        f"❌ Error in career trajectory analysis: {str(career_error)}"
                    )
                    logger.error(traceback.format_exc())
                    # Don't fail the entire parsing if career analysis fails

                # Update ParsedCV with parsed data
                parsed_cv.parsed_data = parsed_data
                parsed_cv.status = "completed"
                parsed_cv.processed_at = timezone.now()

                # Clear cached analysis data when new CV data is parsed
                parsed_cv.analysis_data = None
                parsed_cv.analysis_date = None

                parsed_cv.save()
                logger.info(
                    f"ParsedCV record {parsed_cv_id} updated - Status: completed"
                )

            except Exception as e:
                logger.error(f"Error parsing CV with DeepSeek: {str(e)}")
                logger.error(traceback.format_exc())
                parsed_cv.status = "failed"
                parsed_cv.error_message = str(e)
                parsed_cv.save()
            finally:
                loop.close()

                # Clean up temporary file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                        logger.info(f"Removed temporary file: {temp_path}")
                    except Exception as file_e:
                        logger.error(f"Error removing temporary file: {str(file_e)}")

        except Exception as e:
            logger.error(
                f"Critical error in background CV processing for ID {parsed_cv_id}: {str(e)}"
            )
            logger.error(traceback.format_exc())

            try:
                # Try to update the record even in case of errors
                parsed_cv = ParsedCV.objects.get(id=parsed_cv_id)
                parsed_cv.status = "failed"
                parsed_cv.error_message = f"Critical processing error: {str(e)}"
                parsed_cv.save()
            except Exception as db_e:
                logger.error(
                    f"Could not update ParsedCV record after error: {str(db_e)}"
                )

    @action(detail=False, methods=["POST"], url_path="transfer-to-writer")
    def transfer_to_writer(self, request, pk=None):
        """Transfer parsed CV data to the CV writer app"""
        try:
            # Get the ParsedCV instance by ID
            try:
                parsed_cv = self.get_object()  # This gets the ParsedCV by pk
                if parsed_cv.user != request.user:
                    return Response(
                        {"error": "Access denied: CV does not belong to user"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Extract parsed data from the ParsedCV object
                parsed_data = parsed_cv.parsed_data
                if not parsed_data:
                    return Response(
                        {"error": "No parsed data available for this CV"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                logger.info(
                    f"Found ParsedCV {pk} with parsed data for user {request.user.username}"
                )

            except ParsedCV.DoesNotExist:
                return Response(
                    {"error": "CV not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Also check if parsed_data was provided in request body (for backward compatibility)
            if not parsed_data:
                parsed_data = request.data.get("parsed_data")
                if not parsed_data:
                    logger.warning(
                        f"No parsed data available in CV {pk} or request body"
                    )
                    return Response(
                        {"error": "No parsed data provided"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            logger.info(
                f"Transferring parsed data to CV Writer for user {request.user.username}"
            )

            # Create a new CV in cv_writer
            cv_writer = CvWriter.objects.create(
                user=request.user, title="CV from AI Parser", status="active"
            )
            logger.info(f"Created new CV Writer record with ID: {cv_writer.id}")

            # Create professional summary if available
            if parsed_data.get("professional_summary"):
                ProfessionalSummary.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    summary=parsed_data.get("professional_summary"),
                )
                logger.info(f"Added professional summary to CV Writer")

            # Helper function to parse dates
            def parse_date(date_str):
                """Parse various date formats to YYYY-MM-DD"""
                if not date_str or date_str.lower() in ["present", "current", "now"]:
                    return None

                try:
                    # Handle different date formats
                    if len(date_str) == 7 and "-" in date_str:  # YYYY-MM format
                        return f"{date_str}-01"  # Add day as 01
                    elif len(date_str) == 4:  # YYYY format
                        return f"{date_str}-01-01"  # Add month and day as 01
                    elif len(date_str) == 10:  # Already YYYY-MM-DD
                        return date_str
                    else:
                        # Try to parse other formats
                        from datetime import datetime

                        try:
                            # Try common formats
                            for fmt in ["%Y-%m", "%Y", "%m/%Y", "%m-%Y"]:
                                try:
                                    dt = datetime.strptime(date_str, fmt)
                                    return dt.strftime("%Y-%m-01")
                                except ValueError:
                                    continue
                        except:
                            pass
                        return None
                except:
                    return None

            # Create experiences
            experiences = parsed_data.get("experience", [])
            logger.info(
                f"🔍 ENHANCED PARSER: Processing {len(experiences)} experiences from parsed data"
            )
            for i, exp_data in enumerate(experiences):
                job_title = exp_data.get("job_title", "N/A")
                company = exp_data.get("company", "N/A")
                logger.info(
                    f'🔍 ENHANCED PARSER: Experience {i}: "{job_title}" at "{company}"'
                )
                if job_title.startswith("Position at"):
                    logger.warning(
                        f"⚠️ ENHANCED PARSER: Still getting 'Position at' format - parser needs improvement"
                    )

            for exp_data in experiences:
                # Parse start/end dates properly - provide better defaults when parsing fails
                start_date = parse_date(exp_data.get("start_date", None))
                end_date = parse_date(exp_data.get("end_date", None))

                # If dates couldn't be parsed, provide reasonable defaults based on job context
                if not start_date and not end_date:
                    # Check if this is marked as current employment
                    is_current = exp_data.get("current", False) or exp_data.get(
                        "is_current", False
                    )

                    if is_current:
                        # For current roles, assume started 2-3 years ago
                        from datetime import datetime, timedelta

                        start_date = (
                            datetime.now() - timedelta(days=365 * 2.5)
                        ).strftime("%Y-%m-%d")
                        end_date = None  # Current role
                    else:
                        # For past roles, try to estimate based on job title seniority
                        job_title_lower = job_title.lower()
                        if any(
                            keyword in job_title_lower
                            for keyword in [
                                "senior",
                                "lead",
                                "principal",
                                "manager",
                                "director",
                            ]
                        ):
                            # Senior roles typically 3-5 years
                            start_date = (
                                datetime.now() - timedelta(days=365 * 4)
                            ).strftime("%Y-%m-%d")
                            end_date = (
                                datetime.now() - timedelta(days=365 * 1)
                            ).strftime("%Y-%m-%d")
                        elif any(
                            keyword in job_title_lower
                            for keyword in ["junior", "associate", "assistant"]
                        ):
                            # Junior roles typically 1-2 years
                            start_date = (
                                datetime.now() - timedelta(days=365 * 1.5)
                            ).strftime("%Y-%m-%d")
                            end_date = (
                                datetime.now() - timedelta(days=365 * 0.5)
                            ).strftime("%Y-%m-%d")
                        else:
                            # Mid-level roles typically 2-3 years
                            start_date = (
                                datetime.now() - timedelta(days=365 * 2.5)
                            ).strftime("%Y-%m-%d")
                            end_date = (
                                datetime.now() - timedelta(days=365 * 1)
                            ).strftime("%Y-%m-%d")

                # Extract job title - try multiple field names
                raw_title = (
                    exp_data.get("job_title")
                    or exp_data.get("title")
                    or exp_data.get("position")
                    or "Unknown Position"
                )

                # Extract company name - try multiple field names
                raw_company = (
                    exp_data.get("company_name")
                    or exp_data.get("company")
                    or exp_data.get("employer")
                    or "Unknown Company"
                )

                # Handle "Position at Company" format
                if " at " in raw_title and raw_company == "Unknown Company":
                    # Split "Position at Company Name" format
                    parts = raw_title.split(" at ", 1)
                    if len(parts) == 2:
                        job_title = (
                            parts[0].strip()
                            if parts[0].strip() != "Position"
                            else "Unknown Position"
                        )
                        company_name = parts[1].strip()
                    else:
                        job_title = raw_title
                        company_name = raw_company
                else:
                    job_title = raw_title
                    company_name = raw_company

                # 🚨 PREVENT DUPLICATES: Check if this experience already exists for this CV
                existing_exp = Experience.objects.filter(
                    user=request.user,
                    cv=cv_writer,
                    company_name=company_name,
                    job_title=job_title,
                ).first()

                if not existing_exp:
                    Experience.objects.create(
                        user=request.user,
                        cv=cv_writer,
                        company_name=company_name,
                        job_title=job_title,
                        start_date=start_date,
                        end_date=end_date,
                        current=exp_data.get("current", False),
                        job_description=exp_data.get("description", ""),
                        achievements="",  # Required field
                        employment_type="Full-time",  # Required field with default
                    )
                    logger.info(f"Created experience: {job_title} at {company_name}")
                else:
                    logger.info(
                        f"Skipped duplicate experience: {job_title} at {company_name}"
                    )
            logger.info(f"Added {len(experiences)} experiences to CV Writer")

            # Helper function to detect if an education entry is actually a certification
            def is_certification(edu_data):
                """
                Determine if an education entry is actually a certification/bootcamp
                Returns True if it should be in certifications, False if legitimate education
                Returns "SKIP_WORK_EXPERIENCE" if it's work experience wrongly placed
                """
                degree = edu_data.get("degree", "").lower()
                institution = edu_data.get("institution", "").lower()
                field = edu_data.get("field", "").lower()

                # 🚨 CRITICAL: Check if this is actually work experience misplaced in education
                job_title_keywords = [
                    "manager",
                    "analyst",
                    "officer",
                    "director",
                    "coordinator",
                    "specialist",
                    "consultant",
                    "administrator",
                    "executive",
                    "developer",
                    "engineer",
                    "designer",
                    "technician",
                    "supervisor",
                    "assistant",
                    "associate",
                    "lead",
                    "senior",
                    "junior",
                    "principal",
                    "founder",
                    "co-founder",
                    "ceo",
                    "cto",
                    "cfo",
                    "president",
                    "vice president",
                ]

                # Check if degree field contains job title keywords but not degree keywords
                is_job_title = any(keyword in degree for keyword in job_title_keywords)
                has_degree_word = any(
                    word in degree
                    for word in [
                        "degree",
                        "diploma",
                        "bachelor",
                        "master",
                        "phd",
                        "certificate",
                        "certification",
                    ]
                )

                if is_job_title and not has_degree_word:
                    logger.warning(
                        f"⚠️ WORK EXPERIENCE DETECTED in education: '{degree}' - This should NOT be in education!"
                    )
                    return "SKIP_WORK_EXPERIENCE"

                # Keywords that indicate certification, not formal education
                cert_keywords = [
                    "bootcamp",
                    "certification",
                    "certificate",
                    "training",
                    "course",
                    "workshop",
                    "program",
                    "diploma level",
                    "l3 diploma",
                    "l4 diploma",
                    "l5 diploma",
                    "nvq",
                ]

                # Institutions that offer certifications, not degrees
                cert_institutions = [
                    "code institute",
                    "coursera",
                    "udemy",
                    "linkedin learning",
                    "pluralsight",
                    "udacity",
                    "edx",
                    "codecademy",
                    "freecodecamp",
                    "google",
                    "microsoft",
                    "aws",
                    "ibm",
                    "cisco",
                    "oracle",
                    "waes",
                    "ilx group",
                    "skillsoft",
                    "general assembly",
                ]

                # Check if degree name contains certification keywords
                for keyword in cert_keywords:
                    if keyword in degree or keyword in field:
                        logger.info(
                            f"🔍 Detected certification (keyword '{keyword}'): {degree}"
                        )
                        return True

                # Check if institution is known certification provider
                for provider in cert_institutions:
                    if provider in institution:
                        logger.info(
                            f"🔍 Detected certification (provider '{provider}'): {degree} from {institution}"
                        )
                        return True

                # Check if it's a formal degree (these should stay in education)
                formal_degrees = [
                    "bachelor",
                    "master",
                    "phd",
                    "doctorate",
                    "mba",
                    "bsc",
                    "msc",
                    "ba",
                    "ma",
                    "beng",
                    "meng",
                    "associate of",
                    "doctor of",
                ]

                for formal in formal_degrees:
                    if formal in degree:
                        logger.info(f"✅ Confirmed formal education: {degree}")
                        return False

                # If degree contains educational words, treat as education
                if any(word in degree for word in ["degree", "diploma"]):
                    logger.info(
                        f"✅ Contains degree/diploma keyword, treating as education: {degree}"
                    )
                    return False

                # If we can't determine, assume it's a certification to be safe
                logger.info(f"⚠️ Uncertain, treating as certification: {degree}")
                return True

            # Create education entries - but filter out certifications and work experience
            education_entries = parsed_data.get("education", [])
            misplaced_certifications = []  # Track certifications found in education
            work_experience_in_education_count = 0
            actual_education_count = 0

            for edu_data in education_entries:
                # Check if this is actually a certification or work experience
                classification = is_certification(edu_data)

                if classification == "SKIP_WORK_EXPERIENCE":
                    # This is work experience wrongly placed in education - skip it entirely
                    work_experience_in_education_count += 1
                    logger.error(
                        f"🚨 SKIPPING work experience in education: {edu_data.get('degree')} at {edu_data.get('institution')}"
                    )
                    continue
                elif classification is True:
                    # Move to certifications instead
                    misplaced_certifications.append(edu_data)
                    logger.info(
                        f"Moving '{edu_data.get('degree')}' from education to certifications"
                    )
                    continue

                # This is legitimate education - process normally
                # Parse start/end dates properly - provide better defaults for education
                start_date = parse_date(edu_data.get("start_date", None))
                end_date = parse_date(edu_data.get("end_date", None))

                # If dates couldn't be parsed, provide reasonable defaults for education
                if not start_date and not end_date:
                    degree = edu_data.get("degree", "").lower()

                    # Estimate education duration based on degree type
                    from datetime import datetime, timedelta

                    if "phd" in degree or "doctorate" in degree:
                        # PhD typically 4-6 years
                        start_date = (
                            datetime.now() - timedelta(days=365 * 5)
                        ).strftime("%Y-%m-%d")
                        end_date = (datetime.now() - timedelta(days=365 * 1)).strftime(
                            "%Y-%m-%d"
                        )
                    elif "master" in degree or "mba" in degree:
                        # Master's typically 1-2 years
                        start_date = (
                            datetime.now() - timedelta(days=365 * 2)
                        ).strftime("%Y-%m-%d")
                        end_date = (datetime.now() - timedelta(days=365 * 1)).strftime(
                            "%Y-%m-%d"
                        )
                    elif "bachelor" in degree:
                        # Bachelor's typically 3-4 years
                        start_date = (
                            datetime.now() - timedelta(days=365 * 4)
                        ).strftime("%Y-%m-%d")
                        end_date = (datetime.now() - timedelta(days=365 * 1)).strftime(
                            "%Y-%m-%d"
                        )
                    else:
                        # Default to recent education
                        start_date = (
                            datetime.now() - timedelta(days=365 * 2)
                        ).strftime("%Y-%m-%d")
                        end_date = (datetime.now() - timedelta(days=365 * 1)).strftime(
                            "%Y-%m-%d"
                        )

                Education.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    school_name=edu_data.get("institution", "Unknown Institution"),
                    degree=edu_data.get("degree", "Unknown Degree"),
                    field_of_study=edu_data.get("field", ""),
                    start_date=start_date,
                    end_date=end_date,
                    current=edu_data.get("current", False),
                )
                actual_education_count += 1

            # Log summary of what was filtered
            if work_experience_in_education_count > 0:
                logger.warning(
                    f"🚨 FILTERED OUT {work_experience_in_education_count} work experience entries from education section!"
                )
            logger.info(
                f"Added {actual_education_count} education entries to CV Writer "
                f"(filtered out {len(misplaced_certifications)} certifications, "
                f"{work_experience_in_education_count} work experiences)"
            )

            # Create skills
            skills = parsed_data.get("skills", [])
            for skill_data in skills:
                # Handle both string and object formats
                if isinstance(skill_data, str):
                    skill_name = skill_data
                    skill_level = "Intermediate"  # Default level
                else:
                    skill_name = skill_data.get("name", "Unknown Skill")
                    skill_level = skill_data.get("level", "Intermediate")

                Skill.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    skill_name=skill_name,
                    skill_level=skill_level,
                )
            logger.info(f"Added {len(skills)} skills to CV Writer")

            # Create languages
            languages = parsed_data.get("languages", [])
            for lang_data in languages:
                # Handle both string and object formats
                if isinstance(lang_data, str):
                    lang_name = lang_data
                    proficiency = "Intermediate"  # Default level
                else:
                    lang_name = lang_data.get("name", "Unknown Language")
                    proficiency = lang_data.get("proficiency", "Intermediate")

                Language.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    language=lang_name,
                    proficiency=proficiency,
                )
            logger.info(f"Added {len(languages)} languages to CV Writer")

            # Create certifications - include both regular certifications AND misplaced ones from education
            certifications = parsed_data.get("certifications", [])

            # Add misplaced certifications that were filtered out from education
            for edu_cert in misplaced_certifications:
                # Convert education format to certification format
                cert_converted = {
                    "name": edu_cert.get("degree", "Unknown Certification"),
                    "issuer": edu_cert.get("institution", ""),
                    "issue_date": edu_cert.get("end_date", None),
                    "field": edu_cert.get("field", ""),
                }
                certifications.append(cert_converted)
                logger.info(
                    f"Added misplaced certification: {cert_converted['name']} from {cert_converted['issuer']}"
                )

            for cert_data in certifications:
                # Handle both string and object formats
                if isinstance(cert_data, str):
                    cert_name = cert_data
                    issuer = ""
                    issue_date = None
                else:
                    cert_name = cert_data.get("name", "Unknown Certification")
                    issuer = cert_data.get("issuer", "")
                    issue_date = parse_date(cert_data.get("issue_date", None))

                # Check if issuer is a valid URL, otherwise include it in the name
                certificate_name = cert_name
                certificate_link = None

                if issuer:
                    if issuer.startswith(("http://", "https://")):
                        certificate_link = issuer  # It's a URL
                    else:
                        certificate_name = (
                            f"{cert_name} - {issuer}"  # Include issuer in name
                        )

                Certification.objects.create(
                    user=request.user,
                    cv=cv_writer,
                    certificate_name=certificate_name,
                    certificate_link=certificate_link,
                    certificate_date=issue_date,
                )
            logger.info(
                f"Added {len(certifications)} certifications to CV Writer "
                f"(including {len(misplaced_certifications)} recovered from education)"
            )

            return Response(
                {
                    "status": "success",
                    "message": "CV data transferred to CV Writer successfully",
                    "cv_id": cv_writer.id,
                }
            )

        except Exception as e:
            logger.error(f"Error transferring CV data to writer: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["POST"])
    def job_status(self, request):
        """Get status of multiple jobs"""
        job_ids = request.data.get("job_ids", [])
        if not job_ids:
            return Response(
                {"error": "No job IDs provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        results = {}
        for job_id in job_ids:
            try:
                cv = ParsedCV.objects.get(id=job_id, user=request.user)
                results[job_id] = {
                    "status": cv.status,
                    "error_message": cv.error_message,
                    "processed_at": cv.processed_at,
                }
            except ParsedCV.DoesNotExist:
                results[job_id] = {
                    "status": "not_found",
                    "error_message": "CV not found",
                }

        return Response(results)

    @action(detail=True, methods=["GET"], url_path="status")
    def get_status(self, request, pk=None):
        """
        Get the status of a CV parsing job
        """
        try:
            cv = self.get_object()
            data = {
                "id": cv.id,
                "status": cv.status,
                "uploaded_at": cv.uploaded_at,
                "processed_at": cv.processed_at,
                "processing_time": cv.processing_time,
                "error_message": cv.error_message,
            }
            return Response(data)
        except Exception as e:
            logger.error(f"Error getting CV status: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve CV status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def analyze(self, request):
        """
        Analyze a CV to provide feedback on content quality and improvement suggestions.

        Request format:
        {
            "cv_id": 1,
            "parser_type": "parsed_cv"  # or "cv_writer"
        }
        """
        try:
            # Validate input data
            cv_id = request.data.get("cv_id")
            parser_type = request.data.get("parser_type", "parsed_cv")
            force_refresh = request.data.get("force_refresh", False)

            if not cv_id:
                return Response(
                    {"error": "CV ID is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Get the CV data based on the parser type
            cv_data = None
            parsed_cv = None
            if parser_type == "parsed_cv":
                # Get from the cv_parser module
                try:
                    parsed_cv = ParsedCV.objects.get(id=cv_id, user=request.user)
                    cv_data = parsed_cv.parsed_data

                    # Check if we already have analysis data and it's not too old (e.g., less than 7 days)
                    # Only use cache if force_refresh is False
                    if (
                        not force_refresh
                        and parsed_cv.analysis_data
                        and parsed_cv.analysis_date
                        and (timezone.now() - parsed_cv.analysis_date).days < 7
                    ):
                        # Return cached analysis
                        logger.info(
                            f"Returning cached analysis for ParsedCV ID {cv_id}"
                        )
                        return Response(
                            {
                                "analysis": parsed_cv.analysis_data,
                                "cached": True,
                                "analysis_date": parsed_cv.analysis_date,
                            }
                        )
                    elif force_refresh:
                        logger.info(
                            f"Force refresh requested for ParsedCV ID {cv_id}, bypassing cache and re-parsing CV"
                        )

                        # Re-parse the CV with improved parser when force_refresh is True
                        try:
                            from cv_parser.parsers import AdvancedDocumentParser
                            import tempfile
                            import os

                            # Get the original file path - use temp_file_path since original_file doesn't exist in model
                            original_file_path = (
                                parsed_cv.temp_file_path
                                if parsed_cv.temp_file_path
                                else None
                            )

                            if original_file_path and os.path.exists(
                                original_file_path
                            ):
                                logger.info(
                                    f"Re-parsing original file: {original_file_path}"
                                )

                                # Use our enhanced parser
                                parser = AdvancedDocumentParser()
                                fresh_parsed_data = parser.parse_document_comprehensive(
                                    original_file_path
                                )

                                # Update the stored parsed data with fresh results and clear analysis cache
                                parsed_cv.parsed_data = fresh_parsed_data
                                parsed_cv.analysis_data = None  # Clear cached analysis
                                parsed_cv.analysis_date = None  # Clear analysis date
                                parsed_cv.save(
                                    update_fields=[
                                        "parsed_data",
                                        "analysis_data",
                                        "analysis_date",
                                    ]
                                )

                                # Use the fresh data for analysis
                                cv_data = fresh_parsed_data
                                logger.info(
                                    f"Successfully re-parsed CV with enhanced parser. Experience entries: {len(fresh_parsed_data.get('experience', []))}, Skills: {len(fresh_parsed_data.get('skills', []))}"
                                )

                            else:
                                logger.warning(
                                    f"Original file not found for re-parsing: {original_file_path}"
                                )
                                cv_data = parsed_cv.parsed_data

                        except Exception as reparse_error:
                            logger.error(f"Failed to re-parse CV: {str(reparse_error)}")
                            # Fall back to existing parsed data
                            cv_data = parsed_cv.parsed_data

                except ParsedCV.DoesNotExist:
                    return Response(
                        {
                            "error": "CV not found or you do not have permission to access it"
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
            elif parser_type == "cv_writer":
                # Get from the cv_writer module
                from cv_writer.models import (
                    CV,
                    PersonalInfo,
                    Experience,
                    Education,
                    Skill,
                )

                try:
                    cv = CV.objects.get(id=cv_id, user=request.user)
                    # Assemble CV data from different models
                    cv_data = self._assemble_cv_data(cv)
                except CV.DoesNotExist:
                    return Response(
                        {
                            "error": "CV not found or you do not have permission to access it"
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                return Response(
                    {"error": f"Invalid parser_type: {parser_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not cv_data:
                return Response(
                    {"error": "No CV data found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Prepare the prompt for analysis - use DeepSeek as primary service
            try:
                from .deepseek_service import DeepSeekService

                service = DeepSeekService()
                logger.info("Using DeepSeekService for CV analysis")
            except ImportError:
                # Fallback to FallbackService if DeepSeek not available
                logger.warning("DeepSeekService not available, using FallbackService")
                from .fallback_service import FallbackService

                service = FallbackService()

            # Continue with existing prompt preparation - optimized for concise responses
            # Debug: Log what CV data is being analyzed
            logger.info(
                f"🔍 Analysis Debug (standalone) - CV Data Keys: {list(cv_data.keys()) if isinstance(cv_data, dict) else 'Not a dict'}"
            )
            if isinstance(cv_data, dict):
                logger.info(
                    f"   • Experience entries: {len(cv_data.get('experience', []))}"
                )
                logger.info(
                    f"   • Education entries: {len(cv_data.get('education', []))}"
                )
                logger.info(f"   • Skills: {len(cv_data.get('skills', []))}")
                logger.info(f"   • Personal info present: {'personal_info' in cv_data}")

                # Log actual skills being analyzed
                if cv_data.get("skills"):
                    skills_sample = (
                        cv_data["skills"][:5]
                        if isinstance(cv_data["skills"], list)
                        else (
                            list(cv_data["skills"].keys())[:5]
                            if isinstance(cv_data["skills"], dict)
                            else []
                        )
                    )
                    logger.info(f"   • Skills sample: {skills_sample}")

                if cv_data.get("experience"):
                    logger.info(
                        f"   • First job title: {cv_data['experience'][0].get('position', 'N/A') if cv_data['experience'] else 'N/A'}"
                    )
                    logger.info(
                        f"   • First company: {cv_data['experience'][0].get('company', 'N/A') if cv_data['experience'] else 'N/A'}"
                    )

            # Use chunked analysis to prevent truncation
            analysis_result = self._analyze_cv_chunked(cv_data, service)

            # If we have a parsed_cv, store the analysis results
            if parser_type == "parsed_cv" and parsed_cv:
                parsed_cv.analysis_data = analysis_result
                parsed_cv.analysis_date = timezone.now()
                parsed_cv.save(update_fields=["analysis_data", "analysis_date"])
                logger.info(f"Stored analysis results for ParsedCV ID {cv_id}")

            return Response(
                {
                    "analysis": analysis_result,
                    "cached": False,
                    "analysis_date": (
                        timezone.now() if parser_type == "parsed_cv" else None
                    ),
                }
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during CV analysis: {e}", exc_info=True
            )
            return Response(
                {"error": "An unexpected server error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["GET"], url_path="debug-analysis")
    def debug_analysis(self, request, pk=None):
        """
        A secure endpoint to view the raw analysis data for debugging purposes.
        Only accessible by superusers.
        """
        if not request.user.is_superuser:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        try:
            parsed_cv = self.get_object()

            # Log file to check for raw response
            log_file_path = f"/tmp/raw_ai_response_cv_{pk}.log"
            raw_response = "Log file not found."
            try:
                with open(log_file_path, "r") as f:
                    raw_response = f.read()
            except FileNotFoundError:
                logger.warning(f"Raw AI response log file not found at {log_file_path}")

            return Response(
                {
                    "cv_id": parsed_cv.id,
                    "file_name": parsed_cv.file_name,
                    "analysis_data": parsed_cv.analysis_data,
                    "analysis_date": parsed_cv.analysis_date,
                    "raw_ai_response": raw_response,
                }
            )
        except Exception as e:
            logger.error(f"Error in debug_analysis: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["GET"], url_path="cv-data")
    def cv_data(self, request):
        """
        Return parsed CVs for the authenticated user.
        Frontend calls this endpoint to check for existing parsed CVs and cached analysis.
        Automatically generates analysis from parsed data if not available.
        """
        try:
            queryset = self.get_queryset().order_by("-processed_at")

            # Process each CV to ensure analysis data exists
            processed_data = []
            for cv in queryset:
                # If analysis_data is missing, generate it from parsed_data
                if not cv.analysis_data and cv.parsed_data:
                    logger.info(f"Auto-generating analysis for CV {cv.id}")
                    try:
                        # Import service for analysis - use DeepSeek as primary
                        try:
                            from .deepseek_service import DeepSeekService

                            service = DeepSeekService()
                            logger.info(
                                f"Using DeepSeekService for CV {cv.id} analysis"
                            )
                        except ImportError:
                            logger.warning(
                                f"DeepSeekService not available for CV {cv.id}, using FallbackService"
                            )
                            from .fallback_service import FallbackService

                            service = FallbackService()

                        # Generate analysis directly from parsed data
                        analysis_result = self._analyze_cv_chunked(
                            cv.parsed_data, service
                        )

                        # Ensure overall score is properly calculated
                        if "overall_score" in analysis_result:
                            score_value = analysis_result["overall_score"].get(
                                "score", 0
                            )
                            if score_value == 0.0:  # Only recalculate if actually 0.0
                                # Recalculate from dynamic section scores
                                section_scores = analysis_result.get(
                                    "section_scores", {}
                                )
                                if section_scores:
                                    # Use the same dynamic scores as in _combine_section_analyses
                                    dynamic_scores = [
                                        section_scores.get("content_completeness", 7),
                                        section_scores.get("format_structure", 8),
                                        section_scores.get("skills_relevance", 7),
                                        section_scores.get("job_history", 7),
                                        section_scores.get("education", 7),
                                        section_scores.get("overall_impact", 8),
                                    ]
                                    avg_score = sum(dynamic_scores) / len(
                                        dynamic_scores
                                    )
                                    analysis_result["overall_score"] = {
                                        "score": round(avg_score, 1),
                                        "feedback": f"Overall CV score of {round(avg_score, 1)}/10 based on content quality analysis",
                                    }
                                    logger.info(
                                        f"Recalculated overall score to {round(avg_score, 1)} for CV {cv.id} from dynamic section scores: {dynamic_scores}"
                                    )

                        # Save the analysis
                        cv.analysis_data = analysis_result
                        cv.analysis_date = timezone.now()
                        cv.save(update_fields=["analysis_data", "analysis_date"])

                        logger.info(f"Auto-generated and saved analysis for CV {cv.id}")
                    except Exception as analysis_error:
                        logger.warning(
                            f"Failed to auto-generate analysis for CV {cv.id}: {analysis_error}"
                        )
                        # Continue without analysis - frontend will use fallback

                processed_data.append(cv)

            serializer = ParsedCVSerializer(processed_data, many=True)
            data = serializer.data

            return Response(
                {
                    "exists": True if len(data) > 0 else False,
                    "data": data,
                    "type": "ai_cv_parser",
                }
            )
        except Exception as e:
            logger.error(f"Error fetching cv-data: {e}")
            return Response(
                {"exists": False, "data": None, "type": "ai_cv_parser"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
