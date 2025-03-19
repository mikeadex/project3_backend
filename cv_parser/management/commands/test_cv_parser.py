import os
import json
import time
import signal
from functools import wraps
from django.core.management.base import BaseCommand, CommandError
from cv_parser.parsers import DocumentParser, AdvancedDocumentParser
import logging
from datetime import datetime

# Setup logging
logger = logging.getLogger('cv_parser')

def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Parser operation timed out")

def with_timeout(seconds):
    """Decorator to add timeout to a function"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set the timeout handler
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Disable the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator

class Command(BaseCommand):
    help = 'Test CV parser with sample PDF/DOCX files'
    
    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to CV file or directory with CV files')
        parser.add_argument('--output', type=str, help='Output file path for results (JSON)')
        parser.add_argument('--verbose', action='store_true', help='Print detailed parsing results')
        parser.add_argument('--batch', action='store_true', help='Process all files in directory')
        parser.add_argument('--timeout', type=int, default=60, help='Parser timeout in seconds (default: 60)')
        parser.add_argument('--use-llm', action='store_true', help='Force the use of LLM-based parsing')
        parser.add_argument('--use-deepseek', action='store_true', help='Use DeepSeek for text segmentation')
    
    def handle(self, *args, **options):
        file_path = options['file_path']
        output_file = options.get('output')
        verbose = options.get('verbose', False)
        batch_mode = options.get('batch', False)
        timeout = options.get('timeout', 60)
        use_llm = options.get('use_llm', False)
        use_deepseek = options.get('use_deepseek', False)
        
        self.stdout.write(f"Testing CV parser with: {file_path}")
        if use_llm:
            self.stdout.write("Using LLM-based parsing (forced via command-line option)")
        self.stdout.write(f"Parser timeout set to {timeout} seconds")
        self.stdout.write("="*50)
        
        # Validate the file/directory exists
        if not os.path.exists(file_path):
            raise CommandError(f"File or directory not found: {file_path}")
        
        # Process file or directory
        if os.path.isdir(file_path) and batch_mode:
            self.process_directory(file_path, output_file, verbose, timeout, use_llm, use_deepseek)
        elif os.path.isfile(file_path):
            self.process_file(file_path, output_file, verbose, True, timeout, use_llm, use_deepseek)
        else:
            if os.path.isdir(file_path) and not batch_mode:
                self.stdout.write(self.style.WARNING(
                    f"{file_path} is a directory. Use --batch flag to process all files in it."
                ))
            else:
                self.stdout.write(self.style.ERROR(f"Invalid path: {file_path}"))
        
        self.stdout.write("="*50)
        
    def process_directory(self, directory_path, output_file=None, verbose=False, timeout=60, use_llm=False, use_deepseek=False):
        """Process all PDF and DOCX files in a directory."""
        self.stdout.write(f"Processing directory: {directory_path}")
        
        # Get all PDF and DOCX files
        files = []
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(('.pdf', '.docx')):
                files.append(filename)
        
        if not files:
            self.stdout.write(self.style.WARNING("No PDF or DOCX files found in directory."))
            return
        
        self.stdout.write(f"Found {len(files)} PDF/DOCX files to process.")
        
        # Create JSON output structure if needed
        results = {
            'directory': directory_path,
            'timestamp': datetime.now().isoformat(),
            'files_processed': len(files),
            'results': []
        }
        
        # Process each file
        success_count = 0
        for file_name in files:
            self.stdout.write("-"*50)
            file_path = os.path.join(directory_path, file_name)
            try:
                file_result = self.process_file(file_path, None, verbose, False, timeout, use_llm, use_deepseek)
                results['results'].append({
                    'file_name': file_name,
                    'success': True,
                    'data': file_result
                })
                success_count += 1
            except Exception as e:
                results['results'].append({
                    'file_name': file_name,
                    'success': False,
                    'error': str(e)
                })
                self.stdout.write(self.style.ERROR(f"Failed to process {file_name}: {e}"))
        
        # Save batch results if output file is specified
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f"Batch results saved to {output_file}"))
        
        self.stdout.write(f"Successfully processed {success_count} of {len(files)} files.")
    
    @with_timeout(60)  # Default timeout, will be overridden by the parameter
    def _parse_with_timeout(self, parser, file_path, extracted_text, timeout=60):
        """Parse document with timeout protection"""
        # We need to set the alarm directly here since we can't modify the decorator
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        try:
            result = parser.parse_document(file_path, text=extracted_text)
            signal.alarm(0)  # Disable the alarm
            return result
        except:
            signal.alarm(0)  # Ensure alarm is disabled even on exception
            raise
    
    def process_file(self, file_path, output_file=None, verbose=False, save_output=True, timeout=60, use_llm=False, use_deepseek=False):
        """Process a single file and parse its contents."""
        try:
            file_name = os.path.basename(file_path)
            self.stdout.write(f"Processing: {file_name}")
            
            # Parse document
            start_time = time.time()
            parser = AdvancedDocumentParser()
            
            # Set LLM usage if specified
            if use_llm:
                # Use the global os module instead of importing it again
                os.environ['USE_LLM_CV_PARSING'] = 'True'
            
            # Set DeepSeek usage if specified
            if use_deepseek:
                os.environ['USE_DEEPSEEK_SEGMENTATION'] = 'True'
            
            # Extract text first
            try:
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext == '.pdf':
                    extracted_text = parser.parse_pdf(file_path)
                elif file_ext in ['.docx', '.doc']:
                    extracted_text = parser.parse_docx(file_path)
                else:
                    self.stdout.write(self.style.ERROR(f"Unsupported file format: {file_ext}"))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error extracting text: {str(e)}"))
                return
            
            # Print a sample of the extracted text if verbose
            if verbose:
                text_sample = extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")
                self.stdout.write("\nExtracted Text Sample:")
                self.stdout.write("-" * 50)
                self.stdout.write(text_sample)
                self.stdout.write("-" * 50)
            
            self.stdout.write(f"Text extraction completed ({len(extracted_text)} characters)")
            
            # Now parse the document with the extracted text explicitly passed
            # Apply timeout to the parsing operation
            try:
                # Call the parsing function with the timeout parameter
                parsed_data = self._parse_with_timeout(parser, file_path, extracted_text, timeout)
            except TimeoutError:
                self.stdout.write(self.style.ERROR(f"Parsing timed out after {timeout} seconds"))
                # Return partially parsed data or empty structure
                parsed_data = {
                    'personal_info': {},
                    'professional_summary': 'Parsing timed out',
                    'education': [],
                    'experience': [],
                    'skills': [],
                    'certifications': [],
                    'languages': [],
                    'error': f'Parsing timed out after {timeout} seconds'
                }
            
            elapsed_time = time.time() - start_time
            
            # Count the number of extracted sections
            sections_with_data = 0
            section_counts = []
            
            for section, data in parsed_data.items():
                if section == 'personal_info' and any(data.values()):
                    sections_with_data += 1
                    section_counts.append(f"{section}: {len(data)} fields")
                elif isinstance(data, list) and data:
                    sections_with_data += 1
                    section_counts.append(f"{section}: {len(data)} items")
                elif isinstance(data, str) and data.strip():
                    sections_with_data += 1
                    section_counts.append(f"{section}: '{data[:30]}...'")
                else:
                    section_counts.append(f"{section}: 0 items")
            
            self.stdout.write(f"Parsing completed in {elapsed_time:.2f} seconds")
            self.stdout.write(f"Extracted {sections_with_data} sections: {', '.join([s.split(':')[0] for s in section_counts if not s.endswith('0 items') and not s.endswith('0 fields')])}")
            
            for section_info in section_counts:
                self.stdout.write(f"  - {section_info}")
            
            # Output detailed results to stdout
            if verbose:
                self.stdout.write("\nDetailed Parsing Results:")
                self.stdout.write("-" * 50)
                self.stdout.write(json.dumps(parsed_data, indent=2, default=str))
                self.stdout.write("-" * 50)
            
            # Save to file if requested
            if output_file and save_output:
                if not output_file.endswith('.json'):
                    output_file = f"{output_file}.json"
                with open(output_file, 'w') as f:
                    json.dump(parsed_data, f, indent=2, default=str)
                self.stdout.write(self.style.SUCCESS(f"Results saved to {output_file}"))
            
            return parsed_data
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing {file_path}: {str(e)}"))
            if verbose:
                import traceback
                self.stdout.write(traceback.format_exc()) 