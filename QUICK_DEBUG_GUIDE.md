# Quick Guide: Check Why Scrapers Didn't Extract Jobs

## The Problem

Your cron job ran fast (1-5 seconds) but didn't extract any jobs. This means it likely failed silently.

## What I Fixed

### 1. Added `--debug` Flag ✅

- Workflow now uses: `python manage.py run_all_scrapers --days 1 --debug`
- Shows verbose output from all scrapers
- Logs every API call, response, and job created

### 2. Added Error Handling ✅

- Workflow now exits on first error (`set -e`)
- Captures exit codes
- Displays full error messages
- Saves all output to `scraper_output.log`

### 3. Upload Logs as Artifacts ✅

- Every run uploads logs (even if it fails)
- Logs kept for 7 days
- Can download and analyze

## How to Check Next Run

### Option 1: GitHub Web UI (Easiest)

1. **Go to**: https://github.com/mikeadex/project3_backend/actions
2. **Wait for next run** (tomorrow at 2 AM UTC) OR **trigger manually**:
   - Click "Daily Job Scraper"
   - Click "Run workflow" dropdown
   - Click green "Run workflow" button
3. **Click on the run** when it appears
4. **Expand each step** to see output:
   - Look for "🔍 Run Job Scrapers" step
   - Should show verbose output now
5. **Download logs**:
   - Scroll to bottom
   - Click "scraper-logs" artifact
   - Download zip file
   - Extract and read `scraper_output.log`

### Option 2: Check Database

After workflow runs, check if jobs were created:

```python
# In Django shell or Python script
from jobstract.models import Opportunity
from django.utils import timezone

today = timezone.now().date()
today_jobs = Opportunity.objects.filter(created_at__date=today).count()
total_jobs = Opportunity.objects.count()

print(f"Jobs added today: {today_jobs}")  # Should be ~200
print(f"Total jobs: {total_jobs}")
```

## What You Should See Now

### Before (Broken - Fast Run):

```
✅ ADZUNA_APP_KEY is set                     1s
🔍 Run Job Scrapers                          1s  ← TOO FAST!
📊 Summary Statistics                        0s
📊 Jobs added today: 0                           ← NO JOBS!
```

### After (Fixed - Normal Run):

```
✅ ADZUNA_APP_KEY is set                     2s
🔍 Run Job Scrapers                         180s  ← NORMAL!
📊 Summary Statistics                        4s
📊 Jobs added today: 200                         ← JOBS CREATED!
```

## Expected Verbose Output

With `--debug`, you'll see:

```bash
===== Starting all job scrapers at 2025-10-11 02:00:05 =====

----- Running Reed Scraper -----
Starting Reed job fetching...
Fetching jobs with params: {'resultsToTake': 100}
Response status: 200
Found 112428 total jobs, processing 100 results
Created new job: Software Developer - £50,000 per year
Created new job: Marketing Manager - £45,000 per year
Created new job: Data Analyst - £40,000 per year
... (97 more jobs)
✓ Reed Scraper completed successfully

----- Running Adzuna Scraper -----
📡 Fetching jobs from Adzuna API...
📋 Found 185563 total jobs, processing 50 results
✅ Created new job: Product Manager at Scale Inc
✅ Created new job: DevOps Engineer at TechCorp
... (48 more jobs)
✓ Adzuna Scraper completed successfully

----- Running DWP Scraper -----
Starting DWP Civil Service job fetching...
Found 2500 total jobs, processing 50 results
Created new job: Policy Advisor at Home Office
Created new job: Admin Officer at HMRC
... (48 more jobs)
✓ DWP Scraper completed successfully

📝 Scraper exit code: 0
✅ Job scraping completed successfully!

📊 Jobs added today: 200
📊 Total jobs: 6200
```

## Common Issues & Solutions

### Issue 1: Still Runs Fast (1-5 seconds)

**Likely causes**:

- Database connection failed
- API keys invalid
- Python dependencies missing

**Check**:

1. Download log artifact
2. Look for error messages:
   ```
   ERROR: Unable to connect to database
   ERROR: Invalid API key
   ModuleNotFoundError: No module named 'requests'
   ```

### Issue 2: Runs Long But No Jobs Created

**Likely causes**:

- Jobs already exist (duplicate detection)
- API rate limits hit
- Search criteria too restrictive

**Check**:

1. Look for "skipped" messages in logs:
   ```
   ⏭️ Job already exists: Software Developer at TechCorp
   ```
2. Use `--force` flag to bypass duplicate checks

### Issue 3: Only Some Scrapers Work

**Example**: Reed works, Adzuna fails

**Check**:

1. Look for API-specific errors:
   ```
   ----- Running Adzuna Scraper -----
   ERROR: Invalid app_id or app_key
   ```
2. Verify GitHub Secrets:
   - `ADZUNA_APP_ID` = `7d62aca8`
   - `ADZUNA_APP_KEY` = `94fa100047aa47a28af52caf14fc07f4`

## Manual Test Right Now

Don't wait for tomorrow! Test immediately:

1. **Go to**: https://github.com/mikeadex/project3_backend/actions
2. **Click**: "Daily Job Scraper"
3. **Click**: "Run workflow" (dropdown)
4. **Select**: Branch `new-main`
5. **Click**: Green "Run workflow" button
6. **Watch**: Should take 2-5 minutes
7. **Check**: Download logs and verify jobs created

## Success Checklist

After next run, you should have:

- ✅ Workflow duration: 2-5 minutes (not 1-5 seconds)
- ✅ Jobs created: ~200 (Reed 100 + Adzuna 50 + DWP 50)
- ✅ Exit code: 0 (success)
- ✅ Logs available: Download `scraper-logs` artifact
- ✅ Database updated: Check with Django shell

## Need Help?

If it still doesn't work:

1. **Download the log artifact** from GitHub Actions
2. **Look for the first ERROR message**
3. **Share the error** - I can help diagnose

Common error patterns:

```bash
# Database issue
django.db.utils.OperationalError: FATAL: password authentication failed

# API issue
requests.exceptions.HTTPError: 401 Client Error: Unauthorized

# Network issue
requests.exceptions.ConnectionError: Max retries exceeded

# Dependency issue
ModuleNotFoundError: No module named 'beautifulsoup4'
```

---

**All Changes Deployed**: ✅ 3 commits pushed  
**Next Cron Run**: Tomorrow at 2:00 AM UTC  
**OR Test Now**: Trigger manual run from Actions tab  
**Expected Jobs**: ~200 new jobs per day
