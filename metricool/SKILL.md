---
name: metricool
description: >
  Use Metricool's REST API to pull analytics, manage scheduled posts, check
  competitors, and generate reports across any Metricool-connected account.
  Triggers when the user asks about social media analytics, post performance,
  engagement data, follower stats, scheduled content, competitor analysis, or
  Metricool API usage.
compatibility: |
  Requires curl and Python 3.8+ for JSON handling. The helper script
  `scripts/metricool.sh` wraps the API for convenience.
---

# Metricool API — Gravitas Skill

> **Prerequisite:** Load the `gravitas-gateway` skill first to obtain your
> Metricool API token. The gateway skill auto-updates and fetches
> `METRICOOL_TOKEN` from `gateway.shazan.me` — no local `.env` setup needed.

Metricool's REST API provides programmatic access to social media analytics,
scheduling, competitors, inbox, and more for all connected brands.

## API Overview

| Item | Value |
|------|-------|
| **Base URL** | `https://app.metricool.com/api` |
| **Auth params** | `userToken`, `userId`, `blogId` (query params or `X-Mc-Auth` header for token) |
| **Live Swagger** | `https://app.metricool.com/api/swagger.json` (357+ endpoints) |
| **PDF** | `https://static.metricool.com/API+DOC/API+English.pdf` |

## Brands — Discovered Live

Brands are **not hardcoded** here — the account may change over time. Always
discover them at runtime:

```bash
bash scripts/metricool.sh brands
```

To see which social networks a specific brand has connected:
```bash
bash scripts/metricool.sh info <blogId>
bash scripts/metricool.sh networks <blogId>
```

The script automatically fetches the latest brand list and network connections
from the API every time you run a command.

## Authentication

**Primary method — Gravitas Gateway (recommended):**

Load the `gravitas-gateway` skill. It fetches `METRICOOL_TOKEN` from
`gateway.shazan.me` using the shared team API key. The agent handles this
automatically — the user never sees or pastes the token.

```bash
# Agent workflow:
source ~/.gravitas-skills/.env
METRICOOL_TOKEN=$(curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")
export METRICOOL_TOKEN
```

The API uses three parameters on every call:
```text
blogId=<blogId>&userId=<userId>&userToken=<token>
```

### Fallback: local .env file

If the gateway is unavailable, the script falls back to a local `.env` file:

```bash
bash scripts/metricool.sh setup
# → Paste your API token from Metricool → Account Settings → API
# → Optionally change user ID (default: 4327762)
```

### Fallback: environment variable

```bash
export METRICOOL_TOKEN=your_token_here
export METRICOOL_USER_ID=4327762  # optional, has a default
```

### Precedence (highest to lowest)
1. Gateway-fetched token (via `gravitas-gateway` skill)
2. `$METRICOOL_TOKEN` env var (already set before running)
3. `.env` file (created by `setup` command)

### Security rules for the agent

1. **Never hardcode the userToken** in files or output. Use `$METRICOOL_TOKEN`,
   `.env`, or ask the user.
2. **Treat the token as sensitive** — don't echo it, log it, or paste it raw.
3. **If unset**, run `setup` or tell the user to export the variable.
4. **The `.env` file is gitignored** — never suggest committing it.

## Helper Script

`scripts/metricool.sh` handles auth, JSON formatting, and network discovery.

### Quick start

```bash
# One-time setup (prompts for API token, saves to .gitignored .env)
bash scripts/metricool.sh setup

# Then just use it:
bash scripts/metricool.sh brands              # list all brands
bash scripts/metricool.sh info 5578428         # brand details + networks
bash scripts/metricool.sh networks 5578428     # which social networks
bash scripts/metricool.sh posts instagram 5578522  # posts for a brand+network
bash scripts/metricool.sh swagger --list       # list all API services
bash scripts/metricool.sh swagger --search tiktok  # search endpoints by keyword
bash scripts/metricool.sh swagger --service "Analytics Api Service"  # show service endpoints
```

The script is **network-aware**: if you ask for Instagram posts on a brand
without Instagram, it'll tell you which brands DO have Instagram.

## Key Endpoints — Overview

This is a summary of the main endpoint groups. For the **complete, up-to-date
list**, use the `swagger` command (see above) which queries the live API spec.

### Analytics — Posts per Network

