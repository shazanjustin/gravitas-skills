# -*- coding: utf-8 -*-
"""
Fast Composio client for Google Sheets / Slides / Drive.

Why this exists: the obvious way to drive Composio (one MCP JSON-RPC call per
operation, over a fresh TLS connection, parsing SSE) is slow enough that
building a deck or a model tab takes minutes. This module fixes four things:

  1. REST execute instead of MCP/SSE   ~35% faster per call, no SSE parsing
  2. keep-alive connection reuse       kills a TLS handshake per call
  3. batch-first helpers               a whole deck in 1-3 HTTP calls
  4. thread pool for independent calls

Credentials are read from (in order): explicit args, environment, the Gravitas
Gateway, then a local .env file. The gateway path is what makes this work on a
teammate's machine, since nobody else has the original .env.collected.

IMPORTANT: never build request bodies by shelling out to curl. Spreadsheet
formulas and Slides object ids are full of $ and %, and a shell will eat them.
Everything here goes over http.client directly.
"""
import json, os, pathlib, re, ssl, subprocess, threading, time
import http.client
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HOST = "backend.composio.dev"
# A local .env is the last resort, and only the author's machine has the
# original. Override the path with COMPOSIO_ENV_FILE.
ENV_FILE = os.environ.get(
    "COMPOSIO_ENV_FILE", r"D:\vibe coding stuff\Coolify\.env.collected"
)

GATEWAY_URL = os.environ.get("GRAVITAS_GATEWAY_URL", "https://gateway.shazan.me")

# The MCP server that actually carries googleslides. The older "ev-discord"
# server (8ee020f3-...) has sheets/drive/notion/nocodb but NO slides, which is
# the trap that makes people think Slides is not connected.
SERVER_WITH_SLIDES = "033fa126-1ff0-40bb-8d78-c57c2cd5df4a"

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)


