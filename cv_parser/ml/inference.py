import boto3
import json
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class CVParserPredictor:
    """
    Handles inference using trained SageMaker models
    """
    
    def __init__(self, endpoint_name: str, region: str = "us-east-1"):
        """
        Initialize predictor with SageMaker endpoint
        
        Args:
            endpoint_name: Name of deployed SageMaker endpoint
            region: AWS region
        """
        self.endpoint_name = endpoint_name
        self.runtime = boto3.client('sagemaker-runtime', region_name=region)
        
    def predict(self, text: str, document_type: str) -> Dict[str, Any]:
        """
        Extract information from CV using trained model
        
        Args:
            text: Raw text from CV
            document_type: Type of document (pdf, docx, etc.)
            
        Returns:
            Dict containing parsed CV information
        """
        # Prepare input
        input_data = {
            'text': text,
            'document_type': document_type
        }
        
        try:
            # Call SageMaker endpoint
            response = self.runtime.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType='application/json',
                Body=json.dumps(input_data)
            )
            
            # Parse response
            result = json.loads(response['Body'].read().decode())
            
            return {
                'personal_info': result.get('personal_info', {}),
                'education': result.get('education', []),
                'experience': result.get('experience', []),
                'skills': result.get('skills', []),
                'interests': result.get('interests', []),
                'professional_summary': result.get('professional_summary', ''),
                'references': result.get('references', []),
                'certifications': result.get('certifications', []),
                'languages': result.get('languages', []),
                'social_media': result.get('social_media', []),
                'achievements': result.get('achievements', []),
                'publications': result.get('publications', []),
                'projects': result.get('projects', []),
                'volunteer_work': result.get('volunteer_work', []),
                'confidence_score': result.get('confidence_score', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error during prediction: {str(e)}")
            raise
