---
name: gravitas-data-manager
description: >
  Single entry point for ALL Gravitas social/reporting data across Facebook,
  Instagram, and TikTok. Two clean paths: pull your own brand's data (Metricool
  plus official exports when needed), or pull competitor data (Instaloader/Apify public
  scrape). Owns the Intel App database, cross-platform workbook assembly,
  manual data handling, and QA. Load this when the user wants social
  engagement reports, competitor analysis, collab-aware Instagram data,
  Apify scraping, Metricool TikTok analytics, database-backed proof
  workbooks, or multi-platform reconciliation.
compatibility: |
  Requires Python 3.8+, curl, git. Shared secrets (Apify, Metricool,
  Supabase) and safe Meta account discovery via gravitas-gateway → gateway.shazan.me.
  Per-user: Instaloader session (local .env). Scripts: requests, supabase,
  openpyxl.
argument-hint: "[brand] [date range]"
---

# Gravitas Data Manager

Two paths. One skill. No more routing between separate tools.

## Phase 0: Credentials

Before ANY workflow, fetch shared secrets from the gateway. Load
`gravitas-gateway` first if it hasn't been loaded this session
(`cd ~/.gravitas-skills && git pull`, source `.env`).

```bash
source ~/.gravitas-skills/.env

# Supabase (Intel App database)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/SUPABASE_SERVICE_ROLE_KEY"

# Apify token (FB/IG scraping fallback)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/APIFY_API_KEY"

# Metricool token (TikTok analytics — Own Data path)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN"
```

Export fetched values as environment variables so the Python scripts pick them up
(they check `os.environ` before `.env`):

```bash
export SUPABASE_URL="https://kzobygrjohvbuxiljbgk.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<from gateway>"
export APIFY_API_KEY="<from gateway>"
```

**Local-only credentials** (in `gravitas-data-manager/.env`, never committed):

```env
INSTALOADER_SESSION=C:/Users/dell/AppData/Local/Instaloader/session-_notakaki
IG_MANAGER_OUTPUT_DIR=outputs/gravitas-data-manager
```

**Never print tokens, service-role keys, Apify tokens, Meta access tokens, or
session cookies in chat.**

---

## Phase 1: Choose Your Path

Ask the user:

```
Whose data are we pulling?

1. Our own brand — Metricool first, with official exports for gaps
   (gateway `/pages` validates the FB/IG account mapping)
2. Competitor data — public scrape of their posts
   (Instaloader or Apify for IG/FB)
```

| Choice | Go to |
|--------|-------|
| 1 — Own Data | Path A (Phase 2) |
| 2 — Competitor Data | Path B (Phase 3) |

If the user also mentions cross-platform assembly, manual data, QA, or report
slides — note it and handle after the primary path completes.

---

## Phase 2: Path A — Own Data

We own these accounts. Use Metricool first; use official Meta exports when the
requested metric or collab/tagged-post coverage is missing.

### Step A1: Pick the brand

Query Supabase `competitor_profiles` where `is_own_profile = true`. Show:

- Profile name and slug
- Connected platforms (IG handle, FB page, Metricool)
- Whether `meta_ig_id` and `meta_page_id` are set

Use `ask_user` with options from the results. If only one, auto-select.

### Step A2: What metrics do you want?

**Ask the user** — don't assume. Present with recommendations:

```
What metrics do you need?

Recommended for owned accounts (confirm availability in the selected source):
  ☑ Reach
  ☑ Impressions
  ☑ Likes / Reactions
  ☑ Comments
  ☑ Shares
  ☑ Saves (Instagram)
  ☑ Video views
  ☑ Engagement rate (ER%)
  ☑ Follower count / growth

Also available:
  ☐ Post link / permalink
  ☐ Caption / post text
  ☐ Media type (image, video, carousel)
  ☐ Post date / time
```

The user can select all, some, or name custom metrics. If they don't know,
default to: reach, impressions, likes, comments, shares, engagement rate.

