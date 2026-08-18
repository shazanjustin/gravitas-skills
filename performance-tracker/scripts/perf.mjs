#!/usr/bin/env node

// Read and edit the Central > Performance table through the Gravitas gateway.
//
// Why this exists rather than the curl snippets in SKILL.md: a bare fetch
// returns ~23KB of JSON for 43 rows, nearly all of it fields nobody asked for,
// and every caller then re-derives the same filtering by hand. `list` prints
// the same information in ~1KB. `set` exists because the edit route is
// last-write-wins and needs a read-back check to be safe -- prose can ask for
// that, code can guarantee it.

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const ROUTE = "/nocodb/performance";

// Where a human goes to see this table. Unrelated to the API path the gateway
// uses (/api/v2/tables/<tableId>/records), which needs no base or view id --
// these two ids exist only in the dashboard URL and cannot be discovered
// through the gateway, so they are recorded here.
const TABLE_URL =
  "https://ozy.gravitas.my/wxnfngze/pboui1exiw4lryy/mr4y6x8f39y5m4k/vwp212p03jtdkys1/performance-task-list";
// NocoDB opens the expanded row for ?rowId=N. If a future version renames the
// param it degrades to opening the plain table view, not to a broken link.
const rowUrl = (id) => `${TABLE_URL}?rowId=${id}`;
const DEFAULT_ENV_FILE = join(homedir(), ".gravitas-skills", ".env");
const MAX_LIMIT = 200; // the gateway caps it here; asking for more is silently clamped

// Editable per the gateway's allowlist. `Assigned to`, `Rumah` and `Account`
// are deliberately absent -- the route rejects them.
const FIELD_TO_COLUMN = {
  name: "Task Name",
  desc: "Task Description",
  due: "Due Date",
  status: "Status",
  hours: "Est. Hours",
  deck: "Deck Link",
};

// Creatable but not editable: the gateway takes these on POST and refuses them
// on PATCH. Authoring a task with no owner is fine to allow; reassigning
// someone else's existing task is not.
const CREATE_ONLY_FIELD_TO_COLUMN = {
  who: "Assigned to", // an email address; NocoDB resolves it to the user
  rumah: "Rumah",
  account: "Account",
};

// Observed single-select values. The route can't enumerate the real option
// list, so this is a typo guard, not a schema -- --allow-new-status skips it.
const KNOWN_STATUSES = ["To Do", "In Progress", "Internal Review", "Completed"];

function usage(exitCode = 1) {
  console.error(`Usage:
  node perf.mjs list [filters]
  node perf.mjs show <Id>
  node perf.mjs set <Id> [fields...] [--apply]
  node perf.mjs add --name "New task" [fields...] [--apply]
  node perf.mjs digest [--title Standup] [--max-per-person 6]

Filters for list:
  --open                 exclude Completed
  --overdue              open rows whose Due Date is before today
  --status "To Do"       exact status match
  --who serene           substring match on assignee email/name
  --due 7d | 2026-08-31  due on or before N days from now / that date
  --undated              only rows with no Due Date
  --json                 raw gateway rows instead of the compact table

Fields for set:
  --name "New task name"
  --desc "Longer description"
  --due 2026-08-24        (YYYY-MM-DD, or "" to clear)
  --status Completed
  --hours 4
  --deck https://...
  --allow-new-status      accept a --status outside the known list

Extra fields for add (create-only; the gateway refuses them on set):
  --who someone@gravitas.my   assignee, by email
  --rumah "Rumah Hijau"
  --account "Client name"

digest prints a ready-to-post Discord block: open tasks grouped by person,
overdue flagged, capped to fit one 2000-char message.

Env (process.env wins, else --env-file, else ~/.gravitas-skills/.env):
  GRAVITAS_GATEWAY_URL, GRAVITAS_GATEWAY_KEY, GRAVITAS_GATEWAY_WRITE_KEY

set and add default to dry-run. Add --apply to write.
There is no delete: a row created by mistake has to be removed in NocoDB.`);
  process.exit(exitCode);
}

