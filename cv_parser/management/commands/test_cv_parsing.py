import os
import json
import time
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from cv_parser.models import ParsedCV
from cv_parser.parsers import AdvancedDocumentParser
from ai_cv_parser.deepseek_service import DeepSeekService
from ai_cv_parser.views import analyze_cv
from django.test.client import RequestFactory
import traceback
import pandas as pd

class Command(BaseCommand):
    help = 'Test CV parsing with 50 different CVs and generate comprehensive report'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test-dir',
            type=str,
            default='test_cvs',
            help='Directory containing test CV files'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='cv_test_results',
            help='Directory to save test results'
        )
        parser.add_argument(
            '--create-samples',
            action='store_true',
            help='Create sample CV directory structure'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=1,
            help='User ID to use for testing (default: 1)'
        )
        
    def handle(self, *args, **options):
        self.test_dir = options['test_dir']
        self.output_dir = options['output_dir']
        self.user_id = options['user_id']
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up logging
        self.setup_logging()
        
        if options['create_samples']:
            self.create_sample_structure()
            return
            
        # Get or create test user
        try:
            self.test_user = User.objects.get(id=self.user_id)
        except User.DoesNotExist:
            # Try to find any existing user
            existing_user = User.objects.first()
            if existing_user:
                self.test_user = existing_user
                self.stdout.write(
                    self.style.WARNING(f'User ID {self.user_id} not found. Using existing user: {existing_user.email}')
                )
            else:
                # Create a test user
                self.test_user = User.objects.create_user(
                    username='test_cv_user',
                    email='test@example.com',
                    password='testpassword123'
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Created test user: {self.test_user.email}')
                )
            
        self.stdout.write(
            self.style.SUCCESS(f'Starting CV parsing tests with user: {self.test_user.email}')
        )
        
        # Run comprehensive tests
        results = self.run_cv_tests()
        
        # Generate reports
        self.generate_reports(results)
        
        self.stdout.write(
            self.style.SUCCESS(f'CV testing completed. Results saved to {self.output_dir}')
        )
    
    def setup_logging(self):
        """Set up detailed logging for the test"""
        self.logger = logging.getLogger('cv_test')
        self.logger.setLevel(logging.DEBUG)
        
        # Create file handler
        log_file = os.path.join(self.output_dir, f'cv_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
    def create_sample_structure(self):
        """Create sample directory structure for test CVs"""
        categories = [
            'tech_resumes',
            'business_resumes', 
            'creative_resumes',
            'healthcare_resumes',
            'education_resumes',
            'problematic_formats'
        ]
        
        os.makedirs(self.test_dir, exist_ok=True)
        
        for category in categories:
            category_dir = os.path.join(self.test_dir, category)
            os.makedirs(category_dir, exist_ok=True)
            
            # Create README with instructions
            readme_content = f"""# {category.replace('_', ' ').title()}

Place CV files for testing in this directory.

Supported formats:
- PDF (.pdf)
- Word documents (.doc, .docx)

File naming convention:
- Use descriptive names
- Include experience level: junior_dev_cv.pdf, senior_manager_cv.docx
- Include industry indicators: marketing_specialist_cv.pdf

Examples for {category}:
- entry_level_software_engineer.pdf
- senior_full_stack_developer.docx
- mid_level_data_scientist.pdf
"""
            
            readme_path = os.path.join(category_dir, 'README.md')
            with open(readme_path, 'w') as f:
                f.write(readme_content)
                
        self.stdout.write(
            self.style.SUCCESS(f'Created test directory structure at {self.test_dir}')
        )
        self.stdout.write(
            self.style.WARNING('Please add CV files to the category directories and run the test again.')
        )
        
    def run_cv_tests(self):
        """Run comprehensive CV parsing tests"""
        results = {
            'summary': {
                'total_files': 0,
                'successful_parses': 0,
                'failed_parses': 0,
                'analysis_successes': 0,
                'analysis_failures': 0,
                'unique_roles_suggested': set(),
                'parsing_methods_used': {},
                'test_start_time': datetime.now().isoformat(),
                'test_duration': 0
            },
            'detailed_results': [],
            'parsing_issues': [],
            'role_analysis': {},
            'performance_metrics': {}
        }
        
        start_time = time.time()
        
        # Find all CV files
        cv_files = self.find_cv_files()
        results['summary']['total_files'] = len(cv_files)
        
        if not cv_files:
            self.stdout.write(
                self.style.WARNING(f'No CV files found in {self.test_dir}')
            )
            return results
            
        self.stdout.write(
            self.style.SUCCESS(f'Found {len(cv_files)} CV files to test')
        )
        
        # Test each CV
        for i, (file_path, category) in enumerate(cv_files, 1):
            self.stdout.write(f'Testing CV {i}/{len(cv_files)}: {os.path.basename(file_path)}')
            
            file_result = self.test_single_cv(file_path, category)
            results['detailed_results'].append(file_result)
            
            # Update summary statistics
            if file_result['parsing']['success']:
                results['summary']['successful_parses'] += 1
            else:
                results['summary']['failed_parses'] += 1
                results['parsing_issues'].append(file_result)
                
            if file_result['analysis']['success']:
                results['summary']['analysis_successes'] += 1
                
                # Track role suggestions
                if 'potential_roles' in file_result['analysis'].get('response', {}):
                    roles = file_result['analysis']['response'].get('potential_roles', {}).get('best_matches', [])
                    results['summary']['unique_roles_suggested'].update(roles)
            else:
                results['summary']['analysis_failures'] += 1
                
            # Track parsing methods
            method = file_result['parsing'].get('method_used', 'unknown')
            results['summary']['parsing_methods_used'][method] = \
                results['summary']['parsing_methods_used'].get(method, 0) + 1
        
        # Calculate test duration
        end_time = time.time()
        results['summary']['test_duration'] = round(end_time - start_time, 2)
        results['summary']['unique_roles_suggested'] = list(results['summary']['unique_roles_suggested'])
        
        # Analyze role suggestion patterns
        self.analyze_role_patterns(results)
        
        return results
        
    def find_cv_files(self):
        """Find all CV files in the test directory"""
        cv_files = []
        supported_extensions = ['.pdf', '.doc', '.docx']
        
        if not os.path.exists(self.test_dir):
            return cv_files
            
        for root, dirs, files in os.walk(self.test_dir):
            # Determine category from directory structure
            category = os.path.basename(root) if root != self.test_dir else 'uncategorized'
            
            for file in files:
                if any(file.lower().endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    cv_files.append((file_path, category))
                    
        return cv_files
        
    def test_single_cv(self, file_path, category):
        """Test parsing and analysis of a single CV"""
        file_result = {
            'file_info': {
                'path': file_path,
                'filename': os.path.basename(file_path),
                'category': category,
                'size_bytes': os.path.getsize(file_path),
                'extension': os.path.splitext(file_path)[1].lower()
            },
            'parsing': {
                'success': False,
                'method_used': None,
                'extraction_time': 0,
                'text_length': 0,
                'parsed_data': None,
                'error': None
            },
            'analysis': {
                'success': False,
                'analysis_time': 0,
                'response': None,
                'roles_suggested': [],
                'overall_score': 0,
                'error': None
            }
        }
        
        # Test parsing
        try:
            self.logger.info(f"Starting parse test for {file_path}")
            parse_start = time.time()
            
            parser = AdvancedDocumentParser()
            parsed_data = parser.parse_document(file_path)
            
            parse_time = time.time() - parse_start
            
            if parsed_data and isinstance(parsed_data, dict):
                file_result['parsing'].update({
                    'success': True,
                    'extraction_time': round(parse_time, 2),
                    'parsed_data': parsed_data,
                    'text_length': len(str(parsed_data))
                })
                
                # Determine parsing method used
                if hasattr(parser, 'last_method_used'):
                    file_result['parsing']['method_used'] = parser.last_method_used
                else:
                    file_result['parsing']['method_used'] = 'standard'
                    
                self.logger.info(f"Parse successful for {file_path}: {parse_time:.2f}s")
                
                # Test analysis if parsing succeeded
                file_result['analysis'] = self.test_cv_analysis(parsed_data, file_path)
                
            else:
                file_result['parsing']['error'] = "Empty or invalid parsed data"
                self.logger.error(f"Parse failed for {file_path}: Empty result")
                
        except Exception as e:
            file_result['parsing']['error'] = str(e)
            self.logger.error(f"Parse error for {file_path}: {str(e)}")
            self.logger.error(traceback.format_exc())
            
        return file_result
        
    def test_cv_analysis(self, parsed_data, file_path):
        """Test CV analysis functionality"""
        analysis_result = {
            'success': False,
            'analysis_time': 0,
            'response': None,
            'roles_suggested': [],
            'overall_score': 0,
            'error': None
        }
        
        try:
            self.logger.info(f"Starting analysis test for {file_path}")
            analysis_start = time.time()
            
            # Create a ParsedCV instance for testing (note: no file_name field in model)
            parsed_cv = ParsedCV.objects.create(
                user=self.test_user,
                parsed_data=parsed_data
            )
            
            # Use DeepSeek service directly
            service = DeepSeekService()
            
            # Prepare analysis prompt (simplified version of the actual prompt)
            prompt = f"""
            Analyze this CV data and provide structured feedback:
            
            CV Data: {json.dumps(parsed_data, indent=2)}
            
            Provide analysis in JSON format with:
            {{
                "overall_score": (1-10),
                "potential_roles": {{
                    "best_matches": [list of 3-5 suitable job roles],
                    "match_reasons": [brief reasons for each match]
                }}
            }}
            """
            
            response = service.make_custom_request(prompt)
            analysis_time = time.time() - analysis_start
            
            if 'error' not in response:
                analysis_result.update({
                    'success': True,
                    'analysis_time': round(analysis_time, 2),
                    'response': response
                })
                
                # Extract key metrics
                if isinstance(response, dict):
                    analysis_result['overall_score'] = response.get('overall_score', 0)
                    
                    potential_roles = response.get('potential_roles', {})
                    if isinstance(potential_roles, dict):
                        analysis_result['roles_suggested'] = potential_roles.get('best_matches', [])
                        
                self.logger.info(f"Analysis successful for {file_path}: {analysis_time:.2f}s")
            else:
                analysis_result['error'] = response.get('error', 'Unknown analysis error')
                self.logger.error(f"Analysis failed for {file_path}: {analysis_result['error']}")
                
            # Clean up test data
            parsed_cv.delete()
            
        except Exception as e:
            analysis_result['error'] = str(e)
            self.logger.error(f"Analysis error for {file_path}: {str(e)}")
            self.logger.error(traceback.format_exc())
            
        return analysis_result
        
    def analyze_role_patterns(self, results):
        """Analyze patterns in role suggestions"""
        role_frequency = {}
        role_by_category = {}
        
        for result in results['detailed_results']:
            category = result['file_info']['category']
            roles = result['analysis'].get('roles_suggested', [])
            
            # Track overall role frequency
            for role in roles:
                role_frequency[role] = role_frequency.get(role, 0) + 1
                
            # Track roles by category
            if category not in role_by_category:
                role_by_category[category] = {}
                
            for role in roles:
                role_by_category[category][role] = role_by_category[category].get(role, 0) + 1
        
        results['role_analysis'] = {
            'role_frequency': role_frequency,
            'role_by_category': role_by_category,
            'most_common_roles': sorted(role_frequency.items(), key=lambda x: x[1], reverse=True)[:10],
            'role_diversity_score': len(role_frequency) / max(len(results['detailed_results']), 1)
        }
        
    def generate_reports(self, results):
        """Generate comprehensive test reports"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Save raw results as JSON
        json_file = os.path.join(self.output_dir, f'cv_test_results_{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        # 2. Generate summary report
        self.generate_summary_report(results, timestamp)
        
        # 3. Generate detailed CSV
        self.generate_csv_report(results, timestamp)
        
        # 4. Generate parsing issues report
        self.generate_parsing_issues_report(results, timestamp)
        
        # 5. Generate role analysis report
        self.generate_role_analysis_report(results, timestamp)
        
    def generate_summary_report(self, results, timestamp):
        """Generate human-readable summary report"""
        summary_file = os.path.join(self.output_dir, f'cv_test_summary_{timestamp}.txt')
        
        with open(summary_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("CV PARSING AND ANALYSIS TEST REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            # Summary statistics
            summary = results['summary']
            f.write(f"Test Duration: {summary['test_duration']} seconds\n")
            f.write(f"Total Files Tested: {summary['total_files']}\n")
            f.write(f"Successful Parses: {summary['successful_parses']} ({summary['successful_parses']/summary['total_files']*100:.1f}%)\n")
            f.write(f"Failed Parses: {summary['failed_parses']} ({summary['failed_parses']/summary['total_files']*100:.1f}%)\n")
            f.write(f"Successful Analyses: {summary['analysis_successes']} ({summary['analysis_successes']/summary['total_files']*100:.1f}%)\n")
            f.write(f"Failed Analyses: {summary['analysis_failures']} ({summary['analysis_failures']/summary['total_files']*100:.1f}%)\n\n")
            
            # Parsing methods
            f.write("PARSING METHODS USED:\n")
            f.write("-" * 40 + "\n")
            for method, count in summary['parsing_methods_used'].items():
                f.write(f"{method}: {count} files\n")
            f.write("\n")
            
            # Role diversity analysis
            role_analysis = results['role_analysis']
            f.write("ROLE SUGGESTION ANALYSIS:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Unique Roles Suggested: {len(summary['unique_roles_suggested'])}\n")
            f.write(f"Role Diversity Score: {role_analysis['role_diversity_score']:.2f}\n\n")
            
            f.write("Most Common Role Suggestions:\n")
            for role, count in role_analysis['most_common_roles'][:10]:
                f.write(f"  {role}: {count} times\n")
            f.write("\n")
            
            # Issues summary
            if results['parsing_issues']:
                f.write("PARSING ISSUES SUMMARY:\n")
                f.write("-" * 40 + "\n")
                for issue in results['parsing_issues'][:5]:  # Top 5 issues
                    f.write(f"File: {issue['file_info']['filename']}\n")
                    f.write(f"Error: {issue['parsing']['error']}\n")
                    f.write(f"Size: {issue['file_info']['size_bytes']} bytes\n\n")
                    
    def generate_csv_report(self, results, timestamp):
        """Generate detailed CSV report for analysis"""
        csv_file = os.path.join(self.output_dir, f'cv_test_detailed_{timestamp}.csv')
        
        rows = []
        for result in results['detailed_results']:
            row = {
                'filename': result['file_info']['filename'],
                'category': result['file_info']['category'],
                'file_size_bytes': result['file_info']['size_bytes'],
                'extension': result['file_info']['extension'],
                'parsing_success': result['parsing']['success'],
                'parsing_method': result['parsing'].get('method_used', ''),
                'extraction_time': result['parsing']['extraction_time'],
                'text_length': result['parsing']['text_length'],
                'parsing_error': result['parsing'].get('error', ''),
                'analysis_success': result['analysis']['success'],
                'analysis_time': result['analysis']['analysis_time'],
                'overall_score': result['analysis']['overall_score'],
                'roles_suggested': ', '.join(result['analysis']['roles_suggested']),
                'analysis_error': result['analysis'].get('error', '')
            }
            rows.append(row)
            
        df = pd.DataFrame(rows)
        df.to_csv(csv_file, index=False)
        
    def generate_parsing_issues_report(self, results, timestamp):
        """Generate detailed parsing issues report"""
        issues_file = os.path.join(self.output_dir, f'cv_parsing_issues_{timestamp}.txt')
        
        with open(issues_file, 'w') as f:
            f.write("DETAILED PARSING ISSUES REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            if not results['parsing_issues']:
                f.write("No parsing issues found!\n")
                return
                
            for i, issue in enumerate(results['parsing_issues'], 1):
                f.write(f"ISSUE #{i}\n")
                f.write("-" * 20 + "\n")
                f.write(f"File: {issue['file_info']['filename']}\n")
                f.write(f"Category: {issue['file_info']['category']}\n")
                f.write(f"Size: {issue['file_info']['size_bytes']} bytes\n")
                f.write(f"Extension: {issue['file_info']['extension']}\n")
                f.write(f"Error: {issue['parsing']['error']}\n")
                
                if issue['analysis']['error']:
                    f.write(f"Analysis Error: {issue['analysis']['error']}\n")
                    
                f.write("\n")
                
    def generate_role_analysis_report(self, results, timestamp):
        """Generate role analysis report"""
        role_file = os.path.join(self.output_dir, f'cv_role_analysis_{timestamp}.txt')
        
        with open(role_file, 'w') as f:
            f.write("CV ROLE SUGGESTION ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            role_analysis = results['role_analysis']
            
            f.write("ROLE FREQUENCY ANALYSIS:\n")
            f.write("-" * 30 + "\n")
            for role, count in role_analysis['most_common_roles']:
                f.write(f"{role}: {count} suggestions\n")
            f.write("\n")
            
            f.write("ROLE SUGGESTIONS BY CATEGORY:\n")
            f.write("-" * 30 + "\n")
            for category, roles in role_analysis['role_by_category'].items():
                f.write(f"\n{category.upper()}:\n")
                sorted_roles = sorted(roles.items(), key=lambda x: x[1], reverse=True)
                for role, count in sorted_roles[:5]:  # Top 5 per category
                    f.write(f"  {role}: {count}\n")
                    
            # Diversity analysis
            f.write("\nROLE DIVERSITY ANALYSIS:\n")
            f.write("-" * 30 + "\n")
            f.write(f"Total Unique Roles: {len(role_analysis['role_frequency'])}\n")
            f.write(f"Average Roles per CV: {len(role_analysis['role_frequency']) / max(len(results['detailed_results']), 1):.2f}\n")
            f.write(f"Role Diversity Score: {role_analysis['role_diversity_score']:.2f}\n")
            
            if role_analysis['role_diversity_score'] < 0.5:
                f.write("\n⚠️  LOW DIVERSITY WARNING: Role suggestions may be too generic or repetitive.\n")
            elif role_analysis['role_diversity_score'] > 2.0:
                f.write("\n⚠️  HIGH DIVERSITY WARNING: Role suggestions may be too scattered or inconsistent.\n")
            else:
                f.write("\n✅ DIVERSITY SCORE HEALTHY: Good balance of specific and diverse role suggestions.\n")
