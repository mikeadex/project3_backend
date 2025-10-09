# GitHub Actions Setup Guide - Job Scraper Automation

**Date**: October 9, 2025  
**Cost**: **FREE** ✅  
**Setup Time**: 30 minutes  
**Difficulty**: Easy

---

## 🎉 Why GitHub Actions is Perfect for You

### ✅ **Advantages**

1. **FREE** - No infrastructure costs

   - 2,000 minutes/month (private repos)
   - Unlimited for public repos
   - Your scrapers: ~300-900 min/month ✅

2. **Zero Infrastructure**

   - No Redis needed
   - No Celery setup
   - No worker servers
   - GitHub handles everything

3. **Simple Setup**

   - Create workflow YAML files
   - Add secrets to GitHub
   - Push and done!

4. **Built-in Features**

   - Automatic logs (30 days retention)
   - Email notifications on failure
   - Manual trigger anytime
   - Scheduled cron jobs

5. **Perfect for Your Use Case**
   - Daily scraping ✅
   - Weekly deep scrapes ✅
   - Monthly cleanup ✅
   - Connects to production DB ✅

---

## 📋 What I've Created for You

### 3 Workflow Files

1. **`daily-job-scraper.yml`** - Daily scraping at 2:00 AM UTC
2. **`weekly-deep-scrape.yml`** - Weekly deep scrape (Sundays 3:00 AM)
3. **`monthly-cleanup.yml`** - Monthly cleanup (1st of month, 4:00 AM)

All files are in: `.github/workflows/`

---

## 🚀 Setup Instructions

### Step 1: Add GitHub Secrets (CRITICAL!)

Your workflows need access to your production database and API keys. Add these secrets to GitHub:

#### Go to GitHub Repository Settings:

1. Navigate to: `https://github.com/mikeadex/Ella-backend/settings/secrets/actions`
2. Click **"New repository secret"** for each of the following:

#### Required Secrets:

| Secret Name        | Description             | Example Value                             |
| ------------------ | ----------------------- | ----------------------------------------- |
| `DATABASE_URL`     | Production database URL | `postgresql://user:pass@host:5432/dbname` |
| `REED_API_KEY`     | Reed.co.uk API key      | Your Reed API key                         |
| `SECRET_KEY`       | Django secret key       | Your Django secret key                    |
| `DEEPSEEK_API_KEY` | DeepSeek AI key         | Your DeepSeek key                         |
| `ALLOWED_HOSTS`    | Django allowed hosts    | `your-domain.com,*.onrender.com`          |

#### Optional Secrets (for email notifications):

| Secret Name                   | Description        | Example Value               |
| ----------------------------- | ------------------ | --------------------------- |
| `NOTIFICATION_EMAIL`          | Email for alerts   | `your-email@gmail.com`      |
| `NOTIFICATION_EMAIL_PASSWORD` | Email app password | Gmail app-specific password |

**How to add a secret**:

```
1. Click "New repository secret"
2. Name: DATABASE_URL
3. Value: postgresql://user:password@host:5432/database
4. Click "Add secret"
5. Repeat for all secrets above
```

---

### Step 2: Get Your Database URL

#### If using Render:

1. Go to your Render dashboard
2. Select your PostgreSQL database
3. Copy the **Internal Database URL**
4. Paste as `DATABASE_URL` secret in GitHub

#### Format:

```
postgresql://username:password@hostname:port/database_name
```

---

### Step 3: Push Workflow Files to GitHub

```bash
cd /Users/michaeladeleye/Documents/Coding/ella/Ella-backend

# Check the workflows were created
ls -la .github/workflows/

# Add to git
git add .github/workflows/

# Commit
git commit -m "feat: Add GitHub Actions workflows for automated job scraping

- Daily scraping at 2 AM UTC
- Weekly deep scrape on Sundays
- Monthly cleanup of old jobs (90+ days)
- Manual trigger support
- Email notifications on failure
"

# Push to GitHub
git push origin main
```

---

### Step 4: Verify Workflows are Active

1. Go to: `https://github.com/mikeadex/Ella-backend/actions`
2. You should see 3 workflows:
   - ✅ Daily Job Scraper
   - ✅ Weekly Deep Job Scraper
   - ✅ Monthly Job Cleanup

---

### Step 5: Test Manual Trigger (IMPORTANT!)

Before waiting for the scheduled run, test it manually:

1. Go to: `https://github.com/mikeadex/Ella-backend/actions`
2. Click on **"Daily Job Scraper"**
3. Click **"Run workflow"** dropdown (top right)
4. Leave defaults or customize:
   - Location: (empty for UK-wide)
   - Days: 1
   - Force: false
5. Click **"Run workflow"** button
6. Watch the job run in real-time ✅

