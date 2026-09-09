# YouTube Publish Date Bulk

Fetch YouTube publish dates in bulk from a list of video URLs and return a Google-Sheets-ready single column.

Compatible with any agent that supports the [Agent Skills standard](https://agentskills.io/) — **pi**, **OpenCode**, **Claude Code**, **Cursor**, **Copilot**, and more.

## Features

- 🚀 **Parallel fetching** — uses `yt-dlp` with multiple workers, not one-by-one
- 📋 **Preserves input order** — output matches your original list exactly
- 📊 **Google-Sheets-ready** — single `published_date` column, ready to paste
- 🔁 **Auto-retry** — configurable retries with exponential backoff
- ❌ **Failure tracking** — separate file with failed URLs and error details
- 🍪 **Flexible auth** — use browser cookies or a cookies.txt file
- 💡 **Cookie helpers** — built-in auto-export and step-by-step guide

## Prerequisites

- **Python** 3.8 or later
- **yt-dlp** ([install guide](https://github.com/yt-dlp/yt-dlp#installation))

## Quick Start

```bash
# Clone the skill
git clone <repo-url> youtube-publish-date-bulk
cd youtube-publish-date-bulk

# Run it (pick one auth method)
python scripts/fetch_publish_dates.py \
  --urls-file path/to/urls.txt \
  --browser edge

# Or with a cookies file:
python scripts/fetch_publish_dates.py \
  --urls-file path/to/urls.txt \
  --cookies-file path/to/cookies.txt
```

## Getting Cookies (the only tricky part)

The script includes two helpers to get you a `cookies.txt`:

### 1. Auto-export (try first)

```bash
python scripts/fetch_publish_dates.py --export-cookies edge
```

Uses yt-dlp to extract cookies from your browser. Works great on Mac/Linux.
On Windows it often fails because browser cookies are encrypted (DPAPI) —
that's normal, move to step 2.

### 2. Step-by-step guide

```bash
python scripts/fetch_publish_dates.py --cookie-guide
```

Shows platform-specific instructions for Chrome, Edge, Firefox, etc. with
direct links to the right browser extension.

### 3. Manual (if all else fails)

Install a cookie export extension:

| Browser | Extension |
|---------|-----------|
| Chrome | [Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid) |
| Edge | [Get cookies.txt](https://microsoftedge.microsoft.com/addons/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid) |
| Firefox | [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) |

Then go to youtube.com, log in, click the extension, and export.

### Input format

**`urls.txt`** — one YouTube URL per line:

```
https://www.youtube.com/watch?v=abc123
https://youtu.be/def456
https://www.youtube.com/watch?v=ghi789
```

### Output

```
published_date
2025-08-12
2025-11-21
2025-10-09
```

If some URLs fail, they're logged in `published_dates_failures.txt` for rerun.

## All Options

| Flag | Default | Description |
|------|---------|-------------|
| `--urls-file` | _(required)_ | Text file with one YouTube URL per line |
| `--cookies-file` | — | Netscape-format cookies.txt (use this OR `--browser`) |
| `--browser` | — | Extract cookies from a browser: `chrome`, `chromium`, `firefox`, `edge`, `brave`, `opera`, `safari`, `vivaldi` |
| `--export-cookies` | — | *(standalone)* Export cookies from a browser to a file |
| `--cookie-guide` | — | *(standalone)* Show manual cookie export instructions |
| `--output-file` | `published_dates_output.txt` | Output file path |
| `--failures-file` | `published_dates_failures.txt` | Failures log path |
| `--max-workers` | `4` | Parallel workers |
| `--timeout` | `90` | Seconds per request |
| `--retries` | `4` | Retries per failed URL |

## Installation for your agent

### [pi](https://github.com/earendil-works/pi-coding-agent)

```bash
git clone <repo-url> ~/.agents/skills/youtube-publish-date-bulk
```

Pi auto-discovers skills under `~/.agents/skills/`.

### OpenCode

```bash
git clone <repo-url> .opencode/skills/youtube-publish-date-bulk
```

### Claude Code

```bash
git clone <repo-url> ~/.claude/skills/youtube-publish-date-bulk
```

### Cursor / Copilot

Clone anywhere, then reference it in your agent's settings or rules file.

## How it works

1. Reads the URL list and picks an auth method (`--browser` or `--cookies-file`)
2. Spawns parallel `yt-dlp --dump-single-json` calls (one per worker)
3. Extracts `upload_date` from each response
4. Normalizes `YYYYMMDD` → `YYYY-MM-DD`
5. Writes results in original input order
6. Logs any failures separately
7. On failure, enriches errors with actionable hints (cookie guide, export commands)

## Troubleshooting

| Problem | Likely fix |
|---------|-----------|
| `yt-dlp: command not found` | Install yt-dlp and ensure it's on PATH |
| `HTTP Error 429` / bot check | Cookies are missing or stale — re-export them |
| `Could not copy Chrome cookie database` (Windows) | Use `--cookie-guide` for manual export steps |
| Some URLs return empty | Cookies may not authorize those videos (age-restricted, private) |

## License

MIT
