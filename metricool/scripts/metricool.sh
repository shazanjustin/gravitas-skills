#!/usr/bin/env bash
# ============================================================================
# metricool.sh — Metricool API helper (auto-discovering)
# ============================================================================
# Discovers brands, networks, and API endpoints at runtime — nothing
# hardcoded. Brands and network availability are always fetched live.
#
# Quick start:
#   bash scripts/metricool.sh setup
#   # → paste your API token from Metricool → Account Settings → API
#   bash scripts/metricool.sh brands
#
# Commands:
#   setup               One-time setup: prompts for API token, saves to .env
#   brands              List all connected brands
#   info [blogId]       Show brand details + connected networks
#   networks [blogId]   List which social networks a brand has
#   posts <network> [blogId] [from] [to]
#                       Get posts for a network (instagram, facebook,
#                       linkedin, tiktok, twitter, youtube, bluesky,
#                       threads, pinterest)
#   reels [blogId] [from] [to]          Instagram reels
#   stories [blogId] [from] [to]        Instagram stories
#   besttimes <provider> [blogId]       Best posting times
#   scheduled [blogId] [from] [to]      List scheduled posts
#   competitors <network> [blogId]      List competitors
#   competitor-posts <network> [blogId] [from] [to]
#                                       Get competitor posts
#   demographics <provider> [blogId]    Gender+age distribution
#   summary [blogId]                    Quick brand overview
#   export <blogId> <from> [to]         Export analytics to JSON
#   swagger (--list|--search <q>|--service <name>)
#                                       Query the live API specification
#   swagger --refresh                   Re-fetch cached swagger
#   raw <endpoint> [blogId] [params]    Raw GET to any endpoint
#   help                                Show this message
#
# Credentials (in order of precedence):
#   1. Environment variable METRICOOL_TOKEN
#   2. .env file (created by 'setup' command, gitignored)
#
# User ID can be overridden via METRICOOL_USER_ID env var.
# Date: v2 endpoints need ISO datetime YYYY-MM-DDThh:mm:ss
#       Legacy endpoints accept YYYY-MM-DD
# ============================================================================

set -euo pipefail

BASE_URL="https://app.metricool.com/api"
SWAGGER_URL="https://app.metricool.com/api/swagger.json"
SWAGGER_CACHE="${METRICOOL_CACHE_DIR:-$(python -c "import tempfile; print(tempfile.gettempdir().replace(chr(92), '/') + '/metricool_swagger.json')" 2>/dev/null || echo /tmp/metricool_swagger.json)}"

# ISO datetime defaults (last 30 days)
DEFAULT_FROM=$(python -c "from datetime import datetime, timedelta; print((datetime.now()-timedelta(days=30)).strftime('%Y-%m-%dT00:00:00'))" 2>/dev/null || echo "rolling")
DEFAULT_TO=$(python -c "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%dT23:59:59'))" 2>/dev/null || echo "today")

METRICOOL_TOKEN="${METRICOOL_TOKEN:-}"
METRICOOL_USER_ID="${METRICOOL_USER_ID:-4327762}"

# Resolve the project root (parent of scripts/ directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

# Load .env if present and METRICOOL_TOKEN not already set in environment
if [ -z "$METRICOOL_TOKEN" ] && [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
usage() {
    sed -n '3,/^$/p' "$0" | sed 's/^# //; s/^#$//' | head -n -1
    exit 0
}

die() { echo "ERROR: $*" >&2; exit 1; }

warn() { echo "WARNING: $*" >&2; }

check_token() {
    if [ -z "$METRICOOL_TOKEN" ]; then
        die "METRICOOL_TOKEN is not set.\n\nRun setup first:\n  bash scripts/metricool.sh setup\n\nOr export it:\n  export METRICOOL_TOKEN=your_token"
    fi
}

api_get() {
    local endpoint="$1"
    local blog_id="${2:-}"
    shift 2
    check_token
    local url="${BASE_URL}${endpoint}?userId=${METRICOOL_USER_ID}&userToken=${METRICOOL_TOKEN}"
    [ -n "$blog_id" ] && url="${url}&blogId=${blog_id}"
    [ $# -gt 0 ] && url="${url}&$*"
    curl -s -G "$url" -H "Accept: application/json" --data-urlencode "" 2>/dev/null || curl -s "$url" -H "Accept: application/json"
}

pretty() {
    python -m json.tool 2>/dev/null || python -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, default=str))" 2>/dev/null || cat
}

