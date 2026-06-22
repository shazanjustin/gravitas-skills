---
name: gravitas-gateway
description: >
  Central credential layer for all Gravitas AI agent skills. Teaches agents how
  to authenticate with the Gravitas API Gateway (gateway.shazan.me) and fetch
  API keys for Metricool, Apify, Meta Graph API, and other Gravitas services.
  Load this skill FIRST before any other Gravitas skill that needs API keys.
compatibility: |
  Requires curl. The gateway key must be set in ~/.gravitas-skills/.env
  (one-time setup). Git required for auto-updates.
---

# Gravitas API Gateway — Credential Skill

**Load this skill before any other Gravitas skill.** It provides the shared
authentication layer for all Gravitas API access.

## One-Time Setup

If this is your first time using Gravitas skills, run these commands once:

```bash
git clone https://github.com/shazanjustin/gravitas-skills.git ~/.gravitas-skills
cp ~/.gravitas-skills/.env.example ~/.gravitas-skills/.env
```

Then edit `~/.gravitas-skills/.env` and paste your gateway API key:

```bash
GRAVITAS_GATEWAY_KEY=your-key-here
GRAVITAS_GATEWAY_URL=https://gateway.shazan.me
```

Get the key from Shazan or your team lead.

## Auto-Update (Run Before Every Skill)

Before using ANY Gravitas skill, always pull the latest skill definitions:

```bash
cd ~/.gravitas-skills && git pull
```

If the folder doesn't exist, guide the user through the one-time setup above.

This keeps all skills current without the user thinking about it. New secrets,
new endpoints, and fixes arrive automatically.

## Authentication

Every request to the gateway must include the API key in the `x-api-key` header:

```bash
source ~/.gravitas-skills/.env
curl -H "x-api-key: $GRAVITAS_GATEWAY_KEY" "$GRAVITAS_GATEWAY_URL/secrets"
```

The gateway returns 401 if the key is missing or wrong.

## Available Endpoints

### Static Secrets (API Keys)

| Endpoint | Returns | Used By |
|----------|---------|---------|
| `GET /secret/METRICOOL_TOKEN` | `{name, value}` — Metricool personal token | metricool, metricool-engagement-rate-xlsx, performance-social-report-slides |
| `GET /secret/APIFY_API_KEY` | `{name, value}` — Apify API key | intel-ig-manager, gravitas-data-manager |
| `GET /secrets` | `{secrets: [...]}` — list of available secret names (no values) | Discovery / debugging |

Example:

```bash
source ~/.gravitas-skills/.env
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN"
# → {"name":"METRICOOL_TOKEN","value":"JWEJMBCYSNQ..."}
```

### Meta Graph API (Facebook / Instagram)

| Endpoint | Description |
|----------|-------------|
| `GET /token` | Returns a page access token + page ID + expiry. Auto-refreshes. |
| `GET /pages` | Lists all accessible Facebook pages with linked Instagram business accounts |
| `GET /thumbnail?platform=fb\|ig&post_id=<id>` | Returns `{thumbnail_url}` for a post |
| `GET /comments?platform=fb\|ig&post_id=<id>` | Returns comments array for a post |

Example:

```bash
source ~/.gravitas-skills/.env
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/token"
# → {"page_access_token":"EAAcb7...","page_id":"113376605363982","expires_at":1749000000}
```

Use the returned `page_access_token` directly with Facebook's Graph API:

```bash
curl "https://graph.facebook.com/v25.0/me?access_token=<page_access_token>"
```

## Secret → Skill Mapping

When a Gravitas skill says "load gravitas-gateway first," fetch the
corresponding secret:

| Skill | Secret to Fetch | How |
|-------|----------------|-----|
| `metricool` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `metricool-engagement-rate-xlsx` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `metricool-engagement-rate-xlsx-v2` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `performance-social-report-slides` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `intel-ig-manager` | `APIFY_API_KEY` + Meta token | `GET /secret/APIFY_API_KEY` + `GET /token` |
| `gravitas-data-manager` | `APIFY_API_KEY` | `GET /secret/APIFY_API_KEY` |
| `fb-ig-engagement-xlsx` | Meta token | `GET /token` |

## Full Agent Workflow

When an agent loads a Gravitas skill (e.g., metricool):

1. **Update:** `cd ~/.gravitas-skills && git pull` (skip if folder missing → guide setup)
2. **Load env:** `source ~/.gravitas-skills/.env`
3. **Fetch secret:** `curl -H "x-api-key: $GRAVITAS_GATEWAY_KEY" "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN"`
4. **Use it:** Pass the token to the Metricool API as documented in the metricool skill

The agent never stores or logs the secret value — fetch it, use it, let it
evaporate from context.

## Per-User Credentials (Not on the Gateway)

Some credentials are per-person and cannot be shared via the gateway. These
are stored in your local `~/.gravitas-skills/.env` and set up once.

### Instaloader (Instagram scraping)

Instaloader uses YOUR Instagram account to scrape public data. Each team
member needs their own session.

**One-time setup — agent guides the user:**

1. Check if `INSTALOADER_SESSION` is set in `~/.gravitas-skills/.env`
2. If not set, guide the user:
   ```bash
   pip install instaloader
   instaloader --login
   # → Enter your Instagram username and password
   # → Session saved to ~/.config/instaloader/session-<your_username>
   ```
3. Add the session path to `~/.gravitas-skills/.env`:
   ```
   INSTALOADER_SESSION=~/.config/instaloader/session-your_username
   ```
4. For Windows users, the path is typically:
   ```
   C:/Users/<name>/AppData/Local/Instaloader/session-<your_username>
   ```

Skills that use Instaloader (intel-ig-manager, gravitas-data-manager) will
read `INSTALOADER_SESSION` from this file. If it's missing, they'll fall back
to Apify (which uses the shared `APIFY_API_KEY` from the gateway).

### Credential Precedence

| Type | Source | Example |
|------|--------|---------|
| Shared team keys | Gateway (`gateway.shazan.me`) | METRICOOL_TOKEN, APIFY_API_KEY, Meta tokens |
| Per-user sessions | Local `.env` file | INSTALOADER_SESSION |
| Fallback env vars | Shell environment | `export METRICOOL_TOKEN=...` |

## Adding a New Secret

**Shared secret (add to gateway):**

1. Add the env var to the gateway worker (`wrangler secret put`)
2. Update this SKILL.md with the new secret name and mapping
3. Push to GitHub → next `git pull` picks it up

**Per-user credential (add to .env.example):**

1. Add the variable to `.env.example` with a comment explaining setup
2. Update this SKILL.md with setup instructions
3. Push to GitHub → team members add it to their local `.env` on next pull

No other skills change. No user action needed for shared secrets.
