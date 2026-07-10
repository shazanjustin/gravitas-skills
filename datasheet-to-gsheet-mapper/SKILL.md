---
name: datasheet-to-gsheet-mapper
description: >
  Maps and transforms local social media data CSVs (e.g. from Facebook/IG
  platform exports) into ready-to-paste formats that match a Google Sheet's
  column structure exactly. Handles FB and IG data sheets, detects hidden
  columns, performs intelligent column matching, fills Description from Title
  (FB), maps Post type to Format, formats Publish Time as mm/dd/yyyy HH:MM,
  sorts rows oldest-first, and produces clean CSVs with only visible columns.
  Triggers when the user asks about mapping data to a Google Sheet, preparing
  data for pasting into a Google Sheet, or creating ready-to-copy datasheets.
compatibility: |
  Requires Python 3.8+ with the `csv` and `datetime` standard library modules
  (no external dependencies). Uses browser/URL tools to read Google Sheet
  structure.
---

# Datasheet-to-GSheet Mapper — Gravitas Skill

This skill automates the process of taking raw social media analytics CSVs
(exported from Facebook/Instagram platform tools) and transforming them into
perfectly formatted, ready-to-paste CSVs that match the exact column structure
of a target Google Sheet — including handling hidden columns, column name
differences, description fallback logic, format mapping, datetime formatting,
and row sorting.

## When This Skill Triggers

Activate this skill when the user:
- Asks to "map data to a Google Sheet"
- Wants to "prepare data for pasting into a Google Sheet"
- Mentions "ready to copy" datasheets
- Asks to transform FB/IG/social media CSV data for a Google Sheet
- Wants to match local CSV columns with a Google Sheet's columns
- References copying data from platform exports to Google Sheets

## Workflow Overview

```
User provides Google Sheet link
        ↓
Agent asks for raw data files (FB CSV, IG CSV)
        ↓
Agent reads Google Sheet → extracts column structure for each tab
        ↓
Agent detects hidden columns in Google Sheet
        ↓
Agent reads local CSV files → extracts their column structure
        ↓
Agent performs intelligent column matching (with special rules below)
        ↓
Agent generates ready-to-paste CSVs (hidden columns excluded, sorted oldest-first)
        ↓
Agent delivers output files with clear paste instructions
```

---

## STEP 0: Gather User Inputs

When the user invokes this skill, the agent MUST ask the user the following
questions using the `ask_question` tool:

### Question 1: Google Sheet Link
> **Please provide the Google Sheet link**
> (The sheet must be publicly accessible or shared with "Anyone with the link")

### Question 2: Raw Data Files
> **Please provide the paths to your raw data files**
> Options:
> - I have both FB and IG CSV files
> - I only have an FB CSV file
> - I only have an IG CSV file

Then ask the user to provide the file path(s) for the raw CSV file(s).

> ⚠️ **IMPORTANT**: The agent must NEVER proceed without getting ALL required
> inputs. If the user only provides one file, only process that platform.

---

## STEP 1: Read the Google Sheet Structure

### 1.1 Access the Google Sheet

Navigate to the Google Sheet using the browser. The sheet **must be public**.
If it requires sign-in, ask the user to make it public first.

**Fallback methods** (try in order):
1. Open the sheet URL directly in the browser
2. Try the `/htmlview` variant: replace `/edit...` with `/htmlview`
3. Try the per-sheet HTML: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview/sheet?headers=true&gid={GID}`
4. Use `read_url_content` on the htmlview URL

### 1.2 Navigate to the Correct Tab

The Google Sheet will typically have tabs/sheets named:
- **"IG Data"** — for Instagram post data
- **"FB Data"** — for Facebook post data

Navigate to each relevant tab and extract:
1. **ALL column headers** (visible AND hidden) — in exact left-to-right order
2. **Which columns are hidden** — by detecting gaps in the column letter sequence

### 1.3 Detect Hidden Columns

Hidden columns are identified by **gaps in the column letter sequence**. For
example, if visible columns jump from D to I, then columns E–H are hidden.

The HTML source of the htmlview page lists column letters in `<th id="...Cxx">` 
tags. Parse these to find the gap pattern.

**Common hidden columns** (verify ALWAYS — do not assume):
- **Columns A–D**: Industry, Country, Account Name, Account ID
- **Columns K–N**: Objective, Start Date, End Date, Ad Duration

> ⚠️ **CRITICAL**: Do NOT assume which columns are hidden. ALWAYS verify by
> inspecting the actual Google Sheet. The hidden columns may differ between
> sheets, clients, and time periods.

### 1.4 Record the Column Structure

For each tab (IG Data, FB Data), create two lists:
1. **`all_columns`**: Every column header in order (including hidden ones)
2. **`visible_columns`**: Only the columns that are NOT hidden, in order

**Example (Setia implementation — verified):**
```
FB Data — VISIBLE columns (36):
  Post ID, Permalink, Year, Quarter, Campaign, Organic/Paid,
  Post Name, Description, Pillar, Format, Duration (secs), Post Date,
  Publish Time, Total Reach, Organic Reach, Paid Reach, Total Views,
  Organic Views, Paid Views, Total Like, Organic Like, Paid Like,
  Total Comment, Organic Comment, Paid Comment, Total Share,
  Organic Share, Paid Share, Total Engagement, Organic Engagement,
  Paid Engagement, Total Engagement %, Organic Engagement %,
  Paid Engagement %, Watch Time, Average Watch Time

