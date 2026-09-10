#!/usr/bin/env node
// Install the Gravitas skills into every agent on this machine.
//
// There is no shared registry between Claude Code, Codex and pi: each keeps its
// own install record and its own copy. Without this, a newcomer runs six
// commands and has to know which of the three they have. Here they run one, and
// whatever is not installed is skipped.
//
//   node scripts/install.mjs
//
// Safe to re-run. Each agent treats a second install as a no-op or an update.

import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

const MARKETPLACE = "shazanjustin/gravitas-skills";
const REPO_URL = "https://github.com/shazanjustin/gravitas-skills";

const AGENTS = [
  {
    name: "Claude Code",
    probe: "claude",
    steps: [
      ["claude", ["plugin", "marketplace", "add", MARKETPLACE]],
      ["claude", ["plugin", "install", "gravitas@gravitas-skills"]],
    ],
  },
  {
    name: "Codex",
    probe: "codex",
    steps: [
      ["codex", ["plugin", "marketplace", "add", MARKETPLACE]],
      ["codex", ["plugin", "add", "gravitas@gravitas-skills"]],
    ],
  },
  {
    name: "pi",
    probe: "pi",
    steps: [["pi", ["install", REPO_URL]]],
  },
];

function sh(cmd, args, capture = false) {
  return spawnSync(cmd, args, {
    encoding: "utf8",
    shell: process.platform === "win32",
    stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
    windowsHide: true,
    timeout: 180000,
  });
}

const installed = [];
const missing = [];

for (const agent of AGENTS) {
  const probe = sh(agent.probe, ["--version"], true);
  if (probe.error || probe.status !== 0) {
    missing.push(agent.name);
    continue;
  }

  console.log(`\n== ${agent.name} ==`);
  // A marketplace that is already added reports so and exits non-zero on some
  // agents, which is not a failure worth aborting the whole run for.
  for (const [cmd, args] of agent.steps) sh(cmd, args);
  installed.push(agent.name);
}

console.log("\n" + "=".repeat(72));
if (installed.length) {
  console.log(`Installed into: ${installed.join(", ")}`);
} else {
  console.log("No supported agent found on PATH.");
}
if (missing.length) {
  console.log(`Skipped (not installed): ${missing.join(", ")}`);
}
console.log("=".repeat(72));

// Ask for the key right here, while we still have the user's terminal.
//
// This is the only moment in the whole flow where a hidden prompt is possible:
// the user typed this command themselves, so stdin is a real TTY. Codex and pi
// have no install-time config prompt of their own, and telling someone to run a
// second command later means most people never do, then hit a confusing 401 in
// the middle of unrelated work.
if (installed.length) {
  const has = sh(process.execPath, [join(HERE, "get-key.mjs"), "--check"], true);
  if (has.status === 0) {
    console.log("\nA gateway key is already stored, so nothing else is needed.");
  } else if (process.stdin.isTTY) {
    console.log("\nOne thing left: the Gravitas Gateway key.");
    console.log("Ask Shazan or your team lead for it. Input stays hidden, and it is");
    console.log("stored encrypted in your OS credential store, never in a transcript.\n");
    const r = sh(process.execPath, [join(HERE, "set-key.mjs")]);
    if (r.status !== 0) {
      console.log("\nNo key stored. Run this when you have it:");
      console.log("  node scripts/set-key.mjs");
    }
  } else {
    // Piped, or run through an agent. An agent's shell-out is not a TTY either,
    // including Claude Code's `!` prefix, so "run it in your terminal" is
    // ambiguous exactly when it matters most. Name the terminal.
    console.log("\nOne thing left: the Gravitas Gateway key.");
    console.log("\nThis needs a real terminal window (PowerShell, Terminal, iTerm).");
    console.log("Running it through an agent lands you back here, because the prompt");
    console.log("reads your keystrokes directly rather than through a model:\n");
    console.log(`  node "${join(HERE, "set-key.mjs")}"`);
  }
}
console.log("\nThen restart each agent.");
