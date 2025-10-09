# Celery Setup Guide for Job Scraper Automation

**Date**: October 9, 2025  
**Estimated Time**: 2-4 hours  
**Difficulty**: Medium

---

## 📋 Prerequisites

- Python 3.11+
- Redis installed (locally + production)
- Django project running
- Existing job scrapers tested and working

---

## 🚀 Step-by-Step Implementation

### Step 1: Install Dependencies

```bash
cd /Users/michaeladeleye/Documents/Coding/ella/Ella-backend

# Install Celery, Redis, and monitoring tools
pip install celery[redis]==5.3.4
pip install redis==5.0.1
pip install flower==2.0.1  # Web-based monitoring tool
pip install django-celery-beat==2.5.0  # Database-backed periodic tasks
pip install django-celery-results==2.5.0  # Store task results in DB

# Update requirements.txt
pip freeze > requirements.txt
```

---

### Step 2: Install Redis

#### macOS (Homebrew)

```bash
brew install redis

# Start Redis
brew services start redis

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify
redis-cli ping
```

#### Production (Render/AWS)

- **Render**: Use managed Redis service
- **AWS**: Use ElastiCache Redis
- **Heroku**: Use Heroku Redis add-on

---

### Step 3: Create Celery Configuration

#### 3.1: Create `Ella-backend/celery.py`

```python
"""
Celery configuration for Ella Backend
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_backend.settings')

# Create Celery app
app = Celery('ella_backend')

# Load config from Django settings with 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Daily job scraping at 2:00 AM
    'daily-job-scrape': {
        'task': 'jobstract.tasks.run_all_scrapers_task',
        'schedule': crontab(hour=2, minute=0),  # Every day at 2:00 AM
        'kwargs': {
            'location': '',  # UK-wide search
            'days': 1,
            'force': False
        }
    },

    # Weekly deep scrape on Sundays at 3:00 AM
    'weekly-deep-scrape': {
        'task': 'jobstract.tasks.run_all_scrapers_task',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
        'kwargs': {
            'location': '',
            'days': 7,  # Scrape 7 days of jobs
            'force': True
        }
    },

    # Monthly cleanup of old jobs (90+ days old)
    'monthly-cleanup': {
        'task': 'jobstract.tasks.cleanup_old_jobs',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),  # 1st of month, 4 AM
        'kwargs': {
            'days_old': 90
        }
    },

    # Health check every 6 hours
    'scraper-health-check': {
        'task': 'jobstract.tasks.check_scraper_health',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/London',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery setup"""
    print(f'Request: {self.request!r}')
```

#### 3.2: Update `Ella-backend/ella_backend/__init__.py`

```python
"""
This will make sure the app is always imported when
Django starts so that shared_task will use this app.
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
```

---

### Step 4: Update Django Settings

Add to `Ella-backend/ella_backend/settings.py`:

```python
# ============================================
# CELERY CONFIGURATION
# ============================================

# Celery broker URL (Redis)
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Celery result backend (store results in Redis)
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Celery accept content types
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Celery timezone
CELERY_TIMEZONE = 'Europe/London'
CELERY_ENABLE_UTC = True

# Celery Beat (scheduler) configuration
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery task configuration
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Celery worker configuration
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Celery result expiration (cleanup)
CELERY_RESULT_EXPIRES = 60 * 60 * 24  # 24 hours

# ============================================
# INSTALLED APPS - Add Celery apps
# ============================================

INSTALLED_APPS = [
    # ... existing apps ...
    'django_celery_beat',  # Database-backed periodic tasks
    'django_celery_results',  # Store task results
    # ... rest of apps ...
]
```

---

### Step 5: Create Celery Tasks

#### 5.1: Create `Ella-backend/jobstract/tasks.py`

