#!/usr/bin/env python3
"""Fetch YouTube publish dates in bulk from a list of video URLs."""

from __future__ import annotations

import argparse
import json
import platform
import random
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


VALID_BROWSERS = [
    "chrome", "chromium", "firefox", "edge", "brave", "opera", "safari", "vivaldi",
]

COOKIE_GUIDE = {
    "chrome": {
        "name": "Google Chrome",
        "steps": {
            "win32": [
                "1. Install the 'Get cookies.txt' extension from the Chrome Web Store:",
                "   https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "darwin": [
                "1. Install the 'Get cookies.txt' extension from the Chrome Web Store:",
                "   https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "linux": [
                "1. Install the 'Get cookies.txt' extension from the Chrome Web Store:",
                "   https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
        },
    },
    "chromium": {
        "name": "Chromium",
        "steps": {
            "win32": [
                "1. Install the 'Get cookies.txt' extension from the Chrome Web Store:",
                "   https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "darwin": [
                "1. Install the 'Get cookies.txt' extension from the Chrome Web Store:",
                "   https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "linux": [
                "1. Install the 'Get cookies.txt' extension from the Chrome Web Store:",
                "   https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
        },
    },
    "firefox": {
        "name": "Firefox",
        "steps": {
            "win32": [
                "1. Install the 'cookies.txt' add-on from Firefox Add-ons:",
                "   https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the add-on icon in the toolbar.",
                "4. Click 'Export cookies' -- it will save a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "darwin": [
                "1. Install the 'cookies.txt' add-on from Firefox Add-ons:",
                "   https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the add-on icon in the toolbar.",
                "4. Click 'Export cookies' -- it will save a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "linux": [
                "1. Install the 'cookies.txt' add-on from Firefox Add-ons:",
                "   https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the add-on icon in the toolbar.",
                "4. Click 'Export cookies' -- it will save a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
        },
    },
    "edge": {
        "name": "Microsoft Edge",
        "steps": {
            "win32": [
                "1. Install the 'Get cookies.txt' extension from the Edge Add-ons store:",
                "   https://microsoftedge.microsoft.com/addons/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "darwin": [
                "1. Install the 'Get cookies.txt' extension from the Edge Add-ons store:",
                "   https://microsoftedge.microsoft.com/addons/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
            "linux": [
                "1. Install the 'Get cookies.txt' extension from the Edge Add-ons store:",
                "   https://microsoftedge.microsoft.com/addons/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid",
                "2. Go to youtube.com and make sure you're logged in.",
                "3. Click the extension icon (cookie icon) in the toolbar.",
                "4. Click 'Export' -- it will download a cookies.txt file.",
                "5. Pass it to the script with: --cookies-file /path/to/cookies.txt",
            ],
        },
    },
}

PLATFORM = platform.system().lower()
PLATFORM_KEY = {"windows": "win32", "darwin": "darwin"}.get(PLATFORM, "linux")
OS_NAME = {"windows": "Windows", "darwin": "macOS"}.get(PLATFORM, "Linux")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_date(raw: str) -> str | None:
    raw = (raw or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def build_cookie_args(
    cookies_file: Path | None,
    browser: str | None,
) -> list[str]:
    if browser:
        return ["--cookies-from-browser", browser]
    if cookies_file:
        return ["--cookies", str(cookies_file)]
    return []


def try_export_cookies(browser: str, output: Path) -> bool:
    """Attempt to export cookies from a browser using yt-dlp's native export."""
    print(f"[*] Trying to export cookies from {browser}...")

    dummy_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", browser,
        "--cookies", str(output),
        "--skip-download",
        "--no-warnings",
        "--extractor-retries", "1",
        "--retries", "1",
        "--dump-single-json",
        dummy_url,
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        if output.exists() and output.stat().st_size > 100:
            print(f"[OK] Exported cookies to {output}")
            return True

        stderr = (completed.stderr or "").strip()
        if "DPAPI" in stderr or "Could not copy" in stderr:
            print("[!] Browser cookie database is encrypted (DPAPI on Windows).")
            print("    yt-dlp cannot read it directly.")
        elif completed.returncode != 0:
            print(f"[!] yt-dlp returned exit code {completed.returncode}.")
            print(f"    stderr: {stderr[:300]}")
        else:
            print("[!] Export produced an empty or invalid cookies file.")
            if stderr:
                print(f"    stderr: {stderr[:300]}")

    except FileNotFoundError:
        print("[!] yt-dlp is not installed or not on PATH.")
    except subprocess.TimeoutExpired:
        print("[!] yt-dlp timed out while trying to export cookies.")

    return False


# ---------------------------------------------------------------------------
# Cookie guide
# ---------------------------------------------------------------------------

def print_cookie_guide(browser: str | None = None) -> None:
    """Print instructions for manually exporting cookies from a browser."""
    print("=" * 60)
    print("Manual Cookie Export Guide")
    print("=" * 60)
    print()
    print(f"Detected OS: {OS_NAME}")
    print()

    if browser and browser in COOKIE_GUIDE:
        browsers_to_show = [browser]
    else:
        browsers_to_show = list(COOKIE_GUIDE.keys())

    for b in browsers_to_show:
        info = COOKIE_GUIDE[b]
        print(f"-- {info['name']} --")
        print()
        steps = info["steps"].get(PLATFORM_KEY, info["steps"]["linux"])
        for step in steps:
            print(step)
        print()

    print("-- Alternative: yt-dlp browser export --")
    print()
    print("  You can also try letting yt-dlp export cookies directly:")
    print()
    print("      python scripts/fetch_publish_dates.py --export-cookies <browser>")
    print()
    print("  This uses yt-dlp's --cookies-from-browser under the hood.")
    print("  On Mac/Linux this usually works. On Windows it often fails")
    print("  because browser cookies are encrypted (DPAPI).")
    print()
    print("-- After you have a cookies.txt --")
    print()
    print("  Run the main script with:")
    print()
    print("      python scripts/fetch_publish_dates.py \\")
    print("          --urls-file path/to/urls.txt \\")
    print("          --cookies-file path/to/cookies.txt")
    print()


# ---------------------------------------------------------------------------
# Fetch one URL
# ---------------------------------------------------------------------------

def fetch_one(
    index: int,
    url: str,
    cookie_args: list[str],
    timeout: int,
    retries: int,
) -> tuple[int, str | None, str | None]:
    full_url = url if url.startswith("http") else f"https://{url}"
    last_error = ""

    for attempt in range(retries):
        cmd = [
            "yt-dlp",
            *cookie_args,
            "--skip-download",
            "--no-warnings",
            "--extractor-retries",
            "2",
            "--retries",
            "2",
            "--dump-single-json",
            full_url,
        ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )

            if completed.returncode == 0 and completed.stdout.strip():
                payload = json.loads(completed.stdout)
                value = normalize_date(payload.get("upload_date", ""))
                if value:
                    return index, value, None

            last_error = ((completed.stderr or "") + "\n" + (completed.stdout or "")).strip()[:1200]

            # On last attempt, enhance error with export/guide hints
            if attempt == retries - 1:
                last_error = _enrich_error(last_error)

        except subprocess.TimeoutExpired:
            last_error = f"Timed out after {timeout}s"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:1200]

        if attempt < retries - 1:
            time.sleep((2**attempt) + random.random())

    return index, None, last_error


def _enrich_error(error: str) -> str:
    """Append helpful hints to common yt-dlp error messages."""
    hints = []

    if "Sign in to confirm" in error or "bot" in error.lower() or "429" in error:
        hints.append("YouTube is blocking the request - cookies may be missing or stale.")
        hints.append("Try: --browser <chrome|edge|firefox> to use browser cookies.")
        if PLATFORM_KEY == "win32":
            hints.append("On Windows, browser cookies are often encrypted (DPAPI).")
            hints.append("Export cookies manually with --cookie-guide <browser>,")
            hints.append("or use --export-cookies <browser> to attempt auto-export.")
        else:
            hints.append("Export cookies with: --export-cookies <browser>")
            hints.append("Or see the guide: --cookie-guide <browser>")

    if "Could not copy" in error or "DPAPI" in error:
        hints.append("Browser cookie database is encrypted (DPAPI on Windows).")
        hints.append("Use --cookie-guide <browser> for manual export instructions.")

    if not hints:
        return error

    return error + "\n" + "\n".join("  [!] " + h for h in hints)


# ---------------------------------------------------------------------------
# Argument parsing - two phase to handle standalone modes
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments, handling standalone modes (--export-cookies, --cookie-guide)."""

    raw_args = argv if argv is not None else sys.argv[1:]

    # Phase 1: scan for standalone flags
    p1 = argparse.ArgumentParser(add_help=False)
    p1.add_argument("--export-cookies", type=str, default=None, help=argparse.SUPPRESS)
    p1.add_argument("--cookie-guide", type=str, default=None, nargs="?", const="__all__", help=argparse.SUPPRESS)
    p1.add_argument("--help", action="store_true", default=False, help=argparse.SUPPRESS)
    flags, remainder = p1.parse_known_args(raw_args)

    # --help: defer to the full parser
    if flags.help:
        _show_full_help()
        raise SystemExit(0)

    # --export-cookies: standalone mode
    if flags.export_cookies is not None:
        browser = flags.export_cookies
        if browser not in VALID_BROWSERS:
            print(f"error: --export-cookies: invalid browser '{browser}'.")
            print(f"valid browsers: {', '.join(VALID_BROWSERS)}")
            raise SystemExit(2)
        _handle_export_cookies(browser)
        raise SystemExit(0)

    # --cookie-guide: standalone mode
    if flags.cookie_guide is not None:
        browser = None if flags.cookie_guide == "__all__" else flags.cookie_guide
        if browser is not None and browser not in VALID_BROWSERS:
            print(f"error: --cookie-guide: invalid browser '{browser}'.")
            print(f"valid browsers: {', '.join(VALID_BROWSERS)}")
            raise SystemExit(2)
        print_cookie_guide(browser)
        raise SystemExit(0)

    # Phase 2: full parse for normal mode
    parser = argparse.ArgumentParser(
        description="Fetch YouTube publish dates in bulk from a list of video URLs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/fetch_publish_dates.py --urls-file urls.txt --browser edge
              python scripts/fetch_publish_dates.py --urls-file urls.txt --cookies-file cookies.txt
              python scripts/fetch_publish_dates.py --export-cookies edge
              python scripts/fetch_publish_dates.py --cookie-guide
              python scripts/fetch_publish_dates.py --cookie-guide edge
        """),
    )
    parser.add_argument("--urls-file", type=Path, default=None,
                        help="Plain text file with one YouTube URL per line.")
    parser.add_argument("--cookies-file", type=Path, default=None,
                        help="Netscape-format cookies.txt file. Use this OR --browser.")
    parser.add_argument("--browser", type=str, default=None,
                        choices=VALID_BROWSERS,
                        help="Extract cookies from a browser. One of: {}.".format(
                            ", ".join(VALID_BROWSERS)))
    parser.add_argument("--output-file", type=Path, default=Path("published_dates_output.txt"))
    parser.add_argument("--failures-file", type=Path, default=Path("published_dates_failures.txt"))
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=4)

    args = parser.parse_args(remainder)

    if not args.urls_file:
        parser.error("the following arguments are required: --urls-file")

    if not args.cookies_file and not args.browser:
        parser.error("either --cookies-file or --browser is required")

    if args.urls_file and not args.urls_file.exists():
        parser.error(f"urls file not found: {args.urls_file}")

    return args


def _show_full_help() -> None:
    """Show full help including standalone modes."""
    print("usage: fetch_publish_dates.py --urls-file FILE (--cookies-file FILE | --browser BROWSER)")
    print()
    print("Fetch YouTube publish dates in bulk from a list of video URLs.")
    print()
    print("Main modes:")
    print("  --urls-file FILE      Text file with one YouTube URL per line")
    print("  --cookies-file FILE   Netscape-format cookies.txt (use this OR --browser)")
    print("  --browser BROWSER     Extract cookies from a browser (chrome, edge, firefox, ...)")
    print()
    print("Options:")
    print("  --output-file FILE    Output file (default: published_dates_output.txt)")
    print("  --failures-file FILE  Failures log (default: published_dates_failures.txt)")
    print("  --max-workers N       Parallel workers (default: 4)")
    print("  --timeout N           Seconds per request (default: 90)")
    print("  --retries N           Retries per failed URL (default: 4)")
    print()
    print("Standalone modes:")
    print("  --export-cookies BROWSER   Try to export cookies from a browser to a file")
    print("  --cookie-guide [BROWSER]   Show step-by-step manual cookie export instructions")
    print()
    print("Examples:")
    print("  python scripts/fetch_publish_dates.py --urls-file urls.txt --browser edge")
    print("  python scripts/fetch_publish_dates.py --urls-file urls.txt --cookies-file cookies.txt")
    print("  python scripts/fetch_publish_dates.py --export-cookies edge")
    print("  python scripts/fetch_publish_dates.py --cookie-guide")
    print("  python scripts/fetch_publish_dates.py --cookie-guide edge")


def _handle_export_cookies(browser: str) -> None:
    """Run cookie export and exit."""
    output = Path(f"{browser}_cookies.txt")
    success = try_export_cookies(browser, output)

    if success:
        print()
        print("Now run the main script with:")
        print(f"  python scripts/fetch_publish_dates.py \\")
        print(f"      --urls-file path/to/urls.txt \\")
        print(f"      --cookies-file {output}")
    else:
        print()
        print("Auto-export failed. You can export cookies manually:")
        print_cookie_guide(browser)

    raise SystemExit(0 if success else 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    urls = [line.strip() for line in args.urls_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    if not urls:
        print("error: urls file is empty")
        raise SystemExit(1)

    cookie_args = build_cookie_args(args.cookies_file, args.browser)

    results: list[str | None] = [None] * len(urls)
    failures: list[tuple[int, str, str | None]] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [
            executor.submit(fetch_one, index, url, cookie_args, args.timeout, args.retries)
            for index, url in enumerate(urls)
        ]
        for future in futures:
            index, value, failure = future.result()
            results[index] = value
            if failure:
                failures.append((index + 1, urls[index], failure))

    args.output_file.write_text(
        "\n".join(["published_date", *[(value or "") for value in results]]) + "\n",
        encoding="utf-8",
    )
    args.failures_file.write_text(
        "\n\n".join(f"#{index} {url}\n{failure}" for index, url, failure in failures),
        encoding="utf-8",
    )

    success_count = sum(1 for value in results if value)
    print(
        f"count={len(urls)} success={success_count} failures={len(failures)} output={args.output_file} errors={args.failures_file}"
    )

    # If there were failures with --browser, suggest alternatives
    if failures and args.browser:
        browser = args.browser
        print()
        print(f"[!] {len(failures)} URL(s) failed with --browser {browser}.")
        print(f"    Try exporting cookies manually:")
        print(f"        python scripts/fetch_publish_dates.py --cookie-guide {browser}")
        print(f"    Or attempt auto-export:")
        print(f"        python scripts/fetch_publish_dates.py --export-cookies {browser}")


if __name__ == "__main__":
    main()
