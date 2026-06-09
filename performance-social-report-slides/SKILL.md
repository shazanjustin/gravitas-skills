---
name: social-report-slides
description: Generates a PPTX slide deck and an HTML thumbnail gallery from a social media quarterly report Excel file. One slide per post, covering Instagram, TikTok, and YouTube campaigns. This skill should be used when a user provides a social media performance report in .xlsx format and wants to turn it into presentation slides or view post thumbnails.
---

# Social Report Slides

Converts a social media quarterly performance report (.xlsx) into:
1. A **PPTX slide deck** -- one slide per post, with platform header, reporting period, data table, auto-generated insights, and thumbnail placeholder.
2. An **HTML thumbnail gallery** -- all posts displayed with Instagram iframe embeds, organised by slide number and month.

## When to Use

Trigger this skill when the user:
- Provides a .xlsx social media report and asks for slides, a deck, or a presentation
- Asks to generate thumbnails or a thumbnail page from a report
- Mentions "one slide per post", "performance slides", or "quarterly report slides"

## Prerequisites

Ensure these Python packages are installed:
    pip install python-pptx pandas openpyxl pillow lxml

## Generating the PPTX Slide Deck

Run scripts/generate_slides.py with the Excel file path:

    python scripts/generate_slides.py --excel "path/to/report.xlsx"

Optional arguments:
- --output "path/to/output.pptx"  (default: same dir as Excel, _slides.pptx suffix)
- --sheet "SheetName"              (default: auto-detects first sheet)
- --year 2026                       (default: auto-detected from filename)

### Slide Layout (13.33" x 7.5" widescreen)

Each slide contains:
- Black header bar -- platform name (INSTAGRAM / TIKTOK / YOUTUBE PERFORMANCE) + logo top right
- Reporting period subtitle -- red italic, parsed from campaign name string (|DD-Mon|DD-Mon pattern)
- Data table -- red header row, alternating white/light-grey rows
- Insights box -- red-bordered, 3 auto-generated bullet points
- Thumbnail placeholder -- grey box bottom right, labelled [Thumbnail]

### Column Sets

Instagram / TikTok (13 cols): Campaign name, Placement, Amount spent (MYR), Impressions,
Reach, Frequency, Post comments, Post shares, Post reactions, Post engagements, Post saves,
Clicks (all), Views.

TikTok maps: Paid likes to Post reactions, Paid comments to Post comments, Paid shares to
Post shares. Post engagements and Post saves show "-" (not available in TikTok data).

YouTube (11 cols): Campaign, Objective, Impressions, Reach, Amount spent (MYR), Engagements,
TrueView views, Engagement rate, Video played to 25/50/75/100%.

See references/excel_structure.md for full column index mappings.

## Generating the HTML Thumbnail Gallery

    python scripts/generate_thumbnails.py --excel "path/to/report.xlsx"

Optional arguments:
- --output "path/to/output.html"  (default: same dir as Excel, _thumbnails.html suffix)
- --sheet "SheetName"              (default: auto-detects first sheet)

Open the .html file in any browser. Instagram posts render as live iframes (no login needed
for public posts). TikTok and YouTube show a placeholder card. Posts with missing links
(90-day retention) show a warning card.

## Excel Structure

Expects a monthly breakdown section with campaign blocks separated by platform header rows.
See references/excel_structure.md for the full layout, column indices, and link matching logic.

## Adapting for a Different Report

If column positions differ in a new report:
1. Read references/excel_structure.md to understand the current expected format
2. Inspect the new file: pd.read_excel(path, header=None) to find actual column indices
3. Update IG_COLS, TT_COLS, YT_COLS in scripts/generate_slides.py
4. Month labels and block detection are flexible -- they look for string markers
