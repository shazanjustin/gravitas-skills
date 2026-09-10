#!/usr/bin/env node
// Store the Gravitas Gateway key without it ever passing through an agent.
//
//   node scripts/set-key.mjs              prompt with echo off
//   echo $KEY | node scripts/set-key.mjs --stdin
//
// Why this exists: a key typed into a chat prompt is sent to the model provider
// and written verbatim to that agent's history and transcript files before you
// could delete anything. Claude Code avoids this with a native config prompt
// that stores to the OS keychain. Codex and pi have no equivalent, so this
// takes the key straight from the keyboard to the OS credential store, with the
// model never in the loop.
//
// Storage, best available first:
//   Windows  DPAPI via PowerShell, encrypted to your Windows account
//   macOS    Keychain (security add-generic-password)
//   Linux    libsecret (secret-tool), i.e. GNOME Keyring / KWallet
//   fallback a 0600 file under ~/.config/gravitas-skills/
//
// Read it back with scripts/get-key.mjs.

import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, writeFileSync } from "node:fs";
import { homedir, platform } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";

const SERVICE = "gravitas-gateway-key";
const ACCOUNT = "gravitas";
const FALLBACK_DIR = join(homedir(), ".config", "gravitas-skills");
const FALLBACK_FILE = join(FALLBACK_DIR, "gateway-key");
const GATEWAY = process.env.GRAVITAS_GATEWAY_URL || "https://gateway.shazan.me";

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data.trim()));
  });
}

// Echo off, the way sudo and ssh-add do it, so the key never reaches the
// screen, the scrollback, or the shell history.
function promptHidden(question) {
  return new Promise((resolve, reject) => {
    if (!process.stdin.isTTY) {
      reject(new Error("Not a terminal. Pipe the key in with --stdin instead."));
      return;
    }
    const rl = createInterface({ input: process.stdin, output: process.stdout, terminal: true });
    const onData = () => {
      // Keep the prompt on screen, suppress everything typed after it.
      const len = rl.line.length;
      process.stdout.clearLine(0);
      process.stdout.cursorTo(0);
      process.stdout.write(question + "*".repeat(len));
    };
    process.stdout.write(question);
    process.stdin.on("data", onData);
    rl.question("", (answer) => {
      process.stdin.removeListener("data", onData);
      rl.close();
      process.stdout.write("\n");
      resolve(answer.trim());
    });
  });
}

// Pass the secret on stdin rather than argv wherever the tool allows it: argv is
// visible to anyone who can list processes.
function store(key) {
  const plat = platform();

  if (plat === "win32") {
    const ps = [
      "$ErrorActionPreference='Stop'",
      "$k = [Console]::In.ReadToEnd().Trim()",
      `$d = '${FALLBACK_DIR.replace(/'/g, "''")}'`,
      "New-Item -ItemType Directory -Force -Path $d | Out-Null",
      "ConvertTo-SecureString -String $k -AsPlainText -Force | ConvertFrom-SecureString |" +
        ` Set-Content -Path '${(FALLBACK_FILE + ".dpapi").replace(/'/g, "''")}' -Encoding ascii`,
    ].join("; ");
    const r = spawnSync("powershell", ["-NoProfile", "-NonInteractive", "-Command", ps], {
      input: key,
      encoding: "utf8",
    });
    if (r.status === 0) return "Windows DPAPI (encrypted to your Windows account)";
  }

  if (plat === "darwin") {
    const r = spawnSync(
      "security",
      ["add-generic-password", "-U", "-a", ACCOUNT, "-s", SERVICE, "-w", key],
      { encoding: "utf8" }
    );
    if (r.status === 0) return "macOS Keychain";
  }

  if (plat === "linux") {
    const r = spawnSync(
      "secret-tool",
      ["store", "--label=Gravitas Gateway key", "service", SERVICE, "account", ACCOUNT],
      { input: key, encoding: "utf8" }
    );
    if (r.status === 0) return "libsecret (GNOME Keyring / KWallet)";
  }

  mkdirSync(FALLBACK_DIR, { recursive: true });
  writeFileSync(FALLBACK_FILE, key + "\n", { encoding: "utf8", mode: 0o600 });
  try {
    chmodSync(FALLBACK_FILE, 0o600);
  } catch {}
  return `file ${FALLBACK_FILE} (mode 0600)`;
}

// A key that the gateway rejects is worse than no key: it fails later, somewhere
// unrelated. Check before storing.
async function verify(key) {
  try {
    const res = await fetch(`${GATEWAY}/secrets`, {
      headers: { "x-api-key": key, "User-Agent": "curl/8.4.0" },
      signal: AbortSignal.timeout(8000),
    });
    if (res.status === 401 || res.status === 403) return "rejected";
    if (!res.ok) return "unreachable";
    const body = await res.json();
    return Array.isArray(body?.secrets) ? "valid" : "unreachable";
  } catch {
    return "unreachable";
  }
}

const key = process.argv.includes("--stdin")
  ? await readStdin()
  : await promptHidden("Gravitas Gateway key (input hidden): ");

if (!key) {
  console.error("No key given. Nothing stored.");
  process.exit(1);
}

if (!process.argv.includes("--no-verify")) {
  const state = await verify(key);
  if (state === "rejected") {
    console.error(`\nThe gateway rejected that key (401). Nothing stored.`);
    console.error("Check you copied the whole thing, then try again.");
    process.exit(1);
  }
  if (state === "unreachable") {
    console.error(`\nCould not reach ${GATEWAY} to check the key. Storing it unverified.`);
  } else {
    console.log("\nGateway accepted the key.");
  }
}

const where = store(key);

console.log(`Stored in: ${where}`);
console.log("\nThe key was never sent to a model and is not in any transcript.");
console.log("Skills read it back automatically. To check:  node scripts/get-key.mjs --check");
