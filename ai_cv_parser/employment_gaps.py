import datetime
from dateutil.parser import parse as date_parse
from dateutil.relativedelta import relativedelta

class EmploymentGapsAnalyzer:
    """
    Analyzes a CV for employment gaps and provides insights on their significance.
    
    This class identifies periods without employment in a candidate's career history,
    calculates their duration, and provides context-aware recommendations.
    """
    
    SIGNIFICANT_GAP_MONTHS = 3  # Gaps longer than this are considered significant
    
    def __init__(self, experiences=None):
        """
        Initialize the analyzer with a list of work experiences.
        
        Args:
            experiences: List of dictionaries with 'start_date' and 'end_date' keys
        """
        self.experiences = experiences or []
        self.sorted_experiences = []
        self.gaps = []
    
    def analyze(self):
        """
        Analyze the provided work experiences to identify and quantify employment gaps.
        
        Returns:
            dict: Analysis results including gaps, summary, and recommendations
        """
        if not self.experiences:
            return {
                "summary": "No employment history provided for gap analysis.",
                "gaps": [],
                "has_significant_gaps": False
            }
        
        # Parse and sort experiences by date
        self._parse_and_sort_experiences()
        
        # Find gaps between experiences
        self._identify_gaps()
        
        # Calculate statistics 
        total_gap_months = sum(gap['duration_months'] for gap in self.gaps)
        has_significant_gaps = any(gap['duration_months'] >= self.SIGNIFICANT_GAP_MONTHS for gap in self.gaps)
        
        # Generate summary and recommendations
        summary = self._generate_summary()
        addressing_tips = self._generate_addressing_tips()
        impact = self._assess_impact()
        
        return {
            "summary": summary,
            "gaps": self.gaps,
            "has_significant_gaps": has_significant_gaps,
            "total_gap_months": total_gap_months,
            "addressing_tips": addressing_tips,
            "impact": impact
        }
    
    def _parse_and_sort_experiences(self):
        """Parse date strings and sort experiences chronologically"""
        parsed_experiences = []
        
        for exp in self.experiences:
            # Skip experiences without both dates
            if not exp.get('start_date') or not exp.get('end_date'):
                continue
            
            try:
                start_date = self._parse_date(exp['start_date'])
                
                # Handle "Present" or empty end dates
                if exp['end_date'].lower() in ('present', 'current', 'now', '') or exp['end_date'] is None:
                    end_date = datetime.datetime.now().date()
                else:
                    end_date = self._parse_date(exp['end_date'])
                
                # Only add valid date ranges
                if start_date and end_date and start_date <= end_date:
                    parsed_experiences.append({
                        'company': exp.get('company') or exp.get('company_name', ''),
                        'job_title': exp.get('job_title', ''),
                        'start_date': start_date,
                        'end_date': end_date
                    })
            except (ValueError, TypeError) as e:
                # Skip experiences with invalid dates
                continue
        
        # Sort by start date (oldest first)
        self.sorted_experiences = sorted(parsed_experiences, key=lambda x: x['start_date'])
    
    def _identify_gaps(self):
        """Identify gaps between consecutive job experiences"""
        self.gaps = []
        
        # Need at least 2 experiences to find gaps
        if len(self.sorted_experiences) < 2:
            return
        
        for i in range(len(self.sorted_experiences) - 1):
            current_job = self.sorted_experiences[i]
            next_job = self.sorted_experiences[i + 1]
            
            # Check if there's a gap between current job end and next job start
            if current_job['end_date'] < next_job['start_date']:
                # Calculate gap duration
                gap_delta = relativedelta(next_job['start_date'], current_job['end_date'])
                gap_months = gap_delta.years * 12 + gap_delta.months
                
                # Only count gaps of at least one month
                if gap_months >= 1:
                    # Format dates for display
                    start_date_str = current_job['end_date'].strftime('%B %Y')
                    end_date_str = next_job['start_date'].strftime('%B %Y')
                    period = f"{start_date_str} - {end_date_str}"
                    
                    # Generate an appropriate recommendation based on gap length
                    recommendation = self._generate_recommendation(gap_months)
                    
                    # Add gap to the list
                    self.gaps.append({
                        'start_date': current_job['end_date'].strftime('%Y-%m-%d'),
                        'end_date': next_job['start_date'].strftime('%Y-%m-%d'),
                        'period': period,
                        'duration_months': gap_months,
                        'duration_years': round(gap_months / 12, 1) if gap_months >= 12 else None,
                        'significance': 'high' if gap_months > 12 else 'medium' if gap_months > 6 else 'low',
                        'explanation': None,  # No explanation in CV - would need to be provided by candidate
                        'recommendation': recommendation
                    })
    
    def _generate_recommendation(self, gap_months):
        """Generate a recommendation based on the length of the gap"""
        if gap_months > 12:
            return "Consider adding a detailed explanation for this significant gap. Include any freelance work, education, professional development, or personal projects that demonstrate continued skill development."
        elif gap_months > 6:
            return "Brief explanation recommended. Highlight any skills developed or professional activities during this period."
        else:
            return "Minor gap - consider combining with adjacent positions if related or briefly mention the transition."
    
    def _generate_summary(self):
        """Generate a summary of the employment gaps"""
        if not self.gaps:
            return "No significant employment gaps detected in your work history."
        
        significant_gaps = [g for g in self.gaps if g['significance'] in ('medium', 'high')]
        
        if not significant_gaps:
            return "Your CV shows only minor employment gaps, which are unlikely to raise concerns with employers."
        
        if len(significant_gaps) == 1:
            gap = significant_gaps[0]
            return f"Your CV shows a {gap['duration_months']}-month employment gap from {gap['period']}. This gap may require explanation in job applications."
        else:
            total = len(significant_gaps)
            longest = max(significant_gaps, key=lambda x: x['duration_months'])
            return f"Your CV shows {total} significant employment gaps, including a {longest['duration_months']}-month period from {longest['period']}. These gaps may raise questions with potential employers if not properly addressed."
    
    def _generate_addressing_tips(self):
        """Generate tips for addressing employment gaps"""
        if not self.gaps:
            return []
            
        # Basic tips for everyone with gaps
        tips = [
            "Be honest but strategic about explaining gaps in your cover letter",
            "Focus on skills and knowledge gained during employment gaps",
            "Prepare concise, positive explanations for interviews"
        ]
        
        # Additional tips for significant gaps
        if any(g['significance'] == 'high' for g in self.gaps):
            tips.extend([
                "Consider using a functional resume format to emphasize skills over chronology",
                "Include relevant volunteer work, courses, or certifications obtained during gaps",
                "If gaps were for personal development, highlight transferable skills gained"
            ])
            
        return tips
    
    def _assess_impact(self):
        """Assess the potential impact of the gaps on career progression"""
        if not self.gaps:
            return "No employment gaps detected that would impact your career progression."
            
        recent_gaps = [g for g in self.gaps if self._is_recent(g['end_date'])]
        significant_gaps = [g for g in self.gaps if g['significance'] in ('medium', 'high')]
        
        if recent_gaps and significant_gaps:
            return "Your recent employment gaps may affect how recruiters perceive your career consistency. Without explanation, some automated screening systems might flag your application for review, potentially affecting initial selection phases."
        elif significant_gaps:
            return "While your employment gaps are not recent, their length might still require explanation in interviews. Consider addressing them proactively in your cover letter."
        else:
            return "The minor gaps in your employment history are unlikely to significantly impact your career progression or job prospects."
    
    def _is_recent(self, date_str):
        """Check if a date is within the last 3 years"""
        try:
            date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            three_years_ago = datetime.datetime.now().date() - relativedelta(years=3)
            return date > three_years_ago
        except (ValueError, TypeError):
            return False
    
    def _parse_date(self, date_string):
        """
        Parse date string into a datetime.date object.
        Handles various formats including MM/YYYY, MM-YYYY, Month YYYY, etc.
        """
        if not date_string:
            return None
            
        try:
            # Try standard parsing first
            return date_parse(date_string).date()
        except (ValueError, TypeError):
            # Try custom formats
            formats = ['%m/%Y', '%m-%Y', '%b %Y', '%B %Y', '%Y']
            for fmt in formats:
                try:
                    dt = datetime.datetime.strptime(date_string.strip(), fmt)
                    return dt.date()
                except (ValueError, TypeError):
                    continue
            
            # If all parsing attempts fail
            raise ValueError(f"Could not parse date: {date_string}")


def analyze_employment_gaps(cv_data):
    """
    Analyze employment gaps in a CV.
    
    Args:
        cv_data (dict): CV data containing work experience
        
    Returns:
        dict: Analysis of employment gaps
    """
    experiences = cv_data.get('experience', []) or cv_data.get('work_experience', [])
    analyzer = EmploymentGapsAnalyzer(experiences)
    return analyzer.analyze()
