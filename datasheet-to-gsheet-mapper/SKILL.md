---
name: datasheet-to-gsheet-mapper
description: >
  Maps and transforms local social media data CSVs (e.g. from Metricool) into
  ready-to-paste formats that match a Google Sheet's column structure exactly.
  Handles FB and IG data sheets, detects hidden columns, performs intelligent
  column matching, and produces clean CSVs with only visible columns.
  Triggers when the user asks about mapping data to a Google Sheet, preparing
  data for pasting into a Google Sheet, or creating ready-to-copy datasheets.
compatibility: |
  Requires Python 3.8+ with the `csv` standard library module (no external
  dependencies). Uses browser tools to read Google Sheet structure.
---

# Datasheet-to-GSheet Mapper — Gravitas Skill

This skill automates the process of taking raw social media analytics CSVs
(exported from tools like Metricool) and transforming them into perfectly
formatted, ready-to-paste CSVs that match the exact column structure of a
target Google Sheet — including handling hidden columns, column name
differences, and column ordering.

## When This Skill Triggers

Activate this skill when the user:
- Asks to "map data to a Google Sheet"
- Wants to "prepare data for pasting into a Google Sheet"
- Mentions "ready to copy" datasheets
- Asks to transform FB/IG/social media CSV data for a Google Sheet
- Wants to match local CSV columns with a Google Sheet's columns
- References copying data from Metricool exports to Google Sheets

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
Agent performs intelligent column matching
        ↓
Agent generates ready-to-paste CSVs (hidden columns excluded)
```

---

## STEP 0: Gather User Inputs

When the user invokes this skill (by providing context about mapping data to a
Google Sheet, or explicitly asking for it), the agent MUST ask the user the
following questions using the `ask_question` tool:

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

**Example interaction:**
```
User: "I want to map my May data to the Google Sheet"
Agent: [asks for Google Sheet link]
Agent: [asks which raw data files they have]
Agent: [asks for file paths]
User provides: Google Sheet URL, FB May.csv path, IG May.csv path
```

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
3. Try the published HTML variant: replace `/edit...` with `/pubhtml`
4. Try exporting as HTML: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=html`
5. Use `read_url_content` on the export URL

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

**Common hidden columns** (these are the columns that were hidden in previous
implementations — but you MUST verify by actually checking the sheet):
- **Columns A–D**: Industry, Country, Account Name, Account ID
- **Columns K–N**: Objective, Start Date, End Date, Ad Duration

> ⚠️ **CRITICAL**: Do NOT assume which columns are hidden. ALWAYS verify by
> inspecting the actual Google Sheet. The hidden columns may differ between
> sheets, clients, and time periods.

### 1.4 Record the Column Structure

For each tab (IG Data, FB Data), create two lists:
1. **`all_columns`**: Every column header in order (including hidden ones)
2. **`visible_columns`**: Only the columns that are NOT hidden, in order

**Example (from previous Setia implementation):**
```
IG Data — ALL columns (48):
  Industry, Country, Account Name, Account ID, Post ID, Permalink, Year,
  Quarter, Campaign, Organic/Paid, Objective, Start Date, End Date,
  Ad Duration, Post Name, Description, Pillar, Format, Duration (secs),
  Post Date, Publish Time, Total Reach, Organic Reach, Paid Reach,
  Total Views, Organic Views, Paid Views, Total Like, Organic Like,
  Paid Like, Total Comment, Organic Comment, Paid Comment, Total Share,
  Organic Share, Paid Share, Total Save, Organic Save, Paid Save,
  Total Engagement, Organic Engagement, Paid Engagement,
  Total Engagement %, Organic Engagement %, Paid Engagement %,
  Watch Time, Average Watch Time, Follow

IG Data — VISIBLE columns (40 — hidden columns A-D and K-N removed):
  Post ID, Permalink, Year, Quarter, Campaign, Organic/Paid, Post Name,
  Description, Pillar, Format, Duration (secs), Post Date, Publish Time,
  Total Reach, Organic Reach, Paid Reach, Total Views, Organic Views,
  Paid Views, Total Like, Organic Like, Paid Like, Total Comment,
  Organic Comment, Paid Comment, Total Share, Organic Share, Paid Share,
  Total Save, Organic Save, Paid Save, Total Engagement,
  Organic Engagement, Paid Engagement, Total Engagement %,
  Organic Engagement %, Paid Engagement %, Watch Time,
  Average Watch Time, Follow
```

---

## STEP 2: Read the Local CSV Files

