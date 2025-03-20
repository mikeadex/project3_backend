#!/bin/bash

# Start Gunicorn process
exec gunicorn ella_writer.wsgi:application --bind 0.0.0.0:$PORT
