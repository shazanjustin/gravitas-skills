#!/usr/bin/env node
/**
 * competitor-report.mjs -- one-shot competitor analytics pull -> Google Sheet.
 *
 * Exists because doing this conversationally costs ~33 sequential tool calls,
 * and pi's turn budget (AI_TIMEOUT_MS, 280s) runs out before the write lands.
 * The API work itself takes under a second; the cost was model round-trips.
 * This collapses all of them into one call.
 *
 * Usage:
 *   node competitor-report.mjs --brand "CIMB Malaysia" \
 *     --competitors "Maybank,RHB Group" --from 2026-01-01 --to 2026-06-30
 *
 *   --brand <name>          brand to read competitors from (substring match)
 *   --competitors <a,b>     competitor screen names (substring match, per network)
 *   --from / --to           YYYY-MM-DD, inclusive
 *   --networks <list>       default facebook,instagram,youtube
 *   --tz <zone>             default Asia/Kuala_Lumpur -- affects output timestamps
 *   --sheet <id>            append into an existing spreadsheet instead of creating one
 *   --title <text>          title for a newly created spreadsheet
 *   --folder <driveId>      Drive folder for a newly created spreadsheet (default: root)
 *   --json <path>           also dump the shaped data to disk
 *   --dry-run               fetch and summarise, write nothing
 *
 * Metricool quirks worth keeping (each one cost a round-trip to discover):
 *   - competitor endpoints require from, to, timezone AND limit, or they 400.
 *   - `competitors[]` on the collection endpoints is quietly ignored, so this
 *     uses the per-competitor path instead: /{network}/{competitorId}/{kind}
 *   - responses are stamped with Metricool's own account timezone whatever the
 *     timezone param says, so every timestamp here is derived from epoch ms.
 */

const API = "https://app.metricool.com/api";
const DEFAULT_USER_ID = "4327762";

// -- args ----------------------------------------------------------
function parseArgs(argv) {
  const out = { networks: "facebook,instagram,youtube", tz: "Asia/Kuala_Lumpur" };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const key = a.slice(2);
    if (key === "dry-run") { out.dryRun = true; continue; }
    out[key] = argv[++i];
  }
  return out;
}

function die(msg) { console.error(`error: ${msg}`); process.exit(1); }

// -- auth ----------------------------------------------------------
async function metricoolToken() {
  if (process.env.METRICOOL_TOKEN) return process.env.METRICOOL_TOKEN;
  const url = process.env.GRAVITAS_GATEWAY_URL || "https://gateway.shazan.me";
  const key = process.env.GRAVITAS_GATEWAY_KEY;
  if (!key) die("no METRICOOL_TOKEN and no GRAVITAS_GATEWAY_KEY to fetch one with");
  const r = await fetch(`${url}/secret/METRICOOL_TOKEN`, { headers: { "x-api-key": key } });
  if (!r.ok) die(`gateway returned ${r.status} fetching METRICOOL_TOKEN`);
  const j = await r.json();
  if (!j.value) die("gateway response had no .value");
  return j.value;
}

// -- metricool -----------------------------------------------------
function makeClient(token, blogId) {
  const userId = process.env.METRICOOL_USER_ID || DEFAULT_USER_ID;
  return async function get(path, params = {}) {
    const qs = new URLSearchParams({ userId, userToken: token, ...params });
    if (blogId) qs.set("blogId", blogId);
    const r = await fetch(`${API}${path}?${qs}`);
    const text = await r.text();
    let j;
    try { j = JSON.parse(text); } catch { die(`${path} returned non-JSON: ${text.slice(0, 200)}`); }
    if (j.status && j.code && Number(j.code) >= 400) {
      die(`${path} -> ${j.code} ${JSON.stringify(j.detail || j.title)}`);
    }
    return j.data ?? j;
  };
}

const windowParams = (from, to, tz) => ({
  from: `${from}T00:00:00`,
  to: `${to}T23:59:59`,
  timezone: tz,
  limit: "1000",
});

