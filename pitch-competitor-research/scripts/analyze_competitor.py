#!/usr/bin/env python3
"""
AI analysis layer for competitor research.

Produces the 5-layer dossier from scraped posts + transcripts:
  1. Posts (already scraped)
  2. Campaigns (Gemini clustering)
  3. KOLs (deterministic from collab/tagged data)
  4. Content themes (Gemini from captions + transcripts)
  5. Cadence & benchmarks (computed)

Usage:
    python scripts/analyze_competitor.py \\
        --posts-file outputs/pitch-2026-06-22/posts_with_transcripts.json \\
        --output-dir outputs/pitch-2026-06-22 \\
        --gemini-key YOUR_KEY
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


# ── Layer 2: Campaign Detection (Gemini) ──

def detect_campaigns_gemini(posts: list[dict], api_key: str) -> list[dict]:
    """Use Gemini to cluster posts into campaigns."""
    if not api_key:
        return _detect_campaigns_fallback(posts)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Prepare batched post summaries (max ~50 posts per batch)
        post_summaries = []
        for i, p in enumerate(posts[:100]):  # Cap at 100 for prompt size
            date = p.get("created_at") or p.get("date", "")
            caption = (p.get("caption") or "")[:200]
            hashtags = p.get("hashtags", [])
            post_summaries.append(
                f"[{i}] {date} | {caption} | hashtags: {', '.join(hashtags[:5])}"
            )

        if len(post_summaries) < 5:
            return []  # Not enough data

        prompt = (
            "Analyze these social media posts and identify marketing campaigns.\n\n"
            + "\n".join(post_summaries)
            + "\n\nGroup posts into campaigns. For each campaign, return JSON with:\n"
            "- campaign_name: descriptive name\n"
            "- date_range: {from, to}\n"
            "- post_indices: list of post numbers [0], [1], etc.\n"
            "- key_message: main campaign message\n"
            "- hashtags: campaign hashtags used\n\n"
            "Return ONLY valid JSON array. Posts not in any campaign should not be listed."
        )

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)

        # Parse JSON from response
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n```", 1)[0]

        campaigns = json.loads(text)
        return campaigns

    except ImportError:
        return _detect_campaigns_fallback(posts)
    except Exception as e:
        print(f"⚠️ Gemini campaign detection failed: {e}", file=sys.stderr)
        return _detect_campaigns_fallback(posts)


def _detect_campaigns_fallback(posts: list[dict]) -> list[dict]:
    """Fallback: simple hashtag clustering when Gemini unavailable."""
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
        "follower_estimate": None,
    })

    for post in posts:
        # Check collab flag
        is_collab = post.get("is_collab") or post.get("raw", {}).get("is_collab")

        # Check tagged users
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

    # Convert to list and compute aggregates
    kols = []
    for username, data in kol_map.items():
        data["platforms"] = list(data["platforms"])
        data["avg_engagement"] = round(
            (data["total_likes"] + data["total_comments"]) / max(data["post_count"], 1), 1
        )
        data["content_type"] = _guess_content_type(data["kol_name"], posts)
        data["estimated_tier"] = _estimate_kol_tier(data["total_likes"], data["post_count"])
        # Clean up intermediate fields
        del data["total_likes"]
        del data["total_comments"]
        kols.append(data)

    return sorted(kols, key=lambda x: -x["post_count"])


def _guess_content_type(kol_name: str, posts: list[dict]) -> str:
    """Guess KOL content type from their posts. Simple heuristic."""
    # Default — can be enhanced with Gemini analysis
    return "collaborator"


def _estimate_kol_tier(avg_likes: int, post_count: int) -> str:
    """Estimate KOL tier based on engagement and post count."""
    if post_count >= 10 and avg_likes > 10000:
        return "macro"
    elif post_count >= 5 and avg_likes > 1000:
        return "mid"
    elif post_count >= 2:
        return "micro"
    return "nano"


# ── Layer 4: Content Themes (Gemini) ──

def analyze_themes(posts: list[dict], api_key: str) -> dict:
    """Analyze content themes from captions and transcripts."""
    if not api_key:
        return _analyze_themes_fallback(posts)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Sample captions and transcripts
        samples = []
        for p in posts[:50]:
            caption = (p.get("caption") or "")[:300]
            transcript = (p.get("transcript") or "")[:500]
            samples.append(f"Caption: {caption}\nTranscript: {transcript}\n---")

        prompt = (
            "Analyze these social media posts and identify content themes.\n\n"
            + "\n".join(samples)
            + "\n\nReturn JSON with:\n"
            "- themes: [{name, post_count, pct}, ...] — top 5-8 themes with distribution\n"
            "- tone: brief description of overall tone\n"
            "- visual_style: patterns in visuals\n"
            "- cta_patterns: common calls-to-action\n\n"
            "Return ONLY valid JSON."
        )

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n```", 1)[0]

        return json.loads(text)

    except ImportError:
        return _analyze_themes_fallback(posts)
    except Exception as e:
        print(f"⚠️ Theme analysis failed: {e}", file=sys.stderr)
        return _analyze_themes_fallback(posts)


def _analyze_themes_fallback(posts: list[dict]) -> dict:
    """Fallback: keyword frequency analysis."""
    all_text = " ".join([
        (p.get("caption") or "") + " " + (p.get("transcript") or "")
        for p in posts
    ]).lower()

    # Simple keyword buckets
    theme_keywords = {
        "Product benefits": ["manfaat", "kebaikan", "benefit", "nutrisi", "nutrition", "dha"],
        "Promo / contest": ["promo", "diskaun", "diskon", "giveaway", "menang", "contest"],
        "Parenting tips": ["parenting", "tips", "anak", "bayi", "baby", "ibubapa"],
        "Behind the scenes": ["behindthescenes", "bts", "proses", "team"],
        "KOL / testimonial": ["review", "testimoni", "cuba", "try", "recommend"],
        "Lifestyle": ["lifestyle", "harian", "daily", "routine", "rutin"],
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
        "tone": "Not analyzed (Gemini unavailable)",
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

    # Compute per-week averages (assuming data spans N weeks)
    result = {}
    for plat, data in cadence.items():
        if data["total"] == 0:
            continue
        # Rough week estimate: total posts / 4 weeks per month
        weeks = 4.3
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
        if views > 0:
            er = round((likes + comments) / views * 100, 2)
        else:
            er = 0

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

    # Format mix
    format_counts = Counter()
    for post in posts:
        platform = post.get("platform", "unknown")
        media_type = post.get("media_type") or post.get("post_type") or "unknown"
        format_counts[f"{platform}_{media_type}"] += 1

    total = sum(format_counts.values()) or 1
    format_mix = {k: round(v / total * 100, 1) for k, v in format_counts.most_common(10)}

    return {"engagement_benchmarks": result, "format_mix": format_mix}


# ── Main ──

def analyze(posts: list[dict], gemini_key: str) -> dict:
    """Run full 5-layer analysis."""
    print("\n📊 Running competitor analysis...")

    print("  Layer 2/5: Detecting campaigns...")
    campaigns = detect_campaigns_gemini(posts, gemini_key)
    print(f"    → {len(campaigns)} campaigns found")

    print("  Layer 3/5: Extracting KOLs...")
    kols = extract_kols(posts)
    print(f"    → {len(kols)} KOLs identified")

    print("  Layer 4/5: Analyzing content themes...")
    themes = analyze_themes(posts, gemini_key)
    print(f"    → {len(themes.get('themes', []))} themes identified")

    print("  Layer 5/5: Computing cadence & benchmarks...")
    cadence = compute_cadence(posts)
    benchmarks = compute_benchmarks(posts)

    return {
        "analyzed_at": datetime.now().isoformat(),
        "total_posts": len(posts),
        "platforms_covered": list(set(p.get("platform", "unknown") for p in posts)),
        "campaigns": campaigns,
        "kols": kols,
        "content_themes": themes,
        "cadence": cadence,
        "benchmarks": benchmarks,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze competitor posts")
    parser.add_argument("--posts-file", required=True, help="JSON file with posts (+ transcripts)")
    parser.add_argument("--output-dir", required=True, help="Output directory for analysis")
    parser.add_argument("--gemini-key", default="", help="Gemini API key")
    args = parser.parse_args()

    gemini_key = args.gemini_key or os.environ.get("GEMINI_API_KEY", "")

    with open(args.posts_file, encoding="utf-8") as f:
        posts = json.load(f)

    # Handle both list and dict formats
    if isinstance(posts, dict):
        posts = posts.get("posts", posts.get("results", []))

    output_dir = Path(args.output_dir)
    analysis = analyze(posts, gemini_key)

    # Save
    analysis_file = output_dir / "competitor_analysis.json"
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n✅ Analysis complete. Results saved to {analysis_file}")


if __name__ == "__main__":
    main()
