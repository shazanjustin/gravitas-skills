# Objective → metric set

Meta's own "Results" column is **the optimization goal's outcome**, not a fixed
list. Reporting spend / impressions / CPM on a conversions campaign describes
delivery, not performance, and reads as a report that missed the point.

Always resolve the objective **before** choosing fields:

```bash
curl -s -g "https://graph.facebook.com/v25.0/<CAMPAIGN_ID>?fields=id,name,objective,effective_status,daily_budget,lifetime_budget&access_token=$TOKEN"
```

`objective` sits on the campaign; `optimization_goal` and `billing_event` sit on
the **ad set** and are what actually decide the result metric. `OUTCOME_ENGAGEMENT`
alone is ambiguous — pull the ad set too:

```bash
curl -s -g "https://graph.facebook.com/v25.0/<ADSET_ID>?fields=optimization_goal,billing_event,destination_type&access_token=$TOKEN"
```

## The mapping

Every row assumes `spend, impressions, reach, frequency, account_currency` as the
shared delivery base. The columns below are what you **add**, and the primary
metric is what you lead the answer with.

| Objective | Lead with | Add to `fields` | Pull from `actions[]` |
|---|---|---|---|
| `OUTCOME_SALES` | cost per purchase, ROAS | `actions, action_values, cost_per_action_type, purchase_roas, website_purchase_roas` | `purchase` / `omni_purchase`, `add_to_cart`, `initiate_checkout`, `landing_page_view` |
| `OUTCOME_LEADS` | cost per lead | `actions, cost_per_action_type, outbound_clicks` | `lead`, `onsite_conversion.lead_grouped`, `offsite_conversion.fb_pixel_lead` |
| `OUTCOME_TRAFFIC` | cost per landing page view | `outbound_clicks, outbound_clicks_ctr, cost_per_outbound_click, actions, cost_per_action_type` | `link_click`, `landing_page_view` |
| `OUTCOME_ENGAGEMENT` (video) | cost per ThruPlay | `video_thruplay_watched_actions, video_p25_watched_actions, video_p50_watched_actions, video_p75_watched_actions, video_p100_watched_actions, video_avg_time_watched_actions, cost_per_thruplay` | `video_view` |
| `OUTCOME_ENGAGEMENT` (post) | cost per engagement | `actions, cost_per_action_type` | `post_engagement`, `post_reaction`, `comment`, `post` (= shares) |
| `OUTCOME_ENGAGEMENT` (messaging) | cost per conversation | `actions, cost_per_action_type` | `onsite_conversion.messaging_conversation_started_7d` |
| `OUTCOME_AWARENESS` | CPM, reach, frequency | `estimated_ad_recallers, cost_per_estimated_ad_recallers` | — |
| `OUTCOME_APP_PROMOTION` | cost per install | `actions, cost_per_action_type, mobile_app_purchase_roas` | `mobile_app_install`, `app_custom_event.*` |

Legacy objectives still appear on older campaigns and map straight across:
`CONVERSIONS`/`PRODUCT_CATALOG_SALES` → SALES, `LINK_CLICKS` → TRAFFIC,
`VIDEO_VIEWS`/`POST_ENGAGEMENT` → ENGAGEMENT, `REACH`/`BRAND_AWARENESS` →
AWARENESS, `APP_INSTALLS` → APP_PROMOTION, `LEAD_GENERATION` → LEADS.

Derived numbers worth computing rather than requesting:

- **Hook rate** = 3s video views ÷ impressions. The single best creative
  diagnostic on a video buy.
- **Hold rate** = `video_p100` ÷ 3s views.
- **LPV ratio** = landing page views ÷ link clicks. Well under 1 means the
  landing page or load time is losing people the ads already paid for.
- **Frequency** = impressions ÷ reach, but only within one window (see traps).

## Listing what is actually running

"All running ads" is not `effective_status = ACTIVE` on the ad alone. An ACTIVE
ad under a paused ad set or campaign does not deliver. Filter on the ad's
`effective_status`, which already folds in the parents:

