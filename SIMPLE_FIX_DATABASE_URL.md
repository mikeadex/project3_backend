# ⚠️ DATABASE_URL IS EMPTY - Step-by-Step Fix

**Current Status**: DATABASE_URL secret is NOT working in GitHub Actions

---

## 📱 **DO THIS RIGHT NOW (Takes 2 Minutes)**

### **STEP 1: Click This Exact Link**

```
https://github.com/mikeadex/project3_backend/settings/secrets/actions
```

👆 **CLICK IT NOW** - This takes you to your repository secrets

---

### **STEP 2: Look at the Page**

You should see a list of "Repository secrets" with names like:

- DATABASE_URL
- REED_API_KEY
- SECRET_KEY
- etc.

**DO YOU SEE `DATABASE_URL` IN THE LIST?**

---

## 🔴 **SCENARIO A: I SEE "DATABASE_URL" in the list**

1. **Click the pencil icon** ✏️ next to DATABASE_URL
2. You'll see a text box with the current value
3. **Select ALL the text** (Ctrl+A or Cmd+A)
4. **DELETE everything**
5. **Copy this ENTIRE line** (click to select, then copy):
   ```
   postgresql://neondb_owner:npg_TteR75HFXhpJ@ep-weathered-haze-a8l0ky65-pooler.eastus2.azure.neon.tech/neondb?sslmode=require
   ```
6. **Paste it** into the value field
7. **Make sure there are NO spaces before or after**
8. Click **"Update secret"** button
9. You should see: "Secret DATABASE_URL was updated"

---

## 🟢 **SCENARIO B: I DON'T SEE "DATABASE_URL" in the list**

1. Click the green button **"New repository secret"**
2. In the "Name" field, type EXACTLY: `DATABASE_URL`
   - **Must be ALL CAPS**
   - **Must have underscore (\_) not dash (-)**
   - **Must be exactly: D-A-T-A-B-A-S-E-\_-U-R-L**
3. In the "Secret" field, **paste this**:
   ```
   postgresql://neondb_owner:npg_TteR75HFXhpJ@ep-weathered-haze-a8l0ky65-pooler.eastus2.azure.neon.tech/neondb?sslmode=require
   ```
4. Click **"Add secret"** button
5. You should see DATABASE_URL appear in your list

---

## ✅ **STEP 3: Verify Other Secrets Exist**

While you're on that page, **check these secrets are also there**:

- [ ] `SECRET_KEY` - Should exist
- [ ] `REED_API_KEY` - Should exist
- [ ] `DEEPSEEK_API_KEY` - Should exist
- [ ] `ALLOWED_HOSTS` - Should exist

**If ANY are missing**, click "New repository secret" and add them:

**SECRET_KEY**:

```
cG9wcTJjKV5ebG96XnM3YWUld3NmMz10IXQoPWw3Y2JmNSFzenEmcl4wXnBnKj10bQ==
```

**REED_API_KEY**:

```
78341a75-e20b-41f5-ad6f-2051f4dbbba1
```

**DEEPSEEK_API_KEY**:

```
sk-72efdda392064447b46db563f3bebb0a
```

**ALLOWED_HOSTS**:

```
www.ellacvwriter.com,ellacvwriter.com,localhost
```

---

## 🧪 **STEP 4: Test It**

1. Go to: https://github.com/mikeadex/project3_backend/actions
2. Click on **"Daily Job Scraper"** (left sidebar)
3. Click the blue **"Run workflow"** button (top right)
4. Click the green **"Run workflow"** button in the dropdown
5. **Wait 10 seconds**, then **refresh the page**
6. Click on the running workflow

### **Look for this NEW step (I just added it)**:

```
🔐 Verify Environment Variables
```

**You should see:**

```
✅ DATABASE_URL is set (length: 150 characters)
✅ REED_API_KEY is set
✅ SECRET_KEY is set
```

**If you see:**

```
❌ ERROR: DATABASE_URL is not set!
```

Then **GO BACK TO STEP 1** - the secret is still not configured!

---

## 🚨 **Common Mistakes - DON'T DO THESE**

❌ **Secret name**: `database_url` (wrong - must be ALL CAPS)  
❌ **Secret name**: `DATABASE-URL` (wrong - must use underscore \_)  
❌ **Secret value**: Has spaces before/after the URL  
❌ **Secret value**: Is empty/blank  
❌ **Wrong repo**: You're looking at a different repository's secrets

---

## 📸 **What Success Looks Like**

After adding DATABASE_URL, your secrets page should show:

```
Repository secrets (5)

ALLOWED_HOSTS        Updated 1 minute ago
DATABASE_URL         Updated just now  ← THIS ONE!
DEEPSEEK_API_KEY     Updated 1 minute ago
REED_API_KEY         Updated 1 minute ago
SECRET_KEY           Updated 1 minute ago
```

---

## 🎯 **After You Fix It**

The workflow will:

1. ✅ Verify DATABASE_URL exists (new step!)
2. ✅ Connect to Neon database
3. ✅ Run Reed scraper → ~100 jobs
4. ✅ Run DWP scraper → ~50 jobs
5. ✅ Show statistics
6. ✅ Green checkmark!

---

## 🆘 **STILL NOT WORKING?**

If you've done ALL the steps above and it STILL says DATABASE_URL is empty:

1. **Take a screenshot** of your GitHub Secrets page showing DATABASE_URL in the list
2. **Click the pencil icon** next to DATABASE_URL
3. **Copy the first 20 characters** of the value (e.g., `postgresql://neondb_o...`)
4. **Tell me what you see** - we'll debug together

---

**👉 DO STEP 1 NOW: Click the GitHub Secrets link and check if DATABASE_URL exists!**

Then re-run the workflow and look for the "🔐 Verify Environment Variables" step.
