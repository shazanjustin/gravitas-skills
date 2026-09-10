# Gravitas Skills

Agent skills for Gravitas Digital social-media reporting, competitor
intelligence, paid-media checks and client deliverables.

The skills live in `skills/`, one folder per skill, as plain Markdown plus
Python and Node scripts. Every agent below reads that same directory through its
own thin manifest, so there is only ever one copy of the content.

## Install

One command, every agent you have:

```
git clone https://github.com/shazanjustin/gravitas-skills
node gravitas-skills/scripts/install.mjs
```

It installs into Claude Code, Codex and pi, and skips whichever you do not have.
There is no shared registry between the three, so each needs its own install.

<details>
<summary>Or install per agent by hand</summary>

**Claude Code**

```
/plugin marketplace add shazanjustin/gravitas-skills
/plugin install gravitas@gravitas-skills
```

**Codex**

```
codex plugin marketplace add shazanjustin/gravitas-skills
codex plugin add gravitas@gravitas-skills
```

**pi**

```
pi install https://github.com/shazanjustin/gravitas-skills
```

**Any agent that reads a shared skills directory**

```
npx skills add shazanjustin/gravitas-skills
```

This installs into `~/.agents/skills/` and symlinks into each agent, so it is
one copy rather than one per agent. The trade-off is that you get the skill
files and nothing else: no gateway key prompt, no update check, no `/gravitas:`
namespace. Set `GRAVITAS_GATEWAY_KEY` yourself if you go this route.

</details>

## The gateway key

Ask Shazan or your team lead for it. That one key unlocks Metricool, Apify and
the server-side Meta endpoints from `gateway.shazan.me`, so you never paste an
individual API key.

Three ways to supply it, all of which keep it out of the model's context:

```
node scripts/set-key.mjs
```

Prompts with the input hidden and stores the key encrypted, using Windows DPAPI,
the macOS Keychain, or libsecret on Linux, falling back to a `0600` file. Works
for every agent, and verifies the key against the gateway before storing so a
bad paste fails now rather than somewhere unrelated later.

In Claude Code you can instead use the native prompt, `/plugin configure
gravitas@gravitas-skills`, which stores to the OS keychain the same way. For
cloud sessions and CI, set `GRAVITAS_GATEWAY_KEY` as an environment variable.

Skills resolve it in that order: environment first, then Claude Code's plugin
config, then the credential store.

> **Never paste the key into a chat prompt.** A prompt is an API request to the
> model provider, and it is written verbatim to that agent's history and
> transcript files. Deleting the session afterwards does not undo either. Check
> what is stored with `node scripts/get-key.mjs --check`, which prints presence
> and length but never the key.

## What you get

Under Claude Code and Codex the skills are namespaced by the plugin, so they
appear as `/gravitas:<name>`. Agents also load them on their own when a task
matches the skill's description.

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

## Staying up to date

`main` is the release channel. `plugin.json` declares no `version`, so the
version resolves to the commit SHA and every push is a new version by
definition, with no manual bump to forget.

**Claude Code updates itself.** Turn it on once: `/plugin` -> **Marketplaces**
-> gravitas-skills -> **Enable auto-update**. Third-party marketplaces have it
off by default. Claude Code then checks shortly after each session starts and
loads the new version on your next launch.

**Codex and pi have no auto-update**, so this repo ships its own check. At
session start, at most once every 24 hours per machine, it asks GitHub for
`main`'s commit SHA and compares it to what you have. Every other session start
reads a local stamp file and exits in milliseconds. When you are behind, it
prints a banner naming the commits you are missing and the command to run.

It never applies the update itself: rewriting the plugin cache the agent is
reading at that exact moment is a race worth avoiding, and every agent only
picks up skill changes at session start anyway. To apply:

```
node <install path>/scripts/update.mjs
```

That updates Claude Code, Codex and pi, skipping whichever is not installed.
Run it by hand, or put it in a daily scheduled task for a hands-off setup.
Claude Code is included even though it can update natively, because that only
happens once the auto-update toggle is on.

Wiring, if you need to change it:

| File | Used by |
|------|---------|
| `scripts/update-check.mjs` | the check itself, shared by all three agents |
| `hooks/hooks.json` | Claude Code and Codex, `SessionStart` |
| `extensions/gravitas-update-check.js` | pi, `session_start` |
| `scripts/update.mjs` | applies the update |

Set `GRAVITAS_UPDATE_STAMP` to move the stamp file. Pass `--force` to
`update-check.mjs` to ignore the 24-hour throttle. Every failure path is silent
by design: offline, no git, unwritable home directory, all exit quietly rather
than delay a session.

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

## Release channels

`main` ships. A push reaches every installed copy within 24 hours, since the
plugin declares no `version` and resolves to the commit SHA instead.

If you would rather be promoted to deliberately than track `main`, point at the
`stable` branch, which only moves when someone moves it:

```
/plugin marketplace add https://github.com/shazanjustin/gravitas-skills.git#stable
```

Promote with `git push origin main:stable` once `main` looks good.

## Contributing

`AGENTS.md` has the rules that are not obvious, including the two traps this
repo has already fallen into. Before pushing:

```
node scripts/lint-skills.mjs
claude plugin validate .
```

CI runs both on every push, plus a JSON manifest check, a guard that rejects a
pinned `version`, and a full-history secret scan.

`evals/` holds cases for `claude plugin eval`, which scores whether a skill
actually fires against a no-plugin baseline. Run the matching case whenever you
edit a skill's `description`: that field is the entire trigger mechanism and the
easiest thing here to break by improving the prose.

## Development

```
claude --plugin-dir .        # load without installing
claude plugin validate .
```

Layout:

```
skills/<name>/SKILL.md        the actual content, one folder per skill
scripts/                     install, update, update-check, lint
evals/                       eval cases for claude plugin eval
hooks/hooks.json             SessionStart wiring for Claude Code and Codex
extensions/                  pi extension wiring
.claude-plugin/plugin.json   plugin manifest, and the Claude Code key prompt
.claude-plugin/marketplace.json   the catalog; the plugin source is the repo root
```

Codex reads `.claude-plugin/` too, so both agents work from one manifest set. To
add Cursor, Cline, Gemini or Copilot later, add that tool's manifest at the repo
root pointing at the same `skills/` directory; nothing else moves.

Do not add a `version` to `.claude-plugin/plugin.json`. Setting it pins the
plugin, so pushes stop reaching installed copies until someone remembers to bump
it; leaving it out makes every commit its own version.
