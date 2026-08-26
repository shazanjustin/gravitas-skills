#!/usr/bin/env python3
"""Social Atlas competitor post ingestion via the app's own Supabase Edge Functions.

Reads VITE_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY from the Intel App repo .env
(falls back to environment variables). Never prints secrets.

Commands:
  own --profile CIMB --from 2026-07-01 --to 2026-07-31 [--platforms instagram,facebook]
  metricool --network facebook --from 2026-01-01 --to 2026-01-31 --user-id X --blog-id Y [--competitors "a,b"]
  tiktok --handles "@a,@b" --from 2026-01-01 --to 2026-01-31
  apify --actor clockworks/tiktok-scraper --platform tiktok --input-json '{"profiles":["@a"]}'
  dataset --url https://api.apify.com/v2/datasets/<id>/items?token=... --platform linkedin
  coverage
"""
import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

REPO_ENV = pathlib.Path("D:/vibe coding stuff/Gravitas Intel App/.env")
SKILL_ENV = pathlib.Path(__file__).resolve().parent.parent / ".env"


def _parse_env_text(text):
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return {k: v for k, v in values.items() if v}


GATEWAY_SECRETS = (
    "SOCIAL_ATLAS_AUTH_EMAIL",
    "SOCIAL_ATLAS_AUTH_PASSWORD",
    "SOCIAL_ATLAS_SUPABASE_URL",
    "SOCIAL_ATLAS_SUPABASE_ANON_KEY",
)


