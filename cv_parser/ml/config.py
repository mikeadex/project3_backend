import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AWS Configuration
AWS_CONFIG = {
    'region': os.getenv('AWS_REGION', 'us-east-1'),
    'role_arn': os.getenv('AWS_SAGEMAKER_ROLE_ARN'),
    'bucket_name': os.getenv('AWS_S3_BUCKET'),
    'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
    'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY')
}

# SageMaker Configuration
SAGEMAKER_CONFIG = {
    'model_name': 'cv-parser',
    'instance_type': 'ml.p3.2xlarge',  # GPU instance for training
    'instance_count': 1,
    'output_path': 'models/cv-parser',
    'training_data_path': 'data/training'
}

# Model Configuration
MODEL_CONFIG = {
    'batch_size': 32,
    'epochs': 10,
    'learning_rate': 5e-5,
    'max_length': 512,
    'model_name': 'microsoft/layoutlm-base-uncased'
}
