#!/usr/bin/env python3
"""
Multi-platform competitor scraping orchestrator.

Routes to the correct tool per platform:
  - Facebook, YouTube, LinkedIn → Metricool API
  - Instagram → Instaloader (via gravitas-data-manager) or Apify
  - TikTok → Instaloader or Apify

Usage:
    python scripts/scrape_competitor.py \\
        --competitors "Enfagrow:@enfagrowmy,Friso:@frisogoldmy" \\
        --platforms ig,fb,tt \\
        --from 2026-05-01 \\
        --to 2026-05-31 \\
        --ig-source instaloader \\
        --output-dir outputs/pitch-2026-06-22
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
_DATA_MANAGER_SCRIPTS = SKILL_DIR.parent / "gravitas-data-manager" / "scripts"
if str(_DATA_MANAGER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DATA_MANAGER_SCRIPTS))


def get_gateway_secret(secret_name: str) -> str:
    """Fetch a secret from gateway.shazan.me using the .env key."""
    env_file = Path.home() / ".gravitas-skills" / ".env"
    if not env_file.exists():
        raise RuntimeError("~/.gravitas-skills/.env not found. Run gravitas-gateway first.")

    # Parse .env
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    gateway_key = env_vars.get("GRAVITAS_GATEWAY_KEY", "")
    gateway_url = env_vars.get("GRAVITAS_GATEWAY_URL", "https://gateway.shazan.me")

    import urllib.request
    req = urllib.request.Request(
        f"{gateway_url}/secret/{secret_name}",
        headers={"x-api-key": gateway_key},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return data["value"]


def scrape_instagram_instaloader(username: str, profile_id: str, from_date: str, to_date: str, output_dir: Path):
    """Scrape Instagram via gravitas-data-manager's ingest script."""
    ingest_script = _DATA_MANAGER_SCRIPTS / "ingest_ig_posts.py"
    if not ingest_script.exists():
        raise RuntimeError(f"ingest_ig_posts.py not found at {ingest_script}")

    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / f"ig_{username}.json"

    cmd = [
        sys.executable, str(ingest_script),
        "--username", username.lstrip("@"),
        "--profile-id", profile_id,
        "--from", from_date,
        "--to", to_date,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ Instaloader scrape failed for {username}: {result.stderr[:500]}", file=sys.stderr)

    return {"platform": "instagram", "username": username, "source": "instaloader",
            "status": "ok" if result.returncode == 0 else "failed"}


def scrape_metricool(platform: str, handle: str, from_date: str, to_date: str) -> dict:
    """
    Pull data via Metricool API.
    The agent invokes the metricool skill — this function returns
    instructions that the SKILL.md flow interprets.
    """
    return {
        "platform": platform,
        "handle": handle,
        "source": "metricool",
        "note": f"Agent should load metricool skill and pull {platform} posts for {handle} "
                f"from {from_date} to {to_date}",
    }


def scrape_apify(platform: str, handle: str) -> dict:
    """Scrape via Apify using gateway API key."""
    try:
        apify_key = get_gateway_secret("APIFY_API_KEY")
    except Exception:
        apify_key = os.environ.get("APIFY_API_KEY", "")
    if not apify_key:
        raise RuntimeError("APIFY_API_KEY not available from gateway or environment")

    return {
        "platform": platform,
        "handle": handle,
        "source": "apify",
        "note": f"Use Apify actor for {platform} with handle {handle}. "
                f"API key available from gateway.",
    }


def run_scrape(competitors: dict, platforms: list[str], from_date: str, to_date: str,
               ig_source: str, output_dir: Path) -> list[dict]:
    """Execute scraping for all competitors across all platforms."""
    results = []

    for name, handles in competitors.items():
        for plat in platforms:
            handle = handles.get(plat, "")
            if not handle:
                continue

            print(f"\n🔍 Scraping {name} on {plat}...")

            if plat in ("fb", "yt", "li"):
                # Route to Metricool
                result = scrape_metricool(plat, handle, from_date, to_date)

            elif plat == "ig":
                username = handle.lstrip("@")
                if ig_source == "instaloader":
                    profile_id = handles.get("_profile_id", "unknown")
                    result = scrape_instagram_instaloader(username, profile_id, from_date, to_date, output_dir)
                else:
                    result = scrape_apify("instagram", handle)

            elif plat == "tt":
                if ig_source == "instaloader":
                    result = {"platform": "tiktok", "handle": handle, "source": "instaloader",
                              "note": f"Use Instaloader to scrape TikTok profile @{handle.lstrip('@')}"}
                else:
                    result = scrape_apify("tiktok", handle)

            result["competitor"] = name
            results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Scrape competitor social media posts")
    parser.add_argument("--competitors", required=True, help="JSON string: {name: {ig: handle, fb: url, ...}}")
    parser.add_argument("--platforms", default="ig,fb,tt,yt,li", help="Comma-separated platform codes")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--ig-source", default="instaloader", choices=["instaloader", "apify"])
    parser.add_argument("--output-dir", default="outputs/pitch-research")
    args = parser.parse_args()

    competitors = json.loads(args.competitors)
    platforms = [p.strip() for p in args.platforms.split(",")]
    output_dir = Path(args.output_dir)

    results = run_scrape(competitors, platforms, args.from_date, args.to_date,
                         args.ig_source, output_dir)

    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / "scrape_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✅ Scraping complete. {len(results)} platform-competitor pairs processed.")
    print(f"   Results saved to {results_file}")


if __name__ == "__main__":
    main()
