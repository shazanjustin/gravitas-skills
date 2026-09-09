---
name: youtube-publish-date-bulk
description: |
  Fetch YouTube publish dates in bulk from a list of video URLs and return a
  Google-Sheets-ready single column. Triggers when the user has a batch of
  YouTube URLs and needs the upload dates in the same order.
compatibility: |
  Requires Python 3.8+ and `yt-dlp` installed and on PATH.
---

# YouTube Publish Date Bulk

Use this skill when the user has a batch of YouTube URLs and wants the publish
dates returned in the same order as the input list.

## What this skill does

- Accepts a text file with one YouTube URL per line
- Gets authentication via a browser (`--browser`) or a cookies file (`--cookies-file`)
- Uses `yt-dlp` in parallel instead of slow one-by-one fetching
- Writes a `published_date` column ready for Google Sheets
- Writes a separate failures file for reruns

## Prerequisites

- **Python** 3.8 or later
- **yt-dlp** ([install guide](https://github.com/yt-dlp/yt-dlp#installation))

## Inputs

You must provide either `--cookies-file` or `--browser` for authentication.

| Argument         | Required | Default                       | Description                                    |
|------------------|----------|-------------------------------|------------------------------------------------|
| `--urls-file`    | Yes      | —                             | Plain text file with one URL per line           |
| `--cookies-file` | No*      | —                             | Netscape-format `cookies.txt`                   |
| `--browser`      | No*      | —                             | Extract cookies from a browser. One of: `chrome`, `chromium`, `firefox`, `edge`, `brave`, `opera`, `safari`, `vivaldi` |
| `--output-file`  | No       | `published_dates_output.txt`  | Where the date column is written                |
| `--failures-file`| No       | `published_dates_failures.txt`| Where failed URLs are logged                    |
| `--max-workers`  | No       | `4`                           | Number of parallel workers                      |
| `--timeout`      | No       | `90`                          | Seconds per yt-dlp call                         |
| `--retries`      | No       | `4`                           | Retries per failed URL                          |

\* Either `--cookies-file` or `--browser` is required.

## Usage

### With browser cookies (simplest, try first)

```bash
python scripts/fetch_publish_dates.py \
  --urls-file path/to/urls.txt \
  --browser edge
```

Replace `edge` with `chrome`, `firefox`, `brave`, etc. depending on your browser.
On Mac/Linux this usually works. On Windows with locked-down browsers, it may fail
with a DPAPI error — if so, use the cookies file method below.

### With a cookies file (most reliable)

```bash
python scripts/fetch_publish_dates.py \
  --urls-file path/to/urls.txt \
  --cookies-file path/to/cookies.txt
```

### Full example

```bash
python scripts/fetch_publish_dates.py \
  --urls-file temp_urls.txt \
  --cookies-file temp_youtube_cookies.txt \
  --output-file published_dates_output.txt \
  --failures-file published_dates_failures.txt \
  --max-workers 8 \
  --timeout 60
```

## Getting cookies.txt (the hard part)

The script has two built-in helpers for cookie acquisition:

### Auto-export (try this first)

Attempt to export cookies from a browser automatically using yt-dlp:

```bash
python scripts/fetch_publish_dates.py --export-cookies edge
```

If your browser's cookie database isn't encrypted, this writes `edge_cookies.txt`
and you're done. On Windows it usually fails with DPAPI — that's expected.

### Manual export guide

Shows step-by-step instructions for your specific browser and OS:

```bash
python scripts/fetch_publish_dates.py --cookie-guide
python scripts/fetch_publish_dates.py --cookie-guide edge   # browser-specific
```

The guide includes direct links to the correct browser extension and exact steps.

### What happens when it fails

The script enriches error messages automatically. When `--browser` fails, the
failures file includes hints like:

```
ERROR: Could not copy Chrome cookie database.
  [!] Browser cookie database is encrypted (DPAPI on Windows).
  [!] Use --cookie-guide <browser> for manual export instructions.
```

And the terminal output suggests next steps:

```
[!] 3 URL(s) failed with --browser edge.
    Try exporting cookies manually:
        python scripts/fetch_publish_dates.py --cookie-guide edge
    Or attempt auto-export:
        python scripts/fetch_publish_dates.py --export-cookies edge
```

## Output

Primary output file:

```text
published_date
2025-08-12
2025-11-21
2025-10-09
```

Failure file format:

```text
#12 https://youtube.com/watch?v=...
<error text>
```

## Rules for the agent

- **Preserve input order** in the final output — do not sort by completion order
- Always include the `published_date` header
- Normalize raw `upload_date` from `YYYYMMDD` to `YYYY-MM-DD`
- Use parallel workers for large lists (`--max-workers 8` or higher)
- Prefer `--cookies-file` over `--browser` if the user provides a cookies file
- If the user doesn't have a cookies file, help them get one:
  1. First try: `--export-cookies <browser>` (auto-export via yt-dlp)
  2. If that fails: `--cookie-guide <browser>` (show manual steps)
- When `--browser` fails, the script already suggests these next steps

## Workflow

1. Ask the user for their YouTube URLs (paste or a file).
2. Ask if they have a `cookies.txt` already. If yes, use `--cookies-file`.
3. If no cookies file, try `--browser` with their browser name.
4. If `--browser` fails, offer to guide them:
   - Run `--export-cookies <browser>` to attempt auto-export.
   - If that fails, run `--cookie-guide <browser>` to show manual steps.
5. Once cookies are available, run the fetch.
6. Return the `published_date` column to the user.
7. If there are failures, inspect the failures file and offer to rerun.

## Common failure modes

- **YouTube 429 / bot-check** when cookies are missing or stale — refresh cookies
- **Browser cookie extraction** fails with DPAPI on Windows — use `--cookies-file`
- **Empty output** for some URLs because cookies no longer authorize access (age-restricted, private, etc.)
- **`yt-dlp` not found** — ensure it's installed and on PATH

## Installing this skill

### For pi (recommended)

```bash
git clone <repo-url> ~/.agents/skills/youtube-publish-date-bulk
```

Pi auto-discovers skills under `~/.agents/skills/`.

### For OpenCode

```bash
git clone <repo-url> .opencode/skills/youtube-publish-date-bulk
```

### For Claude Code

```bash
git clone <repo-url> ~/.claude/skills/youtube-publish-date-bulk
```

### Manual

Clone anywhere, then reference it via your agent's settings or `--skill` flag.