def _gateway_secret(name, gateway_url, gateway_key):
    """Fetch one secret from the Gravitas API Gateway.

    Cloudflare rejects Python's default urllib User-Agent with `code: 1010`
    ("banned based on your browser's signature") on every gateway endpoint, so a
    curl-like UA is required, not optional.
    """
    import urllib.error
    request = urllib.request.Request(
        f"{gateway_url.rstrip('/')}/secret/{name}",
        headers={"x-api-key": gateway_key, "User-Agent": "curl/8.4.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response).get("value") or ""
    except (urllib.error.URLError, ValueError):
        return ""


def load_gateway_env():
    """Credentials come from the gateway so this skill holds no secrets itself.

    Reads the gateway key from ~/.gravitas-skills/.env, the same place the
    gravitas-gateway skill puts it. Absent or unreachable, callers fall back to a
    local .env, which is how a laptop without gateway access still works.
    """
    gateway_env = pathlib.Path.home() / ".gravitas-skills" / ".env"
    if not gateway_env.exists():
        return {}
    config = _parse_env_text(gateway_env.read_text(encoding="utf-8", errors="ignore"))
    url = config.get("GRAVITAS_GATEWAY_URL")
    key = config.get("GRAVITAS_GATEWAY_KEY")
    if not url or not key:
        return {}
    fetched = {}
    for name in GATEWAY_SECRETS:
        value = _gateway_secret(name, url, key)
        if value:
            fetched[name] = value
    return fetched


def load_env():
    # Precedence, lowest to highest: gateway -> local .env files -> real env vars.
    # The gateway is the shared source of truth; a local .env is an escape hatch.
    values = dict(load_gateway_env())
    for path in (REPO_ENV, SKILL_ENV):
        if path.exists():
            values.update(_parse_env_text(path.read_text(encoding="utf-8", errors="ignore")))
    import os
    return {**values, **{
        k: v for k, v in os.environ.items()
        if k in ("VITE_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SOCIAL_ATLAS_AUTH_EMAIL", "SOCIAL_ATLAS_AUTH_PASSWORD") and v
    }}


def auth_header(env):
    """Prefer the automation service account (admin user token) over the service key.

    Deployed edge functions compare against the platform-managed SUPABASE_SERVICE_ROLE_KEY
    secret, which is a stale value we cannot override; a real admin user token passes
    requireAdminUser cleanly.
    """
    email = env.get("SOCIAL_ATLAS_AUTH_EMAIL")
    password = env.get("SOCIAL_ATLAS_AUTH_PASSWORD")
    if email and password:
        base = env["VITE_SUPABASE_URL"].rstrip("/")
        req = urllib.request.Request(
            base + "/auth/v1/token?grant_type=password",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"apikey": env.get("VITE_SUPABASE_ANON_KEY", env["SUPABASE_SERVICE_ROLE_KEY"]), "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            return "Bearer " + json.load(response)["access_token"]
    return "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"]


def call_function(env, endpoint, payload, timeout=600):
    base = env["VITE_SUPABASE_URL"].rstrip("/")
    req = urllib.request.Request(
        f"{base}/functions/v1/{endpoint}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": auth_header(env),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:500]
        sys.exit(f"{endpoint} failed HTTP {error.code}: {body}")


def rest_count(env, params):
    import urllib.parse
    query = urllib.parse.urlencode({"select": "id", **params})
    req = urllib.request.Request(
        env["VITE_SUPABASE_URL"].rstrip("/") + "/rest/v1/competitor_posts?" + query,
        headers={
            "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
            "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"],
            "Accept": "application/json",
            "Prefer": "count=exact",
            "Range": "0-0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        total = response.headers.get("content-range", "*/0").rsplit("/", 1)[1]
    return int(total)


def fetch_profile(env, name):
    """Look up a profile row (with its stored Metricool credentials) by name."""
    import urllib.parse
    query = urllib.parse.urlencode({
        "select": "id,name,metricool_api_key,metricool_user_id,metricool_blog_id,metricool_brand_name",
        "name": f"eq.{name}",
    })
    req = urllib.request.Request(
        env["VITE_SUPABASE_URL"].rstrip("/") + "/rest/v1/competitor_profiles?" + query,
        headers={
            "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
            "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"],
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        rows = json.load(response)
    if not rows:
        sys.exit(f"No profile named {name!r}")
    row = rows[0]
    missing = [k for k in ("metricool_api_key", "metricool_user_id", "metricool_blog_id") if not row.get(k)]
    if missing:
        sys.exit(f"Profile {name!r} is missing stored credentials: {missing}")
    return row


def cmd_own(args, env):
    """Ingest the OWN brand's own posts (not its competitors) from Metricool."""
    profile = fetch_profile(env, args.profile)
    payload = {
        "profileId": profile["id"],
        "metricoolApiKey": profile["metricool_api_key"],
        "metricoolUserId": profile["metricool_user_id"],
        "metricoolBlogId": profile["metricool_blog_id"],
        "metricoolBrandName": profile.get("metricool_brand_name"),
        "platforms": [p.strip() for p in args.platforms.split(",") if p.strip()],
        "from": args.from_date,
        "to": args.to_date,
    }
    result = call_function(env, "metricool-own-profile-ingest", payload)
    print(json.dumps(result, indent=2))


def cmd_metricool(args, env):
    payload = {
        "network": args.network,
        "from": args.from_date,
        "to": args.to_date,
        "limit": args.limit,
    }
    if args.user_id:
        payload["userId"] = args.user_id
    if args.blog_id:
        payload["blogId"] = args.blog_id
    if args.timezone:
        payload["timezone"] = args.timezone
    if args.competitors:
        payload["competitors"] = [c.strip() for c in args.competitors.split(",") if c.strip()]
    result = call_function(env, "metricool-competitors-ingest", payload)
    print(json.dumps(result, indent=2))


def cmd_tiktok(args, env):
    profiles = [h.strip() for h in args.handles.split(",") if h.strip()]
    payload = {
        "actorId": "clockworks/tiktok-scraper",
        "platform": "tiktok",
        "input": {
            "excludePinnedPosts": False,
            "profiles": profiles,
            # Without resultsPerPage the actor returns ONE video per profile and the run
            # looks like a success. The scraper walks newest-first and then applies the
            # date bounds, so this must cover everything posted since --to, not just the
            # window itself. Cost scales with videos scraped, so keep it tight.
            "resultsPerPage": args.limit,
            "shouldDownloadSubtitles": False,
            "shouldDownloadVideos": False,
            "oldestPostDateUnified": args.from_date,
            "newestPostDate": args.to_date,
        },
    }
    result = call_function(env, "apify-ingest", payload)
    print(json.dumps(result, indent=2))


def cmd_apify(args, env):
    payload = {"actorId": args.actor, "input": json.loads(args.input_json or "{}")}
    if args.platform:
        payload["platform"] = args.platform
    result = call_function(env, "apify-ingest", payload)
    print(json.dumps(result, indent=2))


def cmd_dataset(args, env):
    payload = {"datasetUrl": args.url}
    if args.platform:
        payload["platform"] = args.platform
    result = call_function(env, "apify-dataset-import", payload)
    print(json.dumps(result, indent=2))


def cmd_coverage(args, env):
    """Coverage per platform, including the two failures that make rows INVISIBLE in the UI.

    A rising row count proves nothing. The competitor table needs BOTH:
      * created_at populated  - a NULL date drops the post out of every date filter
      * raw.inputUrl matching competitor_profile_inputs EXACTLY - otherwise the post
        maps to no brand and the whole platform column reads 0
    Both bugs shipped silently with `ok: true` and a healthy `upserted` count.
    """
    rows = []
    for platform in ("facebook", "instagram", "tiktok", "linkedin", "youtube", "twitter"):
        total = rest_count(env, {"platform": f"eq.{platform}"})
        if not total:
            continue
        unmapped = rest_count(env, {"platform": f"eq.{platform}", "profile_id": "is.null"})
        no_date = rest_count(env, {"platform": f"eq.{platform}", "created_at": "is.null"})
        rows.append({
            "platform": platform,
            "total": total,
            "mapped": total - unmapped,
            "unmapped_profile_id": unmapped,
            "null_created_at": no_date,
            "INVISIBLE_no_date": no_date,
        })
    print(json.dumps(rows, indent=2))

    # A post can be present, dated and branded, and STILL be useless: if the actor nested
    # its metrics, the UI reads 0 engagement because pickMetric() in src/utils/metrics.ts
    # only looks at TOP-LEVEL keys of raw. Mirror that exact key list here - counting rows
    # matching ANY of them, not summing per key (a row can carry several).
    LIKE_KEYS = ["likesCount", "likeCount", "numLikes", "likes", "reactions", "like_count", "diggCount"]
    print("")
    for platform in ("facebook", "instagram", "tiktok", "linkedin", "youtube"):
        total = rest_count(env, {"platform": f"eq.{platform}"})
        if not total:
            continue
        any_key = ",".join(f"raw->>{key}.not.is.null" for key in LIKE_KEYS)
        flat = rest_count(env, {"platform": f"eq.{platform}", "or": f"({any_key})"})
        pct = round(100.0 * flat / total, 1) if total else 0.0
        flag = "  <-- CHECK: metrics likely nested where the UI cannot read them" if pct < 90 else ""
        print(f"  {platform:<10} {flat:5d}/{total:<6d} readable engagement ({pct}%){flag}")

    known = set(fetch_all_input_urls(env))
    orphans = {}
    for url, count in fetch_input_url_histogram(env).items():
        if url and url not in known:
            orphans[url] = count
    if orphans:
        print("\nWARNING - raw.inputUrl values matching NO competitor_profile_inputs row.")
        print("These posts exist in the table but map to no brand, so the UI shows 0:")
        for url, count in sorted(orphans.items(), key=lambda kv: -kv[1]):
            print(f"  {count:5d}  {url}")
    else:
        print("\nAll inputUrl values map to a known competitor input.")


def fetch_all_input_urls(env):
    import urllib.parse
    query = urllib.parse.urlencode({"select": "input_url"})
    req = urllib.request.Request(
        env["VITE_SUPABASE_URL"].rstrip("/") + "/rest/v1/competitor_profile_inputs?" + query,
        headers={
            "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
            "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"],
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return [row["input_url"] for row in json.load(response)]


def fetch_input_url_histogram(env):
    """Count posts per raw.inputUrl, paging through the REST API."""
    import urllib.parse
    counts = {}
    offset, page = 0, 1000
    while True:
        query = urllib.parse.urlencode({"select": "raw", "limit": page, "offset": offset})
        req = urllib.request.Request(
            env["VITE_SUPABASE_URL"].rstrip("/") + "/rest/v1/competitor_posts?" + query,
            headers={
                "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
                "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"],
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            batch = json.load(response)
        for row in batch:
            url = (row.get("raw") or {}).get("inputUrl")
            if isinstance(url, str) and url.startswith("http"):
                counts[url] = counts.get(url, 0) + 1
        if len(batch) < page:
            break
        offset += page
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("metricool")
    p.add_argument("--network", required=True, help="facebook|instagram|youtube|twitter|...")
    p.add_argument("--from", dest="from_date", required=True)
    p.add_argument("--to", dest="to_date", required=True)
    p.add_argument("--user-id")
    p.add_argument("--blog-id")
    p.add_argument("--competitors")
    p.add_argument("--timezone", default="Asia/Kuala_Lumpur")
    p.add_argument("--limit", type=int, default=1000)
    p.set_defaults(func=cmd_metricool)

    p = sub.add_parser("own")
    p.add_argument("--profile", required=True, help="own-brand profile name, e.g. CIMB")
    p.add_argument("--from", dest="from_date", required=True)
    p.add_argument("--to", dest="to_date", required=True)
    p.add_argument("--platforms", default="instagram,facebook,linkedin,youtube,tiktok")
    p.set_defaults(func=cmd_own)

    p = sub.add_parser("tiktok")
    p.add_argument("--handles", required=True, help="comma-separated @handles")
    p.add_argument("--from", dest="from_date", required=True)
    p.add_argument("--to", dest="to_date", required=True)
    p.add_argument("--limit", type=int, default=60, help="resultsPerPage per profile")
    p.set_defaults(func=cmd_tiktok)

    p = sub.add_parser("apify")
    p.add_argument("--actor", required=True)
    p.add_argument("--platform")
    p.add_argument("--input-json", default="{}")
    p.set_defaults(func=cmd_apify)

    p = sub.add_parser("dataset")
    p.add_argument("--url", required=True)
    p.add_argument("--platform")
    p.set_defaults(func=cmd_dataset)

    sub.add_parser("coverage").set_defaults(func=cmd_coverage)

    args = parser.parse_args()
    env = load_env()
    missing = [k for k in ("VITE_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not env.get(k)]
    if missing:
        sys.exit(f"Missing env: {missing}. Expected in {REPO_ENV}")
    args.func(args, env)


if __name__ == "__main__":
    main()
