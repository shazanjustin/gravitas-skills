#!/usr/bin/env python3
"""
Generate an HTML visual review page for Instagram posts.
Downloads full-resolution images and creates a browsable interface
for visual classification into activity categories.

Usage:
    python scripts/visual_review.py \\
        --profile-id 1446c72e-... \\
        --brand "Anmum" \\
        --from 2026-05-01 \\
        --to 2026-05-31 \\
        --output review.html

Opens in browser for visual review. Each post card shows:
- Full-size image (readable text!)
- Caption, date, metrics
- Dropdown to assign activity category
- Save button to write back to Supabase
"""
import argparse
import json
import os
import sys
import hashlib
import requests
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ig_utils import get_supabase, DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_KEY, resolve_output_path

ACTIVITY_GROUPS = [
    'NPD',
    'KOL',
    'LAUNCH',
    'SOCIAL & DIGITAL',
    'ENGAGEMENT',
    'BTL PROMO & ON-GROUND',
]

IMAGE_DIR = 'ig_images'


def get_best_image_url(raw):
    """Extract the highest-resolution image URL from the raw Instagram data."""
    # Try image_versions2 first (highest res)
    image_versions = raw.get('image_versions2') or {}
    candidates = image_versions.get('candidates', [])
    if candidates:
        # Sort by width descending, pick the largest
        sorted_cands = sorted(candidates, key=lambda c: c.get('width', 0), reverse=True)
        return sorted_cands[0].get('url', '')

    # Fallback to display_url
    return raw.get('display_url', '') or raw.get('thumbnail_src', '')


def download_image(url, post_id, image_dir):
    """Download an image and return the local path."""
    if not url:
        return None

    os.makedirs(image_dir, exist_ok=True)

    # Create a stable filename from URL hash
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    shortcode = post_id.replace('ig_', '').replace('_', '-')
    ext = '.jpg'  # Instagram always serves JPEG
    filename = f'{shortcode}_{url_hash}{ext}'
    filepath = os.path.join(image_dir, filename)

    if os.path.exists(filepath):
        return filepath

    try:
        resp = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        resp.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(resp.content)
        return filepath
    except Exception as e:
        print(f'  [WARN] Failed to download {url[:60]}...: {e}')
        return None


