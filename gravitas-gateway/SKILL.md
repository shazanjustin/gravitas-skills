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

# Gravitas Gateway

**This is a runtime guide.** When this skill loads, follow the execution flow
below. Do not skip phases. Do not assume the key — you can only verify it by
calling the Cloudflare Worker.

---

## Phase 0: Introduce Yourself

Before checking anything, tell the user what this skill does in one sentence:

> This is the **Gravitas Gateway** — the credential layer for all Gravitas AI
> agent skills. Once set up, any Gravitas skill (Metricool reports, Apify
> scraping, Meta Graph API, Instagram data) can fetch its API keys from
> `gateway.shazan.me` without you pasting secrets ever again.

Then immediately proceed to Phase 1.

---

## Phase 1: Check Current State

Run these checks **silently** (don't narrate each one — just do them):

```bash
# Check if ~/.gravitas-skills exists and is a git repo
ls ~/.gravitas-skills/.git 2>/dev/null && echo "REPO_OK" || echo "NO_REPO"

# Check if .env exists
test -f ~/.gravitas-skills/.env && echo "ENV_OK" || echo "NO_ENV"
```

Then present the user with a one-line status summary and route:

| State | Route |
|-------|-------|
| `REPO_OK` + `ENV_OK` | Test existing key (Go to Phase 1b) |
| `REPO_OK` + `NO_ENV` | Need key → Phase 2 |
| `NO_REPO` + `ENV_OK` | Weird state — need repo → Phase 2 (clone fresh) |
| `NO_REPO` + `NO_ENV` | First time → Phase 2 |

### Phase 1b: Test Existing Key (skip if no .env)

If `.env` exists, source it and test the key against the gateway without
telling the user what the key is. **Do not use `curl -w` — it breaks on
Windows bash. Use `curl -v` and grep the HTTP status line instead:**

```bash
source ~/.gravitas-skills/.env
curl -sv -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secrets" 2>&1 | grep -c "< HTTP/.*200"
# > 0 means valid, 0 means invalid
```

Or simply check if the response body is valid JSON:

```bash
source ~/.gravitas-skills/.env
RESP=$(curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secrets" 2>/dev/null)
if echo "$RESP" | grep -q '"secrets"'; then
  echo "KEY_VALID"
else
  echo "KEY_INVALID"
fi
```

- `KEY_VALID` → Skip to Phase 5 (full verification), announce: "Gateway key is valid — re-verifying everything."
- `KEY_INVALID` → "Existing key is invalid (HTTP $CODE). Let's re-enter it." → Phase 2
- If `GRAVITAS_GATEWAY_URL` is unset or `curl` couldn't connect → "Cannot reach gateway.shazan.me. Check your network." → Stop, don't proceed.

---

## Phase 2: Ask for the Gateway Key

You, the agent, **do not know the key**. You cannot guess it, infer it, or
read it from anywhere except the gateway's own response. The only way to
verify a key is to send it to `gateway.shazan.me` and check the response.

Use `ask_user` to collect the key. Tell the user:

> The Gravitas Gateway runs on Cloudflare Workers at `gateway.shazan.me`.
> I need your gateway API key to authenticate. I'll test it immediately
> against the live endpoint — I can't know if it's correct until the
> gateway accepts it.

Ask:

```
"Paste your Gravitas Gateway API key"
```

Options: none needed (freeform only). `allowComment: true`.

Once the user provides the key, immediately test it (Phase 3). Do not write
it to disk yet. Do not echo it back.

---

## Phase 3: Verify the Key

Test the key against the Cloudflare Worker. **Do not use `curl -w` — it
breaks on Windows bash. Use `curl -v` and grep the status, or just check
the response body:**

```bash
curl -s -H "x-api-key: <user_key>" "https://gateway.shazan.me/secrets"
# 200 + {"secrets":[...]} = valid, 401 = invalid, no response = network issue
```

| Response | Meaning |
|----------|---------|
| JSON with `secrets` array | ✅ Valid key — proceed to Phase 4 |
| `401` or empty | ❌ Invalid key — go back to Phase 2 |
| Connection error / no response | ⚠️ Cannot reach gateway — check network. Tell the user and stop. |

**Show the user what was unlocked.** Parse the `secrets` array and announce.
List ONLY the skills that actually exist in `~/.gravitas-skills/` (run
`ls -d ~/.gravitas-skills/*/` to discover them). Example announcement:

> ✅ Key accepted! The gateway holds these secrets: `METRICOOL_TOKEN`, `APIFY_API_KEY`
>
> Available skills (🔑 = needs gateway, 🧩 = standalone):
>
> 🔑 **metricool** — pull analytics, manage posts, check competitors via Metricool API
> 🔑 **metricool-engagement-rate-xlsx** — per-post engagement proof workbooks (IG, TikTok, YouTube)
> 🔑 **metricool-engagement-rate-xlsx-v2** — improved version of the above
> 🔑 **performance-social-report-slides** — quarterly Excel → PPTX slides + thumbnail gallery
> 🔑 **gravitas-data-manager** — full FB/IG/TikTok workflow (profile→scrape→export→cross-platform)
> 🧩 **client-friendly-report-writer** — raw metrics → client-facing analysis
> 🧩 **datasheet-to-gsheet-mapper** — map messy CSVs to Google Sheets columns
> 🧩 **youtube-publish-date-bulk** — batch YouTube URLs → publish dates column

If the key fails (401), tell the user:

> ❌ Gateway returned 401 — that key was rejected.
> Make sure you copied the full key from your team lead / Shazan.
> Let's try again.

Go back to Phase 2. Max 3 attempts, then stop and mark blocked.

---

## Phase 4: Set Up the Repo

Now that the key is verified, set up the filesystem. The only durable state
is `~/.gravitas-skills/.env`. **Never write the key to any other file.**

### 4a: Clone (if needed)

If `~/.gravitas-skills/` is missing or not a git repo:

```bash
rm -rf ~/.gravitas-skills 2>/dev/null
git clone https://github.com/shazanjustin/gravitas-skills.git ~/.gravitas-skills
```

### 4b: Write .env

```bash
cat > ~/.gravitas-skills/.env << 'ENVEOF'
# Gravitas Skills — Environment Variables
# .env is gitignored — never committed.

GRAVITAS_GATEWAY_KEY=<the_verified_key>
GRAVITAS_GATEWAY_URL=https://gateway.shazan.me

# Per-user: Instagram session for Instaloader (your own IG account)
# Run: pip install instaloader && instaloader --login
INSTALOADER_SESSION=~/.config/instaloader/session-your_username
ENVEOF
```

Announce: "✅ `.env` written to `~/.gravitas-skills/.env`"

### 4c: Git pull (update skill definitions)

```bash
cd ~/.gravitas-skills && git pull
```

If this fails (no network, etc.), note it but continue — the skill definitions
on disk are the last clone and still usable.

---

## Phase 5: Full Verification

Run the complete verification suite. Show each result to the user.

### 5a: Load env + list secrets

```bash
source ~/.gravitas-skills/.env
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" "$GRAVITAS_GATEWAY_URL/secrets"
```

### 5b: Fetch each available secret (skip value display — just confirm retrieval)

For each secret name from 5a, confirm it returns JSON (don't use `-w`):

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/$SECRET_NAME" | grep -q '"value"' && echo "OK" || echo "FAIL"
```

### 5c: Test Meta account discovery

```bash
RESP_FILE=$(mktemp)
PYTHON_BIN=$(command -v python3 || command -v python)
trap 'rm -f "$RESP_FILE"' EXIT
if curl -sS --fail-with-body -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/pages" > "$RESP_FILE"; then
  "$PYTHON_BIN" -c 'import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d.get("pages"),list) and d["pages"], "no pages returned"; assert "access_token" not in json.dumps(d), "token leaked"' "$RESP_FILE" \
    && echo "OK" || echo "FAIL"
elif grep -q 'OAuthException' "$RESP_FILE"; then
  echo "META_TOKEN_NEEDS_REFRESH"
else
  echo "FAIL"
fi
```

If this prints `META_TOKEN_NEEDS_REFRESH`, the gateway key is valid but the
underlying Facebook source token must be renewed in the Worker secret/KV before
official FB/IG endpoints can be used. Do not use `/token` as the health check:
it is a stateful legacy single-page endpoint and may return either a selected
page token or `409 multiple_pages_found`.

### 5d: Summarize

Present a clean table:

```
     Gateway URL:  https://gateway.shazan.me
     Key status:   ✅ Valid (tested live)
     .env:         ~/.gravitas-skills/.env
     Repo:         ~/.gravitas-skills/ (git)

     Secrets        Status
     ─────────      ──────
     METRICOOL_TOKEN   ✅
     APIFY_API_KEY     ✅

     Endpoints      Status
     ─────────      ──────
     GET /secrets      ✅ 200
     GET /pages        ✅ 200 (Meta account discovery ready)
```

---

## Phase 6: Wrap Up

### 6a: Open the folder

```bash
# On Windows (try multiple approaches — one will work):
cmd //c "start %USERPROFILE%\.gravitas-skills" 2>/dev/null || \
  explorer "%USERPROFILE%\.gravitas-skills" 2>/dev/null || true

# On macOS:
open ~/.gravitas-skills 2>/dev/null || true

# On Linux:
xdg-open ~/.gravitas-skills 2>/dev/null || true
```

### 6b: Explain what was built

Tell the user:

> Here's what was set up:
>
> - **`~/.gravitas-skills/`** — 7 agent skills + the gateway credential layer
> - **`~/.gravitas-skills/.env`** — your gateway key (never committed, never pushed)
> - **`gateway.shazan.me`** — the Cloudflare Worker holding all shared API keys
>
> Any skill that needs credentials will now:
> 1. `source ~/.gravitas-skills/.env` to load the gateway key
> 2. Fetch its specific secret from the gateway
> 3. Use the credential, then let it evaporate from context
>
> You never paste a Metricool or Apify key again.

### 6c: Ask what's next (with real skill names)

List the skills actually found in the repo using `ls ~/.gravitas-skills/*/SKILL.md`.
Present them as concrete options:

```
What do you want to do next?

🔑 Gateway-powered:
  1. gravitas-data-manager — FB/IG/TikTok social data & competitor reports
  2. metricool — pull analytics, manage posts, check competitors
  3. metricool-engagement-rate-xlsx — per-post ER proof workbooks
  4. metricool-engagement-rate-xlsx-v2 — improved ER workbooks
  5. performance-social-report-slides — quarterly Excel → PPTX

🧩 Standalone:
  6. client-friendly-report-writer — metrics → client-ready analysis
  7. datasheet-to-gsheet-mapper — CSV → Google Sheets columns
  8. youtube-publish-date-bulk — batch YouTube publish dates

Setup:
  9. Configure Instaloader (personal IG session for scraping)
  0. Done — gateway is ready when a skill needs it
```

---

## Reference: Secret → Skill Mapping

The agent uses this table to know which secret to fetch when a skill loads:

| Skill | Secret to Fetch | Endpoint |
|-------|-----------------|----------|
| `metricool` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `metricool-engagement-rate-xlsx` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `metricool-engagement-rate-xlsx-v2` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `performance-social-report-slides` | `METRICOOL_TOKEN` | `GET /secret/METRICOOL_TOKEN` |
| `gravitas-data-manager` | `APIFY_API_KEY` + `METRICOOL_TOKEN`; Meta account discovery | `GET /secret/APIFY_API_KEY` + `GET /secret/METRICOOL_TOKEN` + `GET /pages` |
| `pitch-competitor-research` | `APIFY_API_KEY` + `METRICOOL_TOKEN` | `GET /secret/APIFY_API_KEY` + `GET /secret/METRICOOL_TOKEN` |
| `fb-ig-engagement-xlsx` | Official Meta export until a scoped read-only proxy exists | No usable multi-page token endpoint |

> **Note:** `intel-ig-manager` and the old `gravitas-data-manager` have been merged
> into a single `gravitas-data-manager` skill that owns all FB/IG/TikTok workflows.
> The live gateway exposes `METRICOOL_TOKEN`, `APIFY_API_KEY`, and server-side Meta
> endpoints. It does not expose a generic user token or auto-select one of many pages.

---

## Reference: Full Gateway API

### Static Secrets

| Endpoint | Returns |
|----------|---------|
| `GET /secrets` | `{"secrets": ["METRICOOL_TOKEN", "APIFY_API_KEY"]}` — available secret names only, verified live 2026-08-12 |
| `GET /secret/:name` | `{"name": "...", "value": "..."}` — full secret value |

### Meta Graph API (Facebook / Instagram)

| Endpoint | Returns |
|----------|---------|
| `GET /token` | Stateful legacy single-page endpoint. It may return a selected/cached `page_access_token` or `409 multiple_pages_found`; it never returns a generic `access_token`. Do not use it as a multi-page credential source or health check. |
| `GET /pages` | `{"pages": [...]}` with page IDs, names, and linked Instagram business accounts. Use this for health checks and account discovery; page access tokens are intentionally omitted. |
| `GET /thumbnail?platform=fb\|ig&post_id=<id>` | `{"thumbnail_url": "..."}` |
| `GET /comments?platform=fb\|ig&post_id=<id>` | Comments array for a post |

All endpoints require `x-api-key: $GRAVITAS_GATEWAY_KEY` header.

**Gotcha: Cloudflare blocks Python's default `urllib`/`requests` User-Agent**
with error `code: 1010` ("banned based on your browser's signature") on every
gateway endpoint above, curl is unaffected. If a skill script calls the
gateway with anything other than curl, set a normal-looking `User-Agent`
explicitly:
```python
req = urllib.request.Request(url, headers={"x-api-key": KEY, "User-Agent": "curl/8.4.0"})
```

### Meta Marketing API (Ads/Campaigns)

Do not use `GET /token` for Ads Manager / Marketing API work. It never returns
a user ads token and may return `409 multiple_pages_found`. Ads access needs a
separate scoped broker/key before this skill should document it again.

### Per-User Credentials (Local .env)

Some credentials are per-person and stored in `~/.gravitas-skills/.env`:

- **`INSTALOADER_SESSION`** — path to Instagram session file for Instaloader scraping.
  Set up once: `pip install instaloader && instaloader --login`.
  The primary skill that uses Instaloader is `gravitas-data-manager`.
  Fallback: Apify (uses shared `APIFY_API_KEY` from gateway).

---

## Reference: Adding a New Secret

**Shared secret (add to gateway):**
1. Add env var to the gateway worker (`wrangler secret put`)
2. Update this SKILL.md secret mapping tables
3. Push to GitHub → next `git pull` picks it up

**Per-user credential:**
1. Add variable to `.env.example` with setup instructions
2. Update this SKILL.md
3. Push to GitHub → team members add to local `.env` on next pull
