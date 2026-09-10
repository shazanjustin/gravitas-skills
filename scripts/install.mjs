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

if (installed.length) {
  console.log("\nNext, the gateway key. One command covers every agent:\n");
  console.log("  node scripts/set-key.mjs\n");
  console.log("It prompts with the input hidden and stores the key encrypted in your OS");
  console.log("credential store. Never paste a key into a chat prompt: that sends it to");
  console.log("the model provider and writes it to the agent's transcript, and deleting");
  console.log("the session afterwards undoes neither.");
}
console.log("\nThen restart each agent.");