| Network | v2 Endpoint |
|---------|-------------|
| Instagram Posts | `GET /v2/analytics/posts/instagram` |
| Instagram Reels | `GET /v2/analytics/reels/instagram` |
| Instagram Stories | `GET /v2/analytics/stories/instagram` |
| Facebook Posts | `GET /v2/analytics/posts/facebook` |
| Facebook Reels | `GET /v2/analytics/reels/facebook` |
| Facebook Stories | `GET /v2/analytics/stories/facebook` |
| LinkedIn Posts | `GET /v2/analytics/posts/linkedin` |
| TikTok Posts | `GET /v2/analytics/posts/tiktok` |
| Twitter/X Posts | `GET /v2/analytics/posts/twitter` |
| Bluesky Posts | `GET /v2/analytics/posts/bluesky` |
| Threads Posts | `GET /v2/analytics/posts/threads` |
| Pinterest Pins | `GET /v2/analytics/posts/pinterest` |
| YouTube | `GET /v2/analytics/catalogs/accounts/youtube` |

**Query params:** `from=YYYY-MM-DDThh:mm:ss`, `to=YYYY-MM-DDThh:mm:ss`, `page=0`, `size=50`

> ⚠️ v2 endpoints require ISO datetime (`2026-04-12T00:00:00`). Legacy `/stats/`
> endpoints accept plain `YYYY-MM-DD`.

### Analytics — Aggregated & Timeseries

| Endpoint | Purpose |
|----------|---------|
| `GET /v2/analytics/aggregation` | Aggregated metrics across networks |
| `GET /v2/analytics/distribution` | Metric distributions |
| `GET /v2/analytics/timelines?metric=...` | Time series for one metric |
| `GET /v2/analytics/hashtags` | Popular hashtags |
| `GET /v2/analytics/brand-summary/posts` | Brand-level post summary |

### Competitors

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/v2/analytics/competitors/{network}` | List competitors |
| POST | `/v2/analytics/competitors/{network}` | Add a competitor |
| DELETE | `/v2/analytics/competitors/{network}` | Remove a competitor |
| GET | `/v2/analytics/competitors/{network}/posts` | Competitor posts |
| GET | `/v2/analytics/competitors/{competitorId}/timelines` | Metric timeline |
| PATCH | `/v2/analytics/competitors/{network}/{competitorId}` | Set favorite |

**Networks:** `facebook`, `instagram`, `twitter`, `youtube`, `tiktok`, `bluesky`, `twitch`

### Scheduler

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/v2/scheduler/posts` | Scheduled posts between dates |
| POST | `/v2/scheduler/posts` | Create a scheduled post |
| GET | `/v2/scheduler/posts/{id}` | Get post by ID |
| PUT/DELETE/PATCH | `/v2/scheduler/posts/{id}` | Update/delete/edit |
| GET | `/v2/scheduler/library/posts` | Library posts |
| GET | `/v2/scheduler/besttimes/{provider}` | Best times to post |
| GET | `/v2/scheduler/counters` | Scheduling counters |

### Other Services

| Service | Quick Ref |
|---------|-----------|
| **Inbox** | `GET /v2/inbox/conversations`, `/post-comments`, `/reviews` |
| **Smart Links** | `GET /v2/smart-links/links`, `.../{id}/analytics/timeline` |
| **AI** | `POST /v2/integrations/ai/posts`, `/natural-language-scheduling` |
| **Dashboards** | `GET /v2/reporting/campaigns-dashboard`, `.../{id}/analytics` |
| **Brands/Settings** | `GET /v2/settings/brands`, `/v2/settings/brands/{id}` |
| **Legacy Stats** | `GET /stats/values/{category}`, `/stats/timeline/{metric}`, `/stats/gender-age/{provider}` |

For anything not listed here, run:
```bash
bash scripts/metricool.sh swagger --search <keyword>
```

## Common Workflows

### 1. List brands and pick one

```bash
bash scripts/metricool.sh brands
# Pick a blogId, then:
bash scripts/metricool.sh info <blogId>
```

### 2. Get posts for a brand's network

```bash
# The script auto-checks if the brand has the network
bash scripts/metricool.sh posts instagram <blogId>
bash scripts/metricool.sh reels <blogId>
bash scripts/metricool.sh stories <blogId>
```

### 3. Best posting times

```bash
bash scripts/metricool.sh besttimes instagram <blogId>
```

### 4. List scheduled content

```bash
bash scripts/metricool.sh scheduled <blogId>
```

### 5. Track competitors

