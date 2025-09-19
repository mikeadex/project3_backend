#!/usr/bin/env bash
# Render build script for Django backend

set -e  # Exit on any error

echo "🔧 Starting build process..."

# Upgrade pip first
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install numpy first to avoid binary incompatibility
echo "🔢 Installing numpy..."
pip install numpy==1.24.4

# Install core dependencies
echo "📚 Installing requirements..."
pip install -r requirements.txt

# Download spacy model
echo "🧠 Downloading spaCy model..."
python -m spacy download en_core_web_sm

# Collect static files
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations
echo "🗄️ Running database migrations..."
python manage.py migrate

echo "✅ Build completed successfully!"
