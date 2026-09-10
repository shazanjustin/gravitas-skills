// Collect the gateway key through a local browser page instead of a terminal.
//
// This exists because a hidden terminal prompt cannot run anywhere a model sits
// in between, which is exactly where a newcomer usually is: inside an agent,
// being onboarded. A browser page has no such limit. The agent starts the
// server, the page opens on the user's screen, the user types into the browser,
// and the key travels browser -> loopback -> OS credential store. It is never a
// token in anyone's context and never reaches a transcript.
//
// Security shape:
//   - binds 127.0.0.1 only, so nothing leaves the machine
//   - random port, and a random nonce in the path, so another local process
//     cannot guess the URL and serve its own form or scrape ours
//   - the key is POSTed in the body, never in the URL, so it stays out of
//     browser history
//   - the server verifies the key, then shuts down; it does not linger
//   - gives up after a few minutes rather than staying open forever
//
// It is still plain HTTP. That is deliberate: loopback traffic does not touch a
// network, and a self-signed certificate would produce a browser warning that
// trains people to click through warnings.

import { createServer } from "node:http";
import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { platform } from "node:os";

const TIMEOUT_MS = 5 * 60 * 1000;

function page({ nonce, error, gateway }) {
  const banner = error
    ? `<p class="err">${error}</p>`
    : `<p class="hint">Ask Shazan or your team lead for the key. It unlocks Metricool,
       Apify and the Meta endpoints, so it is the only secret you ever handle.</p>`;

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gravitas Gateway key</title>
<style>
  :root { color-scheme: light dark; --bg:#fbfaf9; --fg:#1a1a18; --mut:#6b6a66;
          --line:#e0ddd8; --acc:#b4552d; --err:#a8322a; --ok:#2f6b46; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#17171a; --fg:#eceae6; --mut:#9a978f; --line:#2e2e33;
            --acc:#d9764a; --err:#e0736a; --ok:#5fbe89; }
  }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:var(--bg); color:var(--fg); padding:24px;
         font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; }
  .card { width:100%; max-width:440px; }
  h1 { font-size:19px; margin:0 0 4px; letter-spacing:-0.01em; }
  .sub { color:var(--mut); font-size:13px; margin:0 0 22px; }
  label { display:block; font-size:13px; font-weight:600; margin-bottom:7px; }
  input { width:100%; padding:11px 12px; font-size:15px; font-family:inherit;
          border:1px solid var(--line); border-radius:8px; background:var(--bg);
          color:var(--fg); }
  input:focus { outline:2px solid var(--acc); outline-offset:-1px; border-color:transparent; }
  button { width:100%; margin-top:14px; padding:11px; font-size:15px; font-weight:600;
           font-family:inherit; border:0; border-radius:8px; background:var(--acc);
           color:#fff; cursor:pointer; }
  button:hover { filter:brightness(1.07); }
  button[disabled] { opacity:.6; cursor:progress; }
  .hint, .err, .note { font-size:13px; }
  .hint { color:var(--mut); margin:0 0 18px; }
  .err { color:var(--err); margin:0 0 18px; font-weight:600; }
  .note { color:var(--mut); margin-top:18px; padding-top:16px;
          border-top:1px solid var(--line); }
  code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
</style></head>
<body><div class="card">
  <h1>Gravitas Gateway key</h1>
  <p class="sub">Setting up the Gravitas skills on this machine</p>
  ${banner}
  <form method="POST" action="/${nonce}" autocomplete="off">
    <label for="k">Paste your key</label>
    <input id="k" name="key" type="password" autocomplete="off" autofocus
           spellcheck="false" placeholder="Paste, then press Enter">
    <button type="submit">Verify and save</button>
  </form>
  <p class="note">This page is served from your own machine on
    <code>127.0.0.1</code> and closes as soon as the key is saved. The key is
    checked against <code>${gateway}</code>, then stored in your operating
    system's credential store. It is never sent to an AI model and never
    appears in a chat transcript.</p>
</div>
<script>
  document.querySelector("form").addEventListener("submit", (e) => {
    const b = e.target.querySelector("button");
    b.disabled = true; b.textContent = "Checking with the gateway...";
  });
</script>
</body></html>`;
}

function donePage(where) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Key saved</title>
<style>
  :root { color-scheme: light dark; --bg:#fbfaf9; --fg:#1a1a18; --mut:#6b6a66; --ok:#2f6b46; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#17171a; --fg:#eceae6; --mut:#9a978f; --ok:#5fbe89; }
  }
  body { margin:0; min-height:100vh; display:grid; place-items:center; padding:24px;
         background:var(--bg); color:var(--fg);
         font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; }
  .card { max-width:420px; text-align:center; }
  h1 { font-size:19px; margin:0 0 8px; color:var(--ok); }
  p { color:var(--mut); font-size:13px; margin:0 0 6px; }
  code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
</style></head>
<body><div class="card">
  <h1>Key saved</h1>
  <p>Stored in ${where}.</p>
  <p>You can close this tab and go back to your agent.</p>
</div></body></html>`;
}

function openBrowser(url) {
  const p = platform();
  const [cmd, args] =
    p === "win32" ? ["cmd", ["/c", "start", "", url.replace(/&/g, "^&")]]
    : p === "darwin" ? ["open", [url]]
    : ["xdg-open", [url]];
  try {
    spawn(cmd, args, { detached: true, stdio: "ignore", windowsHide: true }).unref();
    return true;
  } catch {
    return false;
  }
}

// verify(key) -> "valid" | "rejected" | "unreachable"
// store(key)  -> a human-readable description of where it went
export function promptViaBrowser({ verify, store, gateway, autoOpen = true }) {
  return new Promise((resolve) => {
    const nonce = randomBytes(24).toString("hex");
    let settled = false;

    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      // Let the response flush before tearing the socket down.
      setTimeout(() => server.close(() => resolve(value)), 250);
    };

    const server = createServer(async (req, res) => {
      // Anything without the nonce is not our browser tab.
      if (!req.url.startsWith(`/${nonce}`)) {
        res.writeHead(404).end("Not found");
        return;
      }

      if (req.method === "GET") {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        res.end(page({ nonce, gateway }));
        return;
      }

      if (req.method !== "POST") {
        res.writeHead(405).end();
        return;
      }

      let body = "";
      for await (const chunk of req) {
        body += chunk;
        if (body.length > 8192) {
          res.writeHead(413).end();
          return;
        }
      }
      const key = decodeURIComponent(
        (new URLSearchParams(body).get("key") || "").trim()
      );

      if (!key) {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        res.end(page({ nonce, gateway, error: "No key entered. Try again." }));
        return;
      }

      const state = await verify(key);
      if (state === "rejected") {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        res.end(page({
          nonce, gateway,
          error: "The gateway rejected that key. Check you copied all of it.",
        }));
        return;
      }

      const where = store(key);
      res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      res.end(donePage(where));
      finish({ key, where, verified: state === "valid" });
    });

    const timer = setTimeout(() => finish(null), TIMEOUT_MS);

    server.on("error", () => finish(null));

    server.listen(0, "127.0.0.1", () => {
      const url = `http://127.0.0.1:${server.address().port}/${nonce}`;
      const opened = autoOpen && openBrowser(url);
      console.log(
        opened
          ? "\nOpened a page in your browser to collect the key."
          : "\nOpen this page in your browser to enter the key:"
      );
      console.log(`\n  ${url}\n`);
      console.log("It is served from your own machine and closes once saved.");
      console.log("Waiting...");
    });
  });
}