# Get brand info JSON, return as base64 for safe piping
fetch_brand_info() {
    local blog_id="$1"
    api_get "/v2/settings/brands/${blog_id}" "$blog_id"
}

# Check if a brand has a specific network. Returns 0 (yes) or 1 (no).
has_network() {
    local blog_id="$1"
    local target="$2"  # lowercase, e.g. "instagram", "facebook"
    local data
    data=$(fetch_brand_info "$blog_id")
    python -c "
import sys, json
d = json.loads('''${data//\'/\'\"\'\"\'}''').get('data', {})
nd = d.get('networksData', {})
target = '${target}'.lower()
for k in nd:
    if target in k.lower():
        sys.exit(0)
sys.exit(1)
" 2>/dev/null && return 0 || return 1
}

# Get networks a brand has, one per line (machine-readable)
get_networks() {
    local blog_id="$1"
    local data
    data=$(fetch_brand_info "$blog_id")
    python -c "
import sys, json
d = json.loads('''${data//\'/\'\"\'\"\'}''').get('data', {})
nd = d.get('networksData', {})
for k, v in nd.items():
    name = k.replace('Data','').replace('facebookAds','facebook_ads').replace('gbp','google_business').lower()
    uname = v.get('username', v.get('providerUserId', '?')) if isinstance(v, dict) else '?'
    print(f'{name}:{uname}')
" 2>/dev/null
}

# Get human-readable network names
get_network_names() {
    local blog_id="$1"
    local data
    data=$(fetch_brand_info "$blog_id")
    python -c "
import sys, json
d = json.loads('''${data//\'/\'\"\'\"\'}''').get('data', {})
nd = d.get('networksData', {})
for k in nd:
    name = k.replace('Data','').replace('facebookAds','Facebook Ads').replace('gbp','Google Business Profile')
    print(name)
" 2>/dev/null
}

# Find brands that have a specific network
brands_with_network() {
    local target="$1"
    check_token
    local brands_json
    brands_json=$(api_get "/admin/simpleProfiles" "")
    python -c "
import sys, json
import urllib.request, base64

target = '${target}'.lower()
data = json.loads('''${brands_json//\'/\'\"\'\"\'}''')
items = data if isinstance(data, list) else data.get('brands', data.get('data', []))
# We can't check networks without extra API calls per brand, so
# just return the brand list and let the caller filter
for b in items:
    bid = b.get('blogId') or b.get('id') or '?'
    label = b.get('label') or b.get('title') or '?'
    print(f'{bid}:{label}')
" 2>/dev/null
}

