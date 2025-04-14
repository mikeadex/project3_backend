"""
Gunicorn configuration file for production settings
"""
import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker processes
workers = 3
worker_class = 'gthread'
threads = 3
timeout = 120  # Increased timeout to handle longer requests

# Server mechanics
preload_app = True
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Keep-alive settings
keepalive = 65

# Improve handling of large file uploads
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190 