```python
"""
Celery tasks for job scraping automation
"""
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from jobstract.models import Opportunity
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='jobstract.tasks.run_all_scrapers_task')
def run_all_scrapers_task(self, location='', days=1, force=False):
    """
    Run all job scrapers (SME, Reed, DWP)

    Args:
        location (str): Location to search (empty for UK-wide)
        days (int): Number of days to scrape
        force (bool): Force run even if recently scraped

    Returns:
        dict: Summary of scraping results
    """
    try:
        logger.info(f"Starting all job scrapers: location={location}, days={days}, force={force}")

        # Call the management command
        call_command(
            'run_all_scrapers',
            location=location,
            days=days,
            force=force
        )

        logger.info("All scrapers completed successfully")
        return {
            'status': 'success',
            'message': 'All scrapers completed',
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error running scrapers: {str(e)}", exc_info=True)
        # Retry task in 1 hour if it fails (max 3 retries)
        raise self.retry(exc=e, countdown=3600, max_retries=3)


@shared_task(bind=True, name='jobstract.tasks.run_reed_scraper')
def run_reed_scraper_task(self, location='', distance=10, keywords=None):
    """
    Run Reed.co.uk scraper

    Args:
        location (str): Location to search
        distance (int): Distance in miles
        keywords (str): Keywords to search

    Returns:
        dict: Scraping results
    """
    try:
        logger.info(f"Starting Reed scraper: location={location}, distance={distance}")

        call_command(
            'reed_scraper',
            location=location,
            distance=distance,
            keywords=keywords
        )

        return {
            'status': 'success',
            'scraper': 'Reed',
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Reed scraper failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=1800, max_retries=3)


@shared_task(bind=True, name='jobstract.tasks.run_dwp_scraper')
def run_dwp_scraper_task(self, location='', distance=20):
    """
    Run DWP (Find a Job) scraper

    Args:
        location (str): Location to search
        distance (int): Distance in km

    Returns:
        dict: Scraping results
    """
    try:
        logger.info(f"Starting DWP scraper: location={location}, distance={distance}")

        call_command(
            'dwp_scraper',
            location=location,
            distance=distance
        )

        return {
            'status': 'success',
            'scraper': 'DWP',
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"DWP scraper failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=1800, max_retries=3)


@shared_task(bind=True, name='jobstract.tasks.run_sme_scraper')
def run_sme_scraper_task(self, days=1, force=False):
    """
    Run SME scraper

    Args:
        days (int): Number of days to scrape
        force (bool): Force run

    Returns:
        dict: Scraping results
    """
    try:
        logger.info(f"Starting SME scraper: days={days}, force={force}")

        call_command(
            'scrape_jobs',
            days=days,
            force=force
        )

        return {
            'status': 'success',
            'scraper': 'SME',
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"SME scraper failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=1800, max_retries=3)


@shared_task(name='jobstract.tasks.cleanup_old_jobs')
def cleanup_old_jobs(days_old=90):
    """
    Delete jobs older than specified days

    Args:
        days_old (int): Number of days (default: 90)

    Returns:
        dict: Cleanup results
    """
    try:
        cutoff_date = timezone.now().date() - timedelta(days=days_old)

        old_jobs = Opportunity.objects.filter(date_posted__lt=cutoff_date)
        count = old_jobs.count()

        logger.info(f"Deleting {count} jobs older than {days_old} days (before {cutoff_date})")
        old_jobs.delete()

        return {
            'status': 'success',
            'deleted_count': count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task(name='jobstract.tasks.check_scraper_health')
def check_scraper_health():
    """
    Check health of job scrapers by verifying recent job additions

    Returns:
        dict: Health check results
    """
    try:
        # Check if jobs were added in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        recent_jobs = Opportunity.objects.filter(created_at__gte=yesterday).count()

        # Check total job count
        total_jobs = Opportunity.objects.count()

        # Calculate average jobs per day over last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        weekly_jobs = Opportunity.objects.filter(created_at__gte=week_ago).count()
        avg_per_day = weekly_jobs / 7

        status = 'healthy' if recent_jobs > 0 else 'warning'

        logger.info(
            f"Scraper health check: {recent_jobs} jobs in last 24h, "
            f"{total_jobs} total, avg {avg_per_day:.1f}/day"
        )

        return {
            'status': status,
            'recent_jobs_24h': recent_jobs,
            'total_jobs': total_jobs,
            'weekly_jobs': weekly_jobs,
            'avg_jobs_per_day': round(avg_per_day, 2),
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }
```

---

### Step 6: Run Database Migrations

```bash
# Create migrations for Celery Beat and Results
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_results
```

---

### Step 7: Start Celery Services

#### Terminal 1: Django Development Server

```bash
python manage.py runserver
```

#### Terminal 2: Celery Worker

```bash
# Start Celery worker to process tasks
celery -A ella_backend worker --loglevel=info

# For macOS (if you get pool issues)
celery -A ella_backend worker --loglevel=info --pool=solo
```

#### Terminal 3: Celery Beat (Scheduler)

```bash
# Start Celery Beat to trigger scheduled tasks
celery -A ella_backend beat --loglevel=info
```

#### Terminal 4: Flower (Optional - Monitoring UI)

```bash
# Start Flower web interface
celery -A ella_backend flower

# Access at: http://localhost:5555
```

---

### Step 8: Test Celery Setup

#### 8.1: Test Debug Task

```bash
python manage.py shell
```

```python
from ella_backend.celery import debug_task

# Run debug task
result = debug_task.delay()
print(f"Task ID: {result.id}")
print(f"Task Status: {result.status}")
```

#### 8.2: Test Job Scraper Task

```python
from jobstract.tasks import run_all_scrapers_task

# Run scrapers asynchronously
task = run_all_scrapers_task.delay(location='London', days=1)

# Check task status
print(task.status)  # PENDING, STARTED, SUCCESS, FAILURE

# Get result (blocks until complete)
result = task.get(timeout=1800)  # 30 min timeout
print(result)
```

#### 8.3: Test Individual Scrapers

```python
from jobstract.tasks import run_reed_scraper_task, run_dwp_scraper_task

# Run Reed scraper
reed_task = run_reed_scraper_task.delay(location='Manchester', distance=15)

# Run DWP scraper
dwp_task = run_dwp_scraper_task.delay(location='Birmingham', distance=20)
```

---

### Step 9: Monitor Tasks

#### Using Flower (Web UI)

