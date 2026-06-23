---
date: 2026-06-22
topic: pitch-competitor-research
---

# Pitch Competitor Research

## Summary

A new agent skill that researches competitors for Gravitas pitch preparation — scrapes their social media across all platforms, transcribes their video content, and produces an executive-brief HTML dossier covering campaigns, KOLs, content themes, posting cadence, and engagement benchmarks.

---

## Problem Frame

Gravitas pitches for accounts like Friso Gold (RM1M+) and SMU (RM400K+) require competitor intelligence — what are competing brands doing on social media, who are they collaborating with, what campaigns are they running, and what content strategies are working for them. Today this is done manually: team members search platforms, copy-paste data into spreadsheets, and assemble findings by hand. It is slow, shallow, and inconsistent across pitches.

A single competitor deep-dive across Facebook, Instagram, TikTok, YouTube, and LinkedIn — with video content transcribed and analyzed — would take hours manually. The pitch team needs this intelligence to build a credible counter-positioning narrative, but the manual cost means it often doesn't happen at the depth that would make a difference.

---

## Actors

- A1. **Shazan / pitch lead**: Runs the skill, provides competitor names and platform handles, reviews the output, shares with the pitch team.
- A2. **Pitch team**: Consumers of the HTML dossier — use it to understand the competitive landscape and craft the pitch narrative.
- A3. **Agent (AI)**: Executes scraping, transcription, analysis, and HTML generation. Recommends additional competitors or handles when gaps are detected.

---

## Key Flows

- F1. **Full competitor research**
  - **Trigger:** Shazan invokes the skill with competitor names and platform handles.
  - **Actors:** A1, A3
  - **Steps:**
    1. Agent asks for competitor names and exact platform handles (FB, IG, TikTok, YouTube, LinkedIn).
    2. Agent recommends additional competitors or missing handles based on what it finds.
    3. Agent scrapes posts: Metricool for FB/YT/LI, Instaloader or Apify for IG/TT.
    4. Agent downloads all videos via yt-dlp and transcribes via Gemini/Whisper.
    5. Agent analyzes: extracts KOLs (deterministic from collab/tagged data), detects campaigns (Gemini clustering), identifies content themes (Gemini from captions + transcripts), computes cadence and benchmarks.
    6. Agent generates an executive-brief HTML file.
    7. Agent opens the HTML for review.
  - **Outcome:** A local HTML dossier with competitor intelligence, ready for pitch preparation.
  - **Covered by:** R1, R2, R3, R4, R5, R6, R7, R8, R9

- F2. **Quick competitor snapshot**
  - **Trigger:** Shazan wants a fast overview without full transcription.
  - **Actors:** A1, A3
  - **Steps:**
    1. Agent asks for competitor names and handles.
    2. Agent scrapes posts across platforms (no video download).
    3. Agent analyzes campaigns, KOLs, and cadence from post metadata and captions only.
    4. Agent generates a lightweight HTML brief.
  - **Outcome:** A faster, lighter competitor overview (no video analysis).
  - **Covered by:** R10

---

## Requirements

**Input & discovery**
- R1. Agent asks the user for competitor names before scraping.
- R2. Agent asks for exact platform handles (FB page URL, IG handle, TikTok username, YouTube channel, LinkedIn page) — one per competitor per platform.
- R3. After initial data pull, agent recommends additional competitors or missing platform handles it discovered (e.g., "Competitor X also has a TikTok at @xyz — want me to include it?").

**Scraping & data collection**
- R4. Agent pulls FB, YouTube, and LinkedIn data from Metricool when the brand is connected there.
- R5. Agent pulls Instagram and TikTok data via Instaloader (default) or Apify (fallback). Agent explains the trade-off to the user before scraping: Instaloader is free but uses the user's personal IG session; Apify costs money (~$5 free credit) but is more reliable.
- R6. Agent stores scraped posts in Supabase `competitor_posts` with source labels (`instaloader`, `apify`, `metricool`).

**Video transcription**
- R7. Agent downloads all video posts via yt-dlp and transcribes them using Gemini (or Whisper as fallback).
- R8. Agent attaches transcripts to post records in the analysis layer (ephemeral JSON, not Supabase).

**AI analysis**
- R9. Agent produces a 5-layer analysis for each competitor:
  - **Posts**: All scraped content with metrics and transcripts
  - **Campaigns**: Groups of related posts detected by Gemini (hashtags, timing, messaging patterns)
  - **KOLs**: Collaborators extracted deterministically from collab flags and tagged users
  - **Content themes**: Recurring topics, tone, visual style, CTA patterns — derived by Gemini from captions + transcripts
  - **Cadence & benchmarks**: Posting frequency by platform/day/time, engagement rate benchmarks by format

**Modes**
- R10. Agent supports a "quick mode" that skips video download and transcription — faster, but no content theme analysis from video. Useful for initial scans.

**Output**
- R11. Agent generates a single-page HTML executive brief with:
  - Executive summary (top — key findings in 3-5 bullets)
  - Per-competitor sections with platform breakdown
  - Campaign timeline visualization
  - KOL roster with engagement metrics
  - Content theme distribution (pie/bar charts)
  - Cadence heatmap (posting by day + time)
  - Engagement benchmarks by format
- R12. All claims in the HTML are linked to source posts (permalink) so findings are verifiable.
- R13. Agent opens the HTML file automatically upon completion.

