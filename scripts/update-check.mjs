#!/usr/bin/env node
// Throttled update check for the Gravitas skills.
//
// Runs at session start under Claude Code and Codex (hooks/hooks.json) and
// under pi (extensions/gravitas-update-check.js). At most one network call per
// day per machine: every other run reads a stamp file and exits in a few ms.
//
// It never applies the update itself. Mutating the plugin cache that the agent
// is in the middle of reading is a race nobody wants at session start, so this
// prints the one command to run instead. See scripts/update.mjs.
//
// Fails open, always. Offline, DNS down, git missing, unreadable stamp: exit 0
// and say nothing. A broken update check must never stop a session starting.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, basename } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = "https://github.com/shazanjustin/gravitas-skills.git";
const BRANCH = "main";
const INTERVAL_MS = 24 * 60 * 60 * 1000;
const NET_TIMEOUT_MS = 4000;

const STAMP = process.env.GRAVITAS_UPDATE_STAMP
  || join(homedir(), ".cache", "gravitas-skills", "update-check.json");

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);

function readStamp() {
  try {
    return JSON.parse(readFileSync(STAMP, "utf8"));
  } catch {
    return {};
  }
}

function writeStamp(data) {
  try {
    mkdirSync(dirname(STAMP), { recursive: true });
    writeFileSync(STAMP, JSON.stringify(data, null, 2) + "\n", "utf8");
  } catch {
    // A read-only home directory just means we check again next session.
  }
}

function git(args, cwd, timeout) {
  const r = spawnSync("git", args, {
    cwd,
    timeout,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
    windowsHide: true,
  });
  if (r.error || r.status !== 0) return null;
  return (r.stdout || "").trim();
}

// Which commit is this copy? Three layouts to cover, in order of reliability.
function installedSha() {
  // 1. A real checkout: pi clones the repo, and so does anyone developing here.
  let dir = ROOT;
  for (let i = 0; i < 4; i++) {
    if (existsSync(join(dir, ".git"))) {
      const sha = git(["rev-parse", "HEAD"], dir, 2000);
      if (sha) return sha;
      break;
    }
    const up = dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  // 2. A plugin cache keyed by version. With no `version` in plugin.json the
  //    version resolves to the commit SHA, so the directory name is the answer:
  //    .../plugins/cache/gravitas-skills/gravitas/<sha>/
  const name = basename(ROOT);
  if (/^[0-9a-f]{7,40}$/i.test(name)) return name;
  // 3. Give up on the local side; fall back to comparing against what we saw
  //    on the remote last time, which still catches "the repo moved".
  return null;
}

function shortSha(sha) {
  return sha ? sha.slice(0, 8) : "unknown";
}

// Each agent caches this copy somewhere deep in its own tree, and printing that
// absolute path is both ugly and longer than the command it replaces. We know
// which agent is running us from where we are, so print its own one-liner.
function updateCommand() {
  const p = ROOT.replace(/\\/g, "/");
  if (p.includes("/.claude/")) return "claude plugin update gravitas@gravitas-skills";
  if (p.includes("/.codex/")) return "codex plugin marketplace upgrade gravitas-skills";
  if (p.includes("/.pi/")) return `pi update --extension ${REPO.replace(/\.git$/, "")}`;
  // A dev checkout, or an agent we do not recognise: update everything.
  return `node "${join(ROOT, "scripts", "update.mjs")}"`;
}

function subjectsBetween(from, to) {
  let dir = ROOT;
  for (let i = 0; i < 4; i++) {
    if (existsSync(join(dir, ".git"))) {
      const out = git(["log", "--oneline", "--no-decorate", `${from}..${to}`], dir, 2000);
      if (out) return out.split("\n").slice(0, 5);
      break;
    }
    const up = dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  return [];
}

// The box stays a fixed, terminal-friendly width. An install path can run well
// past 80 characters, so the command goes underneath rather than inside, where
// it would either overflow the border or force it absurdly wide.
function box(lines, after, heading = "GRAVITAS SKILLS: UPDATE AVAILABLE") {
  const bar = "=".repeat(72);
  const out = [
    "",
    bar,
    "  " + heading,
    bar,
    ...lines.map((l) => (l ? "  " + l : "")),
    bar,
    ...after,
    "",
  ];
  process.stdout.write(out.join("\n") + "\n");
}

// Deliberately not throttled. A missing key is not news that goes stale: it
// blocks every gateway-backed skill, and the check is a local file read costing
// about a millisecond. Someone who installed without running install.mjs would
// otherwise discover this as a 401 in the middle of unrelated work.
function keyMissingNotice() {
  const r = spawnSync(process.execPath, [join(HERE, "get-key.mjs"), "--check"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
    timeout: 4000,
    windowsHide: true,
  });
  if (!r.error && r.status === 0) return false;

  box(
    [
      "No Gravitas Gateway key is set, so every skill that needs",
      "credentials will fail. Ask Shazan or your team lead for the key.",
      "",
      "Input stays hidden and the key is stored encrypted. Do not paste",
      "it into a chat: that sends it to the model provider and writes it",
      "to this session's transcript.",
    ],
    ["", "  Run:", `    node "${join(ROOT, "scripts", "set-key.mjs")}"`],
    "GRAVITAS SKILLS: NO GATEWAY KEY"
  );
  return true;
}

function main() {
  const now = Date.now();
  const stamp = readStamp();

  keyMissingNotice();

  if (process.argv.includes("--force")) {
    // fall through
  } else if (stamp.lastCheck && now - stamp.lastCheck < INTERVAL_MS) {
    return;
  }

  const out = git(["ls-remote", REPO, BRANCH], undefined, NET_TIMEOUT_MS);
  if (!out) {
    // Offline or git missing. Record the attempt so a flaky network does not
    // mean a probe on every single session start.
    writeStamp({ ...stamp, lastCheck: now });
    return;
  }

  const remote = out.split(/\s+/)[0];
  if (!/^[0-9a-f]{40}$/i.test(remote)) {
    writeStamp({ ...stamp, lastCheck: now });
    return;
  }

  const local = installedSha();
  const behind = local
    ? !remote.startsWith(local) && !local.startsWith(remote)
    : Boolean(stamp.lastSeenRemote) && stamp.lastSeenRemote !== remote;

  writeStamp({ ...stamp, lastCheck: now, lastSeenRemote: remote });

  if (!behind) return;

  const lines = [];
  lines.push(`Installed ${shortSha(local)}, ${BRANCH} is at ${shortSha(remote)}.`);

  const subjects = local ? subjectsBetween(local, remote) : [];
  if (subjects.length) {
    lines.push("");
    for (const s of subjects) lines.push("  " + s);
  }

  lines.push("");
  lines.push("Updating takes effect in your next session.");

  box(lines, ["", "  Run:", "    " + updateCommand()]);
}

try {
  main();
} catch {
  // Never let a broken check block a session.
}
