# 🎯 Quick Fix: Update DATABASE_URL Secret

**Issue**: Workflow trying to connect to old Render database  
**Fix**: Update the DATABASE_URL secret in GitHub

---

## ⚡ **ACTION REQUIRED**

### Step 1: Go to GitHub Secrets

👉 https://github.com/mikeadex/Ella-backend/settings/secrets/actions

### Step 2: Update DATABASE_URL

1. Find **`DATABASE_URL`** in the list
2. Click the **pencil icon** (Edit) next to it
3. Replace with your **current database URL** from `.env` file:

```
postgresql://neondb_owner:npg_TteR75HFXhpJ@ep-weathered-haze-a8l0ky65-pooler.eastus2.azure.neon.tech/neondb?sslmode=require
```

4. Click **"Update secret"**

---

## ✅ **Then Re-run the Workflow**

1. Go to: https://github.com/mikeadex/Ella-backend/actions
2. Click "Daily Job Scraper"
3. Click "Run workflow" → "Run workflow"
4. ✅ **It should work now!**

---

## 🔍 **What Happened**

The error showed:

```
could not translate host name "dpg-d3h1bc7fte5s73chnda0-a"
```

This is an **old Render database hostname** that no longer exists. Your current database is on **Neon** (ep-weathered-haze...).

---

## ✅ **Other Fixes Applied**

I also fixed:

- ✅ Django settings module: `ella_backend.settings` → `ella_writer.settings`
- ✅ SME scraper disabled (not implemented)
- ✅ Email notifications made optional

---

**Update the DATABASE_URL secret and try again!** 🚀