### 2.1 Read the Raw CSV

Use `view_file` to read the local CSV file(s) provided by the user.

Extract the **header row** (first line) to get the column names from the raw
data.

### 2.2 Identify Summary/Aggregate Rows

Many Metricool exports include summary rows at the bottom (totals, engagement
rates, etc.). These rows should be **excluded** from the output.

**Detection rules:**
- Rows where the first identifying column (e.g., Post ID) is empty BUT
  numeric aggregate columns have values (totals)
- Rows containing "ER" or "Engagement Rate" labels
- Completely empty rows

> ⚠️ Strip summary/aggregate rows from the bottom of the data before mapping.

---

## STEP 3: Intelligent Column Matching

This is the most critical step. The raw CSV column names often differ from
the Google Sheet column names. The agent must perform **intelligent matching**
using the rules below.

### 3.1 Matching Strategy (in priority order)

1. **Exact match** (case-insensitive): `"Post ID"` ↔ `"Post ID"` ✅
2. **Known synonym/alias match**: Use the synonym table below
3. **Fuzzy/semantic match**: Match by meaning when names are clearly equivalent
4. **No match → empty column**: If no match is found, leave the column empty

### 3.2 Known Column Synonym Table

These are proven mappings from previous implementations. Use them as the
primary reference, but always verify against the actual data:

#### Instagram (IG) Column Mappings

| Google Sheet Column     | Raw CSV Column (Metricool)    | Notes                                    |
|------------------------|-------------------------------|------------------------------------------|
| Post ID                | Post ID                      | Direct match                             |
| Permalink              | Permalink                    | Direct match                             |
| Description            | Description                  | Direct match                             |
| Format                 | Format                       | Direct match                             |
| Duration (secs)        | Duration (sec)               | Plural difference                        |
| Post Date              | Date                         | "Date" in raw → "Post Date" in sheet     |
| Publish Time           | Publish time                 | Case difference                          |
| Total Reach            | Reach                        | "Reach" → "Total Reach"                  |
| Total Views            | Views                        | "Views" → "Total Views"                  |
| Total Like             | Likes                        | Singular/plural + "Total" prefix         |
| Total Comment          | Comments                     | Singular/plural + "Total" prefix         |
| Total Share            | Shares                       | Singular/plural + "Total" prefix         |
| Total Save             | Saves                        | Singular/plural + "Total" prefix         |
| Total Engagement       | E                            | "E" is short for Engagement              |
| Follow                 | Follows                      | Singular/plural difference               |

**IG columns that stay EMPTY** (no equivalent in raw data):
- Year, Quarter, Campaign, Organic/Paid, Post Name, Pillar
- Organic Reach, Paid Reach, Organic Views, Paid Views
- Organic Like, Paid Like, Organic Comment, Paid Comment
- Organic Share, Paid Share, Organic Save, Paid Save
- Organic Engagement, Paid Engagement
- Total Engagement %, Organic Engagement %, Paid Engagement %
- Watch Time, Average Watch Time

#### Facebook (FB) Column Mappings

| Google Sheet Column     | Raw CSV Column (Metricool)                          | Notes                              |
|------------------------|----------------------------------------------------|------------------------------------|
| Post ID                | Post ID                                            | Direct match                       |
| Permalink              | Permalink                                          | Direct match                       |
| Post Name              | Title                                              | "Title" → "Post Name"             |
| Description            | Description                                        | Direct match                       |
| Format                 | Format                                             | Direct match; "Videos"→keep as-is  |
| Duration (secs)        | Duration (sec)                                     | Plural difference                  |
| Post Date              | Date                                               | "Date" → "Post Date"              |
| Publish Time           | Publish time                                       | Case difference                    |
| Total Reach            | Total Reach                                        | Direct match                       |
| Total Views            | Total Views                                        | Direct match                       |
| Total Like             | Total like                                         | Case difference                    |
| Total Comment          | Total Comment                                      | Direct match                       |
| Total Share            | Total Share                                        | Direct match                       |
| Total Engagement       | E                                                  | "E" → engagement                   |
| Seconds Viewed         | Seconds viewed                                     | Case difference                    |
| Avg. Seconds Viewed    | Avg. Seconds viewed                                | Case difference                    |
| Link Click             | Link clicks                                        | Singular/plural difference         |