# Get swagger, with caching
get_swagger() {
    # Check cache age (max 1 hour)
    if [ -f "$SWAGGER_CACHE" ]; then
        local age
        age=$(python -c "import os, time; print(int(time.time() - os.path.getmtime('${SWAGGER_CACHE}')))" 2>/dev/null)
        if [ -n "$age" ] && [ "$age" -lt 3600 ]; then
            cat "$SWAGGER_CACHE"
            return
        fi
    fi
    # Fetch
    curl -sL "$SWAGGER_URL" > "$SWAGGER_CACHE" 2>/dev/null || true
    cat "$SWAGGER_CACHE" 2>/dev/null || die "Failed to fetch swagger"
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
cmd_brands() {
    check_token
    echo "=== Connected Brands ===" >&2
    local raw
    raw=$(api_get "/admin/simpleProfiles" "")
    local b64
    b64=$(echo "$raw" | python -c "import sys,base64; print(base64.b64encode(sys.stdin.buffer.read()).decode())")
    pydata "$b64" <<- 'PYEOF'
		items = json_data if isinstance(json_data, list) else json_data.get('brands', json_data.get('data', []))
		for b in items:
		    bid = b.get('blogId') or b.get('id') or '?'
		    label = b.get('label') or b.get('title') or '?'
		    print(f'  {str(bid):>8s}  {label}')
	PYEOF
}

cmd_info() {
    local blog_id="${1:-}"
    if [ -z "$blog_id" ]; then
        echo "Usage: info <blogId>" >&2
        echo "Run 'brands' to see available blogIds." >&2
        return 1
    fi
    local raw
    raw=$(fetch_brand_info "$blog_id")
    local b64
    b64=$(echo "$raw" | python -c "import sys,base64; print(base64.b64encode(sys.stdin.buffer.read()).decode())")
    pydata "$b64" <<- 'PYEOF'
		d = json_data.get('data', {})
		print(f'  Name:     {d.get("label", "?")}')
		print(f'  Blog ID:  {d.get("id", "?")}')
		print(f'  Owner:    {d.get("ownerUsername", "?")}')
		nd = d.get('networksData', {})
		if nd:
		    print(f'  Networks:')
		    for k, v in nd.items():
		        name = k.replace('Data','').replace('facebookAds','Facebook Ads').replace('gbp','Google Business Profile')
		        uname = v.get('username', v.get('providerUserId', '?'))
		        print(f'    o {name:30s} @{uname}')
		else:
		    print(f'  Networks: (none connected)')
	PYEOF
}

cmd_networks() {
    local blog_id="${1:-}"
    if [ -z "$blog_id" ]; then
        echo "Usage: networks <blogId>" >&2
        return 1
    fi
    local nets
    nets=$(get_networks "$blog_id")
    if [ -z "$nets" ]; then
        echo "  (no networks connected)" >&2
        return
    fi
    echo "$nets" | while IFS=: read -r net uname; do
        echo "  $net: @$uname"
    done
}

# Network-aware wrapper: checks if brand has the network before calling
require_network() {
    local network="$1"
    local blog_id="$2"
    local cmd_name="$3"  # for error messages

    if ! has_network "$blog_id" "$network"; then
        echo "❌ Brand $blog_id doesn't have \"$network\" connected." >&2
        # Find brands that DO have this network
        local alternatives
        alternatives=$(brands_with_network "$network" 2>/dev/null | head -5)
        if [ -n "$alternatives" ]; then
            echo "" >&2
            echo "Brands that DO have $network:" >&2
            echo "$alternatives" | while IFS=: read -r bid label; do
                if has_network "$bid" "$network" 2>/dev/null; then
                    echo "  $bid  $label" >&2
                fi
            done
        fi
        return 1
    fi
    return 0
}

cmd_posts() {
    local network="${1:-}"
    local blog_id="${2:-}"
    if [ -z "$network" ] || [ -z "$blog_id" ]; then
        echo "Usage: posts <network> <blogId> [from] [to]" >&2
        echo "Networks: instagram, facebook, linkedin, tiktok, twitter, youtube, bluesky, threads, pinterest" >&2
        return 1
    fi
    require_network "$network" "$blog_id" "posts" || return 1
    local from="${3:-$DEFAULT_FROM}"
    local to="${4:-$DEFAULT_TO}"
    echo "=== ${network} posts (${from} to ${to}) ===" >&2
    api_get "/v2/analytics/posts/${network}" "$blog_id" "from=${from}&to=${to}&size=50" | pretty
}

cmd_reels() {
    local blog_id="${1:-}"
    if [ -z "$blog_id" ]; then
        echo "Usage: reels <blogId> [from] [to]" >&2
        return 1
    fi
    require_network "instagram" "$blog_id" "reels" || return 1
    local from="${2:-$DEFAULT_FROM}"
    local to="${3:-$DEFAULT_TO}"
    echo "=== Instagram Reels (${from} to ${to}) ===" >&2
    api_get "/v2/analytics/reels/instagram" "$blog_id" "from=${from}&to=${to}&size=50" | pretty
}

cmd_stories() {
    local blog_id="${1:-}"
    if [ -z "$blog_id" ]; then
        echo "Usage: stories <blogId> [from] [to]" >&2
        return 1
    fi
    require_network "instagram" "$blog_id" "stories" || return 1
    local from="${2:-$DEFAULT_FROM}"
    local to="${3:-$DEFAULT_TO}"
    echo "=== Instagram Stories (${from} to ${to}) ===" >&2
    api_get "/v2/analytics/stories/instagram" "$blog_id" "from=${from}&to=${to}&size=50" | pretty
}

cmd_besttimes() {
    local provider="${1:-}"
    local blog_id="${2:-}"
    if [ -z "$provider" ] || [ -z "$blog_id" ]; then
        echo "Usage: besttimes <provider> <blogId>" >&2
        echo "Providers: instagram, facebook, linkedin, tiktok, twitter, youtube" >&2
        return 1
    fi
    require_network "$provider" "$blog_id" "besttimes" || return 1
    echo "=== Best Posting Times: ${provider} ===" >&2
    api_get "/v2/scheduler/besttimes/${provider}" "$blog_id" | pretty
}

cmd_scheduled() {
    local blog_id="${1:-}"
    if [ -z "$blog_id" ]; then
        echo "Usage: scheduled <blogId> [from] [to]" >&2
        return 1
    fi
    local from="${2:-$(python -c "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%dT00:00:00'))" 2>/dev/null)}"
    local to="${3:-$(python -c "from datetime import datetime, timedelta; print((datetime.now()+timedelta(days=30)).strftime('%Y-%m-%dT23:59:59'))" 2>/dev/null)}"
    echo "=== Scheduled Posts (${from} to ${to}) ===" >&2
    api_get "/v2/scheduler/posts" "$blog_id" "from=${from}&to=${to}" | pretty
}

cmd_competitors() {
    local network="${1:-}"
    local blog_id="${2:-}"
    if [ -z "$network" ] || [ -z "$blog_id" ]; then
        echo "Usage: competitors <network> <blogId>" >&2
        return 1
    fi
    require_network "$network" "$blog_id" "competitors" || return 1
    echo "=== Competitors: ${network} ===" >&2
    api_get "/v2/analytics/competitors/${network}" "$blog_id" | pretty
}

cmd_competitor_posts() {
    local network="${1:-}"
    local blog_id="${2:-}"
    if [ -z "$network" ] || [ -z "$blog_id" ]; then
        echo "Usage: competitor-posts <network> <blogId> [from] [to]" >&2
        return 1
    fi
    require_network "$network" "$blog_id" "competitor-posts" || return 1
    local from="${3:-$DEFAULT_FROM}"
    local to="${4:-$DEFAULT_TO}"
    echo "=== Competitor Posts: ${network} (${from} to ${to}) ===" >&2
    api_get "/v2/analytics/competitors/${network}/posts" "$blog_id" "from=${from}&to=${to}" | pretty
}

cmd_demographics() {
    local provider="${1:-}"
    local blog_id="${2:-}"
    if [ -z "$provider" ] || [ -z "$blog_id" ]; then
        echo "Usage: demographics <provider> <blogId>" >&2
        return 1
    fi
    require_network "$provider" "$blog_id" "demographics" || return 1
    echo "=== Demographics: ${provider} ===" >&2
    api_get "/stats/gender-age/${provider}" "$blog_id" | pretty
}

cmd_summary() {
    local blog_id="${1:-}"
    if [ -z "$blog_id" ]; then
        echo "Usage: summary <blogId>" >&2
        return 1
    fi
    local raw
    raw=$(fetch_brand_info "$blog_id")
    local b64
    b64=$(echo "$raw" | python -c "import sys,base64; print(base64.b64encode(sys.stdin.buffer.read()).decode())")

    echo "============================================" >&2
    echo "  Metricool Summary" >&2
    echo "============================================" >&2

    pydata "$b64" <<- 'PYEOF'
		d = json_data.get('data', {})
		print(f'  Brand:      {d.get("label", "?")}')
		print(f'  Blog ID:    {d.get("id", "?")}')
		print(f'  Owner:      {d.get("ownerUsername", "?")}')
		nd = d.get('networksData', {})
		if nd:
		    names = []
		    for k, v in nd.items():
		        name = k.replace('Data','').replace('facebookAds','FB Ads').replace('gbp','GBP')
		        uname = v.get('username', '?')
		        names.append(f'{name} (@{uname})')
		    print(f'  Networks:   {", ".join(names)}')
		else:
		    print(f'  Networks:   (none)')
	PYEOF

    echo "" >&2
    echo "--- Connected networks ---" >&2
    local nets
    nets=$(get_networks "$blog_id")
    if [ -z "$nets" ]; then
        echo "  (none)" >&2
        return
    fi
    echo "$nets" | while IFS=: read -r net uname; do
        echo "  $net: @$uname" >&2
    done
}

cmd_export() {
    local blog_id="${1:-}"
    local from="${2:-$DEFAULT_FROM}"
    local to="${3:-$DEFAULT_TO}"
    if [ -z "$blog_id" ]; then
        echo "Usage: export <blogId> [from] [to]" >&2
        return 1
    fi
    local safe_from="${from%%T*}"
    local safe_to="${to%%T*}"
    local ts
    ts=$(python -c "from datetime import datetime; print(datetime.now().strftime('%Y%m%d_%H%M%S'))")
    local outfile="metricool_export_${blog_id}_${ts}.json"

    echo "Exporting blog ${blog_id} (${from} to ${to})..." >&2
    echo "Output: ${outfile}" >&2

    python -c "
import json, subprocess, sys, os

blog_id = '${blog_id}'
from_d = '${from}'
to_d = '${to}'
safe_from = '${safe_from}'
safe_to = '${safe_to}'
base = '${BASE_URL}'
uid = '${METRICOOL_USER_ID}'
token = os.environ.get('METRICOOL_TOKEN', '')
outfile = '${outfile}'

def api(endpoint, params=''):
    url = f'{base}{endpoint}?blogId={blog_id}&userId={uid}&userToken={token}'
    if params:
        url += f'&{params}'
    try:
        r = subprocess.run(['curl', '-s', url], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except:
        return {'_error': str(sys.exc_info()[1])}

export = {
    'blogId': blog_id,
    'from': from_d,
    'to': to_d,
    'exported_at': from_d,
}

brand = api(f'/v2/settings/brands/{blog_id}')
export['brand_info'] = brand
d = brand.get('data', {})
nd = d.get('networksData', {})

net_map = {
    'instagram': ('/v2/analytics/posts/instagram', True),
    'facebook': ('/v2/analytics/posts/facebook', False),
    'linkedin': ('/v2/analytics/posts/linkedin', False),
    'tiktok': ('/v2/analytics/posts/tiktok', False),
    'twitter': ('/v2/analytics/posts/twitter', False),
    'youtube': ('/v2/analytics/posts/youtube', False),
    'bluesky': ('/v2/analytics/posts/bluesky', False),
    'threads': ('/v2/analytics/posts/threads', False),
    'pinterest': ('/v2/analytics/posts/pinterest', False),
}

has_instagram = False
for k in nd:
    n = k.replace('Data','').replace('facebookAds','').replace('gbp','').lower()
    if n == 'instagram':
        has_instagram = True
    entry = net_map.get(n)
    if entry:
        ep, _ = entry
        print(f'  Fetching {n}...', file=sys.stderr)
        export[f'posts_{n}'] = api(ep, f'from={from_d}&to={to_d}&size=100')

if has_instagram:
    for tp in ['reels', 'stories']:
        print(f'  Fetching Instagram {tp}...', file=sys.stderr)
        export[f'instagram_{tp}'] = api(f'/v2/analytics/{tp}/instagram', f'from={from_d}&to={to_d}&size=100')

print('  Fetching legacy stats...', file=sys.stderr)
export['legacy_stats'] = api('/stats/values/community', f'from={safe_from}&to={safe_to}')

with open(outfile, 'w') as f:
    json.dump(export, f, indent=2, default=str)

sz = os.path.getsize(outfile)
print(f'Done - {sz} bytes written to {outfile}', file=sys.stderr)
" 2>&1
}

cmd_swagger() {
    local mode="${1:-}"

    # Ensure swagger is cached
    get_swagger > /dev/null 2>&1
    local cache="${SWAGGER_CACHE}"

    case "$mode" in
        --list|-l)
            echo "=== Metricool API Services ===" >&2
            python -c "
import json
with open('${cache}') as f:
    spec = json.load(f)
tags = spec.get('tags', [])
path_tags = set()
for path, methods in spec.get('paths', {}).items():
    for m, details in methods.items():
        for t in details.get('tags', []):
            path_tags.add(t)
all_tags = sorted(set(t['name'] for t in tags) | path_tags)
for t in all_tags:
    print(t)
" 2>/dev/null
            ;;
        --search|-s)
            local query="${2:-}"
            if [ -z "$query" ]; then
                echo "Usage: swagger --search <keyword>" >&2
                return 1
            fi
            echo "=== Searching for \"$query\" in API spec ===" >&2
            python -c "
import json
with open('${cache}') as f:
    spec = json.load(f)
query = '${query}'.lower()
paths = spec.get('paths', {})
found = 0
for path in sorted(paths.keys()):
    if query in path.lower():
        for method, details in paths[path].items():
            tags = ', '.join(details.get('tags', []))
            summary = details.get('summary', details.get('operationId', ''))
            print(f'  {method.upper():6s} {path}')
            if summary:
                print(f'         {summary}')
            if tags:
                print(f'         [{tags}]')
            print()
            found += 1
if found == 0:
    print(f'  No endpoints matching \"${query}\"')
    print(f'  Try: swagger --list (to see all services)')
" 2>/dev/null
            ;;
        --service|-svc)
            local service="${2:-}"
            if [ -z "$service" ]; then
                echo "Usage: swagger --service <service-name>" >&2
                return 1
            fi
            echo "=== Endpoints for service: $service ===" >&2
            python -c "
