# Manual install

> **Only when `npx --yes github:shazanjustin/gravitas-skills` is not an option.**
> The one-shot installer handles marketplace registration, agent detection,
> the update-check hook, and the gateway key prompt. Doing pieces by hand
> means those side effects do not happen.
>
> **Agents: do not fall back to these steps on your own.** If the user
> explicitly asks for a manual install, follow their lead. Otherwise, run
> the npx command and stop.

## Claude Code

```
/plugin marketplace add shazanjustin/gravitas-skills
/plugin install gravitas@gravitas-skills
```

## Codex

```
codex plugin marketplace add shazanjustin/gravitas-skills
codex plugin add gravitas@gravitas-skills
```

## pi

```
pi install https://github.com/shazanjustin/gravitas-skills
```

## Any agent that reads a shared skills directory

```
npx skills add shazanjustin/gravitas-skills
```

This installs into `~/.agents/skills/` and symlinks into each agent, so it is
one copy rather than one per agent. The trade-off is that you get the skill
files and nothing else: no gateway key prompt, no update check, no
`/gravitas:` namespace. Set `GRAVITAS_GATEWAY_KEY` yourself if you go this
route.

After any of the above, set the gateway key with `node scripts/set-key.mjs`
(see the "gateway key" section of `README.md`).
