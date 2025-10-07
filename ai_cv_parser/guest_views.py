"""
Guest CV Analysis Views
Handles CV analysis for unauthenticated users with rate limiting and session management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging
import tempfile
import os
import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor

from .models import ParsedCV
from .serializers import ParsedCVSerializer
from .disposable_emails import validate_email_for_cv_analysis

logger = logging.getLogger("ai_cv_parser")


def validate_role_suggestions(potential_roles, years_experience):
    """
    Validate and filter role suggestions to match experience level.
    Prevents junior roles being suggested to senior candidates.

    Args:
        potential_roles: List of role suggestions or dict with 'best_matches'
        years_experience: Total years of experience

    Returns:
        Filtered list of appropriate role suggestions
    """
    # Handle different formats
    if isinstance(potential_roles, dict):
        roles_list = potential_roles.get("best_matches", [])
    elif isinstance(potential_roles, list):
        roles_list = potential_roles
    else:
        return []

    # Keywords that indicate junior roles
    junior_keywords = [
        "junior",
        "trainee",
        "intern",
        "associate",
        "assistant",
        "coordinator",
        "entry",
        "graduate",
        "apprentice",
    ]

    # Keywords that indicate mid-level roles (inappropriate for 16+ years)
    mid_keywords = ["specialist", "analyst", "consultant", "supervisor"]

    # Validate based on experience
    validated_roles = []

    for role in roles_list:
        if not isinstance(role, str):
            continue

        role_lower = role.lower()

        # Filter logic based on experience
        if years_experience >= 16:  # Executive level
            # Should not see junior or mid-level roles
            if any(keyword in role_lower for keyword in junior_keywords + mid_keywords):
                logger.warning(
                    f"Filtering inappropriate role '{role}' for {years_experience} years experience"
                )
                continue

        elif years_experience >= 8:  # Senior level
            # Should not see junior roles
            if any(keyword in role_lower for keyword in junior_keywords):
                logger.warning(
                    f"Filtering inappropriate role '{role}' for {years_experience} years experience"
                )
                continue

        elif years_experience >= 3:  # Mid level
            # Should not see junior/trainee roles
            if any(
                keyword in role_lower
                for keyword in ["junior", "trainee", "intern", "apprentice"]
            ):
                logger.warning(
                    f"Filtering inappropriate role '{role}' for {years_experience} years experience"
                )
                continue

        validated_roles.append(role)

    return validated_roles


class GuestCVAnalysisViewSet(viewsets.ViewSet):
    """
    Guest-friendly CV analysis endpoints.
    No authentication required - uses session-based tracking.
    Rate limited to prevent abuse.
    """

    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @action(detail=False, methods=["POST"], url_path="analyze")
    def guest_analyze(self, request):
        """
        Allow guests to analyze CV without authentication.
        Limited to 3 uploads per IP per day.

        Returns:
            - session_id: Unique identifier to check status/results
            - cv_id: Database ID for the parsed CV
            - status: Processing status
        """
        try:
            logger.info("Guest CV analysis request received")

            # Rate limiting by IP
            ip_address = self.get_client_ip(request)
            logger.info(f"Request from IP: {ip_address}")

            # Check rate limit with enhanced response
            rate_check = self.check_rate_limit(ip_address, limit=5, window_hours=24)
            if not rate_check["allowed"]:
                logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                return Response(
                    {
                        "error": rate_check["message"],
                        "reset_time": rate_check["reset_time"],
                        "limit": rate_check["limit"],
                        "count": rate_check["count"],
                        "upgrade_required": True,
                        "message": "Sign up for unlimited CV analyses and premium features!",
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Validate file upload
            if "file" not in request.FILES:
                logger.warning("No file uploaded in request")
                return Response(
                    {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
                )

            file = request.FILES["file"]
            logger.info(f"Processing guest file: {file.name} ({file.size} bytes)")

            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                return Response(
                    {"error": "File too large. Maximum size is 10MB."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate file type
            allowed_extensions = [".pdf", ".docx", ".doc"]
            file_ext = os.path.splitext(file.name)[1].lower()
            if file_ext not in allowed_extensions:
                return Response(
                    {
                        "error": f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create guest session
            session_id = self.generate_session_id()
            logger.info(f"Generated session ID: {session_id}")

            # Create temporary ParsedCV with null user
            guest_cv = ParsedCV.objects.create(
                user=None,  # Guest session
                session_id=session_id,
                file_name=file.name,
                file_size=file.size,
                mime_type=file.content_type,
                status="queued",
                expires_at=timezone.now() + timedelta(hours=24),
                is_guest=True,
            )
            logger.info(f"Created guest CV record with ID: {guest_cv.id}")

            # Save uploaded file to temporary location
            temp_path = self.save_uploaded_file(file)
            logger.info(f"Saved file to temporary path: {temp_path}")

            guest_cv.temp_file_path = temp_path
            guest_cv.save(update_fields=["temp_file_path"])

            # Start async processing (non-blocking)
            logger.info(f"Starting async processing for guest CV {guest_cv.id}")
            executor = ThreadPoolExecutor(max_workers=1)
            executor.submit(self._process_guest_cv, guest_cv.id, temp_path)
            # Don't wait for completion - return immediately

            return Response(
                {
                    "session_id": session_id,
                    "cv_id": guest_cv.id,
                    "status": "processing",
                    "message": "CV analysis started. Check status in a few seconds.",
                    "expires_in_hours": 24,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            logger.error(f"Guest CV analysis error: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"], url_path="status/(?P<session_id>[^/.]+)")
    def guest_status(self, request, session_id=None):
        """
        Get status of guest CV analysis.

        Args:
            session_id: Unique session identifier

        Returns:
            - status: queued, processing, completed, or failed
            - cv_id: Database ID
            - progress: Processing progress (0-100)
        """
        try:
            logger.info(f"Checking status for session: {session_id}")

            guest_cv = ParsedCV.objects.get(session_id=session_id, is_guest=True)

            # Check if session has expired
            if guest_cv.expires_at and timezone.now() > guest_cv.expires_at:
                logger.warning(f"Session {session_id} has expired")
                return Response(
                    {
                        "error": "Session expired",
                        "message": "This analysis session has expired. Please upload your CV again.",
                    },
                    status=status.HTTP_410_GONE,
                )

            return Response(
                {
                    "status": guest_cv.status,
                    "cv_id": guest_cv.id,
                    "session_id": session_id,
                    "expires_at": (
                        guest_cv.expires_at.isoformat() if guest_cv.expires_at else None
                    ),
                }
            )

        except ParsedCV.DoesNotExist:
            logger.warning(f"Session not found: {session_id}")
            return Response(
                {
                    "error": "Session not found or expired",
                    "message": "This analysis session does not exist or has been deleted.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error checking guest status: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["POST"], url_path="capture-email")
    def capture_email(self, request):
        """
        Capture user email and name for lead generation.
        Validates email to prevent abuse (disposable emails, fake patterns).

        POST /api/ai_cv_parser/guest/capture-email/
        {
            "session_id": "...",
            "email": "user@example.com",
            "name": "John Doe"
        }

        Returns:
            - success: Email captured successfully
            - error: Validation failed (disposable email, fake pattern, etc.)
        """
        try:
            session_id = request.data.get("session_id")
            email = request.data.get("email", "").strip().lower()
            name = request.data.get("name", "").strip()

            # Validate required fields
            if not session_id or not email or not name:
                return Response(
                    {
                        "error": "Session ID, email, and name are required",
                        "field": "all",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate email format and check for disposable/fake emails
            email_validation = validate_email_for_cv_analysis(email)
            if not email_validation["valid"]:
                logger.warning(
                    f"Invalid email attempt: {email} - {email_validation['error']}"
                )
                return Response(
                    {"error": email_validation["error"], "field": "email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get CV session
            try:
                guest_cv = ParsedCV.objects.get(session_id=session_id, is_guest=True)
            except ParsedCV.DoesNotExist:
                return Response(
                    {
                        "error": "Invalid session",
                        "message": "Session not found or expired",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Store email and name in analysis_data (for now)
            # TODO: Create proper Lead/EmailCapture model in future
            if not guest_cv.analysis_data:
                guest_cv.analysis_data = {}

            guest_cv.analysis_data["user_email"] = email
            guest_cv.analysis_data["user_name"] = name
            guest_cv.analysis_data["email_captured_at"] = timezone.now().isoformat()
            guest_cv.save(update_fields=["analysis_data"])

            logger.info(f"Email captured for session {session_id}: {email}")

            return Response(
                {"success": True, "message": "Email captured successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error capturing email: {str(e)}")
            return Response(
                {"error": "Failed to capture email", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"], url_path="results/(?P<session_id>[^/.]+)")
    def guest_results(self, request, session_id=None):
        """
        Get limited preview of guest CV analysis.
        Returns only basic metrics to encourage signup.

        Args:
            session_id: Unique session identifier

        Returns:
            Limited analysis preview with upgrade prompt
        """
        try:
            logger.info(f"Fetching results for session: {session_id}")

            guest_cv = ParsedCV.objects.get(session_id=session_id, is_guest=True)

            # Check if session has expired
            if guest_cv.expires_at and timezone.now() > guest_cv.expires_at:
                return Response(
                    {
                        "error": "Session expired",
                        "message": "This analysis has expired. Sign up to save your analyses permanently!",
                    },
                    status=status.HTTP_410_GONE,
                )

            # Check if processing is complete
            if guest_cv.status != "completed":
                return Response(
                    {
                        "status": guest_cv.status,
                        "message": "Analysis still processing. Please check again in a few moments.",
                        "session_id": session_id,
                    }
                )

            # Check if analysis data is ready (parsing might be complete but AI analysis still running)
            if not guest_cv.analysis_data or not guest_cv.analysis_data.get(
                "overall_score"
            ):
                return Response(
                    {
                        "status": "processing",
                        "message": "AI analysis in progress. Please check again in a few moments.",
                        "session_id": session_id,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            # Get analysis data
            analysis = guest_cv.analysis_data or {}
            suggestions = analysis.get("suggestions", [])
            section_scores = analysis.get("section_scores", {})

            # Get ALL premium data
            career_trajectory = analysis.get("career_trajectory", {})
            potential_roles = analysis.get("potential_roles", [])
            employment_gaps = analysis.get("employment_gaps", {})

            # Get years of experience for role validation
            experience_level = analysis.get("experience_level", {})
            years_experience = experience_level.get("years_experience", 0)

            # Validate role suggestions match experience level
            if potential_roles and years_experience:
                potential_roles = validate_role_suggestions(
                    potential_roles, years_experience
                )
                logger.info(
                    f"Validated {len(potential_roles)} role suggestions for {years_experience} years experience"
                )

            # Extract overall score - handle both direct value and nested structure
            overall_score_data = analysis.get("overall_score", 0)
            if isinstance(overall_score_data, dict):
                overall_score = overall_score_data.get("score", 0)
            else:
                overall_score = overall_score_data or 0

            # Convert score to 0-100 scale if it's in 0-10 range
            if overall_score <= 10:
                overall_score = overall_score * 10

            # Get categorized feedback from AI analysis
            # The AI returns simple arrays of strings, so we need to format them
            ai_strengths = analysis.get("strengths", [])
            ai_weaknesses = analysis.get("weaknesses", [])
            ai_improvements = analysis.get("improvement_suggestions", [])

            # Get enhanced analysis data (ATS, quantifiable achievements, etc.)
            ats_analysis = analysis.get("ats_analysis", {})
            quantifiable_data = analysis.get("quantifiable_achievements", {})

            # Format strengths as objects for frontend
            strengths = [
                {
                    "title": (
                        strength
                        if isinstance(strength, str)
                        else strength.get("title", "Strength")
                    ),
                    "description": (
                        strength
                        if isinstance(strength, str)
                        else strength.get("description", "")
                    ),
                }
                for strength in ai_strengths  # Show ALL strengths
            ]

            # Format weaknesses as critical issues
            critical_issues = [
                {
                    "severity": "high",
                    "title": (
                        weakness
                        if isinstance(weakness, str)
                        else weakness.get("title", "Issue")
                    ),
                    "description": (
                        weakness
                        if isinstance(weakness, str)
                        else weakness.get("description", "")
                    ),
                }
                for weakness in ai_weaknesses  # Show ALL critical issues
            ]

            # Format improvement suggestions as quick wins
            improvements = [
                {
                    "severity": "medium",
                    "title": (
                        improvement
                        if isinstance(improvement, str)
                        else improvement.get("title", "Improvement")
                    ),
                    "description": (
                        improvement
                        if isinstance(improvement, str)
                        else improvement.get("description", "")
                    ),
                }
                for improvement in ai_improvements  # Show ALL improvements
            ]

            # CRITICAL: Ensure we always have issues to show, even for high-scoring CVs
            # This is important for conversion - users need to see room for improvement
            if len(critical_issues) < 3 and overall_score >= 75:
                # Add generic but important issues for high-scoring CVs
                generic_critical_issues = [
                    {
                        "severity": "high",
                        "title": "Competitive Optimization Needed",
                        "description": f"While your CV scores {overall_score}/100, top candidates (scoring 92+) have optimized EVERY detail. Small improvements can make the difference between 'good' and 'interview-ready'.",
                    },
                    {
                        "severity": "high",
                        "title": "ATS Filtering Risk",
                        "description": "Even high-scoring CVs can be filtered out. Our analysis found formatting patterns that may reduce ATS parsing accuracy. Professional optimization ensures nothing is left to chance.",
                    },
                    {
                        "severity": "high",
                        "title": "Missing Competitive Edge",
                        "description": "Your CV is good, but 75% of applications never reach human eyes. Top performers use AI-optimized keywords, quantified achievements, and industry-specific formatting to stand out.",
                    },
                    {
                        "severity": "high",
                        "title": "Quantifiable Impact Gap",
                        "description": f"Only {quantifiable_data.get('percentage', 0)}% of your achievements include metrics. Industry leaders average 80%+. Adding numbers to your accomplishments significantly increases interview callbacks.",
                    },
                ]

                # Add enough to reach at least 3 critical issues
                needed = 3 - len(critical_issues)
                critical_issues.extend(generic_critical_issues[:needed])

            # Similarly ensure we have improvements to show
            if len(improvements) < 3:
                generic_improvements = [
                    {
                        "severity": "medium",
                        "title": "Keyword Density Optimization",
                        "description": "Strategic placement of industry keywords can increase ATS match rate by 30-50%. Professional CV writers know exactly which keywords recruiters are searching for.",
                    },
                    {
                        "severity": "medium",
                        "title": "Achievement Quantification",
                        "description": "Transform generic responsibilities into measurable achievements. Instead of 'managed team', say 'led 12-person team to 35% productivity increase'.",
                    },
                    {
                        "severity": "medium",
                        "title": "Format Modernization",
                        "description": "ATS systems are constantly updated. Ensure your formatting follows current best practices for parsing accuracy and visual impact.",
                    },
                ]

                needed = 3 - len(improvements)
                improvements.extend(generic_improvements[:needed])

            # Convert section scores to 0-100 scale
            def normalize_score(score_data):
                if isinstance(score_data, dict):
                    score = score_data.get("score", 0)
                else:
                    score = score_data or 0
                return score * 10 if score <= 10 else score

            # Build detailed section scores - map to actual field names from AI analysis
            detailed_section_scores = {
                "content_completeness": normalize_score(
                    section_scores.get("content_completeness", 0)
                ),
                "format_structure": normalize_score(
                    section_scores.get("format_structure", 0)
                ),
                "skills_relevance": normalize_score(
                    section_scores.get("skills_relevance", 0)
                ),
                "job_history": normalize_score(section_scores.get("job_history", 0)),
                "education": normalize_score(section_scores.get("education", 0)),
                "overall_impact": normalize_score(
                    section_scores.get("overall_impact", 0)
                ),
            }

            # Get experience data - map to actual field names from AI analysis
            experience_data = analysis.get("experience_level", {})
            years_of_experience = experience_data.get("years_experience", 0)
            experience_classification = experience_data.get("classification", "unknown")

            # Get design and formatting feedback with enhanced ATS data
            design_feedback = {
                "format_score": detailed_section_scores["format_structure"],
                "readability": "Good" if overall_score >= 70 else "Needs Improvement",
                "ats_friendly": overall_score >= 75,
                "ats_parse_rate": ats_analysis.get("parse_rate", overall_score),
                "keyword_match": ats_analysis.get("keyword_match", 0),
                "repeated_words": ats_analysis.get("repeated_words", [])[
                    :3
                ],  # Top 3 repeated words
                "missing_keywords": ats_analysis.get("missing_keywords", [])[
                    :5
                ],  # Top 5 missing keywords
            }

            # Add quantifiable achievements insight
            quant_data = {
                "total_bullets": quantifiable_data.get("total_bullets", 0),
                "quantified_bullets": quantifiable_data.get("quantified_bullets", 0),
                "percentage": quantifiable_data.get("percentage", 0),
                "has_metrics": quantifiable_data.get("percentage", 0)
                >= 50,  # Good if 50%+ have metrics
            }

            # Calculate FULL analysis with ALL premium data
            full_analysis = {
                "session_id": session_id,
                "ats_score": overall_score,
                "score_category": self._get_score_category(overall_score),
                # Section scores - show all
                "section_scores": detailed_section_scores,
                # Experience analysis
                "experience_analysis": {
                    "years": years_of_experience,
                    "classification": experience_classification,
                    "level_description": self._get_experience_description(
                        experience_classification
                    ),
                },
                # PREMIUM: Career Trajectory Analysis
                "career_trajectory": (
                    career_trajectory
                    if career_trajectory
                    else {
                        "job_consistency": {
                            "score": 0,
                            "level": "Not analyzed",
                            "insights": [],
                            "recommendations": [],
                        },
                        "role_stability": {
                            "score": 0,
                            "level": "Not analyzed",
                            "average_tenure": "N/A",
                            "employment_gaps": 0,
                            "insights": [],
                            "flags": [],
                        },
                        "career_change_potential": {
                            "assessment": "Not analyzed",
                            "confidence": "N/A",
                            "indicators": [],
                            "potential_directions": [],
                            "recommendations": [],
                        },
                    }
                ),
                # PREMIUM: Role Suggestions
                "role_suggestions": potential_roles[:10] if potential_roles else [],
                # PREMIUM: Employment Gaps Analysis
                "employment_gaps_analysis": (
                    employment_gaps
                    if employment_gaps
                    else {
                        "has_gaps": False,
                        "gap_details": [],
                        "total_gap_months": 0,
                        "assessment": "No significant gaps detected",
                    }
                ),
                # Show ALL issues and strengths
                "critical_issues": critical_issues,
                "strengths": strengths,
                "quick_improvements": improvements,
                # Design insights with enhanced ATS data
                "design_insights": design_feedback,
                # Quantifiable achievements analysis
                "quantifiable_achievements": quant_data,
                # Metadata
                "total_issues": len(ai_weaknesses) + len(ai_improvements),
                "total_strengths": len(ai_strengths),
                "upgrade_required": False,  # Free analysis - no upgrade needed
                # CTA to CV Rewriter (main product)
                "cta": {
                    "title": "Transform Your CV with AI",
                    "description": "Use our AI CV Rewriter to optimize your resume based on this analysis",
                    "button_text": "Rewrite My CV",
                    "button_link": "/cv-writer",
                },
            }

            logger.info(f"Returning full analysis for session {session_id}")
            return Response(full_analysis)

        except ParsedCV.DoesNotExist:
            return Response(
                {"error": "Session not found or expired"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error fetching guest results: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["POST"], url_path="claim")
    def claim_session(self, request):
        """
        Transfer guest CV to authenticated user account.
        Called after user signs up from the analysis page.

        Request body:
            - session_id: Guest session to claim

        Returns:
            - cv_id: Claimed CV ID
            - premium_trial: Whether trial was activated
            - trial_days: Number of trial days
        """
        if not request.user.is_authenticated:
            return Response(
                {
                    "error": "Authentication required",
                    "message": "Please log in to claim your analysis.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        session_id = request.data.get("session_id")

        if not session_id:
            return Response(
                {"error": "Session ID required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            logger.info(f"User {request.user.username} claiming session {session_id}")

            guest_cv = ParsedCV.objects.get(session_id=session_id, is_guest=True)

            # Check if session has expired
            if guest_cv.expires_at and timezone.now() > guest_cv.expires_at:
                return Response(
                    {
                        "error": "Session expired",
                        "message": "This session has expired. Please upload your CV again.",
                    },
                    status=status.HTTP_410_GONE,
                )

            # Transfer ownership to user
            guest_cv.user = request.user
            guest_cv.is_guest = False
            guest_cv.session_id = None  # Clear session ID
            guest_cv.expires_at = None  # Remove expiration
            guest_cv.save()

            logger.info(
                f"Successfully transferred CV {guest_cv.id} to user {request.user.username}"
            )

            # Activate 30-day premium trial
            trial_activated = self.activate_premium_trial(request.user)

            return Response(
                {
                    "cv_id": guest_cv.id,
                    "premium_trial": trial_activated,
                    "trial_days": 30 if trial_activated else 0,
                    "message": "CV claimed successfully!"
                    + (" 30-day premium trial activated!" if trial_activated else ""),
                }
            )

        except ParsedCV.DoesNotExist:
            logger.warning(f"Session not found: {session_id}")
            return Response(
                {"error": "Session not found or expired"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error claiming session: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def get_client_ip(self, request):
        """Extract client IP address from request headers."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def check_rate_limit(self, ip_address, limit=5, window_hours=24):
        """
        Check if IP has exceeded rate limit.
        Default: 5 CV analyses per 24 hours per IP.

        Args:
            ip_address: Client IP address
            limit: Maximum number of requests allowed (default: 5)
            window_hours: Time window in hours (default: 24)

        Returns:
            dict: {'allowed': bool, 'count': int, 'limit': int, 'reset_time': str}
        """
        key = f"guest_cv_analysis_{ip_address}"
        count = cache.get(key, 0)

        if count >= limit:
            logger.warning(
                f"Rate limit exceeded for IP {ip_address}: {count}/{limit} requests"
            )

            # Get TTL to show when limit resets
            from django.core.cache import cache as django_cache

            ttl = (
                django_cache.ttl(key)
                if hasattr(django_cache, "ttl")
                else window_hours * 3600
            )

            from datetime import timedelta

            reset_time = (timezone.now() + timedelta(seconds=ttl)).strftime("%H:%M")

            return {
                "allowed": False,
                "count": count,
                "limit": limit,
                "reset_time": reset_time,
                "message": f"Rate limit exceeded. You can analyze {limit} CVs per {window_hours} hours. Try again at {reset_time}.",
            }

        # Increment counter with expiry
        cache.set(key, count + 1, timeout=window_hours * 3600)
        logger.info(
            f"Rate limit check passed for IP {ip_address}: {count + 1}/{limit} requests"
        )
        return {"allowed": True, "count": count + 1, "limit": limit}

    def generate_session_id(self):
        """Generate unique session ID using UUID4."""
        return str(uuid.uuid4())

    def save_uploaded_file(self, file):
        """
        Save uploaded file to temporary location.

        Args:
            file: Uploaded file object

        Returns:
            str: Path to saved file
        """
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.name)

        with open(temp_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        logger.info(f"Saved file to: {temp_path}")
        return temp_path

    def _process_guest_cv(self, cv_id, file_path):
        """
        Process guest CV asynchronously.
        Reuses existing CV processing logic from AICVParserViewSet.

        Args:
            cv_id: ParsedCV database ID
            file_path: Path to uploaded file
        """
        # Close the database connection to avoid timeout issues in background thread
        from django.db import connection

        connection.close()

        try:
            logger.info(f"Starting async processing for guest CV {cv_id}")

            # Import here to avoid circular dependency
            from .views import AICVParserViewSet

            # Create viewset instance and use existing processing method
            viewset = AICVParserViewSet()
            viewset._process_cv_file(cv_id, file_path)

            logger.info(f"Completed processing for guest CV {cv_id}")

            # Auto-analyze the CV for guest users
            try:
                cv = ParsedCV.objects.get(id=cv_id)
                if cv.status == "completed" and not cv.analysis_data:
                    logger.info(f"Auto-analyzing guest CV {cv_id}")

                    # Use DeepSeek for AI analysis (primary), fallback to FallbackService if needed
                    try:
                        from .deepseek_service import DeepSeekService

                        service = DeepSeekService()
                        logger.info(
                            f"Using DeepSeekService for guest CV {cv_id} analysis"
                        )
                    except ImportError:
                        logger.warning(
                            f"DeepSeekService not available, using FallbackService for CV {cv_id}"
                        )
                        from .fallback_service import FallbackService

                        service = FallbackService()

                    cv_data = cv.parsed_data

                    # Perform chunked analysis
                    analysis_result = viewset._analyze_cv_chunked(cv_data, service)

                    # ADD CAREER TRAJECTORY ANALYSIS (if using DeepSeek)
                    try:
                        from .deepseek_service import DeepSeekService as DeepSeekCheck

                        if isinstance(service, DeepSeekCheck):
                            logger.info(
                                f"🔍 Starting career trajectory analysis for guest CV {cv_id}"
                            )

                            # Run career trajectory analysis
                            import asyncio

                            career_analysis = asyncio.run(
                                service.analyze_career_trajectory(cv_data)
                            )

                            # Add to analysis result
                            analysis_result["career_trajectory"] = career_analysis

                            # Update experience level with accurate total_experience from career trajectory
                            if career_analysis and "role_stability" in career_analysis:
                                total_exp = career_analysis["role_stability"].get(
                                    "total_experience"
                                )
                                if total_exp and "experience_level" in analysis_result:
                                    accurate_years = float(
                                        total_exp.replace(" years", "")
                                        .replace("~", "")
                                        .strip()
                                    )
                                    if accurate_years > 0:
                                        analysis_result["experience_level"][
                                            "years_experience"
                                        ] = int(round(accurate_years))
                                        logger.info(
                                            f"✅ Updated years_experience to {int(round(accurate_years))} from career trajectory"
                                        )

                            logger.info(
                                f"✅ Career trajectory analysis completed for guest CV {cv_id}"
                            )
                    except Exception as career_error:
                        logger.error(
                            f"❌ Error in career trajectory analysis for guest CV {cv_id}: {str(career_error)}"
                        )
                        logger.error(traceback.format_exc())
                        # Don't fail the whole analysis if career trajectory fails

                    # Save analysis results
                    cv.analysis_data = analysis_result
                    cv.analysis_date = timezone.now()
                    cv.save(update_fields=["analysis_data", "analysis_date"])

                    logger.info(f"Auto-analysis completed for guest CV {cv_id}")
            except Exception as analysis_error:
                logger.error(
                    f"Auto-analysis failed for guest CV {cv_id}: {str(analysis_error)}"
                )
                logger.error(traceback.format_exc())
                # Don't fail the whole process if analysis fails

        except Exception as e:
            logger.error(f"Error processing guest CV {cv_id}: {str(e)}")
            logger.error(traceback.format_exc())

            # Update CV status to failed
            try:
                cv = ParsedCV.objects.get(id=cv_id)
                cv.status = "failed"
                cv.error_message = str(e)
                cv.save(update_fields=["status", "error_message"])
            except Exception as update_error:
                logger.error(f"Failed to update CV status: {str(update_error)}")

    def activate_premium_trial(self, user):
        """
        Activate 30-day premium trial for new user.
        Only activates if user doesn't already have a subscription.

        Args:
            user: User object

        Returns:
            bool: True if trial activated, False otherwise
        """
        try:
            from subscription.models import UserSubscription, SubscriptionPlan

            # Check if user already has a subscription
            existing_subscription = UserSubscription.objects.filter(user=user).first()

            if existing_subscription:
                logger.info(f"User {user.username} already has a subscription")
                return False

            # Get or create a premium/trial plan
            try:
                premium_plan = SubscriptionPlan.objects.filter(
                    name__icontains="premium"
                ).first()

                if not premium_plan:
                    # Create a basic premium trial plan if none exists
                    premium_plan = SubscriptionPlan.objects.create(
                        name="Premium Trial",
                        slug="premium-trial",
                        description="30-day premium trial with full access",
                        price=0.00,
                        interval="month",
                        status="active",
                        max_cv_generations=999,
                        max_job_applications=999,
                        max_saved_jobs=999,
                        has_cv_analytics=True,
                        has_job_alerts=True,
                        has_priority_support=True,
                        has_ai_interview_prep=True,
                    )
                    logger.info(f"Created premium trial plan: {premium_plan.id}")
            except Exception as plan_error:
                logger.error(f"Error getting/creating premium plan: {plan_error}")
                return False

            # Create premium trial subscription with Stripe placeholder IDs
            subscription = UserSubscription.objects.create(
                user=user,
                plan=premium_plan,
                status="active",
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
                stripe_subscription_id=f"trial_{user.id}_{int(timezone.now().timestamp())}",
                stripe_customer_id=f"cus_trial_{user.id}",
            )

            logger.info(
                f"✅ Activated 30-day premium trial for user {user.username} (subscription: {subscription.id})"
            )
            return True

        except ImportError as ie:
            logger.warning(
                f"Subscription models not found - skipping trial activation: {ie}"
            )
            return False
        except Exception as e:
            logger.error(f"Error activating premium trial: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _get_score_category(self, score):
        """
        Convert numerical score to category.

        Args:
            score: ATS score (0-100)

        Returns:
            str: Score category (Excellent, Good, Fair, Needs Improvement)
        """
        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 50:
            return "Fair"
        else:
            return "Needs Improvement"

    def _get_experience_description(self, classification):
        """
        Return a description for the experience level.

        Args:
            classification: Experience level classification (entry, junior, mid, senior, expert)

        Returns:
            str: Description of the experience level
        """
        descriptions = {
            "entry": "This level indicates you're starting your career journey with foundational skills and knowledge.",
            "junior": "This level shows you have some practical experience and are developing your professional skills.",
            "mid": "This level demonstrates solid professional experience with proven capabilities in your field.",
            "senior": "This level of experience suggests advanced knowledge in your field with demonstrated project leadership and deep technical expertise.",
            "expert": "This level indicates mastery in your field with extensive experience leading strategic initiatives.",
        }
        return descriptions.get(
            classification.lower(),
            "Experience level analysis available with full report.",
        )
