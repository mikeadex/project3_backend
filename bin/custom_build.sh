#!/bin/bash
set -e

echo "Starting custom build process..."

# Downgrade pip to a version that can handle the invalid dependency specification
echo "Downgrading pip to a version that can handle invalid metadata..."
python -m pip install pip==23.0.1

# Install from minimal requirements file
echo "Installing from minimal requirements file..."
pip install -r requirements-render.txt

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