// -- shaping -------------------------------------------------------
function fmt(ms, tz) {
  // Epoch is the only trustworthy field; Metricool renders dateTime in its own zone.
  const p = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(new Date(ms)).reduce((a, x) => (a[x.type] = x.value, a), {});
  return [`${p.year}-${p.month}-${p.day}`, `${p.hour}:${p.minute}`];
}

const clean = (s, n = 500) => s == null ? "" : String(s).replace(/\s+/g, " ").trim().slice(0, n);
const pct = (v) => Math.round((v || 0) * 100 * 1e4) / 1e4;
const round1 = (v) => Math.round(v * 10) / 10;

function buildTabs(pulls, tz) {
  const fb = [["Brand", "Date", "Time", "Reactions", "Comments", "Shares", "Total Interactions", "Engagement %", "Post Text", "Link"]];
  const igHeader = () => [["Brand", "Date", "Time", "Likes", "Comments", "Interactions", "Engagement %", "Caption", "URL"]];
  const igPosts = igHeader(), igReels = igHeader();
  const yt = [["Brand", "Date", "Time", "Views", "Likes", "Comments", "Title", "Watch URL"]];

  for (const { brand, network, kind, rows } of pulls) {
    for (const p of rows) {
      if (network === "facebook") {
        const [d, t] = fmt(p.created, tz);
        const r = p.reactions || 0, c = p.comments || 0, s = p.shares || 0;
        fb.push([brand, d, t, r, c, s, r + c + s, pct(p.engagement), clean(p.text), p.link || ""]);
      } else if (network === "instagram") {
        const [d, t] = fmt(p.timestamp, tz);
        const l = p.likes || 0, c = p.comments || 0;
        (kind === "reels" ? igReels : igPosts)
          .push([brand, d, t, l, c, p.interactions ?? l + c, pct(p.engagement), clean(p.content), p.url || ""]);
      } else if (network === "youtube") {
        const [d, t] = fmt(p.publishedAt, tz);
        yt.push([brand, d, t, p.views ?? "", p.likes ?? "", p.comments ?? "", clean(p.title, 300), p.watchUrl || ""]);
      }
    }
  }

  const tabs = {};
  if (fb.length > 1) tabs["FB Posts"] = fb;
  if (igPosts.length > 1) tabs["IG Posts"] = igPosts;
  if (igReels.length > 1) tabs["IG Reels"] = igReels;
  if (yt.length > 1) tabs["YT Posts"] = yt;
  return tabs;
}

function buildSummary(tabs, meta, followers) {
  const rows = [
    [`${meta.brand} competitors -- ${meta.competitors.join(" & ")} -- ${meta.from} to ${meta.to}`],
    [`Source: Metricool competitor analytics - blogId ${meta.blogId} - timestamps in ${meta.tz}`],
    [`Generated ${new Date().toISOString()}`],
    [""],
    ["Network", "Brand", "Followers", "Posts", "Total Interactions", "Avg Interactions/Post", "Avg Eng. Rate %", "Best Post", "Best Post Link"],
  ];

  const block = (tab, label, iCol, eCol) => {
    if (!tabs[tab]) return;
    for (const brand of meta.competitors) {
      const rs = tabs[tab].slice(1).filter((r) => r[0] === brand);
      if (!rs.length) continue;
      const total = rs.reduce((a, r) => a + (r[iCol] || 0), 0);
      const eng = rs.reduce((a, r) => a + (r[eCol] || 0), 0) / rs.length;
      const best = rs.reduce((a, r) => ((r[iCol] || 0) > (a[iCol] || 0) ? r : a));
      rows.push([label, brand, followers[`${brand}|${tab}`] ?? "", rs.length, total,
        round1(total / rs.length), Math.round(eng * 1e4) / 1e4, best[iCol], best[best.length - 1]]);
    }
  };

  block("FB Posts", "Facebook", 6, 7);
  block("IG Posts", "Instagram", 5, 6);
  block("IG Reels", "Instagram Reels", 5, 6);

  if (tabs["YT Posts"]) {
    rows.push([""]);
    rows.push(["Network", "Brand", "Subscribers", "Videos", "Total Views", "Avg Views/Video", "Total Likes", "Most-viewed Video", "Watch URL"]);
    for (const brand of meta.competitors) {
      const rs = tabs["YT Posts"].slice(1).filter((r) => r[0] === brand);
      if (!rs.length) continue;
      const views = rs.reduce((a, r) => a + (Number(r[3]) || 0), 0);
      const likes = rs.reduce((a, r) => a + (Number(r[4]) || 0), 0);
      const best = rs.reduce((a, r) => ((Number(r[3]) || 0) > (Number(a[3]) || 0) ? r : a));
      rows.push(["YouTube", brand, followers[`${brand}|YT Posts`] ?? "", rs.length, views,
        round1(views / rs.length), likes, clean(best[6], 80), best[7]]);
    }
  }

  rows.push([""]);
  rows.push(["Notes"]);
  rows.push(["Engagement % is Metricool per-post engagement rate averaged over the period, not total interactions / followers."]);
  rows.push(["Instagram posts and Reels are separate Metricool datasets and are counted separately."]);
  rows.push(["YouTube competitor data exposes no engagement rate and no comment counts; views and likes are used instead."]);
  rows.push([`Timestamps are converted from epoch to ${meta.tz}, so a post near midnight can fall a day outside the requested window.`]);
  return rows;
}

