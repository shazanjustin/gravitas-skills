---
name: paid-ads-spend-router
description: Route Gravitas paid media questions correctly. Use when the user asks about ad spend, paid ads, media spend, campaign spend, Meta Ads/Facebook Ads/Instagram Ads, actual spend vs planned budget, SP/SKP MY/SG ad accounts, or paid-media performance breakdowns. Forces a clarification when spend could mean either live platform spend or budget/media-plan sheets, then uses Meta Marketing API via gravitas-gateway for actual Meta spend and Drive/Sheets only for planned budgets or trackers.
compatibility: |
  Requires gravitas-gateway and curl. Meta access token comes from
  gateway.shazan.me `GET /token`; never print raw Graph API responses because
  paging URLs can contain access tokens.
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

For actual Facebook/Instagram/Meta paid spend, load `gravitas-gateway` first and
use the Meta Marketing API token from the gateway. Do **not** use Drive/Sheets as
the first source for actual spend.

1. Source gateway env:

```bash
source ~/.gravitas-skills/.env
```

2. Fetch the token safely. Do not print it.

```bash
TOKEN=$(curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/token" | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
```

3. Discover accessible ad accounts when the user gives shorthand like SP/SKP or
MY/SG. Known current accounts include `SP MY`, `SKP MY`, `SP SG`, and `SKP SG`,
but still discover instead of hardcoding when possible.

```bash
curl -s "https://graph.facebook.com/v25.0/me/adaccounts?fields=id,account_id,name,currency,account_status&limit=100&access_token=$TOKEN" \
  | python -c 'import json,sys; d=json.load(sys.stdin); cols=["id","name","currency","account_status"]; [print("\t".join(str(a.get(k,"")) for k in cols)) for a in d.get("data", [])]'
```

4. Query spend through `/act_ACCOUNT_ID/insights`. Use `time_range` for exact
dates and `time_increment=monthly` or `1` only when the user asks for a monthly
or daily breakdown.

```bash
curl -s "https://graph.facebook.com/v25.0/act_ACCOUNT_ID/insights?fields=account_id,account_name,spend,impressions,reach,clicks,cpc,cpm,ctr&time_range={\"since\":\"YYYY-MM-DD\",\"until\":\"YYYY-MM-DD\"}&time_increment=monthly&access_token=$TOKEN" \
  | python -c 'import json,sys; d=json.load(sys.stdin); cols=["account_name","date_start","date_stop","spend","impressions","reach","clicks","cpc","cpm","ctr"]; [print("\t".join(str(r.get(k,"")) for k in cols)) for r in d.get("data", [])]'
```

5. For campaign/adset/campaign-name breakdowns, query the same insights edge with
`level=campaign` or `level=adset` and include `campaign_name` / `adset_name`.
Follow pagination when a response has more pages.

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
