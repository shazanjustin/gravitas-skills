---
name: gravitas-data-manager
description: >
  Single entry point for ALL Gravitas social/reporting data work across
  Facebook, Instagram, and TikTok. Owns the Intel App database-backed FB/IG
  workflow (profile → competitor → scrape → export), TikTok analytics via
  Metricool, cross-platform workbook assembly, manual data handling, and QA.
  Load this when the user wants FB/IG competitor data, social engagement
  reports, collab-aware Instagram data, Apify scraping, Metricool TikTok
  analytics, database-backed proof workbooks, or multi-platform reconciliation.
compatibility: |
  Requires Python 3.8+, curl, git. Credentials: Supabase (local .env),
  Apify + Meta tokens (via gravitas-gateway → gateway.shazan.me),
  Metricool token (via gravitas-gateway), Instaloader session (local .env).
  Scripts: requests, supabase, openpyxl.
argument-hint: "[platform] [brand] [date range]"
---

# Gravitas Data Manager

Single skill for all Gravitas social data — FB/IG via Intel App database,
TikTok via Metricool, cross-platform assembly, manual data, and QA. No more
routing between separate skills.

## Phase 0: Credentials

Before ANY workflow, authenticate. Load `gravitas-gateway` if it hasn't been
loaded in this session (run `cd ~/.gravitas-skills && git pull`, source the
`.env`). Then fetch the secrets this skill needs:

```bash
source ~/.gravitas-skills/.env

# Apify token (for FB/IG scraping fallback)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/APIFY_API_KEY"

# Meta Page token (for official FB/IG insights)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/token"

# Metricool token (for TikTok analytics)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN"
```

**Local credentials** (in `gravitas-data-manager/.env`, never committed):

```env
SUPABASE_URL=https://kzobygrjohvbuxiljbgk.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
INSTALOADER_SESSION=C:/Users/dell/AppData/Local/Instaloader/session-_notakaki
IG_MANAGER_OUTPUT_DIR=outputs/gravitas-data-manager
```

Credentials are resolved in this order: environment variables → `.env` file → hardcoded defaults.

**Never print tokens, service-role keys, Apify tokens, Meta access tokens, or session cookies in chat.**

---

## Phase 1: Route

Ask the user what they need. Not script-by-script — figure out the intent:

```
What do you need?

1. FB/IG competitor report — scrape posts, export XLSX, visual review
2. TikTok analytics — pull from Metricool
3. Cross-platform workbook — combine FB + IG + TikTok into one report
4. Manual/pasted data — clean and normalize client-provided tables
5. QA check — verify an existing report's sources, formulas, and coverage
```

Route based on the answer:

| Choice | Go to |
|--------|-------|
| 1 | FB/IG Database Workflow (Phase 2) |
| 2 | TikTok via Metricool (Phase 5) |
| 3 | Cross-Platform Assembly (Phase 6) |
| 4 | Manual Data (Phase 7) |
| 5 | QA & Delivery (Phase 8) |

---

## Phase 2: FB/IG Database Workflow

The core Intel App workflow: pick an account profile → pick competitors →
scrape/ingest → export.

### Step 2a — List account profiles

Query Supabase `competitor_profiles` where `is_own_profile = true`. Show:

- Profile name and slug
- Number of linked competitors
- Meta IG/Page IDs if set
- Known platform handles from `competitor_profile_inputs`

Use `ask_user` with options from the results. If only one profile, auto-select
with a one-line confirmation.

### Step 2b — Show competitors

Look up `profile_competitors` for the selected profile. For each competitor:

- Name, IG handles, FB URLs from `competitor_profile_inputs`
- Whether posts already exist in `competitor_posts`
- Available platforms

If no competitors linked, offer to show all unlinked competitor profiles.

### Step 2c — Pick platform

```
Which platform?
1. Instagram
2. Facebook
3. Both
```

### Step 2d — Action menu

Show the 7 actions the user can take on these competitors:

```
1. Scrape / ingest posts
2. Visual Review & Classify
3. Export XLSX engagement report
4. Generate Report Slides
5. List existing DB posts
6. Refresh thumbnails
7. Manage platform handles/URLs
```

#### [1] Scrape / Ingest Posts

Ask: source (Instaloader, Apify, Official Meta, DB-only), platform, date range.
Confirm before executing.

**Instagram internal API (Instaloader session):**

```bash
python scripts/ingest_ig_posts.py \
  --username <ig_username> \
  --profile-id <uuid> \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD
```

