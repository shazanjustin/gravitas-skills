---
name: metricool-engagement-rate-xlsx
description: >
  Build Metricool per-post engagement-rate proof workbooks for Instagram,
  TikTok, YouTube, and LinkedIn. Use when a user asks for average engagement
  rate, engagement rate over reach, ER/reach, per-post proof, or an XLSX
  export from Metricool for owned social accounts.
compatibility: >
  Requires Python 3.8+, openpyxl, and Metricool credentials via
  METRICOOL_TOKEN or an existing metricool/.env file.
  Uses GET-only Metricool API calls.
---

# Metricool Engagement Rate XLSX

Use this skill to create client-ready Excel proof files showing per-post
engagement rate and average engagement rate for Instagram, TikTok, YouTube,
and LinkedIn using Metricool data.

## When to also load other skills

Always also load the `metricool` skill because this workflow uses Metricool
credentials, brands, and API endpoints.

## Supported platforms

| Platform  | Fetches                          | ER Denominator         |
|-----------|----------------------------------|------------------------|
| Instagram | Feed posts + Reels               | Reach                  |
| TikTok    | Videos                           | Views (reach proxy)    |
| YouTube   | Videos                           | Views (reach proxy)    |
| LinkedIn  | Posts                            | Impressions / Reach    |

Pass `--networks` as a comma-separated list to control which platforms are
fetched. Default is `instagram,tiktok`.

Examples:
```bash
# Instagram + TikTok only (default)
python build_metricool_engagement_xlsx.py --blog-id 123 --from 2026-01-01 --to 2026-04-30

# All four platforms
python build_metricool_engagement_xlsx.py --blog-id 123 --from 2026-01-01 --to 2026-04-30 \
  --networks instagram,tiktok,youtube,linkedin

# TikTok + YouTube only
python build_metricool_engagement_xlsx.py --blog-id 123 --from 2026-01-01 --to 2026-04-30 \
  --networks tiktok,youtube
```

## Output

The workbook contains:

| Sheet               | Contents                                              |
|---------------------|-------------------------------------------------------|
| `Summary`           | Post counts, total engagements, average ER, weighted ER, data limitation notes |
| `Instagram Proof`   | Combined Instagram feed + reels per-post proof        |
| `TikTok Proof`      | TikTok per-video proof                                |
| `IG Feed Raw Proof` | Instagram feed only                                   |
| `IG Reels Raw Proof`| Instagram reels only                                  |
| `YouTube Proof`     | YouTube per-video proof *(if --networks includes youtube)* |
| `LinkedIn Proof`    | LinkedIn per-post proof *(if --networks includes linkedin)* |

## Engagement-rate formula

```
Engagement Rate = (Likes + Comments + Shares + Saves) / Reach or Views
```

Platform-specific notes:

- **Instagram**: uses Metricool `reach` as the denominator.
- **TikTok**: uses `viewCount` as the reach proxy. **Saves are excluded** — see Known Limitations below.
- **YouTube**: uses `viewCount` as the reach proxy. Saves not applicable.
- **LinkedIn**: uses `impressions` as the denominator (falls back to `reach` if impressions unavailable). `Clicks` are included in the engagements numerator.
- Rows with denominator `0` are excluded from average ER but remain in proof tabs.
- `Average ER` is the simple average of post-level ERs.
- `Weighted ER` is total engagements divided by total reach/views across all posts.

## Minimum views filter

Use `--min-views N` to exclude TikTok posts with N views/reach or fewer from ER
averages. Excluded posts still appear in proof tabs, greyed out and marked
`EXCLUDED`, so the audit trail is preserved.

```bash
# Exclude TikTok posts with 20 views or fewer from ER calculation
python build_metricool_engagement_xlsx.py --blog-id 123 --from 2026-01-01 --to 2026-04-30 \
  --min-views 20
```

Recommended value: `--min-views 20`. This removes low-impression TikTok test posts
or scheduling artifacts that would otherwise distort the average ER.

## Known Limitations

### 1. TikTok Saves not available via Metricool API

Metricool's TikTok API endpoint (`/v2/analytics/posts/tiktok`) does **not**
return a Saves or Add-to-Favorites field. The raw post object only contains:
`likeCount`, `commentCount`, `shareCount`, `viewCount`, `engagement`.

As a result:
- TikTok ER in this workbook = (Likes + Comments + Shares) / Views
- TikTok native ER = (Likes + Comments + Shares + **Saves**) / Views
- Metricool TikTok ER will be **slightly lower** than native TikTok analytics
- A yellow warning box is automatically added to the Summary sheet

**Workaround**: For the most accurate TikTok ER including Saves, use a
TikTok native analytics export and compare with the Metricool output.

### 2. Metricool data lags TikTok native data

Metricool syncs from TikTok's public API on a schedule. TikTok's public API
itself introduces a processing delay vs the TikTok native dashboard. For
**recent posts (< 30 days old)**, Metricool view counts may be lower than
TikTok native by 0.1–0.6%. For **older posts (30+ days)**, the gap is
typically negligible (< 0.01%).

**Recommendation**: Run this skill at least 60 days after the end of the
reporting period for the most stable historical data.

### 3. YouTube and LinkedIn support is new

YouTube and LinkedIn endpoints are included based on Metricool's documented
API structure. Field names may vary depending on your Metricool plan and
account connection. If a fetch returns 0 rows, verify the account is
connected in Metricool and the date range contains published content.