1. Start Flower: `celery -A ella_backend flower`
2. Open: http://localhost:5555
3. View:
   - Active tasks
   - Completed tasks
   - Task details
   - Worker status
   - Task graphs

#### Using Django Shell

```python
from django_celery_results.models import TaskResult

# Get recent task results
recent_tasks = TaskResult.objects.order_by('-date_done')[:10]

for task in recent_tasks:
    print(f"{task.task_name}: {task.status} - {task.date_done}")
```

#### Using Celery CLI

```bash
# Inspect active tasks
celery -A ella_backend inspect active

# Inspect scheduled tasks
celery -A ella_backend inspect scheduled

# Inspect registered tasks
celery -A ella_backend inspect registered
```

---

### Step 10: Production Deployment

#### Update Environment Variables (.env)

```bash
# Production Redis URL (example for Render)
REDIS_URL=redis://red-xxxxx:6379/0

# For AWS ElastiCache
REDIS_URL=redis://your-elasticache-endpoint:6379/0
```

#### Procfile (for Render/Heroku)

```
web: gunicorn ella_backend.wsgi:application
worker: celery -A ella_backend worker --loglevel=info
beat: celery -A ella_backend beat --loglevel=info
```

#### render.yaml (for Render)

```yaml
services:
  - type: web
    name: ella-backend
    env: python
    buildCommand: "./build.sh"
    startCommand: "gunicorn ella_backend.wsgi:application"

  - type: worker
    name: ella-celery-worker
    env: python
    buildCommand: "./build.sh"
    startCommand: "celery -A ella_backend worker --loglevel=info"

  - type: worker
    name: ella-celery-beat
    env: python
    buildCommand: "./build.sh"
    startCommand: "celery -A ella_backend beat --loglevel=info"

databases:
  - name: ella-postgres
    plan: starter

  - name: ella-redis
    plan: starter
    ipAllowList: []
```

---

## 🎯 Quick Reference Commands

### Development

```bash
# Start all services (use separate terminals)
python manage.py runserver                          # Django
celery -A ella_backend worker -l info --pool=solo  # Worker (macOS)
celery -A ella_backend beat -l info                 # Scheduler
celery -A ella_backend flower                       # Monitoring

# Manual task execution
python manage.py shell
>>> from jobstract.tasks import run_all_scrapers_task
>>> run_all_scrapers_task.delay()
```

### Production

```bash
# Start services (systemd/supervisor)
celery -A ella_backend worker --loglevel=info --concurrency=4
celery -A ella_backend beat --loglevel=info
```

### Monitoring

```bash
# Check worker status
celery -A ella_backend status

# Purge all tasks (BE CAREFUL!)
celery -A ella_backend purge

# Inspect tasks
celery -A ella_backend inspect active
celery -A ella_backend inspect scheduled
```

---

## 📊 Verification Checklist

- [ ] Redis installed and running
- [ ] Celery dependencies installed
- [ ] `celery.py` created in project root
- [ ] `__init__.py` updated
- [ ] Settings configured with CELERY\_\* variables
- [ ] `tasks.py` created in jobstract app
- [ ] Migrations run successfully
- [ ] Celery worker starts without errors
- [ ] Celery beat starts without errors
- [ ] Debug task executes successfully
- [ ] Job scraper task executes successfully
- [ ] Flower accessible at localhost:5555
- [ ] Scheduled tasks appear in Flower
- [ ] Task results stored in database

---

## 🐛 Common Issues & Solutions

### Issue 1: "No module named 'celery'"

```bash
pip install celery[redis]==5.3.4
```

### Issue 2: "Connection refused" to Redis

```bash
# Check Redis is running
redis-cli ping

# Start Redis
brew services start redis  # macOS
sudo systemctl start redis  # Linux
```

### Issue 3: "kombu.exceptions.EncodeError"

- Ensure `task_serializer='json'` in celery config
- Check task arguments are JSON-serializable

### Issue 4: Tasks not executing on schedule

- Verify Celery Beat is running
- Check `beat_schedule` in `celery.py`
- Inspect scheduled tasks: `celery -A ella_backend inspect scheduled`

### Issue 5: macOS "billiard.exceptions.TimeLimitExceeded"

```bash
# Use solo pool on macOS
celery -A ella_backend worker --pool=solo
```

---

## 🎉 Success Indicators

You'll know it's working when:

1. ✅ Flower shows active workers
2. ✅ Scheduled tasks appear in Flower's "Tasks" tab
3. ✅ `run_all_scrapers_task.delay()` returns immediately with task ID
4. ✅ Task completes successfully in Flower
5. ✅ New jobs appear in database after scheduled run
6. ✅ No errors in Celery worker logs

---

## 📚 Next Steps

1. **Test extensively** in development
2. **Monitor first week** of scheduled runs
3. **Add email alerts** for task failures
4. **Create admin dashboard** for task management
5. **Optimize scraper performance** based on metrics
6. **Scale workers** as needed in production

---

**Estimated Total Setup Time**: 2-4 hours  
**Difficulty**: Medium  
**Recommended**: Yes - Production-ready, scalable, battle-tested

Good luck! 🚀
