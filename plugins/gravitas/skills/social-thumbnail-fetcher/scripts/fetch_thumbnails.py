"""
Fetch thumbnail URLs from Instagram and TikTok posts.
Usage: python fetch_thumbnails.py [urls...] [--file urls.txt] [--output thumbnails.txt]
"""

import re
import sys
import json
import urllib.request
import urllib.error
import ssl

ssl_ctx = ssl.create_default_context()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

INSTA_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)"
)
TIKTOK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?tiktok\.com/@[\w.]+/video/(\d+)"
)


def instagram_thumbnail(shortcode: str) -> str | None:
    url = f"https://www.instagram.com/p/{shortcode}/media/?size=l"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
        return resp.url  # redirected to actual image
    except Exception:
        return None


def tiktok_thumbnail(video_id: str) -> str | None:
    url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@x/video/{video_id}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
        data = json.loads(resp.read())
        return data.get("thumbnail_url")
    except Exception:
        return None


def extract_urls(args: list[str]) -> list[str]:
    urls = []
    for arg in args:
        if arg.startswith("--file="):
            path = arg.split("=", 1)[1]
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append(line)
        elif arg.startswith("--"):
            continue
        elif arg.strip():
            urls.append(arg.strip())
    return urls


def main():
    output_file = None
    url_args = []

    for arg in sys.argv[1:]:
        if arg.startswith("--output="):
            output_file = arg.split("=", 1)[1]
        else:
            url_args.append(arg)

    urls = extract_urls(url_args)
    if not urls:
        print("Usage: python fetch_thumbnails.py <url...> [--file=urls.txt] [--output=thumbnails.txt]")
        sys.exit(1)

    results = []
    for url in urls:
        m = INSTA_RE.search(url)
        if m:
            thumb = instagram_thumbnail(m.group(1))
            results.append((url, thumb or "FAILED"))
            continue
        m = TIKTOK_RE.search(url)
        if m:
            thumb = tiktok_thumbnail(m.group(1))
            results.append((url, thumb or "FAILED"))
            continue
        results.append((url, "UNSUPPORTED URL"))

    lines = []
    for src, thumb in results:
        lines.append(f"{src}")
        lines.append(f"{thumb}")
        lines.append("")

    output = "\n".join(lines).rstrip("\n")

    if output_file:
        with open(output_file, "w") as f:
            f.write(output + "\n")
        print(f"Wrote {len(results)} thumbnail(s) to {output_file}")
    else:
        print(output)


if __name__ == "__main__":
    main()
