# Job Scrapers Review & Automation Plan

**Date**: October 9, 2025  
**Status**: ⚠️ Ready for Automation Implementation

---

## 📋 Current State Analysis

### Existing Job Scrapers (4 Total)

#### 1. **Reed Scraper** (`reed_scraper.py`)

- **Source**: Reed.co.uk API
- **Status**: ✅ **Production Ready** - Uses official API
- **Authentication**: API Key (REED_API_KEY)
- **Features**:
  - UK-wide or location-specific search
  - Distance-based filtering (miles)
  - Keyword search support
  - Rate limiting: 100 results per request (API max)
  - Uses Cleaner utility for data normalization

**API Details**:

```python
Base URL: https://www.reed.co.uk/api/1.0/search
Auth: Basic (API_KEY, '')
Max Results: 100 per request
```

**Parameters**:

- `--location`: Search location (optional, UK-wide if omitted)
- `--distance`: Distance in miles (default: 10)
- `--keywords`: Search keywords (optional)
- `--debug`: Enable debug logging

#### 2. **DWP Scraper** (`dwp_scraper.py`)

- **Source**: Find a Job (DWP - Government)
- **Status**: ✅ **Production Ready** - Web scraping
- **Method**: BeautifulSoup + Requests
- **Features**:
  - UK government jobs portal
  - Location-based search with distance
  - UK cities validation (100+ cities)
  - 50 results per page
  - Smart location parsing

**Configuration**:

```python
Base URL: https://findajob.dwp.gov.uk/search
Results per page: 50
Default distance: 20km
```

**Parameters**:

- `--location`: Search location (optional)
- `--distance`: Distance in km (default: 20)
- `--debug`: Enable debug logging

#### 3. **Civil Service Scraper** (`cs_scraper.py`)

- **Source**: Civil Service Jobs
- **Status**: ⚠️ **Needs Review** - Selenium-based
- **Method**: Selenium + BeautifulSoup
- **Issues**:
  - Uses headless Chrome (requires ChromeDriver)
  - Hard-coded CSS selectors may break
  - No database integration visible in first 100 lines
  - May need infrastructure setup (Chrome/ChromeDriver in production)

**Infrastructure Requirements**:

```python
- ChromeDriver installed
- Chrome browser (headless mode)
- Selenium WebDriver
```

#### 4. **SME Scraper** (`scrape_jobs.py`)

- **Source**: SME website (service imported)
- **Status**: ✅ **Production Ready**
- **Method**: Custom SMEScraper service
- **Features**:
  - Date range scraping
  - Batch processing (100 jobs per batch)
  - Duplicate detection
  - Smart update/create logic
  - 24-hour cooldown (skips if recently run)

**Configuration**:

```python
Batch size: 100 jobs
Default scrape: Last 1 day
Cooldown: 24 hours (can force with --force)
```

**Parameters**:

- `--days`: Number of days to scrape (default: 1)
- `--force`: Override 24-hour cooldown

#### 5. **Master Orchestrator** (`run_all_scrapers.py`)

- **Status**: ✅ **Excellent Implementation**
- **Features**:
  - Sequential execution with error isolation
  - Transaction-based safety
  - Comprehensive logging
  - Detailed summary reports
  - Independent scraper failure handling

**Scrapers Orchestrated**:

1. SME Scraper (scrape_jobs)
2. Reed Scraper (reed_scraper)
3. DWP Scraper (dwp_scraper)

**Parameters**:

- `--force`: Force run all scrapers
- `--location`: Pass location to all scrapers
- `--days`: Number of days for SME scraper

---

## 🗄️ Database Schema

### Employer Model

```python
- employer_name: CharField(255)
- employer_website: URLField (optional)
- is_nonprofit: Boolean
- charity_number: CharField(20) (optional)
- created_at, updated_at: Auto timestamps
```

### Opportunity Model

```python
# Core Fields
- employer: ForeignKey(Employer)
- title: CharField(255)
- description: TextField
- location: CharField(255)
- opportunity_type: ('internship', 'job', 'volunteer')
- mode: ('on_site', 'remote', 'hybrid')
- time_commitment: ('full_time', 'part_time', 'flexible', etc.)
- experience_level: ('entry_level', 'junior', 'mid', 'senior', etc.)

# Compensation
- salary_range: CharField(100) (optional)
- expenses_paid: Boolean

# Skills & Dates
- skills_required: TextField
- skills_gained: TextField
- start_date, end_date: DateField (optional)
- date_posted: DateField (required)

# URLs
- application_url: URLField
- source: URLField

# Metadata
- created_at, updated_at: Auto timestamps
```

