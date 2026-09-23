#!/usr/bin/env node
// Pick the Apify token to spend, in the gateway's order.
//
//   node scripts/apify-key.mjs            print the first token with credit left to stdout
//   node scripts/apify-key.mjs --status   print every account's balance, no tokens
//   node scripts/apify-key.mjs --min-usd 2   need at least $2 of headroom (default 0.50)
//
// The gateway dispenses APIFY_API_KEY, then APIFY_API_KEY_2, APIFY_API_KEY_3,
// and so on, in the order they should be spent. This walks that list and
// returns the first account whose monthly cap still has room, so a skill that
// used to fetch APIFY_API_KEY directly now moves on by itself when that
// account runs dry. Which account was chosen goes to stderr, never the token.
//
// Like get-key.mjs, the plain form writes a secret to stdout for command
// substitution. Never let an agent run it and read the output into context:
//
//   APIFY_TOKEN=$(node scripts/apify-key.mjs) || echo "every Apify account is out of credit"

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const status = args.includes("--status");
const minIdx = args.indexOf("--min-usd");
const minUsd = minIdx >= 0 ? Number(args[minIdx + 1]) : 0.5;

function gatewayKey() {
  const env = (process.env.GRAVITAS_GATEWAY_KEY || "").trim();
  if (env && !env.includes("user_config")) return env;
  const r = spawnSync(process.execPath, [join(here, "get-key.mjs")], { encoding: "utf8" });
  if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  // Last resort, as the Python scripts do. This file has been seen with CRLF endings.
  const legacy = join(homedir(), ".gravitas-skills", ".env");
  if (existsSync(legacy)) {
    const m = readFileSync(legacy, "utf8").match(/^\s*GRAVITAS_GATEWAY_KEY\s*=\s*['"]?([^'"\r\n]+)/m);
    if (m) return m[1].trim();
  }
  return "";
}

const base = ((process.env.GRAVITAS_GATEWAY_URL || "").includes("user_config") ? "" : process.env.GRAVITAS_GATEWAY_URL || "https://gateway.shazan.me").replace(/\/+$/, "");
const key = gatewayKey();
if (!key) {
  console.error("No Gravitas Gateway key. Run: node scripts/set-key.mjs");
  process.exit(1);
}

async function json(url, headers) {
  // Cloudflare rejects default library user agents on the gateway (error 1010).
  const r = await fetch(url, { headers: { "User-Agent": "curl/8.4.0", ...headers }, signal: AbortSignal.timeout(20_000) });
  if (!r.ok) throw new Error(`${new URL(url).host} returned ${r.status}`);
  return r.json();
}
const gw = (path) => json(base + path, { "x-api-key": key });

const names = ((await gw("/secrets")).secrets || []).filter((n) => /^APIFY_API_KEY(_\d+)?$/.test(n));
if (!names.length) {
  console.error("The gateway has no APIFY_API_KEY configured.");
  process.exit(1);
}

const rows = [];
for (const name of names) {
  try {
    const token = String((await gw(`/secret/${name}`)).value || "").trim();
    const auth = { Authorization: `Bearer ${token}` };
    const [me, limits] = await Promise.all([
      json("https://api.apify.com/v2/users/me", auth),
      json("https://api.apify.com/v2/users/me/limits", auth),
    ]);
    const cap = limits.data?.limits?.maxMonthlyUsageUsd ?? 0;
    const used = limits.data?.current?.monthlyUsageUsd ?? 0;
    rows.push({
      name, token, user: me.data?.username || "?", plan: me.data?.plan?.id || "?",
      cap, used, left: cap - used, resets: (limits.data?.monthlyUsageCycle?.endAt || "").slice(0, 10),
    });
  } catch (e) {
    rows.push({ name, error: e.message });
  }
}

if (status) {
  for (const r of rows) {
    console.log(r.error
      ? `${r.name.padEnd(16)} error: ${r.error}`
      : `${r.name.padEnd(16)} ${r.user.padEnd(20)} ${r.plan.padEnd(8)} $${r.used.toFixed(2)} of $${r.cap} used, $${r.left.toFixed(2)} left, resets ${r.resets}`);
  }
  process.exit(0);
}

const pick = rows.find((r) => !r.error && r.left >= minUsd);
if (!pick) {
  console.error(`Every Apify account has less than $${minUsd} left this cycle:`);
  for (const r of rows) console.error(`  ${r.name}: ${r.error || `$${r.left.toFixed(2)} left, resets ${r.resets}`}`);
  process.exit(1);
}
const skipped = rows.slice(0, rows.indexOf(pick)).map((r) => r.name);
console.error(`Apify: using ${pick.name} (${pick.user}, $${pick.left.toFixed(2)} left)` +
  (skipped.length ? `; skipped ${skipped.join(", ")} (out of credit or unreachable)` : ""));
process.stdout.write(pick.token);
