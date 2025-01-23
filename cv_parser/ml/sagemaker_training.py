import boto3
import sagemaker
from sagemaker.huggingface import HuggingFace
from sagemaker.processing import ProcessingInput, ProcessingOutput
from typing import Dict, List, Optional
import logging
import os
import json

logger = logging.getLogger(__name__)

class CVParserTrainer:
    """
    Handles training of CV parsing models using AWS SageMaker
    """
    
    def __init__(self, 
                role_arn: str,
                bucket_name: str,
                model_name: str = "cv-parser",
                region: str = "us-east-1"):
        """
        Initialize the trainer with AWS credentials and configuration
        
        Args:
            role_arn: AWS IAM role ARN with SageMaker permissions
            bucket_name: S3 bucket for storing training data and models
            model_name: Name for the trained model
            region: AWS region for SageMaker
        """
        self.role_arn = role_arn
        self.bucket_name = bucket_name
        self.model_name = model_name
        self.region = region
        
        # Initialize AWS clients
        self.sagemaker_session = sagemaker.Session()
        self.s3_client = boto3.client('s3')
        
    def prepare_training_data(self, 
                            cv_documents: List[Dict],
                            output_path: str) -> str:
        """
        Prepare and upload training data to S3
        
        Args:
            cv_documents: List of CV documents with parsed data
            output_path: S3 path for storing prepared data
            
        Returns:
            str: S3 URI of prepared training data
        """
        # Convert CV documents to training format
        training_data = []
        for doc in cv_documents:
            # Extract features and labels
            features = {
                'text': doc['original_text'],
                'document_type': doc['document_type']
            }
            
            labels = {
                'personal_info': doc['parsed_data']['personal_info'],
                'education': doc['parsed_data']['education'],
                'experience': doc['parsed_data']['experience'],
                'skills': doc['parsed_data']['skills'],
                'interests': doc['parsed_data'].get('interests', []),
                'professional_summary': doc['parsed_data'].get('professional_summary', ''),
                'references': doc['parsed_data'].get('references', []),
                'certifications': doc['parsed_data'].get('certifications', []),
                'languages': doc['parsed_data'].get('languages', []),
                'social_media': doc['parsed_data'].get('social_media', []),
                'achievements': doc['parsed_data'].get('achievements', []),
                'publications': doc['parsed_data'].get('publications', []),
                'projects': doc['parsed_data'].get('projects', []),
                'volunteer_work': doc['parsed_data'].get('volunteer_work', [])
            }
            
            training_data.append({
                'features': features,
                'labels': labels
            })
            
        # Upload to S3
        s3_uri = f's3://{self.bucket_name}/{output_path}'
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=f'{output_path}/training_data.json',
            Body=json.dumps(training_data)
        )
        
        return s3_uri
        
    def train_model(self,
                   training_data_uri: str,
                   hyperparameters: Optional[Dict] = None) -> str:
        """
        Train the CV parsing model using SageMaker
        
        Args:
            training_data_uri: S3 URI of training data
            hyperparameters: Optional model hyperparameters
            
        Returns:
            str: Model artifact URI
        """
        if hyperparameters is None:
            hyperparameters = {
                'epochs': 10,
                'train_batch_size': 32,
                'model_name': 'microsoft/layoutlm-base-uncased',
                'learning_rate': 5e-5
            }
            
        # Create HuggingFace estimator
        huggingface_estimator = HuggingFace(
            entry_point='train.py',
            source_dir='./scripts',
            instance_type='ml.p3.2xlarge',
            instance_count=1,
            role=self.role_arn,
            transformers_version='4.26',
            pytorch_version='1.13',
            py_version='py39',
            hyperparameters=hyperparameters
        )
        
        # Start training job
        huggingface_estimator.fit({
            'train': training_data_uri
        })
        
        return huggingface_estimator.model_data
        
    def deploy_model(self, model_uri: str) -> str:
        """
        Deploy trained model to SageMaker endpoint
        
        Args:
            model_uri: S3 URI of trained model artifacts
            
        Returns:
            str: Endpoint name
        """
        # Create model in SageMaker
        predictor = huggingface_estimator.deploy(
            initial_instance_count=1,
            instance_type='ml.t2.medium',
            endpoint_name=f'{self.model_name}-endpoint'
        )
        
        return predictor.endpoint_name
