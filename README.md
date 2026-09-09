# Gravitas Skills

Agent skills for Gravitas Digital social-media reporting, competitor
intelligence, paid-media checks and client deliverables, packaged as a Claude
Code plugin.

## Install

```
/plugin marketplace add shazanjustin/gravitas-skills
/plugin install gravitas@gravitas-skills
```

You are prompted for the **Gravitas Gateway API key** during install. Ask Shazan
or your team lead for it. That one key unlocks Metricool, Apify and the
server-side Meta endpoints from `gateway.shazan.me`, so you never paste an
individual API key, and nothing is written to a `.env` file on your disk. Claude
Code stores it in your OS keychain.

If the install summary says `Run /reload-plugins to activate.`, run that.

## What you get

Skills are namespaced under the plugin, so they appear as `/gravitas:<name>`.
Claude also loads them on its own when a task matches their description.

| Skill | What it does | Gateway |
|-------|--------------|:---:|
| `gravitas-gateway` | Credential layer for everything below | — |
| `gravitas-data-manager` | FB/IG/TikTok data: own-brand via Meta + Metricool, competitors via Instaloader/Apify. Owns the Intel App database | yes |
| `metricool` | Metricool REST API: analytics, scheduled posts, competitors, one-shot competitor report to a Google Sheet | yes |
| `metricool-engagement-rate-xlsx` | Per-post engagement-rate proof workbooks (IG, TikTok) | yes |
| `metricool-engagement-rate-xlsx-v2` | Same, plus YouTube and LinkedIn | yes |
| `social-atlas-ingest` | Ingest competitor content into the Social Atlas database, with the pg_cron scheduler | yes |
| `pitch-competitor-research` | New-business pitch intel: scrape five platforms, transcribe video, build an executive-brief HTML dossier | yes |
| `paid-ads-spend-router` | Paid-media spend and campaign metrics, picked from the campaign objective | yes |
| `performance-tracker` | The NocoDB Performance table: read, add, edit, and print the team digest | yes |
| `performance-social-report-slides` | Quarterly report .xlsx into a PPTX deck plus an HTML thumbnail gallery | yes |
| `social-thumbnail-fetcher` | Instagram and TikTok post URLs into direct thumbnail image URLs | — |
| `client-friendly-report-writer` | Raw metrics into calm, client-facing report copy | — |
| `datasheet-to-gsheet-mapper` | Messy Metricool CSVs into a target Google Sheet's exact columns | — |
| `fill-linkedin-content-types` | Classify LinkedIn posts into content types | — |
| `youtube-publish-date-bulk` | Bulk YouTube URLs into publish dates, sheet-ready | — |

## Using it on a team repo

A plugin installed with `/plugin` lives in `~/.claude/plugins/` on that machine
only. It does not follow you to another laptop or into a cloud session.

To make it available to everyone working in a given repository, commit this to
that repo's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "gravitas-skills": {
      "source": { "source": "github", "repo": "shazanjustin/gravitas-skills" }
    }
  },
  "enabledPlugins": {
    "gravitas@gravitas-skills": true
  }
}
```

Once a teammate trusts the repo folder, Claude Code registers the marketplace
without another prompt. Locally they still run `claude plugin install
gravitas@gravitas-skills` once; cloud sessions install it at session start.

## Using it in Claude Code cloud sessions

`/plugin` does not exist in cloud sessions, so there are two ways in:

1. **Commit the repo settings above.** Plugins declared in a repo's
   `.claude/settings.json` are installed when the cloud session starts.
2. **Enable the plugin for your claude.ai account.** Cloud sessions download
   account-enabled plugins and load them as `gravitas@synced`, in every repo,
   with no per-repo config. They do not load in your local terminal, so install
   locally as well.

Two things to configure on the cloud environment at claude.ai/code, or nothing
will work:

- **Network access.** The default **Trusted** level allowlists package
  registries and GitHub, not `gateway.shazan.me`. Switch to **Custom** and
  allowlist `gateway.shazan.me`, plus whichever of `api.metricool.com`,
  `api.apify.com`, `graph.facebook.com` and `openrouter.ai` you need.
- **`GRAVITAS_GATEWAY_KEY`** as an environment variable, since the plugin cannot
  prompt for it there. Anyone using that environment can read its variables, so
  use a dedicated environment rather than a shared one.

## Development

```
claude --plugin-dir ./plugins/gravitas     # load without installing
claude plugin validate ./plugins/gravitas
```

Layout:

```
.claude-plugin/marketplace.json   the catalog
plugins/gravitas/
  .claude-plugin/plugin.json      manifest, and the gateway key prompt
  skills/<name>/SKILL.md          one folder per skill
```

Bump `version` in `plugins/gravitas/.claude-plugin/plugin.json` so installed
copies pick up changes on their next auto-update.
