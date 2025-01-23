import os
import json
import boto3
from typing import List, Dict
from django.core.management.base import BaseCommand
from cv_parser.models import CVDocument
from .config import AWS_CONFIG, SAGEMAKER_CONFIG

class DataPreparation:
    def __init__(self):
        """Initialize AWS clients"""
        # Set up AWS credentials
        self.s3_client = boto3.client(
            's3',
            region_name=AWS_CONFIG['region'],
            aws_access_key_id=AWS_CONFIG['access_key_id'],
            aws_secret_access_key=AWS_CONFIG['secret_access_key']
        )
        
        self.bucket_name = AWS_CONFIG['bucket_name']
        
    def prepare_training_data(self) -> List[Dict]:
        """
        Prepare training data from CVDocument models
        
        Returns:
            List[Dict]: List of prepared training examples
        """
        # Get all CV documents marked as training data
        cv_documents = CVDocument.objects.filter(
            is_training_data=True,
            parsing_status='completed'
        ).select_related('user')
        
        training_data = []
        for doc in cv_documents:
            if not doc.original_text or not doc.parsed_data:
                continue
                
            # Create training example
            example = {
                'features': {
                    'text': doc.original_text,
                    'document_type': doc.document_type
                },
                'labels': {
                    'personal_info': doc.parsed_data.get('personal_info', {}),
                    'education': doc.parsed_data.get('education', []),
                    'experience': doc.parsed_data.get('experience', []),
                    'skills': doc.parsed_data.get('skills', []),
                    'interests': doc.parsed_data.get('interests', []),
                    'professional_summary': doc.parsed_data.get('professional_summary', ''),
                    'references': doc.parsed_data.get('references', []),
                    'certifications': doc.parsed_data.get('certifications', []),
                    'languages': doc.parsed_data.get('languages', []),
                    'social_media': doc.parsed_data.get('social_media', []),
                    'achievements': doc.parsed_data.get('achievements', []),
                    'publications': doc.parsed_data.get('publications', []),
                    'projects': doc.parsed_data.get('projects', []),
                    'volunteer_work': doc.parsed_data.get('volunteer_work', [])
                }
            }
            
            training_data.append(example)
            
        return training_data
    
    def upload_to_s3(self, training_data: List[Dict]) -> str:
        """
        Upload training data to S3
        
        Args:
            training_data: List of training examples
            
        Returns:
            str: S3 URI of uploaded data
        """
        # Create training data file
        training_file = 'training_data.json'
        with open(training_file, 'w') as f:
            json.dump(training_data, f)
        
        # Upload to S3
        s3_key = f"{SAGEMAKER_CONFIG['training_data_path']}/training_data.json"
        self.s3_client.upload_file(
            training_file,
            self.bucket_name,
            s3_key
        )
        
        # Clean up local file
        os.remove(training_file)
        
        return f"s3://{self.bucket_name}/{s3_key}"

class Command(BaseCommand):
    help = 'Prepare and upload training data to S3'
    
    def handle(self, *args, **options):
        try:
            data_prep = DataPreparation()
            
            # Prepare training data
            self.stdout.write("Preparing training data...")
            training_data = data_prep.prepare_training_data()
            
            if not training_data:
                self.stdout.write(self.style.ERROR("No training data found!"))
                return
                
            self.stdout.write(f"Found {len(training_data)} training examples")
            
            # Upload to S3
            self.stdout.write("Uploading to S3...")
            s3_uri = data_prep.upload_to_s3(training_data)
            
            self.stdout.write(self.style.SUCCESS(
                f"Successfully uploaded training data to {s3_uri}"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