### JobApplication Model

```python
- user: ForeignKey(User)
- opportunity: ForeignKey(Opportunity)
- status: ('applied', 'screening', 'interview', etc.)
- applied_date: DateTime
- cv_used: ForeignKey('cv_writer.CvWriter') (optional)
- cover_letter: TextField (optional)
```

---

## ⚠️ Current Issues & Gaps

### 1. **No Automation** ❌

- All scrapers require manual execution
- No scheduled runs
- No cron jobs or Celery tasks configured

### 2. **Civil Service Scraper Concerns** ⚠️

- Selenium dependency (infrastructure overhead)
- May not work in production without Chrome/ChromeDriver
- No error handling visible
- Hard-coded selectors (fragile)

### 3. **Missing Features**

- No duplicate job detection across sources
- No data quality validation
- No scraper health monitoring
- No failure alerting
- No metrics/statistics tracking

### 4. **Configuration Management**

- Reed API key in .env (good ✅)
- Other scrapers have hard-coded configs
- No centralized scraper configuration

### 5. **Data Consistency**

- Different scrapers may parse locations differently
- Salary formats may vary
- No standardized job type mapping

---

## 🚀 Automation Strategy

### Option 1: **Celery + Redis** (Recommended for Production)

**Advantages**:

- ✅ Robust, battle-tested
- ✅ Better error handling
- ✅ Task retry mechanisms
- ✅ Real-time monitoring (Flower)
- ✅ Distributed execution
- ✅ Better for cloud deployment (Render, AWS)

**Implementation**:

```python
# Install dependencies
pip install celery redis flower

# Create celery.py in project root
# Create periodic tasks
# Configure Celery Beat for scheduling
```

**Estimated Setup Time**: 2-4 hours

### Option 2: **Django-Cron** (Simpler Alternative)

**Advantages**:

- ✅ Django-native
- ✅ Easier setup
- ✅ No additional services needed
- ✅ Good for simple periodic tasks

**Disadvantages**:

- ⚠️ Requires cron daemon running
- ⚠️ Less robust error handling
- ⚠️ Limited monitoring

**Implementation**:

```python
# Install django-cron
pip install django-cron

# Create cron jobs class
# Add to INSTALLED_APPS
# Run python manage.py runcrons
```

**Estimated Setup Time**: 1-2 hours

### Option 3: **System Cron** (Simple, Traditional)

**Advantages**:

- ✅ No dependencies
- ✅ OS-level reliability
- ✅ Simple to understand

**Disadvantages**:

- ⚠️ Manual server configuration
- ⚠️ No Django integration
- ⚠️ Harder to monitor

**Implementation**:

```bash
# Edit crontab
crontab -e

# Add daily scraper job at 2 AM
0 2 * * * cd /path/to/ella/Ella-backend && python manage.py run_all_scrapers
```

**Estimated Setup Time**: 30 minutes

---

## 📅 Recommended Automation Plan

### **Phase 1: Implement Celery + Redis** (Week 1)

#### Day 1-2: Setup Infrastructure

1. Install Celery, Redis, Flower
2. Configure Celery in Django settings
3. Create `celery.py` in project root
4. Setup Redis (local + production)
5. Test basic task execution

#### Day 3-4: Create Job Scraper Tasks

1. Convert scrapers to Celery tasks
2. Add error handling and retry logic
3. Implement duplicate detection
4. Add logging and monitoring

#### Day 5: Configure Celery Beat

1. Setup periodic task schedule
2. Configure daily scraper runs
3. Add health checks
4. Test scheduling

#### Day 6-7: Monitoring & Alerts

1. Setup Flower for monitoring
2. Implement email/Slack alerts on failures
3. Add metrics collection
4. Create admin dashboard

### **Phase 2: Enhance Scrapers** (Week 2)

#### Day 1-2: Data Quality

1. Add data validation layer
2. Standardize location parsing
3. Normalize salary formats
4. Implement deduplication across sources

#### Day 3-4: Civil Service Scraper