function parseArgs(argv) {
  const flags = new Set(["apply", "dryRun", "open", "overdue", "undated", "json", "allowNewStatus"]);
  const out = { _: [], apply: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--")) { out._.push(arg); continue; }
    const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    if (key === "dryRun") { out.apply = false; continue; }
    if (flags.has(key)) { out[key] = true; continue; }
    const value = argv[++i];
    if (value === undefined) usage();
    out[key] = value;
  }
  return out;
}

// Env files here are hand-maintained and have been seen with CRLF endings and
// quoted values; a stray \r in a header value makes fetch throw on an invalid
// header rather than fail a request, which is a confusing way to find out.
function loadEnvFile(path) {
  const out = {};
  if (!path || !existsSync(path)) return out;
  for (const line of readFileSync(path, "utf8").replace(/\r/g, "").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 1) continue;
    out[trimmed.slice(0, eq)] = trimmed.slice(eq + 1).replace(/^["']|["']$/g, "");
  }
  return out;
}

function resolveEnv(args) {
  const fromFile = loadEnvFile(args.envFile || DEFAULT_ENV_FILE);
  const pick = (name) => (process.env[name] || fromFile[name] || "").trim();
  return {
    url: pick("GRAVITAS_GATEWAY_URL") || "https://gateway.shazan.me",
    readKey: pick("GRAVITAS_GATEWAY_KEY"),
    writeKey: pick("GRAVITAS_GATEWAY_WRITE_KEY"),
  };
}

async function gatewayFetch(env, { method = "GET", query = "", key, body } = {}) {
  if (!key) {
    throw new Error(
      method === "GET"
        ? "GRAVITAS_GATEWAY_KEY is not set (pass --env-file or export it)"
        : "GRAVITAS_GATEWAY_WRITE_KEY is not set -- edits need the write key, which is not the read key",
    );
  }
  const headers = { "x-api-key": key };
  if (body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${env.url}${ROUTE}${query}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  if (!res.ok) throw new Error(`gateway ${method} ${res.status}: ${raw.slice(0, 300)}`);
  try {
    return raw ? JSON.parse(raw) : {};
  } catch {
    throw new Error(`gateway returned non-JSON: ${raw.slice(0, 200)}`);
  }
}

async function fetchRows(env, query = `?limit=${MAX_LIMIT}`) {
  const data = await gatewayFetch(env, { query, key: env.readKey });
  return data.list || [];
}

async function fetchRow(env, id) {
  const rows = await fetchRows(env, `?where=${encodeURIComponent(`(Id,eq,${id})`)}&limit=1`);
  if (!rows.length) throw new Error(`No row with Id ${id}`);
  return rows[0];
}

// "Today" has to be the team's today, not the container's. ev runs on UTC while
// everyone reading this is in Malaysia (UTC+8), so `new Date().toISOString()`
// reports yesterday's date for any run between 00:00 and 08:00 local -- which is
// exactly when a morning standup fires. Every overdue marker would be a day out.
// Same reasoning as ev's own EV_SCHEDULE_TZ default.
const TZ = process.env.EV_SCHEDULE_TZ || "Asia/Kuala_Lumpur";
// en-CA formats as YYYY-MM-DD, which sorts and compares like the ISO dates
// NocoDB stores.
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());

function assignees(row) {
  return (row["Assigned to"] || [])
    .map((u) => u.display_name || u.email || "")
    .filter(Boolean);
}

// Everyone is @gravitas.my and display_name is usually empty, so the domain is
// pure column width in the table. `show` still prints the full address.
function shortAssignees(row) {
  return assignees(row).map((who) => (who.includes("@") ? who.split("@")[0] : who));
}

function applyFilters(rows, args) {
  let out = rows;
  if (args.open) out = out.filter((r) => r.Status !== "Completed");
  if (args.status) out = out.filter((r) => (r.Status || "") === args.status);
  if (args.undated) out = out.filter((r) => !r["Due Date"]);
  if (args.overdue) {
    const now = today();
    out = out.filter((r) => r.Status !== "Completed" && r["Due Date"] && r["Due Date"] < now);
  }
  if (args.who) {
    const needle = String(args.who).toLowerCase();
    // `Assigned to` is a linked-user field, so a server-side `where` on it is
    // unreliable -- filter the fetched rows instead.
    out = out.filter((r) =>
      (r["Assigned to"] || []).some((u) =>
        `${u.email || ""} ${u.display_name || ""}`.toLowerCase().includes(needle),
      ),
    );
  }
  if (args.due) {
    let cutoff = String(args.due);
    const rel = cutoff.match(/^(\d+)d$/);
    if (rel) {
      const d = new Date();
      d.setDate(d.getDate() + Number(rel[1]));
      cutoff = d.toISOString().slice(0, 10);
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(cutoff)) throw new Error(`--due wants YYYY-MM-DD or Nd, got: ${args.due}`);
    // Undated rows are legitimate but can't satisfy a date bound; they are
    // excluded here and reachable with --undated.
    out = out.filter((r) => r["Due Date"] && r["Due Date"] <= cutoff);
  }
  return out;
}

function renderTable(rows) {
  if (!rows.length) return "(no matching rows)";
  const now = today();
  const header = ["Id", "Due", "Status", "Assignee", "Hrs", "Task"];
  const body = rows.map((r) => {
    const due = r["Due Date"] || "-";
    const late = r["Due Date"] && r["Due Date"] < now && r.Status !== "Completed";
    return [
      String(r.Id),
      late ? `${due}!` : due,
      r.Status || "-",
      shortAssignees(r).join(", ") || "-",
      r["Est. Hours"] == null ? "-" : String(r["Est. Hours"]),
      (r["Task Name"] || "").trim() || "-",
    ];
  });
  const widths = header.map((h, i) => Math.max(h.length, ...body.map((row) => row[i].length)));
  const line = (cells) => cells.map((c, i) => (i === cells.length - 1 ? c : c.padEnd(widths[i]))).join("  ");
  return [line(header), line(widths.map((w) => "-".repeat(w))), ...body.map(line)].join("\n");
}

function sortByDue(rows) {
  // Undated rows sort last rather than first, which is what "what's next"
  // callers expect; ISO dates compare correctly as strings.
  return [...rows].sort((a, b) => String(a["Due Date"] || "9999-99-99").localeCompare(String(b["Due Date"] || "9999-99-99")));
}

async function cmdList(env, args) {
  const rows = sortByDue(applyFilters(await fetchRows(env), args));
  if (args.json) {
    console.log(JSON.stringify(rows, null, 2));
    return;
  }
  const now = today();
  const overdue = rows.filter((r) => r["Due Date"] && r["Due Date"] < now && r.Status !== "Completed").length;
  console.log(renderTable(rows));
  console.log(`\n${rows.length} row(s)${overdue ? `, ${overdue} overdue (!) as of ${now}` : ""}`);
  console.log(TABLE_URL);
}

async function cmdShow(env, args) {
  const id = args._[1];
  if (!/^\d+$/.test(String(id || ""))) usage();
  const row = await fetchRow(env, Number(id));
  console.log(JSON.stringify({
    Id: row.Id,
    "Task Name": row["Task Name"],
    "Task Description": row["Task Description"],
    "Due Date": row["Due Date"],
    Status: row.Status,
    "Est. Hours": row["Est. Hours"],
    "Deck Link": row["Deck Link"],
    Rumah: row.Rumah,
    Account: row.Account,
    "Assigned to": assignees(row),
    UpdatedAt: row.UpdatedAt,
    url: rowUrl(row.Id),
  }, null, 2));
}

function buildPatch(args) {
  const patch = {};
  for (const [flag, column] of Object.entries(FIELD_TO_COLUMN)) {
    if (args[flag] === undefined) continue;
    let value = args[flag];
    if (flag === "hours") {
      if (!/^\d+(\.\d+)?$/.test(String(value))) throw new Error(`--hours wants a number, got: ${value}`);
      value = Number(value);
    }
    if (flag === "due" && value !== "" && !/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
      throw new Error(`--due wants YYYY-MM-DD (or "" to clear), got: ${value}`);
    }
    if (flag === "status" && !args.allowNewStatus && !KNOWN_STATUSES.includes(value)) {
      throw new Error(`Unknown status "${value}". Known: ${KNOWN_STATUSES.join(", ")}. Use --allow-new-status to send it anyway.`);
    }
    patch[column] = value === "" ? null : value;
  }
  return patch;
}

// --- digest -----------------------------------------------------------------
// A ready-to-post Discord block. Built here rather than described in a schedule
// prompt so the daily post is byte-identical every morning and a model wobble
// can't reshape it.

const DISCORD_MESSAGE_LIMIT = 2000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// NocoDB's display_name is null for everyone in this base, so names come from
// the address. A couple of people go by something shorter on the team's own
// trackers than their email suggests.
const DISPLAY_NAME_OVERRIDES = { "dulanaka.yasaswin": "Dula" };

function personName(email) {
  const local = (email || "").split("@")[0];
  if (DISPLAY_NAME_OVERRIDES[local]) return DISPLAY_NAME_OVERRIDES[local];
  const first = local.split(/[._-]/)[0] || local || "Unassigned";
  return first.charAt(0).toUpperCase() + first.slice(1);
}

const isoParts = (iso) => iso.split("-").map(Number);
const shortDate = (iso) => { const [, m, d] = isoParts(iso); return `${d} ${MONTHS[m - 1]}`; };
const asUTC = (iso) => { const [y, m, d] = isoParts(iso); return Date.UTC(y, m - 1, d); };
const daysBetween = (from, to) => Math.round((asUTC(to) - asUTC(from)) / 86400000);

function headingDate(iso) {
  const [y, m, d] = isoParts(iso);
  return `${DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]} ${d} ${MONTHS[m - 1]}`;
}

function buildDigest(rows, { now, maxPerPerson, title }) {
  const open = rows.filter((r) => r.Status !== "Completed");
  const isLate = (r) => r["Due Date"] && r["Due Date"] < now;

  const groups = new Map();
  for (const row of open) {
    const email = ((row["Assigned to"] || [])[0] || {}).email || "";
    const name = personName(email);
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(row);
  }

  // Alphabetical, not most-overdue-first: a daily post that reorders people by
  // how far behind they are turns a status update into a leaderboard.
  const names = [...groups.keys()].sort((a, b) => a.localeCompare(b));

  const overdueTotal = open.filter(isLate).length;
  const lines = [
    `## ${title} — ${headingDate(now)}`,
    `**${open.length} open · ${overdueTotal} overdue**`,
  ];

  for (const name of names) {
    const tasks = sortByDue(groups.get(name));
    const late = tasks.filter(isLate).length;
    lines.push("", `**${name}** — ${tasks.length} open${late ? `, ${late} overdue` : ""}`);
    for (const row of tasks.slice(0, maxPerPerson)) {
      const due = row["Due Date"]
        ? `${shortDate(row["Due Date"])}${isLate(row) ? ` (${daysBetween(row["Due Date"], now)}d late)` : ""}`
        : "no date";
      lines.push(`${isLate(row) ? "🔴" : "·"} ${row["Task Name"].trim()} — ${due}`);
    }
    const hidden = tasks.length - maxPerPerson;
    if (hidden > 0) lines.push(`  …and ${hidden} more`);
  }

  if (!open.length) lines.push("", "Nothing open. 🎉");
  // A bare URL in angle brackets renders as a plain clickable link with no
  // embed card. Masked [text](url) links are not reliably rendered in message
  // content, and a link preview card under a daily digest is pure noise.
  lines.push("", `<${TABLE_URL}>`);
  return lines.join("\n");
}

async function cmdDigest(env, args) {
  const rows = await fetchRows(env);
  const now = today();
  const title = args.title || "Standup";
  let maxPerPerson = args.maxPerPerson ? Number(args.maxPerPerson) : 6;
  if (!Number.isInteger(maxPerPerson) || maxPerPerson < 1) throw new Error("--max-per-person wants a positive integer");

  // Discord splits anything over 2000 chars, and a standup spanning two
  // messages has already stopped being scannable. Tighten the per-person cap
  // until it fits rather than letting the chunker decide where to cut.
  let text = buildDigest(rows, { now, maxPerPerson, title });
  while (text.length > DISCORD_MESSAGE_LIMIT && maxPerPerson > 1) {
    maxPerPerson -= 1;
    text = buildDigest(rows, { now, maxPerPerson, title });
  }
  console.log(text);
  if (text.length > DISCORD_MESSAGE_LIMIT) {
    console.error(`warning: ${text.length} chars even at 1 task per person; Discord will split this.`);
  }
}

async function cmdAdd(env, args) {
  if (args.name === undefined || !String(args.name).trim()) {
    throw new Error("--name is required to add a task");
  }
  // Reuse the edit validators (dates, hours, status) so add and set can't drift
  // apart on what they accept, then layer the create-only fields on top.
  const record = buildPatch(args);
  for (const [flag, column] of Object.entries(CREATE_ONLY_FIELD_TO_COLUMN)) {
    if (args[flag] === undefined) continue;
    if (flag === "who" && !String(args[flag]).includes("@")) {
      throw new Error(`--who wants an email address, got: ${args[flag]}`);
    }
    record[column] = args[flag];
  }

  const result = { ok: true, dryRun: !args.apply, willCreate: record };

  if (args.apply) {
    const created = await gatewayFetch(env, { method: "POST", key: env.writeKey, body: record });
    // NocoDB answers a create with [{ Id }] and nothing else, so the new row
    // has to be read back before anything can be said about what was stored.
    const id = Array.isArray(created) ? created[0]?.Id : created?.Id;
    if (!Number.isInteger(id)) throw new Error(`Create returned no Id: ${JSON.stringify(created).slice(0, 200)}`);

    const after = await fetchRow(env, id);
    const mismatched = Object.entries(record).filter(([column, want]) => {
      // `Assigned to` goes in as an email and comes back as an array of user
      // objects, so compare on what was actually asked for: the address.
      if (column === "Assigned to") {
        return !(after[column] || []).some((u) => (u.email || "").toLowerCase() === String(want).toLowerCase());
      }
      return String(after[column] ?? "") !== String(want ?? "");
    });
    if (mismatched.length) {
      throw new Error(
        `Created row ${id} but these did not stick: ${mismatched.map(([c, want]) => `${c} (wanted ${JSON.stringify(want)}, saved ${JSON.stringify(after[c] ?? null)})`).join("; ")}. Inspect: ${rowUrl(id)}`,
      );
    }
    result.Id = id;
    result.verified = true;
    result.url = rowUrl(id);
  }

  console.log(JSON.stringify(result, null, 2));
}

async function cmdSet(env, args) {
  const id = args._[1];
  if (!/^\d+$/.test(String(id || ""))) usage();
  const patch = buildPatch(args);
  if (!Object.keys(patch).length) throw new Error("No edit fields provided");

  const before = await fetchRow(env, Number(id));
  const changes = Object.entries(patch)
    .map(([column, after]) => ({ column, before: before[column] ?? null, after }))
    .filter((c) => String(c.before ?? "") !== String(c.after ?? ""));

  if (!changes.length) throw new Error("Requested edit would not change anything");

  const result = {
    ok: true,
    dryRun: !args.apply,
    Id: Number(id),
    taskName: before["Task Name"],
    changes,
    url: rowUrl(Number(id)),
  };

  if (args.apply) {
    // Minimal changed-field patch only: the route is last-write-wins, so
    // sending a full row snapshot would restore stale values for anything
    // edited elsewhere since this read.
    await gatewayFetch(env, { method: "PATCH", key: env.writeKey, body: { Id: Number(id), ...patch } });

    // A 2xx is not proof the values landed -- read back and compare.
    const after = await fetchRow(env, Number(id));
    const mismatched = Object.entries(patch).filter(
      ([column, want]) => String(after[column] ?? "") !== String(want ?? ""),
    );
    if (mismatched.length) {
      throw new Error(
        `Edit did not stick for: ${mismatched.map(([c, want]) => `${c} (wanted ${JSON.stringify(want)}, saved ${JSON.stringify(after[c] ?? null)})`).join("; ")}. Not retrying. Inspect: ${rowUrl(Number(id))}`,
      );
    }
    result.verified = true;
    result.updatedAt = after.UpdatedAt;
  }

  console.log(JSON.stringify(result, null, 2));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const command = args._[0] || "list";
  const env = resolveEnv(args);
  if (command === "list") return cmdList(env, args);
  if (command === "show") return cmdShow(env, args);
  if (command === "set") return cmdSet(env, args);
  if (command === "add") return cmdAdd(env, args);
  if (command === "digest") return cmdDigest(env, args);
  usage();
}

main().catch((err) => {
  console.error(JSON.stringify({ ok: false, error: err.message }, null, 2));
  process.exit(1);
});
