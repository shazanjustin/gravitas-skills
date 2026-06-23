---
date: 2026-06-22
plan_type: feat
topic: pitch-competitor-research
origin: docs/brainstorms/pitch-competitor-research-requirements.md
status: active
---

# feat: Pitch Competitor Research Skill

> **Origin:** `docs/brainstorms/pitch-competitor-research-requirements.md`

## Summary

A new agent skill (`pitch-competitor-research`) that researches competitors for Gravitas pitches — scrapes social media across FB/IG/TikTok/YouTube/LinkedIn, transcribes video content via yt-dlp → Gemini/ChatGPT, analyzes campaigns/KOLs/themes/cadence, and produces an executive-brief HTML dossier.

---

## Problem Frame

Gravitas pitch preparation requires deep competitor intelligence across five social platforms. Today this is manual — team members search platforms, copy-paste into spreadsheets, and assemble findings by hand. It's slow, shallow, and inconsistent. A single competitor deep-dive with video transcription would take hours manually. The skill automates the entire pipeline: input → scrape → transcribe → analyze → HTML.

---

## Actors

- A1. **Shazan / pitch lead**: Invokes the skill, provides competitor names and handles, reviews output
- A2. **Pitch team**: Consumers of the HTML dossier
- A3. **Agent (AI)**: Executes scraping, transcription, analysis, HTML generation

---

## Key Flows

- F1. **Full competitor research** — Trigger: Shazan invokes skill. Steps: ask names/handles → recommend gaps → scrape all platforms → download + transcribe videos → AI analysis → HTML output. Outcome: local HTML dossier. Covered by: R1-R9, R11-R15.
- F2. **Quick competitor snapshot** — Trigger: Shazan chooses quick mode. Steps: ask names/handles → scrape metadata only (no video) → lightweight analysis → lightweight HTML. Outcome: faster overview. Covered by: R10.

---

## Requirements Trace

All requirements from origin carried forward. Key mapping to implementation units below.

| Requirement | Unit |
|---|---|
| R1-R3 (Input & discovery) | U1 |
| R4-R6 (Scraping) | U2 |
| R7-R8 (Transcription) | U3 |
| R9 (5-layer analysis) | U4 |
| R10 (Quick mode) | U1, U2, U5 |
| R11-R13 (HTML output) | U5 |
| R14-R15 (Credentials) | U6 |

---

## Output Structure

```
gravitas-skills/pitch-competitor-research/
  SKILL.md                     # Agent skill definition
  .env.example                 # Template for local credentials
  scripts/
    discover_competitors.py    # Handle discovery + AI recommendations
    scrape_competitor.py       # Multi-platform scraping orchestrator
    transcribe_videos.py       # yt-dlp download + Gemini/ChatGPT transcription
    analyze_competitor.py      # Campaign, KOL, theme, cadence analysis
    generate_html_report.py    # Executive brief HTML generation
  templates/
    executive_brief.html       # Jinja2/string template for HTML output
  references/
    gemini-prompts.md          # Prompt templates for AI analysis
```

---

## Implementation Units

### U1. Input & Discovery

- **Goal:** Collect competitor names and platform handles from the user, validate them, and recommend additional competitors or missing handles.
- **Requirements:** R1, R2, R3, R10
- **Dependencies:** None (first unit)
- **Files:**
  - `pitch-competitor-research/scripts/discover_competitors.py` (create)
  - `pitch-competitor-research/SKILL.md` (create — Phase 1 routing section)
- **Approach:**
  - Agent asks (via `ask_user`) for competitor names and exact platform handles (FB URL, IG handle, TikTok username, YT channel URL, LI page URL).
  - Script validates handle formats and checks Supabase `competitor_profiles` for existing entries.
  - After initial scrape (U2), script cross-references discovered @mentions and tagged accounts against the user's list — suggests additions.
  - Quick mode flag skips the recommendation step.
- **Patterns to follow:** gravitas-data-manager Phase 1 routing, gravitas-gateway Phase 2 ask_user pattern.
- **Test scenarios:**
  - Given user provides "Enfagrow" with @enfagrowmy IG handle → validates format, returns structured competitor dict.
  - Given user provides malformed handle ("just a name") → prompts for platform-specific handle.
  - Given scrape discovers @enfagrowmy_tiktok not in original list → agent asks "Found TikTok handle — include?"
  - Given quick mode → skips recommendation step.
