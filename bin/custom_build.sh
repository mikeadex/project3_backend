#!/bin/bash
set -e

echo "Starting custom build process..."

# Downgrade pip to a version that can handle the invalid dependency specification
echo "Setting up pip and build dependencies..."
python -m pip install pip==23.0.1
pip install wheel setuptools

# Install dependencies in stages to better manage any issues
echo "Installing base Django and utility packages..."
grep -v -E 'spacy|nltk|llama|torch|transformers|accelerate|loralib' requirements-render.txt > requirements-base.txt
pip install -r requirements-base.txt

echo "Installing NLP dependencies..."
pip install spacy==3.5.2 spacy-legacy==3.0.12 spacy-loggers==1.0.5
pip install nltk==3.8.1

echo "Installing LLM dependencies..."
pip install torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.31.0
pip install accelerate==0.27.2 loralib==0.1.2
pip install llama-recipes==0.0.1
pip install llama_cpp_python==0.2.23

# Download spaCy models
echo "Downloading spaCy models..."
python -m spacy download en_core_web_sm

# Install NLTK models
echo "Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')"

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs

# Django setup
echo "Collecting static files..."
python manage.py collectstatic --noinput --no-post-process

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"