**Credentials**
- R14. Agent fetches all shared credentials (Metricool token, Apify key, Supabase key) from `gateway.shazan.me` via gravitas-gateway.
- R15. Per-user credentials (Instaloader session) are read from local `.env`.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3.** Given Shazan says "research Enfagrow and Anmum for the Friso pitch", agent asks for their exact IG handles, FB pages, TikTok usernames, etc. After scraping, agent notices Enfagrow has a TikTok it wasn't told about and asks "Found @enfagrowmy on TikTok — include it?"
- AE2. **Covers R5.** Given Shazan chooses Instagram scraping, agent presents: "Instaloader (free, uses your IG session at C:/Users/dell/...) or Apify (~$5 credit, no personal account)?" and waits for choice.
- AE3. **Covers R9, R11, R12.** Given 3 competitors with ~100 posts each across 3 platforms, the HTML output has a campaign timeline showing Enfagrow's "Tahun Baru Cina" campaign spanning Jan 15-Feb 10 across IG and FB, with each campaign post linked to its permalink.
- AE4. **Covers R7, R8.** Given a competitor has 15 video posts, agent downloads all 15 via yt-dlp, transcribes them, and the content themes section reflects messaging extracted from the transcripts (e.g., "Enfagrow consistently says 'susu terbaik untuk perkembangan otak' — brain development claim repeated in 8/15 videos").
- AE5. **Covers R10.** Given Shazan chooses quick mode, agent skips yt-dlp and transcription entirely, and the output notes "Video content not analyzed (quick mode)."

---

## Success Criteria

- A pitch lead can go from "I want competitor research on X" to a reviewed HTML dossier in under 30 minutes (automated time), compared to hours of manual work.
- The HTML dossier is client-presentable — a pitch team member can open it and immediately understand the competitive landscape without prior context.
- Every data point in the dossier links back to its source post, so claims are defensible in a client meeting.
- The skill works without Shazan pasting any API keys — all shared secrets come from the gateway.

---

## Scope Boundaries

- v1 is agent-native (CLI/chat trigger). No web dashboard, no Slack bot, no scheduled runs.
- Output is a local HTML file. No hosted URL, no automatic sharing.
- Only social media platforms are covered (FB, IG, TikTok, YouTube, LinkedIn). No website scraping, no SEM/ads intelligence, no CRM data.
- Campaign detection is AI-assisted (Gemini), not human-verified. Agent surfaces campaigns with confidence indicators.
- KOL follower counts and cost estimates are AI-estimated from public data — not verified.
- No integration with Gravitas pitch deck generation (PPTX). HTML only.
- No historical trend comparison across time periods. Single snapshot per pitch.
- No paid media / ads library analysis. Organic content only.

---

## Key Decisions

- **Separate skill, not a path in gravitas-data-manager**: The pitch workflow has its own UX (competitor name input, AI recommendations, video transcription, HTML output) that is distinct from day-to-day data management. Reuses gravitas-data-manager scripts for scraping but is its own skill.
- **Ephemeral analysis, not new DB tables**: Campaigns, themes, and cadence are generated fresh per pitch as JSON. Only raw posts go into Supabase (reusable). Avoids schema migration and keeps the analysis layer flexible.
- **Hybrid AI: deterministic KOLs, Gemini for campaigns/themes**: KOL extraction is deterministic from existing collab/tagged-user data (no AI needed). Campaign detection and theme analysis use Gemini because they require pattern recognition across text.
- **All-video transcription**: Ambitious but thorough — for a pitch, incomplete intelligence is worse than slow intelligence. yt-dlp handles download; Gemini free tier handles transcription.
- **Executive brief HTML, single page**: Scannable, presentation-ready. Not an interactive dashboard. Designed for a meeting, not exploration.

---

## Dependencies / Assumptions

- **gravitas-gateway**: All shared credentials (Metricool, Apify, Supabase, Meta tokens) must be available at `gateway.shazan.me`.
- **gravitas-data-manager scripts**: IG scraping (ingest_ig_posts.py, export_ig_xlsx.py) and Supabase utilities (ig_utils.py) are reused from gravitas-data-manager.
- **metricool skill**: FB, YouTube, and LinkedIn data come from Metricool API. Assumes the brand is connected in Metricool.
- **yt-dlp**: Must be installed on the user's machine (`pip install yt-dlp`). Handles TikTok, YouTube, Instagram video downloads.
- **Gemini API**: Available via Google AI Studio free tier for transcription and content analysis. ChatGPT/OpenAI Whisper API as transcription fallback.
- **Instaloader session**: User must have a valid Instagram session file from `instaloader --login`.
- **Supabase**: `competitor_posts` table exists with current schema. No new tables needed.
- **Competitor profiles**: Competitor entries exist in Supabase `competitor_profiles` or can be created on-the-fly.

---

## Outstanding Questions

### Resolve Before Planning

- [Affects R4][Product] Should LinkedIn data come from Metricool or is it low-priority enough to skip for v1? LinkedIn competitor content is often sparse.
- [Affects R7][Product] Is Whisper (local) the preferred transcription fallback, or is Gemini sufficient alone? Whisper requires local GPU/CPU — may not work on all machines.
  - **Resolved:** Gemini primary, ChatGPT/OpenAI Whisper API as cloud fallback. No local Whisper needed.

### Deferred to Planning

- [Affects R9][Technical] What is the Gemini prompt structure for campaign detection and theme analysis? (How many posts per prompt, what output format, confidence scoring.)
- [Affects R11][Technical] What charting library for the HTML? (Chart.js vs D3 vs plain CSS — affects bundle size and rendering.)
- [Affects R7][Needs research] yt-dlp TikTok support — verify it can download without login for public profiles.
- [Affects R3][Needs research] How does the agent discover missing competitor handles? (Search handles in Supabase, check Metricool connected accounts, web search?)
