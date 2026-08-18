---
name: paid-ads-spend-router
description: Route Gravitas paid media questions correctly. Use when the user asks about ad spend, paid ads, media spend, campaign spend, Meta Ads/Facebook Ads/Instagram Ads, actual spend vs planned budget, SP/SKP MY/SG ad accounts, which ads are running, or paid-media performance breakdowns. Forces a clarification when spend could mean either live platform spend or budget/media-plan sheets. Reports objective-appropriate metrics rather than generic delivery figures. Actual Meta spend and performance run through the gateway ads routes; planned budgets use Drive/Sheets. Replies are shaped for Discord.
compatibility: |
  Requires gravitas-gateway and curl. Live ads data comes from
  gateway.shazan.me `/ads/accounts` and `/ads/running`; `GET /token` returns
  page access tokens only and is not for Marketing API work. Objective-to-metric
  mapping and the Graph API field recipes live in
  `reference/objective-metrics.md`.
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
`/me/adaccounts` — go through the gateway's scoped ads routes instead, which
keep the token server-side and return allowlisted fields only.

```bash
# Every ad account, with its billing currency.
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/ads/accounts"

# What is actually delivering, with objective-appropriate metrics.
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/ads/running?days=30&delivering=1"
```

Parameters worth knowing:

| Param | Effect |
|---|---|
| `account=` | Name substring or account id. Ambiguous shorthand returns `409` with the candidates — pick one, never guess. |
| `days=` / `since=`+`until=` | Reporting window. Defaults to 30 days. |
| `delivering=1` | Return only ads that actually spent. `running_ads` still reports the true ACTIVE total. |
| `diagnose=1` | Adds `observed_actions`: the action types and counts Meta really returned. |
| `attribution=` | e.g. `7d_click,1d_view`. Overrides the unified account setting. |

Each ad comes back with `schedule` (start, end, days left, budget) and `links`
(Ads Manager deep links to the ad, ad set and campaign).

**Three things the response will tell you that the numbers alone will not:**

- **`running_ads` vastly exceeds the delivering count.** Measured 18 Aug 2026:
  5,671 ads flagged ACTIVE across the 11 accounts, 67 delivering. The remainder
  are old campaigns nobody paused, some dating to 2023. Never answer "how many
  ads are running" with the ACTIVE count.
- **`delivering: true` is not "live now".** It means the ad spent inside the
  window. Of those 67, only 8 had a flight that had not already ended. When
  someone asks what is running, filter on `schedule.days_left >= 0`.
- **`budget_remaining` is unreliable** — it read 0 for all 67 ads including
  actively-spending ones, because these buys use campaign-level budgets. Quote
  `lifetime_budget`, not remaining.

If a conversion count is zero, do not report it as a result until you have run
`diagnose=1` with at least one explicit `attribution=` window. See Phase 2e.

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

### 2c. Reference: the Graph calls behind the routes

The two sections below document what `/ads/accounts` and `/ads/running` do on
your behalf. **You cannot run them** — they need the Marketing API token, which
the gateway never dispenses. Read them to understand a response or to extend
the routes, not as a call to make.

#### Account discovery

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

#### Insights

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

### 2e. Before reporting a zero

A zero-conversion campaign is the highest-stakes number in this skill: it either
means the creative failed, or that nothing is being measured, and those lead to
opposite actions. Never report one without ruling out the second.

```bash
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/ads/running?account=<acct>&days=60&diagnose=1&attribution=28d_click,1d_view"
```

Read `observed_actions`, then say which of these it is:

1. **No conversion action of any type, across windows** → genuinely zero.
2. **A conversion type is present but unmapped** → a reporting gap, not a
   campaign failure. Say so and name the action type.
3. **Clicks with almost no landing page views** → tracking is broken. On a real
   case, 391 link clicks produced 1 landing page view; the pixel fired
   `view_content` twice, so it existed but the page was not reporting. That is
   a pixel problem, and worse than a reporting one: an ad set optimizing for
   offsite conversions has no signal to learn from and keeps spending blind.

Also compare `link_click` against `outbound_clicks` before quoting traffic.
On that same campaign they were 391 and 82 — nearly 5x apart, because
`link_click` counts any link click while `outbound_clicks` counts people who
actually left Meta.

## Phase 3: Planned budget / sheet path

Use Composio Drive/Sheets only after the user confirms they want planned budget,
media-plan, allocation, tracker, or spreadsheet data.

State the source explicitly in the answer:

- "Actual platform spend from Meta Ads API"
- "Planned budget from media-plan sheet"

Never blend planned and actual spend without labeling both.

## Phase 4: Answering in Discord

The API returns far more than a chat message should carry. A 30-day sweep is
about 2.5MB and 67 ads across 30-odd campaigns; pasting a fraction of that is
the most common way this skill produces a bad answer. Discord chunks cleanly at
2000 characters, so nothing breaks — it just becomes a dozen messages nobody
reads.

**Answer at campaign level, not ad level.** Ads within a campaign nearly always
share a flight and an objective, so the campaign is the unit someone acts on.
Drop to individual ads only when asked, or when one ad is the anomaly.

**Shape of a good reply:**

1. One sentence with the actual answer — how many are live, and total spend per
   currency.
2. A numbered list of live campaigns, soonest-ending first. Per line: name,
   what ends when, spend, and the objective's primary metric.
3. Anything alarming, called out separately.
4. An offer to drill in, rather than pre-emptively dumping the detail.

**Formatting rules specific to Discord:**

- **Never pipe tables.** Discord does not render them; they arrive as noise.
  Numbered bullets carry the same information.
- **Wrap every URL in angle brackets** — `<https://adsmanager...>`. Bare links
  each generate a preview embed, so five ads turn one reply into a wall of
  cards. The angle brackets suppress that and keep the link clickable.
- **At most ~5 links per reply.** Link the campaign, not each of its ads.
- Round money to 2 decimals and cost-per-result to 3–4. Raw API precision
  (`0.164666`) reads like a machine dumped its buffer.
- **Always name the currency**, and never total MYR and SGD together.
- Keep the whole reply under about 1500 characters. If it does not fit, the
  answer is too granular, not too long.

**Worked example** — "what ads are running right now?":

> 8 ads are live right now across 3 campaigns — 3,545.13 MYR and 270.83 SGD
> spent in the last 30 days. (5,671 are flagged ACTIVE, but almost all are old
> campaigns nobody paused.)
>
> 1. **SKP MY — FC Instant Infusion** · ends today. 569.65 MYR, 4 ads.
>    15,214 ThruPlays at 0.018 MYR and 1,783 landing page views at 0.166 MYR.
>    <https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=...>
> 2. **SP MY — TIMETIC Home Care (Purchases)** · ends 23 Aug. 827.12 MYR,
>    2 ads, **0 purchases**. Worth a look — 391 clicks produced 1 landing page
>    view, so the pixel is not reporting and ~1,290 MYR is still unspent.
>    <https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=...>
> 3. **SP MY — TIMETIC Holistic Care** · ends 31 Aug. 58.10 MYR, 2 ads,
>    3,574 ThruPlays at 0.016 MYR. Started yesterday, best efficiency of the three.
>
> Want the ad-level breakdown for any of these, or the 30 campaigns that
> already finished?

Note what that reply does: leads with the number asked for, corrects the
misleading ACTIVE count in one clause, puts the money-losing campaign second
where it cannot be missed, and stops.

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