### Step A3: Date range

Ask for the reporting period. Accept `YYYY-MM-DD` to `YYYY-MM-DD`, presets
("last month", "May 2026"), or a single month.

### Step A4: Pull the data

Route by platform — handled automatically based on what the brand has connected:

**Instagram + Facebook:**

Load the `metricool` skill and pull the selected brand's owned posts. Then
validate the stored FB page / IG account mapping without exposing a token.
Set the IDs from the selected profile in Step A1; exactly one gateway page must
match both:

```bash
source ~/.gravitas-skills/.env
PAGES_FILE=$(mktemp)
PYTHON_BIN=$(command -v python3 || command -v python)
trap 'rm -f "$PAGES_FILE"' EXIT
curl -sS --fail-with-body -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/pages" > "$PAGES_FILE"
META_PAGE_ID="<selected meta_page_id>" META_IG_ID="<selected meta_ig_id>" \
  "$PYTHON_BIN" -c 'import json,os,sys; d=json.load(open(sys.argv[1])); assert isinstance(d.get("pages"),list) and d["pages"], "no pages returned"; assert "access_token" not in json.dumps(d), "token leaked"; m=[p for p in d["pages"] if p.get("id")==os.environ["META_PAGE_ID"] and (p.get("instagram_business_account") or {}).get("id")==os.environ["META_IG_ID"]]; assert len(m)==1, f"expected one matching page, found {len(m)}"; print(m[0]["name"], (m[0].get("instagram_business_account") or {}).get("username",""), sep="\t")' "$PAGES_FILE"
```

Do **not** fetch `/token`: it is a legacy single-page endpoint and is not a
usable multi-page credential source. For exact Meta
insights or collab/tagged-post coverage missing from Metricool, use an official
Meta Business Suite export until a scoped read-only insights proxy exists.
Gateway `/thumbnail` and `/comments` remain available server-side when a post ID
is already known.

**TikTok (Metricool):**

Load the `metricool` skill, run `brands`, pick the matching brand,
confirm TikTok is connected via `networks <blogId>`, then pull:
```
posts tiktok <blogId> YYYY-MM-DDT00:00:00 YYYY-MM-DDT23:59:59
```

### Step A5: Output

Present the data as a table in chat first. Then offer:
1. Export to XLSX (with official-source labels)
2. Add to database with the actual source (`metricool` or `official_meta` export)
3. Generate report slides

---

## Phase 3: Path B — Competitor Data

We don't own these accounts. We scrape publicly available data. Metrics are
limited to what's visible.

### Step B1: Pick the brand (account profile)

Same as Step A1 — query `competitor_profiles` where `is_own_profile = true`.
The brand determines which competitors are linked.

### Step B2: Pick competitors

Look up `profile_competitors` for the selected profile. Show each competitor
with:

- Name
- IG handles / FB URLs (from `competitor_profile_inputs`)
- Whether posts already exist in `competitor_posts`
- Available platforms

If no competitors linked, show all unlinked competitor profiles.

User picks one or more competitors. Use `ask_user` with `allowMultiple: true`.

### Step B3: What metrics do you want?

**This is critical — competitor data has hard limits.** Present with clear
availability warnings:

```
What metrics do you need?

✅ Available via public scrape:
  ☑ Likes / Reactions
  ☑ Comments
  ☑ Video views (Instagram)
  ☑ Post type (image, video, carousel)
  ☑ Post link / permalink
  ☑ Caption / post text
  ☑ Post date / time
  ☑ Collab / tagged users (Instagram)
  ☑ Engagement rate (ER%) — calculated as (likes+comments)/views

❌ NOT available via public scrape:
  ✗ Reach
  ✗ Impressions
  ✗ Saves
  ✗ Shares (Instagram)
  ✗ Follower count changes
  ✗ Any official Meta metrics

⚠️  If you need reach/saves/impressions, those only come from
    official Meta API — and only for accounts you own.
```

