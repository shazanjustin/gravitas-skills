"""
Fetch Instagram posts (including collab/partner posts) from a public profile
using Instagram's internal REST API with a logged-in session.

Usage:
    python scripts/ingest_ig_posts.py \\
        --username TARGET_PROFILE \\
        --session-file /path/to/session-_yourlogin \\
        --supabase-url https://project.supabase.co \\
        --supabase-key your-service-role-key \\
        --profile-id COMPETITOR_PROFILE_UUID \\
        --from 2026-05-01 \\
        --to 2026-05-31

Requires:
    pip install requests supabase

Session file:
    Create via Instaloader:
        instaloader --login YOUR_IG_USERNAME
    Session saved to ~/AppData/Local/Instaloader/session-YOUR_IG_USERNAME
    Or on Linux: ~/.config/instaloader/session-YOUR_IG_USERNAME
"""
import os
import sys
import json
import pickle
import time
import argparse
import requests
from datetime import datetime, timezone, date
from supabase import create_client


def build_session(session_file: str) -> requests.Session:
    """Build a requests.Session with Instagram cookies from an Instaloader pickle."""
    with open(session_file, 'rb') as f:
        cookies = pickle.load(f)

    s = requests.Session()
    for k, v in cookies.items():
        s.cookies.set(k, v)

    s.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36'
        ),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'X-IG-App-ID': '936619743392459',
        'X-CSRFToken': cookies.get('csrftoken', ''),
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.instagram.com/',
    })
    return s


def get_user_id(session: requests.Session, username: str) -> tuple:
    """Fetch the Instagram user ID for the target username."""
    url = f'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}'
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    user = data['data']['user']
    return user['id'], user


def fetch_posts(
    session: requests.Session,
    user_id: str,
    start_date: date,
    end_date: date,
    delay: float = 1.5,
) -> list:
    """
    Fetch all posts in date range using Instagram's internal feed/user API.
    Returns Instagram API item dicts.
    """
    all_items = []
    next_max_id = None
    stop = False
    page = 0

    while not stop:
        page += 1
        url = f'https://www.instagram.com/api/v1/feed/user/{user_id}/?count=50'
        if next_max_id:
            url += f'&max_id={next_max_id}'

        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            print(f'  [WARN] Page {page}: HTTP {resp.status_code}')
            break

        data = resp.json()
        items = data.get('items', [])
        more = data.get('more_available', False)
        next_max_id = data.get('next_max_id')

        if items:
            oldest = datetime.fromtimestamp(items[-1]['taken_at'], tz=timezone.utc).date()
            newest = datetime.fromtimestamp(items[0]['taken_at'], tz=timezone.utc).date()
            print(f'  Page {page}: {len(items)} items ({oldest}..{newest})')
        else:
            print(f'  Page {page}: 0 items')

        # Count how many items on this page are before our date range
        old_count = 0
        for item in items:
            post_date = datetime.fromtimestamp(item['taken_at'], tz=timezone.utc).date()
            if post_date < start_date:
                old_count += 1
            elif post_date <= end_date:
                all_items.append(item)
        
        # Only stop if ALL items on this page are before our range
        # (mixed-order feeds may have old pinned posts mixed with new ones)
        if old_count == len(items) and len(items) > 0:
            stop = True

        if not more or not next_max_id or stop:
            break

        if page % 5 == 0:
            time.sleep(delay * 2)  # Extra delay every 5 pages
        else:
            time.sleep(delay)

    return all_items


def extract_metrics(item: dict) -> tuple:
    """Extract likes, comments, video views from an API item."""
    likes = item.get('like_count', 0)
    comments = item.get('comment_count', 0)
    views = item.get('view_count')

    # Fallback to GraphQL-style fields if present
    if not likes:
        likes = item.get('edge_liked_by', {}).get('count', 0) or \
                item.get('edge_media_preview_like', {}).get('count', 0)
    if not comments:
        comments = item.get('edge_media_to_comment', {}).get('count', 0)

    return likes, comments, views


