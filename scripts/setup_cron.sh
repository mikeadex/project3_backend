#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get the project root directory
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Make sure the job scraping script is executable
chmod +x "$SCRIPT_DIR/schedule_job_scraping.sh"
echo "Made job scraping script executable."

# Create a temporary file for the crontab
TEMP_CRONTAB=$(mktemp)

# Export current crontab to the temporary file
crontab -l > "$TEMP_CRONTAB" 2>/dev/null || echo "# New crontab" > "$TEMP_CRONTAB"

# Check if the job is already in crontab
if grep -q "schedule_job_scraping.sh" "$TEMP_CRONTAB"; then
    echo "Job scraping cron job already exists."
else
    # Add the new cron job to run at 2 AM every day
    echo "# Job scraping every day at 2 AM" >> "$TEMP_CRONTAB"
    echo "0 2 * * * $SCRIPT_DIR/schedule_job_scraping.sh" >> "$TEMP_CRONTAB"
    
    # Install the new crontab
    crontab "$TEMP_CRONTAB"
    echo "Job scraping cron job installed. It will run daily at 2 AM."
fi

# Clean up
rm "$TEMP_CRONTAB"

echo ""
echo "To customize the job scraping, you can set environment variables before the cron job:"
echo "For example, to set location and email:"
echo "0 2 * * * ADMIN_EMAIL=your@email.com LOCATION=\"London\" $SCRIPT_DIR/schedule_job_scraping.sh"
echo ""
echo "Available environment variables:"
echo "- ADMIN_EMAIL: Email address for notifications (default: admin@example.com)"
echo "- LOCATION: Location to search for jobs (default: empty for nationwide)"
echo "- DAYS: Number of days to scrape (default: 1)"
echo "- FORCE: Whether to force run even if recent (true/false, default: false)"
echo ""
echo "To edit the crontab manually, run: crontab -e" 