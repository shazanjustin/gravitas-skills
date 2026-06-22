---
date: 2026-06-22
status: active
source: D:/vibe coding stuff/gravitas-beacon/docs/brainstorms/2026-06-22-gravitas-gateway-skill-requirements.md
---

# feat: Add gravitas-gateway skill to gravitas-skills monorepo

## Summary

Add a `gravitas-gateway` SKILL.md to the gravitas-skills repo that teaches agents how to fetch API keys from `gateway.shazan.me`. Add `.env.example` at the repo root. Update the `metricool` skill to reference the gateway as its credential source.

---

## Implementation Units

### U1. Create .env.example and verify .gitignore

- **Goal:** Provide the setup template and ensure `.env` is ignored
- **Files:** `.env.example` (create), `.gitignore` (verify)
- **Approach:** Add `.env.example` with `GRAVITAS_GATEWAY_KEY` and `GRAVITAS_GATEWAY_URL`. Verify `.env` is already in `.gitignore`.
- **Verification:** `.env.example` exists, `.env` is gitignored

### U2. Create gravitas-gateway/SKILL.md

- **Goal:** The gateway skill that all other Gravitas skills reference
- **Files:** `gravitas-gateway/SKILL.md` (create)
- **Approach:** Document gateway URL, auth format, all endpoints, setup flow, auto-update instructions, and the secret-to-skill mapping
- **Verification:** SKILL.md is well-formed with YAML frontmatter

### U3. Update metricool SKILL.md to reference gateway

- **Goal:** metricool skill uses gateway instead of managing its own `.env`
- **Files:** `metricool/SKILL.md` (modify)
- **Approach:** Add dependency note at top: "Load gravitas-gateway first to obtain your Metricool token." Update auth section to reference `GRAVITAS_GATEWAY_KEY` from the gateway.
- **Verification:** metricool SKILL.md references gateway skill

### U4. Push to GitHub

- **Goal:** Deploy the skill to all team members
- **Files:** N/A
- **Approach:** Commit all changes, push to main
