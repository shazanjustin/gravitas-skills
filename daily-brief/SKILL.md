---
name: daily-brief
description: >
  Runs a structured morning brief — checks calendar, goals, tasks, and habits
  from Directus, fetches today's events via Composio MCP, and composes a
  personalized motivational summary. Self-improves every run by logging
  mistakes, fixes, and improvements to the skill file itself.
compatibility: |
  Requires: curl, python3, jq. Env vars: DIRECTUS_URL, DIRECTUS_TOKEN,
  COMPOSIO_MCP_URL, COOLIFY_URL, COOLIFY_API_TOKEN (for env bootstrap).
  Timezone: Asia/Kuala_Lumpur.
triggers: |
  "good morning", "daily brief", "what's my day", "daily", "brief me"
---

# Daily Brief

**Triggers:** "good morning", "daily brief", "what's my day", "daily", "brief me"

When the user says any of these, run the full daily brief:
1. Read `/workspace/ME.md` to know who they are
2. Get current date/time (MYT)
3. Query Directus for goals, tasks, habits
4. Query Composio MCP for today's calendar events
5. Synthesize into a structured morning brief
6. Offer follow-up actions
7. Self-improvement: log what went well, mistakes, fixes, and update the skill

---

## Step 1 — Read identity

Read `/workspace/ME.md` to know the user's name, what services they use, and their goals context.

## Step 2 — Get time

Use:
```bash
TZ='Asia/Kuala_Lumpur' date '+%A, %B %d, %Y — %I:%M %p %Z'
```

Greet appropriately (morning/afternoon/evening based on local hour).

## Step 3 — Query Directus

Directus is at `$DIRECTUS_URL` with API token `$DIRECTUS_TOKEN`.

> ⚠️ All user collections are under the `timetracker_*` prefix.

### Goals

```bash
curl -s "$DIRECTUS_URL/items/timetracker_goals?access_token=$DIRECTUS_TOKEN&limit=200"
```

| Field | What it is |
|---|---|
| `content` | Goal description |
| `scope` | yearly / monthly / weekly / daily |
| `periodKey` | e.g. "2026", "2026-W20", "2026-05" |
| `done` | true / false / null |
| `targetValue` | Numeric target |
| `currentValue` | Current progress |
| `deadlineIso` | Due date |

### Tasks

```bash
curl -s "$DIRECTUS_URL/items/timetracker_tasks?access_token=$DIRECTUS_TOKEN&limit=200&sort[]=-updatedAt&meta=total_count"
```

> ⚠️ There are 232+ total tasks. Always use `meta=total_count` and `limit=200` to catch pagination.
> Filter client-side: `not deleted` AND `not completed` / `status not done`.

| Field | What it is |
|---|---|
| `title` | Task name |
| `status` | todo / in_progress / done / blocked / not_started |
| `completed` | true / false |
| `deleted` | true / false |
| `dueDate` | Due date (YYYY-MM-DD) |
| `project` / `projectId` | Grouping |
| `importance` | Priority (1-3) |
| `updatedAt` | Last update (sort by this!) |

### Habits

```bash
curl -s "$DIRECTUS_URL/items/timetracker_habits?access_token=$DIRECTUS_TOKEN&limit=100"
```

For logs:
```bash
curl -s "$DIRECTUS_URL/items/timetracker_habit_logs?access_token=$DIRECTUS_TOKEN&limit=100&sort[]=-date"
```

| Field | What it is |
|---|---|
| `name` | Habit name |
| `type` | check / number |
| `target` | Daily target count |
| `unit` | Unit label |
| `active` | true / false |
| `deleted` | true / false |

Habit logs schema:

| Field | What it is |
|---|---|
| `habitId` | UUID of the habit |
| `date` | YYYY-MM-DD |
| `value` | Number or "true"/"false" for check type |

> Note: Habit tracking stopped around Dec 2025 / Jan 2026. No recent logs expected.

### Helper script

Alternatively, run:
```bash
bash scripts/fetch-data.sh
```
to dump all Directus data into `/tmp/daily-brief-data.json`.

## Step 4 — Query Calendar (Composio MCP)

Use the MCP protocol to get today's events:

```bash
echo '{"jsonrpc":"2.0","method":"tools/call","params":{
  "name":"GOOGLECALENDAR_FIND_EVENT",
  "arguments":{
    "calendar_id":"primary",
    "time_min":"YYYY-MM-DDT00:00:00Z",
    "time_max":"YYYY-MM-DDT23:59:59Z"
  }
},"id":1}' | \
curl -s --max-time 10 \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d @- \
  "$COMPOSIO_MCP_URL"
```

> ⚠️ Must include both `Accept: application/json` AND `text/event-stream` headers.
> Use `GOOGLECALENDAR_FIND_EVENT` (not `calendar_get_events`).

If not available, skip gracefully.

## Step 5 — Compose the brief

Format the output compactly (for Termux/mobile readability). Use this template:

```
☀️ Good {morning/afternoon/evening} Shazan — {day}, {date} — {time} MYT


📅 TODAY
  ✅ HH:MM  Event (done)
  🔴 NOW   Current event
  🔜 HH:MM  Upcoming event
  📧 All-day  Event


🎯 {YEAR} GOALS (all ❌)
  goal1 · goal2 · goal3


✅ TASKS — {N} active (of {total} total)

  🔄 Obsidian CMS · RSS feed to telegram
  ⏸️ Data scraper
  ⬜ Group1 (N) · Group2 (N) · Group3 (N)


📊 HABITS — {N} (note if stale)

  Health     Sleep 7h 🛏️  Walk 🚶  Stairs 🪜  Steps 👣
             Weight ⚖️  No phone 🚽📵  Calories 🍽️
  Spiritual  Khatam 30pg 📖
  Learn      Read 50pg 📚  3 Notes 📝  3+3 articles 📰
  Build      1 commit 💻  1 Notakaki ✍️  1 app 📱
  Mindset    Journal 📔  Work smart 💡  Update 🔄


⚡ PUSH
  Personalized 1-2 line motivational message referencing their
  actual goals, tasks, or events today. Keep it punchy. 🔥


─────────────────────────────

a) 📧 Check Gmail
b) 💡 Suggest what to work on first
c) ➕ Add a new task/goal/habit
d) ✅ Log a habit for today
```