// -- composio / sheets ---------------------------------------------
async function composio(name, args) {
  const url = process.env.COMPOSIO_MCP_URL, key = process.env.COMPOSIO_API_KEY;
  if (!url || !key) die("COMPOSIO_MCP_URL / COMPOSIO_API_KEY not set -- cannot write a sheet (try --dry-run)");
  const r = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Both required: a missing Accept gives -32000, a missing key gives 401.
      "Accept": "application/json, text/event-stream",
      "x-api-key": key,
    },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
  });
  const text = await r.text();
  const line = text.split(/\r?\n/).find((l) => l.startsWith("data: "));
  if (!line) die(`composio returned no SSE frame (status ${r.status}): ${text.slice(0, 200)}`);
  const payload = JSON.parse(line.slice(6));
  const inner = payload.result?.content?.[0]?.text;
  if (!inner) die(`composio ${name} returned no content: ${JSON.stringify(payload).slice(0, 300)}`);
  const j = JSON.parse(inner);
  if (j.successful !== true) die(`composio ${name} failed: ${JSON.stringify(j.error || j).slice(0, 300)}`);
  return j.data;
}

async function writeSheet(all, opts) {
  let sheetId = opts.sheet;
  const fresh = !sheetId;
  if (fresh) {
    const created = await composio("GOOGLESHEETS_CREATE_GOOGLE_SHEET1", {
      title: opts.title,
      ...(opts.folder ? { folder_id: opts.folder } : {}),
    });
    sheetId = created.spreadsheetId || created.spreadsheet_id || created.id;
    if (!sheetId) die(`no spreadsheetId in create response: ${JSON.stringify(created).slice(0, 300)}`);
  }

  const info = await composio("GOOGLESHEETS_GET_SPREADSHEET_INFO", { spreadsheet_id: sheetId });
  const before = (info.sheets || []).map((s) => s.properties);
  const existing = new Set(before.map((p) => p.title));

  for (const [tab, rows] of Object.entries(all)) {
    if (!existing.has(tab)) await composio("GOOGLESHEETS_ADD_SHEET", { spreadsheet_id: sheetId, title: tab });
    // Append rather than update: it grows the grid, so the default 100-row
    // tab does not have to be resized first. 150 keeps payloads well under
    // the request size ceiling.
    for (let i = 0; i < rows.length; i += 150) {
      await composio("GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND", {
        spreadsheetId: sheetId,
        range: `${tab}!A:Z`,
        values: rows.slice(i, i + 150),
        valueInputOption: "RAW",
        insertDataOption: "INSERT_ROWS",
        majorDimension: "ROWS",
      });
    }
    console.log(`  wrote ${tab}: ${rows.length - 1} rows`);
  }

  // A newly created spreadsheet arrives with an empty default tab that none of
  // our data lands in. Drop it so the report opens on Summary.
  if (fresh) {
    const stray = before.find((p) => !all[p.title]);
    if (stray) await composio("GOOGLESHEETS_DELETE_SHEET", { spreadsheetId: sheetId, sheetId: stray.sheetId });
  }
  return sheetId;
}

