#!/usr/bin/env node
// Check that this machine can actually run the Gravitas skills.
//
//   node scripts/doctor.mjs
//
// Written because the credential store, the browser opener and the update check
// each take a different code path per operating system, and the Windows paths
// are the only ones that have been exercised in anger. Rather than let a Mac or
// Linux user discover a broken path in the middle of real work, this exercises
// every one of them up front, including a full write-then-read round trip
// through the OS credential store.
//
// It never touches your real key: the round trip uses a throwaway service name
// and deletes what it wrote.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { homedir, platform } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const PLAT = platform();
const GATEWAY = process.env.GRAVITAS_GATEWAY_URL || "https://gateway.shazan.me";

const TEST_SERVICE = "gravitas-doctor-selftest";
const TEST_ACCOUNT = "gravitas-doctor";
const TEST_VALUE = "doctor-" + Date.now();

let failures = 0;
let warnings = 0;

function pass(what, detail = "") {
  console.log(`  ok    ${what}${detail ? "  " + detail : ""}`);
}
function warn(what, detail = "") {
  warnings++;
  console.log(`  warn  ${what}${detail ? "  " + detail : ""}`);
}
function fail(what, detail = "") {
  failures++;
  console.log(`  FAIL  ${what}${detail ? "  " + detail : ""}`);
}

function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, {
    encoding: "utf8",
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
    timeout: 15000,
    ...opts,
  });
}

console.log(`\nGravitas skills doctor  (${PLAT}, node ${process.version})\n`);

// ---------------------------------------------------------------- runtime
console.log("Runtime");
const major = Number(process.version.slice(1).split(".")[0]);
if (major >= 18) pass("node >= 18", `(global fetch available)`);
else fail("node >= 18", `found ${process.version}; fetch and several scripts need 18+`);

if (run("git", ["--version"]).status === 0) pass("git on PATH", "(needed by the update check)");
else warn("git on PATH", "missing: the update check will stay silent");

// ------------------------------------------------------- credential store
console.log("\nCredential store");

function roundTrip() {
  if (PLAT === "win32") {
    const dir = join(homedir(), ".config", "gravitas-skills");
    const file = join(dir, "doctor-selftest.dpapi");
    const ps = [
      "$ErrorActionPreference='Stop'",
      "$k = [Console]::In.ReadToEnd().Trim()",
      `New-Item -ItemType Directory -Force -Path '${dir.replace(/'/g, "''")}' | Out-Null`,
      `ConvertTo-SecureString -String $k -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -Path '${file.replace(/'/g, "''")}' -Encoding ascii`,
    ].join("; ");
    const w = run("powershell", ["-NoProfile", "-NonInteractive", "-Command", ps], { input: TEST_VALUE });
    if (w.status !== 0) return { ok: false, how: "Windows DPAPI", why: (w.stderr || "").trim().split("\n")[0] };

    const rps = [
      "$ErrorActionPreference='Stop'",
      `$s = Get-Content -Path '${file.replace(/'/g, "''")}' | ConvertTo-SecureString`,
      "$b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)",
      "[Runtime.InteropServices.Marshal]::PtrToStringAuto($b)",
    ].join("; ");
    const r = run("powershell", ["-NoProfile", "-NonInteractive", "-Command", rps]);
    try { rmSync(file); } catch {}
    return { ok: r.status === 0 && r.stdout.trim() === TEST_VALUE, how: "Windows DPAPI" };
  }

  if (PLAT === "darwin") {
    if (run("security", ["-h"]).error) return { ok: false, how: "macOS Keychain", why: "`security` not found" };
    const w = run("security", [
      "add-generic-password", "-U", "-a", TEST_ACCOUNT, "-s", TEST_SERVICE, "-w", TEST_VALUE,
    ]);
    if (w.status !== 0) return { ok: false, how: "macOS Keychain", why: (w.stderr || "").trim().split("\n")[0] };
    const r = run("security", ["find-generic-password", "-a", TEST_ACCOUNT, "-s", TEST_SERVICE, "-w"]);
    run("security", ["delete-generic-password", "-a", TEST_ACCOUNT, "-s", TEST_SERVICE]);
    if (r.status !== 0) {
      return {
        ok: false, how: "macOS Keychain",
        why: "wrote but could not read back; a Keychain access prompt may have been declined",
      };
    }
    return { ok: r.stdout.trim() === TEST_VALUE, how: "macOS Keychain" };
  }

  if (PLAT === "linux") {
    if (run("secret-tool", ["--version"]).error) {
      return { ok: false, how: "libsecret", why: "`secret-tool` not installed (apt install libsecret-tools)" };
    }
    const w = run("secret-tool", ["store", "--label=doctor", "service", TEST_SERVICE, "account", TEST_ACCOUNT], { input: TEST_VALUE });
    if (w.status !== 0) return { ok: false, how: "libsecret", why: "no unlocked keyring? (headless sessions often have none)" };
    const r = run("secret-tool", ["lookup", "service", TEST_SERVICE, "account", TEST_ACCOUNT]);
    run("secret-tool", ["clear", "service", TEST_SERVICE, "account", TEST_ACCOUNT]);
    return { ok: r.status === 0 && r.stdout.trim() === TEST_VALUE, how: "libsecret" };
  }

  return { ok: false, how: "unknown platform", why: PLAT };
}

