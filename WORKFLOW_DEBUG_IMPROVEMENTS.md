# Workflow Debug Improvements

## Issue
The GitHub Actions cron job ran at the expected time but completed very quickly (1-5 seconds per step), suggesting it didn't actually extract any jobs.

## Root Cause Analysis
The workflow was running silently without proper error handling or verbose output, making it impossible to diagnose failures.

## Solutions Implemented

### 1. **Enhanced Error Handling in Workflow** ✅
Updated `.github/workflows/daily-job-scraper.yml`:

```yaml
- name: 🔍 Run Job Scrapers
  run: |
    echo "🚀 Starting job scrapers..."
    set -e  # Exit on error
    python manage.py run_all_scrapers --days 1 --debug 2>&1 | tee scraper_output.log
    EXIT_CODE=${PIPESTATUS[0]}
    echo "📝 Scraper exit code: $EXIT_CODE"
    if [ $EXIT_CODE -ne 0 ]; then
      echo "❌ Job scraping failed with exit code $EXIT_CODE"
      cat scraper_output.log
      exit $EXIT_CODE
    fi
    echo "✅ Job scraping completed successfully!"
```

**Benefits**:
- `set -e`: Exits immediately if any command fails
- `--debug`: Enables verbose output from all scrapers
- `2>&1 | tee`: Captures both stdout and stderr to log file
- `${PIPESTATUS[0]}`: Gets exit code even with pipe
- Displays full log on failure

### 2. **Log Artifact Upload** ✅
Added step to upload logs as artifacts:

```yaml
- name: 📤 Upload Scraper Logs
  if: always()  # Run even if previous step fails
  uses: actions/upload-artifact@v3
  with:
    name: scraper-logs
    path: scraper_output.log
    retention-days: 7
```

**Benefits**:
- Logs available for 7 days after each run
- Can download and analyze even successful runs
- `if: always()` ensures logs uploaded even on failure

### 3. **Debug Flag Support in Orchestrator** ✅
Updated `jobstract/management/commands/run_all_scrapers.py`:

**Added debug argument**:
```python
parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug mode for verbose output",
)
```

**Pass debug to all scrapers**:
```python
{
    "name": "Reed Scraper",
    "command": "reed_scraper",
    "args": {
        "location": location,
        "distance": 10,
        "debug": debug,  # ✅ Now dynamic
    },
},
{
    "name": "Adzuna Scraper",
    "command": "adzuna_scraper",
    "args": {
        "location": location if location else "UK",
        "days": days,
        "results": 50,
        "force": force,
        "debug": debug,  # ✅ Now dynamic
    },
},
{
    "name": "DWP Scraper",
    "command": "dwp_scraper",
    "args": {
        "location": location,
        "distance": 20,
        "debug": debug,  # ✅ Now dynamic
    },
},
```

## How to Check Logs After Next Run

### Method 1: GitHub Actions Web UI
1. Go to: https://github.com/mikeadex/project3_backend/actions
2. Click on the latest "Daily Job Scraper" run
3. Expand each step to see detailed output
4. Look for the "📤 Upload Scraper Logs" step
5. Download the `scraper-logs` artifact (zip file)
6. Extract and read `scraper_output.log`

### Method 2: Via API (if you have GitHub CLI)
```bash
# List recent runs
gh run list --workflow=daily-job-scraper.yml --limit 5

# View specific run
gh run view <RUN_ID>

# Download logs
gh run download <RUN_ID> --name scraper-logs
```

## Expected Debug Output

With `--debug` flag, you should see:

**Reed Scraper**:
```
----- Running Reed Scraper -----
Starting Reed job fetching...
Fetching jobs with params: {'resultsToTake': 100}
Response status: 200
Found 112428 total jobs, processing 100 results
Created new job: Software Developer at TechCorp
Created new job: Marketing Manager at StartupCo
...
✓ Reed Scraper completed successfully
```

**Adzuna Scraper**:
```
----- Running Adzuna Scraper -----
📡 Fetching jobs from Adzuna API...
📋 Found 185563 total jobs, processing 50 results
✅ Created new job: Data Analyst at BigCorp
✅ Created new job: Product Manager at Scale Inc
...
✓ Adzuna Scraper completed successfully
```

**DWP Scraper**:
```
----- Running DWP Scraper -----
Starting DWP Civil Service job fetching...
Found 2500 total jobs, processing 50 results
Created new job: Policy Advisor at Home Office
Created new job: Admin Officer at HMRC
...
✓ DWP Scraper completed successfully
```

**Final Summary**:
```
📊 Jobs added today: 200
📊 Total jobs: 200
```

## Troubleshooting

### If Workflow Still Fails Fast

**Check for these common issues**:

1. **Database Connection**: Verify `DATABASE_URL` secret is correct
   ```bash
   # In workflow logs, look for:
   ✅ DATABASE_URL is set (length: 150+ characters)
   ```

2. **API Keys Missing**: Ensure all secrets are set
   ```bash
   ✅ REED_API_KEY is set
   ✅ ADZUNA_APP_ID is set
   ✅ ADZUNA_APP_KEY is set
   ```

3. **Python Dependencies**: Check if pip install succeeded
   ```bash
   # Should see in "📦 Install dependencies" step:
   Successfully installed django psycopg2-binary requests beautifulsoup4...
   ```

4. **Network Issues**: API endpoints might be down
   - Reed API: https://www.reed.co.uk/api
   - Adzuna API: https://api.adzuna.com/status
   - DWP: https://findajob.dwp.gov.uk

### If No Jobs Created Despite Success

Check the log file for:

```bash
# Look for "skipped" messages
⏭️ Job already exists: <job_title>

# Or database warnings
WARNING: Unable to connect to database
ERROR: Duplicate key violation
```

**Possible causes**:
- Jobs already exist (check `--force` flag)
- Database full or locked
- Duplicate detection too aggressive

## Testing Changes Manually

You can test the workflow manually before waiting for cron:

1. Go to: https://github.com/mikeadex/project3_backend/actions
2. Click "Daily Job Scraper"
3. Click "Run workflow" dropdown
4. Select branch: `new-main`
5. Click green "Run workflow" button
6. Watch it run in real-time
7. Download logs after completion

## Next Steps

1. **Wait for next cron run** (tomorrow at 2 AM UTC)
2. **Check workflow logs** immediately after
3. **Download artifact logs** for detailed analysis
4. **Verify job counts** in database:
   ```python
   from jobstract.models import Opportunity
   from django.utils import timezone
   
   today = timezone.now().date()
   today_jobs = Opportunity.objects.filter(created_at__date=today).count()
   print(f"Jobs added today: {today_jobs}")  # Should be ~200
   ```

## Commits

All improvements pushed in 2 commits:

1. **ff81d38**: "feat: Add debug logging and error handling to scraper workflow"
   - Enhanced workflow error handling
   - Added log artifact upload
   - Better error messages

2. **2a15abb**: "feat: Add --debug flag support to run_all_scrapers command"
   - Added --debug argument
   - Pass debug to all scrapers
   - Updated logging

## Success Criteria

The workflow should now:
- ✅ Run for 2-5 minutes (not 1-5 seconds)
- ✅ Show verbose output from all scrapers
- ✅ Create ~200 jobs daily (100 Reed + 50 Adzuna + 50 DWP)
- ✅ Upload detailed logs for analysis
- ✅ Report clear errors if anything fails

---

**Status**: ✅ All improvements pushed and deployed  
**Next Cron Run**: Tomorrow at 2:00 AM UTC  
**Expected Duration**: 2-5 minutes  
**Expected Jobs**: ~200 new jobs
