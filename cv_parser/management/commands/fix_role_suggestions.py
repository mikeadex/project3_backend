import json
from collections import Counter, defaultdict
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from cv_parser.models import ParsedCV
from ai_cv_parser.deepseek_service import DeepSeekService
import time

class Command(BaseCommand):
    help = 'Analyze and fix role suggestion issues'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze-existing',
            action='store_true',
            help='Analyze existing CVs in database for role suggestion patterns'
        )
        parser.add_argument(
            '--fix-prompts',
            action='store_true',
            help='Test improved prompts for role suggestions'
        )
        parser.add_argument(
            '--sample-size',
            type=int,
            default=20,
            help='Number of CVs to analyze (default: 20)'
        )
        
    def handle(self, *args, **options):
        if options['analyze_existing']:
            self.analyze_existing_role_suggestions(options['sample_size'])
            
        if options['fix_prompts']:
            self.test_improved_prompts(options['sample_size'])
            
    def analyze_existing_role_suggestions(self, sample_size):
        """Analyze existing CVs for role suggestion patterns"""
        self.stdout.write("Analyzing existing role suggestions...")
        
        # Get sample of parsed CVs
        parsed_cvs = ParsedCV.objects.filter(
            parsed_data__isnull=False
        ).order_by('-created_at')[:sample_size]
        
        if not parsed_cvs:
            self.stdout.write(
                self.style.WARNING("No analyzed CVs found in database")
            )
            return
            
        role_analysis = {
            'total_cvs': len(parsed_cvs),
            'role_frequency': Counter(),
            'cv_roles': [],
            'issues_found': []
        }
        
        for cv in parsed_cvs:
            try:
                # Since we don't have analysis_data, let's generate it on the fly for testing
                self.stdout.write(f"Analyzing CV {cv.id}...")
                
                # Test role generation for this CV
                roles = self.test_role_generation_for_cv(cv.parsed_data)
                
                cv_info = {
                    'cv_id': cv.id,
                    'filename': f"CV_{cv.id}",
                    'roles': roles,
                    'analysis_date': cv.created_at.isoformat() if cv.created_at else None
                }
                
                role_analysis['cv_roles'].append(cv_info)
                
                # Count role frequencies
                for role in roles:
                    role_analysis['role_frequency'][role] += 1
                    
                # Detect issues
                issues = self.detect_role_issues(roles, cv.parsed_data)
                if issues:
                    role_analysis['issues_found'].extend([
                        {'cv_id': cv.id, 'issue': issue} for issue in issues
                    ])
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error analyzing CV {cv.id}: {str(e)}")
                )
                
    def test_role_generation_for_cv(self, parsed_data):
        """Generate roles for a CV to test the current system"""
        try:
            service = DeepSeekService()
            
            prompt = f"""
            Analyze this CV and suggest suitable job roles:
            
            CV Data: {json.dumps(parsed_data, indent=2)}
            
            Provide response in JSON format:
            {{
                "potential_roles": {{
                    "best_matches": [list of 3-5 job roles]
                }}
            }}
            """
            
            response = service.make_custom_request(prompt)
            
            if isinstance(response, dict) and 'potential_roles' in response:
                return response['potential_roles'].get('best_matches', [])
                
        except Exception as e:
            self.stdout.write(f"Error generating roles: {str(e)}")
            
        return []
                
        # Generate report
        self.generate_role_analysis_report(role_analysis)
        
    def extract_roles_from_analysis(self, analysis_data):
        """Extract role suggestions from analysis data"""
        roles = []
        
        if isinstance(analysis_data, dict):
            # Try different possible keys
            potential_role_keys = [
                'potential_roles',
                'suggested_roles', 
                'best_matches',
                'job_roles',
                'role_suggestions'
            ]
            
            for key in potential_role_keys:
                if key in analysis_data:
                    role_data = analysis_data[key]
                    
                    if isinstance(role_data, dict):
                        # Handle nested structure
                        if 'best_matches' in role_data:
                            roles.extend(role_data['best_matches'])
                        elif 'roles' in role_data:
                            roles.extend(role_data['roles'])
                    elif isinstance(role_data, list):
                        # Handle direct list
                        roles.extend(role_data)
                        
        return roles
        
    def detect_role_issues(self, roles, parsed_data):
        """Detect issues with role suggestions"""
        issues = []
        
        # Issue 1: No roles suggested
        if not roles:
            issues.append("No roles suggested")
            
        # Issue 2: Too generic roles
        generic_roles = [
            'Professional', 'Employee', 'Worker', 'Specialist', 
            'Expert', 'Individual', 'Person', 'Candidate'
        ]
        
        if any(role in generic_roles for role in roles):
            issues.append("Generic role suggestions")
            
        # Issue 3: Roles don't match CV content
        if parsed_data and isinstance(parsed_data, dict):
            experience = parsed_data.get('experience', [])
            skills = parsed_data.get('skills', [])
            
            # Check if roles match actual job titles in experience
            actual_titles = []
            if isinstance(experience, list):
                for exp in experience:
                    if isinstance(exp, dict) and 'title' in exp:
                        actual_titles.append(exp['title'])
                        
            if actual_titles and roles:
                # Check if suggested roles are completely different from actual experience
                role_match_found = False
                for role in roles:
                    for title in actual_titles:
                        if any(word in role.lower() for word in title.lower().split()):
                            role_match_found = True
                            break
                            
                if not role_match_found:
                    issues.append("Roles don't match experience")
                    
        # Issue 4: Duplicate roles
        if len(roles) != len(set(roles)):
            issues.append("Duplicate role suggestions")
            
        # Issue 5: Too many roles
        if len(roles) > 8:
            issues.append("Too many roles suggested")
            
        return issues
        
    def test_improved_prompts(self, sample_size):
        """Test improved prompts for better role suggestions"""
        self.stdout.write("Testing improved role suggestion prompts...")
        
        # Get sample CVs
        parsed_cvs = ParsedCV.objects.filter(
            parsed_data__isnull=False
        ).order_by('-created_at')[:sample_size]
        
        if not parsed_cvs:
            self.stdout.write(
                self.style.WARNING("No parsed CVs found for testing")
            )
            return
            
        service = DeepSeekService()
        
        comparison_results = []
        
        for i, cv in enumerate(parsed_cvs):
            self.stdout.write(f"Testing CV {i+1}/{len(parsed_cvs)}: {cv.file_name}")
            
            # Test original prompt (simplified)
            original_roles = self.test_original_prompt(service, cv.parsed_data)
            
            # Test improved prompt
            improved_roles = self.test_improved_prompt(service, cv.parsed_data)
            
            comparison = {
                'cv_id': cv.id,
                'filename': cv.file_name,
                'original_roles': original_roles,
                'improved_roles': improved_roles,
                'improvement_score': self.calculate_improvement_score(
                    original_roles, improved_roles, cv.parsed_data
                )
            }
            
            comparison_results.append(comparison)
            
            # Add delay to avoid rate limiting
            time.sleep(1)
            
        # Generate comparison report
        self.generate_prompt_comparison_report(comparison_results)
        
    def test_original_prompt(self, service, parsed_data):
        """Test the original prompt style"""
        try:
            prompt = f"""
            Analyze this CV and suggest suitable job roles:
            
            CV Data: {json.dumps(parsed_data, indent=2)}
            
            Provide response in JSON format:
            {{
                "potential_roles": {{
                    "best_matches": [list of 3-5 job roles]
                }}
            }}
            """
            
            response = service.make_custom_request(prompt)
            
            if isinstance(response, dict) and 'potential_roles' in response:
                return response['potential_roles'].get('best_matches', [])
                
        except Exception as e:
            self.stdout.write(f"Error with original prompt: {str(e)}")
            
        return []
        
    def test_improved_prompt(self, service, parsed_data):
        """Test improved prompt with better context and specificity"""
        try:
            # Extract key information for better context
            experience = parsed_data.get('experience', [])
            skills = parsed_data.get('skills', [])
            education = parsed_data.get('education', [])
            
            # Build context-aware prompt
            context_info = []
            
            if experience:
                recent_jobs = experience[:2]  # Most recent jobs
                job_context = []
                for job in recent_jobs:
                    if isinstance(job, dict):
                        title = job.get('title', '')
                        company = job.get('company', '')
                        if title:
                            job_context.append(f"{title} at {company}")
                            
                if job_context:
                    context_info.append(f"Recent experience: {', '.join(job_context)}")
                    
            if skills:
                top_skills = skills[:10] if isinstance(skills, list) else []
                if top_skills:
                    context_info.append(f"Key skills: {', '.join(top_skills)}")
                    
            if education:
                edu_info = []
                for edu in education[:2]:  # Most relevant education
                    if isinstance(edu, dict):
                        degree = edu.get('degree', '')
                        major = edu.get('major', '')
                        if degree and major:
                            edu_info.append(f"{degree} in {major}")
                            
                if edu_info:
                    context_info.append(f"Education: {', '.join(edu_info)}")
                    
            context = ". ".join(context_info)
            
            prompt = f"""
            You are a career advisor analyzing a CV to suggest the most appropriate job roles.
            
            Context: {context}
            
            Instructions:
            1. Analyze the candidate's experience, skills, and education
            2. Suggest 3-5 specific job roles that best match their background
            3. Focus on roles they could realistically obtain given their experience level
            4. Avoid generic titles - be specific about the role type and level
            5. Consider career progression from their current/recent positions
            
            CV Data: {json.dumps(parsed_data, indent=2)}
            
            Respond in JSON format:
            {{
                "role_analysis": {{
                    "experience_level": "entry-level|mid-level|senior|executive",
                    "primary_domain": "main field/industry",
                    "best_matches": [
                        "Specific Role Title 1",
                        "Specific Role Title 2", 
                        "Specific Role Title 3",
                        "Specific Role Title 4",
                        "Specific Role Title 5"
                    ],
                    "match_reasoning": [
                        "Why role 1 matches",
                        "Why role 2 matches",
                        "Why role 3 matches", 
                        "Why role 4 matches",
                        "Why role 5 matches"
                    ]
                }}
            }}
            """
            
            response = service.make_custom_request(prompt)
            
            if isinstance(response, dict) and 'role_analysis' in response:
                return response['role_analysis'].get('best_matches', [])
                
        except Exception as e:
            self.stdout.write(f"Error with improved prompt: {str(e)}")
            
        return []
        
    def calculate_improvement_score(self, original_roles, improved_roles, parsed_data):
        """Calculate improvement score based on role quality"""
        score = 0
        
        # Factor 1: Number of roles (3-5 is optimal)
        if 3 <= len(improved_roles) <= 5:
            score += 2
        elif len(improved_roles) > 0:
            score += 1
            
        # Factor 2: Specificity (avoid generic terms)
        generic_terms = ['professional', 'specialist', 'expert', 'manager', 'coordinator']
        improved_generic_count = sum(1 for role in improved_roles 
                                   if any(term in role.lower() for term in generic_terms))
        original_generic_count = sum(1 for role in original_roles 
                                   if any(term in role.lower() for term in generic_terms))
        
        if improved_generic_count < original_generic_count:
            score += 2
            
        # Factor 3: Relevance to experience
        if parsed_data and 'experience' in parsed_data:
            experience = parsed_data['experience']
            if isinstance(experience, list) and experience:
                actual_titles = [exp.get('title', '') for exp in experience 
                               if isinstance(exp, dict)]
                
                # Check if improved roles better match actual experience
                improved_relevance = self.calculate_relevance_score(improved_roles, actual_titles)
                original_relevance = self.calculate_relevance_score(original_roles, actual_titles)
                
                if improved_relevance > original_relevance:
                    score += 3
                elif improved_relevance == original_relevance and improved_relevance > 0:
                    score += 1
                    
        # Factor 4: Diversity (roles should be varied but related)
        if len(set(improved_roles)) == len(improved_roles):  # No duplicates
            score += 1
            
        return score
        
    def calculate_relevance_score(self, suggested_roles, actual_titles):
        """Calculate how relevant suggested roles are to actual job titles"""
        if not suggested_roles or not actual_titles:
            return 0
            
        relevance_score = 0
        
        for suggested in suggested_roles:
            for actual in actual_titles:
                # Simple word overlap scoring
                suggested_words = set(suggested.lower().split())
                actual_words = set(actual.lower().split())
                
                overlap = len(suggested_words.intersection(actual_words))
                if overlap > 0:
                    relevance_score += overlap
                    
        return relevance_score
        
    def generate_role_analysis_report(self, role_analysis):
        """Generate comprehensive role analysis report"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("ROLE SUGGESTION ANALYSIS REPORT")
        self.stdout.write("="*60)
        
        # Summary statistics
        total_cvs = role_analysis['total_cvs']
        role_freq = role_analysis['role_frequency']
        
        self.stdout.write(f"\nSUMMARY:")
        self.stdout.write(f"Total CVs analyzed: {total_cvs}")
        self.stdout.write(f"Unique roles suggested: {len(role_freq)}")
        self.stdout.write(f"Average roles per CV: {sum(role_freq.values()) / max(total_cvs, 1):.2f}")
        
        # Most common roles
        self.stdout.write(f"\nMOST COMMON ROLE SUGGESTIONS:")
        for role, count in role_freq.most_common(10):
            percentage = (count / total_cvs) * 100
            self.stdout.write(f"  {role}: {count} CVs ({percentage:.1f}%)")
            
        # Issues found
        issues = role_analysis['issues_found']
        if issues:
            self.stdout.write(f"\nISSUES DETECTED ({len(issues)} total):")
            issue_summary = Counter([issue['issue'] for issue in issues])
            for issue_type, count in issue_summary.most_common():
                self.stdout.write(f"  {issue_type}: {count} cases")
                
        # Role diversity analysis
        self.stdout.write(f"\nROLE DIVERSITY ANALYSIS:")
        if len(role_freq) < total_cvs * 0.3:
            self.stdout.write(
                self.style.ERROR("⚠️  LOW DIVERSITY: Role suggestions appear repetitive")
            )
        elif len(role_freq) > total_cvs * 1.5:
            self.stdout.write(
                self.style.WARNING("⚠️  HIGH DIVERSITY: Role suggestions may be too scattered")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ HEALTHY DIVERSITY: Good balance of role suggestions")
            )
            
    def generate_prompt_comparison_report(self, comparison_results):
        """Generate prompt comparison report"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("PROMPT IMPROVEMENT COMPARISON REPORT")
        self.stdout.write("="*60)
        
        if not comparison_results:
            self.stdout.write("No comparison data available")
            return
            
        # Calculate overall improvement
        total_score = sum(result['improvement_score'] for result in comparison_results)
        avg_improvement = total_score / len(comparison_results)
        
        self.stdout.write(f"\nOVERALL IMPROVEMENT:")
        self.stdout.write(f"Average improvement score: {avg_improvement:.2f}/10")
        
        improved_count = sum(1 for result in comparison_results 
                           if result['improvement_score'] > 5)
        improvement_rate = (improved_count / len(comparison_results)) * 100
        
        self.stdout.write(f"CVs with significant improvement: {improved_count}/{len(comparison_results)} ({improvement_rate:.1f}%)")
        
        # Examples of improvement
        best_improvements = sorted(comparison_results, 
                                 key=lambda x: x['improvement_score'], 
                                 reverse=True)[:3]
        
        self.stdout.write(f"\nTOP IMPROVEMENTS:")
        for i, result in enumerate(best_improvements, 1):
            self.stdout.write(f"\n{i}. {result['filename']} (Score: {result['improvement_score']}/10)")
            self.stdout.write(f"   Original: {result['original_roles']}")
            self.stdout.write(f"   Improved: {result['improved_roles']}")
            
        # Recommendations
        self.stdout.write(f"\nRECOMMENDALITIONS:")
        if avg_improvement >= 7:
            self.stdout.write(
                self.style.SUCCESS("✅ Implement improved prompt - significant enhancement detected")
            )
        elif avg_improvement >= 5:
            self.stdout.write(
                self.style.WARNING("⚠️  Consider implementing improved prompt - moderate enhancement")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Further prompt optimization needed")
            )