- **Verification:** Agent interactive flow works end-to-end for input collection. Supabase lookup resolves existing profiles.

---

### U2. Multi-Platform Scraping

- **Goal:** Scrape competitor posts across all five platforms using the appropriate tool per platform.
- **Requirements:** R4, R5, R6, R10
- **Dependencies:** U1 (needs competitor handles), U6 (needs credentials)
- **Files:**
  - `pitch-competitor-research/scripts/scrape_competitor.py` (create)
- **Approach:**
  - **FB, YouTube, LinkedIn:** Route to Metricool API using METRICOOL_TOKEN from gateway. Pull posts within date range.
  - **Instagram, TikTok:** Route to Instaloader (default) or Apify (fallback). Agent presents trade-off: Instaloader free but uses personal IG session; Apify costs ~$5 credit but is more reliable.
  - Instagram: Call `gravitas-data-manager/scripts/ingest_ig_posts.py` via subprocess or import.
  - TikTok: Use Instaloader for public profile scraping; fall back to Apify TikTok actor.
  - All posts stored in Supabase `competitor_posts` with source labels (`instaloader`, `apify`, `metricool`).
  - Returns structured post data for U4 analysis.
- **Patterns to follow:** gravitas-data-manager Phase 2 scraping flow, ig_utils.py Supabase connection pattern.
- **Test scenarios:**
  - Given IG handle and Instaloader choice → scrapes IG posts, stores in competitor_posts with source=`instaloader`.
  - Given FB page URL → pulls via Metricool, stores with source=`metricool`.
  - Given Apify chosen → uses APIFY_API_KEY from gateway, normalizes into competitor_posts.
  - Given no Instaloader session → fails gracefully with clear "run instaloader --login" message.
  - Given rate limit hit → reports how many posts were captured before limit.
- **Verification:** Posts appear in Supabase with correct platform, source label, and date range. Post count matches expected.

---

### U3. Video Transcription Pipeline

- **Goal:** Download all video posts via yt-dlp and transcribe them using Gemini (primary) or ChatGPT/OpenAI (fallback).
- **Requirements:** R7, R8
- **Dependencies:** U2 (needs scraped posts with video URLs)
- **Files:**
  - `pitch-competitor-research/scripts/transcribe_videos.py` (create)
- **Approach:**
  - Filter posts by media_type = video/reel from U2 output.
  - For each video: download via `yt-dlp` to temp directory.
  - Extract audio if needed (ffmpeg) or send video directly to Gemini.
  - Transcribe via Gemini API (google-generativeai SDK). If Gemini fails (rate limit, auth), fall back to OpenAI Whisper API.
  - Attach transcript to post record in ephemeral JSON.
  - Clean up temp files after transcription.
  - Track progress — show "Transcribed 12/15 videos..."
- **Patterns to follow:** yt-dlp CLI usage from youtube-publish-date-bulk skill.
- **Test scenarios:**
  - Given 5 IG Reels → downloads all 5, transcribes via Gemini, returns transcripts.
  - Given Gemini rate-limited → falls back to OpenAI Whisper API for remaining videos.
  - Given video download fails (private/deleted) → skips with note "Video unavailable: [url]".
  - Given 0 video posts → skips transcription entirely, notes "No video content to transcribe."
- **Verification:** Transcripts are attached to correct post records. Temp files cleaned. Progress reporting works.

---

### U4. AI Analysis Layer

- **Goal:** Analyze scraped posts + transcripts to produce the 5-layer competitor dossier: campaigns, KOLs, content themes, cadence, and benchmarks.
- **Requirements:** R9
- **Dependencies:** U2 (needs posts), U3 (needs transcripts)
- **Files:**
  - `pitch-competitor-research/scripts/analyze_competitor.py` (create)
  - `pitch-competitor-research/references/gemini-prompts.md` (create)
- **Approach:**
  - **KOLs (deterministic):** Extract from collab flags + tagged_users in post metadata. Count posts per KOL, compute avg engagement. Estimate follower tier from public profile data.
  - **Campaigns (Gemini):** Send batched posts (title, date, hashtags, caption summary) to Gemini with prompt: "Group these posts into campaigns. For each campaign, provide: name, date range, platforms, key message, hashtags used." Output as structured JSON.
  - **Content themes (Gemini):** Send captions + transcripts to Gemini with prompt: "Identify recurring content themes, tone, visual style patterns, and CTA patterns." Output as categorized distribution.
  - **Cadence (computed):** Timestamp analysis — posts per week by platform, best day/time by engagement.
  - **Benchmarks (computed):** Avg/median ER by format and platform.
  - All analysis stored as ephemeral JSON (not Supabase). Passed to U5 for HTML rendering.