// -- main ----------------------------------------------------------
const args = parseArgs(process.argv.slice(2));
for (const req of ["brand", "competitors", "from", "to"]) {
  if (!args[req]) die(`--${req} is required`);
}
const wanted = args.competitors.split(",").map((s) => s.trim()).filter(Boolean);
const networks = args.networks.split(",").map((s) => s.trim()).filter(Boolean);

const token = await metricoolToken();
const profiles = await makeClient(token, null)("/admin/simpleProfiles");
const list = Array.isArray(profiles) ? profiles : profiles.brands || [];
const named = (b) => b.label || b.title || b.name || "";
const matches = list.filter((b) => named(b).toLowerCase().includes(args.brand.toLowerCase()));
if (matches.length !== 1) {
  die(`--brand "${args.brand}" matched ${matches.length} of: ${list.map(named).join(", ")}`);
}
const blogId = String(matches[0].id || matches[0].blogId);
console.log(`brand: ${named(matches[0])} (blogId ${blogId})`);

const api = makeClient(token, blogId);
const win = windowParams(args.from, args.to, args.tz);

// Resolve competitor ids per network, then fan out every pull at once.
// The parallel fan-out is the whole point of this script.
const jobs = [];
const followers = {};
for (const network of networks) {
  const comps = await api(`/v2/analytics/competitors/${network}`, win);
  for (const want of wanted) {
    const needle = want.toLowerCase().split(" ")[0];
    const hit = (comps || []).find((c) => (c.screenName || "").toLowerCase().includes(needle));
    if (!hit) { console.warn(`  ! ${want} is not tracked on ${network} -- skipping`); continue; }
    const tab = network === "facebook" ? "FB Posts" : network === "youtube" ? "YT Posts" : "IG Posts";
    followers[`${want}|${tab}`] = hit.followers ?? "";
    jobs.push({ brand: want, network, kind: "posts", id: hit.id });
    if (network === "instagram") jobs.push({ brand: want, network, kind: "reels", id: hit.id });
  }
}
if (!jobs.length) die("no competitors resolved on any requested network");

const t0 = Date.now();
const pulls = await Promise.all(jobs.map(async (j) => ({
  ...j,
  rows: (await api(`/v2/analytics/competitors/${j.network}/${j.id}/${j.kind}`, win)) || [],
})));
const records = pulls.reduce((a, p) => a + p.rows.length, 0);
console.log(`pulled ${pulls.length} datasets, ${records} records in ${Date.now() - t0}ms`);

const tabs = buildTabs(pulls, args.tz);
const meta = { brand: named(matches[0]), competitors: wanted, from: args.from, to: args.to, tz: args.tz, blogId };
const all = { Summary: buildSummary(tabs, meta, followers), ...tabs };

if (args.json) {
  const { writeFileSync } = await import("node:fs");
  writeFileSync(args.json, JSON.stringify({ meta, tabs: all }, null, 2));
  console.log(`dump: ${args.json}`);
}

for (const [tab, rows] of Object.entries(tabs)) console.log(`  ${tab}: ${rows.length - 1} rows`);

if (args.dryRun) {
  console.log("\n--dry-run, nothing written. Summary preview:");
  for (const r of all.Summary.slice(4, 12)) console.log("   ", JSON.stringify(r));
  process.exit(0);
}

const title = args.title || `${meta.brand} competitors -- ${wanted.join(" & ")} ${args.from} to ${args.to}`;
const sheetId = await writeSheet(all, { sheet: args.sheet, title, folder: args.folder });
console.log(`\nhttps://docs.google.com/spreadsheets/d/${sheetId}/edit`);