Captures: shortcode, URL, date, caption, likes, comments, video views,
media type, tagged users, collab signals, thumbnail URLs.
Does NOT capture official reach, saves, or shares.

**Apify (fallback when Instaloader is stale/rate-limited):**

Use the Intel App `apify-ingest` path. Configure platform-specific actor input
with handle/page URL and date filters. Normalize into `competitor_posts`.

**Official Meta API (for owned-account metrics):**

Use the gateway's Meta token endpoint:

```bash
source ~/.gravitas-skills/.env
TOKEN=$(curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/token" | python -c "import sys,json; print(json.load(sys.stdin)['page_access_token'])")
```

Then query Facebook's Graph API directly.

After ingest, summarize: total posts, new vs existing, platform, collab count
for IG, media type breakdown.

#### [2] Visual Review & Classify

Generate HTML review page with full-resolution images:

```bash
python scripts/visual_review.py \
  --profile-id <uuid> \
  --brand "<Brand>" \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD
```

Downloads full-res images, creates browsable HTML page, saves classifications
back to Supabase. Use when small thumbnails are too low quality.

#### [3] Export XLSX

Instagram DB-backed export:

```bash
python scripts/export_ig_xlsx.py \
  --profile-id <uuid> \
  --brand "<Brand>" \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD
```

Produces Summary + Instagram Proof tabs with date, type, likes, comments,
views, engagements, ER%, collab status, tagged users, caption.

For Facebook or combined FB/IG, create a new exporter that reads
`competitor_posts` by platform, writes separate proof tabs, and labels
formulas/denominators.

#### [4] Generate Report Slides

For Friso Gold reports, load `friso-gold-report` for full PPTX with
competitive analysis slides.

For other brands, use `scripts/activity_slide_review.py` for drag-and-drop
review and presentation-ready layouts.

#### [5] List Existing DB Posts

Query `competitor_posts` for selected profile, platform(s), date range. Show:
total count, date range, collab count (IG), platform breakdown, sample posts.

#### [6] Refresh Thumbnails

Call the Intel App thumbnail refresh helper when CDN URLs expire.

#### [7] Manage Platform Handles/URLs

Show current `competitor_profile_inputs` rows. Offer: add IG handle, add FB
Page URL, update existing, remove stale. Then return to action menu.

### Step 2e — After action

Return to the action menu until the user says done, then offer export or
cross-platform assembly.

---

## Phase 3: Instagram Source Priority

When IG campaign coverage may include KOL/collab/tagged posts, follow this
order. Never silently blend sources:

1. **Instaloader / internal API** — owned, tagged, collab-aware public proof.
2. **Apify** — when Instaloader is stale, rate-limited, or broader public/KOL collection is needed.
3. **Official Meta API** — only for owned-account official metrics (reach, saves, shares, impressions). Label separately from public/collab proof.
4. **Manual / pasted data** — only when API/database collection is unavailable or explicitly supplied.

---

## Phase 4: Engagement Formulas

All formulas in one place. Always label which formula was used.

| Platform + Source | Formula | Denominator | Notes |
|---|---|---|---|
| IG official | `(likes + comments + saves + shares) / reach` | reach | Requires Meta API |
| IG public/proxy | `(likes + comments) / views` | views | Instaloader/Apify; fallback to `N/A` if no views |
| FB official | `engagements / reach` | reach | Requires Meta Page insights |
| FB public/proxy | `public engagements / followers` | followers | Apify scrape; engagements = reactions + comments + shares |
| TikTok Metricool | Use Metricool's returned `engagement` % | reach (Metricool) | Components: likes + shares + comments |
| TikTok manual | Use export's formula | as provided | Do not assume it matches Metricool |

**Never calculate a single cross-platform ER across FB, IG, and TikTok.**
Sum engagements/views/reach only as planning/reference totals, clearly labeled.

---

## Phase 5: TikTok via Metricool

When TikTok analytics are needed and the brand is connected in Metricool:

1. Load the `metricool` skill and run `brands` to discover live brands.
2. Pick the relevant brand by account/handle match.
3. Confirm TikTok is connected: `networks <blogId>`.
4. Pull posts with ISO date-time ranges:
   ```
   posts tiktok <blogId> YYYY-MM-DDT00:00:00 YYYY-MM-DDT23:59:59
   ```
5. Match returned `videoId`, `shareUrl`, title, description, post date to report rows.
6. Label Metricool rows as `Metricool API v2 /v2/analytics/posts/tiktok`.

