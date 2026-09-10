# AGENTS.md

Instructions for any agent working **on** this repository. If you are looking
for what the skills do, read `README.md`.

## What this repo is

A multi-agent skill package for Gravitas Digital. `skills/` at the repo root
holds the only copy of the content; everything else is a thin manifest pointing
at it, one per agent. Claude Code, Codex and pi all install from this repo.

```
skills/<name>/SKILL.md            the content, one folder per skill
scripts/                          install, update, update-check, lint
hooks/hooks.json                  SessionStart wiring for Claude Code + Codex
extensions/                       pi extension wiring
evals/                            eval cases for the skills
.claude-plugin/                   Claude Code manifest + marketplace (Codex reads these too)
.codex-plugin/plugin.json         Codex-native manifest
.agents/plugins/marketplace.json  cross-agent marketplace path
```

## Before you push

```bash
node scripts/lint-skills.mjs      # names must match folders, descriptions must be short
claude plugin validate .          # manifests must parse
```

CI runs both plus a secret scan. The one validation warning you should expect
and keep is `No version specified` (see below).

## Rules that are not obvious

**Never add a `version` to `.claude-plugin/plugin.json`.** Setting it pins the
plugin, so pushes stop reaching installed copies until someone bumps the string.
Without it the version resolves to the commit SHA and every push ships. This
repo already lost two layout changes to that trap.

**The folder name is the skill name.** `skills/foo/SKILL.md` must declare
`name: foo`. A mismatch is a silent routing bug, not an error anyone sees. Two
shipped before the linter existed.

**Descriptions are always-on cost.** Every skill's description sits in context
on every turn whether the skill fires or not, so keep them under 60 words and
put procedure in the body. Trigger phrases earn their place; restating the body
does not. `claude plugin details gravitas@gravitas-skills` shows the running
total.

**Commit subjects are user-facing.** The update banner prints them to whoever is
behind, so write the subject line as a release note, not as git archaeology.

**`main` is the release channel.** A push reaches every installed copy within
24 hours. If you need to work without shipping, branch. `stable` exists for
teams that want to be promoted to deliberately rather than tracking `main`.

**Credentials never live in this repo, and never in a chat prompt.**
`GRAVITAS_GATEWAY_KEY` comes from the environment, Claude Code's plugin config,
or the OS credential store via `scripts/set-key.mjs`. Everything else is fetched
from `gateway.shazan.me` at runtime.

Never ask a user to paste a secret into the chat, and never print one. A prompt
is an API request to the model provider and is written verbatim to that agent's
history and transcript files, so deleting the session afterwards undoes neither.
`scripts/get-key.mjs --check` reports presence and length; the plain form writes
the key to stdout for shell substitution and must never be read into context.

**Do not edit an installed copy.** Agents keep their own managed copies
(`~/.claude/plugins/cache/`, `~/.codex/plugins/cache/`,
`~/.pi/agent/git/github.com/...`) and reset them on update. Edit here, push,
then `node scripts/update.mjs`.

## Agent-specific quirks worth knowing

- **`claude plugin details` shows the marketplace catalog, not what is
  installed.** Read `~/.claude/plugins/installed_plugins.json` for the truth.
- **Claude Code auto-update is off by default** for third-party marketplaces,
  and it is a TUI-only toggle: `/plugin` > Marketplaces > Enable auto-update.
- **Codex resolves a git-marketplace version to the literal string `local`**, so
  `codex plugin marketplace upgrade` alone never reinstalls. `scripts/update.mjs`
  does remove-then-add for Codex because of this.
- **Codex has no `userConfig`**, so `${user_config.*}` is never substituted
  there. Treat any value still containing `user_config` as empty.
- **pi auto-discovers `skills/` and `extensions/`** from a package root. That is
  why the layout is what it is.