**Expected Result**:

- Job should complete in 5-15 minutes
- Green checkmark ✅ on success
- Click on the job to see detailed logs
- Check your database for new jobs

---

## 📅 Schedule Summary

### Daily Scraping

```yaml
Schedule: Every day at 2:00 AM UTC (3:00 AM BST in summer)
Command: python manage.py run_all_scrapers --days 1
Duration: ~5-15 minutes
Expected Jobs: 200-500/day
```

### Weekly Deep Scrape

```yaml
Schedule: Every Sunday at 3:00 AM UTC
Command: python manage.py run_all_scrapers --days 7 --force
Duration: ~15-30 minutes
Expected Jobs: 1,000-2,000
```

### Monthly Cleanup

```yaml
Schedule: 1st of every month at 4:00 AM UTC
Command: Delete jobs older than 90 days
Duration: ~2-5 minutes
```

---

## 🎯 Monitoring Your Scrapers

### View Workflow Runs

1. Go to: `https://github.com/mikeadex/Ella-backend/actions`
2. See all runs (successful ✅ and failed ❌)
3. Click any run to see detailed logs

### Check Logs

```
1. Go to Actions tab
2. Click on a workflow run
3. Click on "scrape-jobs" job
4. Expand steps to see output
5. See statistics at bottom
```

### What You'll See in Logs:

```
📈 Statistics:
  - Jobs added today: 347
  - Total jobs in DB: 12,453
  - Jobs from last 7 days: 2,341
  - Average per day (last 7d): 334.4
```

---

## 🔧 Manual Triggers

All workflows support manual triggering:

### Daily Scraper (with options)

```
1. Go to Actions > Daily Job Scraper
2. Click "Run workflow"
3. Options:
   - Location: "London", "Manchester", etc. (or empty for UK-wide)
   - Days: 1, 3, 7, etc.
   - Force: true/false (ignore cooldown)
4. Click "Run workflow"
```

### Weekly Scraper

```
1. Go to Actions > Weekly Deep Job Scraper
2. Click "Run workflow"
3. Click "Run workflow" (no options)
```

### Cleanup

```
1. Go to Actions > Monthly Job Cleanup
2. Click "Run workflow"
3. Option: Days old (default: 90)
4. Click "Run workflow"
```

---

## 📧 Email Notifications (Optional)

To receive email alerts when scrapers fail:

### Setup Gmail App Password:

1. Go to: https://myaccount.google.com/apppasswords
2. Sign in to your Google account
3. Create app password for "GitHub Actions"
4. Copy the 16-character password
5. Add to GitHub secrets:
   - `NOTIFICATION_EMAIL`: your-email@gmail.com
   - `NOTIFICATION_EMAIL_PASSWORD`: the-16-char-password

### What You'll Receive:

- Email ONLY on failures ❌
- Includes run ID and link to logs
- No email on success ✅

---

## ⚙️ Advanced Configuration

### Change Schedule Times

Edit workflow files to change timing:

```yaml
# Daily at 2:00 AM UTC
schedule:
  - cron: '0 2 * * *'

# Change to 6:00 AM UTC
schedule:
  - cron: '0 6 * * *'

# Twice daily (2 AM and 2 PM)
schedule:
  - cron: '0 2,14 * * *'
```

**Cron Syntax Reference**:

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-6, Sunday=0)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Add More Scrapers to Workflow

Edit `.github/workflows/daily-job-scraper.yml`:

```yaml
- name: 🔍 Run Job Scrapers
  run: |
    # Run all scrapers
    python manage.py run_all_scrapers --days 1

    # OR run individual scrapers
    python manage.py reed_scraper --location "London"
    python manage.py dwp_scraper --location "Manchester"
    python manage.py scrape_jobs --days 1
```

---

## 🐛 Troubleshooting

### Issue 1: Workflow Not Running

**Problem**: Scheduled workflow doesn't trigger

**Solutions**:

