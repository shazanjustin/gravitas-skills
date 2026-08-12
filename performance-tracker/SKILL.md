---
name: performance-tracker
description: |
  Read the team's "Performance" task/deliverables list (NocoDB "Central" base)
  through the Gravitas gateway: what's assigned, due dates, status, estimated
  hours, deck links, which Rumah. Use for questions like "what's on the
  Performance list", "what is Serene working on", "what's due this week", or
  "show completed deliverables". Read-only, one table, no NocoDB token needed.
compatibility: |
  Requires curl. Uses GRAVITAS_GATEWAY_KEY + GRAVITAS_GATEWAY_URL from
  ~/.gravitas-skills/.env (already present in the ev container). No NocoDB
  token is needed or handled here — the gateway holds it server-side.
---

# Performance Tracker

Reads the **Performance** table in the NocoDB "Central" base — the team's task
and deliverables list — through the Gravitas gateway (`gateway.shazan.me`).

The gateway holds the NocoDB credential and only exposes this one table,
read-only. You get rows back; you never see the token, cannot write, and no
other base or table is reachable through this route. If you need to *add* or
*edit* tasks, that is a separate, deliberately gated capability — not this skill.

## Fetch

```bash
source ~/.gravitas-skills/.env
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/nocodb/performance?limit=100"
```

Returns `{"list":[ ... ]}` — one object per task.

## Fields per row

- `Task Name`, `Task Description`
- `Due Date` (`YYYY-MM-DD`), `Status` (single-select, e.g. *To start* /
  *Currently doing* / *Completed*)
- `Est. Hours` (number)
- `Assigned to` — array of users, each `{ email, display_name }`
- `Assigned By` — user object
- `Deck Link` (URL), `Rumah` (team, e.g. "Rumah Hijau"), `Account`
- `Id`, `CreatedAt`, `UpdatedAt`

## Filtering & sorting

The route passes a whitelist of NocoDB read params straight through:
`limit` (capped at 200), `offset`, `where`, `sort`, `fields`, `viewId`.

```bash
# Open (not completed) tasks
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/nocodb/performance?where=(Status,neq,Completed)&limit=100"

# Soonest due first, only a few fields
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/nocodb/performance?sort=Due%20Date&fields=Task%20Name,Due%20Date,Status,Assigned%20to"
```

NocoDB `where` grammar is `(Field,op,value)` — ops include `eq`, `neq`, `like`,
`gt`, `lt`, `isWithin`; combine with `~and` / `~or`.

## Notes

- **Read-only by design.** There is no add/edit/delete path here.
- **Filtering by assignee:** `Assigned to` is a linked-user field, so a server
  `where` on it is unreliable. Simplest is to pull the rows and filter on the
  email inside each row's `Assigned to` array yourself.
- **Undated tasks are legitimate** — rows with a `Task Name` but no `Due Date`
  exist; report them as undated rather than dropping them.
- Never paste raw gateway keys or tokens into chat.
