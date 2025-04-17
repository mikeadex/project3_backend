#!/bin/bash
set -e

echo "Starting custom build process..."

# Upgrade pip to latest
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Filter requirements to remove any textract-related lines
echo "Filtering requirements..."
grep -v "textract" requirements.txt > requirements_filtered.txt

# Add pip constraints to block textract from being installed as a dependency
echo "textract<0 # This blocks textract from being installed at all" > constraints.txt

# Install with constraints
echo "Installing requirements..."
pip install -r requirements_filtered.txt -c constraints.txt

# Django setup
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"