const rt = roundTrip();
if (rt.ok) {
  pass(`${rt.how} write and read back`);
} else {
  // The 0600 file fallback always works, so this is a downgrade, not a blocker.
  warn(`${rt.how} unavailable`, rt.why || "");
  const dir = join(homedir(), ".config", "gravitas-skills");
  const f = join(dir, "doctor-selftest");
  try {
    mkdirSync(dir, { recursive: true });
    writeFileSync(f, TEST_VALUE, { mode: 0o600 });
    const ok = readFileSync(f, "utf8") === TEST_VALUE;
    rmSync(f);
    if (ok) pass("0600 file fallback", `(${dir})`);
    else fail("0600 file fallback", "wrote but read back differently");
  } catch (e) {
    fail("0600 file fallback", e.message);
  }
}

const existing = run(process.execPath, [join(HERE, "get-key.mjs"), "--check"]);
if (existing.status === 0) pass("a gateway key is stored", (existing.stdout || "").trim());
else warn("no gateway key stored", "run: node scripts/set-key.mjs");

// -------------------------------------------------------- browser opener
console.log("\nBrowser");
const opener = PLAT === "win32" ? "cmd" : PLAT === "darwin" ? "open" : "xdg-open";
const probe = PLAT === "win32" ? run("cmd", ["/c", "echo", "ok"]) : run(opener, ["--help"]);
if (!probe.error) pass(`${opener} available`, "(used to open the key page)");
else if (PLAT === "linux") warn("xdg-open missing", "the key page URL will be printed instead of opened");
else fail(`${opener} missing`, "the key page cannot be opened automatically");

// ------------------------------------------------------------ networking
console.log("\nNetwork");
try {
  const res = await fetch(`${GATEWAY}/secrets`, {
    headers: { "User-Agent": "curl/8.4.0" },
    signal: AbortSignal.timeout(8000),
  });
  // 401 without a key is the correct, healthy answer.
  if (res.status === 401 || res.ok) pass(`${GATEWAY} reachable`, `(HTTP ${res.status})`);
  else warn(`${GATEWAY} answered oddly`, `HTTP ${res.status}`);
} catch (e) {
  fail(`${GATEWAY} unreachable`, e.message);
}

// ---------------------------------------------------------------- skills
console.log("\nSkills");
const skillsDir = join(dirname(HERE), "skills");
if (existsSync(skillsDir)) {
  const n = run(process.execPath, [join(HERE, "lint-skills.mjs")]);
  const line = (n.stdout || "").trim().split("\n").filter(Boolean).pop() || "";
  if (n.status === 0) pass("skills lint", line);
  else fail("skills lint", line);
} else {
  warn("no skills/ directory", "running from outside the package?");
}

console.log(
  `\n${failures ? "FAILED" : warnings ? "OK with warnings" : "All good"}: ` +
  `${failures} failure(s), ${warnings} warning(s).\n`
);
process.exit(failures ? 1 : 0);
