---
name: gravitas-gateway
description: >
  Central credential layer for every Gravitas skill. Resolves the Gravitas
  Gateway key and fetches API credentials for Metricool, Apify, and the
  server-side Meta endpoints from gateway.shazan.me. Load this before any other
  Gravitas skill that needs an API key, and whenever a Gravitas skill fails with
  a 401, a 409, or a missing-credential error.
compatibility: |
  Requires curl. The gateway key comes from the gravitas plugin's own config,
  collected when the plugin is installed, or from a GRAVITAS_GATEWAY_KEY
  environment variable in environments that cannot prompt (cloud sessions, CI).
---

# Gravitas Gateway

Every shared Gravitas credential lives behind one Cloudflare Worker at
`gateway.shazan.me`. Nobody on the team pastes a Metricool or Apify token by
hand: a skill asks the gateway for the secret it needs, uses it, and lets it
fall out of context.

There is no repo to clone and no `.env` file to write. The key was collected
when the `gravitas` plugin was installed.

---

## Step 1: Resolve the key

Use the first source that yields a non-empty value.

| Order | Source | When it applies |
|-------|--------|-----------------|
| 1 | `${user_config.gateway_key}` | Normal local install. Prompted at install time, stored in the OS keychain. |
| 2 | `$GRAVITAS_GATEWAY_KEY` | Cloud sessions, CI, and anywhere `/plugin` cannot prompt. |

The gateway URL resolves the same way: `${user_config.gateway_url}`, else
`$GRAVITAS_GATEWAY_URL`, else `https://gateway.shazan.me`.

Never echo the key, never write it to a file, and never bake it into a script
you leave on disk. Pass it inline as a header on the call that needs it.

For a shell session that will make several calls, export it once:

```bash
export GRAVITAS_GATEWAY_KEY=<resolved key>
export GRAVITAS_GATEWAY_URL="${GRAVITAS_GATEWAY_URL:-https://gateway.shazan.me}"
```

If neither source has a value, stop and tell the user:

> No Gravitas Gateway key is configured. Locally, run `/plugin` -> **Installed**
> -> **gravitas** -> configure, and paste the key from Shazan or your team lead.
> In a cloud session, add `GRAVITAS_GATEWAY_KEY` to the environment's variables
> at claude.ai/code.

---

## Step 2: Verify it

One call proves the key, the network path, and the Worker at once:

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" "$GRAVITAS_GATEWAY_URL/secrets"
```

| Response | Meaning |
|----------|---------|
| `{"secrets":[...]}` | Key is good. Proceed. |
| `401` or empty body | Key rejected. Ask for a new one; do not retry the same key. |
| No response, connection error | Cannot reach the gateway. See **Troubleshooting**. |

Report the result in one line and get on with the actual task. Do not sweep
every endpoint unless the user asked you to check the setup itself.

**Do not use `curl -w`** to read status codes here; it breaks under Git Bash on
Windows. Use `curl -sv ... 2>&1 | grep "< HTTP/"`, or just test the response body.

---

## Step 3: Fetch what the skill needs

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/METRICOOL_TOKEN"
# {"name":"METRICOOL_TOKEN","value":"..."}
```

For Meta work, start at `GET /pages`, never at bare `GET /token` -- see the API
reference below for why.

---

## Full setup check

Run this only when the user is setting the plugin up, debugging access, or
asking "does my gateway work". It is not a preamble to normal work.

**a. List secrets**

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" "$GRAVITAS_GATEWAY_URL/secrets"
```

**b. Confirm each named secret resolves**

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/secret/$SECRET_NAME" | grep -q '"value"' && echo OK || echo FAIL
```

**c. Test Meta account discovery**

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

`META_TOKEN_NEEDS_REFRESH` means the gateway key is fine but the underlying
Facebook source token must be renewed in the Worker secret/KV before official
FB/IG endpoints work.

**d. Summarize**

```
     Gateway URL:  https://gateway.shazan.me
     Key source:   plugin config  (or: GRAVITAS_GATEWAY_KEY env var)
     Key status:   Valid (tested live)

     Secrets            Status
     ---------          ------
     METRICOOL_TOKEN       OK
     APIFY_API_KEY         OK

     Endpoints          Status
     ---------          ------
     GET /secrets          200
     GET /pages            200 (Meta account discovery ready)
```

Then list the skills this plugin actually ships and offer them as next steps.

---

## Troubleshooting

**Connection refused or a timeout in a cloud session.** Cloud environments
default to **Trusted** network access, an allowlist covering package registries
and GitHub but not `gateway.shazan.me`. Set the environment's network access to
**Custom** at claude.ai/code and allowlist `gateway.shazan.me`, plus whichever
of `api.metricool.com`, `api.apify.com`, `graph.facebook.com` and
`openrouter.ai` the task needs.

**HTTP 403, Cloudflare error 1010, from a Python script.** See the User-Agent
gotcha in the API reference below. `curl` is unaffected.

**`curl: (43) A libcurl function was given a bad argument`.** A key with a
trailing carriage return, from a CRLF-line-ending file. The key now comes from
plugin config rather than a sourced `.env`, so if you still hit this, something
is reading an old `~/.gravitas-skills/.env`. Delete that file.

