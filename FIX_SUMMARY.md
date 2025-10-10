# CV Template Data Persistence Fix

## Problem Identified

User 'mall' and potentially other users have CVs with templates that **display** experience data (like "Accounts Assistant at Salford Accountancy Firm"), but this data is **NOT saved in the database tables**:

- `Experience` table: Empty (0 records)
- `Skill` table: Empty (0 records)

This causes the recommendation engine to return generic tech jobs for everyone because it can't detect their actual career field.

## Root Cause

There are **TWO separate data flows** that are disconnected:

### 1. Professional Summary Text (What's Currently Saved)

- Users can write/edit their professional summary
- Saved in `ProfessionalSummary` model as plain text
- Templates render this text, but it's not structured data
- **This is what user 'mall' has** - text saying "Accounts Assistant" but not in Experience table

### 2. Structured Experience/Skill Data (What's Missing)

- Should be saved in `Experience` and `Skill` tables
- Used by recommendation engine for job matching
- **This is what's missing** - no database records exist

## Current Data Flows That WORK

✅ **AI CV Parser → Transfer to Writer:**

- `ai_cv_parser/views.py` - `transfer_to_writer()` action
- Parses CV → Creates Experience/Skill records
- **This works for users who uploaded CVs through parser**

✅ **CV Rewrite Service:**

- `cv_writer/services.py` - `save_rewritten_cv_to_database()`
- Takes rewritten CV data → Creates Experience/Skill records
- **This works for users who used CV rewrite feature**

❌ **What's MISSING:**

- **Manual CV creation** - Users who manually enter data or use templates
- **Template application** - When templates are selected, no sample data is saved
- **Professional summary text parsing** - Text exists but isn't extracted to tables

## Solution: Add Post-Processing Hook

We need to add a **signal or post-save hook** that automatically extracts experience data from professional summary text and saves it to Experience/Skill tables.

### Implementation Options:

### Option 1: Automatic Text Parsing (Recommended)

When a `ProfessionalSummary` is saved, automatically parse it for:

- Job titles
- Company names
- Skills
- Dates

Then create corresponding `Experience` and `Skill` records.

### Option 2: Manual Data Entry Enforcement

Require users to fill out Experience/Skills in structured forms instead of just text.

### Option 3: Migration Script for Existing Users

Create a one-time script to parse existing professional summaries and populate tables.

## Immediate Fix Applied

Created `populate_mall_cv_data.py` script that:

1. ✅ Extracted "Accounts Assistant at Salford Accountancy Firm" from template
2. ✅ Created 1 Experience record
3. ✅ Created 8 relevant Skills records
4. ✅ Recommendation engine now works - detects "finance" field, recommends accounting jobs

## Next Steps

1. **Short-term:** Run similar population scripts for other affected users
2. **Long-term:** Implement Option 1 (automatic parsing) to prevent future issues
3. **Best practice:** Update CV creation flow to require structured data entry

## Files to Modify

1. `cv_writer/models.py` - Add signal handler for ProfessionalSummary
2. `cv_writer/services.py` - Add text parsing function
3. `cv_writer/views.py` - Update CV creation to validate Experience/Skill data exists