**FB columns that stay EMPTY** (no equivalent in raw data):
- Year, Quarter, Campaign, Organic/Paid, Pillar
- Organic Reach, Paid Reach, Organic Views, Paid Views
- Organic Like, Paid Like, Organic Comment, Paid Comment
- Organic Share, Paid Share
- Organic Engagement, Paid Engagement
- Total Engagement %, Organic Engagement %, Paid Engagement %
- Minutes Viewed, Avg. Minutes Viewed, Clicks To Play

### 3.3 Matching Rules for New/Unknown Sheets

When encountering a sheet that doesn't match the known mappings above, use
these heuristic rules:

1. **Strip "Total " prefix** when matching: `"Total Reach"` matches `"Reach"`
2. **Normalize plurals**: `"Likes"` matches `"Like"`, `"Views"` matches `"View"`
3. **Normalize case**: All comparisons are case-insensitive
4. **Normalize abbreviations**: `"secs"` ↔ `"sec"`, `"Avg."` ↔ `"Average"`
5. **Handle parenthetical variants**: `"Duration (sec)"` ↔ `"Duration (secs)"`
6. **"E" always maps to engagement**: `"E"` → `"Total Engagement"` or `"Engagement"`
7. **"Date" → "Post Date"**: When the sheet has "Post Date" and the CSV has "Date"
8. **"Title" → "Post Name"**: When the sheet has "Post Name" and the CSV has "Title"

> ⚠️ **NEVER force-match columns that don't logically correspond.** If unsure,
> leave the column empty. It's better to have an empty column than wrong data.

---

## STEP 4: Generate Ready-to-Copy CSV

### 4.1 Build the Output

Using the **visible_columns** list from Step 1 and the **column mappings**
from Step 3, generate a new CSV file where:

1. **Header row**: Exactly the visible column names from the Google Sheet
2. **Data rows**: For each row in the raw CSV:
   - For each visible column, either:
     - Fill with the mapped raw CSV value, OR
     - Leave empty if no mapping exists
3. **Column order**: Must be EXACTLY the same as the Google Sheet's visible
   column order (left to right)

### 4.2 Data Cleaning Rules

Apply these cleaning rules during generation:

1. **Strip summary rows**: Remove any aggregate/total rows from the bottom
2. **Preserve empty values**: If a cell is empty in the raw data, keep it empty
3. **Preserve data types**: Don't convert numbers to text or vice versa
4. **Handle multi-line descriptions**: Properly handle CSV quoting for
   descriptions that contain newlines, commas, or quotes
5. **No trailing commas**: Ensure consistent column count across all rows

### 4.3 Output File Naming Convention

Save the output files in the **same directory** as the raw CSV files:

```
{Platform}_{Period}_Ready_to_Copy_Visible_Only.csv
```

Examples:
- `IG_May_Ready_to_Copy_Visible_Only.csv`
- `FB_May_Ready_to_Copy_Visible_Only.csv`
- `IG_June_Ready_to_Copy_Visible_Only.csv`
- `FB_Q2_Ready_to_Copy_Visible_Only.csv`

The `{Period}` should be inferred from the raw file name. If the raw file is
`IG May.csv`, the period is `May`. If it's `FB June 2026.csv`, the period
is `June_2026`.

### 4.4 Generate Using Python Script

Use the provided Python script for accurate CSV generation:

```bash
python scripts/map_columns.py \
  --raw-csv "path/to/IG May.csv" \
  --visible-columns "Post ID,Permalink,Year,Quarter,..." \
  --column-map "Description=Description,Duration (secs)=Duration (sec),..." \
  --output "path/to/IG_May_Ready_to_Copy_Visible_Only.csv"
```

Or generate the CSV directly using inline Python (see Step 5 for the script).

---

## STEP 5: Python Script for CSV Generation

The agent should use Python to generate the CSVs. Here is the approach:

