"""
Job Recommendation Algorithm - AI-Powered Matching
Matches users with jobs based on multiple factors with weighted scoring
"""

from django.db.models import Q, F, Case, When, IntegerField, Value
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
from .career_fields import CAREER_FIELDS


class JobRecommendationEngine:
    """
    Advanced job recommendation engine using multi-factor scoring

    Scoring Factors:
    1. Skills Match (40%) - How many required skills user has
    2. Title Similarity (25%) - How similar job title is to user's experience
    3. Experience Level (20%) - Match between job requirements and user's level
    4. Location (10%) - Preference for user's location
    5. Recency (5%) - Newer jobs scored higher
    """

    # Weight configuration
    WEIGHTS = {
        "skills": 0.40,
        "title": 0.25,
        "experience": 0.20,
        "location": 0.10,
        "recency": 0.05,
    }

    # Minimum score threshold (0-100)
    MIN_SCORE_THRESHOLD = 30

    # Career field keywords for industry alignment (imported from career_fields.py)
    CAREER_FIELDS = CAREER_FIELDS

    def __init__(self, user, cv=None):
        self.user = user
        self.cv = cv
        self.user_profile = self._build_user_profile()

    def _build_user_profile(self):
        """Build comprehensive user profile from CV and database"""
        from cv_writer.models import Skill, Experience

        profile = {
            "skills": set(),
            "job_titles": [],
            "years_experience": 0,
            "experience_level": "entry_level",
            "location": None,
            "industries": set(),
            "career_field": None,  # Primary career field (technology, finance, etc.)
            "career_change_field": None,  # Target field if user is a career changer
        }

        # Get user skills - try CV first, then fallback to user
        if self.cv:
            skills = Skill.objects.filter(cv=self.cv)
        else:
            skills = Skill.objects.filter(user=self.user)
        profile["skills"] = set(skill.skill_name.lower() for skill in skills)

        # Get experience data - try CV first, then fallback to user
        if self.cv:
            experiences = Experience.objects.filter(cv=self.cv).order_by(
                "-end_date", "-start_date"
            )
        else:
            experiences = Experience.objects.filter(user=self.user).order_by(
                "-end_date", "-start_date"
            )

        if experiences.exists():
            # Get job titles
            profile["job_titles"] = [
                exp.job_title.lower() for exp in experiences if exp.job_title
            ]

            # Calculate total years of experience
            total_days = 0
            for exp in experiences:
                if exp.start_date:
                    end = exp.end_date or datetime.now().date()
                    days = (end - exp.start_date).days
                    total_days += max(days, 0)

            profile["years_experience"] = total_days / 365.25
            profile["total_years_experience"] = (
                total_days / 365.25
            )  # Store total for reference

            # Determine experience level
            if profile["years_experience"] >= 16:
                profile["experience_level"] = "executive"
            elif profile["years_experience"] >= 8:
                profile["experience_level"] = "senior"
            elif profile["years_experience"] >= 3:
                profile["experience_level"] = "mid"
            elif profile["years_experience"] >= 1:
                profile["experience_level"] = "junior"
            else:
                profile["experience_level"] = "entry_level"

            # Note: Location is stored in User profile or separate model, not in Experience
            # Skip location extraction from experience for now

        # Detect primary career field from job titles and skills
        profile["career_field"] = self._detect_career_field(profile)

        # CAREER CHANGER DETECTION: Calculate field-specific experience
        # If user has experience in multiple fields, only count experience in their current field
        if profile["career_field"] and experiences:
            field_specific_days = 0
            field_keywords = self.CAREER_FIELDS.get(profile["career_field"], [])

            # Filter keywords: Remove overly generic terms that cause false positives
            # For tech field, prioritize specific tech role keywords
            if profile["career_field"] == "technology":
                # Use only specific tech keywords, exclude generic terms like "analyst", "manager", "systems"
                tech_specific_keywords = [
                    "developer",
                    "engineer",
                    "programmer",
                    "software",
                    "devops",
                    "data scientist",
                    "machine learning",
                    "ai",
                    "cybersecurity",
                    "architect",
                    "coding",
                ]
                field_keywords = tech_specific_keywords

            for exp in experiences:
                # Check if this experience matches the current career field
                # STRICT MATCHING: Only check JOB TITLE, not description (to avoid false positives)
                job_title_lower = exp.job_title.lower() if exp.job_title else ""

                # Check if job title contains field-specific keywords
                is_in_field = any(
                    keyword in job_title_lower for keyword in field_keywords
                )

                if is_in_field and exp.start_date:
                    end = exp.end_date or datetime.now().date()
                    days = (end - exp.start_date).days
                    field_specific_days += max(days, 0)

            # Calculate field-specific years
            field_specific_years = field_specific_days / 365.25

            # If field-specific experience is significantly less than total (career changer)
            # Use field-specific years instead
            if field_specific_years < profile["total_years_experience"] * 0.7:
                # Career changer detected! Use relevant experience only
                profile["years_experience"] = field_specific_years
                profile["is_career_changer"] = True
                profile["career_change_note"] = (
                    f"Career changer: {field_specific_years:.1f} years in {profile['career_field']}, "
                    f"{profile['total_years_experience']:.1f} years total"
                )

                # Recalculate experience level based on field-specific years
                if profile["years_experience"] >= 16:
                    profile["experience_level"] = "executive"
                elif profile["years_experience"] >= 8:
                    profile["experience_level"] = "senior"
                elif profile["years_experience"] >= 3:
                    profile["experience_level"] = "mid"
                elif profile["years_experience"] >= 1:
                    profile["experience_level"] = "junior"
                else:
                    profile["experience_level"] = "entry_level"
            else:
                profile["is_career_changer"] = False

        # Detect career change intent (look for 'career change' or 'transition to X' in summary)
        if self.cv:
            # Get professional summary from the CV's related professional_summary
            try:
                professional_summary = self.cv.professional_summary.first()
                if professional_summary and professional_summary.summary:
                    summary = professional_summary.summary.lower()
                    for field, keywords in self.CAREER_FIELDS.items():
                        for keyword in keywords:
                            if (
                                f"transition to {keyword}" in summary
                                or f"career change to {keyword}" in summary
                                or f"moving to {keyword}" in summary
                                or f"switching to {keyword}" in summary
                            ):
                                profile["career_change_field"] = field
                                break
            except Exception:
                pass  # If no professional summary, continue without career change detection

        # Optionally, look for a 'target_field' attribute on the CV
        if hasattr(self.cv, "target_field") and self.cv.target_field:
            profile["career_change_field"] = self.cv.target_field.lower()

        return profile

    def _detect_career_field(self, profile):
        """Detect user's primary career field from titles and skills"""
        field_scores = {field: 0 for field in self.CAREER_FIELDS}

        # Analyze job titles (HEAVILY WEIGHTED - most important indicator)
        for title in profile["job_titles"]:
            title_lower = title.lower()
            for field, keywords in self.CAREER_FIELDS.items():
                for keyword in keywords:
                    if keyword in title_lower:
                        # Job titles get MUCH higher weight (10 points)
                        # This ensures job title is primary indicator
                        field_scores[field] += 10

        # Analyze skills (lower weight to avoid false positives)
        for skill in profile["skills"]:
            skill_lower = skill.lower()
            for field, keywords in self.CAREER_FIELDS.items():
                for keyword in keywords:
                    if keyword in skill_lower:
                        # Skills only add 1 point (10x less than job title)
                        field_scores[field] += 1

        # Return field with highest score (or None if no clear match)
        if max(field_scores.values()) > 0:
            detected_field = max(field_scores, key=field_scores.get)

            # Debug logging
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"🎯 Career field detection scores: {dict(sorted(field_scores.items(), key=lambda x: x[1], reverse=True)[:5])}"
            )
            logger.info(
                f"✅ Detected career field: {detected_field} (score: {field_scores[detected_field]})"
            )

            return detected_field
        return None

    def calculate_skills_score(self, job):
        """Calculate skills match score (0-100)"""
        if not self.user_profile["skills"]:
            return 0

        # Extract skills from job
        job_skills = set()
        if job.skills_required:
            # Split by common delimiters
            skills_text = job.skills_required.lower()
            job_skills = set(re.split(r"[,;|\n•]", skills_text))
            job_skills = {skill.strip() for skill in job_skills if skill.strip()}

        if not job_skills:
            return 50  # Neutral score if no skills specified

        # Calculate match
        matched_skills = self.user_profile["skills"].intersection(job_skills)
        match_percentage = len(matched_skills) / len(job_skills) * 100

        return min(match_percentage, 100)

    def calculate_title_similarity(self, job):
        """Calculate job title similarity score (0-100)"""
        if not self.user_profile["job_titles"]:
            return 50  # Neutral score if no experience

        job_title = job.title.lower()

        # Calculate similarity with each of user's past titles
        max_similarity = 0
        for user_title in self.user_profile["job_titles"]:
            similarity = SequenceMatcher(None, job_title, user_title).ratio()
            max_similarity = max(max_similarity, similarity)

        # Check for keyword matches
        job_keywords = set(re.findall(r"\b\w+\b", job_title))
        user_keywords = set()
        for title in self.user_profile["job_titles"]:
            user_keywords.update(re.findall(r"\b\w+\b", title))

        keyword_match = len(job_keywords.intersection(user_keywords)) / max(
            len(job_keywords), 1
        )

        # Combine similarity and keyword match
        final_score = (max_similarity * 0.6 + keyword_match * 0.4) * 100

        return min(final_score, 100)

    def calculate_experience_score(self, job):
        """Calculate experience level match score (0-100)"""
        user_level = self.user_profile["experience_level"]
        job_level = job.experience_level

        # Experience level hierarchy
        level_hierarchy = {
            "no_experience": 0,
            "entry_level": 1,
            "junior": 2,
            "mid": 3,
            "mid_level": 3,
            "senior": 4,
            "lead": 5,
            "manager": 6,
            "director": 7,
            "executive": 8,
        }

        user_rank = level_hierarchy.get(user_level, 3)
        job_rank = level_hierarchy.get(job_level, 3)

        # Perfect match = 100
        # 1 level difference = 80
        # 2 levels difference = 60
        # 3+ levels difference = 40
        difference = abs(user_rank - job_rank)

        if difference == 0:
            return 100
        elif difference == 1:
            return 80
        elif difference == 2:
            return 60
        else:
            return 40

    def calculate_location_score(self, job):
        """Calculate location match score (0-100)"""
        if not self.user_profile["location"]:
            return 50  # Neutral if no location preference

        job_location = job.location.lower() if job.location else ""
        user_location = self.user_profile["location"]

        # Exact match
        if user_location in job_location or job_location in user_location:
            return 100

        # Remote jobs always score high
        if job.mode == "remote":
            return 90

        # Hybrid jobs score medium
        if job.mode == "hybrid":
            return 70

        # Different location but on-site
        return 30

    def calculate_recency_score(self, job):
        """Calculate recency score - newer jobs score higher (0-100)"""
        from django.utils import timezone

        now = timezone.now().date()
        job_date = job.date_posted

        days_old = (now - job_date).days

        # Jobs posted within:
        # 0-7 days = 100
        # 8-14 days = 90
        # 15-30 days = 80
        # 31-60 days = 70
        # 61-90 days = 60
        # 90+ days = 50

        if days_old <= 7:
            return 100
        elif days_old <= 14:
            return 90
        elif days_old <= 30:
            return 80
        elif days_old <= 60:
            return 70
        elif days_old <= 90:
            return 60
        else:
            return 50

    def calculate_overall_score(self, job):
        """Calculate weighted overall match score (0-100)"""
        scores = {
            "skills": self.calculate_skills_score(job),
            "title": self.calculate_title_similarity(job),
            "experience": self.calculate_experience_score(job),
            "location": self.calculate_location_score(job),
            "recency": self.calculate_recency_score(job),
        }

        # Calculate weighted average
        overall_score = sum(scores[factor] * self.WEIGHTS[factor] for factor in scores)

        # Apply career field penalty for mismatched industries
        if self.user_profile["career_field"]:
            job_field = self._detect_job_career_field(job)

            if job_field and job_field != self.user_profile["career_field"]:
                # Heavy penalty (40%) for completely different career fields
                # E.g., showing developer jobs to accountants
                overall_score *= 0.60

                # If cross-industry match is still above threshold, it means
                # there are genuinely transferable skills

        return round(overall_score, 1), scores

    def _detect_job_career_field(self, job):
        """Detect job's career field from title and description"""
        field_scores = {field: 0 for field in self.CAREER_FIELDS}

        job_text = f"{job.title} {job.description or ''}".lower()

        for field, keywords in self.CAREER_FIELDS.items():
            for keyword in keywords:
                if keyword in job_text:
                    field_scores[field] += 1

        # Return field with highest score (or None if no clear match)
        if max(field_scores.values()) > 0:
            return max(field_scores, key=field_scores.get)
        return None

    def get_recommendations(self, limit=20):
        """Get recommended jobs with scores, filtered by career field (with career change support)"""
        from jobstract.models import Opportunity

        # Get all active jobs
        jobs = (
            Opportunity.objects.filter(opportunity_type="job")
            .select_related("employer")
            .order_by("-date_posted")
        )

        user_field = self.user_profile.get("career_field")
        change_field = self.user_profile.get("career_change_field")
        allowed_fields = set()
        if user_field:
            allowed_fields.add(user_field)
            # Add related fields for better matching
            if user_field == "retail":
                allowed_fields.add(
                    "business"
                )  # Retail managers often manage business operations
        if change_field:
            allowed_fields.add(change_field)

        def job_field(job):
            # Detect job field from title (simple keyword match)
            title = (job.title or "").lower()
            for field, keywords in self.CAREER_FIELDS.items():
                for keyword in keywords:
                    if keyword in title:
                        return field
            return None

        # Filter jobs by field if known
        filtered_jobs = []
        for job in jobs:
            field = job_field(job)

            # If user has a field, filter by it
            if allowed_fields:
                # For unknown field jobs, calculate score first and allow if high match
                if field is None:
                    overall_score, component_scores = self.calculate_overall_score(job)
                    # Allow unknown field jobs only if they score very well (60%+)
                    if overall_score >= 60:
                        filtered_jobs.append(
                            {
                                "job": job,
                                "score": overall_score,
                                "component_scores": component_scores,
                            }
                        )
                    continue  # Skip other unknown field jobs

                # Skip jobs from completely different fields
                if field not in allowed_fields:
                    continue

            # Calculate score for allowed jobs
            overall_score, component_scores = self.calculate_overall_score(job)
            if overall_score >= self.MIN_SCORE_THRESHOLD:
                filtered_jobs.append(
                    {
                        "job": job,
                        "score": overall_score,
                        "component_scores": component_scores,
                    }
                )

        # Sort by score (highest first)
        filtered_jobs.sort(key=lambda x: x["score"], reverse=True)
        return filtered_jobs[:limit]

    def explain_recommendation(self, job, score, component_scores):
        """Generate human-readable explanation for why job was recommended"""
        explanations = []

        # Skills match
        if component_scores["skills"] >= 70:
            explanations.append(
                f"Strong skills match ({component_scores['skills']:.0f}%)"
            )
        elif component_scores["skills"] >= 50:
            explanations.append(
                f"Good skills match ({component_scores['skills']:.0f}%)"
            )

        # Title similarity
        if component_scores["title"] >= 70:
            explanations.append("Similar to your past roles")
        elif component_scores["title"] >= 50:
            explanations.append("Related to your experience")

        # Experience level
        if component_scores["experience"] == 100:
            explanations.append("Perfect experience level match")
        elif component_scores["experience"] >= 80:
            explanations.append("Good experience level fit")

        # Location
        if component_scores["location"] >= 90:
            explanations.append("Matches your location preference")
        elif job.mode == "remote":
            explanations.append("Remote work available")

        # Recency
        if component_scores["recency"] >= 90:
            explanations.append("Recently posted")

        return (
            " • ".join(explanations)
            if explanations
            else "Recommended based on your profile"
        )
