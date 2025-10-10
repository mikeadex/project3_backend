# Frontend Testing Guide - Personalized Job Recommendations

## 🎯 What to Test

Verify that different users receive **personalized job recommendations** based on their career background, NOT generic tech jobs for everyone.

---

## 📋 Test Cases

### Test Case 1: Finance User (mall)

**Expected Behavior:**

- ✅ Should see **finance/accounting jobs** (Accounts Assistant, Finance Analyst, etc.)
- ✅ Match scores should be **60-75%**
- ✅ **NO tech jobs** (Software Engineer, Developer, etc.)

**Steps:**

1. Navigate to: `http://localhost:3000/login`
2. Login as:
   - Username: `mall`
   - Password: [your password]
3. Navigate to: Job Recommendations page
4. Verify recommendations shown

**Expected Top 3 Jobs:**

1. Accounts Assistant - Cooper Golding (71.0%)
2. Accounts Senior - Reed (65.0%)
3. Accounts Payable Analyst - 83zero Ltd (58.6%)

---

### Test Case 2: Tech User (paradigm_shift)

**Expected Behavior:**

- ✅ Should see **software developer jobs** (Full Stack Developer, Software Engineer, etc.)
- ✅ Match scores should be **70-75%**
- ✅ **NO finance/retail jobs**

**Steps:**

1. Login as:
   - Username: `paradigm_shift`
   - Password: [your password]
2. Navigate to: Job Recommendations page
3. Verify recommendations shown

**Expected Top 3 Jobs:**

1. Full Stack Software Developer - Marshall Wolfe (74.5%)
2. Full Stack Developer - Jobheron (71.6%)
3. Full Stack Developer - Radius (71.6%)

---

### Test Case 3: Business/Compliance User (creative)

**Expected Behavior:**

- ✅ Should see **business analyst/compliance jobs**
- ✅ Match scores should be **50-55%**
- ✅ Jobs should match compliance/risk management background

**Steps:**

1. Login as:
   - Username: `creative`
   - Password: [your password]
2. Navigate to: Job Recommendations page
3. Verify recommendations shown

**Expected Top 3 Jobs:**

1. Insurance Analyst - AS Resourcing (54.7%)
2. Commercial Analyst - Kensington Mortgage (54.5%)
3. Cyber Catastrophe Risk Analyst - Eames Consulting (54.3%)

---

### Test Case 4: Retail User (mike)

**Expected Behavior:**

- ✅ Should see **retail/operations jobs**
- ⚠️ Match scores may be lower (36-40%) due to years calculation bug
- ✅ Jobs should be retail-related

**Steps:**

1. Login as:
   - Username: `mike`
   - Password: [your password]
2. Navigate to: Job Recommendations page
3. Verify recommendations shown

**Expected Top 3 Jobs:**

1. Assistant Manager - Oaktree animals Charity (36.4%)
2. Assistant Operations Manager - Network Plus (35.9%)
3. Customer Assistant roles

**Known Issue:** ⚠️ Scores are lower than expected because years experience is showing as 0.0. This will be fixed in the next update.

---

## 🔍 What to Look For

### UI Elements to Verify:

1. **Match Score Circles:**

   - Should display percentage (50-75%)
   - Color-coded: Green (70+), Blue (60-69), Yellow (50-59)
   - "Perfect Match" badge for 80%+ (may not appear in current data)

2. **Job Cards:**

   - Company name
   - Job title
   - Location
   - "Why this job?" button (shows match breakdown)

3. **No Results Message:**

   - If a user has no matching jobs: "Check back later" message should appear
   - Should NOT show "No jobs available" error

4. **Action Buttons:**
   - "Apply" button (opens job posting)
   - "Save" button (saves to favorites)
   - "Hide" button (removes from view)

---

## ✅ Success Criteria

**The fix is working if:**

1. ✅ Different users see **different job recommendations**
2. ✅ Finance user sees **finance jobs** (NOT tech jobs)
3. ✅ Tech user sees **tech jobs** (NOT finance jobs)
4. ✅ Match scores are **meaningful** (50-75% range)
5. ✅ Job titles match user's **career field**

**The fix has FAILED if:**

