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

// Design tokens lifted from gravitas.my, so this page reads as part of the
// company's own surface rather than a stray localhost form. Taken from the
// site's stylesheet rather than eyeballed:
//   --primary #ff1503  --secondary #fe6a16  --accent #ffbb14
//   --background #fff6ec  --gray #c4bcb4  --black #434343
//   Manrope for display, Noto Sans for body.
// Committed to the light palette on purpose: the brand is a warm cream, and a
// dark variant would be an invention rather than a match. Every colour is set
// explicitly so the page never borrows the browser's theme.
const FONTS =
  '<link rel="preconnect" href="https://fonts.googleapis.com">' +
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
  '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800' +
  '&family=Noto+Sans:wght@400;600&display=swap" rel="stylesheet">';

const CSS = `
  :root{--primary:#ff1503;--secondary:#fe6a16;--accent:#ffbb14;
        --background:#fff6ec;--gray:#c4bcb4;--black:#434343;--white:#fff;
        --display:"Manrope",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
        --body:"Noto Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:grid;place-items:center;
       padding:24px;background:var(--background);color:var(--black);
       font:400 15px/1.6 var(--body);-webkit-font-smoothing:antialiased}
  .card{width:100%;max-width:460px;background:var(--white);
        border:1px solid color-mix(in srgb,var(--gray) 55%,transparent);
        border-radius:16px;padding:34px 32px;
        box-shadow:0 1px 2px rgba(67,67,67,.04),0 12px 32px -12px rgba(67,67,67,.10)}
  .rule{height:3px;border-radius:3px;margin-bottom:24px;
        background:linear-gradient(90deg,var(--primary),var(--secondary) 55%,var(--accent))}
  .eyebrow{font:800 11px/1 var(--display);letter-spacing:.16em;text-transform:uppercase;
           color:var(--primary);margin:0 0 12px}
  h1{font:800 25px/1.15 var(--display);letter-spacing:-.02em;margin:0 0 8px}
  .sub{color:color-mix(in srgb,var(--black) 62%,var(--white));font-size:14px;margin:0 0 24px}
  label{display:block;font:600 13px/1 var(--display);letter-spacing:.01em;margin-bottom:8px}
  input{width:100%;padding:13px 14px;font:400 15px/1.2 var(--body);
        color:var(--black);background:var(--background);
        border:1px solid color-mix(in srgb,var(--gray) 70%,transparent);
        border-radius:10px;transition:border-color .15s,box-shadow .15s}
  input::placeholder{color:color-mix(in srgb,var(--gray) 90%,var(--black))}
  input:focus{outline:0;border-color:var(--secondary);background:var(--white);
              box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 40%,transparent)}
  button{width:100%;margin-top:16px;padding:13px;border:0;border-radius:10px;
         font:700 15px/1 var(--display);letter-spacing:.01em;color:var(--white);
         background:linear-gradient(90deg,var(--primary),var(--secondary));
         cursor:pointer;transition:filter .15s,transform .06s}
  button:hover{filter:brightness(1.06)}
  button:active{transform:translateY(1px)}
  button[disabled]{opacity:.65;cursor:progress;filter:none}
  .err{font:600 13px/1.5 var(--body);color:var(--primary);margin:0 0 20px;
       padding:11px 13px;border-radius:10px;
       background:color-mix(in srgb,var(--primary) 8%,var(--white));
       border:1px solid color-mix(in srgb,var(--primary) 22%,transparent)}
  .hint{font-size:13.5px;color:color-mix(in srgb,var(--black) 66%,var(--white));margin:0 0 22px}
  .note{font-size:12.5px;line-height:1.65;margin:22px 0 0;padding-top:18px;
        color:color-mix(in srgb,var(--black) 55%,var(--white));
        border-top:1px solid color-mix(in srgb,var(--gray) 45%,transparent)}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
       padding:1px 5px;border-radius:5px;
       background:color-mix(in srgb,var(--gray) 24%,var(--background));color:var(--black)}
  .ok{color:#2f6b46}
  @media (max-width:460px){.card{padding:28px 20px}h1{font-size:22px}}
`;

function page({ nonce, error, gateway }) {
  const banner = error
    ? `<p class="err">${error}</p>`
    : `<p class="hint">Ask Shazan or your team lead for the key. It unlocks Metricool,
       Apify and the Meta endpoints, so it is the only secret you ever handle.</p>`;

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gravitas Gateway key</title>
${FONTS}
<style>${CSS}</style></head>
<body><main class="card">
  <div class="rule"></div>
  <p class="eyebrow">Gravitas Skills</p>
  <h1>Connect the gateway</h1>
  <p class="sub">One key, then every Gravitas skill works on this machine.</p>
  ${banner}
  <form method="POST" action="/${nonce}" autocomplete="off">
    <label for="k">Gateway key</label>
    <input id="k" name="key" type="password" autocomplete="off" autofocus
           spellcheck="false" placeholder="Paste, then press Enter">
    <button type="submit">Verify and save</button>
  </form>
  <p class="note">Served from your own machine on <code>127.0.0.1</code>, and it
    closes as soon as the key is saved. The key is checked against
    <code>${gateway}</code>, then stored in your operating system's credential
    store. It is never sent to an AI model and never appears in a chat
    transcript.</p>
</main>
<script>
  document.querySelector("form").addEventListener("submit", (e) => {
    const b = e.target.querySelector("button");
    b.disabled = true; b.textContent = "Checking with the gateway\u2026";
  });
</script>
</body></html>`;
}

function donePage(where) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Key saved</title>
${FONTS}
<style>${CSS}</style></head>
<body><main class="card">
  <div class="rule"></div>
  <p class="eyebrow">Gravitas Skills</p>
  <h1 class="ok">Key saved</h1>
  <p class="sub">Stored in ${where}.</p>
  <p class="hint">You can close this tab and go back to your agent. Restart it
    once so the skills pick the key up.</p>
  <p class="note">The key never passed through an AI model and is not in any
    chat transcript.</p>
</main></body></html>`;
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
