import os
import boto3
import sagemaker
from sagemaker.huggingface import HuggingFace
from django.core.management.base import BaseCommand
from .config import AWS_CONFIG, SAGEMAKER_CONFIG, MODEL_CONFIG

class ModelTraining:
    def __init__(self):
        """Initialize SageMaker session and clients"""
        # Set up AWS session
        boto_session = boto3.Session(
            region_name=AWS_CONFIG['region'],
            aws_access_key_id=AWS_CONFIG['access_key_id'],
            aws_secret_access_key=AWS_CONFIG['secret_access_key']
        )
        
        # Initialize SageMaker session
        sagemaker_session = sagemaker.Session(boto_session=boto_session)
        
        self.role = AWS_CONFIG['role_arn']
        self.bucket = AWS_CONFIG['bucket_name']
        self.session = sagemaker_session
        
    def train_model(self, training_data_uri: str) -> str:
        """
        Train model using SageMaker
        
        Args:
            training_data_uri: S3 URI of training data
            
        Returns:
            str: S3 URI of trained model artifacts
        """
        # Create HuggingFace estimator
        huggingface_estimator = HuggingFace(
            entry_point='train.py',
            source_dir='scripts',
            instance_type=SAGEMAKER_CONFIG['instance_type'],
            instance_count=SAGEMAKER_CONFIG['instance_count'],
            role=self.role,
            transformers_version='4.26',
            pytorch_version='1.13',
            py_version='py39',
            hyperparameters={
                'epochs': MODEL_CONFIG['epochs'],
                'train_batch_size': MODEL_CONFIG['batch_size'],
                'model_name': MODEL_CONFIG['model_name'],
                'learning_rate': MODEL_CONFIG['learning_rate']
            },
            output_path=f"s3://{self.bucket}/{SAGEMAKER_CONFIG['output_path']}"
        )
        
        # Start training job
        huggingface_estimator.fit({'train': training_data_uri})
        
        return huggingface_estimator.model_data
        
    def deploy_model(self, model_uri: str) -> str:
        """
        Deploy trained model to endpoint
        
        Args:
            model_uri: S3 URI of model artifacts
            
        Returns:
            str: Endpoint name
        """
        # Deploy model to endpoint
        predictor = huggingface_estimator.deploy(
            initial_instance_count=1,
            instance_type='ml.t2.medium',
            endpoint_name=f"{SAGEMAKER_CONFIG['model_name']}-endpoint"
        )
        
        return predictor.endpoint_name

class Command(BaseCommand):
    help = 'Train and deploy CV parser model on SageMaker'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--training-data-uri',
            type=str,
            help='S3 URI of training data'
        )
        
    def handle(self, *args, **options):
        try:
            training_data_uri = options['training_data_uri']
            if not training_data_uri:
                self.stdout.write(self.style.ERROR("Training data URI is required"))
                return
                
            trainer = ModelTraining()
            
            # Train model
            self.stdout.write("Starting model training...")
            model_uri = trainer.train_model(training_data_uri)
            self.stdout.write(self.style.SUCCESS(
                f"Model training completed. Model artifacts: {model_uri}"
            ))
            
            # Deploy model
            self.stdout.write("Deploying model...")
            endpoint_name = trainer.deploy_model(model_uri)
            self.stdout.write(self.style.SUCCESS(
                f"Model deployed to endpoint: {endpoint_name}"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
