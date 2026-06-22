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

### 5c: Test Meta Graph API token endpoint

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/token" | grep -q 'page_access_token' && echo "OK" || echo "FAIL"
```

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
     GET /token         ✅ 200 (Meta Graph API ready)
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
  1. metricool — pull analytics, manage posts, check competitors
  2. metricool-engagement-rate-xlsx — per-post ER proof workbooks
  3. metricool-engagement-rate-xlsx-v2 — improved ER workbooks
  4. performance-social-report-slides — quarterly Excel → PPTX

🧩 Standalone:
  5. client-friendly-report-writer — metrics → client-ready analysis
  6. datasheet-to-gsheet-mapper — CSV → Google Sheets columns
  7. youtube-publish-date-bulk — batch YouTube publish dates

Setup:
  8. Configure Instaloader (personal IG session for scraping)
  9. Done — gateway is ready when a skill needs it
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
| `intel-ig-manager` | `APIFY_API_KEY` + Meta token | `GET /secret/APIFY_API_KEY` + `GET /token` |
| `gravitas-data-manager` | `APIFY_API_KEY` | `GET /secret/APIFY_API_KEY` |
| `fb-ig-engagement-xlsx` | Meta token | `GET /token` |

---

## Reference: Full Gateway API

### Static Secrets

| Endpoint | Returns |
|----------|---------|
| `GET /secrets` | `{"secrets": ["METRICOOL_TOKEN", "APIFY_API_KEY"]}` — available secret names only |
| `GET /secret/:name` | `{"name": "...", "value": "..."}` — full secret value |

### Meta Graph API (Facebook / Instagram)

| Endpoint | Returns |
|----------|---------|
| `GET /token` | `{"page_access_token": "...", "page_id": "...", "expires_at": ...}` |
| `GET /pages` | List of Facebook pages with linked Instagram business accounts |
| `GET /thumbnail?platform=fb\|ig&post_id=<id>` | `{"thumbnail_url": "..."}` |
| `GET /comments?platform=fb\|ig&post_id=<id>` | Comments array for a post |

All endpoints require `x-api-key: $GRAVITAS_GATEWAY_KEY` header.

### Per-User Credentials (Local .env)

Some credentials are per-person and stored in `~/.gravitas-skills/.env`:

- **`INSTALOADER_SESSION`** — path to Instagram session file for Instaloader scraping.
  Set up once: `pip install instaloader && instaloader --login`.
  Skills that use it: intel-ig-manager, gravitas-data-manager.
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
