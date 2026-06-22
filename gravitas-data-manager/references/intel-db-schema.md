# Intel App Database Schema Reference

Key tables for the IG Manager workflow in Supabase project `kzobygrjohvbuxiljbgk`.

## competitor_profiles

| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` PK | Primary key |
| `name` | `text` | Display name (e.g. "Friso Gold", "Anmum") |
| `slug` | `text` | URL-friendly identifier (e.g. "friso-gold") |
| `is_own_profile` | `boolean` | `true` = account you manage, `false` = competitor |
| `meta_ig_id` | `text` | Instagram Business Account ID (for Meta API) |
| `meta_page_id` | `text` | Facebook Page ID (for Meta API) |
| `metricool_*` | various | Metricool API configuration |

**Key profiles (as of June 2026):**

| Name | Type | Slug |
|------|------|------|
| Friso Gold | Own | `friso-gold` |
| CIMB | Own | `cimb` |
| 7Days | Own | `7days` |
| Enfagrow | Competitor | — |
| Anmum | Competitor | — |
| Morinaga | Competitor | — |
| S26 | Competitor | — |
| Ensure Gold | Competitor | — |

## profile_competitors

Links account profiles (`is_own_profile = true`) to their competitors.

| Column | Type |
|--------|------|
| `profile_id` | `uuid` FK → `competitor_profiles.id` (the account) |
| `competitor_profile_id` | `uuid` FK → `competitor_profiles.id` (the competitor) |

**Relationships:**
- Friso Gold → Enfagrow, Anmum, Morinaga, S26, Ensure Gold
- CIMB → RHB, Maybank, BSN, ASNB

## competitor_profile_inputs

Stores platform handles and URLs for each profile (used to map names to actual accounts).

| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` PK | |
| `profile_id` | `uuid` FK | → competitor_profiles.id |
| `input_url` | `text` | URL or handle (e.g. `@anmumessentialmy`, `https://instagram.com/anmumessentialmy/`) |

IG handles are stored with or without `@` prefix. The skill extracts the username by stripping `@` or parsing `instagram.com/...`.

## competitor_posts

The main posts table. Full schema in `supabase-schema.md` (or see `src/types/supabase.ts`).

Key fields used by this skill:
- `id` — Format: `ig_{username}_{shortcode}`
- `profile_id` — Links to competitor_profiles
- `platform` — `'instagram'`
- `created_at` — Post timestamp
- `campaign_label` — AI-tagged campaign
- `post_type` — Content type (null on ingest, set by AI pipeline)
- `post_type_source` — `'manual'`, `'auto'`, `'metricool'`
- `raw` — JSONB with full Instagram API response
- `meta_post_id` — Instagram shortcode
- `original_thumbnail_url` — Expiring CDN URL

### Key fields in `raw` JSONB

```jsonc
{
  "code": "DZHbg8zvhfC",            // Shortcode
  "caption": "...",
  "likes": 283,
  "comments": 37,
  "video_view_count": null,
  "media_type": 2,                  // 1=image, 2=video, 8=carousel
  "post_type": "video",             // Media format
  "display_url": "https://...",     // CDN URL (expires)
  "post_url": "https://www.instagram.com/p/DZHbg8zvhfC/",
  "tagged_users": ["user1", "user2"],
  "is_collab": true,                // Has co-authors or tags
  "owner_username": "anmumessentialmy"
}
```

## competitor_platform_tags

Content-type tags per profile per platform.

| Column | Type |
|--------|------|
| `profile_id` | `uuid` FK |
| `platform` | `text` |
| `tags` | `text[]` (e.g. `['Product', 'Promo', 'Education']`) |

## Key Queries

```sql
-- Get account profiles with competitor names
SELECT p.name, p.slug, cp.name AS competitor
FROM competitor_profiles p
JOIN profile_competitors pc ON pc.profile_id = p.id
JOIN competitor_profiles cp ON cp.id = pc.competitor_profile_id
WHERE p.is_own_profile = true;

-- Get IG handles for a profile
SELECT input_url
FROM competitor_profile_inputs
WHERE profile_id = '<uuid>';

-- Get posts for a competitor in date range
SELECT id, created_at, raw->>'likes' AS likes,
       raw->>'is_collab' AS is_collab
FROM competitor_posts
WHERE profile_id = '<uuid>'
  AND platform = 'instagram'
  AND created_at >= '2026-05-01'
  AND created_at < '2026-06-01'
ORDER BY created_at DESC;
```
