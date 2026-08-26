---
name: social-atlas-ingest
description: Add competitor posts to the Social Atlas (Gravitas Intel App) Supabase database the way the app itself does it. Meta (Facebook/Instagram) and YouTube/X competitor posts come from the Metricool competitors API; TikTok comes from Apify clockworks/tiktok-scraper; LinkedIn comes from an Apify dataset import. Use when Shazan wants to ingest, backfill, or automate adding competitor posts into Social Atlas, or verify post coverage per platform.
---

# Social Atlas Competitor Post Ingestion

Add competitor posts to the live Social Atlas Supabase database using the app's own
edge functions — same normalization, same ID scheme, same dedup as the UI.

- Repo: `D:/vibe coding stuff/Gravitas Intel App` (Supabase project `kzobygrjohvbuxiljbgk`, linked online)
- Frontend: https://socialatlas.shazan.me (Vercel)
- Never use Docker or local Supabase containers (Shazan's standing rule)

## Source routing (how the app does it)

| Platform | Source | Edge function | Post ID shape |
|---|---|---|---|
| **OWN brand, all networks** | Metricool own-profile API | `metricool-own-profile-ingest` | `{network}:{postId}` |
| Facebook, Instagram (competitors) | Metricool competitors API | `metricool-competitors-ingest` | `{network}:{postId}` |
| YouTube, X/Twitter, Twitch, Bluesky | Metricool competitors API | `metricool-competitors-ingest` | `{network}:{postId}` |
| TikTok | Apify `clockworks/tiktok-scraper` | `apify-ingest` | numeric video ID (from URL) |
| LinkedIn (competitors, date-windowed) | Apify `harvestapi/linkedin-company-posts` | `apify-ingest` | numeric activity ID |
| LinkedIn | Apify dataset URL (company posts actor run in Apify console) | `apify-dataset-import` | numeric activity ID |
| Instagram collab-aware public proof | Instaloader/internal REST | use `intel-ig-manager` skill instead | `ig_{user}_{shortcode}` |

Do not build new ingestion paths when these exist. The edge functions already:
normalize per-platform fields to `caption`/`thumbnailUrl`/`postUrl`, strip
Postgres-unsafe Unicode, resolve `profile_id` from `competitor_profile_inputs`,
and upsert into `competitor_posts` with `onConflict: 'id'` (re-running is safe).

## Auth

Deployed edge functions require an **admin user token**. The platform-managed
`SUPABASE_SERVICE_ROLE_KEY` secret inside the functions is a stale value that cannot be
overridden (`SUPABASE_`-prefixed secrets are reserved), so a plain service-key Bearer gets
401 `bad_jwt`.

The script therefore signs in as the automation service account and gets its credentials
from the **Gravitas API Gateway** - this skill contains no secrets. Load the
`gravitas-gateway` skill first if `~/.gravitas-skills/.env` is not set up yet.

```bash
# what ingest.py does for you, using ~/.gravitas-skills/.env
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/SOCIAL_ATLAS_AUTH_EMAIL"
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/SOCIAL_ATLAS_AUTH_PASSWORD"
```

Precedence is gateway -> local `.env` -> real environment variables, so a machine without
gateway access can still drop a local `.env` in as an escape hatch. Cloudflare rejects
Python's default urllib User-Agent on every gateway endpoint with `code: 1010`, so a
curl-like UA is required, not optional.

Metricool `userId`/`blogId` identify the OWN brand whose competitor watchlist is queried and
must be passed per call (CIMB Malaysia blogId is `5703543`; `--timezone Asia/Kuala_Lumpur`
is required - Metricool rejects requests without it).

Never print tokens or keys.

## This runs automatically - check before you ingest by hand

| Layer | Runs | Cadence |
|---|---|---|
| pg_cron `metricool-daily-ingest` | `metricool-auto-ingest`: competitors + own brands via Metricool | daily 21:00 UTC (05:00 MYT) |
| the same function | competitor TikTok + LinkedIn via Apify | Mondays only, on cost grounds |
| ev schedule `464e84` | `social-atlas-health` posted to Discord | weekdays 09:00 MYT |
| this skill | ad-hoc backfills, one-off windows, `coverage` | on demand |

So a missing month is usually a **failed run**, not a missing ingest. Check `ingest_runs`
and `social-atlas-health` before backfilling by hand.

`cron.job_run_details.status = 'succeeded'` only means `net.http_post` was QUEUED. It read
"succeeded" every night for 3.5 months while the ingest inside it was failing. Trust
`ingest_runs`, never the pg_cron status.

A deep backfill (wider Apify windows) is `{"deep": true}`; `{"forceApify": true}` runs the
Apify steps on a non-Monday.

## Apify accounts (primary + fallback)

Both Apify accounts are FREE plan, $5/month each, so the primary runs dry mid-cycle.
All Apify callers (`apify-ingest`, `apify-comments-ingest`, `apify-dataset-import`,
`api-credits`) share `_shared/apify.ts`, which reads `APIFY_TOKEN` then
`APIFY_TOKEN_FALLBACK` (both Supabase edge-function secrets) and retries the next account **only** on a credit-exhaustion error — a bad actor
input or bad token still fails on the first account instead of burning the backup. The
success response carries `apifyAccount: "primary" | "fallback-1"` so you can see who paid.

Apify signals exhaustion with two different shapes; both are matched:
- `not-enough-usage-to-run-paid-actor` - "you will exceed your remaining usage of $X"
- `platform-feature-disabled` - "Monthly usage hard limit exceeded"

`api-credits` now reports BOTH accounts (`credits.apify.accounts[]`) using the limits
endpoint. To check by hand:
`curl -s "https://api.apify.com/v2/users/me/limits?token=$T"` -> `current.monthlyUsageUsd` of `limits.maxMonthlyUsageUsd`

## Script

```bash
PYTHONUTF8=1 python "C:/Users/dell/.pi/agent/skills/social-atlas-ingest/scripts/ingest.py" <command>
```

Commands (reads repo `.env` automatically):

```bash
# OWN brand's own posts (NOT its competitors) - covers ig/fb/linkedin/youtube/tiktok
# with NO Apify involvement. Run this whenever the client brand itself is missing.
ingest.py own --profile CIMB --from 2026-07-01 --to 2026-07-31 [--platforms instagram,facebook]

# Meta/YouTube/X competitors via Metricool (network: facebook|instagram|youtube|twitter|...)
ingest.py metricool --network facebook --from 2026-01-01 --to 2026-01-31 \
  --user-id <metricoolUserId> --blog-id 5578522 [--competitors "handle1,handle2"]

# TikTok via Apify clockworks/tiktok-scraper (--from maps to oldestPostDateUnified, --to to newestPostDate)
ingest.py tiktok --handles "@brand,@competitor" --from 2026-01-01 --to 2026-01-31

# LinkedIn (or any platform) from an Apify dataset URL
ingest.py dataset --url "https://api.apify.com/v2/datasets/<id>/items?token=..." --platform linkedin

# Generic Apify actor run + import
ingest.py apify --actor clockworks/tiktok-scraper --platform tiktok --input-json '{"profiles":["@x"]}'

# Verify coverage per platform (counts + unmapped profile_id rows)
ingest.py coverage
```

## Workflow

1. Identify the own-brand account and the competitors (check `competitor_profiles`
   and `profile_competitors`; handles live in `competitor_profile_inputs`).
2. Run `coverage` to see current state and spot gaps.
3. Ingest per platform using the routing table. Confirm date ranges before running.
4. Re-run `coverage` and compare counts. Report items ingested vs upserted.
5. Rows with `profile_id IS NULL` mean no matching `competitor_profile_inputs`
   entry — add the handle/URL input first, then re-ingest (upsert fills it in).

## Conventions

- `competitor_posts.platform`: `facebook` | `instagram` | `tiktok` | `linkedin` | `youtube` | `twitter`
- `raw` JSONB keeps the full normalized source payload; keep it untouched.
- `post_type_source` marks provenance (`metricool`, `manual`, `ai_batch`, `unknown`).
- Metrics stay source-labeled: Metricool fields vs Apify fields are never blended.
- Ingestion is idempotent (upsert on `id`); overlapping date ranges are safe.

## Gotchas

- Metricool needs `userId` + `blogId` of the OWN brand, not the competitor's, plus a `timezone` param (required, not optional).
- **Date fields are asymmetric.** Own-profile rows get the real publish time in the `created_at`
  COLUMN; competitor rows leave `created_at` NULL and keep the date only inside `raw`, under a
  different key AND encoding per source (`timestamp`, `createTimeISO`, `publishedAt`,
  `postedAtISO`, or `posted_at` as a nested `{date,relative}` object; ISO string vs epoch s vs
  epoch ms). Any "how much July data do we have" query must handle all of them or it will
  silently report zero.
- Metricool-sourced rows land with `profile_id IS NULL` by design — the app filters by `raw.inputUrl`/author, and `profile_id` was backfilled historically. Do not treat null profile_id on Metricool rows as an error.
- **The own brand needs its own ingest run.** `metricool-competitors-ingest` pulls ONLY the
  watchlist, never the client's own posts. Filling competitors and forgetting `own` leaves the
  client absent from its own report. Own-brand TikTok/LinkedIn come from Metricool, not Apify.
- **`competitor_posts.post_type` is a CONTENT CATEGORY**, constrained to 'Promotional',
  'Product/Feature', 'Educational/How-to', 'UGC/Testimonial', 'Brand/Story', 'Announcement',
  'Partnership/Influencer', 'Community/Engagement', 'Other' (or NULL). It is NOT the media
  format. Writing Metricool's `type` ('reel'/'photo'/'video') into it fails the whole batch with
  `competitor_posts_post_type_chk`. Media format belongs in `raw.post_type` only.
  `post_type_source` is separately constrained to unknown|manual|ai_single|ai_batch — 'metricool'
  is NOT valid there either, it goes in `raw`.
- **Check the deployed edge function before trusting the repo.** The live functions have drifted
  ahead of `D:/vibe coding stuff/Gravitas Intel App`. Use `supabase functions download <slug>`
  and patch THAT; deploying the repo copy silently reverts live fixes.
- **`api-credits` under-reports Apify usage.** It reads `usage.monthlyUsageCreditsUsd` with `??`,
  and a literal `0` is not null, so it never falls back to `limits.usedCreditsUsd` — the dashboard
  showed "$5 of $5 remaining" while the real balance was $0.07. Trust the actor error, not the tile.
- Apify runs cost platform usage; when BOTH accounts are dry, actor runs fail with `not-enough-usage-to-run-paid-actor` — top up at console.apify.com.
- **TikTok: always pass `resultsPerPage`.** Without it `clockworks/tiktok-scraper` returns
  exactly ONE video per profile and still reports `ok: true` — a silent near-empty ingest.
  `ingest.py tiktok --limit N` sets it (default 60). The scraper walks newest-first then
  applies the date bounds, so N must span from today back through the target window, not
  just the window's own length. Cost scales with videos scraped (~$0.62 for 6 profiles x 60).
- **LinkedIn: `apimaestro/linkedin-company-posts` cannot window a month.** Its `limit` is
  ignored (one page is ~14 posts) and `page_number` is NOT chronologically contiguous —
  page 1 returned Aug 2026 and page 2 jumped straight to Sep 2025, skipping July entirely.
  Use `harvestapi/linkedin-company-posts` instead: it takes all companies in ONE run via
  `targetUrls` and honours `postedLimitDate` (an ISO date meaning "posts newer than this").
- **Three things must ALL be true or the post is useless in the UI.** Row count going up
  proves none of them. Check each after every ingest with a new actor:
  1. `raw.inputUrl` exactly matches a `competitor_profile_inputs` row -> else no brand
  2. `created_at` column is populated -> else it falls out of every date filter
  3. metrics sit at the TOP LEVEL of `raw` -> `pickMetric()` in `src/utils/metrics.ts`
     does `if (key in raw)` with NO nesting, so harvestapi's `engagement: {likes,...}`
     reads as 0 engagement on every post. Flatten to `numLikes`/`numComments`/`numShares`.
- **LinkedIn thumbnails hide in five different places** and a post is only genuinely
  image-less if all are empty: `postImages[0].url`, `postVideo.thumbnailUrl` (video posts
  carry an EMPTY `postImages` array), `article.image.url` (link shares),
  `document.coverPages[0].imageUrls[0]` (carousels), `document.thumbnail` (apimaestro).
  `pickLinkedInThumbnail()` in `apify-ingest` walks all five.
- **Dedupe on a UNIFIED key across actors.** harvestapi puts the LinkedIn activity id in
  `id`; apimaestro puts the same id in `activity_urn`. Deduping on `activity_urn` alone
  never compares the two shapes, so the same post survives twice. Use
  `coalesce(raw->>'activity_urn', raw->>'entityId', id)`.

- **`created_at` NULL = invisible.** The UI filters by the `created_at` COLUMN, so a NULL
  date drops the post out of every date range no matter how good the rest of the row is.
  The LinkedIn actors disagree on casing — apimaestro emits `posted_at: {date}`, harvestapi
  emits `postedAt: {date}` — and `pickCreatedAt` only handled the snake_case one, leaving
  every harvestapi row dateless. Both are handled now in `apify-ingest` and
  `apify-dataset-import`. **Any new actor: check `created_at` is populated, not just that
  rows arrived.**
- **`ingest.py coverage` now catches both invisibility bugs** — it reports `null_created_at`
  per platform and lists every `raw.inputUrl` that matches no `competitor_profile_inputs`
  row. Run it after EVERY ingest. It found 117 CIMB YouTube posts and 61 Friso Gold IG
  posts that were only being attributed by a hardcoded brand-name fallback in the UI.
- `competitor_profile_inputs` now has a unique constraint on `(profile_id, input_url)`.
  It was missing, so `metricool-own-profile-ingest`'s `onConflict: 'profile_id,input_url'`
  upsert had been failing (logged, non-fatal) on every own-profile run.

- **A row can be in the table and still show 0 in the UI.** `getBrandFromRow`
  (`src/panels/competitors-view.ts`) maps a post to a brand by matching `raw.inputUrl`
  EXACTLY against `competitor_profile_inputs` — trailing slash and `www.` vs `my.` all
  matter. `harvestapi` emits no `inputUrl` at all, so its rows landed brand-less and the
  competitor table read 0 for LinkedIn. `apify-ingest` now derives it from
  `author.universalName` -> `https://www.linkedin.com/company/<slug>`, which matches the
  stored inputs. **After ANY new-actor ingest, verify `raw->>'inputUrl'` is populated and
  matches an existing input row — not just that the post count went up.**
- **`profile_id` is not set by `apify-ingest`.** Backfill it after an ingest:
  `update competitor_posts p set profile_id = i.profile_id from competitor_profile_inputs i
   where p.profile_id is null and p.raw->>'inputUrl' = i.input_url;`
- **LinkedIn rows used to duplicate on every run.** `pickId` in `apify-ingest` had no
  candidate that matched LinkedIn actor output (no `id`/`postId`, and `post_url` is
  snake_case), so it fell through to `crypto.randomUUID()` and re-inserted instead of
  upserting. Fixed by keying on `activity_urn`/`full_urn`/`post_url`. Rows ingested before
  that fix still carry UUID ids and can duplicate against newly-keyed rows — dedupe on
  `raw->>'activity_urn'`.
- TikTok date filters are inclusive bounds set by the scraper, not the DB.
- LinkedIn ingestion uses Apify company-posts datasets (run from the Apify console, then `dataset --url ... --platform linkedin`).
- Ask Shazan before large backfills or deleting rows. Never print secrets.
