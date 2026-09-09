#!/usr/bin/env python3
"""
Generate executive brief HTML from competitor analysis.

Usage:
    python scripts/generate_html_report.py \\
        --analysis-file outputs/pitch-2026-06-22/competitor_analysis.json \\
        --output-dir outputs/pitch-2026-06-22 \\
        --title "Friso Gold Pitch — Competitor Research"
"""
import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "templates"


def load_template() -> str:
    """Load the HTML template."""
    template_path = TEMPLATE_DIR / "executive_brief.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return _build_inline_template()


def _build_inline_template() -> str:
    """Built-in template — used when template file is missing."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; background: #f8f9fa; line-height: 1.6; }
.container { max-width: 1100px; margin: 0 auto; padding: 40px 24px; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 48px 40px; border-radius: 12px; margin-bottom: 32px; }
.header h1 { font-size: 2rem; margin-bottom: 8px; }
.header .meta { opacity: 0.8; font-size: 0.9rem; }
.summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 40px; }
.card { background: white; border-radius: 10px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card h3 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; margin-bottom: 12px; }
.section { margin-bottom: 40px; }
.section h2 { font-size: 1.4rem; margin-bottom: 20px; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }
table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
th { background: #f1f5f9; text-align: left; padding: 12px 16px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }
td { padding: 12px 16px; border-top: 1px solid #f1f5f9; font-size: 0.9rem; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 100px; font-size: 0.75rem; font-weight: 600; }
.badge-ig { background: #fdf2f8; color: #be185d; }
.badge-fb { background: #eff6ff; color: #1d4ed8; }
.badge-tt { background: #fef2f2; color: #000; }
.badge-yt { background: #fef2f2; color: #dc2626; }
.badge-li { background: #eff6ff; color: #2563eb; }
.bar-chart { margin: 16px 0; }
.bar-row { display: flex; align-items: center; margin-bottom: 8px; }
.bar-label { width: 140px; font-size: 0.85rem; text-align: right; padding-right: 12px; }
.bar-track { flex: 1; background: #f1f5f9; border-radius: 4px; height: 24px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.bar-value { width: 50px; font-size: 0.8rem; padding-left: 8px; color: #6b7280; }
.heatmap { display: grid; grid-template-columns: 80px repeat(7, 1fr); gap: 2px; font-size: 0.8rem; }
.heatmap-cell { padding: 8px 4px; text-align: center; border-radius: 3px; }
.heatmap-header { font-weight: 600; color: #6b7280; }
.heatmap-label { text-align: right; padding-right: 8px; color: #6b7280; }
.campaign-timeline { position: relative; padding: 20px 0; }
.campaign-bar { display: flex; align-items: center; margin-bottom: 12px; padding: 12px 16px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.campaign-name { font-weight: 600; min-width: 200px; }
.campaign-date { font-size: 0.85rem; color: #6b7280; margin: 0 16px; }
.campaign-msg { font-size: 0.85rem; color: #374151; flex: 1; }
.warning { background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 16px; margin-bottom: 24px; font-size: 0.9rem; }
.empty-state { text-align: center; padding: 40px; color: #9ca3af; }
.footer { text-align: center; padding: 32px; color: #9ca3af; font-size: 0.8rem; border-top: 1px solid #e5e7eb; margin-top: 48px; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>{{ title }}</h1>
  <div class="meta">Generated {{ date }} &middot; {{ competitor_count }} competitors &middot; {{ platform_list }}</div>
</div>

{{#quick_mode}}
<div class="warning">⚡ <strong>Quick mode</strong> — video content not analyzed. Run full mode for transcript-based theme analysis.</div>
{{/quick_mode}}

<!-- Executive Summary -->
<div class="section">
  <h2>📋 Executive Summary</h2>
  <div class="summary-cards">
    {{#summary_cards}}
    <div class="card">
      <h3>{{ label }}</h3>
      <p>{{ value }}</p>
    </div>
    {{/summary_cards}}
  </div>
</div>

<!-- Competitors -->
{{#competitors}}
<div class="section">
  <h2>🏢 {{ name }}</h2>
  <table>
    <tr><th>Platform</th><th>Posts</th><th>Avg ER</th><th>Top Format</th><th>Posting Freq</th></tr>
    {{#platform_stats}}
    <tr>
      <td><span class="badge badge-{{ platform }}">{{ platform_label }}</span></td>
      <td>{{ post_count }}</td>
      <td>{{ avg_er }}%</td>
      <td>{{ top_format }}</td>
      <td>{{ posts_per_week }}/week</td>
    </tr>
    {{/platform_stats}}
  </table>
</div>
{{/competitors}}

<!-- Campaign Timeline -->
<div class="section">
  <h2>📅 Campaigns</h2>
  {{#has_campaigns}}
  <div class="campaign-timeline">
    {{#campaigns}}
    <div class="campaign-bar">
      <div class="campaign-name">{{ campaign_name }}</div>
      <div class="campaign-date">{{ date_range.from }} → {{ date_range.to }}</div>
      <div class="campaign-msg">{{ key_message }}</div>
    </div>
    {{/campaigns}}
  </div>
  {{/has_campaigns}}
  {{^has_campaigns}}
  <div class="empty-state">No campaigns detected.</div>
  {{/has_campaigns}}
</div>

<!-- KOL Roster -->
<div class="section">
  <h2>👥 KOL Collaborations</h2>
  {{#has_kols}}
  <table>
    <tr><th>KOL</th><th>Platforms</th><th>Posts</th><th>Avg ER</th><th>Est. Tier</th><th>Links</th></tr>
    {{#kols}}
    <tr>
      <td>@{{ kol_name }}</td>
      <td>{{#platforms}}<span class="badge badge-{{.}}">{{.}}</span> {{/platforms}}</td>
      <td>{{ post_count }}</td>
      <td>{{ avg_engagement }}%</td>
      <td>{{ estimated_tier }}</td>
      <td>{{#posts}}<a href="{{.}}" target="_blank">post</a> {{/posts}}</td>
    </tr>
    {{/kols}}
  </table>
  {{/has_kols}}
  {{^has_kols}}
  <div class="empty-state">No KOL collaborations detected.</div>
  {{/has_kols}}
</div>

<!-- Content Themes -->
<div class="section">
  <h2>📊 Content Themes</h2>
  {{#has_themes}}
  <div class="bar-chart">
    {{#themes}}
    <div class="bar-row">
      <div class="bar-label">{{ name }}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{{ pct }}%; background: {{ color }};"></div></div>
      <div class="bar-value">{{ pct }}%</div>
    </div>
    {{/themes}}
  </div>
  <p style="margin-top: 16px; font-size: 0.9rem;"><strong>Tone:</strong> {{ tone }}</p>
  <p style="font-size: 0.9rem;"><strong>CTAs:</strong> {{ cta_patterns }}</p>
  {{/has_themes}}
  {{^has_themes}}
  <div class="empty-state">Theme analysis unavailable.</div>
  {{/has_themes}}
</div>

<!-- Cadence -->
<div class="section">
  <h2>⏰ Posting Cadence</h2>
  {{#has_cadence}}
  <table>
    <tr><th>Platform</th><th>Posts/Week</th><th>Best Day</th><th>Best Time</th></tr>
    {{#cadence}}
    <tr>
      <td><span class="badge badge-{{ platform }}">{{ platform }}</span></td>
      <td>{{ posts_per_week }}</td>
      <td>{{ best_day }}</td>
      <td>{{ best_time }}</td>
    </tr>
    {{/cadence}}
  </table>
  {{/has_cadence}}
  {{^has_cadence}}
  <div class="empty-state">Cadence data unavailable.</div>
  {{/has_cadence}}
</div>

<!-- Benchmarks -->
<div class="section">
  <h2>📈 Engagement Benchmarks</h2>
  {{#has_benchmarks}}
  <table>
    <tr><th>Platform / Format</th><th>Avg ER</th><th>Median ER</th><th>Posts</th></tr>
    {{#benchmarks}}
    <tr>
      <td>{{ key }}</td>
      <td>{{ avg_er }}%</td>
      <td>{{ median_er }}%</td>
      <td>{{ post_count }}</td>
    </tr>
    {{/benchmarks}}
  </table>
  {{/has_benchmarks}}
  {{^has_benchmarks}}
  <div class="empty-state">Benchmark data unavailable.</div>
  {{/has_benchmarks}}
</div>

<div class="footer">
  Generated by Gravitas Pitch Research &middot; {{ date }}
</div>

</div>
</body>
</html>"""