If the user insists on metrics that aren't available, explain the limitation
again and offer the closest proxy. Don't silently substitute.

### Step B4: Instagram scraping source

**For Instagram competitor data, ask the user which scraping source:**

```
How should we pull Instagram data?

1. Instaloader (FREE)
   • Uses YOUR Instagram login session
   • Username + password → stored locally on your machine
   • Rate limited: ~200 posts per scrape, needs delays
   • Captures collab posts, tagged users, post types
   • Drawback: uses your personal account, session expires
     (refresh with: instaloader --login _notakaki)

2. Apify (PAID, ~$5 free credit)
   • No personal account needed
   • More reliable, fewer rate limits
   • Better for bulk/large scrapes
   • Drawback: costs money after free credit runs out
   • Uses shared APIFY_API_KEY from gateway
```

Wait for the user's choice. Default to Instaloader for small scrapes, suggest
Apify for bulk or when rate limits become a problem.

If they choose Instaloader, check that `INSTALOADER_SESSION` is set in
`.env`. If not, guide them:

```bash
pip install instaloader
instaloader --login _notakaki
# → Enter Instagram username and password
# → Session saved to C:/Users/dell/AppData/Local/Instaloader/session-_notakaki
```

Then set it in the `.env`.

### Step B5: Date range

Same as Step A3 — ask for the reporting period.

### Step B6: Scrape

Execute based on the user's platform + source choices.

**Instagram via Instaloader:**

```bash
python scripts/ingest_ig_posts.py \
  --username <ig_username> \
  --profile-id <uuid> \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD
```

Captures: shortcode, URL, date, caption, likes, comments, video views,
media type, tagged users, collab signals, thumbnail URLs.
Does NOT capture: reach, saves, shares, impressions.

**Instagram via Apify:**

Use the Intel App `apify-ingest` path with the `APIFY_API_KEY` from gateway.
Configure platform-specific actor input. Normalize into `competitor_posts`.

**Facebook via Apify:**

Use the configured Facebook Apify actor. Store normalized rows in
`competitor_posts` with `platform = 'facebook'`.

After scraping, summarize: total posts, new vs existing, collab count (IG),
media type breakdown, any errors or rate limits hit.

### Step B7: Visual Review (optional, IG only)

Offer visual review for quality classification:

```bash
python scripts/visual_review.py \
  --profile-id <uuid> \
  --brand "<Brand>" \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD
```

Downloads full-res images, creates browsable HTML, saves classifications.

### Step B8: Export

```bash
python scripts/export_ig_xlsx.py \
  --profile-id <uuid> \
  --brand "<Brand>" \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD
```

Produces Summary + Instagram Proof tabs. For Facebook or combined FB/IG,
create an exporter reading `competitor_posts` by platform, with separate
proof tabs and labeled formulas.

---

## Phase 4: Cross-Platform Assembly

When the task spans both Own Data (Path A) and Competitor Data (Path B), or
when TikTok + FB/IG need to be combined, assemble a master workbook.

### Tabs

| Tab | Content |
|-----|---------|
| `Summary` | One row per post/campaign, static totals, NO blended ER unless approved |
| `All Matched Data` | Normalized combined rows across all platforms |
| `Instagram Proof` | IG-only, source + denominator labels |
| `Facebook Proof` | FB-only, source + denominator labels |
| `TikTok Proof` | TikTok-only, Metricool-checked when available |
| `Data Notes` | Source, formula, date range, assumptions, limitations |
| Optional raw tabs | `Raw Metricool`, `Raw Intel`, `Raw Manual Export` |

### Normalized columns

Include what's available: planned post/campaign name, platform, metric source,
source campaign/title, publish time, post type/format, duration, views, reach,
likes/reactions, shares, comments, saves/favorites, follows, total engagements,
engagement rate, ER denominator, engagement components, post ID, link/permalink,
notes.

---

## Phase 5: Manual / Pasted Data

Use only when API/database access is unavailable or the user provides a client
export.

