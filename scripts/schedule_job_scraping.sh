#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get the project root directory (one level up from scripts)
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Create logs directory if it doesn't exist
LOGS_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOGS_DIR"

# Set log file with timestamp
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOGS_DIR/job_scraper_$TIMESTAMP.log"

# Function to send email notification
send_notification() {
    SUBJECT="$1"
    BODY="$2"
    
    # Check if mail command is available
    if command -v mail &> /dev/null; then
        echo "$BODY" | mail -s "$SUBJECT" "$ADMIN_EMAIL"
    else
        echo "Email notification not sent (mail command not available)"
        echo "Subject: $SUBJECT"
        echo "Body: $BODY"
    fi
}

# Configuration - edit these values
ADMIN_EMAIL=${ADMIN_EMAIL:-"admin@example.com"}  # Override by setting ADMIN_EMAIL env var
LOCATION=${LOCATION:-""}  # Default to empty for nationwide search
DAYS=${DAYS:-1}  # Default to 1 day
FORCE=${FORCE:-false}  # Default to not force

# Start logging
echo "=======================================" >> "$LOG_FILE"
echo "Starting Job Scraper at $(date)" >> "$LOG_FILE"
echo "=======================================" >> "$LOG_FILE"

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
    echo "Activated virtual environment" >> "$LOG_FILE"
fi

# Set the Python path to include the project root
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Change to the project root directory
cd "$PROJECT_ROOT"
echo "Changed to directory: $PROJECT_ROOT" >> "$LOG_FILE"

# Build command with options
CMD="python manage.py run_all_scrapers"

if [ "$FORCE" = true ]; then
    CMD="$CMD --force"
fi

if [ ! -z "$LOCATION" ]; then
    CMD="$CMD --location=$LOCATION"
fi

CMD="$CMD --days=$DAYS"

# Run the command and capture output
echo "Running command: $CMD" >> "$LOG_FILE"
OUTPUT=$($CMD 2>&1)
EXIT_CODE=$?

# Log the output
echo "$OUTPUT" >> "$LOG_FILE"
echo "Command exit code: $EXIT_CODE" >> "$LOG_FILE"

# Check if successful
if [ $EXIT_CODE -eq 0 ]; then
    SUCCESS_MESSAGE="Job scrapers ran successfully at $(date)"
    echo "$SUCCESS_MESSAGE" >> "$LOG_FILE"
    
    # Send success notification (uncomment to enable)
    # send_notification "Job Scrapers Success" "$SUCCESS_MESSAGE\n\nOutput:\n$OUTPUT"
else
    ERROR_MESSAGE="Job scrapers failed with exit code $EXIT_CODE at $(date)"
    echo "$ERROR_MESSAGE" >> "$LOG_FILE"
    
    # Send failure notification
    send_notification "ALERT: Job Scrapers Failed" "$ERROR_MESSAGE\n\nOutput:\n$OUTPUT"
fi

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
    echo "Deactivated virtual environment" >> "$LOG_FILE"
fi

# Log completion
echo "Job scraper script completed at $(date)" >> "$LOG_FILE"
echo "=======================================" >> "$LOG_FILE"

# Auto-cleanup old log files (keep last 30 days)
find "$LOGS_DIR" -name "job_scraper_*.log" -type f -mtime +30 -delete 