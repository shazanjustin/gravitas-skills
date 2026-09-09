#!/usr/bin/env python3
"""
Discover and validate competitor platform handles for pitch research.

Usage:
    python scripts/discover_competitors.py --competitors "Enfagrow:@enfagrowmy,Friso:@frisogoldmy" --platforms ig,fb,tt

Supports interactive mode (ask_user via agent) and CLI mode.
"""
import argparse
import json
import sys
import re
from pathlib import Path

# Resolve skill root and add gravitas-data-manager scripts to path
SKILL_DIR = Path(__file__).resolve().parent.parent
_DATA_MANAGER_SCRIPTS = SKILL_DIR.parent / "gravitas-data-manager" / "scripts"
if str(_DATA_MANAGER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DATA_MANAGER_SCRIPTS))

PLATFORM_PATTERNS = {
    "ig": {
        "label": "Instagram",
        "prefix": "@",
        "example": "@enfagrowmy",
        "pattern": re.compile(r"^@?[\w.]+$"),
    },
    "fb": {
        "label": "Facebook",
        "prefix": "",
        "example": "https://facebook.com/enfagrowmy",
        "pattern": re.compile(r"^(https?://)?(www\.)?facebook\.com/[\w.]+$|^@?[\w.]+$"),
    },
    "tt": {
        "label": "TikTok",
        "prefix": "@",
        "example": "@enfagrowmy",
        "pattern": re.compile(r"^@?[\w.]+$"),
    },
    "yt": {
        "label": "YouTube",
        "prefix": "",
        "example": "https://youtube.com/@enfagrowmy",
        "pattern": re.compile(r"^(https?://)?(www\.)?youtube\.com/@[\w.]+$|^@[\w.]+$"),
    },
    "li": {
        "label": "LinkedIn",
        "prefix": "",
        "example": "https://linkedin.com/company/enfagrow",
        "pattern": re.compile(r"^(https?://)?(www\.)?linkedin\.com/company/[\w.-]+$"),
    },
}


def parse_competitor_input(competitor_str: str) -> dict:
    """Parse 'Name:@handle,Name2:@handle2' into structured dict."""
    results = {}
    for entry in competitor_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            name, handle = entry.split(":", 1)
            results[name.strip()] = handle.strip()
        else:
            results[entry] = ""
    return results


def validate_handles(competitors: dict, platforms: list[str]) -> dict:
    """Validate each competitor's handles against platform patterns."""
    validated = {}
    for name, raw_handle in competitors.items():
        validated[name] = {"handles": {}, "warnings": []}
        for plat in platforms:
            info = PLATFORM_PATTERNS.get(plat)
            if not info:
                continue
            if raw_handle:
                if info["pattern"].match(raw_handle):
                    validated[name]["handles"][plat] = raw_handle
                else:
                    validated[name]["warnings"].append(
                        f"{info['label']} handle '{raw_handle}' doesn't match expected format "
                        f"(e.g., {info['example']})"
                    )
                    validated[name]["handles"][plat] = raw_handle  # keep anyway
            else:
                validated[name]["warnings"].append(
                    f"No {info['label']} handle provided for {name}"
                )
    return validated


def discover_missing_handles(competitors: dict, platforms: list[str]) -> list[dict]:
    """
    After initial scrape, check for @mentions and tagged accounts
    not in the original list. Returns suggestions.
    """
    suggestions = []
    # This would be populated after U2 scraping runs.
    # For now, returns empty — agent calls this post-scrape.
    return suggestions


def format_for_agent(validated: dict) -> str:
    """Format discovery results for agent display."""
    lines = []
    for name, data in validated.items():
        lines.append(f"\n📋 **{name}**")
        for plat, handle in data["handles"].items():
            label = PLATFORM_PATTERNS[plat]["label"]
            lines.append(f"  {label}: {handle}")
        for warning in data["warnings"]:
            lines.append(f"  ⚠️ {warning}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Discover competitor platform handles")
    parser.add_argument("--competitors", required=True, help="Comma-separated Name:Handle pairs")
    parser.add_argument("--platforms", default="ig,fb,tt,yt,li", help="Comma-separated platform codes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--validate-only", action="store_true", help="Validate without Supabase lookup")
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",")]
    competitors = parse_competitor_input(args.competitors)
    validated = validate_handles(competitors, platforms)

    if args.json:
        print(json.dumps(validated, indent=2))
    else:
        print(format_for_agent(validated))

    # Exit with warning code if any warnings
    has_warnings = any(data["warnings"] for data in validated.values())
    sys.exit(1 if has_warnings else 0)


if __name__ == "__main__":
    main()