- **Patterns to follow:** Gemini API usage from existing Gravitas transcription patterns.
- **Test scenarios:**
  - Given 50 posts from one competitor → detects 3 campaigns with date ranges, platforms, and hashtags.
  - Given collab posts with tagged users → extracts KOL list with post counts and engagement.
  - Given captions across 100 posts → identifies top 5 content themes with distribution percentages.
  - Given 3 months of post timestamps → computes posting frequency by platform/day/time.
  - Given engagement data → computes avg ER by format (image, reel, carousel).
- **Verification:** Analysis JSON validates against expected schema. Campaign detection finds known campaigns in test data. Theme distribution sums to 100%.

---

### U5. HTML Executive Brief

- **Goal:** Generate a single-page HTML executive brief from the analysis data.
- **Requirements:** R11, R12, R13, R10
- **Dependencies:** U4 (needs analysis JSON)
- **Files:**
  - `pitch-competitor-research/scripts/generate_html_report.py` (create)
  - `pitch-competitor-research/templates/executive_brief.html` (create)
- **Approach:**
  - Single HTML file, no external dependencies (inline CSS, no CDN).
  - Sections (top to bottom):
    1. **Header:** Competitor names, date range, platforms covered
    2. **Executive Summary:** 3-5 key findings in callout boxes
    3. **Per-Competitor Sections:** Platform breakdown with key stats
    4. **Campaign Timeline:** Horizontal timeline with campaign bars
    5. **KOL Roster:** Table with KOL name, platform, follower est., avg ER, post count
    6. **Content Themes:** Horizontal bar chart (pure CSS) showing theme distribution
    7. **Cadence Heatmap:** Day-of-week × time-of-day grid
    8. **Engagement Benchmarks:** Format comparison table
  - Every data point links to source post permalink (R12).
  - Quick mode output is a stripped-down version — summary + campaign timeline + KOLs only.
  - Agent opens the HTML file automatically after generation (R13).
  - Use Python string templating (no heavy framework — consistent with existing skills).
- **Patterns to follow:** visual_review.py HTML generation pattern, performance-social-report-slides HTML gallery pattern.
- **Test scenarios:**
  - Given full 5-layer analysis → generates HTML with all 8 sections, opens in browser.
  - Given quick mode analysis → generates stripped HTML with 3 sections.
  - Given analysis with 3 competitors → each competitor has its own section, timeline shows all 3.
  - Given a KOL with 4 posts → clicking KOL name shows linked post permalinks.
  - Given no KOLs found → KOL section shows "No KOL collaborations detected."
- **Verification:** HTML renders correctly in browser. All sections present. Links work. No broken images. File opens automatically.

---

### U6. Integration & Wiring

- **Goal:** Wire the skill into the Gravitas ecosystem — gateway credentials, script dependencies, skill registration.
- **Requirements:** R14, R15
- **Dependencies:** U1-U5 (wiring happens alongside development)
- **Files:**
  - `pitch-competitor-research/SKILL.md` (create — full skill definition)
  - `pitch-competitor-research/.env.example` (create)
  - `gravitas-gateway/SKILL.md` (modify — add to secret→skill mapping)
- **Approach:**
  - SKILL.md follows the 6-phase runtime pattern established in gravitas-gateway:
    - Phase 0: Credentials (fetch from gateway.shazan.me — METRICOOL_TOKEN, APIFY_API_KEY, SUPABASE_SERVICE_ROLE_KEY)
    - Phase 1: Route (full research vs quick snapshot)
    - Phase 2: Input & Discovery (U1)
    - Phase 3: Scraping (U2)
    - Phase 4: Transcription (U3) — skipped in quick mode
    - Phase 5: AI Analysis (U4)
    - Phase 6: HTML Output (U5)
  - .env.example: Only per-user credentials (Instaloader session path, output directory).
  - Update gravitas-gateway secret→skill mapping: add `pitch-competitor-research` → `METRICOOL_TOKEN` + `APIFY_API_KEY` + `SUPABASE_SERVICE_ROLE_KEY` + Meta token.
  - Install dependencies section in SKILL.md: `pip install yt-dlp google-generativeai openai openpyxl requests supabase`.
