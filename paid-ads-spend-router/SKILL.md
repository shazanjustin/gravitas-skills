---
name: paid-ads-spend-router
description: Route Gravitas paid media questions correctly. Use when the user asks about ad spend, paid ads, media spend, campaign spend, Meta Ads/Facebook Ads/Instagram Ads, actual spend vs planned budget, SP/SKP MY/SG ad accounts, or paid-media performance breakdowns. Forces a clarification when spend could mean either live platform spend or budget/media-plan sheets. Planned budgets can use Drive/Sheets; actual Meta spend is blocked until a separate scoped ads gateway exists.
compatibility: |
  Requires gravitas-gateway and curl. As of 2026-08-12, gateway.shazan.me
  `GET /token` returns a page token, not a Marketing API user token.
argument-hint: "[brand/account] [date range] [actual spend or planned budget]"
---

# Paid Ads Spend Router

Route paid-media questions before touching tools.

## Phase 1: Clarify the source of truth

If the user asks for "ad spend", "media spend", "how much are we spending", or
similar wording without saying **actual/live/platform spend** or **planned/budget
/media plan**, ask one short clarification and stop:

Do you mean actual spend from the ad platforms, or planned/budget spend from
the media-plan sheets?

Do not start Drive/Sheets or Meta calls until that is answered.

Skip the clarification only when the wording clearly names the source:

- Actual/platform wording: "actual spend", "live spend", "Meta spend",
  "FB/IG Ads Manager", "campaign performance", "delivered spend" → use the
  platform API path.
- Planned/sheet wording: "budget", "media plan", "allocation", "booking",
  "tracker", "what did we plan" → use Drive/Sheets/Composio.

## Phase 2: Actual Meta spend path

For actual Facebook/Instagram/Meta paid spend, stop and say the live gateway no
longer exposes a Marketing API user token. `GET /token` returns
`page_access_token`, `page_id`, and `expires_at` for organic FB/IG access only.
Do **not** try to use that token against `/me/adaccounts`, and do **not** switch
to Drive/Sheets as if it were actual platform spend.

Needed fix before this path can run again: create a separate scoped ads gateway
Worker/key for Marketing API access, then update this skill with that endpoint.

Historical notes to preserve when the scoped ads gateway exists:

Discover accessible ad accounts when the user gives shorthand like SP/SKP or
MY/SG. Known current accounts included `SP MY`, `SKP MY`, `SP SG`, and `SKP SG`,
but still discover instead of hardcoding when possible.

Two traps confirmed against the live token on 2026-08-12, both of which the
discovery step surfaces and a hardcoded list would hide:

- **"SP MY" matches more than one account.** There is a separate
  `SP MY - Lazada SEA CPAS` account alongside plain `SP MY`. A substring match
  on "SP MY" hits both. Ask which one is meant, per the shorthand rule in
  Safety rules — CPAS spend is a different commercial thing from BAU spend.
- **Markets do not share a currency.** The MY accounts bill in **MYR** and the
  SG accounts in **SGD**. `spend` comes back as a bare number with no currency
  attached, so a cross-market request ("SP and SKP, MY and SG") must never be
  summed into one figure.

```bash
curl -s "https://graph.facebook.com/v25.0/me/adaccounts?fields=id,account_id,name,currency,account_status&limit=100&access_token=$TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); cols=["id","name","currency","account_status"]; [print("\t".join(str(a.get(k,"")) for k in cols)) for a in d.get("data", [])]'
```

4. Query spend through `/act_ACCOUNT_ID/insights`. Use `time_range` for exact
dates and `time_increment=monthly` or `1` only when the user asks for a monthly
or daily breakdown.

`curl -g` is **required** here, not optional. `time_range={"since":...,"until":...}`
contains braces with a comma, which curl treats as a URL glob: without `-g` it
silently fires *two* requests with an empty `time_range`, Meta rejects both with
`(#100) param time_range must be non-empty`, and the two error documents arrive
concatenated so the JSON parse fails with "Extra data" rather than anything that
points at the real cause.

```bash
curl -s -g "https://graph.facebook.com/v25.0/act_ACCOUNT_ID/insights?fields=account_id,account_name,account_currency,spend,impressions,reach,clicks,cpc,cpm,ctr&time_range={\"since\":\"YYYY-MM-DD\",\"until\":\"YYYY-MM-DD\"}&time_increment=monthly&access_token=$TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); cols=["account_name","account_currency","date_start","date_stop","spend","impressions","reach","clicks","cpc","cpm","ctr"]; [print("\t".join(str(r.get(k,"")) for k in cols)) for r in d.get("data", [])]'
```

Add `account_currency` to `fields` whenever more than one account is being
reported, and print the figure with its currency. Never add spend across
accounts that do not share one.

5. For campaign/adset/campaign-name breakdowns, query the same insights edge with
`level=campaign` or `level=adset` and include `campaign_name` / `adset_name`.
Follow pagination when a response has more pages.

6. Meta clamps `until` to today. A range ending in the future comes back with
`date_stop` set to today, not the date asked for — report the range actually
covered rather than the one requested, or a partial month reads as a full one.

## Phase 3: Planned budget / sheet path

Use Composio Drive/Sheets only after the user confirms they want planned budget,
media-plan, allocation, tracker, or spreadsheet data.

State the source explicitly in the answer:

- "Actual platform spend from Meta Ads API"
- "Planned budget from media-plan sheet"

Never blend planned and actual spend without labeling both.

## Safety rules

- Never print raw Meta Graph/Marketing API JSON. Parse and print allowlisted
  fields only; raw `paging.next` URLs can contain `access_token`.
- If a brand/market shorthand does not map cleanly to exactly one ad account,
  ask the user to choose from the discovered account names.
- If Meta returns no account for the requested brand, say access is missing; do
  not switch to Drive/Sheets and present a planned budget as actual spend.
- Keep Discord output as numbered bullets, not pipe tables.
- Use `python3`, never bare `python`. The ev-discord image installs python3 only,
  so `python` fails with "command not found" — and because these snippets assign
  through a pipeline, `TOKEN` silently becomes the error text instead of a token,
  turning a missing interpreter into a confusing auth failure several calls later.
- Pass `-g` to every curl whose URL contains `{...}`. See the note above the
  insights call: without it the request is glob-expanded and fails in a way whose
  error message points nowhere near the actual problem.
