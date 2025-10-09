# Quick Setup - GitHub Actions Job Scraper

**Time**: 30 minutes | **Cost**: FREE ✅

---

## ✅ Setup Checklist

### 1️⃣ Add GitHub Secrets (5 min)

Go to: `https://github.com/mikeadex/Ella-backend/settings/secrets/actions`

Add these secrets:

```
✅ DATABASE_URL          → postgresql://user:pass@host:5432/db
✅ REED_API_KEY          → Your Reed API key
✅ SECRET_KEY            → Django secret key
✅ DEEPSEEK_API_KEY      → Your DeepSeek key
✅ ALLOWED_HOSTS         → your-domain.com,*.onrender.com
```

**Optional (for email alerts)**:

```
⚪ NOTIFICATION_EMAIL           → your-email@gmail.com
⚪ NOTIFICATION_EMAIL_PASSWORD  → Gmail app password
```

---

### 2️⃣ Push Workflows to GitHub (5 min)

```bash
cd /Users/michaeladeleye/Documents/Coding/ella/Ella-backend

# Check workflows exist
ls .github/workflows/

# Should see:
# - daily-job-scraper.yml
# - weekly-deep-scrape.yml
# - monthly-cleanup.yml

# Add and commit
git add .github/workflows/
git commit -m "feat: Add GitHub Actions for automated job scraping"
git push origin main
```

---

### 3️⃣ Test Manual Trigger (10 min)

1. Go to: `https://github.com/mikeadex/Ella-backend/actions`
2. Click **"Daily Job Scraper"**
3. Click **"Run workflow"** (top right dropdown)
4. Click **"Run workflow"** button
5. ✅ Watch it run (5-15 min)
6. ✅ Check logs for job statistics

---

### 4️⃣ Verify Success (5 min)

```python
# Check your database
from jobstract.models import Opportunity
from django.utils import timezone

# Jobs added today
today_jobs = Opportunity.objects.filter(created_at__date=timezone.now().date()).count()
print(f"Jobs added today: {today_jobs}")
```

---

## 📅 What Happens Next

### Automatic Runs:

- ✅ **Daily 2 AM UTC**: Scrape yesterday's jobs (200-500 jobs)
- ✅ **Sunday 3 AM UTC**: Deep scrape last 7 days (1,000-2,000 jobs)
- ✅ **1st of Month 4 AM UTC**: Delete jobs >90 days old

### You Get:

- ✅ Automated job scraping (no manual work!)
- ✅ Free infrastructure (GitHub's servers)
- ✅ Detailed logs (30 days retention)
- ✅ Email alerts on failures (if configured)
- ✅ Manual trigger anytime

---

## 🎯 Quick Commands

### Manual Trigger Options:

**Daily Scraper**:

- Location: `London`, `Manchester`, or empty for UK-wide
- Days: `1`, `3`, `7`
- Force: `true`/`false`

**Weekly Scraper**:

- Runs automatically every Sunday
- Can trigger manually anytime

**Monthly Cleanup**:

- Days old: `90` (default), `60`, `120`
- Deletes old jobs

---

## 📊 Free Tier Usage

```
Daily:    ~10 min/day × 30 days  = 300 min/month
Weekly:   ~20 min/week × 4 weeks = 80 min/month
Monthly:  ~5 min/month × 1       = 5 min/month
─────────────────────────────────────────────────
Total:                           ~385 min/month

Your limit:   2,000 min/month ✅
Remaining:    1,615 min/month (plenty!)
```

---

## 🐛 Quick Troubleshooting

**Workflow not running?**

- ✅ Check secrets are added
- ✅ Ensure on `main` branch
- ✅ Test with manual trigger first

**Database connection failed?**

- ✅ Use **Internal Database URL** from Render
- ✅ Verify DATABASE_URL secret is correct

**Missing API key error?**

- ✅ Add REED_API_KEY secret
- ✅ Secret names are case-sensitive

---

## 📚 Full Documentation

- **Setup Guide**: `GITHUB_ACTIONS_SETUP_GUIDE.md`
- **Scraper Review**: `JOB_SCRAPERS_REVIEW_AND_AUTOMATION.md`
- **Workflow Files**: `.github/workflows/`

---

## ✨ That's It!

You now have:

1. ✅ Automated daily job scraping
2. ✅ Zero infrastructure costs
3. ✅ Built-in monitoring
4. ✅ Email notifications (optional)
5. ✅ Manual control anytime

**No Celery, no Redis, no servers to manage!** 🎉

---

**Next Step**: Add GitHub secrets and push workflows → You're live in 30 min! 🚀
