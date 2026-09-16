#!/usr/bin/env node

// List and add members of the NocoDB "Central" base through the Gravitas
// gateway.
//
// Why this exists rather than the curl snippets in SKILL.md: adding a person
// is a two-part job and only the first part is the HTTP call. The second is
// getting the signup link into their hands, because the instance's invite mail
// never arrives -- a bare curl leaves that link buried in a JSON blob that is
// easy to skim past, and the person then cannot get in. `add` makes the link
// the loudest thing on screen and says who to send it to.
//
// It is also dry-run by default, for the same reason perf.mjs is: there is no
// delete path on the other side, so a wrong invite is cleaned up by hand.

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const ROUTE = "/nocodb/base-user";
const DEFAULT_ENV_FILE = join(homedir(), ".gravitas-skills", ".env");

// Where a human goes to manage this by hand -- removals, role changes and
// re-issuing a lost invite all live here, and none of them are reachable
// through the gateway route on purpose.
const BASE_URL = "https://ozy.gravitas.my/wxnfngze/pboui1exiw4lryy";

function usage(exitCode = 1) {
  console.error(`Usage:
  node member.mjs list [--json]
  node member.mjs add <email> [--apply]

Adds one @gravitas.my address to the Central base as an editor. Dry-run
unless --apply. Cannot remove anyone or grant any other role -- do that in
NocoDB: ${BASE_URL}`);
  process.exit(exitCode);
}

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
    adminKey: pick("GRAVITAS_GATEWAY_ADMIN_KEY"),
  };
}

async function gatewayFetch(env, { method = "GET", body } = {}) {
  if (!env.adminKey) {
    throw new Error(
      "GRAVITAS_GATEWAY_ADMIN_KEY is not set. Membership needs the admin key -- " +
        "it is a third key, and neither the read nor the write key works here.",
    );
  }
  const headers = { "x-api-key": env.adminKey };
  if (body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${env.url}${ROUTE}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  let parsed = null;
  try {
    parsed = raw ? JSON.parse(raw) : {};
  } catch {
    throw new Error(`gateway returned non-JSON: ${raw.slice(0, 200)}`);
  }
  if (!res.ok) {
    const err = new Error(`gateway ${method} ${res.status}: ${raw.slice(0, 300)}`);
    err.status = res.status;
    err.body = parsed;
    throw err;
  }
  return parsed;
}

function parseArgs(argv) {
  const args = { _: [], apply: false, json: false, envFile: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--apply") args.apply = true;
    else if (a === "--json") args.json = true;
    else if (a === "--env-file") args.envFile = argv[++i];
    else if (a === "-h" || a === "--help") usage(0);
    else if (a.startsWith("--")) usage();
    else args._.push(a);
  }
  return args;
}

async function listMembers(env, args) {
  const data = await gatewayFetch(env);
  const members = data.members || [];
  if (args.json) {
    console.log(JSON.stringify(members, null, 2));
    return;
  }
  const width = Math.max(5, ...members.map((m) => m.email.length));
  console.log(`Central base — ${members.length} member${members.length === 1 ? "" : "s"}`);
  for (const m of [...members].sort((a, b) => a.email.localeCompare(b.email))) {
    const state = m.pendingInvite ? "invite pending" : "active";
    console.log(`  ${m.email.padEnd(width)}  ${String(m.roles).padEnd(8)}  ${state}`);
  }
  const pending = members.filter((m) => m.pendingInvite).length;
  if (pending) {
    console.log(`\n${pending} invite${pending === 1 ? "" : "s"} never accepted — those people cannot sign in yet.`);
  }
  console.log(`\n${BASE_URL}`);
}

async function addMember(env, args) {
  const email = (args._[1] || "").trim().toLowerCase();
  if (!email) usage();

  // Checked here as well as at the gateway so a typo costs a local error
  // rather than a round trip -- the gateway is still the enforcing side.
  if (!/^[^\s@]+@gravitas\.my$/.test(email)) {
    console.error(`Refused: "${email}" is not a @gravitas.my address.`);
    console.error("Only Gravitas addresses can be added to Central.");
    process.exit(1);
  }

  const existing = (await gatewayFetch(env)).members?.find(
    (m) => m.email.toLowerCase() === email,
  );
  if (existing) {
    const state = existing.pendingInvite
      ? "already invited (invite not yet accepted)"
      : "already an active member";
    console.log(`${email} is ${state} — nothing to do.`);
    if (existing.pendingInvite) {
      console.log(
        "\nRe-inviting would mint a new link and invalidate the one they may already have.\n" +
          `If they lost it, re-issue it by hand: ${BASE_URL}`,
      );
    }
    return;
  }

  if (!args.apply) {
    console.log("DRY RUN — nothing sent. Re-run with --apply to do it.\n");
    console.log(`  add    ${email}`);
    console.log("  to     Central base");
    console.log("  as     editor");
    console.log("\nOn --apply this creates their NocoDB account and returns a signup link.");
    return;
  }

  const result = await gatewayFetch(env, { method: "POST", body: { email } });

  console.log(`Added ${result.user.email} to Central as ${result.user.roles}.`);
  if (!result.inviteUrl) {
    console.log(
      "\nWARNING: no signup link was issued, so they cannot sign in yet.\n" +
        `Re-issue the invite by hand: ${BASE_URL}`,
    );
    process.exitCode = 1;
    return;
  }
  console.log("\nSend them this link — it is the only way in, the invite email does not arrive:\n");
  console.log(`  ${result.inviteUrl}\n`);
  console.log("Send it to them directly. It claims the account, so treat it like a password,");
  console.log("and do not post it in a shared channel.");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0];
  if (!cmd) usage();
  const env = resolveEnv(args);

  try {
    if (cmd === "list") await listMembers(env, args);
    else if (cmd === "add") await addMember(env, args);
    else usage();
  } catch (e) {
    // The gateway's own error names are more useful than a stack trace.
    if (e.status === 409) console.error(`Refused: ${e.body?.error} — already a member.`);
    else if (e.status === 400) console.error(`Refused: ${e.body?.error}`);
    else if (e.status === 502 && e.body?.error === "invite_failed") {
      console.error(
        "The invite did not land. This is a real failure, not the usual timeout —\n" +
          "the gateway re-read the member list and they are not there.",
      );
    } else console.error(e.message);
    process.exit(1);
  }
}

main();
