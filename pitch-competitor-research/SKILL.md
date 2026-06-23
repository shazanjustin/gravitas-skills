---
name: pitch-competitor-research
description: >
  End-to-end competitor research for Gravitas pitches. Scrapes social media
  across Facebook, Instagram, TikTok, YouTube, and LinkedIn, transcribes video
  content via OpenRouter, and produces an executive-brief HTML dossier covering
  campaigns, KOLs, content themes, posting cadence, and engagement benchmarks.
  Use when preparing for a new business pitch and you need deep competitor
  intelligence.
compatibility: |
  Requires Python 3.8+, yt-dlp, requests, supabase, openpyxl.
  Credentials via gravitas-gateway (gateway.shazan.me) for Metricool,
  Apify, Supabase. Per-user: OpenRouter API key, Instaloader session.
  ffmpeg recommended for audio extraction from large videos.
argument-hint: "[competitor names] [platform handles]"
---

# Pitch Competitor Research

Deep competitor intelligence for winning pitches. Scrapes → transcribes →
analyzes → outputs an executive brief you can present. All AI goes through
**OpenRouter** — one API key, access to Gemini Flash, ChatGPT, Claude.

## Phase 0: Credentials

Before anything, load `gravitas-gateway` if not already loaded this session
(`cd ~/.gravitas-skills && git pull`, source `.env`).

Fetch shared secrets:

```bash
source ~/.gravitas-skills/.env

# Metricool token (FB, YouTube, LinkedIn, TikTok data)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN"

# Apify token (IG/TT scraping fallback)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/APIFY_API_KEY"

# Supabase (Intel App database)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/SUPABASE_SERVICE_ROLE_KEY"

# Meta token (official insights if needed)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/token"

# OpenRouter API key (transcription + AI analysis)
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/OPENROUTER_API_KEY"
```

Export fetched values as env vars so scripts pick them up.

**Local credentials** (in `pitch-competitor-research/.env`, never committed):

```env
INSTALOADER_SESSION=C:/Users/...  # Path to Instagram session file
PITCH_OUTPUT_DIR=outputs/pitch-research
```

**Never print API keys or tokens in chat.**

---

## Phase 1: Route

Ask the user:

```
What kind of research do you need?

1. Full research — everything: scrape all platforms, transcribe all videos,
   full AI analysis, comprehensive HTML dossier. (30-60 min for 3 competitors)

2. Quick snapshot — faster: scrape posts only (no video download), lightweight
   analysis, stripped-down HTML. Good for initial landscape scan. (10-15 min)
```

| Choice | Go to |
|--------|-------|
| 1 — Full | Phase 2 (continue below) |
| 2 — Quick | Phase 2, then skip Phase 4 (Transcription), Phase 5 runs in quick mode |

---

## Phase 2: Input & Discovery

### Step 2a: Gather competitor names

Ask the user for competitor names and platform handles using `ask_user`:

```
List the competitors you want to research, with their platform handles:

Format: Name: @ighandle, fb.com/page, @tiktok, youtube.com/@channel, linkedin.com/company/name

Example:
  Enfagrow: @enfagrowmy, facebook.com/enfagrowmy
  Anmum: @anmumessentialmy, @anmumtiktok
```

Parse the input and validate handle formats:

```bash
python scripts/discover_competitors.py \
  --competitors "Enfagrow:@enfagrowmy,Anmum:@anmumessentialmy" \
  --platforms ig,fb,tt,yt,li
```

### Step 2b: Validation & warnings

Report any warnings (missing handles, unrecognized formats). If a competitor
is missing handles for key platforms, ask the user if they want to provide
them or skip those platforms.

### Step 2c: AI recommendations (post-scrape)

After scraping (Phase 3), check for @mentions and tagged accounts not in the
original list. If discovered, ask: "Found these additional accounts — include them?"

---

## Phase 3: Scraping

### Step 3a: Choose Instagram/TikTok source

For Instagram and TikTok, ask the user which scraping source:

```
How should we scrape Instagram and TikTok?

1. Instaloader (FREE)
   • Uses YOUR Instagram login session
   • Rate limited, session expires periodically
   • Captures collab posts, tagged users, post types

2. Apify (PAID, ~$5 free credit)
   • No personal account needed
   • More reliable, fewer rate limits
   • Better for large scrapes
```

### Step 3b: Date range

Ask for the research period. Accept YYYY-MM-DD to YYYY-MM-DD, or presets
("last 3 months", "Jan-Mar 2026").

### Step 3c: Execute scraping

The orchestrator routes each platform to the correct tool:

| Platform | Tool | Notes |
|----------|------|-------|
| Facebook | Metricool API | Pulls page posts with engagement |
| Instagram | Instaloader or Apify | Uses gravitas-data-manager scripts |
| TikTok | Instaloader or Apify | Public profile scraping |
| YouTube | Metricool API | Channel videos with metrics |
| LinkedIn | Metricool API | Company page posts |

All AI (transcription + analysis) goes through **OpenRouter** — one API key,
access to Gemini Flash, ChatGPT, Claude.

