"""
Shared utilities for Intel IG Manager — Supabase connection, profile listing,
competitor resolution, and session management.

Credentials are read from:
  1. Environment variables (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
  2. .env file in the skill root directory
  3. Hardcoded defaults (fallback)
"""
import os
import sys
import json
import pickle
from pathlib import Path
import requests
from typing import Optional
from supabase import create_client

# ── Skill root directory (parent of scripts/) ──
SKILL_DIR = Path(__file__).resolve().parent.parent

# ── Try loading .env from skill root ──
_dotenv = SKILL_DIR / '.env'
if _dotenv.exists():
    with open(_dotenv) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())

# ── Default credentials (read from env, then .env, then hardcoded fallback) ──
DEFAULT_SUPABASE_URL = os.environ.get('SUPABASE_URL') or 'https://kzobygrjohvbuxiljbgk.supabase.co'
DEFAULT_SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6b2J5Z3Jqb2h2YnV4aWxqYmdrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODI0Njk0MSwiZXhwIjoyMDgzODIyOTQxfQ.JgkVfMVnAydX4WKwbSO1l-bGKfEDAOpjDA2tFv6ZxBA'
DEFAULT_SESSION_FILE = os.environ.get('INSTALOADER_SESSION') or 'C:/Users/dell/AppData/Local/Instaloader/session-_notakaki'
DEFAULT_OUTPUT_DIR = os.environ.get('IG_MANAGER_OUTPUT_DIR') or str(SKILL_DIR)


def get_supabase(url=None, key=None):
    """Create a Supabase client (uses service_role key for RLS bypass)."""
    return create_client(
        url or DEFAULT_SUPABASE_URL,
        key or DEFAULT_SUPABASE_KEY,
    )


def fetch_json(url, key, table, params=None):
    """Raw REST GET to Supabase."""
    h = {'apikey': key, 'Authorization': f'Bearer {key}'}
    r = requests.get(f'{url}/rest/v1/{table}', params=params, headers=h, timeout=15)
    r.raise_for_status()
    return r.json()


def list_account_profiles(url=None, key=None):
    """Return all account profiles (is_own_profile = true) with their competitor counts."""
    u = url or DEFAULT_SUPABASE_URL
    k = key or DEFAULT_SUPABASE_KEY
    h = {'apikey': k, 'Authorization': f'Bearer {k}'}

    # Get all profiles
    r = requests.get(f'{u}/rest/v1/competitor_profiles', params={
        'select': 'id,name,is_own_profile,slug,meta_ig_id'
    }, headers=h, timeout=10)
    profiles = r.json()

    # Get all relationships
    r2 = requests.get(f'{u}/rest/v1/profile_competitors', params={
        'select': 'profile_id,competitor_profile_id'
    }, headers=h, timeout=10)
    rels = r2.json()

    # Build name map
    name_map = {p['id']: p for p in profiles}

    # Get input URLs for IG handles
    r3 = requests.get(f'{u}/rest/v1/competitor_profile_inputs', params={
        'select': 'profile_id,input_url'
    }, headers=h, timeout=10)
    inputs = r3.json()

    input_map = {}
    for inp in inputs:
        pid = inp['profile_id']
        if pid not in input_map:
            input_map[pid] = []
        input_map[pid].append(inp['input_url'])

    # Build account profiles
    accounts = []
    for p in profiles:
        if p.get('is_own_profile'):
            comp_ids = [r['competitor_profile_id'] for r in rels if r['profile_id'] == p['id']]
            competitors = []
            for cid in comp_ids:
                cp = name_map.get(cid, {})
                # Extract clean IG usernames from input URLs
                ig_handles_clean = []
                for s in input_map.get(cid, []):
                    s = s.strip()
                    if 'instagram.com/' in s:
                        username = s.rstrip('/').split('/')[-1]
                        ig_handles_clean.append(username)
                    elif s.startswith('@') and 'tiktok' not in s and 'facebook' not in s:
                        ig_handles_clean.append(s[1:])
                competitors.append({
                    'id': cid,
                    'name': cp.get('name', '?'),
                    'slug': cp.get('slug'),
                    'meta_ig_id': cp.get('meta_ig_id'),
                    'ig_handles': ig_handles_clean,
                })
            accounts.append({
                'id': p['id'],
                'name': p['name'],
                'slug': p.get('slug'),
                'meta_ig_id': p.get('meta_ig_id'),
                'competitors': competitors,
            })

    # Also add competitor-only profiles (not linked to any account)
    orphans = []
    for p in profiles:
        if not p.get('is_own_profile'):
            linked = any(r['competitor_profile_id'] == p['id'] for r in rels)
            if not linked:
                ig_handles_clean = []
                for s in input_map.get(p['id'], []):
                    s = s.strip()
                    if 'instagram.com/' in s:
                        ig_handles_clean.append(s.rstrip('/').split('/')[-1])
                    elif s.startswith('@') and 'tiktok' not in s and 'facebook' not in s:
                        ig_handles_clean.append(s[1:])
                orphans.append({
                    'id': p['id'],
                    'name': p['name'],
                    'slug': p.get('slug'),
                    'meta_ig_id': p.get('meta_ig_id'),
                    'ig_handles': ig_handles_clean,
                })

    return accounts, orphans, name_map


def get_posts_in_range(supabase, profile_id, platform, from_date, to_date, limit=500):
    """Fetch competitor_posts for a profile in a date range."""
    result = supabase.table('competitor_posts') \
        .select('*') \
        .eq('profile_id', profile_id) \
        .eq('platform', platform) \
        .gte('created_at', f'{from_date}T00:00:00') \
        .lte('created_at', f'{to_date}T23:59:59') \
        .order('created_at', desc=True) \
        .limit(limit) \
        .execute()
    return result.data or []


def build_ig_session(session_file=None):
    """Build a requests.Session from an Instaloader pickle file."""
    sf = session_file or DEFAULT_SESSION_FILE
    if not os.path.exists(sf):
        raise FileNotFoundError(f'Session file not found: {sf}')

    with open(sf, 'rb') as f:
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


def resolve_ig_username(input_urls):
    """Try to extract an IG username from competitor_profile_input entries."""
    for s in input_urls or []:
        s = s.strip()
        if '@' in s:
            return s.lstrip('@')
        if 'instagram.com/' in s:
            parts = s.rstrip('/').split('/')
            return parts[-1]
    return None


def resolve_output_path(path_or_name, default_dir=None):
    """
    Resolve an output file path.
    
    If the path is absolute, return as-is.
    If relative, resolve against default_dir (or the configured output dir).
    """
    p = Path(path_or_name)
    if p.is_absolute():
        return str(p)
    base = Path(default_dir) if default_dir else Path(DEFAULT_OUTPUT_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return str(base / p.name)