```bash
curl -s -g "https://graph.facebook.com/v25.0/act_<ACCOUNT_ID>/ads?fields=id,name,effective_status,adset{id,name,effective_status,optimization_goal},campaign{id,name,objective,effective_status}&filtering=[{\"field\":\"effective_status\",\"operator\":\"IN\",\"value\":[\"ACTIVE\"]}]&limit=200&access_token=$TOKEN"
```

Then request insights separately at `level=ad` and **join the two lists**.

## Collaborative Ads report conversions somewhere else

If the account runs **Collaborative Ads (CPAS)** — a brand buying against a
retailer's catalogue, which any `* CPAS` account here does — conversions do
**not** appear in `actions[]`. They come back in `catalog_segment_actions`,
with `catalog_segment_value` for the revenue. Ads Manager labels them
"purchases with shared items" and "in-app adds to cart with shared items".

Omit those fields and a CPAS campaign is *structurally incapable* of showing a
conversion: `actions[]` still carries the engagement and video types, so the
response looks healthy while everything commercial is missing, and the campaign
reads as a total failure. Measured 18 Aug 2026, a campaign reported as 0
purchases was in fact returning 16 purchases at 68.74 MYR each on a **6.81
ROAS** — the best performer in the account, called the worst.

Request them alongside the normal sales fields:

```
catalog_segment_actions, catalog_segment_value,
converted_product_quantity, converted_product_value
```

Resolve purchases as `actions[purchase]` first, then
`catalog_segment_actions[purchase]`, then `converted_product_quantity`.

## Traps

Each of these has produced a wrong number in a real report.

- **An active ad that spent nothing returns no insights row.** The insights edge
  only emits rows for entities with delivery in the window. If you build the
  report from insights alone, ads that are live but not spending vanish — and a
  live ad spending nothing is usually the finding, not a blank. Always start
  from the entity list and left-join insights onto it.
- **`clicks` is not `link_clicks`.** `clicks` counts every click including
  reactions, comments, and profile taps, and `ctr` is computed from it. On a
  traffic or conversion buy that inflates performance, sometimes several-fold.
  Report `outbound_clicks` / `outbound_clicks_ctr` instead.
- **Attribution windows decide conversion counts.** The same campaign returns
  different purchase numbers under `1d_view` vs `7d_click`. Pass
  `use_unified_attribution_setting=true` so figures reconcile with what the
  client sees in Ads Manager; if you override with
  `action_attribution_windows`, state the window in the answer.
- **`actions`, `action_values`, `cost_per_action_type` and `purchase_roas` are
  all arrays of `{action_type, value}`**, not scalars. Flatten to the action
  types you need. Never print them raw — see the safety rules in SKILL.md.
- **`spend` carries no currency.** Always request `account_currency` and print
  it. MY accounts bill MYR, SG accounts SGD; never sum across them.
- **Meta clamps `until` to today.** A range ending in the future returns
  `date_stop` = today, so a partial month silently reads as a full one. Report
  the range actually covered.
- **`date_preset=maximum` is lifetime** and blends every optimization change the
  campaign has been through. For "how is it doing", use an explicit recent
  `time_range`; reserve lifetime for "what did this cost in total".
- **Frequency cannot be averaged across breakdowns.** Recompute it from summed
  impressions and reach, and note that reach does not sum across placements —
  the same person reached on Feed and Reels is one person, so per-placement
  reach added together overcounts.
- **Paused ads keep their spend.** Filtering on
  `effective_status = ACTIVE` drops ads that spent earlier in the window and
  were paused since, so account and campaign totals silently undershoot Ads
  Manager. Measured: 883.83 MYR reported against 1,099.86 actual, and the
  missing 216 MYR carried most of the conversions. Reconcile totals with
  `status=any`; reserve the ACTIVE filter for "what is running", never for
  "what did this cost".
- **`curl -g` is mandatory** on any URL containing `{...}` — `time_range` and
  `filtering` both do. Without it curl glob-expands the URL, fires the request
  without the parameter, and the resulting error points nowhere near the cause.
