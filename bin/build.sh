#!/bin/bash
set -e

echo "Starting build process..."

# Upgrade pip to latest
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies with careful handling for textract
echo "Installing dependencies..."
pip install -r <(grep -v "textract" requirements.txt)

# Install textract dependencies manually to avoid version specification issue
echo "Installing textract dependencies..."
pip install beautifulsoup4>=4.8.0 chardet>=3.0.4 docx2txt>=0.8 extract-msg==0.28.0 pdfminer.six>=20181108 python-pptx>=0.6.5 six>=1.12.0 SpeechRecognition>=3.8.1

# Install textract separately
echo "Installing textract..."
pip install textract==1.6.4

# Django setup
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"