**`409 multiple_pages_found` from `/token`.** Not a fault. Name the page with
`?page_id=`. See the API reference.

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
| `fb-ig-engagement-xlsx` | Per-page Meta reads | `GET /pages` → `GET /ig/media?ig_account_id=<id>` or `GET /debug?page_id=<id>` |

> **Note:** `intel-ig-manager` and the old `gravitas-data-manager` have been merged
> into a single `gravitas-data-manager` skill that owns all FB/IG/TikTok workflows.
> The live gateway exposes `METRICOOL_TOKEN`, `APIFY_API_KEY`, and server-side Meta
> endpoints. It still does not expose a generic user token, and it will not guess a
> page for you — but every page is reachable by naming it, so "multi-page" is no
> longer a blocker for content reads. Ads remain the exception (see below).

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
| `GET /pages` | `{"pages": [...]}` with page IDs, names, and linked Instagram business accounts. **Start here** — it is both the health check and the source of the `page_id` / `ig_account_id` every other endpoint wants. Page access tokens are intentionally omitted. |
| `GET /token?page_id=<id>` | `{"page_access_token", "page_id", "expires_at"}` for that page. `page_id` comes from `/pages`. An unmanaged id returns `404 page_not_found` **with the managed list**, so a wrong guess tells you the right answer. |
| `GET /token` (no `page_id`) | `409 multiple_pages_found` listing all pages. This is normal, not a fault: the account manages 11 pages and no default is bound. Pick one and retry with `?page_id=`. Never use bare `/token` as a health check. |
| `GET /ig/media?ig_account_id=<id>` | Instagram post listing — `{"media": [...], "paging", "page_id"}` with caption, `media_type`, `media_url`, `thumbnail_url`, `permalink`, `timestamp`, `like_count`, `comments_count`. Optional `&limit=` (default 25, capped 100) and `&page_id=` to skip the owning-page lookup. |
| `GET /debug?page_id=<id>` | **Facebook** post listing (id, message, `full_picture`, `created_time`, newest 5). Unfortunate name — it is a normal listing endpoint, and it is the Facebook counterpart to `/ig/media`. |
| `GET /thumbnail?platform=fb\|ig&post_id=<id>` | `{"thumbnail_url": "..."}` |
| `GET /comments?platform=fb\|ig&post_id=<id>` | Comments array for a post |

**`/thumbnail` and `/comments` need to know which page owns the post.** For
Facebook they infer it from the `{page_id}_{object_id}` post-id prefix, so no
extra parameter is needed. **Instagram media IDs carry no such prefix**, so pass
`&ig_account_id=<id>` (or `&page_id=<id>`) alongside `post_id` — otherwise the
page cannot be resolved and the call returns `409 page_unresolved`. That 409 is
deliberate: these routes used to answer `200 {"thumbnail_url": null}` in exactly
this situation, which was indistinguishable from a post that genuinely had no
thumbnail, and reports were silently built on the empty result.

Two ways to read Instagram posts, both fine:

- **Proxied (preferred)** — `GET /ig/media`. No token ever leaves the Worker.
- **Direct** — mint a page token with `/token?page_id=`, then call
  `graph.facebook.com/v25.0/{ig_account_id}/media` yourself. Use this when you
  need fields or edges the proxy does not expose (e.g. `/{media_id}/children`
  for individual carousel slides — `/ig/media` returns a `CAROUSEL_ALBUM` as a
  single entry with its cover image).

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

Do not use `GET /token` for Ads Manager / Marketing API work, with or without
`?page_id=`. It returns a **page** access token; the Marketing API needs a
**user** token with `ads_read`/`ads_management`, and the gateway deliberately
never dispenses one — that token carries spend authority over every client ad
account, so it stays inside the Worker. Ads access needs a separate scoped
broker/key before this skill should document it again.

This is the one thing the multi-page fix did **not** unblock. If a task needs
Meta *spend* or campaign data, it is still blocked; use Metricool as the proxy.
Content reads (posts, captions, thumbnails, comments, engagement counts) are
fully available — do not confuse the two and assume everything Meta is down.

### Per-User Credentials

Some credentials are personal and never go in the gateway. Set them as
environment variables:

- **`INSTALOADER_SESSION`** — path to your own Instagram session file for
  Instaloader scraping. Set up once with `pip install instaloader && instaloader
  --login`, then export
  `INSTALOADER_SESSION=~/.config/instaloader/session-<your_username>`.
  The primary skill that uses Instaloader is `gravitas-data-manager`.
  Fallback: Apify (uses shared `APIFY_API_KEY` from gateway).

---

## Reference: Adding a New Secret

**Shared secret (add to gateway):**
1. Add env var to the gateway worker (`wrangler secret put`)
2. Update this SKILL.md secret mapping tables
3. Bump `version` in `plugins/gravitas/.claude-plugin/plugin.json` and push →
   installed copies pick it up on the next plugin auto-update

**Per-user credential:**
1. Document the environment variable in this SKILL.md and the plugin README
2. Bump the plugin version and push
