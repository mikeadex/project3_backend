#!/bin/bash
set -e

echo "🔧 Starting custom build process for Ella Backend..."

# Upgrade pip to latest stable version
echo "📦 Setting up pip and build dependencies..."
python -m pip install --upgrade pip
pip install wheel setuptools

# CRITICAL: Install numpy first to avoid binary incompatibility issues
echo "🔢 Installing numpy first (critical for spaCy compatibility)..."
pip install numpy==1.24.4

# Install thinc before spaCy to ensure compatibility
echo "🧠 Installing thinc with compatible numpy..."
pip install thinc==8.1.12

# Install all remaining dependencies
echo "📚 Installing all dependencies from requirements.txt..."
pip install -r requirements.txt

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
