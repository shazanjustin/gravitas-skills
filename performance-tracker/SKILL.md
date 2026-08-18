---
name: performance-tracker
description: |
  Read and edit the team's "Performance" task/deliverables list (NocoDB
  "Central" base) through the Gravitas gateway: what's assigned, due dates,
  status, estimated hours, deck links, which Rumah. Use for questions like
  "what's on the Performance list", "what is Serene working on", "what's due
  this week", "mark task 42 complete", or "change task 42's due date". Also
  builds the daily standup digest posted to Discord. One
  table only; supports guarded adds and edits without exposing the NocoDB token.
compatibility: |
  Requires node (>=18, for global fetch). Uses GRAVITAS_GATEWAY_KEY +
  GRAVITAS_GATEWAY_WRITE_KEY + GRAVITAS_GATEWAY_URL from
  ~/.gravitas-skills/.env (already present in the ev container). No NocoDB
  token is needed or handled here — the gateway holds it server-side.
---

# Performance Tracker

Reads, adds to and edits the **Performance** table in the NocoDB "Central" base — the
team's task and deliverables list — through the Gravitas gateway
(`gateway.shazan.me`).

The gateway holds the NocoDB credential and only exposes this one table. You
never see the token, and no other base or table is reachable through this route.
Edits require a numeric row `Id`. Rows can be created, but never deleted.

**Use `scripts/perf.mjs` rather than hand-rolling HTTP calls.** It reads the
same env file, prints a compact table instead of ~23KB of JSON for 43 rows, and
makes every write dry-run by default with a mandatory read-back check. The raw HTTP
contract is documented at the bottom for cases the script doesn't cover.

## Read

```bash
node scripts/perf.mjs list --open          # everything not Completed
node scripts/perf.mjs list --overdue       # open and past due, as of today
node scripts/perf.mjs list --who serene    # substring match on assignee
node scripts/perf.mjs list --due 7d        # due within 7 days (or --due 2026-08-31)
node scripts/perf.mjs list --status "In Progress"
node scripts/perf.mjs list --undated       # rows with no Due Date
node scripts/perf.mjs show 42              # one row, all fields
```

Filters combine. Output is sorted soonest-due-first with undated rows last, and
overdue dates are marked with a trailing `!`. Add `--json` to `list` for the raw
gateway rows when you need a field the table doesn't show.

Every result carries a NocoDB link — `list` prints the table URL in its footer,
while `show`, `set` and `add` return a `url` deep-linked to that row
(`?rowId=N`). Pass
it along when reporting to a human so they can click through and see the row
themselves.

## Edit one task

Identify the row by its numeric `Id` — `list`/`show` first if you don't have it.
If the request could match multiple rows, ask which one. Before applying, state
the exact row and field change and get confirmation, unless the user already
named both in the same request.

```bash
node scripts/perf.mjs set 42 --status Completed             # dry-run: prints the diff
node scripts/perf.mjs set 42 --status Completed --apply     # actually writes
```

Fields: `--name`, `--desc`, `--due YYYY-MM-DD` (or `--due ""` to clear),
`--status`, `--hours`, `--deck`. Several can be set in one call.

The script refuses an edit that would change nothing, rejects a `--status`
outside the known list (`--allow-new-status` overrides), sends only the changed
fields, and after applying re-fetches the row and compares every requested value
against what was saved — a mismatch is reported as a failed edit and is not
retried. That read-back matters because the route is last-write-wins and a 2xx
is not proof the value landed.

`Assigned to`, `Rumah` and `Account` **cannot be changed on an existing row** —
the gateway rejects them on edit. They can only be set when the task is created
(see below). Reassigning someone else's task is a decision the tracker does not
let you make from here; do it in NocoDB.

## Add a task

```bash
node scripts/perf.mjs add --name "CIMB Aug Report: Data Collection" \
  --due 2026-09-02 --status "To Do" --who dulanaka.yasaswin@gravitas.my \
  --rumah "Rumah Hijau" [--apply]
```

`--name` is required; everything else is optional. On top of the editable
fields, `add` also takes the three create-only ones: `--who` (assignee, by email
— NocoDB resolves the address to the user), `--rumah`, and `--account`.

Like `set`, it is dry-run by default and prints exactly what it would create.
On `--apply` it creates the row, then re-fetches it by the returned `Id` and
verifies every field, reporting the new row's `url`.

**There is no delete.** A row added by mistake has to be removed by hand in
NocoDB, so prefer running the dry-run first and reading it.