def transform_item(item: dict, username: str, user_id: str, profile_id: str) -> dict:
    """Transform an Instagram API item into a competitor_posts row dict."""
    code = item.get('code') or item.get('shortcode', '')
    ts = item['taken_at']
    post_date = datetime.fromtimestamp(ts, tz=timezone.utc)

    # Media type: 1=image, 2=video, 8=carousel
    media_type = item.get('media_type', 1)
    type_map = {1: 'image', 2: 'video', 8: 'carousel'}
    ptype = type_map.get(media_type, 'unknown')

    # Caption
    caption = ''
    cap_data = item.get('caption')
    if isinstance(cap_data, dict):
        caption = cap_data.get('text', '')
    elif isinstance(cap_data, str):
        caption = cap_data

    # Metrics
    likes, comments, views = extract_metrics(item)

    # Tagged users (collab detection)
    tagged_users = []
    usertags = item.get('usertags', {}).get('in', [])
    for tag in usertags:
        u = tag.get('user', {})
        if u and u.get('username'):
            tagged_users.append(u['username'])

    # Coauthor producers (proper Instagram collab tag)
    for ca in item.get('coauthor_producers', []):
        if isinstance(ca, dict) and ca.get('username'):
            tagged_users.append(ca['username'])

    # fb_user_tags (additional collab tagging)
    for tag in item.get('fb_user_tags', {}).get('in', []):
        u = tag.get('user', {})
        if u and u.get('username') and u['username'] not in tagged_users:
            tagged_users.append(u['username'])

    # Carousel children
    carousel_media = []
    if media_type == 8:
        for cm in item.get('carousel_media', []):
            cm_type = type_map.get(cm.get('media_type', 1), 'unknown')
            img = cm.get('image_versions2', {}) or {}
            candidates = img.get('candidates', [])
            cm_url = candidates[0].get('url', '') if candidates else ''
            carousel_media.append({'media_type': cm_type, 'url': cm_url})

    # Display / thumbnail URL
    image_versions = item.get('image_versions2', {}) or {}
    candidates = image_versions.get('candidates', [])
    display_url = candidates[0].get('url', '') if candidates else ''

    # Video URL
    video_url = None
    if media_type == 2:
        video_versions = item.get('video_versions', [])
        if video_versions:
            video_url = video_versions[0].get('url', '')

    # Deduplicate tagged users
    tagged_users = list(set(u for u in tagged_users if u))

    raw = {
        'code': code,
        'pk': item.get('pk', ''),
        'id': item.get('id', ''),
        'owner_username': username,
        'owner_id': user_id,
        'caption': caption,
        'date_utc': post_date.isoformat(),
        'taken_at': ts,
        'likes': likes,
        'comments': comments,
        'video_view_count': views,
        'media_type': media_type,
        'post_type': ptype,
        'display_url': display_url,
        'video_url': video_url,
        'post_url': f'https://www.instagram.com/p/{code}/',
        'tagged_users': tagged_users,
        'is_collab': len(tagged_users) > 0,
        'carousel_media': carousel_media or None,
        'product_type': item.get('product_type'),
        'location': item.get('location'),
        'comments_disabled': item.get('comments_disabled', False),
    }

    return {
        'id': f'ig_{username}_{code}',
        'profile_id': profile_id,
        'platform': 'instagram',
        'created_at': post_date.isoformat(),
        'campaign_source': 'manual',
        'post_type_source': 'manual',
        'post_type': None,  # Let AI tagging / pipeline handle this
        'raw': raw,
        'meta_post_id': code,
        'original_thumbnail_url': display_url,
    }


