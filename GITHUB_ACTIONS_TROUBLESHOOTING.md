# GitHub Actions Troubleshooting - Common Issues & Fixes

**Last Updated**: October 9, 2025

---

## 🚨 Error: "At least one of 'to', 'cc' or 'bcc' must be specified"

### What Happened

The email notification step tried to run but the `NOTIFICATION_EMAIL` secret wasn't set.

### Fix Applied ✅

Updated all workflows to only send emails if the secret exists:

```yaml
if: failure() && secrets.NOTIFICATION_EMAIL != ''
```

### What You Should Do

**Option 1**: Do nothing - emails are now optional ✅

**Option 2**: Setup email notifications (optional):

1. Go to: https://myaccount.google.com/apppasswords
2. Create app password for "GitHub Actions"
3. Add to GitHub secrets:
   - `NOTIFICATION_EMAIL`: your-email@gmail.com
   - `NOTIFICATION_EMAIL_PASSWORD`: 16-char-password

---

## 🚨 Error: "Process completed with exit code 1"

### What This Means

The job scraper command failed. Common causes:

1. **Missing DATABASE_URL secret** ❌
2. **Missing REED_API_KEY secret** ❌
3. **Database connection issue** ⚠️
4. **Missing Django SECRET_KEY** ❌
5. **Python dependency issue** ⚠️

### How to Debug

#### Step 1: Check the Full Logs

1. Go to: https://github.com/mikeadex/Ella-backend/actions
2. Click on the failed workflow run
3. Click on "scrape-jobs" job
4. Expand the "🔍 Run Job Scrapers" step
5. Look for the error message

#### Step 2: Common Error Messages

**"KeyError: 'DATABASE_URL'"**

```
Fix: Add DATABASE_URL to GitHub Secrets
Go to: Settings > Secrets and variables > Actions > New repository secret
Name: DATABASE_URL
Value: postgresql://user:pass@host:5432/database
```

**"KeyError: 'REED_API_KEY'"**

```
Fix: Add REED_API_KEY to GitHub Secrets
Name: REED_API_KEY
Value: Your Reed API key from https://www.reed.co.uk/developers/jobseeker
```

**"KeyError: 'SECRET_KEY'"**

```
Fix: Add Django SECRET_KEY to GitHub Secrets
Name: SECRET_KEY
Value: Your Django secret key (from .env file)
```

**"OperationalError: could not connect to database"**

```
Fix: Verify DATABASE_URL is correct
- Use INTERNAL database URL from Render (not external)
- Format: postgresql://username:password@hostname:port/database
- Ensure database allows public connections
```

**"No module named 'jobstract'"**

```
Fix: Missing Django app or wrong directory
This shouldn't happen - let me know if you see this
```

---

## 🔍 How to Get Your Secrets

### DATABASE_URL (Render PostgreSQL)

1. Go to: https://dashboard.render.com/
2. Click on your PostgreSQL database
3. Scroll to "Connections"
4. Copy **Internal Database URL** (starts with `postgresql://`)
5. Add to GitHub secrets

### REED_API_KEY

1. Go to: https://www.reed.co.uk/developers/jobseeker
2. Sign up or log in
3. Get your API key
4. Add to GitHub secrets

### SECRET_KEY

1. Check your `.env` file in Ella-backend
2. Find `SECRET_KEY=...`
3. Copy the value
4. Add to GitHub secrets

### DEEPSEEK_API_KEY

1. Check your `.env` file
2. Find `DEEPSEEK_API_KEY=...`
3. Copy the value
4. Add to GitHub secrets

### ALLOWED_HOSTS

1. Your production domain(s)
2. Format: `your-domain.com,*.onrender.com`
3. Add to GitHub secrets

---

## ✅ Checklist: Required GitHub Secrets

Go to: https://github.com/mikeadex/Ella-backend/settings/secrets/actions

Make sure you have:

- [ ] **DATABASE_URL** - PostgreSQL connection string
- [ ] **REED_API_KEY** - Reed.co.uk API key
- [ ] **SECRET_KEY** - Django secret key
- [ ] **DEEPSEEK_API_KEY** - DeepSeek AI key
- [ ] **ALLOWED_HOSTS** - Comma-separated domains

**Optional**:

- [ ] **NOTIFICATION_EMAIL** - Your email for alerts
- [ ] **NOTIFICATION_EMAIL_PASSWORD** - Gmail app password

---

## 🧪 Test Locally Before GitHub Actions

To ensure the scraper works before trying GitHub Actions:

```bash
cd /Users/michaeladeleye/Documents/Coding/ella/Ella-backend

# Test with your local database
python manage.py run_all_scrapers --days 1

# Or test individual scrapers
python manage.py reed_scraper --location "London"
python manage.py dwp_scraper --location "Manchester"
python manage.py scrape_jobs --days 1 --force
```

If these work locally, they'll work in GitHub Actions (as long as secrets are set).

---

## 🔧 Quick Fix Commands

### Re-run Failed Workflow

1. Go to: https://github.com/mikeadex/Ella-backend/actions
2. Click on failed workflow
3. Click "Re-run jobs" (top right)
4. Select "Re-run failed jobs"

### Trigger Manual Run (After Fixing Secrets)

1. Go to: https://github.com/mikeadex/Ella-backend/actions
2. Click "Daily Job Scraper"
3. Click "Run workflow"
4. Click "Run workflow" button

### View Secret Names (Not Values)

```bash
# You can't view secret values, but you can see what's set
Go to: Settings > Secrets and variables > Actions
You'll see a list of secret names
```

---

## 📊 What Success Looks Like

When everything works, you'll see:

```
✅ Green checkmark on workflow
📊 Job statistics in logs:
    - Jobs added today: 347
    - Total jobs in DB: 12,453
    - Jobs from last 7 days: 2,341
    - Average per day: 334.4
```

---

## 🆘 Still Having Issues?

### Check These:

1. **Secrets are case-sensitive**: `DATABASE_URL` ≠ `database_url`
2. **No quotes in secret values**: Don't wrap in quotes in GitHub UI
3. **Database URL format**: `postgresql://` not `postgres://`
4. **Render database**: Use Internal URL, not External
5. **Branch**: Workflows only run on `main` branch

### Get More Help:

1. Check workflow logs (expand all steps)
2. Test command locally first
3. Verify all 5 required secrets are set
4. Check database is accessible (not IP-restricted)

---

## 🎯 Next Steps After Fixing

1. ✅ Add missing secrets to GitHub
2. ✅ Re-run the failed workflow
3. ✅ Verify success (green checkmark)
4. ✅ Check database for new jobs
5. ✅ Wait for tomorrow's scheduled run

---

**Need the secret values?** Check your `.env` file or Render dashboard!
