#!/usr/bin/env node
// Apply Gravitas skills updates across every agent installed on this machine.
//
// Run it by hand when the session-start check tells you to, or wire it into a
// daily scheduled task for a hands-off setup. Each agent is skipped silently
// when its CLI is not on PATH, so the same command works on any machine.
//
// Claude Code is included even though it can update natively, because that only
// happens when auto-update is switched on for the marketplace, and third-party
// marketplaces have it off by default. One command should not depend on a
// setting you may never have flipped.

import { spawnSync } from "node:child_process";

const REPO_URL = "https://github.com/shazanjustin/gravitas-skills";

const STEPS = [
  {
    agent: "claude code",
    probe: ["claude", ["--version"]],
    run: [
      ["claude", ["plugin", "marketplace", "update", "gravitas-skills"]],
      ["claude", ["plugin", "update", "gravitas@gravitas-skills"]],
    ],
  },
  {
    agent: "codex",
    probe: ["codex", ["--version"]],
    run: [
      ["codex", ["plugin", "marketplace", "upgrade", "gravitas-skills"]],
      ["codex", ["plugin", "remove", "gravitas@gravitas-skills"]],
      ["codex", ["plugin", "add", "gravitas@gravitas-skills"]],
    ],
  },
  {
    agent: "pi",
    probe: ["pi", ["--version"]],
    run: [["pi", ["update", "--extension", REPO_URL]]],
  },
];

function run(cmd, args, { capture = false } = {}) {
  return spawnSync(cmd, args, {
    encoding: "utf8",
    shell: process.platform === "win32",
    stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
    windowsHide: true,
    timeout: 180000,
  });
}

let updated = 0;
let skipped = [];

for (const step of STEPS) {
  const [pc, pa] = step.probe;
  const probe = run(pc, pa, { capture: true });
  if (probe.error || probe.status !== 0) {
    skipped.push(step.agent);
    continue;
  }

  console.log(`\n== ${step.agent} ==`);
  let ok = true;
  for (const [cmd, args] of step.run) {
    const r = run(cmd, args);
    // `remove` fails harmlessly when the plugin was never installed; only the
    // final step of each agent decides success.
    if (r.error) ok = false;
  }
  if (ok) updated++;
}

console.log("");
if (updated) {
  console.log(`Updated ${updated} agent(s). Changes take effect in your next session.`);
}
if (skipped.length) {
  console.log(`Skipped (not installed): ${skipped.join(", ")}`);
}
console.log("Restart each agent to pick up the new version.");