- ✅ Workflows only run on default branch (main)
- ✅ Must have at least 1 commit in last 60 days
- ✅ Scheduled workflows can be ±15 min late (GitHub's disclaimer)
- ✅ Test with manual trigger first

### Issue 2: Database Connection Failed

**Problem**: `OperationalError: could not connect to server`

**Solutions**:

- ✅ Verify `DATABASE_URL` secret is correct
- ✅ Check database allows connections from GitHub IPs (usually public)
- ✅ Render databases: Use **Internal Database URL**, not External

### Issue 3: Missing Environment Variable

**Problem**: `KeyError: 'REED_API_KEY'`

**Solutions**:

- ✅ Add missing secret to GitHub repository settings
- ✅ Secret names are CASE-SENSITIVE
- ✅ After adding secret, re-run workflow

### Issue 4: Workflow Times Out

**Problem**: Job runs for 30 minutes then cancels

**Solutions**:

- ✅ Increase timeout in YAML: `timeout-minutes: 60`
- ✅ Optimize scrapers (reduce days, add filters)
- ✅ Split into multiple workflows

### Issue 5: Duplicate Jobs Created

**Problem**: Same jobs scraped multiple times

**Solutions**:

- ✅ Ensure SME scraper's 24h cooldown is working
- ✅ Add `--force false` to daily scraper
- ✅ Implement better duplicate detection in scrapers

---

## 📊 Usage & Costs

### Free Tier Limits (Private Repo)

```
Minutes per month: 2,000
Your expected usage: ~300-900 min/month
Remaining: ~1,100-1,700 min/month for other workflows
```

### Calculation:

```
Daily scrape: ~10 min/day × 30 days = 300 min/month
Weekly scrape: ~20 min/week × 4 weeks = 80 min/month
Monthly cleanup: ~5 min/month × 1 = 5 min/month
Total: ~385 min/month (well within free tier!)
```

### If You Need More:

- Make repo public = unlimited minutes ✅
- GitHub Pro: 3,000 min/month ($4/month)
- GitHub Team: 10,000 min/month ($44/month for 1 user)

---

## ✅ Success Checklist

After setup, verify:

- [ ] 3 workflow files in `.github/workflows/`
- [ ] All secrets added to GitHub (DATABASE_URL, REED_API_KEY, etc.)
- [ ] Workflows visible in Actions tab
- [ ] Manual trigger test successful ✅
- [ ] Logs show jobs being scraped
- [ ] Database has new jobs
- [ ] Next scheduled run appears in Actions tab
- [ ] Email notifications working (if configured)

---

## 🎯 Next Steps

### Today:

1. ✅ Add GitHub secrets (DATABASE_URL, API keys)
2. ✅ Push workflow files to GitHub
3. ✅ Test with manual trigger
4. ✅ Verify jobs appear in database

### Tomorrow:

1. ✅ Check if scheduled run executed
2. ✅ Review logs for errors
3. ✅ Verify job statistics

### This Week:

1. ✅ Monitor daily runs
2. ✅ Fine-tune schedules if needed
3. ✅ Setup email notifications (optional)

### This Month:

1. ✅ Verify weekly deep scrape works
2. ✅ Test monthly cleanup
3. ✅ Optimize scraper performance based on metrics

---

## 📚 Additional Resources

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Cron Expression Generator**: https://crontab.guru/
- **Workflow Syntax**: https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions
- **GitHub Actions Limits**: https://docs.github.com/en/actions/learn-github-actions/usage-limits-billing-and-administration

---

## 💡 Pro Tips

1. **Test Locally First**: Before pushing workflows, test scrapers locally

   ```bash
   python manage.py run_all_scrapers --days 1
   ```

2. **Use Manual Triggers**: Don't wait for schedule - test immediately

3. **Monitor First Week**: Check logs daily to catch issues early

4. **Adjust Timing**: If 2 AM doesn't work, change to low-traffic time

5. **Keep Workflows Simple**: If one scraper fails, others continue

6. **Version Control**: Treat workflow files like code - commit, review, test

---

## 🎉 Comparison: GitHub Actions vs Celery

| Feature             | GitHub Actions    | Celery + Redis    |
| ------------------- | ----------------- | ----------------- |
| **Cost**            | FREE ✅           | $10-25/month ❌   |
| **Setup Time**      | 30 min ✅         | 2-4 hours ❌      |
| **Infrastructure**  | None ✅           | Redis, workers ❌ |
| **Monitoring**      | Built-in ✅       | Need Flower ❌    |
| **Reliability**     | GitHub's 99.9% ✅ | DIY ⚠️            |
| **Timing Accuracy** | ±15 min ⚠️        | Exact ✅          |
| **Max Frequency**   | Every 5 min ⚠️    | Real-time ✅      |
| **Real-time Tasks** | No ❌             | Yes ✅            |
| **Best For**        | Scheduled jobs ✅ | Complex queues ✅ |

**Verdict**: For your daily scraping needs, **GitHub Actions is perfect!** ✅

---

## 🚀 You're All Set!

Your job scrapers will now run automatically:

- 🌙 **Daily at 2 AM** - Fresh jobs every morning
- 📅 **Sundays at 3 AM** - Deep scrape to catch missed jobs
- 🗑️ **Monthly at 4 AM** - Cleanup old jobs to keep DB lean

**No infrastructure costs, no maintenance, fully automated!** 🎉

---

**Status**: ✅ **READY TO DEPLOY**  
**Cost**: $0/month  
**Setup Time**: 30 minutes  
**Next Action**: Add GitHub secrets and push workflows
