#!/usr/bin/env python3
"""
Generate an Activity Slide review page — a standalone HTML that recreates
the intel-app's Activity Slide with full-resolution images.

Features:
- Source list of uncategorized posts (left)
- 6 category columns: NPD, KOL, LAUNCH, SOCIAL & DIGITAL, ENGAGEMENT, BTL PROMO & ON-GROUND
- Drag-and-drop between columns
- Full-resolution images (not thumbnails)
- Multi-competitor tabs
- Save to Supabase
- Generate slide summaries

Usage:
    python scripts/activity_slide_review.py \\
        --profile-ids "id1,id2,id3" \\
        --brand "Friso Gold" \\
        --from 2026-05-01 \\
        --to 2026-05-31 \\
        --output friso_activity_review.html
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
from ig_utils import get_supabase, list_account_profiles, DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_KEY, resolve_output_path

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
    """Extract the highest-resolution image URL."""
    image_versions = raw.get('image_versions2') or {}
    candidates = image_versions.get('candidates', [])
    if candidates:
        sorted_cands = sorted(candidates, key=lambda c: c.get('width', 0), reverse=True)
        return sorted_cands[0].get('url', '')
    return raw.get('display_url', '') or raw.get('thumbnail_src', '')


def download_image(url, post_id, image_dir):
    """Download an image and return the local path."""
    if not url:
        return None
    os.makedirs(image_dir, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    shortcode = post_id.replace('ig_', '').replace('_', '-')
    filename = f'{shortcode}_{url_hash}.jpg'
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
        print(f'  [WARN] Failed to download: {e}')
        return None


def pick_int(raw, *keys):
    """Return the first numeric metric found in a raw Instagram payload."""
    for key in keys:
        value = raw.get(key)
        if isinstance(value, dict):
            value = value.get('count') or value.get('value')
        if value is None or value == '':
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def get_caption(raw):
    caption = raw.get('caption') or ''
    if isinstance(caption, dict):
        caption = caption.get('text') or ''
    return str(caption).strip()


def generate_html(all_posts_by_competitor, brand, from_date, to_date, image_dir):
    """Generate the Activity Slide review HTML."""

    # Build competitor tabs
    competitor_tabs = []
    competitor_data = {}  # {competitor_name: {posts: [...], profile_id: str}}

    for comp_name, posts in all_posts_by_competitor.items():
        competitor_tabs.append(f'<button class="comp-tab" data-comp="{comp_name}">{comp_name} ({len(posts)})</button>')

        # Download images and prepare post data
        post_cards = []
        for p in sorted(posts, key=lambda x: x.get('created_at', ''), reverse=True):
            raw = p.get('raw', {})
            post_id = p.get('id', '')
            shortcode = raw.get('code', '')
            caption = get_caption(raw)
            likes = pick_int(raw, 'likes', 'like_count') or 0
            comments = pick_int(raw, 'comments', 'comment_count') or 0
            shares = pick_int(raw, 'shares', 'share_count', 'reshare_count')
            saves = pick_int(raw, 'saves', 'save_count', 'saved_count')
            views = pick_int(raw, 'video_view_count', 'view_count', 'play_count')
            media_type = raw.get('media_type', 1)
            post_url = raw.get('post_url', '')
            if not post_url and shortcode:
                post_url = f'https://www.instagram.com/p/{shortcode}/'
            owner = raw.get('owner_username') or raw.get('username') or (raw.get('user') or {}).get('username') or ''
            if not owner and post_id.startswith('ig_'):
                id_parts = post_id.split('_')
                if len(id_parts) >= 3:
                    owner = '_'.join(id_parts[1:-1])
            tagged_users = raw.get('tagged_users', []) or []
            if not isinstance(tagged_users, list):
                tagged_users = []
            created = p.get('created_at', '')[:10]
            current_group = p.get('activity_group') or []
            if isinstance(current_group, list) and current_group:
                current_group = current_group[0]
            elif isinstance(current_group, list):
                current_group = ''

            img_url = get_best_image_url(raw)
            local_img = None
            if img_url:
                local_img = download_image(img_url, post_id, image_dir)
            img_src = local_img or img_url or ''

            type_label = {1: 'IMG', 2: 'VID', 8: 'CAR'}.get(media_type, '?')

            post_cards.append({
                'id': post_id,
                'img': img_src.replace('\\', '/'),
                'caption': caption,
                'likes': likes,
                'comments': comments,
                'views': views or 0,
                'shares': shares,
                'saves': saves,
                'type': type_label,
                'url': post_url,
                'owner': owner,
                'tagged_users': tagged_users,
                'is_collab': bool(raw.get('is_collab')),
                'date': created,
                'group': current_group,
                'profile_id': p.get('profile_id', ''),
            })

        competitor_data[comp_name] = {
            'posts': post_cards,
            'profile_id': posts[0].get('profile_id', '') if posts else '',
        }

    # Build source list cards and column cards
    first_comp = list(competitor_data.keys())[0] if competitor_data else ''
    first_posts = competitor_data.get(first_comp, {}).get('posts', [])

    source_cards = []
    column_cards = {g: [] for g in ACTIVITY_GROUPS}

    for post in first_posts:
        card_html = f'''
        <article class="post-card" draggable="true" data-id="{post['id']}" data-comp="{first_comp}">
            <div class="post-img-wrap">
                <img src="{post['img']}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=no-img>No img</div>'" />
                <span class="type-badge">{post['type']}</span>
            </div>
            <div class="post-info">
                <div class="post-meta-row"><span class="post-tagged">Tagged: {', '.join('@' + str(t) for t in (post.get('tagged_users') or [])) or 'none'}</span></div>
                {f'<div class="post-actions"><a class="post-link" href="{post.get('url')}" target="_blank" rel="noopener noreferrer">Open post ↗</a></div>' if post.get('url') else ''}
                <div class="post-metrics">{post['likes']}L {post['comments']}C {post['views']}V</div>
                <div class="post-cap">{post['caption'][:80]}{'...' if len(post['caption']) > 80 else ''}</div>
            </div>
        </article>'''

        if post['group'] in ACTIVITY_GROUPS:
            column_cards[post['group']].append(card_html)
        else:
            source_cards.append(card_html)

    source_html = '\n'.join(source_cards) if source_cards else '<div class="empty-state">All posts categorized!</div>'
    column_htmls = {}
    for g in ACTIVITY_GROUPS:
        cards = '\n'.join(column_cards[g])
        column_htmls[g] = f'''<div class="cat-column" data-group="{g}">
            <div class="cat-header">{g} <span class="cat-count">{len(column_cards[g])}</span></div>
            <div class="cat-cards" data-group="{g}">{cards if cards else '<div class="empty-drop">Drop here</div>'}</div>
        </div>'''

    all_competitor_data_json = json.dumps(competitor_data)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand} — Activity Slide Review</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {{
        --bg: #1C1C1C;
        --surface: #202020;
        --surface-2: #242424;
        --surface-3: #2A2A2A;
        --line: rgba(255,255,255,0.08);
        --line-strong: rgba(255,255,255,0.13);
        --text: #E5E5E5;
        --muted: #A1A1A1;
        --muted-2: #737373;
        --accent: #E5E5E5;
        --green: #1EDB8F;
        --cyan: #16B8E8;
        --orange: #FF7A18;
        --yellow: #F8C51B;
        --purple: #A78BFA;
        --red: #FF4D5E;
        --friso-blue: #1F5FAE;
        --friso-blue-deep: #123A73;
        --shadow: 0 18px 48px rgba(0,0,0,0.42);
        --r-sm: 6px;
        --r-md: 8px;
        --r-lg: 12px;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html {{ background: var(--bg); }}
    body {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        letter-spacing: -0.15px;
        background: var(--bg);
        color: var(--text);
        height: 100vh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        font-size: 13px;
    }}

    .hi {{ width: 13px; height: 13px; flex: 0 0 auto; stroke: currentColor; stroke-width: 1.85; fill: none; stroke-linecap: round; stroke-linejoin: round; }}

    /* Header */
    .header {{
        background: linear-gradient(135deg, var(--friso-blue-deep) 0%, var(--friso-blue) 72%, #2A75C8 100%);
        color: var(--text);
        padding: 18px 24px;
        display: flex;
        align-items: baseline;
        gap: 14px;
        flex-shrink: 0;
        border-bottom: 1px solid rgba(255,255,255,0.14);
        box-shadow: inset 0 -1px 0 rgba(0,0,0,0.22);
    }}
    .header h1 {{ font-size: 20px; font-weight: 800; letter-spacing: -0.45px; }}
    .header .subtitle {{ color: rgba(229,229,229,0.78); font-size: 12px; font-weight: 500; }}

    /* Competitor Tabs */
    .comp-tabs {{
        display: flex;
        gap: 8px;
        background: linear-gradient(180deg, #153F78 0%, #102D55 100%);
        padding: 12px 20px;
        flex-shrink: 0;
        border-bottom: 1px solid var(--line);
        overflow-x: auto;
    }}
    .comp-tab {{
        padding: 8px 13px;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: var(--r-md);
        background: rgba(28,28,28,0.34);
        color: rgba(229,229,229,0.78);
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
        transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.15s;
        white-space: nowrap;
    }}
    .comp-tab:hover {{ background: rgba(255,255,255,0.1); color: var(--text); border-color: rgba(255,255,255,0.26); }}
    .comp-tab.active {{ background: var(--text); color: #123A73; border-color: var(--text); }}

    /* Toolbar */
    .toolbar {{
        background: var(--bg);
        padding: 10px 20px;
        border-bottom: 1px solid var(--line);
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
        color: var(--muted);
    }}
    .toolbar .stat {{ font-size: 12px; color: var(--muted); font-weight: 500; }}
    .toolbar .stat strong {{ color: var(--text); font-weight: 700; }}
    .toolbar .spacer {{ flex: 1; }}
    .toolbar label, .card-size-label {{ font-size: 11px !important; color: var(--muted) !important; font-weight: 600; }}
    .toolbar input[type="date"], .toolbar select {{
        background: #191919 !important;
        color: var(--text) !important;
        border: 1px solid var(--line-strong) !important;
        border-radius: var(--r-sm) !important;
        padding: 6px 9px !important;
        color-scheme: dark;
        font-family: inherit;
        font-weight: 600;
    }}
    .card-size {{ width: 100px; accent-color: var(--text); }}
    .btn {{
        padding: 7px 13px;
        border-radius: var(--r-md);
        border: 1px solid var(--line-strong);
        background: #191919;
        color: var(--text);
        cursor: pointer;
        font-size: 12px;
        font-weight: 700;
        transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.15s;
    }}
    .btn:hover {{ background: var(--surface-2); border-color: rgba(255,255,255,0.22); color: var(--text); }}
    .btn-primary {{ background: var(--text); color: #151515; border-color: var(--text); }}
    .btn-primary:hover {{ background: #fff; color: #111; }}
    .btn-success {{ background: #E5E5E5; color: #111; border-color: #E5E5E5; }}
    .btn-success:hover {{ background: #fff; color: #111; }}

    /* Main Layout */
    .main {{ display: flex; flex: 1; overflow: hidden; background: #181818; }}

    /* Source Panel */
    .source-panel {{
        width: 292px;
        background: var(--bg);
        border-right: 1px solid var(--line);
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
    }}
    .source-header {{
        padding: 12px 14px;
        font-size: 12px;
        font-weight: 700;
        border-bottom: 1px solid var(--line);
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: var(--text);
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }}
    .source-count, .cat-count {{
        background: var(--surface-3);
        color: var(--text);
        border: 1px solid var(--line);
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 10px;
        font-weight: 800;
    }}
    .source-cards {{ flex: 1; overflow-y: auto; padding: 10px; }}
    .source-cards[data-group] {{ min-height: 60px; }}

    /* Post Card */
    .post-card {{
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: var(--r-md);
        overflow: hidden;
        margin-bottom: 10px;
        cursor: grab;
        transition: box-shadow 0.15s, transform 0.15s, border-color 0.15s, background 0.15s;
    }}
    .post-card:hover {{ box-shadow: 0 10px 28px rgba(0,0,0,0.28); border-color: var(--line-strong); background: var(--surface-2); }}
    .post-card.dragging {{ opacity: 0.45; transform: scale(0.96); }}
    .post-img-wrap {{ position: relative; background: #111; overflow: hidden; border-bottom: 1px solid var(--line); }}
    .post-img-wrap img {{ width: 100%; height: 100%; display: block; object-fit: cover; }}
    .type-badge {{
        position: absolute;
        top: 7px;
        left: 7px;
        padding: 3px 7px;
        border-radius: var(--r-sm);
        font-size: 9px;
        font-weight: 800;
        background: rgba(28,28,28,0.82);
        color: var(--text);
        border: 1px solid rgba(255,255,255,0.12);
        backdrop-filter: blur(10px);
    }}
    .no-img {{ padding: 24px; text-align: center; color: var(--muted); font-size: 11px; }}
    .post-info {{ padding: 10px; }}
    .post-meta-row {{ margin-bottom: 6px; }}
    .post-actions {{ display: flex; justify-content: flex-end; margin: 4px 0 7px; }}
    .post-tagged {{ display: block; min-width: 0; white-space: normal; overflow: visible; overflow-wrap: anywhere; line-height: 1.35; font-size: 10px; font-weight: 700; color: var(--text); }}
    .post-tagged.muted {{ color: var(--muted-2); font-weight: 600; }}
    .post-comp-label {{ color: var(--text); font-size: 10px; font-weight: 800; }}
    .post-date-label {{ color: var(--muted-2); font-size: 10px; font-weight: 600; }}
    .post-link {{
        flex-shrink: 0;
        padding: 5px 8px;
        border-radius: var(--r-sm);
        background: #E5E5E5;
        color: #111;
        border: 1px solid #E5E5E5;
        font-size: 10px;
        font-weight: 800;
        text-decoration: none;
    }}
    .post-link:hover {{ background: #fff; }}
    .post-tags {{ margin-bottom: 4px; font-size: 10px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .post-metrics {{ display: flex; flex-wrap: wrap; gap: 5px; margin: 6px 0 8px; }}
    .metric-chip {{ display: inline-flex; align-items: center; gap: 3px; padding: 3px 6px; border-radius: 999px; background: #171717; border: 1px solid var(--line); color: var(--muted); font-size: 9px; font-weight: 800; line-height: 1.1; }}
    .metric-chip.primary {{ color: var(--text); background: #252525; }}
    .post-cap {{ display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; font-size: 11px; line-height: 1.45; color: var(--muted); white-space: pre-wrap; word-break: break-word; overflow: hidden; }}
    .post-card.expanded .post-cap {{ display: block; max-height: 160px; overflow-y: auto; }}
    .see-more {{ margin-top: 7px; padding: 0; border: 0; background: transparent; color: var(--text); font-size: 10px; font-weight: 800; cursor: pointer; }}
    .see-more:hover {{ color: #fff; text-decoration: underline; }}

    /* Hover preview */
    #imgPreview {{
        display: none;
        position: fixed;
        z-index: 9999;
        pointer-events: none;
        width: min(760px, calc(100vw - 24px));
        max-height: 90vh;
        background: rgba(28,28,28,0.94);
        border: 1px solid var(--line-strong);
        border-radius: var(--r-lg);
        box-shadow: var(--shadow);
        overflow: hidden;
        backdrop-filter: blur(18px);
    }}
    #imgPreview .preview-inner {{ display: grid; grid-template-columns: minmax(220px, 46%) 1fr; align-items: stretch; max-height: 90vh; }}
    #imgPreview .preview-media {{ display: flex; align-items: center; justify-content: center; min-height: 260px; background: #0F0F0F; border-right: 1px solid var(--line); }}
    #imgPreview img {{ display: block; width: 100%; height: 100%; max-height: 90vh; object-fit: contain; }}
    #imgPreview .preview-detail {{ min-width: 0; display: flex; flex-direction: column; gap: 12px; padding: 16px; color: var(--text); overflow: hidden; }}
    #imgPreview .preview-kicker {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 11px; font-weight: 800; }}
    #imgPreview .preview-stats {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    #imgPreview .preview-stat {{ padding: 10px; border: 1px solid var(--line); border-radius: var(--r-md); background: rgba(255,255,255,0.035); }}
    #imgPreview .preview-stat span {{ display: flex; align-items: center; gap: 5px; color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 800; }}
    #imgPreview .preview-stat strong {{ display: block; margin-top: 5px; font-size: 17px; color: var(--text); letter-spacing: -0.35px; }}
    #imgPreview .preview-cap {{ flex: 1; min-height: 0; color: var(--text); font-size: 12px; line-height: 1.5; overflow-y: auto; white-space: pre-wrap; word-break: break-word; }}
    @media (max-width: 700px) {{
        #imgPreview .preview-inner {{ grid-template-columns: 1fr; }}
        #imgPreview .preview-media {{ min-height: 180px; max-height: 42vh; border-right: 0; border-bottom: 1px solid var(--line); }}
    }}

    /* Category Columns */
    .columns-container {{ flex: 1; display: flex; overflow-x: auto; gap: 0; background: #181818; }}
    .cat-column {{ min-width: 210px; flex: 1; display: flex; flex-direction: column; border-right: 1px solid var(--line); background: #181818; }}
    .cat-header {{ padding: 12px; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.03em; border-bottom: 1px solid var(--line); background: var(--bg); color: var(--text); display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; min-height: 46px; }}
    .cat-cards {{ flex: 1; overflow-y: auto; padding: 10px; min-height: 100px; }}
    .cat-cards.drag-over {{ background: #202020; outline: 1px dashed rgba(255,255,255,0.24); outline-offset: -6px; }}
    .empty-drop {{ padding: 22px 8px; text-align: center; color: var(--muted-2); font-size: 12px; font-style: italic; }}

    /* Column-specific accents */
    .cat-column[data-group="NPD"] .cat-header {{ border-top: 2px solid var(--red); }}
    .cat-column[data-group="NPD"] .cat-count {{ color: var(--red); }}
    .cat-column[data-group="KOL"] .cat-header {{ border-top: 2px solid var(--purple); }}
    .cat-column[data-group="KOL"] .cat-count {{ color: var(--purple); }}
    .cat-column[data-group="LAUNCH"] .cat-header {{ border-top: 2px solid var(--orange); }}
    .cat-column[data-group="LAUNCH"] .cat-count {{ color: var(--orange); }}
    .cat-column[data-group="SOCIAL & DIGITAL"] .cat-header {{ border-top: 2px solid #14B8A6; }}
    .cat-column[data-group="SOCIAL & DIGITAL"] .cat-count {{ color: #14B8A6; }}
    .cat-column[data-group="ENGAGEMENT"] .cat-header {{ border-top: 2px solid var(--green); }}
    .cat-column[data-group="ENGAGEMENT"] .cat-count {{ color: var(--green); }}
    .cat-column[data-group="BTL PROMO & ON-GROUND"] .cat-header {{ border-top: 2px solid var(--yellow); }}
    .cat-column[data-group="BTL PROMO & ON-GROUND"] .cat-count {{ color: var(--yellow); }}

    /* Status bar */
    .save-details {{ display: none; max-height: 140px; overflow-y: auto; padding: 10px 20px; background: #251A1A; color: #FFB4B4; border-top: 1px solid rgba(255,77,94,0.25); border-bottom: 1px solid rgba(255,77,94,0.25); font-size: 12px; line-height: 1.4; white-space: pre-wrap; flex-shrink: 0; }}
    .save-details.active {{ display: block; }}
    .save-details.success {{ background: #16251D; color: #A7F3D0; border-color: rgba(30,219,143,0.25); }}
    .status-bar {{ background: var(--bg); color: var(--muted); padding: 10px 20px; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; font-size: 12px; flex-shrink: 0; }}
    .save-status {{ color: var(--text); }}

    /* All-comps view */
    .all-comps {{ display: none; }}
    .all-comps.active {{ display: flex; flex: 1; overflow: hidden; }}
    .comp-slide {{ flex: 1; border-right: 1px solid var(--line); display: flex; flex-direction: column; min-width: 300px; background: var(--bg); }}
    .comp-slide-header {{ padding: 10px 12px; font-size: 13px; font-weight: 800; background: var(--surface); color: var(--text); text-align: center; border-bottom: 1px solid var(--line); }}
    .comp-slide-body {{ flex: 1; overflow-y: auto; padding: 10px; }}
    .comp-slide-group {{ margin-bottom: 12px; }}
    .comp-slide-group-title {{ font-size: 10px; font-weight: 800; text-transform: uppercase; color: var(--muted); padding: 4px 0; border-bottom: 1px solid var(--line); margin-bottom: 6px; }}
    .comp-slide-row {{ display: flex; gap: 4px; flex-wrap: wrap; }}
    .comp-slide-thumb {{ width: 60px; height: 60px; border-radius: var(--r-sm); overflow: hidden; border: 1px solid var(--line); }}
    .comp-slide-thumb img {{ width: 100%; height: 100%; object-fit: cover; }}

    ::selection {{ background: #E5E5E5; color: #111; }}
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: #181818; }}
    ::-webkit-scrollbar-thumb {{ background: #3A3A3A; border: 2px solid #181818; border-radius: 999px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #4A4A4A; }}
</style>
</head>
<body>

<div class="header">
    <h1>{brand} — Activity Slide Review</h1>
    <div class="subtitle">{from_date} to {to_date} · Drag posts into activity categories</div>
</div>

<div class="comp-tabs">
    <button class="comp-tab active" data-comp="all">All Competitors</button>
    {"".join(competitor_tabs)}
</div>

<div class="toolbar">
    <span class="stat"><strong id="total-count">0</strong> posts</span>
    <span class="stat"><strong id="categorized-count">0</strong> categorized</span>
    <span class="stat" id="uncategorized-count">0 uncategorized</span>
    <span class="spacer"></span>
    <label style="font-size:11px;color:#999">From:</label>
    <input type="date" id="dateFrom" value="{from_date}" style="padding:4px 8px;border:1px solid #cbd5e0;border-radius:4px;font-size:12px" />
    <label style="font-size:11px;color:#999">To:</label>
    <input type="date" id="dateTo" value="{to_date}" style="padding:4px 8px;border:1px solid #cbd5e0;border-radius:4px;font-size:12px" />
    <button class="btn btn-primary" id="filterDateBtn" style="font-size:11px">Filter</button>
    <label style="font-size:11px;color:#999">Sort:</label>
    <select id="sortMode" style="padding:4px 8px;border:1px solid #cbd5e0;border-radius:4px;font-size:12px">
        <option value="date_desc">Date newest</option>
        <option value="engagement_desc">Engagement highest</option>
        <option value="date_asc">Date oldest</option>
    </select>
    <span class="card-size-label">Card size:</span>
    <input type="range" class="card-size" id="cardSize" min="80" max="300" value="160" />
    <button class="btn" id="collapseSource">← Source</button>
    <button class="btn btn-success" id="saveBtn">Save All</button>
</div>

<div class="main" id="mainView">
    <!-- Single competitor view -->
    <div class="source-panel" id="sourcePanel">
        <div class="source-header">
            Uncategorized <span class="source-count" id="sourceCount">0</span>
        </div>
        <div class="source-cards" id="sourceCards" data-group="source">
        </div>
    </div>
    <div class="columns-container" id="columnsContainer">
        {"".join(column_htmls[g] for g in ACTIVITY_GROUPS)}
    </div>
</div>

<div id="imgPreview">
    <div class="preview-inner">
        <div class="preview-media"><img src="" alt="" /></div>
        <div class="preview-detail">
            <div class="preview-kicker"></div>
            <div class="preview-stats"></div>
            <div class="preview-cap"></div>
        </div>
    </div>
</div>

<div class="save-details" id="saveDetails" aria-live="polite"></div>
<div class="status-bar">
    <span class="save-status" id="saveStatus">Moves autosave locally; click Save All to sync Supabase</span>
    <span>Local layout stays when switching competitors or reopening this file</span>
</div>

<script>
const SUPABASE_URL = '{DEFAULT_SUPABASE_URL}';
const SUPABASE_KEY = '{DEFAULT_SUPABASE_KEY}';

// All competitor data
const ALL_DATA = {all_competitor_data_json};

let currentComp = 'all';
let changes = new Map();
let cardSize = 160;
const STORAGE_KEY = `activity-slide-review:${{location.pathname}}:${{document.getElementById('dateFrom').value}}:${{document.getElementById('dateTo').value}}`;
let localAssignments = loadLocalAssignments();

function loadLocalAssignments() {{
    try {{
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    }} catch (e) {{
        console.warn('Could not read local autosave', e);
        return {{}};
    }}
}}

function persistLocalAssignments(statusText) {{
    try {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify(localAssignments));
        if (statusText) setSaveStatus(statusText);
    }} catch (e) {{
        setSaveStatus(`Local autosave failed: ${{e.message}}`);
        setSaveDetails([`Browser localStorage error: ${{e.message}}`]);
    }}
}}

function setSaveStatus(text) {{
    document.getElementById('saveStatus').textContent = text;
}}

function setSaveDetails(messages, type = 'error') {{
    const details = document.getElementById('saveDetails');
    if (!messages || messages.length === 0) {{
        details.className = 'save-details';
        details.textContent = '';
        return;
    }}
    details.className = `save-details active ${{type === 'success' ? 'success' : ''}}`;
    details.textContent = messages.join('\\n');
}}

function findPost(postId, comp) {{
    if (comp && ALL_DATA[comp]) {{
        const post = ALL_DATA[comp].posts.find(p => p.id === postId);
        if (post) return post;
    }}
    for (const data of Object.values(ALL_DATA)) {{
        const post = data.posts.find(p => p.id === postId);
        if (post) return post;
    }}
    return null;
}}

function setPostGroup(postId, comp, group) {{
    const post = findPost(postId, comp);
    if (post) post.group = group || '';
}}

function pendingChangeEntries() {{
    return Object.entries(localAssignments).filter(([, data]) => !data.synced);
}}

function syncChangesFromLocal() {{
    changes.clear();
    for (const [postId, data] of Object.entries(localAssignments)) {{
        setPostGroup(postId, data.comp, data.group);
        if (!data.synced) changes.set(postId, data);
    }}
}}

function recordLocalChange(postId, comp, group) {{
    localAssignments[postId] = {{
        group: group || null,
        profile_id: getProfileId(comp),
        comp: comp || '',
        synced: false,
        updated_at: new Date().toISOString(),
    }};
    setPostGroup(postId, comp, group);
    changes.set(postId, localAssignments[postId]);
    const pending = pendingChangeEntries().length;
    persistLocalAssignments(`Autosaved locally · ${{pending}} pending DB save`);
    setSaveDetails([], 'success');
}}

syncChangesFromLocal();
const loadedLocalCount = Object.keys(localAssignments).length;
if (loadedLocalCount > 0) {{
    const pending = pendingChangeEntries().length;
    setSaveStatus(`Loaded ${{loadedLocalCount}} local classifications · ${{pending}} pending DB save`);
}}

// ── Competitor tabs ──
document.querySelectorAll('.comp-tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
        document.querySelectorAll('.comp-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentComp = tab.dataset.comp;
        rebuildView();
    }});
}});

// ── Date filter ──
document.getElementById('filterDateBtn').addEventListener('click', () => {{
    const fromDate = document.getElementById('dateFrom').value;
    const toDate = document.getElementById('dateTo').value;
    if (!fromDate || !toDate) {{ alert('Please select both dates'); return; }}
    // Filter posts by date
    for (const [name, data] of Object.entries(ALL_DATA)) {{
        data.posts = data.posts.filter(p => p.date >= fromDate && p.date <= toDate);
    }}
    rebuildView();
}});

// ── Sort mode ──
document.getElementById('sortMode').addEventListener('change', rebuildView);

// ── Card size slider ──
document.getElementById('cardSize').addEventListener('input', (e) => {{
    cardSize = parseInt(e.target.value);
    document.querySelectorAll('.post-img-wrap').forEach(w => {{
        w.style.height = cardSize + 'px';
    }});
}});

// ── Collapse source ──
document.getElementById('collapseSource').addEventListener('click', () => {{
    const panel = document.getElementById('sourcePanel');
    panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
}});

// ── Rebuild view for current competitor ──
function rebuildView() {{
    const sourceCards = document.getElementById('sourceCards');
    sourceCards.innerHTML = '';

    // Clear all columns
    document.querySelectorAll('.cat-cards').forEach(col => {{
        col.innerHTML = '<div class="empty-drop">Drop here</div>';
    }});

    // Collect posts
    let posts = [];
    if (currentComp === 'all') {{
        for (const [name, data] of Object.entries(ALL_DATA)) {{
            posts.push(...data.posts.map(p => ({{...p, comp: name}})));
        }}
    }} else {{
        const data = ALL_DATA[currentComp];
        if (data) posts = data.posts.map(p => ({{...p, comp: currentComp}}));
    }}

    // Sort cards within each bucket/column.
    const sortMode = document.getElementById('sortMode')?.value || 'date_desc';
    posts.sort((a, b) => {{
        if (sortMode === 'engagement_desc') {{
            return (engagementTotal(b) || 0) - (engagementTotal(a) || 0) || b.date.localeCompare(a.date);
        }}
        if (sortMode === 'date_asc') {{
            return a.date.localeCompare(b.date) || (engagementTotal(b) || 0) - (engagementTotal(a) || 0);
        }}
        return b.date.localeCompare(a.date) || (engagementTotal(b) || 0) - (engagementTotal(a) || 0);
    }});

    let categorized = 0;
    let uncategorized = 0;

    posts.forEach(post => {{
        const card = createCard(post);
        if (post.group && ['NPD','KOL','LAUNCH','SOCIAL & DIGITAL','ENGAGEMENT','BTL PROMO & ON-GROUND'].includes(post.group)) {{
            addToColumn(post.group, card);
            categorized++;
        }} else {{
            sourceCards.appendChild(card);
            uncategorized++;
        }}
    }});

    // Remove empty-drop placeholders if cards exist
    document.querySelectorAll('.cat-cards').forEach(col => {{
        const placeholder = col.querySelector('.empty-drop');
        if (placeholder && col.querySelectorAll('.post-card').length > 0) {{
            placeholder.remove();
        }}
    }});

    updateCounts(categorized, uncategorized);
    applyCardSize();
}}

function ownerFromId(postId) {{
    if (!postId || !postId.startsWith('ig_')) return '';
    const parts = postId.split('_');
    if (parts.length < 3) return '';
    parts.shift();
    parts.pop();
    return parts.join('_');
}}

function getPostOwner(post) {{
    return post.owner || post.owner_username || ownerFromId(post.id) || post.comp || 'Unknown';
}}

function getPostUrl(post) {{
    if (post.url) return post.url;
    if (!post.id) return '';
    const shortcode = post.id.split('_').pop();
    return shortcode ? `https://www.instagram.com/p/${{shortcode}}/` : '';
}}

function escapeHtml(value) {{
    return String(value || '').replace(/[&<>"']/g, ch => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }}[ch]));
}}

function hugeIcon(name) {{
    const icons = {{
        activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />',
        heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8Z" />',
        comment: '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z" />',
        share: '<circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 10.5 15.4 6.5" /><path d="M8.6 13.5 15.4 17.5" />',
        bookmark: '<path d="M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-6-4-6 4V4Z" />',
    }};
    return `<svg class="hi" viewBox="0 0 24 24" aria-hidden="true">${{icons[name] || icons.activity}}</svg>`;
}}

function numberOrNull(value) {{
    if (value === null || value === undefined || value === '') return null;
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
}}

function firstMetric(post, keys) {{
    for (const key of keys) {{
        const value = numberOrNull(post[key]);
        if (value !== null) return value;
    }}
    return null;
}}

function engagementTotal(post) {{
    const explicit = firstMetric(post, ['total_engagements', 'engagements', 'engagement']);
    if (explicit !== null) return explicit;
    const parts = ['likes', 'comments', 'shares', 'saves'].map(key => firstMetric(post, [key]));
    const known = parts.filter(value => value !== null);
    return known.length ? known.reduce((sum, value) => sum + value, 0) : null;
}}

function formatMetric(value) {{
    const num = numberOrNull(value);
    if (num === null) return '—';
    return new Intl.NumberFormat('en-US', {{ notation: num >= 10000 ? 'compact' : 'standard' }}).format(num);
}}

function metricRows(post) {{
    return [
        {{ label: 'Total engagements', value: engagementTotal(post), primary: true, short: 'Eng', icon: 'activity' }},
        {{ label: 'Likes', value: firstMetric(post, ['likes', 'like_count']), short: 'L', icon: 'heart' }},
        {{ label: 'Comments', value: firstMetric(post, ['comments', 'comment_count']), short: 'C', icon: 'comment' }},
        {{ label: 'Shares', value: firstMetric(post, ['shares', 'share_count']), short: 'Sh', icon: 'share' }},
        {{ label: 'Saves', value: firstMetric(post, ['saves', 'save_count']), short: 'Sv', icon: 'bookmark' }},
    ];
}}

function renderMetricChips(post) {{
    return metricRows(post).map(row =>
        `<span class="metric-chip${{row.primary ? ' primary' : ''}}" title="${{row.label}}">${{hugeIcon(row.icon)}}${{row.short}} ${{formatMetric(row.value)}}</span>`
    ).join('');
}}

function positionPreview(e) {{
    const preview = document.getElementById('imgPreview');
    const pw = preview.offsetWidth;
    const ph = preview.offsetHeight;
    let x = e.clientX + 16;
    let y = e.clientY - ph / 2;
    if (x + pw > window.innerWidth - 10) x = e.clientX - pw - 16;
    if (y < 10) y = 10;
    if (y + ph > window.innerHeight - 10) y = Math.max(10, window.innerHeight - ph - 10);
    preview.style.left = x + 'px';
    preview.style.top = y + 'px';
}}

function showPostPreview(post, e) {{
    const preview = document.getElementById('imgPreview');
    const img = preview.querySelector('img');
    img.src = post.img || '';
    img.style.display = post.img ? 'block' : 'none';
    preview.querySelector('.preview-kicker').innerHTML = [
        post.comp ? escapeHtml(post.comp) : '',
        post.date ? escapeHtml(post.date) : '',
        post.type ? escapeHtml(post.type) : '',
    ].filter(Boolean).map(item => `<span>${{item}}</span>`).join('');
    preview.querySelector('.preview-stats').innerHTML = metricRows(post).map(row => `
        <div class="preview-stat">
            <span>${{hugeIcon(row.icon)}}${{escapeHtml(row.label)}}</span>
            <strong>${{formatMetric(row.value)}}</strong>
        </div>
    `).join('');
    preview.querySelector('.preview-cap').textContent = post.caption || 'No caption';
    preview.style.display = 'block';
    positionPreview(e);
}}

function hidePostPreview() {{
    document.getElementById('imgPreview').style.display = 'none';
}}

function createCard(post) {{
    const card = document.createElement('article');
    card.className = 'post-card';
    card.draggable = true;
    card.dataset.id = post.id;
    card.dataset.comp = post.comp || '';

    const cap = post.caption || '';
    const compLabel = currentComp === 'all' ? `<span class="post-comp-label">${{escapeHtml(post.comp)}}</span> ` : '';
    const dateLabel = post.date ? `<span class="post-date-label">${{escapeHtml(post.date)}}</span> ` : '';
    const postUrl = getPostUrl(post).replace(/"/g, '%22');
    const postLink = postUrl ? `<a class="post-link" href="${{postUrl}}" target="_blank" rel="noopener noreferrer" title="Open Instagram post">Open post ↗</a>` : '';
    const tagged = Array.isArray(post.tagged_users) && post.tagged_users.length ? post.tagged_users.map(t => `@${{t}}`).join(', ') : '';
    const taggedText = tagged || 'none';
    const taggedClass = tagged ? 'post-tagged' : 'post-tagged muted';

    const safeCap = escapeHtml(cap);
    const hasLongCaption = cap.length > 140;

    card.innerHTML = `
        <div class="post-img-wrap">
            <img src="${{post.img}}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=no-img>No img</div>'" />
            <span class="type-badge">${{post.type}}</span>
        </div>
        <div class="post-info">
            <div class="post-meta-row"><span class="${{taggedClass}}" title="Tagged profiles: ${{escapeHtml(taggedText)}}">Tagged: ${{escapeHtml(taggedText)}}</span></div>
            ${{postLink ? `<div class="post-actions">${{postLink}}</div>` : ''}}
            <div>${{compLabel}}${{dateLabel}}</div>
            <div class="post-metrics">${{renderMetricChips(post)}}</div>
            <div class="post-cap" title="${{escapeHtml(cap)}}">${{safeCap}}</div>
            ${{hasLongCaption ? '<button type="button" class="see-more">See more</button>' : ''}}
        </div>
    `;

    const seeMoreBtn = card.querySelector('.see-more');
    if (seeMoreBtn) {{
        seeMoreBtn.addEventListener('click', (e) => {{
            e.preventDefault();
            e.stopPropagation();
            const expanded = card.classList.toggle('expanded');
            seeMoreBtn.textContent = expanded ? 'See less' : 'See more';
        }});
    }}

    card.addEventListener('mouseenter', (e) => showPostPreview(post, e));
    card.addEventListener('mousemove', positionPreview);
    card.addEventListener('mouseleave', hidePostPreview);

    // Drag events
    card.addEventListener('dragstart', (e) => {{
        e.dataTransfer.setData('text/plain', post.id);
        e.dataTransfer.setData('application/comp', post.comp || '');
        card.classList.add('dragging');
    }});
    card.addEventListener('dragend', () => card.classList.remove('dragging'));

    return card;
}}

function addToColumn(group, card) {{
    const col = document.querySelector(`.cat-cards[data-group="${{group}}"]`);
    if (col) {{
        const placeholder = col.querySelector('.empty-drop');
        if (placeholder) placeholder.remove();
        col.appendChild(card);
    }}
}}

function updateCounts(cat, uncat) {{
    document.getElementById('total-count').textContent = cat + uncat;
    document.getElementById('categorized-count').textContent = cat;
    document.getElementById('uncategorized-count').textContent = uncat + ' uncategorized';
    document.getElementById('sourceCount').textContent = uncat;
}}

function applyCardSize() {{
    document.querySelectorAll('.post-img-wrap').forEach(w => {{
        w.style.height = cardSize + 'px';
    }});
}}

// ── Drag and Drop ──
document.addEventListener('dragover', (e) => e.preventDefault());

document.querySelectorAll('.cat-cards, .source-cards').forEach(dropZone => {{
    dropZone.addEventListener('dragover', (e) => {{
        e.preventDefault();
        dropZone.classList.add('drag-over');
    }});
    dropZone.addEventListener('dragleave', () => {{
        dropZone.classList.remove('drag-over');
    }});
    dropZone.addEventListener('drop', (e) => {{
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const postId = e.dataTransfer.getData('text/plain');
        const comp = e.dataTransfer.getData('application/comp');
        const targetGroup = dropZone.dataset.group;

        const card = document.querySelector(`.post-card[data-id="${{postId}}"]`);
        if (!card) return;

        // Remove empty-drop placeholder
        const placeholder = dropZone.querySelector('.empty-drop');
        if (placeholder) placeholder.remove();

        dropZone.appendChild(card);

        // Autosave locally and update in-memory data so the layout survives tab switches.
        recordLocalChange(postId, comp, targetGroup === 'source' ? null : targetGroup);

        // Re-add empty state if column is empty
        document.querySelectorAll('.cat-cards').forEach(col => {{
            if (col.querySelectorAll('.post-card').length === 0 && !col.querySelector('.empty-drop')) {{
                col.innerHTML = '<div class="empty-drop">Drop here</div>';
            }}
        }});

        // Update counts
        let cat = 0, uncat = 0;
        document.querySelectorAll('.source-cards .post-card').forEach(() => uncat++);
        document.querySelectorAll('.cat-cards .post-card').forEach(() => cat++);
        updateCounts(cat, uncat);

        // Update source count
        document.getElementById('sourceCount').textContent = uncat;
    }});
}});

function getProfileId(comp) {{
    if (ALL_DATA[comp]) return ALL_DATA[comp].profile_id;
    for (const [name, data] of Object.entries(ALL_DATA)) {{
        if (name === comp) return data.profile_id;
    }}
    return '';
}}

// ── Save ──
document.getElementById('saveBtn').addEventListener('click', async () => {{
    const btn = document.getElementById('saveBtn');
    const pending = pendingChangeEntries();
    setSaveDetails([]);

    if (pending.length === 0) {{
        setSaveStatus('Nothing to save · local layout is already synced');
        return;
    }}

    btn.disabled = true;
    btn.textContent = `Saving 0/${{pending.length}}`;

    let saved = 0;
    const errors = [];

    for (let i = 0; i < pending.length; i++) {{
        const [postId, data] = pending[i];
        const label = `${{data.comp || 'Unknown competitor'}} · ${{data.group || 'Uncategorized'}}`;
        btn.textContent = `Saving ${{i + 1}}/${{pending.length}}`;
        setSaveStatus(`Saving ${{i + 1}}/${{pending.length}}: ${{label}}`);

        try {{
            const resp = await fetch(`${{SUPABASE_URL}}/rest/v1/competitor_posts?id=eq.${{encodeURIComponent(postId)}}`, {{
                method: 'PATCH',
                headers: {{
                    'apikey': SUPABASE_KEY,
                    'Authorization': `Bearer ${{SUPABASE_KEY}}`,
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal',
                }},
                body: JSON.stringify({{
                    activity_group: data.group ? [data.group] : [],
                }}),
            }});

            if (resp.ok) {{
                saved++;
                localAssignments[postId] = {{ ...data, synced: true, synced_at: new Date().toISOString() }};
            }} else {{
                const body = await resp.text().catch(() => '');
                errors.push(`${{label}} (${{postId}}): HTTP ${{resp.status}} ${{resp.statusText}}${{body ? ` — ${{body.slice(0, 300)}}` : ''}}`);
            }}
        }} catch (e) {{
            errors.push(`${{label}} (${{postId}}): ${{e.message || e}}`);
        }}

        persistLocalAssignments();
    }}

    syncChangesFromLocal();
    btn.disabled = false;
    btn.textContent = 'Save All';

    if (errors.length > 0) {{
        setSaveStatus(`Saved ${{saved}}/${{pending.length}} · ${{errors.length}} failed; see details`);
        setSaveDetails(['Some items did not save to Supabase. They remain autosaved locally and will retry next Save All:', ...errors]);
    }} else {{
        setSaveStatus(`Saved ${{saved}}/${{pending.length}} to Supabase · local layout kept`);
        setSaveDetails([`All ${{saved}} changes saved to Supabase. Local layout is also kept for this HTML file.`], 'success');
    }}
}});

// ── Init ──
rebuildView();
</script>
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(description='Activity Slide review page')
    parser.add_argument('--profile-ids', required=True, help='Comma-separated competitor_profiles UUIDs')
    parser.add_argument('--brand', required=True, help='Brand name')
    parser.add_argument('--from', dest='from_date', required=True)
    parser.add_argument('--to', dest='to_date', required=True)
    parser.add_argument('--output', default=None)
    parser.add_argument('--image-dir', default=IMAGE_DIR)
    args = parser.parse_args()

    supabase = get_supabase()
    profile_ids = [pid.strip() for pid in args.profile_ids.split(',')]

    # Get profile names
    all_profiles = supabase.table('competitor_profiles').select('id,name').execute().data or []
    name_map = {p['id']: p['name'] for p in all_profiles}

    all_posts_by_competitor = {}

    for pid in profile_ids:
        comp_name = name_map.get(pid, pid)
        print(f'Fetching {comp_name} ({args.from_date} to {args.to_date})...')
        result = supabase.table('competitor_posts') \
            .select('*') \
            .eq('profile_id', pid) \
            .eq('platform', 'instagram') \
            .gte('created_at', f'{args.from_date}T00:00:00') \
            .lte('created_at', f'{args.to_date}T23:59:59') \
            .order('created_at', desc=True) \
            .execute()
        posts = result.data or []
        print(f'  Found {len(posts)} posts')
        all_posts_by_competitor[comp_name] = posts

    total = sum(len(p) for p in all_posts_by_competitor.values())
    print(f'\nTotal: {total} posts across {len(profile_ids)} competitors')

    # Resolve output path
    default_name = f'{args.brand.lower().replace(" ", "_")}_activity_{args.from_date}_{args.to_date}.html'
    output_path = resolve_output_path(args.output or default_name)
    print(f'  Output: {output_path}')

    # Image directory: alongside the output file by default
    if os.path.isabs(args.image_dir):
        image_dir = args.image_dir
    elif args.image_dir == IMAGE_DIR:
        image_dir = os.path.join(os.path.dirname(output_path), 'ig_images')
    else:
        image_dir = os.path.join(os.getcwd(), args.image_dir)
    print(f'Downloading images to {image_dir}...')
    downloaded = 0
    for posts in all_posts_by_competitor.values():
        for p in posts:
            raw = p.get('raw', {})
            img_url = get_best_image_url(raw)
            if img_url:
                path = download_image(img_url, p['id'], image_dir)
                if path:
                    downloaded += 1
    print(f'  Downloaded {downloaded}/{total} images')

    # Generate HTML
    html = generate_html(all_posts_by_competitor, args.brand, args.from_date, args.to_date, image_dir)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\nReview page: {output_path}')


if __name__ == '__main__':
    main()