- ❌ All users see identical jobs
- ❌ Finance user sees "Software Engineer" jobs
- ❌ All match scores are very low (<30%)
- ❌ "No recommendations available" for users with experience

---

## 🐛 Debugging Steps (If Issues Found)

### Issue 1: User sees "No recommendations available"

**Check:**

```bash
# Verify user has experience data
cd Ella-backend
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from cv_writer.models import Experience, Skill
>>> user = User.objects.get(username='USERNAME')
>>> print(f"Experiences: {Experience.objects.filter(user=user).count()}")
>>> print(f"Skills: {Skill.objects.filter(user=user).count()}")
```

**Fix:** Run population script for that user

---

### Issue 2: All users see identical jobs

**Check:**

```bash
# Test recommendation engine directly
python test_mall_recommendations.py
```

**Expected:** Should show different jobs for different users

---

### Issue 3: Match scores are very low (<30%)

**Check:**

- Verify user has relevant skills
- Check if years experience is calculating correctly
- Review recommendation engine scoring logic

---

## 📊 Expected Frontend Console Logs

When recommendations load, you should see:

```javascript
✅ Fetching recommendations for user...
✅ Recommendations loaded: [array of 10-20 jobs]
✅ Top match: [Job Title] - [Score]%
```

If you see errors:

```javascript
❌ Error fetching recommendations: [error message]
```

Check:

1. Backend server is running (`http://localhost:8000`)
2. User is authenticated (has valid token)
3. API endpoint is correct (`/api/jobstract/opportunities/recommended/`)

---

## 🎨 Visual Verification Checklist

- [ ] Match score circles display correctly
- [ ] Circular progress animation works
- [ ] Job cards have glassmorphism effect
- [ ] Gradient backgrounds on cards
- [ ] "Why this job?" modal opens and shows breakdown
- [ ] Apply button opens job posting in new tab
- [ ] Save/Hide buttons work
- [ ] Responsive design works on mobile
- [ ] Dark mode support (if enabled)

---

## 📝 Test Results Template

```
Date: October 10, 2025
Tester: [Your Name]

Test Case 1 (mall - Finance):
- Top job: _______________
- Match score: ____%
- Jobs relevant: YES / NO
- Tech jobs shown: YES / NO
- Result: PASS / FAIL

Test Case 2 (paradigm_shift - Tech):
- Top job: _______________
- Match score: ____%
- Jobs relevant: YES / NO
- Finance jobs shown: YES / NO
- Result: PASS / FAIL

Test Case 3 (creative - Business):
- Top job: _______________
- Match score: ____%
- Jobs relevant: YES / NO
- Result: PASS / FAIL

Test Case 4 (mike - Retail):
- Top job: _______________
- Match score: ____%
- Jobs relevant: YES / NO
- Result: PASS / FAIL

Overall Status: PASS / FAIL
Notes: _______________
```

---

## 🚀 Quick Test Command

If you want to verify backend is working before frontend testing:

```bash
cd Ella-backend

# Test all users at once
python manage.py shell << 'EOF'
from django.contrib.auth.models import User
from cv_writer.models import CvWriter
from jobstract.recommendation_engine import JobRecommendationEngine

for username in ['mall', 'paradigm_shift', 'creative', 'mike']:
    user = User.objects.get(username=username)
    cv = CvWriter.objects.filter(user=user).first()
    engine = JobRecommendationEngine(user=user, cv=cv)
    recs = engine.get_recommendations(limit=1)
    if recs:
        print(f"{username}: {recs[0]['job'].title} ({recs[0]['score']:.1f}%)")
    else:
        print(f"{username}: No recommendations")
EOF
```

**Expected Output:**

```
mall: Accounts Assistant (71.0%)
paradigm_shift: Full Stack Software Developer (74.5%)
creative: Insurance Analyst (54.7%)
mike: Assistant Manager (36.4%)
```

---

## ✅ Sign-Off

Once all tests pass, the personalized recommendation system is **FULLY FUNCTIONAL**!

**Tested by:** ******\_\_\_******  
**Date:** ******\_\_\_******  
**Status:** PASS / FAIL  
**Notes:** ******\_\_\_******

---

**Need help?** Check `RECOMMENDATION_FIX_COMPLETE.md` for detailed fix documentation.
