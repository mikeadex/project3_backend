#!/bin/bash
set -e

echo "Starting custom build process..."

# Downgrade pip to a version that can handle the invalid dependency specification
echo "Downgrading pip to a version that can handle invalid metadata..."
python -m pip install pip==23.0.1

# Install from minimal requirements file
echo "Installing from minimal requirements file..."
pip install -r requirements-render.txt

# Django setup
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"