One row per call — the gateway takes a single object, not a batch. Adding
several tasks means several calls.

## Daily digest

```bash
node scripts/perf.mjs digest [--title Standup] [--max-per-person 6]
```

Prints a ready-to-post Discord block: open tasks grouped by person,
alphabetically, overdue ones flagged 🔴 with how many days late, and a link to
the table. Completed rows are excluded.

It is built to land in **one** Discord message: if the block would exceed 2000
characters the per-person cap tightens until it fits, and the excess shows as
"…and N more". Deciding that here beats letting Discord's chunker pick a split
point — a standup spread over two messages has stopped being scannable.

**Post it verbatim.** When this runs on a schedule, the whole point is that the
output is identical every morning; re-describing or "improving" the layout each
day defeats it. If the format is wrong, change it here, not in the prompt.

Suggested schedule (weekdays, 9am Malaysia — `/ev-schedule add` in Discord):

> prompt: Run `node /root/gravitas-workspace/.pi/skills/performance-tracker/scripts/perf.mjs digest` and post its output exactly as-is — no preamble, no summary, no reformatting.
> cron: `0 9 * * 1-5`  ·  tz: `Asia/Kuala_Lumpur`

Dates are resolved in `EV_SCHEDULE_TZ` (default `Asia/Kuala_Lumpur`), not the
container's UTC — otherwise a 9am run computes "overdue" against yesterday.

## Fields per row

- `Task Name`, `Task Description`
- `Due Date` (`YYYY-MM-DD`), `Status` (single-select)
- `Est. Hours` (number)
- `Assigned to` — array of users, each `{ email, display_name }`
- `Assigned By` — user object
- `Deck Link` (URL), `Rumah` (team, e.g. "Rumah Hijau"), `Account`
- `Id`, `CreatedAt`, `UpdatedAt`

`Status` values in use are **To Do**, **In Progress**, **Internal Review**,
**Completed**. (Do not confuse these with the Deadline Tracker's own status
vocabulary — *To start / Can start / Currently doing / Ongoing / Delivered* —
which belongs to a different system and is rejected here.)

## Notes

- Edits are scoped to existing rows and allowlisted fields. Creates are one row
  per call. There is no delete path.
- **Reads and writes use different keys.** `GRAVITAS_GATEWAY_KEY` is read-only;
  a POST or PATCH with it returns 401. Both need `GRAVITAS_GATEWAY_WRITE_KEY`.
- **Filtering by assignee:** `Assigned to` is a linked-user field, so a server
  `where` on it is unreliable — `--who` filters the fetched rows client-side for
  this reason.
- **Undated tasks are legitimate** — rows with a `Task Name` but no `Due Date`
  exist; report them as undated rather than dropping them. Date filters like
  `--due` necessarily exclude them; use `--undated` to see them.
- Never paste raw gateway keys or tokens into chat.

## Raw HTTP contract

Only needed for something `perf.mjs` doesn't do (e.g. `viewId`, `offset`
paging). The route passes a whitelist of NocoDB read params straight through:
`limit` (capped at 200), `offset`, `where`, `sort`, `fields`, `viewId`.

```bash
source ~/.gravitas-skills/.env

# Read
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_KEY" \
  "$GRAVITAS_GATEWAY_URL/nocodb/performance?where=(Status,neq,Completed)&limit=100"

# Edit — minimal changed-field patch only, never a full row snapshot
curl --fail-with-body -sS -X PATCH \
  -H "x-api-key: $GRAVITAS_GATEWAY_WRITE_KEY" \
  -H "Content-Type: application/json" \
  "$GRAVITAS_GATEWAY_URL/nocodb/performance" \
  -d '{"Id":42,"Status":"Completed"}'

# Create — one object, no Id (NocoDB assigns it and returns [{"Id":N}])
curl --fail-with-body -sS -X POST   -H "x-api-key: $GRAVITAS_GATEWAY_WRITE_KEY"   -H "Content-Type: application/json"   "$GRAVITAS_GATEWAY_URL/nocodb/performance"   -d '{"Task Name":"New task","Due Date":"2026-09-02","Assigned to":"someone@gravitas.my"}'
```

NocoDB `where` grammar is `(Field,op,value)` — ops include `eq`, `neq`, `like`,
`gt`, `lt`, `isWithin`; combine with `~and` / `~or`. If you write by hand, do
the read-back comparison yourself.
