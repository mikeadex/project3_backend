"""
WSGI config for ella_writer project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

# Add the project directory to the Python path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ella_writer.settings")

# Get the standard Django WSGI application
application = get_wsgi_application()

# Import and apply our CORS middleware
from cors_headers import CORSMiddleware
application = CORSMiddleware(application)

# Add a debug message to verify this code is running in production
if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production'):
    print("CORS headers middleware applied at WSGI level")