```bash
bash scripts/metricool.sh competitors instagram <blogId>
bash scripts/metricool.sh competitor-posts instagram <blogId>
```

### 6. Full export

```bash
bash scripts/metricool.sh export <blogId> 2026-04-12 2026-05-12
```

### 7. Discover what the API can do

```bash
# List all services
bash scripts/metricool.sh swagger --list

# Search for something specific
bash scripts/metricool.sh swagger --search linkedin
bash scripts/metricool.sh swagger --search "scheduler"
bash scripts/metricool.sh swagger --service "Stats Service"
```

### 8. Competitor report straight into a Google Sheet

**Use this instead of hand-assembling competitor pulls.** Anything shaped like
"get <competitors> data for <period> into a sheet" is one command:

```bash
node scripts/competitor-report.mjs \
  --brand "CIMB Malaysia" \
  --competitors "Maybank,RHB Group" \
  --from 2026-01-01 --to 2026-06-30
```

It resolves the brand and competitor ids at runtime, pulls every network in
parallel, builds a Summary tab plus per-network post tabs, and creates the
spreadsheet — about 20 seconds end to end, of which under a second is Metricool.

| Flag | Default | Notes |
|------|---------|-------|
| `--brand` | required | substring match against the live brand list |
| `--competitors` | required | comma-separated, substring match per network |
| `--from` / `--to` | required | `YYYY-MM-DD`, inclusive |
| `--networks` | `facebook,instagram,youtube` | Instagram always yields both Posts and Reels tabs |
| `--tz` | `Asia/Kuala_Lumpur` | affects output timestamps only |
| `--sheet <id>` | — | write into an existing spreadsheet instead of creating one |
| `--title` / `--folder` | — | title and Drive folder for a newly created sheet |
| `--json <path>` | — | also dump the shaped data |
| `--dry-run` | — | fetch and summarise, write nothing |

Why it exists: doing this conversationally costs ~33 sequential tool calls, and
in ev's Discord daemon that overruns the 280s turn budget — the spreadsheet gets
created and left **empty** while the reply still looks like success. The API work
is not the bottleneck; the model round-trips are.

Three things the script encodes that are easy to get wrong by hand:

- Competitor endpoints need `from`, `to`, `timezone` **and** `limit` or they 400,
  one missing param at a time.
- `competitors[]` on the collection endpoints is quietly ignored — you get
  everyone's posts back. Use `/{network}/{competitorId}/{posts|reels}` instead.
- Responses are stamped with Metricool's **own** account timezone no matter what
  `timezone` you send, so derive timestamps from the epoch field, never from
  `dateTime`. Trusting `dateTime` silently shifts every row.

Writing the sheet needs `COMPOSIO_MCP_URL` and `COMPOSIO_API_KEY`; without them
use `--dry-run`.

## Rules for the Agent

1. **Never hardcode brand IDs or the userToken.** Discover brands at runtime via
   `brands` / `info`.

2. **Ask before mutating** (POST, PUT, DELETE, PATCH). GET calls are safe if the
   user asked for data.

3. **Network-aware defaults.** If the user says "get my Instagram posts" without
   specifying a brand, run `brands` first, check which brands have Instagram via
   `info`, then ask or pick the most relevant one.

4. **Prefer v2 endpoints.** Fall back to `/stats/` only if no v2 equivalent exists.

5. **Default to last 30 days** for date ranges unless the user specifies otherwise.

6. **When the user asks "what can Metricool do?"**, either point to the table
   above or run `swagger --list` / `swagger --search <topic>` for the live list.

7. **For large exports**, save to a JSON file via the `export` command.

8. **If the swagger doesn't have what they need**, suggest the PDF at
   `https://static.metricool.com/API+DOC/API+English.pdf` as a secondary source.

9. **For competitor data destined for a sheet, run `competitor-report.mjs`**
   (workflow 8) rather than assembling the pulls yourself. Hand-assembly takes
   ~33 tool calls, which overruns a Discord turn and leaves an empty spreadsheet
   behind that still looks like a success.

## Installing This Skill

### For pi (recommended)

Symlinked from Gravitas Skills into pi's skills directory:
```bash
ln -s "D:/Vibe coding stuff/Gravitas Skills/metricool" "C:/Users/dell/.agents/skills/metricool"
```

### Direct usage

```bash
bash D:/Vibe\ coding\ stuff/Gravitas\ Skills/metricool/scripts/metricool.sh --help
```
