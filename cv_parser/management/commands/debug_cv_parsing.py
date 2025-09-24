import os
import json
import time
from django.core.management.base import BaseCommand
from cv_parser.parsers import AdvancedDocumentParser
from ai_cv_parser.deepseek_service import DeepSeekService
import traceback

class Command(BaseCommand):
    help = 'Debug CV parsing issues for specific files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the CV file to debug'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
        parser.add_argument(
            '--save-output',
            action='store_true',
            help='Save debug output to file'
        )
        
    def handle(self, *args, **options):
        file_path = options['file_path']
        verbose = options['verbose']
        save_output = options['save_output']
        
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f'File not found: {file_path}')
            )
            return
            
        self.stdout.write(
            self.style.SUCCESS(f'Debugging CV parsing for: {file_path}')
        )
        
        debug_info = {
            'file_info': self.get_file_info(file_path),
            'parsing_steps': [],
            'final_result': None,
            'errors': [],
            'performance': {}
        }
        
        # Test parsing with detailed debugging
        debug_info = self.debug_parsing(file_path, debug_info, verbose)
        
        # Test analysis if parsing succeeded
        if debug_info['final_result']:
            debug_info = self.debug_analysis(debug_info, verbose)
            
        # Display results
        self.display_debug_results(debug_info)
        
        # Save output if requested
        if save_output:
            self.save_debug_output(file_path, debug_info)
            
    def get_file_info(self, file_path):
        """Get basic file information"""
        stat = os.stat(file_path)
        return {
            'path': file_path,
            'filename': os.path.basename(file_path),
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'extension': os.path.splitext(file_path)[1].lower(),
            'modified_time': time.ctime(stat.st_mtime)
        }
        
    def debug_parsing(self, file_path, debug_info, verbose):
        """Debug the parsing process step by step"""
        parser = AdvancedDocumentParser()
        
        # Step 1: Text Extraction
        self.stdout.write("Step 1: Text Extraction")
        try:
            start_time = time.time()
            text = parser._extract_text(file_path)
            extraction_time = time.time() - start_time
            
            step_info = {
                'step': 'text_extraction',
                'success': bool(text and len(text) > 10),
                'time_taken': round(extraction_time, 3),
                'text_length': len(text) if text else 0,
                'text_preview': text[:200] + '...' if text and len(text) > 200 else text,
                'method_used': self.detect_extraction_method(parser, file_path)
            }
            
            debug_info['parsing_steps'].append(step_info)
            
            if verbose and text:
                self.stdout.write(f"  ✓ Extracted {len(text)} characters in {extraction_time:.3f}s")
                self.stdout.write(f"  Preview: {text[:100]}...")
            elif not text:
                self.stdout.write(self.style.WARNING("  ⚠ No text extracted"))
                debug_info['errors'].append("Text extraction failed")
                return debug_info
                
        except Exception as e:
            error_msg = f"Text extraction error: {str(e)}"
            debug_info['errors'].append(error_msg)
            debug_info['parsing_steps'].append({
                'step': 'text_extraction',
                'success': False,
                'error': error_msg
            })
            self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))
            return debug_info
        
        # Step 2: Text Segmentation  
        self.stdout.write("Step 2: Text Segmentation")
        try:
            start_time = time.time()
            segments = parser._segment_with_deepseek(text)
            segmentation_time = time.time() - start_time
            
            step_info = {
                'step': 'text_segmentation',
                'success': bool(segments),
                'time_taken': round(segmentation_time, 3),
                'segments_found': len(segments) if segments else 0,
                'segment_types': list(segments.keys()) if segments else []
            }
            
            debug_info['parsing_steps'].append(step_info)
            
            if verbose and segments:
                self.stdout.write(f"  ✓ Found {len(segments)} segments in {segmentation_time:.3f}s")
                for section, content in segments.items():
                    self.stdout.write(f"    - {section}: {len(content)} chars")
            elif not segments:
                self.stdout.write(self.style.WARNING("  ⚠ No segments extracted"))
                
        except Exception as e:
            error_msg = f"Segmentation error: {str(e)}"
            debug_info['errors'].append(error_msg)
            debug_info['parsing_steps'].append({
                'step': 'text_segmentation',
                'success': False,
                'error': error_msg
            })
            self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))
            
        # Step 3: Information Extraction
        self.stdout.write("Step 3: Information Extraction")
        try:
            start_time = time.time()
            
            # Test different extraction methods
            extracted_info = {}
            
            # Extract personal info
            personal_info = parser.extract_personal_info(text)
            extracted_info['personal_info'] = personal_info
            
            # Extract experience
            experience = parser.extract_experience(text, segments if segments else {})
            extracted_info['experience'] = experience
            
            # Extract education
            education = parser.extract_education(text)
            extracted_info['education'] = education
            
            # Extract skills
            skills = parser.extract_skills(text, segments if segments else {})
            extracted_info['skills'] = skills
            
            extraction_time = time.time() - start_time
            
            step_info = {
                'step': 'information_extraction',
                'success': True,
                'time_taken': round(extraction_time, 3),
                'sections_extracted': {
                    'personal_info': bool(personal_info),
                    'experience': len(experience) if experience else 0,
                    'education': len(education) if education else 0,
                    'skills': len(skills) if skills else 0
                }
            }
            
            debug_info['parsing_steps'].append(step_info)
            debug_info['final_result'] = extracted_info
            
            if verbose:
                self.stdout.write(f"  ✓ Information extracted in {extraction_time:.3f}s")
                for section, data in step_info['sections_extracted'].items():
                    self.stdout.write(f"    - {section}: {data}")
                    
        except Exception as e:
            error_msg = f"Information extraction error: {str(e)}"
            debug_info['errors'].append(error_msg)
            debug_info['parsing_steps'].append({
                'step': 'information_extraction',
                'success': False,
                'error': error_msg
            })
            self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))
            
        # Calculate total performance
        total_time = sum([
            step.get('time_taken', 0) 
            for step in debug_info['parsing_steps'] 
            if 'time_taken' in step
        ])
        debug_info['performance']['total_parsing_time'] = round(total_time, 3)
        
        return debug_info
        
    def detect_extraction_method(self, parser, file_path):
        """Detect which extraction method was used"""
        extension = os.path.splitext(file_path)[1].lower()
        
        if extension == '.pdf':
            if hasattr(parser, 'pdf2image_available') and parser.pdf2image_available:
                return 'pdf_with_ocr_fallback'
            else:
                return 'pdf_text_extraction'
        elif extension in ['.doc', '.docx']:
            if hasattr(parser, 'docx2python_available') and parser.docx2python_available:
                return 'docx2python'
            else:
                return 'python_docx'
        else:
            return 'unknown'
            
    def debug_analysis(self, debug_info, verbose):
        """Debug the analysis process"""
        self.stdout.write("Step 4: CV Analysis")
        
        try:
            start_time = time.time()
            
            service = DeepSeekService()
            
            # Create analysis prompt
            prompt = f"""
            Analyze this CV data and identify potential job roles:
            
            CV Data: {json.dumps(debug_info['final_result'], indent=2)}
            
            Provide analysis in JSON format with:
            {{
                "overall_score": (1-10),
                "potential_roles": {{
                    "best_matches": [list of suitable job roles],
                    "match_reasons": [brief reasons for each match]
                }},
                "key_skills_identified": [list of key skills],
                "experience_level": "entry/mid/senior/executive"
            }}
            """
            
            response = service.make_custom_request(prompt)
            analysis_time = time.time() - start_time
            
            analysis_info = {
                'step': 'cv_analysis',
                'success': 'error' not in response,
                'time_taken': round(analysis_time, 3),
                'response': response
            }
            
            debug_info['parsing_steps'].append(analysis_info)
            debug_info['performance']['analysis_time'] = round(analysis_time, 3)
            
            if 'error' not in response:
                if verbose:
                    self.stdout.write(f"  ✓ Analysis completed in {analysis_time:.3f}s")
                    if isinstance(response, dict):
                        roles = response.get('potential_roles', {}).get('best_matches', [])
                        if roles:
                            self.stdout.write(f"    Suggested roles: {', '.join(roles[:3])}")
            else:
                error_msg = f"Analysis error: {response.get('error', 'Unknown error')}"
                debug_info['errors'].append(error_msg)
                self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))
                
        except Exception as e:
            error_msg = f"Analysis exception: {str(e)}"
            debug_info['errors'].append(error_msg)
            debug_info['parsing_steps'].append({
                'step': 'cv_analysis',
                'success': False,
                'error': error_msg
            })
            self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))
            
        return debug_info
        
    def display_debug_results(self, debug_info):
        """Display comprehensive debug results"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DEBUG RESULTS SUMMARY")
        self.stdout.write("=" * 60)
        
        # File info
        file_info = debug_info['file_info']
        self.stdout.write(f"File: {file_info['filename']}")
        self.stdout.write(f"Size: {file_info['size_mb']} MB ({file_info['size_bytes']} bytes)")
        self.stdout.write(f"Type: {file_info['extension']}")
        
        # Performance summary
        if debug_info['performance']:
            self.stdout.write(f"\nPerformance:")
            perf = debug_info['performance']
            if 'total_parsing_time' in perf:
                self.stdout.write(f"  Parsing: {perf['total_parsing_time']}s")
            if 'analysis_time' in perf:
                self.stdout.write(f"  Analysis: {perf['analysis_time']}s")
                
        # Step results
        self.stdout.write(f"\nProcessing Steps:")
        for step in debug_info['parsing_steps']:
            status = "✓" if step['success'] else "✗"
            time_info = f" ({step['time_taken']}s)" if 'time_taken' in step else ""
            self.stdout.write(f"  {status} {step['step']}{time_info}")
            
            if not step['success'] and 'error' in step:
                self.stdout.write(f"    Error: {step['error']}")
                
        # Errors summary
        if debug_info['errors']:
            self.stdout.write(f"\nErrors Found ({len(debug_info['errors'])}):")
            for i, error in enumerate(debug_info['errors'], 1):
                self.stdout.write(f"  {i}. {error}")
        else:
            self.stdout.write(f"\n✓ No errors found!")
            
        # Final result preview
        if debug_info['final_result']:
            self.stdout.write(f"\nParsed Data Summary:")
            result = debug_info['final_result']
            
            if 'personal_info' in result:
                personal = result['personal_info']
                name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip()
                if name:
                    self.stdout.write(f"  Name: {name}")
                if personal.get('email'):
                    self.stdout.write(f"  Email: {personal['email']}")
                    
            if 'experience' in result and result['experience']:
                self.stdout.write(f"  Experience: {len(result['experience'])} jobs")
                
            if 'education' in result and result['education']:
                self.stdout.write(f"  Education: {len(result['education'])} entries")
                
            if 'skills' in result and result['skills']:
                self.stdout.write(f"  Skills: {len(result['skills'])} identified")
                
    def save_debug_output(self, file_path, debug_info):
        """Save debug output to file"""
        output_filename = f"debug_{os.path.basename(file_path)}.json"
        output_path = os.path.join(os.path.dirname(file_path), output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(debug_info, f, indent=2, default=str)
            
        self.stdout.write(f"\nDebug output saved to: {output_path}")
