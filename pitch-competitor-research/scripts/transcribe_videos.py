#!/usr/bin/env python3
"""
Video download and transcription pipeline for competitor research.

Downloads videos via yt-dlp, transcribes via Gemini API (primary)
or OpenAI Whisper API (fallback).

Usage:
    python scripts/transcribe_videos.py \\
        --posts-file outputs/pitch-2026-06-22/scrape_results.json \\
        --output-dir outputs/pitch-2026-06-22 \\
        --gemini-key YOUR_KEY
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


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

        # Find the downloaded file
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


def transcribe_gemini(video_path: Path, api_key: str) -> str | None:
    """Transcribe video using Gemini API."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Upload video file
        video_file = genai.upload_file(str(video_path))

        # Wait for processing
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            print(f"  ⚠️ Gemini processing failed for {video_path.name}", file=sys.stderr)
            return None

        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Transcribe this video word-for-word. "
            "Include speaker labels if multiple speakers are present. "
            "Return only the transcript text, no commentary."
        )
        response = model.generate_content([prompt, video_file])
        return response.text if response.text else None

    except ImportError:
        print("  ⚠️ google-generativeai not installed. pip install google-generativeai", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠️ Gemini transcription error: {e}", file=sys.stderr)
        return None
    finally:
        # Clean up uploaded file from Gemini
        try:
            if 'video_file' in locals():
                genai.delete_file(video_file.name)
        except Exception:
            pass


def transcribe_openai(video_path: Path, api_key: str) -> str | None:
    """Transcribe using OpenAI Whisper API (fallback). Extract audio first."""
    try:
        from openai import OpenAI

        # Extract audio with ffmpeg
        audio_path = video_path.with_suffix(".mp3")
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vn", "-ar", "16000", "-ac", "1",
            "-b:a", "64k", "-y", str(audio_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"  ⚠️ Audio extraction failed: {result.stderr[:200]}", file=sys.stderr)
            return None

        client = OpenAI(api_key=api_key)
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
            )

        # Clean up audio
        try:
            audio_path.unlink()
        except Exception:
            pass

        return transcript if isinstance(transcript, str) else str(transcript)

    except ImportError:
        print("  ⚠️ openai not installed. pip install openai", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠️ OpenAI transcription error: {e}", file=sys.stderr)
        return None


def transcribe_posts(posts: list[dict], output_dir: Path,
                     gemini_key: str, openai_key: str = "") -> list[dict]:
    """Transcribe all video posts. Returns posts with transcript field added."""
    video_dir = output_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    video_posts = [p for p in posts if p.get("media_type") in ("video", "reel", "VIDEO")]
    if not video_posts:
        print("ℹ️ No video posts to transcribe.")
        return posts

    print(f"\n🎬 Transcribing {len(video_posts)} videos...")
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

        # Download
        video_path = download_video(post_url, video_dir)
        if not video_path:
            skipped += 1
            post["transcript"] = None
            post["transcript_error"] = "Download failed"
            continue

        # Transcribe (Gemini first, OpenAI fallback)
        transcript = None
        if gemini_key:
            transcript = transcribe_gemini(video_path, gemini_key)

        if not transcript and openai_key:
            print(f"  ↪ Falling back to OpenAI Whisper...")
            transcript = transcribe_openai(video_path, openai_key)

        if transcript:
            post["transcript"] = transcript
            post["transcript_source"] = "gemini" if gemini_key and transcript else "openai"
            transcribed += 1
        else:
            post["transcript"] = None
            post["transcript_error"] = "Transcription failed (both Gemini and OpenAI)"
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
    parser.add_argument("--gemini-key", default="", help="Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--openai-key", default="", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    args = parser.parse_args()

    gemini_key = args.gemini_key or os.environ.get("GEMINI_API_KEY", "")
    openai_key = args.openai_key or os.environ.get("OPENAI_API_KEY", "")

    if not gemini_key and not openai_key:
        print("❌ No API keys provided. Set GEMINI_API_KEY or OPENAI_API_KEY.", file=sys.stderr)
        sys.exit(1)

    with open(args.posts_file) as f:
        posts = json.load(f)

    output_dir = Path(args.output_dir)
    posts = transcribe_posts(posts, output_dir, gemini_key, openai_key)

    # Save updated posts
    transcript_file = output_dir / "posts_with_transcripts.json"
    with open(transcript_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False, default=str)

    print(f"   Transcripts saved to {transcript_file}")


if __name__ == "__main__":
    main()