def generate_html(posts, brand, from_date, to_date, image_dir):
    """Generate the HTML review page."""
    cards_html = []

    for p in sorted(posts, key=lambda x: x.get('created_at', ''), reverse=True):
        raw = p.get('raw', {})
        post_id = p.get('id', '')
        shortcode = raw.get('code', '')
        caption = (raw.get('caption') or '')[:200].replace('\n', ' ').strip()
        likes = raw.get('likes', 0) or 0
        comments = raw.get('comments', 0) or 0
        views = raw.get('video_view_count')
        media_type = raw.get('media_type', 1)
        post_url = raw.get('post_url', '')
        created = p.get('created_at', '')[:10]
        current_group = p.get('activity_group') or []

        # Image
        img_url = get_best_image_url(raw)
        local_img = None
        if img_url:
            local_img = download_image(img_url, post_id, image_dir)

        img_tag = ''
        if local_img:
            img_tag = f'<img src="{local_img}" alt="{shortcode}" loading="lazy" />'
        elif img_url:
            img_tag = f'<img src="{img_url}" alt="{shortcode}" loading="lazy" onerror="this.style.display=\'none\'" />'
        else:
            img_tag = '<div class="no-image">No image</div>'

        # Metrics
        metrics_parts = [f'{likes} likes', f'{comments} comments']
        if views:
            metrics_parts.append(f'{views} views')
        metrics_str = ' · '.join(metrics_parts)

        # Type badge
        type_label = {1: 'Image', 2: 'Video', 8: 'Carousel'}.get(media_type, '?')
        type_class = {1: 'img', 2: 'vid', 8: 'car'}.get(media_type, '')

        # Current group tag
        current_tag = ''
        if current_group:
            g = current_group[0] if isinstance(current_group, list) else current_group
            current_tag = f'<span class="current-group">{g}</span>'

        # Activity options
        options_html = '<option value="">— Select —</option>'
        for g in ACTIVITY_GROUPS:
            selected = ' selected' if g in current_group else ''
            options_html += f'<option value="{g}"{selected}>{g}</option>'

        cards_html.append(f'''
        <article class="post-card" data-id="{post_id}">
            <div class="post-image">
                {img_tag}
                <span class="type-badge {type_class}">{type_label}</span>
                {current_tag}
            </div>
            <div class="post-meta">
                <div class="post-date">{created}</div>
                <div class="post-metrics">{metrics_str}</div>
                <a href="{post_url}" target="_blank" class="post-link">View on IG ↗</a>
            </div>
            <div class="post-caption">{caption[:120]}{'...' if len(caption) > 120 else ''}</div>
            <div class="post-classify">
                <select class="activity-select" data-id="{post_id}">
                    {options_html}
                </select>
            </div>
        </article>
        ''')

    cards_joined = '\n'.join(cards_html)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand} — Visual Review ({from_date} to {to_date})</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }}
    .header {{ background: #1a365d; color: white; padding: 24px 32px; }}
    .header h1 {{ font-size: 24px; margin-bottom: 4px; }}
    .header .subtitle {{ opacity: 0.8; font-size: 14px; }}
    .toolbar {{ background: white; padding: 16px 32px; border-bottom: 1px solid #e2e8f0; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; position: sticky; top: 0; z-index: 100; }}
    .toolbar .stat {{ font-size: 13px; color: #666; }}
    .toolbar .stat strong {{ color: #1a365d; }}
    .filter-btn {{ padding: 6px 14px; border: 1px solid #cbd5e0; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; transition: all 0.15s; }}
    .filter-btn:hover {{ border-color: #3182ce; color: #3182ce; }}
    .filter-btn.active {{ background: #3182ce; color: white; border-color: #3182ce; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; padding: 24px 32px; }}
    .post-card {{ background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: box-shadow 0.2s; }}
    .post-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
    .post-image {{ position: relative; aspect-ratio: 1; background: #f0f0f0; overflow: hidden; }}
    .post-image img {{ width: 100%; height: 100%; object-fit: cover; }}
    .no-image {{ display: flex; align-items: center; justify-content: center; height: 100%; color: #999; }}
    .type-badge {{ position: absolute; top: 8px; left: 8px; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
    .type-badge.img {{ background: #3182ce; color: white; }}
    .type-badge.vid {{ background: #e53e3e; color: white; }}
    .type-badge.car {{ background: #805ad5; color: white; }}
    .current-group {{ position: absolute; top: 8px; right: 8px; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #38a169; color: white; }}
    .post-meta {{ padding: 12px 16px 0; display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #718096; }}
    .post-link {{ color: #3182ce; text-decoration: none; }}
    .post-link:hover {{ text-decoration: underline; }}
    .post-caption {{ padding: 8px 16px; font-size: 13px; line-height: 1.4; color: #4a5568; }}
    .post-classify {{ padding: 8px 16px 16px; }}
    .activity-select {{ width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white; cursor: pointer; }}
    .activity-select:focus {{ outline: none; border-color: #3182ce; box-shadow: 0 0 0 3px rgba(49,130,206,0.1); }}
    .save-bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: #1a365d; color: white; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; z-index: 100; }}
    .save-btn {{ padding: 10px 24px; background: #38a169; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }}
    .save-btn:hover {{ background: #2f855a; }}
    .save-btn:disabled {{ background: #a0aec0; cursor: not-allowed; }}
    .save-status {{ font-size: 13px; opacity: 0.8; }}
    .summary-section {{ padding: 24px 32px; }}
    .summary-section h2 {{ font-size: 18px; margin-bottom: 12px; color: #1a365d; }}
    .group-summary {{ background: white; border-radius: 8px; padding: 16px; margin-bottom: 12px; border-left: 4px solid #3182ce; }}
    .group-summary h3 {{ font-size: 14px; margin-bottom: 8px; }}
    .group-summary .count {{ color: #718096; font-size: 12px; }}
</style>
</head>
<body>
<div class="header">
    <h1>{brand} — Visual Review</h1>
    <div class="subtitle">{from_date} to {to_date} · {len(posts)} posts · Review images and assign activity categories</div>
</div>

<div class="toolbar">
    <span class="stat"><strong>{len(posts)}</strong> total posts</span>
    <span class="stat" id="categorized-count">0</span> categorized
    <span class="stat" id="uncategorized-count">{len(posts)}</span> uncategorized
    <div style="flex:1"></div>
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="categorized">Categorized</button>
    <button class="filter-btn" data-filter="uncategorized">Uncategorized</button>
    {"".join(f'<button class="filter-btn" data-filter="{g}">{g}</button>' for g in ACTIVITY_GROUPS)}
</div>

<div class="grid" id="post-grid">
    {cards_joined}
</div>

<div class="save-bar">
    <span class="save-status" id="save-status">Make your selections above</span>
    <button class="save-btn" id="save-btn" onclick="saveClassifications()">Save All Classifications</button>
</div>

<script>
const SUPABASE_URL = '{DEFAULT_SUPABASE_URL}';
const SUPABASE_KEY = '{DEFAULT_SUPABASE_KEY}';

// Track changes
const changes = new Map();

document.querySelectorAll('.activity-select').forEach(sel => {{
    sel.addEventListener('change', () => {{
        const id = sel.dataset.id;
        const val = sel.value;
        changes.set(id, val);
        updateCounts();
        updateCardTag(sel);
    }});
}});

function updateCardTag(sel) {{
    const card = sel.closest('.post-card');
    let tag = card.querySelector('.current-group');
    if (sel.value) {{
        if (!tag) {{
            tag = document.createElement('span');
            tag.className = 'current-group';
            card.querySelector('.post-image').appendChild(tag);
        }}
        tag.textContent = sel.value;
    }} else if (tag) {{
        tag.remove();
    }}
}}

function updateCounts() {{
    const allSelects = document.querySelectorAll('.activity-select');
    let cat = 0;
    allSelects.forEach(s => {{ if (s.value) cat++; }});
    document.getElementById('categorized-count').innerHTML = `<strong>${{cat}}</strong> categorized`;
    document.getElementById('uncategorized-count').innerHTML = `${{allSelects.length - cat}} uncategorized`;
}}

// Filter buttons
document.querySelectorAll('.filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const filter = btn.dataset.filter;
        document.querySelectorAll('.post-card').forEach(card => {{
            if (filter === 'all') {{
                card.style.display = '';
            }} else if (filter === 'categorized') {{
                const sel = card.querySelector('.activity-select');
                card.style.display = sel.value ? '' : 'none';
            }} else if (filter === 'uncategorized') {{
                const sel = card.querySelector('.activity-select');
                card.style.display = sel.value ? 'none' : '';
            }} else {{
                const sel = card.querySelector('.activity-select');
                card.style.display = sel.value === filter ? '' : 'none';
            }}
        }});
    }});
}});

async function saveClassifications() {{
    const btn = document.getElementById('save-btn');
    const status = document.getElementById('save-status');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    let saved = 0;
    let errors = 0;

    for (const [postId, group] of changes) {{
        try {{
            const resp = await fetch(`${{SUPABASE_URL}}/rest/v1/competitor_posts?id=eq.${{postId}}`, {{
                method: 'PATCH',
                headers: {{
                    'apikey': SUPABASE_KEY,
                    'Authorization': `Bearer ${{SUPABASE_KEY}}`,
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal',
                }},
                body: JSON.stringify({{
                    activity_group: group ? [group] : [],
                }}),
            }});
            if (resp.ok) saved++;
            else errors++;
        }} catch (e) {{
            errors++;
        }}
    }}

    btn.disabled = false;
    btn.textContent = 'Save All Classifications';
    status.textContent = `Saved ${{saved}} classifications${{errors ? `, ${{errors}} errors` : ''}}`;
    changes.clear();
}}

updateCounts();
</script>
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(description='Generate visual review page for IG posts')
    parser.add_argument('--profile-id', required=True, help='competitor_profiles UUID')
    parser.add_argument('--brand', required=True, help='Brand name')
    parser.add_argument('--from', dest='from_date', required=True)
    parser.add_argument('--to', dest='to_date', required=True)
    parser.add_argument('--output', default=None, help='Output HTML path')
    parser.add_argument('--image-dir', default=IMAGE_DIR, help='Directory for downloaded images')
    args = parser.parse_args()

    print(f'Fetching posts for {args.brand} ({args.from_date} to {args.to_date})...')
    supabase = get_supabase()
    result = supabase.table('competitor_posts') \
        .select('*') \
        .eq('profile_id', args.profile_id) \
        .eq('platform', 'instagram') \
        .gte('created_at', f'{args.from_date}T00:00:00') \
        .lte('created_at', f'{args.to_date}T23:59:59') \
        .order('created_at', desc=True) \
        .execute()

    posts = result.data or []
    print(f'  Found {len(posts)} posts')

    if not posts:
        print('No posts found. Exiting.')
        return

    # Resolve output path first
    default_name = f'{args.brand.lower().replace(" ", "_")}_review_{args.from_date}_{args.to_date}.html'
    output_path = resolve_output_path(args.output or default_name)
    print(f'  Output: {output_path}')

    # Image directory: alongside the output file by default
    if os.path.isabs(args.image_dir):
        image_dir = args.image_dir
    elif args.image_dir == IMAGE_DIR:
        # Default: place ig_images/ next to the HTML output
        image_dir = os.path.join(os.path.dirname(output_path), 'ig_images')
    else:
        image_dir = os.path.join(os.getcwd(), args.image_dir)
    print(f'\nDownloading images to {image_dir}...')
    downloaded = 0
    for p in posts:
        raw = p.get('raw', {})
        img_url = get_best_image_url(raw)
        if img_url:
            path = download_image(img_url, p['id'], image_dir)
            if path:
                downloaded += 1
    print(f'  Downloaded {downloaded}/{len(posts)} images')

    # Generate HTML
    html = generate_html(posts, args.brand, args.from_date, args.to_date, image_dir)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'\n  Review page: {output_path}')
    print(f'  Open in browser to classify posts visually.')
    print(f'  After classification, use the Activity Slide Review to generate slide summaries.')


if __name__ == '__main__':
    main()
