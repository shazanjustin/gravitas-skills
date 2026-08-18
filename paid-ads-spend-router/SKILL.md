---
name: paid-ads-spend-router
description: Route Gravitas paid media questions correctly. Use when the user asks about ad spend, paid ads, media spend, campaign spend, Meta Ads/Facebook Ads/Instagram Ads, actual spend vs planned budget, SP/SKP MY/SG ad accounts, which ads are running, or paid-media performance breakdowns. Forces a clarification when spend could mean either live platform spend or budget/media-plan sheets. Reports objective-appropriate metrics rather than generic delivery figures. Planned budgets can use Drive/Sheets; general Meta reporting needs the scoped ads route.
compatibility: |
  Requires gravitas-gateway and curl. gateway.shazan.me `GET /token` returns
  page access tokens only, never a Marketing API user token, and may return
  `409 multiple_pages_found`. Objective-to-metric mapping and the Graph API
  field recipes live in `reference/objective-metrics.md`.
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
  "FB/IG Ads Manager", "campaign performance", "delivered spend", "which ads
  are running" → use the platform API path.
- Planned/sheet wording: "budget", "media plan", "allocation", "booking",
  "tracker", "what did we plan" → use Drive/Sheets/Composio.

## Phase 2: Actual Meta spend path

### 2a. Know what access actually exists

`GET /token` on the shared gateway is a legacy **organic page-token** endpoint.
It never returns a Marketing API user token. Do **not** point it at
`/me/adaccounts`, and do **not** quietly fall back to Drive/Sheets as if a
planned budget were actual spend.

One live ads read exists today:

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/skp-eastwest-monitor?save=0"
```

Its limits matter before you quote it as "our ads data":

- **One hardcoded campaign.** Not an account sweep, not "all running ads".
- **Fixed fields** — impressions, reach, spend, CPM, broken down by placement.
  No objective-appropriate metrics (see 2b), so it cannot answer "how is this
  performing" for anything except an awareness buy.
- **Lifetime only** (`date_preset: maximum`), so it blends every optimization
  change the campaign has been through.
- **A plain GET writes a checkpoint**, moving the baseline that the dashboard's
  movement column compares against. Always pass `?save=0` unless the user
  explicitly wants a new baseline set.
- Human-facing dashboard: `https://gateway.shazan.me/skp-eastwest-dashboard`
  (prompts for the gateway API key in the browser; the key is not embedded).

Anything broader — account discovery, other campaigns, ad-level listings — needs
the **scoped ads route** on the gateway. Until it exists, say plainly that
general Meta reporting is not wired up yet rather than improvising around it.

### 2b. Resolve the objective before choosing metrics

This is the step that separates a useful answer from a useless one. Meta's
"Results" column is the optimization goal's outcome, so the correct metric set
depends entirely on what the campaign was bought to do. Spend, impressions and
CPM describe *delivery*; on a conversions or leads buy they are not performance.

Read `reference/objective-metrics.md` and follow it. It carries:

- the objective → metric-set table, including the ad-set `optimization_goal`
  split that `OUTCOME_ENGAGEMENT` needs,
- the exact `fields` and `actions[]` action types per objective,
- derived metrics worth computing (hook rate, hold rate, LPV ratio),
- how to list what is genuinely running versus merely flagged ACTIVE,
- the traps that have each produced a wrong number in a real report.

Never report a fixed metric set across mixed objectives. When a request spans
campaigns with different objectives, group the answer by objective and lead each
group with its own primary metric.

### 2c. Discover accounts before querying them

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

### 2d. Query insights

Query through `/act_ACCOUNT_ID/insights`. Use `time_range` for exact dates and
`time_increment=monthly` or `1` only when the user asks for a monthly or daily
breakdown. Build `fields` from the objective's row in
`reference/objective-metrics.md` — the delivery base below is the floor, not the
whole request.

`curl -g` is **required** here, not optional. `time_range={"since":...,"until":...}`
contains braces with a comma, which curl treats as a URL glob: without `-g` it
silently fires *two* requests with an empty `time_range`, Meta rejects both with
`(#100) param time_range must be non-empty`, and the two error documents arrive
concatenated so the JSON parse fails with "Extra data" rather than anything that
points at the real cause.

```bash
curl -s -g "https://graph.facebook.com/v25.0/act_ACCOUNT_ID/insights?fields=account_id,account_name,account_currency,spend,impressions,reach,frequency,objective&time_range={\"since\":\"YYYY-MM-DD\",\"until\":\"YYYY-MM-DD\"}&use_unified_attribution_setting=true&time_increment=monthly&access_token=$TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); cols=["account_name","account_currency","date_start","date_stop","objective","spend","impressions","reach","frequency"]; [print("\t".join(str(r.get(k,"")) for k in cols)) for r in d.get("data", [])]'
```

Add `account_currency` to `fields` whenever more than one account is being
reported, and print the figure with its currency. Never add spend across
accounts that do not share one.

For campaign/adset/ad breakdowns, query the same insights edge with
`level=campaign`, `level=adset` or `level=ad` and include `campaign_name` /
`adset_name` / `ad_name`. Follow pagination when a response has more pages, and
left-join the rows onto the entity list — an active ad with no delivery returns
no insights row at all.

Meta clamps `until` to today. A range ending in the future comes back with
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
- `actions`, `action_values`, `cost_per_action_type` and `purchase_roas` come
  back as arrays of `{action_type, value}`. Flatten to the action types the
  objective calls for; never dump the array.
- State the attribution window whenever conversions are reported. Prefer
  `use_unified_attribution_setting=true` so the figures reconcile with what the
  client sees in Ads Manager.
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