import json
with open('${cache}') as f:
    spec = json.load(f)
service = '${service}'.lower()
paths = spec.get('paths', {})
found = 0
for path in sorted(paths.keys()):
    for method, details in paths[path].items():
        tags = [t.lower() for t in details.get('tags', [])]
        if service in tags:
            summary = details.get('summary', details.get('operationId', ''))
            print(f'  {method.upper():6s} {path}')
            if summary:
                print(f'         {summary}')
            print()
            found += 1
if found == 0:
    print(f'  No endpoints found for service \"${service}\"')
" 2>/dev/null
            ;;
        --refresh|-r)
            rm -f "$SWAGGER_CACHE"
            echo "Swagger cache cleared. Will re-fetch on next command." >&2
            ;;
        *)
            echo "Usage: swagger <option>" >&2
            echo "  --list              List all API services" >&2
            echo "  --search <keyword>  Search endpoints by keyword" >&2
            echo "  --service <name>    List endpoints for a service" >&2
            echo "  --refresh           Clear cached swagger" >&2
            ;;
    esac
}

cmd_raw() {
    local endpoint="${1:-}"
    local blog_id="${2:-}"
    if [ -z "$endpoint" ]; then
        echo "Usage: raw <endpoint> [blogId] [params...]" >&2
        echo "Endpoint is the URL path starting with / (e.g. /v2/analytics/hashtags)" >&2
        return 1
    fi
    shift 2
    api_get "$endpoint" "$blog_id" "$*" | pretty
}

