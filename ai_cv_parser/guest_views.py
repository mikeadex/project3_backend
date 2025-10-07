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

logger = logging.getLogger("ai_cv_parser")


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

            if not self.check_rate_limit(ip_address):
                logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                return Response(
                    {
                        "error": "Rate limit exceeded. You can analyze up to 3 CVs per day.",
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

            # Start async processing
            logger.info(f"Starting async processing for guest CV {guest_cv.id}")
            with ThreadPoolExecutor() as executor:
                executor.submit(self._process_guest_cv, guest_cv.id, temp_path)

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

            # Get analysis data
            analysis = guest_cv.analysis_data or {}
            suggestions = analysis.get("suggestions", [])
            section_scores = analysis.get("section_scores", {})

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
                for strength in ai_strengths[:5]  # Get top 5 strengths
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
                for weakness in ai_weaknesses[:3]  # Get top 3 critical issues
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
                for improvement in ai_improvements[:5]  # Get top 5 improvements
            ]

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

            # Get design and formatting feedback
            design_feedback = {
                "format_score": detailed_section_scores["format_structure"],
                "readability": "Good" if overall_score >= 70 else "Needs Improvement",
                "ats_friendly": overall_score >= 75,
            }

            # Calculate limited preview with enhanced data
            limited_preview = {
                "session_id": session_id,
                "ats_score": overall_score,
                "score_category": self._get_score_category(overall_score),
                # Section scores - show all in preview
                "section_scores": detailed_section_scores,
                # Experience analysis
                "experience_analysis": {
                    "years": years_of_experience,
                    "classification": experience_classification,
                    "level_description": self._get_experience_description(
                        experience_classification
                    ),
                },
                # Show top 3 critical issues (weaknesses)
                "critical_issues": critical_issues[:3],
                # Show 2 strengths to highlight what's working
                "strengths": strengths[:2],
                # Show 2 quick wins (improvement suggestions)
                "quick_improvements": improvements[:2],
                # Design insights
                "design_insights": design_feedback,
                # Counts for locked content
                "hidden_issues_count": max(
                    0, len(ai_weaknesses) + len(ai_improvements) - 5
                ),
                "total_issues": len(ai_weaknesses) + len(ai_improvements),
                "total_strengths": len(ai_strengths),
                "upgrade_required": True,
                "premium_features": {
                    "career_trajectory": {
                        "available": False,
                        "description": "Visualize your career progression and get role-specific insights",
                    },
                    "role_suggestions": {
                        "available": False,
                        "description": "AI-powered job role recommendations based on your experience",
                    },
                    "detailed_analysis": {
                        "available": False,
                        "description": "Complete breakdown of all sections with actionable improvements",
                    },
                    "ats_optimization": {
                        "available": False,
                        "description": "Keyword analysis and ATS compatibility scoring",
                    },
                    "industry_insights": {
                        "available": False,
                        "description": "Benchmark against industry standards and best practices",
                    },
                },
                "trial_offer": {
                    "enabled": True,
                    "duration_days": 30,
                    "message": "Sign up now to get 30 days of premium features FREE!",
                },
            }

            logger.info(f"Returning limited preview for session {session_id}")
            return Response(limited_preview)

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

    def check_rate_limit(self, ip_address):
        """
        Check if IP has exceeded rate limit.
        Limit: 3 CV analyses per 24 hours per IP.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if within limit, False if exceeded
        """
        key = f"guest_cv_analysis_{ip_address}"
        count = cache.get(key, 0)

        if count >= 3:
            logger.warning(f"Rate limit exceeded for IP {ip_address}: {count} requests")
            return False

        # Increment counter with 24-hour expiry
        cache.set(key, count + 1, timeout=86400)
        logger.info(
            f"Rate limit check passed for IP {ip_address}: {count + 1}/3 requests"
        )
        return True

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

                    # Use the same service selection as the regular analyze endpoint
                    try:
                        from .fallback_service import FallbackService

                        service = FallbackService()
                    except ImportError:
                        from cv_parser.services import DeepSeekService

                        service = DeepSeekService()

                    cv_data = cv.parsed_data

                    # Perform chunked analysis
                    analysis_result = viewset._analyze_cv_chunked(cv_data, service)

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
            from subscription.models import Subscription

            # Check if user already has a subscription
            existing_subscription = Subscription.objects.filter(user=user).first()

            if existing_subscription:
                logger.info(f"User {user.username} already has a subscription")
                return False

            # Create premium trial subscription
            subscription = Subscription.objects.create(
                user=user,
                plan="premium",
                status="trial",
                trial_ends_at=timezone.now() + timedelta(days=30),
                is_active=True,
            )

            logger.info(f"Activated 30-day premium trial for user {user.username}")
            return True

        except ImportError:
            logger.warning("Subscription model not found - skipping trial activation")
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