IG Data — VISIBLE columns (40):
  Post ID, Permalink, Year, Quarter, Campaign, Organic/Paid,
  Post Name, Description, Pillar, Format, Duration (secs), Post Date,
  Publish Time, Total Reach, Organic Reach, Paid Reach, Total Views,
  Organic Views, Paid Views, Total Like, Organic Like, Paid Like,
  Total Comment, Organic Comment, Paid Comment, Total Share,
  Organic Share, Paid Share, Total Save, Organic Save, Paid Save,
  Total Engagement, Organic Engagement, Paid Engagement,
  Total Engagement %, Organic Engagement %, Paid Engagement %,
  Watch Time, Average Watch Time, Follow
```

---

## STEP 2: Read the Local CSV Files

### 2.1 Read the Raw CSV

Use `view_file` to read the local CSV file(s) provided by the user.
Extract the **header row** (first line) to get all available column names.

### 2.2 Identify Summary/Aggregate Rows

Platform exports often include summary rows at the bottom. These must be
**excluded** from the output.

**Detection rules:**
- Rows where Post ID is empty
- Rows where Post ID contains non-numeric text labels (e.g. "Total", "ER")
- Completely empty rows

> ⚠️ Strip ALL summary/aggregate rows before processing.

---

## STEP 3: Column Mapping Rules

Apply the following intelligent column mapping when building each output row.

### 3.1 FB Column Mapping

| Raw FB CSV Column | GSheet Column | Notes |
|---|---|---|
| Post ID | Post ID | |
| Permalink | Permalink | |
| Title | Description | **Primary source** — use first |
| Description | Description | **Fallback** — only use if Title is empty |
| Post type | Format | e.g. "Photos", "Video", "Link" |
| Duration (sec) | Duration (secs) | |
| Publish time | Publish Time | Format as `mm/dd/yyyy HH:MM` (full datetime) |
| Publish time (date part) | Post Date | Extract date → format as `dd/mm/yyyy` |
| Publish time (year) | Year | e.g. "2026" |
| Publish time (quarter) | Quarter | Derive: Jan-Mar=Q1, Apr-Jun=Q2, Jul-Sep=Q3, Oct-Dec=Q4 |
| Reach | Total Reach | |
| Reach from Organic posts | Organic Reach | |
| Reach from Boosted posts | Paid Reach | |
| Views | Total Views | |
| Views from Organic posts | Organic Views | |
| Views from Boosted posts | Paid Views | |
| Reactions | Total Like | |
| Comments | Total Comment | |
| Shares | Total Share | |
| Reactions, comments and shares | Total Engagement | |
| Seconds viewed | Watch Time | |
| Average Seconds viewed | Average Watch Time | |

**FB special rule — Description fallback:**
```
if Title column is not empty:
    Description = Title
else:
    Description = Description column
```

**Columns left blank** (require manual editorial input):
- Post Name, Pillar, Campaign, Organic/Paid (default to "Organic"), Objective,
  Organic Like, Paid Like, Organic Comment, Paid Comment, Organic Share,
  Paid Share, Organic Engagement, Paid Engagement, Total Engagement %,
  Organic Engagement %, Paid Engagement %

### 3.2 IG Column Mapping

| Raw IG CSV Column | GSheet Column | Notes |
|---|---|---|
| Post ID | Post ID | |
| Permalink | Permalink | |
| Description | Description | |
| Post type | Format | e.g. "IG image", "IG carousel", "IG reel" |
| Duration (sec) | Duration (secs) | |
| Publish time | Publish Time | Format as `mm/dd/yyyy HH:MM` (full datetime) |
| Publish time (date part) | Post Date | Extract date → format as `dd/mm/yyyy` |
| Publish time (year) | Year | e.g. "2026" |
| Publish time (quarter) | Quarter | Derive: Q1–Q4 |
| Reach | Total Reach | |
| Views | Total Views | |
| Likes | Total Like | |
| Comments | Total Comment | |
| Shares | Total Share | |
| Saves | Total Save | |
| Follows | Follow | |

**Columns left blank** (require manual editorial input):
- Post Name, Pillar, Campaign, Organic/Paid (default to "Organic"),
  Organic Reach, Paid Reach, Organic Views, Paid Views, Organic Like,
  Paid Like, Organic Comment, Paid Comment, Organic Share, Paid Share,
  Organic Save, Paid Save, Organic Engagement, Paid Engagement,
  Total Engagement %, Organic Engagement %, Paid Engagement %, Watch Time,
  Average Watch Time

---

## STEP 4: Generate Output CSVs

Write a Python script (no external dependencies) that:

1. Reads each raw CSV
2. Strips summary/aggregate rows
3. Applies the column mapping rules above
4. Sets `Organic/Paid` = "Organic" by default if empty
5. Derives `Post Date`, `Year`, `Quarter` from `Publish time`
6. Formats `Publish Time` as `mm/dd/yyyy HH:MM` (full datetime, NOT time-only)
7. **Sorts all rows by Post Date ascending (oldest post first)**
8. Writes only the GSheet visible columns, in GSheet column order
9. Saves output as:
   - `FB_mapped.csv` — same folder as input FB CSV
   - `IG_mapped.csv` — same folder as input IG CSV
10. Uses `utf-8-sig` encoding (Excel-compatible BOM)

**Publish time parsing** — handle multiple formats:
```python
for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
            "%d/%m/%Y %H:%M", "%m/%d/%Y", "%d-%b-%y %H:%M", "%b %d, %Y"):
    try:
        dt = datetime.datetime.strptime(s.strip(), fmt)
        break
    except ValueError:
        continue
