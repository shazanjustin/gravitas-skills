---
name: performance-tracker
description: |
  Read and edit the team's "Performance" task/deliverables list (NocoDB
  "Central" base) through the Gravitas gateway: what's assigned, due dates,
  status, estimated hours, deck links, which Rumah. Use for questions like
  "what's on the Performance list", "what is Serene working on", "what's due
  this week", "mark task 42 complete", or "change task 42's due date". One
  table only; supports guarded edits without exposing the NocoDB token.
compatibility: |
  Requires curl. Uses GRAVITAS_GATEWAY_KEY + GRAVITAS_GATEWAY_WRITE_KEY +
  GRAVITAS_GATEWAY_URL from ~/.gravitas-skills/.env (already present in the ev
  container). No NocoDB token is needed or handled here — the gateway holds it
  server-side.
---

# Performance Tracker

Reads and edits the **Performance** table in the NocoDB "Central" base — the
team's task and deliverables list — through the Gravitas gateway
(`gateway.shazan.me`).

The gateway holds the NocoDB credential and only exposes this one table. You
never see the token, and no other base or table is reachable through this route.
Edits require a numeric row `Id`; create and delete are not supported.

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

## Edit one task

Always fetch the row first and identify it by its numeric `Id`. If the user's
request could match multiple rows, ask which row they mean. Before editing,
state the exact row and field change and get confirmation unless the user has
already explicitly named both in the same request.

```bash
source ~/.gravitas-skills/.env
curl --fail-with-body -sS -X PATCH \
  -H "x-api-key: $GRAVITAS_GATEWAY_WRITE_KEY" \
  -H "Content-Type: application/json" \
  "$GRAVITAS_GATEWAY_URL/nocodb/performance" \
  -d '{"Id":42,"Status":"Completed"}'
```

Editable fields: `Task Name`, `Task Description`, `Due Date`, `Status`,
`Est. Hours`, `Deck Link`. Assignment, Rumah, and Account changes stay blocked
until their relation payloads and authorization rules are documented.

Only send `Id` plus the fields being changed. After a 2xx response, fetch the row
again with `where=(Id,eq,42)` and compare every requested value with the saved
row. Report a mismatch as a failed edit and do not retry blindly. Never send a
full row snapshot: the route is last-write-wins, so minimal changed-field patches
avoid restoring stale values.

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

- Edits are scoped to existing rows and allowlisted fields. There is no add or
  delete path.
- **Filtering by assignee:** `Assigned to` is a linked-user field, so a server
  `where` on it is unreliable. Simplest is to pull the rows and filter on the
  email inside each row's `Assigned to` array yourself.
- **Undated tasks are legitimate** — rows with a `Task Name` but no `Due Date`
  exist; report them as undated rather than dropping them.
- Never paste raw gateway keys or tokens into chat.