def upsert_to_supabase(
    posts: list,
    supabase_url: str,
    supabase_key: str,
    batch_size: int = 50,
):
    """Upsert rows into competitor_posts. Returns (already_exist, new_count)."""
    supabase = create_client(supabase_url, supabase_key)

    # Check which already exist
    ids = [p['id'] for p in posts]
    result = supabase.table('competitor_posts') \
        .select('id') \
        .in_('id', ids) \
        .execute()
    already = {r['id'] for r in (result.data or [])}

    new_posts = [p for p in posts if p['id'] not in already]
    if not new_posts:
        return already, 0

    for i in range(0, len(new_posts), batch_size):
        batch = new_posts[i:i + batch_size]
        supabase.table('competitor_posts').upsert(batch).execute()

    return already, len(new_posts)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch Instagram posts (incl. collabs) for a profile and upsert to Supabase.',
    )
    parser.add_argument('--username', required=True, help='Instagram username to scrape (e.g. anmumessentialmy)')
    parser.add_argument('--session-file', required=True, help='Path to Instaloader session pickle file')
    parser.add_argument('--supabase-url', required=True, help='Supabase project URL')
    parser.add_argument('--supabase-key', required=True, help='Supabase service_role key (bypasses RLS)')
    parser.add_argument('--profile-id', required=True, help='competitor_profiles UUID for this account')
    parser.add_argument('--from', dest='from_date', required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--to', dest='to_date', required=True, help='End date YYYY-MM-DD')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between API calls (seconds)')
    args = parser.parse_args()

    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)

    print(f'[instaloader-ig-scraper]')
    print(f'  Profile: @{args.username}')
    print(f'  Period:  {start} to {end}')
    print(f'  Session: {args.session_file}')
    print()

    # 1. Build session
    print('Building session...')
    session = build_session(args.session_file)

    # 2. Get user ID
    print(f'Fetching profile @{args.username}...')
    uid, profile_data = get_user_id(session, args.username)
    print(f'  User ID: {uid}')
    print(f'  Name: {profile_data.get("full_name", "")}')
    print(f'  Followers: {profile_data.get("edge_followed_by", {}).get("count", "?")}')

    # 3. Fetch posts
    print(f'\nFetching posts...')
    items = fetch_posts(session, uid, start, end, delay=args.delay)
    print(f'\n  Found {len(items)} posts in date range')

    if not items:
        print('No posts found. Exiting.')
        return

    # 4. Transform
    posts = [transform_item(it, args.username, uid, args.profile_id) for it in items]

    # Deduplicate by ID
    seen = set()
    deduped = []
    for p in posts:
        if p['id'] not in seen:
            seen.add(p['id'])
            deduped.append(p)
    posts = deduped
    print(f'  After dedup: {len(posts)}')

    # 5. Upsert to Supabase
    print('\nUpserting to Supabase...')
    already, new_count = upsert_to_supabase(posts, args.supabase_url, args.supabase_key)
    print(f'  Already in DB: {len(already)}')
    print(f'  Newly inserted: {new_count}')

    # 6. Stats
    collab = sum(1 for p in posts if p['raw'].get('is_collab'))
    media_types = {}
    for p in posts:
        mt = p['raw'].get('post_type', 'unknown')
        media_types[mt] = media_types.get(mt, 0) + 1

    print(f'\n{"=" * 60}')
    print(f'  Profile: @{args.username}')
    print(f'  Period:  {start} to {end}')
    print(f'  Total posts: {len(posts)}')
    print(f'  New: {new_count}  Existing: {len(already)}')
    print(f'  Collab posts: {collab}')
    print(f'  Types: {media_types}')
    print(f'{"=" * 60}')

    # 7. Print posts
    print(f'\n--- Posts ---')
    for p in sorted(posts, key=lambda x: x['created_at'], reverse=True):
        dt = p['created_at'][:10]
        likes = p['raw']['likes']
        comments = p['raw']['comments']
        cap = (p['raw']['caption'] or '')[:70].replace('\n', ' ').strip()
        tagged = p['raw'].get('tagged_users', [])
        tag_str = f' [collab: {", ".join(tagged)}]' if tagged else ''
        views = p['raw'].get('video_view_count')
        views_str = f' views:{views}' if views else ''
        print(f'  {dt} | {p["raw"]["post_type"]:8s} | '
              f'likes:{likes:4d} comments:{comments:2d}{views_str} | '
              f'{cap}{tag_str}')


if __name__ == '__main__':
    main()
