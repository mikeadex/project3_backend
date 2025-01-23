import os
import json
import torch
from transformers import (
    LayoutLMForTokenClassification,
    LayoutLMTokenizer,
    Trainer,
    TrainingArguments
)
from datasets import Dataset
import numpy as np
from typing import Dict, List

# Define label types for each CV section
LABEL_TYPES = {
    'PERSONAL_INFO': 0,
    'EDUCATION': 1,
    'EXPERIENCE': 2,
    'SKILLS': 3,
    'INTERESTS': 4,
    'PROFESSIONAL_SUMMARY': 5,
    'REFERENCES': 6,
    'CERTIFICATIONS': 7,
    'LANGUAGES': 8,
    'SOCIAL_MEDIA': 9,
    'ACHIEVEMENTS': 10,
    'PUBLICATIONS': 11,
    'PROJECTS': 12,
    'VOLUNTEER_WORK': 13,
    'OTHER': 14
}

def load_dataset(data_path: str) -> Dataset:
    """Load and preprocess training data"""
    with open(os.path.join(data_path, 'training_data.json'), 'r') as f:
        raw_data = json.load(f)
    
    # Convert to HuggingFace dataset
    features = []
    labels = []
    
    for item in raw_data:
        # Tokenize and encode text
        encoded = tokenizer(
            item['features']['text'],
            truncation=True,
            padding='max_length',
            max_length=512,
            return_tensors='pt'
        )
        
        # Create label encodings
        label_encoding = create_label_encoding(item['labels'])
        
        features.append({
            'input_ids': encoded['input_ids'],
            'attention_mask': encoded['attention_mask'],
            'token_type_ids': encoded['token_type_ids']
        })
        labels.append(label_encoding)
    
    return Dataset.from_dict({
        'input_ids': [f['input_ids'] for f in features],
        'attention_mask': [f['attention_mask'] for f in features],
        'token_type_ids': [f['token_type_ids'] for f in features],
        'labels': labels
    })

def create_label_encoding(labels: Dict) -> torch.Tensor:
    """
    Create token-level labels for named entity recognition
    
    Args:
        labels: Dictionary containing parsed CV sections
        
    Returns:
        torch.Tensor: Token-level labels for model training
    """
    # Initialize label sequence with OTHER
    label_sequence = torch.full((512,), LABEL_TYPES['OTHER'])
    current_position = 0
    
    # Helper function to add section labels
    def add_section_labels(text: str, label_type: int, start_pos: int) -> int:
        tokens = tokenizer.tokenize(text)
        end_pos = min(start_pos + len(tokens), 512)
        label_sequence[start_pos:end_pos] = label_type
        return end_pos
    
    # Add labels for each section
    if labels.get('professional_summary'):
        current_position = add_section_labels(
            labels['professional_summary'],
            LABEL_TYPES['PROFESSIONAL_SUMMARY'],
            current_position
        )
    
    # Personal info
    personal_info = labels.get('personal_info', {})
    for key, value in personal_info.items():
        if value:
            current_position = add_section_labels(
                str(value),
                LABEL_TYPES['PERSONAL_INFO'],
                current_position
            )
    
    # Education
    for edu in labels.get('education', []):
        for key, value in edu.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['EDUCATION'],
                    current_position
                )
    
    # Experience
    for exp in labels.get('experience', []):
        for key, value in exp.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['EXPERIENCE'],
                    current_position
                )
    
    # Skills
    for skill in labels.get('skills', []):
        current_position = add_section_labels(
            str(skill),
            LABEL_TYPES['SKILLS'],
            current_position
        )
    
    # Interests
    for interest in labels.get('interests', []):
        current_position = add_section_labels(
            str(interest),
            LABEL_TYPES['INTERESTS'],
            current_position
        )
    
    # References
    for ref in labels.get('references', []):
        for key, value in ref.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['REFERENCES'],
                    current_position
                )
    
    # Certifications
    for cert in labels.get('certifications', []):
        for key, value in cert.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['CERTIFICATIONS'],
                    current_position
                )
    
    # Languages
    for lang in labels.get('languages', []):
        for key, value in lang.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['LANGUAGES'],
                    current_position
                )
    
    # Social Media
    for social in labels.get('social_media', []):
        for key, value in social.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['SOCIAL_MEDIA'],
                    current_position
                )
    
    # Achievements
    for achievement in labels.get('achievements', []):
        current_position = add_section_labels(
            str(achievement),
            LABEL_TYPES['ACHIEVEMENTS'],
            current_position
        )
    
    # Publications
    for pub in labels.get('publications', []):
        for key, value in pub.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['PUBLICATIONS'],
                    current_position
                )
    
    # Projects
    for project in labels.get('projects', []):
        for key, value in project.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['PROJECTS'],
                    current_position
                )
    
    # Volunteer Work
    for work in labels.get('volunteer_work', []):
        for key, value in work.items():
            if value:
                current_position = add_section_labels(
                    str(value),
                    LABEL_TYPES['VOLUNTEER_WORK'],
                    current_position
                )
    
    return label_sequence

