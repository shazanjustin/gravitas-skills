---
name: social-thumbnail-fetcher
description: |
  Fetch thumbnail image URLs from Instagram (posts/reels) and TikTok video
  URLs. Returns direct image links you can open, embed, or download.
compatibility: |
  Requires Python 3.8+ and `requests` (`pip install requests`).
---

# Social Thumbnail Fetcher

Given Instagram or TikTok URLs, returns the direct thumbnail image URL for
each one. No login or cookies required.

## What it does

- **Instagram** — works for both `/p/` posts and `/reel/` reels
- **TikTok** — works for any public video
- Outputs source URL + thumbnail URL per post, grouped with blank lines
- Supports `--file=` for bulk URLs and `--output=` to save to a file

## Usage

```bash
# One or more URLs as arguments
python scripts/fetch_thumbnails.py \
  "https://www.instagram.com/reel/ABC123/" \
  "https://www.tiktok.com/@user/video/1234567890"

# From a file (one URL per line, # for comments)
python scripts/fetch_thumbnails.py --file=urls.txt

# Save to a file
python scripts/fetch_thumbnails.py \
  --file=urls.txt --output=thumbnails.txt

# Combined
python scripts/fetch_thumbnails.py \
  "https://www.instagram.com/reel/ABC123/" \
  --file=more_urls.txt \
  --output=results.txt
```

Output format:
```
<source_url>
<thumbnail_url>

<source_url>
<thumbnail_url>
```

## How it works (no secrets needed)

- **Instagram**: hits `https://www.instagram.com/p/{id}/media/?size=l` and
  follows the redirect to the actual CDN image URL
- **TikTok**: uses the public oEmbed endpoint
  `https://www.tiktok.com/oembed?url=...` and reads `thumbnail_url`
- No API keys, no cookies, no browser emulation

## Limitations

- **Instagram**: returns the square/low-res thumbnail for reels (same as the
  preview you see before tapping). Use yt-dlp if you need the full video.
- **TikTok**: oEmbed thumbnails are signed URLs that expire — download them
  promptly if you need to keep them.
- Private/age-restricted posts will fail.
