#!/bin/bash
set -e

echo "Starting custom build process..."

# Downgrade pip to a version that can handle the invalid dependency specification
echo "Setting up pip and build dependencies..."
python -m pip install pip==23.0.1
pip install wheel setuptools

# Install core numerical libraries first to ensure compatibility
echo "Installing numerical libraries first..."
pip install numpy==1.24.4

# Install dependencies in stages to better manage any issues
echo "Installing base Django and utility packages..."
grep -v -E 'numpy|thinc|spacy|nltk|llama|torch|transformers|accelerate|loralib' requirements-render.txt > requirements-base.txt
pip install -r requirements-base.txt

echo "Installing NLP dependencies carefully..."
pip install thinc==8.1.12
pip install nltk==3.8.1

# Install spaCy separately with specific compatible versions
echo "Installing spaCy with compatible versions..."
pip install spacy==3.5.2 spacy-legacy==3.0.12 spacy-loggers==1.0.5

echo "Installing LLM dependencies..."
pip install torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.31.0
pip install accelerate==0.27.2 loralib==0.1.2
pip install llama-recipes==0.0.1
pip install llama_cpp_python==0.2.23

# Try to download spaCy models, but continue if it fails
echo "Attempting to download spaCy models..."
python -m spacy download en_core_web_sm || echo "Could not download spaCy models, but continuing build..."

# Install NLTK models with error handling
echo "Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')" || echo "Could not download all NLTK data, but continuing build..."

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs

# Django setup
echo "Collecting static files..."
python manage.py collectstatic --noinput --no-post-process

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"