1. Review and test CS scraper
2. Either: Fix Selenium setup OR Replace with API/simpler method
3. Add to orchestrator if viable

#### Day 5: Testing

1. End-to-end testing
2. Load testing with large datasets
3. Failure scenario testing

#### Day 6-7: Documentation & Deployment

1. Document all tasks and schedules
2. Create runbook for operations
3. Deploy to production
4. Monitor first week of automated runs

---

## 🎯 Recommended Schedule (Celery Beat)

### Daily Scraping (Recommended)

```python
# Run at 2:00 AM daily (low traffic time)
'daily-job-scrape': {
    'task': 'jobstract.tasks.run_all_scrapers',
    'schedule': crontab(hour=2, minute=0),
    'kwargs': {
        'location': '',  # UK-wide
        'days': 1,
        'force': False
    }
}
```

### Weekly Deep Scrape (Optional)

```python
# Run Sundays at 3:00 AM for 7 days of data
'weekly-deep-scrape': {
    'task': 'jobstract.tasks.run_all_scrapers',
    'schedule': crontab(hour=3, minute=0, day_of_week=0),
    'kwargs': {
        'location': '',
        'days': 7,
        'force': True
    }
}
```

### Cleanup Task

```python
# Remove old jobs (90+ days) - Monthly
'monthly-cleanup': {
    'task': 'jobstract.tasks.cleanup_old_jobs',
    'schedule': crontab(hour=4, minute=0, day_of_month=1),
}
```

---

## 📊 Success Metrics

### Track the Following:

1. **Jobs Scraped Per Day**: Target 100-500 jobs/day
2. **Scraper Success Rate**: Target >95%
3. **Duplicate Rate**: Expect 10-30% duplicates
4. **Average Scrape Time**: Monitor for performance
5. **Error Rate**: Target <5%
6. **Data Quality Score**: Custom validation metrics

---

## 🔧 Quick Start Commands

### Manual Testing (Current)

```bash
# Run all scrapers
python manage.py run_all_scrapers

# Run individual scrapers
python manage.py reed_scraper --location "London" --distance 10
python manage.py dwp_scraper --location "Manchester" --distance 20
python manage.py scrape_jobs --days 3 --force

# With debug
python manage.py run_all_scrapers --debug --location "Birmingham"
```

### After Celery Setup (Future)

```bash
# Start Celery worker
celery -A ella_backend worker -l info

# Start Celery Beat (scheduler)
celery -A ella_backend beat -l info

# Start Flower (monitoring)
celery -A ella_backend flower

# Trigger manual scrape
python manage.py shell
>>> from jobstract.tasks import run_all_scrapers_task
>>> run_all_scrapers_task.delay()
```

---

## 🎯 Immediate Next Steps

1. **Choose Automation Method**: Celery (recommended) vs Django-Cron vs System Cron
2. **Review Civil Service Scraper**: Determine if we keep, fix, or remove it
3. **Setup Development Environment**: Install Celery + Redis locally
4. **Create Tasks**: Convert scrapers to Celery tasks
5. **Test Scheduling**: Verify daily runs work correctly
6. **Deploy to Production**: Configure on Render/AWS
7. **Monitor First Week**: Ensure stability

---

## 💡 Recommendations

### Priority: HIGH ⚡

1. **Implement Celery + Redis** - Provides robust automation
2. **Add Duplicate Detection** - Prevent database bloat
3. **Setup Monitoring** - Flower + alerts
4. **Test CS Scraper** - Fix or remove

### Priority: MEDIUM 🔶

1. **Data Quality Validation** - Standardize formats
2. **Add Health Checks** - Scraper availability monitoring
3. **Implement Metrics** - Track performance over time

### Priority: LOW 🔵

1. **Add More Sources** - LinkedIn, Indeed, Glassdoor (if APIs available)
2. **ML-based Deduplication** - Smart duplicate detection
3. **Job Recommendation Engine** - Match users to jobs

---

## 📝 Notes

- All scrapers use the `Cleaner` utility for data normalization
- `run_all_scrapers.py` provides excellent error isolation
- Reed scraper is the most reliable (official API)
- SME scraper has built-in 24-hour cooldown
- No current automation exists - all manual runs

---

**Next Action**: Decide on Celery vs Django-Cron vs System Cron, then begin implementation.