1. Read the provided data (CSV, Excel, pasted table).
2. Match to known profiles/handles when possible.
3. Normalize into the standard column format.
4. Label every row as `pasted/manual` in the Metric Source column.
5. Include a canary note: "Client-critical numbers should be checked against
   the source export."

---

## Engagement Formulas (Reference)

All formulas in one place. Always label which formula was used.

| Platform + Source | Formula | Denominator | Notes |
|---|---|---|---|
| IG official | `(likes + comments + saves + shares) / reach` | reach | Own Data only; requires Meta API |
| IG public/proxy | `(likes + comments) / views` | views | Competitor Data; fallback to `N/A` if no views |
| FB official | `engagements / reach` | reach | Own Data only; requires Meta Page insights |
| FB public/proxy | `public engagements / followers` | followers | Competitor Data; engagements = reactions + comments + shares |
| TikTok Metricool | Use Metricool's returned `engagement` % | reach (Metricool) | Own Data; components: likes + shares + comments |
| TikTok manual | Use export's formula | as provided | Do not assume it matches Metricool |

**Never calculate a single cross-platform ER across FB, IG, and TikTok.**
Sum engagements/views/reach only as planning/reference totals, clearly labeled.

---

## QA Checklist

Before delivering any workbook:

- [ ] Every requested campaign/post has expected platform rows or a missing-data note
- [ ] Date ranges match the user's reporting period
- [ ] Instagram collab/tagged content checked via Instaloader/Apify before declaring IG complete
- [ ] TikTok data uses ISO date-time ranges, not plain dates
- [ ] Metricool `engagement` values converted correctly as Excel percentages
- [ ] Favorites/saves not included when source didn't provide them
- [ ] Cross-platform summaries do not imply a shared denominator
- [ ] Manual/pasted data labeled as such
- [ ] Source mismatches (planned static vs source video/reel) documented
- [ ] Official Meta metrics never silently blended with public/proxy scrape metrics
- [ ] Competitor data doesn't claim reach/saves/impressions that aren't available

---

## Scripts

All scripts in `scripts/` relative to this SKILL.md.

| Script | Purpose |
|--------|---------|
| `scripts/ig_utils.py` | Supabase connection, profile listing, session management |
| `scripts/ingest_ig_posts.py` | IG scraping via Instaloader; collab-aware |
| `scripts/export_ig_xlsx.py` | IG public/proxy engagement XLSX from Supabase |
| `scripts/visual_review.py` | HTML review page with full-res images |
| `scripts/activity_slide_review.py` | Multi-competitor drag-and-drop classification |

Credential resolution order: `os.environ` → `.env` file → hardcoded defaults.
Supabase credentials come from gateway (exported as env vars in Phase 0).

---

## Database Reference

See `references/intel-db-schema.md` for schema of:
`competitor_profiles`, `profile_competitors`, `competitor_profile_inputs`,
`competitor_posts`.

Key conventions:
- Instagram → `platform = 'instagram'`
- Facebook → `platform = 'facebook'`
- Raw payloads → `raw` JSONB column
- Source labels: `official_meta`, `instaloader`, `apify`, `metricool`, `manual`

---

## Known Issues

1. **Instaloader session expiry** — refresh with `instaloader --login _notakaki`.
2. **Instagram rate limiting** — use 1.5s+ delays between calls.
3. **No official metrics from public scrape** — Instaloader/Apify do not provide reach, saves, shares, or impressions. Only available via Meta API for owned accounts.
4. **CDN URL expiry** — refresh thumbnails when images break.
5. **Collab dedup** — IG collab posts appear on multiple profiles; dedupe by shortcode.
6. **Apify actor drift** — actor names/schemas can change; verify before building reports.
7. **FB metric variance** — public scrapes give reactions/comments/shares but not reach.
8. **Metricool engagement %** — multiply by 100 when converting to Excel %.
9. **Credentials** — never print tokens, service-role keys, or session cookies in chat.