```bash
python scripts/scrape_competitor.py \
  --competitors '{"Enfagrow":{"ig":"@enfagrowmy","fb":"enfagrowmy"}}' \
  --platforms ig,fb,tt,yt,li \
  --from 2026-05-01 \
  --to 2026-05-31 \
  --ig-source instaloader \
  --output-dir outputs/pitch-research/2026-06-22
```

**Progress reporting:** Show "Scraping Enfagrow on Instagram... 45 posts found"
for each platform-competitor pair.

---

## Phase 4: Video Transcription (Full mode only)

In quick mode, skip this phase entirely. In full mode:

### Step 4a: Check dependencies

Verify `yt-dlp` and `requests` are installed:

```bash
pip install yt-dlp requests
```

### Step 4b: Download & transcribe via OpenRouter

```bash
python scripts/transcribe_videos.py \
  --posts-file outputs/pitch-research/2026-06-22/scrape_results.json \
  --output-dir outputs/pitch-research/2026-06-22
```

The script:
1. Filters posts to videos/reels only
2. Downloads each via yt-dlp
3. Transcribes via OpenRouter (Gemini Flash for video; extracts audio via ffmpeg for files >20MB)
4. Cleans up temp video files
5. Shows progress: "Transcribed 12/15 videos..."

**Known limitations:**
- Private/deleted videos will be skipped with a note
- TikTok downloads may require public profile access
- Large videos (>500MB) are skipped to save bandwidth

---

## Phase 5: AI Analysis

Run the 5-layer analysis on the scraped posts + transcripts:

```bash
python scripts/analyze_competitor.py \
  --posts-file outputs/pitch-research/2026-06-22/posts_with_transcripts.json \
  --output-dir outputs/pitch-research/2026-06-22
```

All analysis goes through OpenRouter (Gemini Flash by default).

What it produces:

| Layer | Method | Output |
|-------|--------|--------|
| Campaigns | AI clustering via OpenRouter | Campaign name, date range, key message, hashtags |
| KOLs | Deterministic (collab + tagged) | KOL name, platforms, post count, avg ER, tier est. |
| Content themes | AI from captions + transcripts | Theme distribution, tone, visual style, CTA patterns |
| Cadence | Computed from timestamps | Posts/week by platform, best day/time |
| Benchmarks | Computed from engagement | Avg/median ER by format + platform |

If OpenRouter is unavailable, falls back to simple hashtag-based campaign
detection and keyword-based theme analysis. The output notes which method was used.

Save analysis as `competitor_analysis.json`.

---

## Phase 6: HTML Output

Generate the executive brief:

```bash
python scripts/generate_html_report.py \
  --analysis-file outputs/pitch-research/2026-06-22/competitor_analysis.json \
  --output-dir outputs/pitch-research/2026-06-22 \
  --title "Friso Gold Pitch — Competitor Research"
```

Use `--quick` flag for quick mode (stripped-down output).

The HTML includes:
1. **Executive Summary** — 4 key metrics in callout cards
2. **Per-Competitor** — Platform breakdown with post counts, ER, top format
3. **Campaign Timeline** — Detected campaigns with date ranges and messaging
4. **KOL Roster** — Table with links to source posts
5. **Content Themes** — Bar chart showing theme distribution
6. **Posting Cadence** — Best day/time per platform
7. **Engagement Benchmarks** — Avg/median ER by format

The agent opens the HTML automatically upon completion.

Add `--no-open` to skip auto-opening.

---

## Quick Mode Summary

In quick mode, the flow is shorter:

1. Phase 2: Input & discovery
2. Phase 3: Scraping (metadata only)
3. **Skip Phase 4** (no video download/transcription)
4. Phase 5: AI analysis (from captions only — themes will be less rich)
5. Phase 6: HTML output with `--quick` flag

The output notes "Quick mode — video content not analyzed."

---

## Output Files

After a full run, the output directory contains:

```
outputs/pitch-research/2026-06-22/
  scrape_results.json              # Raw scrape data
  posts_with_transcripts.json      # Posts + video transcripts
  competitor_analysis.json         # 5-layer analysis
  competitor_research_report.html  # Executive brief (opens in browser)
```

---

## Dependencies

Install all at once:

```bash
pip install yt-dlp requests supabase openpyxl
```

Additional:
- **ffmpeg**: For audio extraction from large videos. `choco install ffmpeg` on Windows.
- **Instaloader**: For Instagram scraping. `pip install instaloader && instaloader --login _notakaki`
- **OpenRouter**: https://openrouter.ai/keys — one API key for all AI models

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/discover_competitors.py` | Validate handles, discover missing accounts |
| `scripts/scrape_competitor.py` | Multi-platform scraping orchestrator |
| `scripts/transcribe_videos.py` | yt-dlp download + OpenRouter transcription (Gemini Flash) |
| `scripts/analyze_competitor.py` | 5-layer AI analysis via OpenRouter |
| `scripts/generate_html_report.py` | Executive brief HTML generation |

All scripts accept `--help` for full argument lists.
