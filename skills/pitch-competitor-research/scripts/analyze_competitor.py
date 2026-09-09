#!/usr/bin/env python3
"""
AI analysis layer for competitor research via OpenRouter.

Produces the 5-layer dossier from scraped posts + transcripts:
  1. Posts (already scraped)
  2. Campaigns (AI clustering via OpenRouter)
  3. KOLs (deterministic from collab/tagged data)
  4. Content themes (AI from captions + transcripts via OpenRouter)
  5. Cadence & benchmarks (computed)

Usage:
    python scripts/analyze_competitor.py \\
        --posts-file outputs/pitch-2026-06-22/posts_with_transcripts.json \\
        --output-dir outputs/pitch-2026-06-22 \\
        --openrouter-key YOUR_KEY
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests

SKILL_DIR = Path(__file__).resolve().parent.parent

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ANALYSIS_MODEL = "google/gemini-2.0-flash-001"


def call_openrouter(prompt: str, api_key: str, system: str = "") -> str | None:
    """Call OpenRouter chat completions API and return response text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": ANALYSIS_MODEL, "messages": messages},
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"  ⚠️ OpenRouter error {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
            return None

        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ⚠️ OpenRouter call failed: {e}", file=sys.stderr)
        return None


def parse_json_response(text: str) -> dict | list | None:
    """Extract JSON from an AI response that may have markdown wrapping."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON block
        import re
        match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None


# ── Layer 2: Campaign Detection ──

def detect_campaigns(posts: list[dict], api_key: str) -> list[dict]:
    """Use OpenRouter to cluster posts into campaigns."""
    if not api_key or len(posts) < 5:
        return _detect_campaigns_fallback(posts)

    post_summaries = []
    for i, p in enumerate(posts[:100]):
        date = p.get("created_at") or p.get("date", "")
        caption = (p.get("caption") or "")[:200]
        hashtags = p.get("hashtags", [])
        post_summaries.append(
            f"[{i}] {date} | {caption} | hashtags: {', '.join(hashtags[:5])}"
        )

    prompt = (
        "Analyze these social media posts and identify marketing campaigns.\n\n"
        + "\n".join(post_summaries)
        + "\n\nGroup posts into campaigns. Return ONLY a JSON array. Each campaign object:\n"
        '{"campaign_name": "...", "date_range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}, '
        '"post_indices": [0, 1, ...], "key_message": "...", "hashtags": ["..."]}\n\n'
        "Posts not in any campaign should NOT be listed."
    )

    response = call_openrouter(prompt, api_key)
    if response:
        campaigns = parse_json_response(response)
        if isinstance(campaigns, list):
            return campaigns

    return _detect_campaigns_fallback(posts)


def _detect_campaigns_fallback(posts: list[dict]) -> list[dict]:
    """Fallback: simple hashtag clustering."""
    hashtag_groups = defaultdict(list)
    for i, p in enumerate(posts):
        for tag in p.get("hashtags", []):
            hashtag_groups[tag.lower()].append(i)

    campaigns = []
    seen_indices = set()
    for tag, indices in sorted(hashtag_groups.items(), key=lambda x: -len(x[1])):
        new_indices = [i for i in indices if i not in seen_indices]
        if len(new_indices) >= 3:
            dates = [posts[i].get("created_at", "") for i in new_indices]
            campaigns.append({
                "campaign_name": f"#{tag}",
                "date_range": {"from": min(dates), "to": max(dates)},
                "post_indices": new_indices,
                "key_message": f"Posts using #{tag}",
                "hashtags": [tag],
                "detection": "fallback_hashtag",
            })
            seen_indices.update(new_indices)
    return campaigns


# ── Layer 3: KOL Extraction (Deterministic) ──

def extract_kols(posts: list[dict]) -> list[dict]:
    """Extract KOLs from collab flags and tagged users."""
    kol_map = defaultdict(lambda: {
        "kol_name": "",
        "platforms": set(),
        "post_count": 0,
        "total_likes": 0,
        "total_comments": 0,
        "posts": [],
    })

    for post in posts:
        is_collab = post.get("is_collab") or post.get("raw", {}).get("is_collab")
        tagged = post.get("tagged_users") or post.get("raw", {}).get("tagged_users", [])

        users_to_record = set()
        if is_collab:
            owner = post.get("owner_username") or post.get("username", "")
            if owner:
                users_to_record.add(owner)

        for user in tagged:
            if isinstance(user, str):
                users_to_record.add(user.lstrip("@"))
            elif isinstance(user, dict):
                users_to_record.add(user.get("username", "").lstrip("@"))

        for username in users_to_record:
            if not username:
                continue
            kol = kol_map[username]
            kol["kol_name"] = username
            kol["platforms"].add(post.get("platform", "instagram"))
            kol["post_count"] += 1
            kol["total_likes"] += int(post.get("likes") or post.get("raw", {}).get("likes", 0))
            kol["total_comments"] += int(post.get("comments") or post.get("raw", {}).get("comments", 0))
            kol["posts"].append(post.get("permalink") or post.get("post_url", ""))

    kols = []
    for username, data in kol_map.items():
        data["platforms"] = list(data["platforms"])
        data["avg_engagement"] = round(
            (data["total_likes"] + data["total_comments"]) / max(data["post_count"], 1), 1
        )
        data["estimated_tier"] = _estimate_kol_tier(data["post_count"])
        del data["total_likes"]
        del data["total_comments"]
        kols.append(data)

    return sorted(kols, key=lambda x: -x["post_count"])


def _estimate_kol_tier(post_count: int) -> str:
    if post_count >= 10:
        return "macro"
    elif post_count >= 5:
        return "mid"
    elif post_count >= 2:
        return "micro"
    return "nano"


# ── Layer 4: Content Themes ──

def analyze_themes(posts: list[dict], api_key: str) -> dict:
    """Analyze content themes from captions and transcripts via OpenRouter."""
    if not api_key:
        return _analyze_themes_fallback(posts)

    samples = []
    for p in posts[:50]:
        caption = (p.get("caption") or "")[:300]
        transcript = (p.get("transcript") or "")[:500]
        samples.append(f"Caption: {caption}\nTranscript: {transcript}\n---")

    prompt = (
        "Analyze these social media posts and identify content themes.\n\n"
        + "\n".join(samples)
        + "\n\nReturn ONLY valid JSON with:\n"
        '"themes": [{"name": "...", "post_count": N, "pct": N.N}, ...] — top 5-8 themes\n'
        '"tone": "brief description of overall tone",\n'
        '"visual_style": "patterns in visuals",\n'
        '"cta_patterns": ["common CTA 1", "common CTA 2"]\n'
    )

    response = call_openrouter(prompt, api_key)
    if response:
        result = parse_json_response(response)
        if isinstance(result, dict):
            return result

    return _analyze_themes_fallback(posts)


def _analyze_themes_fallback(posts: list[dict]) -> dict:
    """Fallback: keyword frequency analysis."""
    all_text = " ".join([
        (p.get("caption") or "") + " " + (p.get("transcript") or "")
        for p in posts
    ]).lower()

    theme_keywords = {
        "Product benefits": ["manfaat", "kebaikan", "benefit", "nutrisi", "nutrition", "dha"],
        "Promo / contest": ["promo", "diskaun", "giveaway", "menang", "contest"],
        "Parenting tips": ["parenting", "tips", "anak", "bayi", "baby"],
        "Behind the scenes": ["behindthescenes", "bts", "proses", "team"],
        "KOL / testimonial": ["review", "testimoni", "cuba", "recommend"],
        "Lifestyle": ["lifestyle", "harian", "daily", "routine"],
    }

    themes = []
    for theme_name, keywords in theme_keywords.items():
        count = sum(all_text.count(kw) for kw in keywords)
        if count > 0:
            themes.append({"name": theme_name, "post_count": count, "pct": 0})

    total = sum(t["post_count"] for t in themes) or 1
    for t in themes:
        t["pct"] = round(t["post_count"] / total * 100, 1)

    return {
        "themes": sorted(themes, key=lambda x: -x["post_count"])[:6],
        "tone": "Not analyzed (OpenRouter unavailable)",
        "visual_style": "Not analyzed",
        "cta_patterns": [],
    }


# ── Layer 5: Cadence & Benchmarks (Computed) ──

def compute_cadence(posts: list[dict]) -> dict:
    """Compute posting frequency by platform, day, and time."""
    cadence = {}
    for post in posts:
        platform = post.get("platform", "unknown")
        if platform not in cadence:
            cadence[platform] = {"day_counts": Counter(), "hour_counts": Counter(), "total": 0}

        date_str = post.get("created_at") or post.get("date", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                cadence[platform]["day_counts"][dt.strftime("%A")] += 1
                cadence[platform]["hour_counts"][dt.hour] += 1
                cadence[platform]["total"] += 1
            except (ValueError, TypeError):
                pass

    result = {}
    weeks = 4.3
    for plat, data in cadence.items():
        if data["total"] == 0:
            continue
        result[plat] = {
            "posts_per_week": round(data["total"] / weeks, 1),
            "best_day": data["day_counts"].most_common(1)[0][0] if data["day_counts"] else "unknown",
            "best_time": f"{data['hour_counts'].most_common(1)[0][0]:02d}:00"
                         if data["hour_counts"] else "unknown",
        }
    return result


def compute_benchmarks(posts: list[dict]) -> dict:
    """Compute engagement benchmarks by format and platform."""
    benchmarks = defaultdict(lambda: {"total_er": 0, "count": 0, "er_values": []})

    for post in posts:
        platform = post.get("platform", "unknown")
        media_type = post.get("media_type") or post.get("post_type") or "unknown"
        likes = int(post.get("likes") or post.get("raw", {}).get("likes", 0))
        comments = int(post.get("comments") or post.get("raw", {}).get("comments", 0))
        views = int(post.get("views") or post.get("video_view_count") or
                    post.get("raw", {}).get("video_view_count", 0))

        key = f"{platform}_{media_type}"
        er = round((likes + comments) / views * 100, 2) if views > 0 else 0
        benchmarks[key]["total_er"] += er
        benchmarks[key]["count"] += 1
        benchmarks[key]["er_values"].append(er)

    result = {}
    for key, data in benchmarks.items():
        if data["count"] == 0:
            continue
        sorted_ers = sorted(data["er_values"])
        mid = len(sorted_ers) // 2
        result[key] = {
            "avg_er": round(data["total_er"] / data["count"], 2),
            "median_er": round(sorted_ers[mid], 2) if sorted_ers else 0,
            "post_count": data["count"],
        }

    format_counts = Counter()
    for post in posts:
        platform = post.get("platform", "unknown")
        media_type = post.get("media_type") or post.get("post_type") or "unknown"
        format_counts[f"{platform}_{media_type}"] += 1

    total = sum(format_counts.values()) or 1
    format_mix = {k: round(v / total * 100, 1) for k, v in format_counts.most_common(10)}

    return {"engagement_benchmarks": result, "format_mix": format_mix}


# ── Main ──

def analyze(posts: list[dict], openrouter_key: str) -> dict:
    """Run full 5-layer analysis."""
    print("\n📊 Running competitor analysis...")

    print("  Layer 2/5: Detecting campaigns...")
    campaigns = detect_campaigns(posts, openrouter_key)
    print(f"    → {len(campaigns)} campaigns found")

    print("  Layer 3/5: Extracting KOLs...")
    kols = extract_kols(posts)
    print(f"    → {len(kols)} KOLs identified")

    print("  Layer 4/5: Analyzing content themes...")
    themes = analyze_themes(posts, openrouter_key)
    print(f"    → {len(themes.get('themes', []))} themes identified")

    print("  Layer 5/5: Computing cadence & benchmarks...")
    cadence = compute_cadence(posts)
    benchmarks = compute_benchmarks(posts)

    return {
        "analyzed_at": datetime.now().isoformat(),
        "analysis_model": ANALYSIS_MODEL,
        "total_posts": len(posts),
        "platforms_covered": list(set(p.get("platform", "unknown") for p in posts)),
        "campaigns": campaigns,
        "kols": kols,
        "content_themes": themes,
        "cadence": cadence,
        "benchmarks": benchmarks,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze competitor posts via OpenRouter")
    parser.add_argument("--posts-file", required=True, help="JSON file with posts (+ transcripts)")
    parser.add_argument("--output-dir", required=True, help="Output directory for analysis")
    parser.add_argument("--openrouter-key", default="", help="OpenRouter API key")
    args = parser.parse_args()

    openrouter_key = args.openrouter_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        print("❌ No OpenRouter API key. Set OPENROUTER_API_KEY or pass --openrouter-key.", file=sys.stderr)
        sys.exit(1)

    with open(args.posts_file, encoding="utf-8") as f:
        posts = json.load(f)

    if isinstance(posts, dict):
        posts = posts.get("posts", posts.get("results", []))

    output_dir = Path(args.output_dir)
    analysis = analyze(posts, openrouter_key)

    analysis_file = output_dir / "competitor_analysis.json"
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n✅ Analysis complete. Results saved to {analysis_file}")


if __name__ == "__main__":
    main()
