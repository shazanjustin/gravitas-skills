// pi extension: run the shared update check once a day at session start.
//
// pi auto-discovers extensions/*.js from a package root, the same way it finds
// skills/. The check itself lives in scripts/update-check.mjs so Claude Code,
// Codex and pi all run one implementation; this file only wires up the trigger.
//
// It spawns rather than imports, matching the pattern pi's own docs use for
// helper scripts, so there is no module resolution to get wrong across agents.

import { fileURLToPath } from "node:url";

const checkScript = fileURLToPath(new URL("../scripts/update-check.mjs", import.meta.url));

export default function (pi) {
  pi.on("session_start", async (event, ctx) => {
    // Only on a genuinely new session. Reloads and forks would re-announce the
    // same thing to someone who has already seen it.
    if (event.reason !== "startup" && event.reason !== "new") return;

    try {
      const result = await pi.exec(process.execPath, [checkScript], { timeout: 8000 });
      const output = (result.stdout || "").trim();
      if (output) ctx.ui.notify(output, "warning");
    } catch {
      // Fail open: a failed update check must never disturb a session.
    }
  });
}