## Step 6 — Offer follow-up actions

After the brief, ask which action they want (a/b/c/d from the template).

## Step 7 — Self-Improvement (run every time)

After the brief and any follow-ups, run self-improvement:

### 7a — Reflect on this run

Think about:
- **What went well?** — e.g. data sources that worked well, formatting that clicked
- **What went wrong / mistakes?** — e.g. wrong collection names, missing pagination, stale data, wrong timezone, formatting issues
- **How to fix those mistakes?** — specific actionable fixes
- **Improvement ideas** — what would make the next brief better, faster, more useful
- **User feedback from this session** — what did the user ask for or complain about?

### 7b — Read the Self-Improvement Log

Read the `## Self-Improvement Log` section at the bottom of this file. Check what was previously noted and whether those fixes were applied.

### 7c — Update the Self-Improvement Log

Append a new entry to the `## Self-Improvement Log` section at the bottom of this file with:

```markdown
### Run YYYY-MM-DD HH:MM

**What went well:**
- ...

**Mistakes / Issues:**
- ...

**Fixes applied this run:**
- ...

**Improvement ideas:**
- ...

**User feedback:**
- ...

**Changes made to this skill:**
- ...
```

### 7d — Apply fixes to the skill itself

If you identified a fix that can be applied to the skill instructions (e.g. wrong collection names, better query patterns, better formatting), update the relevant section of this file immediately so the next run benefits.

### 7e — Check pending TODOs

If there are pending `[TODO]` items in the log, try to address one if possible.

---

## Self-Improvement Log

<!-- Each run appends a new entry here to track what was learned and improved. -->

### Run 2026-05-17 10:33

**What went well:**
- Successfully extracted env vars from PID 1 and persisted them
- All integrations verified (Coolify, Directus, GitHub, Composio, Cloudflare)
- Calendar events fetched successfully via Composio MCP
- Discovered correct Directus collection names (timetracker_goals, timetracker_tasks, etc.)

**Mistakes / Issues:**
- COOLIFY_URL was incorrectly set to pi.shazan.me (service URL) instead of coolify.shazan.me (server URL)
- Initial Directus queries used wrong collection names (goals, tasks, habits instead of timetracker_*)
- Initial run missed pagination — only showed 9 tasks instead of 56
- Habit logs showed no recent data because tracking stopped in Dec 2025
- Time was wrong (showed 2:32 AM instead of 10:33 AM) — used server time instead of MYT
- Composio MCP needed specific headers (Accept: application/json, text/event-stream) and MCP protocol format

**Fixes applied this run:**
- Fixed COOLIFY_URL to point to coolify.shazan.me
- Created /root/.env-vars with proper export syntax
- Added auto-source to .bashrc
- Updated Directus queries to use timetracker_* collection names
- Added pagination awareness — now uses limit=200, meta=total_count
- Added sort[]=-updatedAt to get newest tasks first
- Added TZ='Asia/Kuala_Lumpur' for correct local time
- Calendar query now uses MCP protocol (tools/call) with proper headers

**Improvement ideas:**
- [TODO] Add weekly habit streak calculation from habit_logs when data is fresh
- [TODO] Show goal progress bars if timetracker_goals ever has currentValue/targetValue
- [TODO] Add ability to log a habit directly from the brief flow
- [TODO] Add email summary from Gmail via Composio
- [TODO] Add n8n workflow status check via Coolify
- [TODO] Make the habit sections collapsible for Termux/mobile readability
- [TODO] Auto-detect timezone from env or IP instead of hardcoding Asia/Kuala_Lumpur

**User feedback:**
- Tasks were incomplete — pagination issue, fixed by increasing limit and checking meta.total_count
- Time was wrong — fixed by using TZ=Asia/Kuala_Lumpur
- Termux readability — need more compact formatting with blank lines
- Needs self-improvement mechanism — this log was created

**Changes made to this skill:**
- Added Step 7 — Self-Improvement
- Added Self-Improvement Log section at bottom
- Updated Directus collection names from old guesses to actual timetracker_* names
- Added YAML frontmatter matching gravitas-skills repo convention
- Added helper script scripts/fetch-data.sh

---

## Notes

- Never print API tokens. Use `$VAR_NAME` references.
- If a service is unavailable, skip that section gracefully — don't error out.
- Keep the tone motivational but honest. If they're slacking on something, call it out with a friendly nudge.
- The user's identity file is at `/workspace/ME.md`.
- **Time**: Always use `TZ='Asia/Kuala_Lumpur'` for local time.
- **Tasks**: There are 232+ total tasks. Always use `limit=200&sort[]=-updatedAt` and check `meta.total_count` for pagination.
- **Directus collections**: All user data is under `timetracker_*` prefix (timetracker_tasks, timetracker_goals, timetracker_habits, timetracker_habit_logs).
- **Composio MCP**: Use tools/call method with GOOGLECALENDAR_FIND_EVENT for calendar. Headers must include `Accept: application/json, text/event-stream`.