def _load_env():
    out = {}
    try:
        with open(ENV_FILE, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip("'").strip('"')
    except OSError:
        pass
    return out


def _gateway_key():
    """The Gravitas Gateway key, from the environment or the OS credential store.

    scripts/get-key.mjs in this package knows every storage backend, so shell out
    to it rather than reimplementing DPAPI, Keychain and libsecret here.
    """
    key = os.environ.get("GRAVITAS_GATEWAY_KEY", "").strip()
    if key:
        return key
    getter = (pathlib.Path(__file__).resolve().parents[3] / "scripts" / "get-key.mjs")
    if not getter.exists():
        return None
    try:
        r = subprocess.run(
            ["node", str(getter)], capture_output=True, text=True, timeout=15
        )
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _from_gateway(name):
    """Fetch one secret from the gateway. Returns None if unavailable.

    This is the path that makes the skill work for anyone other than the author.
    It stays quiet on every failure: no gateway key, no network, or the secret
    simply not being on the gateway yet, all fall through to the local .env.
    """
    key = _gateway_key()
    if not key:
        return None
    try:
        req = urllib.request.Request(
            f"{GATEWAY_URL}/secret/{name}",
            headers={
                "x-api-key": key,
                # Cloudflare answers Python's default urllib UA with error 1010
                # before the request reaches the Worker.
                "User-Agent": "curl/8.4.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("value") or None
    except Exception:
        return None


class Composio:
    def __init__(self, api_key=None, user_id=None, timeout=180):
        env = _load_env()
        self.key = (api_key
                    or os.environ.get("COMPOSIO_API_KEY")
                    or _from_gateway("COMPOSIO_API_KEY")
                    or env.get("COMPOSIO_API_KEY"))
        self.user = (user_id
                     or os.environ.get("COMPOSIO_EXTERNAL_USER_ID")
                     or _from_gateway("COMPOSIO_EXTERNAL_USER_ID")
                     or env.get("COMPOSIO_EXTERNAL_USER_ID"))
        if not self.key or not self.user:
            raise RuntimeError(
                "Missing COMPOSIO_API_KEY / COMPOSIO_EXTERNAL_USER_ID.\n"
                "These are not on the Gravitas Gateway yet, so set them in your "
                "environment, or ask Shazan to add them to the gateway with "
                "`wrangler secret put`."
            )
        self.timeout = timeout
        self._local = threading.local()

    # ---------- transport ----------
    def _conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = http.client.HTTPSConnection(HOST, timeout=self.timeout,
                                            context=ssl.create_default_context())
            self._local.conn = c
        return c

    def _drop(self):
        c = getattr(self._local, "conn", None)
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
            self._local.conn = None

    def execute(self, tool, arguments, retries=4):
        """Run one Composio tool. Returns the tool's parsed `data` payload."""
        body = json.dumps({"user_id": self.user, "arguments": arguments})
        headers = {"Content-Type": "application/json", "x-api-key": self.key,
                   "Accept": "application/json", "Connection": "keep-alive"}
        path = "/api/v3/tools/execute/" + tool
        delay = 1.5
        last = None
        for attempt in range(retries + 1):
            try:
                conn = self._conn()
                conn.request("POST", path, body=body, headers=headers)
                resp = conn.getresponse()
                raw = resp.read().decode("utf-8", "replace")
                if resp.status in RETRY_STATUS:
                    last = "HTTP %d: %s" % (resp.status, raw[:200])
                    self._drop()
                elif resp.status >= 400:
                    raise RuntimeError("%s -> HTTP %d: %s" % (tool, resp.status, raw[:400]))
                else:
                    j = json.loads(raw)
                    if not j.get("successful", j.get("successfull", True)):
                        raise RuntimeError("%s failed: %s" % (tool, str(j.get("error"))[:400]))
                    return j.get("data", j)
            except (http.client.HTTPException, OSError, ValueError) as e:
                last = repr(e)
                self._drop()
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("%s exhausted retries: %s" % (tool, last))

    def parallel(self, jobs, workers=6):
        """jobs = [(tool, arguments), ...] -> list of results in the same order.
        Only for calls with no ordering dependency on each other."""
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(lambda j: self.execute(*j), jobs))

    # ---------- sheets ----------
    def sheet_names(self, ssid):
        return self.execute("GOOGLESHEETS_GET_SHEET_NAMES",
                            {"spreadsheet_id": ssid})["sheet_names"]

    def sheet_info(self, ssid):
        r = self.execute("GOOGLESHEETS_GET_SPREADSHEET_INFO", {"spreadsheet_id": ssid})
        # this tool nests everything under response_data
        return r.get("response_data") or r

    def sheet_ids(self, ssid):
        """{tab title: numeric sheetId}. FORMAT_CELL needs the numeric id, not a name."""
        out = {}
        for s in self.sheet_info(ssid).get("sheets", []):
            p = s.get("properties", s)
            out[p.get("title")] = p.get("sheetId")
        return out

    def sheet_read(self, ssid, ranges):
        if isinstance(ranges, str):
            ranges = [ranges]
        r = self.execute("GOOGLESHEETS_BATCH_GET",
                         {"spreadsheet_id": ssid, "ranges": ranges})
        return [vr.get("values", []) for vr in r["valueRanges"]]

    def sheet_write(self, ssid, rng, values, raw=False, chunk=50, pause=1.2):
        """Write a 2D list at an A1 range.

        GOOGLESHEETS_VALUES_UPDATE does NOT exist on this project -- checked
        against the live tool list. The only writer is GOOGLESHEETS_BATCH_UPDATE,
        which takes sheet_name + first_cell_location rather than an A1 range, so
        the range is split here. Ragged rows are padded, because the API rejects
        rows of differing length. Long writes are chunked and paced.
        """
        tab, cell = _split_a1(rng)
        col0, row0 = _cell_to_rc(cell)
        if not values:
            return None
        w = max(len(r) for r in values)
        grid = [list(r) + [""] * (w - len(r)) for r in values]
        grid = [["" if v is None else v for v in r] for r in grid]
        out = []
        for i in range(0, len(grid), chunk):
            part = grid[i:i + chunk]
            out.append(self.execute("GOOGLESHEETS_BATCH_UPDATE", {
                "spreadsheet_id": ssid,
                "sheet_name": tab,
                "first_cell_location": "%s%d" % (_rc_to_col(col0), row0 + i + 1),
                "values": part,
                "valueInputOption": "RAW" if raw else "USER_ENTERED"}))
            if i + chunk < len(grid):
                time.sleep(pause)
        return out

    def sheet_add_tab(self, ssid, title, index=None, rows=200, cols=26):
        props = {"title": title, "gridProperties": {"rowCount": rows, "columnCount": cols}}
        if index is not None:
            props["index"] = index
        return self.execute("GOOGLESHEETS_ADD_SHEET",
                            {"spreadsheet_id": ssid, "title": title, "properties": props})

    def sheet_format(self, ssid, sheet_name, rng, bold=None, italic=None,
                     font_size=None, rgb=None, underline=None, strikethrough=None,
                     _ids=None):
        """Format an A1 range such as "A1:I1" on the named tab.

        GOOGLESHEETS_FORMAT_CELL takes a NUMERIC worksheet_id and 0-based,
        half-open row/column indices -- not a sheet name and an A1 range. Passing
        the latter fails with "Invalid request data provided - following fields
        are missing". The conversion happens here.

        Pass _ids=c.sheet_ids(ssid) when formatting many ranges, to avoid
        re-fetching the spreadsheet metadata on every call.
        """
        ids = _ids if _ids is not None else self.sheet_ids(ssid)
        if sheet_name not in ids:
            raise KeyError("no tab named %r (have: %s)" % (sheet_name, sorted(ids)))
        if "!" in rng:
            rng = rng.split("!", 1)[1]
        a, _, b = rng.partition(":")
        c0, r0 = _cell_to_rc(a)
        c1, r1 = _cell_to_rc(b) if b else (c0, r0)
        args = {"spreadsheet_id": ssid, "worksheet_id": ids[sheet_name],
                "start_row_index": r0, "end_row_index": r1 + 1,
                "start_column_index": c0, "end_column_index": c1 + 1}
        for k, v in (("bold", bold), ("italic", italic), ("underline", underline),
                     ("strikethrough", strikethrough), ("fontSize", font_size)):
            if v is not None:
                args[k] = v
        if rgb:
            args["red"], args["green"], args["blue"] = rgb
        return self.execute("GOOGLESHEETS_FORMAT_CELL", args)

    # ---------- slides ----------
    def deck_create(self, title):
        r = self.execute("GOOGLESLIDES_PRESENTATIONS_CREATE", {"title": title})
        return r.get("presentationId") or r.get("presentation_id") or r

    def deck_get(self, pid):
        return self.execute("GOOGLESLIDES_PRESENTATIONS_GET", {"presentationId": pid})

    def deck_batch(self, pid, requests, chunk=60):
        """THE speed lever. `requests` is a list of raw Google Slides API request
        dicts; they are sent in as few HTTP calls as possible. Slides applies
        them in order, so keep creation before styling within a chunk."""
        out = []
        for i in range(0, len(requests), chunk):
            out.append(self.execute("GOOGLESLIDES_PRESENTATIONS_BATCH_UPDATE",
                                    {"presentationId": pid,
                                     "requests": requests[i:i + chunk]}))
        return out

    # ---------- drive ----------
    def drive_find(self, name_contains, mime=None, limit=20):
        q = "name contains '%s' and trashed = false" % name_contains.replace("'", "\\'")
        if mime:
            q += " and mimeType = '%s'" % mime
        return self.execute("GOOGLEDRIVE_LIST_FILES",
                            {"q": q, "pageSize": limit})

    def drive_move(self, file_id, folder_id):
        return self.execute("GOOGLEDRIVE_ADD_PARENT",
                            {"file_id": file_id, "parent_id": folder_id})

    # ---------- raw Google APIs through Composio's proxy ----------
    def connected_account(self, toolkit):
        """The ACTIVE connected account id for a toolkit slug, e.g. "googledrive"."""
        cache = self.__dict__.setdefault("_accounts", {})
        if toolkit not in cache:
            conn = http.client.HTTPSConnection(HOST, timeout=self.timeout, context=ssl.create_default_context())
            conn.request("GET", "/api/v3/connected_accounts?user_ids=%s&limit=100" % self.user,
                         headers={"x-api-key": self.key, "Accept": "application/json"})
            items = json.loads(conn.getresponse().read().decode("utf-8", "replace")).get("items", [])
            for a in items:
                if a.get("status") == "ACTIVE":
                    cache.setdefault(a.get("toolkit", {}).get("slug"), a.get("id"))
        if not cache.get(toolkit):
            raise RuntimeError("no ACTIVE %s connected account for this user" % toolkit)
        return cache[toolkit]

    def proxy(self, method, url, body=None, toolkit="googledrive"):
        """Call a Google API endpoint directly with the connected account's auth.

        For anything a Composio tool does not expose, such as supportsAllDrives."""
        conn = http.client.HTTPSConnection(HOST, timeout=self.timeout, context=ssl.create_default_context())
        payload = {"endpoint": url, "method": method, "connected_account_id": self.connected_account(toolkit)}
        if body is not None:
            payload["body"] = body
        conn.request("POST", "/api/v3/tools/execute/proxy", body=json.dumps(payload),
                     headers={"x-api-key": self.key, "Content-Type": "application/json"})
        resp = conn.getresponse(); raw = resp.read().decode("utf-8", "replace")
        j = json.loads(raw)
        status = j.get("status", resp.status)
        if resp.status >= 400 or (isinstance(status, int) and status >= 400):
            raise RuntimeError("proxy %s %s -> %s: %s" % (method, url, status, raw[:400]))
        return j.get("data", j)

    def drive_copy(self, file_id, title):
        """Copy a file, including one on a shared drive. The copy lands in the source's folder.

        GOOGLEDRIVE_COPY_FILE answers 404 "File not found" for shared-drive files,
        because it cannot send supportsAllDrives=true."""
        return self.proxy("POST", "https://www.googleapis.com/drive/v3/files/%s/copy?supportsAllDrives=true&fields=id,name,parents,driveId" % file_id,
                          {"name": title})

    def drive_trash(self, file_id):
        """Move a file to Trash, which can be undone. Prefer this to
        GOOGLEDRIVE_GOOGLE_DRIVE_DELETE_FOLDER_OR_FILE_ACTION, which deletes permanently."""
        return self.proxy("PATCH", "https://www.googleapis.com/drive/v3/files/%s?supportsAllDrives=true&fields=id,name,trashed" % file_id,
                          {"trashed": True})


if __name__ == "__main__":
    import sys
    c = Composio()
    t = time.time()
    print("sheet tabs:", c.sheet_names(sys.argv[1] if len(sys.argv) > 1
                                      else "1WIOvH6cQP39MfcgaLRQxT62tudYHXRZjY3aWzKaUNFE"))
    print("one call in %.2fs" % (time.time() - t))


# ---------- A1 notation ----------
def _split_a1(rng):
    """"'My Tab'!B3:D9" -> ("My Tab", "B3").  A range with no tab raises."""
    if "!" not in rng:
        raise ValueError("range %r needs a tab name, e.g. \"Sheet1!A1\"" % rng)
    tab, cell = rng.split("!", 1)
    tab = tab.strip()
    if len(tab) > 1 and tab[0] == tab[-1] == "'":
        tab = tab[1:-1].replace("''", "'")
    return tab, cell.split(":")[0]


def _cell_to_rc(cell):
    """"B3" -> (1, 2), both 0-based."""
    m = re.match(r"^\$?([A-Za-z]+)\$?(\d+)$", cell.strip())
    if not m:
        raise ValueError("bad A1 cell: %r" % cell)
    letters, digits = m.group(1).upper(), m.group(2)
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return col - 1, int(digits) - 1


def _rc_to_col(idx):
    """0 -> "A", 26 -> "AA"."""
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s
