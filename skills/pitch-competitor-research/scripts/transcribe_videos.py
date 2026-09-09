#!/usr/bin/env python3
"""
Video download and transcription pipeline for competitor research.

Downloads videos via yt-dlp, transcribes via OpenRouter API
(Gemini Flash for video, or any model for text-based analysis).

Usage:
    python scripts/transcribe_videos.py \\
        --posts-file outputs/pitch-2026-06-22/scrape_results.json \\
        --output-dir outputs/pitch-2026-06-22 \\
        --openrouter-key YOUR_KEY
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# OpenRouter supports Gemini Flash for video understanding
TRANSCRIPTION_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def download_video(post_url: str, output_dir: Path) -> Path | None:
    """Download a video using yt-dlp. Returns path to downloaded file or None."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize", "500M",
        "-o", output_template,
        post_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  ⚠️ Download failed: {result.stderr[:200]}", file=sys.stderr)
            return None

        for f in output_dir.iterdir():
            if f.suffix in (".mp4", ".webm", ".mkv", ".mov"):
                return f
        return None
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Download timed out for {post_url}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("  ❌ yt-dlp not found. Install with: pip install yt-dlp", file=sys.stderr)
        return None


def extract_audio(video_path: Path) -> Path | None:
    """Extract audio from video using ffmpeg. Returns path to mp3 file."""
    audio_path = video_path.with_suffix(".mp3")
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn", "-ar", "16000", "-ac", "1",
        "-b:a", "64k", "-y", str(audio_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and audio_path.exists():
            return audio_path
    except Exception:
        pass
    return None


def transcribe_via_openrouter(video_path: Path, api_key: str) -> str | None:
    """
    Transcribe video using OpenRouter with Gemini Flash.
    Sends video as base64 in a multimodal request.
    """
    import requests

    try:
        # Read video and encode as base64
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        # If file is too large (>20MB), extract audio and transcribe that instead
        if len(video_bytes) > 20 * 1024 * 1024:
            print("  ↪ Video >20MB, extracting audio for transcription...")
            audio_path = extract_audio(video_path)
            if audio_path:
                with open(audio_path, "rb") as f:
                    video_bytes = f.read()
                try:
                    audio_path.unlink()
                except Exception:
                    pass
            else:
                print("  ⚠️ Audio extraction failed, trying video anyway...", file=sys.stderr)

        video_b64 = base64.b64encode(video_bytes).decode("utf-8")
        mime_type = "video/mp4" if video_path.suffix == ".mp4" else "video/webm"

        payload = {
            "model": TRANSCRIPTION_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe this video word-for-word. Include speaker labels if multiple speakers. Return ONLY the transcript text, no commentary."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{video_b64}"
                        }
                    }
                ]
            }]
        }

        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if resp.status_code != 200:
            print(f"  ⚠️ OpenRouter error {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
            return None

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else None

    except ImportError:
        print("  ⚠️ requests not installed. pip install requests", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠️ Transcription error: {e}", file=sys.stderr)
        return None


def transcribe_posts(posts: list[dict], output_dir: Path, openrouter_key: str) -> list[dict]:
    """Transcribe all video posts via OpenRouter."""
    video_dir = output_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    video_posts = [p for p in posts if p.get("media_type") in ("video", "reel", "VIDEO")]
    if not video_posts:
        print("ℹ️ No video posts to transcribe.")
        return posts

    print(f"\n🎬 Transcribing {len(video_posts)} videos via OpenRouter ({TRANSCRIPTION_MODEL})...")
    transcribed = 0
    skipped = 0

    for i, post in enumerate(video_posts):
        post_url = post.get("permalink") or post.get("post_url") or post.get("url", "")
        if not post_url:
            skipped += 1
            post["transcript"] = None
            post["transcript_error"] = "No video URL available"
            continue

        print(f"  [{i+1}/{len(video_posts)}] {post_url[:80]}...")

        video_path = download_video(post_url, video_dir)
        if not video_path:
            skipped += 1
            post["transcript"] = None
            post["transcript_error"] = "Download failed"
            continue

        transcript = transcribe_via_openrouter(video_path, openrouter_key)

        if transcript:
            post["transcript"] = transcript
            post["transcript_source"] = TRANSCRIPTION_MODEL
            transcribed += 1
        else:
            post["transcript"] = None
            post["transcript_error"] = "Transcription failed"
            skipped += 1

        # Clean up video file
        try:
            video_path.unlink()
        except Exception:
            pass

    print(f"\n✅ Transcription complete: {transcribed} succeeded, {skipped} skipped/failed")
    return posts


def main():
    parser = argparse.ArgumentParser(description="Download and transcribe competitor videos")
    parser.add_argument("--posts-file", required=True, help="JSON file with posts from scrape")
    parser.add_argument("--output-dir", required=True, help="Output directory for videos and results")
    parser.add_argument("--openrouter-key", default="", help="OpenRouter API key")
    args = parser.parse_args()

    openrouter_key = args.openrouter_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        print("❌ No OpenRouter API key. Set OPENROUTER_API_KEY env var or pass --openrouter-key.", file=sys.stderr)
        sys.exit(1)

    with open(args.posts_file) as f:
        posts = json.load(f)

    output_dir = Path(args.output_dir)
    posts = transcribe_posts(posts, output_dir, openrouter_key)

    transcript_file = output_dir / "posts_with_transcripts.json"
    with open(transcript_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False, default=str)

    print(f"   Transcripts saved to {transcript_file}")


if __name__ == "__main__":
    main()