- **Patterns to follow:** gravitas-gateway SKILL.md structure, gravitas-data-manager Phase 0 credential pattern.
- **Test scenarios:**
  - Given fresh clone → `pip install` installs all deps.
  - Given gateway reachable → Phase 0 fetches all 4 secrets successfully.
  - Given missing Instaloader session → agent guides user through `instaloader --login`.
- **Verification:** Skill loads cleanly via `gravitas-gateway`. All scripts import successfully. Gateway auth works end-to-end.

---

## Key Technical Decisions

- **Separate skill, reuse scripts:** `pitch-competitor-research` is its own skill with its own scripts. It imports from `gravitas-data-manager/scripts/` for IG scraping (ingest_ig_posts.py, ig_utils.py) rather than duplicating. Path: use relative import with `sys.path` manipulation (same pattern as existing scripts).
- **Ephemeral analysis JSON:** Analysis results (campaigns, themes, cadence) are stored as JSON files in the output directory, not in Supabase. Only raw posts go to `competitor_posts`. This avoids schema migration and keeps the analysis layer flexible for iteration.
- **yt-dlp as subprocess:** Video download uses `subprocess.run(['yt-dlp', ...])` rather than the Python API — consistent with how youtube-publish-date-bulk uses it, simpler dependency management.
- **HTML: inline everything:** No external CSS/JS/fonts. Single self-contained file. Uses pure CSS for charts (bar charts via flexbox widths, heatmap via CSS grid). This makes the file portable — email it, open offline, no build step.
- **Gemini prompt templates in references/**: Keeps prompts editable without touching code. Same pattern as intel-db-schema.md.

---

## Scope Boundaries

- v1 is agent-native (CLI/chat trigger). No web dashboard, Slack bot, or scheduled runs.
- Output is local HTML file. No hosted URL or automatic sharing.
- FB, IG, TikTok, YouTube, LinkedIn only. No website scraping, SEM/ads, CRM data.
- Campaign detection is AI-assisted (Gemini), not human-verified.
- KOL follower counts are AI-estimated from public data — not verified.
- No PPTX output. HTML only.
- Single snapshot per pitch. No historical trend comparison.
- Organic content only. No paid media / ads library.

### Deferred to Follow-Up Work

- Slack bot trigger ("/pitch research @competitor")
- Hosted HTML URL for team sharing (deploy to Coolify)
- PPTX export via performance-social-report-slides integration
- Historical trend comparison across multiple time periods
- Paid media / Facebook Ads Library analysis
- Website scraping for landing page / SEO analysis
- Scheduled recurring competitor monitoring

---

## Dependencies / Assumptions

- **gravitas-gateway**: All shared credentials available at gateway.shazan.me (METRICOOL_TOKEN, APIFY_API_KEY, SUPABASE_SERVICE_ROLE_KEY, Meta tokens).
- **gravitas-data-manager scripts**: IG scraping scripts (ingest_ig_posts.py, ig_utils.py, export_ig_xlsx.py) are importable from `gravitas-data-manager/scripts/`.
- **metricool skill**: FB, YouTube, LinkedIn, TikTok data from Metricool API. Brand must be connected in Metricool.
- **yt-dlp**: Installed via pip. Handles TikTok, YouTube, Instagram video downloads.
- **Gemini API**: Available via `google-generativeai` Python SDK with API key.
- **OpenAI API**: Available as fallback for transcription.
- **Instaloader session**: User has valid session at configured path.
- **Supabase**: competitor_posts table exists. No new tables needed.
- **ffmpeg**: Available on PATH for audio extraction from video files (optional — Gemini can accept video directly).

---

## Outstanding Questions

### Resolve Before Planning

(None — all blockers resolved in brainstorm.)

### Deferred to Implementation

- [Affects U4][Needs research] Optimal batch size for Gemini campaign detection (how many posts per prompt before quality degrades).
- [Affects U3][Needs research] yt-dlp TikTok support — verify public profile download without login.
- [Affects U1][Needs research] How the agent discovers missing competitor handles — search Supabase, Metricool connected accounts, web search?
- [Affects U5][Technical] Specific CSS approach for bar charts and heatmap — determine during implementation based on data density.
- [Affects U4][Technical] Gemini output JSON schema — exact field names and structure to be finalized when writing prompts.