# ---------------------------------------------------------------------------
# Setup / .env management
# ---------------------------------------------------------------------------
cmd_setup() {
    local env_file="$ENV_FILE"

    echo "======================================" >&2
    echo "  Metricool API — One-Time Setup" >&2
    echo "======================================" >&2
    echo "" >&2
    echo "You need your Metricool API token." >&2
    echo "Find it at: Metricool → Account Settings → API" >&2
    echo "" >&2

    # Check if .env already has a token
    if [ -f "$env_file" ]; then
        local existing
        existing=$(grep "^METRICOOL_TOKEN=" "$env_file" 2>/dev/null | head -1 | cut -d= -f2)
        if [ -n "$existing" ] && [ ${#existing} -gt 10 ]; then
            echo "ℹ️  .env already has a token saved. Overwrite?" >&2
            echo -n "Type 'yes' to overwrite, anything else to cancel: " >&2
            local answer
            IFS= read -r answer
            if [ "$answer" != "yes" ]; then
                echo "Setup cancelled. Existing token kept." >&2
                return 0
            fi
        fi
    fi

    echo -n "Paste your Metricool API token: " >&2
    IFS= read -r token || true
    token="${token//[[:space:]]/}"

    if [ -z "$token" ]; then
        echo "❌ No token entered. Setup cancelled." >&2
        return 1
    fi

    # Ask for optional userId override
    local user_id="${METRICOOL_USER_ID:-4327762}"
    echo "" >&2
    echo "Your user ID is $user_id (default). Change it? (press Enter to keep)" >&2
    echo -n "User ID [$user_id]: " >&2
    IFS= read -r uid_input || true
    uid_input="${uid_input//[[:space:]]/}"
    if [ -n "$uid_input" ]; then
        user_id="$uid_input"
    fi

    # Write .env
    cat > "$env_file" <<- ENVEOF
		# Metricool API credentials
		# Created by 'setup' command — keep this file private!
		METRICOOL_TOKEN=${token}
		METRICOOL_USER_ID=${user_id}
	ENVEOF

    chmod 600 "$env_file" 2>/dev/null || true
    echo "" >&2
    echo "✅ Token saved to $(python -c "import os; print(os.path.relpath('${env_file}'))" 2>/dev/null || echo "$env_file")" >&2
    echo "   File permissions set to 600 (owner read/write only)." >&2
    echo "" >&2
    echo "Run 'brands' to verify it works:" >&2
    echo "  bash scripts/metricool.sh brands" >&2
}

# Run Python code with base64-encoded JSON data
pydata() {
    local b64json="$1"
    shift
    python -c "
import json, base64, sys
json_data = json.loads(base64.b64decode('${b64json}').decode('utf-8'))
$(cat)
" "$@"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    case "$cmd" in
        setup|init|configure)  cmd_setup "$@" ;;
        brands|list)           cmd_brands "$@" ;;
        info)                  cmd_info "$@" ;;
        networks|nets)         cmd_networks "$@" ;;
        posts)                 cmd_posts "$@" ;;
        reels)                 cmd_reels "$@" ;;
        stories)               cmd_stories "$@" ;;
        besttimes)             cmd_besttimes "$@" ;;
        scheduled|sched)       cmd_scheduled "$@" ;;
        competitors|comp)      cmd_competitors "$@" ;;
        competitor-posts|cposts) cmd_competitor_posts "$@" ;;
        demographics|demo)     cmd_demographics "$@" ;;
        summary)               cmd_summary "$@" ;;
        export)                cmd_export "$@" ;;
        swagger|api|spec)      cmd_swagger "$@" ;;
        raw)                   cmd_raw "$@" ;;
        help|--help|-h)        usage ;;
        *)                     echo "Unknown: $cmd" >&2; usage ;;
    esac
}

main "$@"