```

---

## STEP 5: Deliver Output with Paste Instructions

After generating the output files, the agent MUST provide the user with:

### 5.1 Output Summary Table

| File | Rows | Tab in GSheet |
|---|---|---|
| FB_mapped.csv | N rows | FB Data |
| IG_mapped.csv | N rows | IG Data |

### 5.2 Step-by-Step Paste Instructions

Deliver these instructions clearly every time:

---

**How to paste into the Google Sheet:**

**PART 1 — Paste columns: Post ID → Organic/Paid (columns E to J)**

These 6 columns paste directly without conflicting with hidden columns:

1. Open `FB_mapped.csv` (or IG) in **Excel**
2. Select columns **A to F** (Post ID, Permalink, Year, Quarter, Campaign, Organic/Paid) — data rows only, **no header**
3. Press `Ctrl+C`
4. In the Google Sheet, go to the **FB Data** tab (or IG Data)
5. Click the **first empty cell in column E** (Post ID column) of the next empty row
6. Press `Ctrl+Shift+V` → select **"Paste values only"**

**PART 2 — Paste remaining columns: Post Name → last column (column O onwards)**

1. Back in Excel, select from column **G onwards** (Post Name, Description, Pillar, Format, Duration, Post Date, Publish Time, and all metric columns) — data rows only, **no header**
2. Press `Ctrl+C`
3. In the Google Sheet, click the **first empty cell in column O** of the same rows you just pasted into
4. Press `Ctrl+Shift+V` → **"Paste values only"**

> ⚠️ **Why two separate pastes?** Columns K–N are hidden in the Google Sheet.
> If you paste all at once starting from column E, the data will misalign at
> column K. Splitting into two pastes avoids this problem entirely.

> ⚠️ **Always use Paste Values Only** (`Ctrl+Shift+V`) — never plain `Ctrl+V`,
> as that will overwrite cell formatting.

---

### 5.3 Columns Requiring Manual Fill-in

Remind the user that these columns are intentionally left blank and need
manual editorial input after pasting:

- **Post Name** — the creative/campaign name for the post
- **Pillar** — content pillar category
- **Campaign** — campaign name (if applicable)
- **Organic Like / Paid Like**, **Organic Comment / Paid Comment**, etc. — organic/paid splits for engagement metrics (FB only, if boosted)

---

## Field Reference: Raw Platform CSV → GSheet Column Names

### FB Platform Export Key Columns
```
Post ID              → Post ID
Title                → Description (PRIMARY — use this first)
Description          → Description (FALLBACK — only if Title empty)
Post type            → Format
Publish time         → Publish Time (as mm/dd/yyyy HH:MM) + derive Post Date/Year/Quarter
Reach                → Total Reach
Reach from Organic posts  → Organic Reach
Reach from Boosted posts  → Paid Reach
Views                → Total Views
Views from Organic posts  → Organic Views
Views from Boosted posts  → Paid Views
Reactions            → Total Like
Comments             → Total Comment
Shares               → Total Share
Reactions, comments and shares → Total Engagement
Seconds viewed       → Watch Time
Average Seconds viewed → Average Watch Time
```

### IG Platform Export Key Columns
```
Post ID    → Post ID
Permalink  → Permalink
Description → Description
Post type  → Format
Publish time → Publish Time (as mm/dd/yyyy HH:MM) + derive Post Date/Year/Quarter
Reach      → Total Reach
Views      → Total Views
Likes      → Total Like
Comments   → Total Comment
Shares     → Total Share
Saves      → Total Save
Follows    → Follow
```
