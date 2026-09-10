#!/usr/bin/env node
// Read the Gravitas Gateway key back out of the OS credential store.
//
//   node scripts/get-key.mjs           print the key to stdout
//   node scripts/get-key.mjs --check   print only whether one is stored
//
// Prints nothing and exits 1 when no key is stored, so it composes:
//
//   KEY=$(node scripts/get-key.mjs) || echo "run scripts/set-key.mjs first"
//
// Use --check in anything an agent will see. The plain form writes the secret
// to stdout, which is correct for command substitution and wrong for a
// transcript, so never let an agent run the plain form and read the output.

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir, platform } from "node:os";
import { join } from "node:path";

const SERVICE = "gravitas-gateway-key";
const ACCOUNT = "gravitas";
const FALLBACK_DIR = join(homedir(), ".config", "gravitas-skills");
const FALLBACK_FILE = join(FALLBACK_DIR, "gateway-key");
const DPAPI_FILE = FALLBACK_FILE + ".dpapi";

function fromStore() {
  const plat = platform();

  if (plat === "win32" && existsSync(DPAPI_FILE)) {
    const ps = [
      "$ErrorActionPreference='Stop'",
      `$s = Get-Content -Path '${DPAPI_FILE.replace(/'/g, "''")}' | ConvertTo-SecureString`,
      "$b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)",
      "[Runtime.InteropServices.Marshal]::PtrToStringAuto($b)",
    ].join("; ");
    const r = spawnSync("powershell", ["-NoProfile", "-NonInteractive", "-Command", ps], {
      encoding: "utf8",
    });
    if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  }

  if (plat === "darwin") {
    const r = spawnSync("security", ["find-generic-password", "-a", ACCOUNT, "-s", SERVICE, "-w"], {
      encoding: "utf8",
    });
    if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  }

  if (plat === "linux") {
    const r = spawnSync("secret-tool", ["lookup", "service", SERVICE, "account", ACCOUNT], {
      encoding: "utf8",
    });
    if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  }

  if (existsSync(FALLBACK_FILE)) {
    const v = readFileSync(FALLBACK_FILE, "utf8").trim();
    if (v) return v;
  }

  return null;
}

// The environment still wins. Cloud sessions and CI set it directly, and an
// explicit export should always beat a stored value.
const key = (process.env.GRAVITAS_GATEWAY_KEY || "").trim() || fromStore();

if (process.argv.includes("--check")) {
  if (key) {
    const source = process.env.GRAVITAS_GATEWAY_KEY ? "environment" : "OS credential store";
    console.log(`A gateway key is stored (source: ${source}, ${key.length} characters).`);
    process.exit(0);
  }
  console.log("No gateway key stored. Run: node scripts/set-key.mjs");
  process.exit(1);
}

if (!key) process.exit(1);
process.stdout.write(key);