THEME_COLORS = [
    "#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed",
    "#db2777", "#0891b2", "#65a30d",
]


def render_template(template: str, context: dict) -> str:
    """Minimal mustache-style template renderer."""
    result = template

    # Handle sections: {{#section}}...{{/section}}
    import re
    for match in re.finditer(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", result, re.DOTALL):
        key = match.group(1)
        inner = match.group(2)
        if context.get(key):
            # True section: render inner content
            rendered = _render_section(inner, context, key)
            result = result.replace(match.group(0), rendered, 1)
        else:
            # False section: check for inverse {{^key}}
            inverse_match = re.search(
                r"\{\{\^" + key + r"\}\}(.*?)\{\{/" + key + r"\}\}",
                match.group(2), re.DOTALL
            )
            if inverse_match:
                result = result.replace(match.group(0), inverse_match.group(1), 1)
            else:
                result = result.replace(match.group(0), "", 1)

    # Handle inverted sections: {{^section}}...{{/section}}
    for match in re.finditer(r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}", result, re.DOTALL):
        key = match.group(1)
        if not context.get(key):
            inner = match.group(2)
            result = result.replace(match.group(0), inner, 1)
        else:
            result = result.replace(match.group(0), "", 1)

    # Handle simple variables: {{ var }}
    for match in re.finditer(r"\{\{\s*([\w.]+)\s*\}\}", result):
        key = match.group(1)
        value = context.get(key, "")
        result = result.replace(match.group(0), str(value), 1)

    return result


def _render_section(template: str, context: dict, list_key: str) -> str:
    """Render a list section by repeating the inner template per item."""
    items = context.get(list_key, [])
    if not isinstance(items, list):
        items = [items] if items else []

    # Find the repeating pattern (content between list markers)
    # Simple approach: render each item with the template
    result_parts = []
    for item in items:
        if isinstance(item, dict):
            part = template
            for k, v in item.items():
                if isinstance(v, list):
                    # Nested lists — flatten to joined string
                    v = " ".join(str(x) for x in v)
                part = part.replace(f"{{{{ {k} }}}}", str(v) if v is not None else "")
            result_parts.append(part)
        else:
            result_parts.append(template.replace("{{ . }}", str(item)))

    return "\n".join(result_parts)


def build_context(analysis: dict, title: str, quick_mode: bool = False) -> dict:
    """Build template context from analysis JSON."""
    competitors = analysis.get("competitors", [analysis])

    # Summary cards
    total_posts = analysis.get("total_posts", 0)
    total_kols = len(analysis.get("kols", []))
    total_campaigns = len(analysis.get("campaigns", []))
    platforms = analysis.get("platforms_covered", [])

    summary_cards = [
        {"label": "Total Posts Analyzed", "value": str(total_posts)},
        {"label": "KOLs Identified", "value": str(total_kols)},
        {"label": "Campaigns Detected", "value": str(total_campaigns)},
        {"label": "Platforms", "value": ", ".join(platforms).upper()},
    ]

    # Campaigns
    campaigns = analysis.get("campaigns", [])

    # KOLs
    kols = analysis.get("kols", [])

    # Themes with colors
    themes_data = analysis.get("content_themes", {})
    themes = themes_data.get("themes", [])
    for i, t in enumerate(themes):
        t["color"] = THEME_COLORS[i % len(THEME_COLORS)]

    # Cadence
    cadence_data = analysis.get("cadence", {})
    cadence = []
    for plat, data in cadence_data.items():
        cadence.append({**data, "platform": plat})

    # Benchmarks
    benchmarks_data = analysis.get("benchmarks", {})
    benchmarks = []
    bench_eng = benchmarks_data.get("engagement_benchmarks", {})
    for key, data in bench_eng.items():
        benchmarks.append({**data, "key": key})

    # Competitor platform stats (simplified)
    competitor_sections = []
    for comp_name, comp_data in (analysis.get("_competitors", {}) or {}).items():
        competitor_sections.append({"name": comp_name, "platform_stats": []})

    if not competitor_sections:
        competitor_sections = [{
            "name": title,
            "platform_stats": [{
                "platform": p, "platform_label": p.upper(),
                "post_count": total_posts, "avg_er": "N/A",
                "top_format": "N/A", "posts_per_week": "N/A",
            } for p in platforms]
        }]

    return {
        "title": title,
        "date": datetime.now().strftime("%B %d, %Y"),
        "competitor_count": len(competitor_sections),
        "platform_list": ", ".join(platforms).upper(),
        "quick_mode": quick_mode,
        "summary_cards": summary_cards,
        "has_campaigns": len(campaigns) > 0,
        "campaigns": campaigns,
        "has_kols": len(kols) > 0,
        "kols": kols,
        "has_themes": bool(themes),
        "themes": themes,
        "tone": themes_data.get("tone", "Not analyzed"),
        "cta_patterns": ", ".join(themes_data.get("cta_patterns", [])),
        "has_cadence": bool(cadence),
        "cadence": cadence,
        "has_benchmarks": bool(benchmarks),
        "benchmarks": benchmarks,
        "competitors": competitor_sections,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate pitch research HTML report")
    parser.add_argument("--analysis-file", required=True, help="JSON file from analyze_competitor.py")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--title", default="Competitor Research Report", help="Report title")
    parser.add_argument("--quick", action="store_true", help="Quick mode (no video analysis)")
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser")
    args = parser.parse_args()

    with open(args.analysis_file, encoding="utf-8") as f:
        analysis = json.load(f)

    template = load_template()
    context = build_context(analysis, args.title, args.quick)
    html = render_template(template, context)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_file = output_dir / "competitor_research_report.html"

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report generated: {html_file}")

    if not args.no_open:
        webbrowser.open(f"file:///{html_file.resolve()}")


if __name__ == "__main__":
    main()