def compute_metrics(pred):
    """
    Compute evaluation metrics for model performance
    
    Args:
        pred: Prediction object from trainer
        
    Returns:
        Dict containing precision, recall, and F1 score for each label type
    """
    predictions = pred.predictions
    labels = pred.label_ids
    
    metrics = {}
    
    # Calculate metrics for each label type
    for label_name, label_id in LABEL_TYPES.items():
        # Get binary masks for this label
        pred_mask = (predictions == label_id)
        true_mask = (labels == label_id)
        
        # Calculate true positives, false positives, false negatives
        tp = (pred_mask & true_mask).sum()
        fp = (pred_mask & ~true_mask).sum()
        fn = (~pred_mask & true_mask).sum()
        
        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics.update({
            f'{label_name.lower()}_precision': precision,
            f'{label_name.lower()}_recall': recall,
            f'{label_name.lower()}_f1': f1
        })
    
    # Calculate macro averages
    metrics.update({
        'macro_precision': np.mean([metrics[f'{label_name.lower()}_precision'] for label_name in LABEL_TYPES]),
        'macro_recall': np.mean([metrics[f'{label_name.lower()}_recall'] for label_name in LABEL_TYPES]),
        'macro_f1': np.mean([metrics[f'{label_name.lower()}_f1'] for label_name in LABEL_TYPES])
    })
    
    return metrics

def main():
    # Load hyperparameters
    hyperparameters = {
        'epochs': int(os.environ.get('epochs', 10)),
        'train_batch_size': int(os.environ.get('train_batch_size', 32)),
        'model_name': os.environ.get('model_name', 'microsoft/layoutlm-base-uncased'),
        'learning_rate': float(os.environ.get('learning_rate', 5e-5))
    }
    
    # Initialize model and tokenizer
    model = LayoutLMForTokenClassification.from_pretrained(
        hyperparameters['model_name'],
        num_labels=len(LABEL_TYPES)
    )
    
    tokenizer = LayoutLMTokenizer.from_pretrained(
        hyperparameters['model_name']
    )
    
    # Load and prepare dataset
    train_dataset = load_dataset('/opt/ml/input/data/train')
    
    # Set up training arguments
    training_args = TrainingArguments(
        output_dir='/opt/ml/model',
        num_train_epochs=hyperparameters['epochs'],
        per_device_train_batch_size=hyperparameters['train_batch_size'],
        learning_rate=hyperparameters['learning_rate'],
        weight_decay=0.01,
        logging_dir='/opt/ml/output/logs',
        logging_steps=100,
        save_strategy='epoch',
        evaluation_strategy='epoch',
        load_best_model_at_end=True,
        metric_for_best_model='macro_f1'
    )
    
    # Initialize trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        compute_metrics=compute_metrics
    )
    
    # Start training
    trainer.train()
    
    # Save model
    trainer.save_model('/opt/ml/model')
    tokenizer.save_pretrained('/opt/ml/model')

if __name__ == '__main__':
    main()
