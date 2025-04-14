#!/bin/bash

# Start Gunicorn process with environment variables for timeout
exec gunicorn ella_writer.wsgi:application --bind 0.0.0.0:$PORT --timeout 120 --workers 3 --threads 3 --worker-class=gthread
