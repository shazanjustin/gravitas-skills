---
name: metricool-engagement-rate-xlsx
description: Build Metricool per-post engagement-rate proof workbooks for Instagram and TikTok. Use when a user asks for average engagement rate, engagement rate over reach, ER/reach, per-post proof, or an XLSX export from Metricool for owned social accounts.
compatibility: Requires Python 3.8+, openpyxl, and Metricool credentials via METRICOOL_TOKEN or an existing metricool/.env file. Uses GET-only Metricool API calls.
---

# Metricool Engagement Rate XLSX

Use this skill to create client-ready Excel proof files showing per-post engagement rate and average engagement rate for Instagram and TikTok using Metricool data.

## When to also load other skills

Always also load the `metricool` skill because this workflow uses Metricool credentials, brands, and API endpoints.

## Output

The workbook contains:
- `Summary` — post counts, total engagements, average ER, weighted ER
- `Instagram Proof` — combined Instagram feed + reels per-post proof
- `TikTok Proof` — TikTok per-video proof
- `IG Feed Raw Proof` — Instagram feed only
- `IG Reels Raw Proof` — Instagram reels only

## Engagement-rate formula

Default formula:

```text
Engagement Rate = (likes + comments + shares + saves) / reach
```

Network notes:
- Instagram: use Metricool `reach` as the denominator.
- TikTok: Metricool’s post endpoint exposes `viewCount`, not reach. Use `viewCount` as the reach proxy unless the user provides another denominator.
- Rows with denominator `0` or missing denominator are excluded from average ER, but remain in the proof tab.
- `Average ER` is the simple average of post-level ERs.
- `Weighted ER` is also included for reference: total engagements / total reach-or-views.

## Required confirmations

If the user has not specified these, ask before running:
1. Brand/account or Metricool `blogId`
2. Date range
3. Whether TikTok views are acceptable as the reach proxy

If the user says “until today”, use the current system date.

## Brand discovery

Use the Metricool helper to discover brands:

```bash
cd metricool
bash scripts/metricool.sh brands
bash scripts/metricool.sh info <blogId>
```

Do not hardcode brand IDs in the skill instructions. For a one-off report, it is okay to use the discovered `blogId` in the command.

## Build the workbook

From the repository root:

```bash
python metricool-engagement-rate-xlsx/scripts/build_metricool_engagement_xlsx.py \
  --blog-id <blogId> \
  --brand "<Brand Name>" \
  --from YYYY-MM-DD \
  --to today
```

Example:

```bash
python metricool-engagement-rate-xlsx/scripts/build_metricool_engagement_xlsx.py \
  --blog-id 5703543 \
  --brand "CIMB Malaysia" \
  --from 2026-01-01 \
  --to today
```

Optional flags:
- `--output path/to/file.xlsx` — custom output workbook path
- `--raw-dir path/to/raw-dir` — custom raw JSON directory
- `--no-raw` — do not save raw Metricool JSON responses
- `--networks instagram,tiktok` — default; supports `instagram`, `tiktok`
- `--no-instagram-reels` — only fetch Instagram feed posts

## Deliverable checklist

Before responding to the user, verify:

```bash
python - <<'PY'
from openpyxl import load_workbook
p = 'OUTPUT.xlsx'
wb = load_workbook(p, read_only=True)
print(wb.sheetnames)
for ws in wb.worksheets:
    print(ws.title, ws.max_row, ws.max_column)
PY
```

Final response should include:
- workbook path
- date range
- formula
- Instagram average ER
- TikTok average ER
- TikTok denominator caveat, if applicable

## Security rules

- Never paste or print the Metricool token.
- Use `METRICOOL_TOKEN` or local `.env` files only.
- This workflow is GET-only; do not use POST/PUT/PATCH/DELETE for reports.