```python
import csv
import sys
import os

def map_and_generate_csv(
    raw_csv_path: str,
    visible_columns: list,
    column_map: dict,
    output_path: str,
    skip_summary_rows: bool = True
):
    """
    Read a raw CSV, map its columns to the Google Sheet structure,
    and output a ready-to-copy CSV.

    Args:
        raw_csv_path: Path to the raw Metricool CSV export
        visible_columns: List of visible column names from Google Sheet (in order)
        column_map: Dict mapping Google Sheet column name → raw CSV column name
        output_path: Path to save the output CSV
        skip_summary_rows: Whether to skip summary/aggregate rows at the bottom
    """
    # Read raw CSV
    with open(raw_csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        raw_headers = reader.fieldnames
        raw_rows = list(reader)

    # Find the identifying column in raw data (usually first column like "Post ID")
    id_col = raw_headers[0] if raw_headers else None

    # Filter out summary rows
    data_rows = []
    for row in raw_rows:
        if skip_summary_rows:
            # Skip rows where most identifying fields are empty (summary rows)
            id_val = row.get(id_col, '').strip() if id_col else ''
            # Check if this looks like a summary row
            non_empty = sum(1 for v in row.values() if v.strip())
            if not id_val and non_empty <= len(raw_headers) * 0.3:
                continue
        data_rows.append(row)

    # Generate output
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(visible_columns)

        # Write data rows
        for row in data_rows:
            out_row = []
            for col in visible_columns:
                if col in column_map:
                    raw_col = column_map[col]
                    out_row.append(row.get(raw_col, ''))
                else:
                    out_row.append('')  # No mapping → empty
            writer.writerow(out_row)

    print(f"File successfully saved to {output_path}")
    print(f"  Columns: {len(visible_columns)}")
    print(f"  Data rows: {len(data_rows)}")
```

---

## STEP 6: Verification

After generating the CSVs, the agent MUST verify:

### 6.1 Column Count Check
```
✓ Output CSV has exactly N columns (matching Google Sheet visible columns)
✓ Every row has exactly N fields
```

### 6.2 Data Integrity Check
```
✓ Number of data rows matches raw CSV (minus summary rows)
✓ Mapped columns contain actual data (not all empty)
✓ Empty columns are intentionally empty (no mapping exists)
✓ Multi-line descriptions are properly quoted
```

### 6.3 Report to User

After completion, report:
1. How many columns were matched vs. left empty
2. The exact column mapping used
3. Which columns are hidden (excluded)
4. The output file path
5. Instructions for pasting into Google Sheets

**Pasting Tip for the User:**
> When pasting into Google Sheets with hidden columns, first **unhide all
> columns** in the Google Sheet, paste the data, then **re-hide** the columns.
> This avoids Google Sheets pasting data into hidden columns and shifting
> everything.

---

## Rules for the Agent

1. **ALWAYS verify the Google Sheet structure live.** Never assume column
   positions, names, or which columns are hidden based on past runs.

2. **The synonym table is a STARTING POINT.** If the Google Sheet has different
   column names than expected, perform intelligent matching using the heuristic
   rules in Step 3.3.

3. **NEVER put wrong data into a column.** If you're not sure about a mapping,
   leave it empty and tell the user.

4. **Handle edge cases:**
   - Columns that exist in the raw data but NOT in the Google Sheet → ignore
   - Columns in the Google Sheet that have no equivalent in raw data → empty
   - Multiple possible matches → use the most semantically similar one

5. **Preserve the Google Sheet's exact column order.** This is critical for
   paste-to-work functionality.

6. **Exclude summary/aggregate rows** from the bottom of Metricool exports.

7. **Do NOT modify the Google Sheet.** This skill only READS the Google Sheet
   structure. All changes are made locally.

8. **Ask before overwriting** any existing ready-to-copy files.

9. **Process FB and IG independently.** They may have different column
   structures even within the same Google Sheet.

10. **The output CSV must be paste-ready.** The user should be able to select
    all cells in the output CSV, copy, and paste directly into the Google
    Sheet's visible area.

---

## Quick Reference — File Naming

| Input File        | Output File                                  |
|-------------------|----------------------------------------------|
| `IG May.csv`      | `IG_May_Ready_to_Copy_Visible_Only.csv`      |
| `FB May.csv`      | `FB_May_Ready_to_Copy_Visible_Only.csv`      |
| `IG June.csv`     | `IG_June_Ready_to_Copy_Visible_Only.csv`     |
| `FB June.csv`     | `FB_June_Ready_to_Copy_Visible_Only.csv`     |
| `IG Q2 2026.csv`  | `IG_Q2_2026_Ready_to_Copy_Visible_Only.csv`  |

---

## Troubleshooting

### Google Sheet requires sign-in
Ask the user to:
1. Open the Google Sheet
2. Click Share → General Access → "Anyone with the link" → Viewer
3. Copy the link and provide it again

### Column names don't match anything
1. Print both column lists side by side
2. Ask the user to manually confirm the mapping
3. Use the confirmed mapping to proceed

### CSV has encoding issues
Try reading with `encoding='utf-8-sig'` first, then `encoding='latin-1'`.
Metricool exports are typically UTF-8 with BOM.

### Multi-line descriptions break the CSV
Ensure Python's `csv` module is used (it handles quoting automatically).
Never try to manually construct CSV strings.