Common TikTok fields from Metricool: views, reach, likes, comments, shares,
engagement percentage, duration, cover image, share URL. Do not assume
favorites/saves unless present in the response.

---

## Phase 6: Cross-Platform Assembly

When the report needs FB + IG + TikTok combined, build or update an `.xlsx`
with these tabs:

| Tab | Content |
|-----|---------|
| `Summary` | One row per requested post/campaign, static totals, NO blended ER unless explicitly approved |
| `All Matched Data` | Normalized combined rows across all platforms |
| `Instagram Proof` | IG-only rows with source and denominator labels |
| `Facebook Proof` | FB-only rows with source and denominator labels |
| `TikTok Proof` | TikTok-only rows, Metricool-checked when available |
| `Data Notes` | Source, formula, date range, assumptions, limitations |
| Optional: `Raw Metricool`, `Raw Intel`, `Raw Manual Export` | Raw evidence tabs |

Normalized columns (include what's available):

- Planned post/campaign name, Platform, Metric Source
- Source campaign/title, Publish time, Post type / format
- Duration, Views, Reach, Likes/Reactions, Shares, Comments, Saves/Favorites
- Follows, Total Engagements, Engagement Rate, ER Denominator
- Engagement Components, Post ID, Link/Permalink, Notes

---

## Phase 7: Manual / Pasted Data

Use only when API/database access is unavailable or the user provides a
client export. Steps:

1. Read the provided data (CSV, Excel, pasted table).
2. Match to known profiles/handles when possible.
3. Normalize into the standard column format.
4. Label every row as `pasted/manual` in the Metric Source column.
5. Include a canary note: "Client-critical numbers should be checked against
   the source export."

---

## Phase 8: QA & Delivery

Before delivering any workbook, run these checks:

- [ ] Every requested campaign/post has expected platform rows or a clear missing-data note
- [ ] Date ranges match the user's report period
- [ ] Instagram KOL/collab/tagged content checked via Instaloader/Apify before declaring IG rows complete
- [ ] TikTok data uses ISO date-time ranges, not plain dates
- [ ] Metricool `engagement` values converted correctly when writing as Excel percentages
- [ ] Favorites/saves not included when the source didn't provide them
- [ ] Cross-platform summaries do not imply a shared denominator
- [ ] Any manual/pasted data is labeled as such
- [ ] Any source mismatch (planned static vs source video/reel) is documented
- [ ] Official Meta metrics never silently blended with public/proxy scrape metrics

---

## Scripts

All scripts live in `scripts/` relative to this SKILL.md. They use
`Path(__file__).resolve().parent.parent` to locate the skill root and `.env`.

| Script | Purpose |
|--------|---------|
| `scripts/ig_utils.py` | Shared: Supabase connection, profile listing, session management |
| `scripts/ingest_ig_posts.py` | Instagram scraping via internal API with Instaloader cookies; collab-aware |
| `scripts/export_ig_xlsx.py` | Build IG public/proxy engagement XLSX from Supabase |
| `scripts/visual_review.py` | Generate HTML review page with full-res images for classification |
| `scripts/activity_slide_review.py` | Multi-competitor drag-and-drop activity classification |

Run scripts with `--help` for full argument lists. The Supabase credentials,
Instaloader session path, and output directory are read from `.env` in the
skill directory.

---

## Database Reference

See `references/intel-db-schema.md` for full schema of:
`competitor_profiles`, `profile_competitors`, `competitor_profile_inputs`,
`competitor_posts`.

Key conventions:
- Instagram rows → `platform = 'instagram'`
- Facebook rows → `platform = 'facebook'`
- Raw payloads → `raw` JSONB column
- IG handles stored in `competitor_profile_inputs.input_url` (with or without `@`)

---

## Known Issues

1. **Instagram image quality** — small thumbnails too low quality for classification; use Visual Review for full-res.
2. **Instaloader session expiry** — refresh with `instaloader --login _notakaki`.
3. **Instagram rate limiting** — use 1.5s+ delays between calls.
4. **No official IG reach from public scrape** — internal API/Apify do not provide reach/saves/shares.
5. **CDN URL expiry** — refresh thumbnails when images break.
6. **Collab dedup** — IG collab posts can appear on multiple profiles; dedupe by shortcode/post URL.
7. **Apify actor drift** — actor names/schemas can change; verify before building reports.
8. **FB metric variance** — public scrapes expose reactions/comments/shares but not reach; official API needs owned-page permissions.
9. **Service role key in `.env`** — never commit or print.
10. **Metricool engagement %** — multiply by 100 when converting to Excel percentage format.
