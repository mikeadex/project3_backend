#!/bin/bash

# Start Gunicorn process with config file
exec gunicorn ella_writer.wsgi:application -c /app/gunicorn.conf.py
