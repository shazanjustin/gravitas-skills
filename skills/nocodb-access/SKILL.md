---
name: nocodb-access
description: |
  Give a Gravitas teammate access to the NocoDB "Central" base (the one behind
  the Performance task list) and see who already has it. Use for "add
  <someone> to NocoDB", "give <someone> access to the Performance table",
  "is <someone> in NocoDB", "who has access to Central". Adds one person at a
  time as an editor and returns a signup link to send them. Cannot remove
  anyone, cannot grant owner or creator, cannot touch any other base.
compatibility: |
  Requires node (>=18, for global fetch). Uses GRAVITAS_GATEWAY_URL +
  GRAVITAS_GATEWAY_ADMIN_KEY from ~/.gravitas-skills/.env. No NocoDB token is
  needed or handled here — the gateway holds it server-side and never returns it.
---

# NocoDB Access

Adds a person to the NocoDB **Central** base — the one holding the Performance
task list that [performance-tracker](../performance-tracker/SKILL.md) reads —
through the Gravitas gateway (`gateway.shazan.me`).

## What this can and cannot do

The NocoDB credential behind the gateway is an unrestricted super-admin token
over all 11 bases. This skill exists so that adding a teammate never requires
handing that token to anyone. The gateway route exposes exactly one capability:

| | |
|---|---|
| **Base** | Central (`pboui1exiw4lryy`) only — hardcoded, not a parameter |
| **Role** | `editor` only — `owner` and `creator` are refused |
| **Email** | `@gravitas.my` addresses only |
| **Verbs** | list and add. **No remove, no downgrade, no role change** |

These are enforced at the gateway, not here. Asking this skill nicely to add
someone as an owner, or to a client base, does not work — there is no request
that expresses it. Removing someone's access is a deliberate gap: do it by hand
in NocoDB, signed in as an admin.

## See who has access

```bash
node scripts/member.mjs list
node scripts/member.mjs list --json
```

Prints everyone with a real role on Central, marking who still has an unaccepted
invite. **This is not the same as "everyone NocoDB knows about."** Every org user
is listed against every base whether or not they can open it; the route already
filters to real members, so what you see here is the true access list.

## Add someone

```bash
node scripts/member.mjs add danya.loo@gravitas.my            # dry-run
node scripts/member.mjs add danya.loo@gravitas.my --apply    # actually invites
```

Dry-run by default: it checks the address, checks whether they are already a
member, and prints exactly what it would do. `--apply` performs the invite and
prints a **signup link**.

**The signup link is the deliverable, not a formality.** The invite email on this
instance does not arrive, so the person cannot get in until someone sends them
that URL. Treat it as a credential — anyone holding it can claim the account, so
send it to them directly, never into a shared channel or a ticket.

Adding somebody who is already a member is refused rather than repeated. That is
not tidiness: a second invite mints a new token and silently kills a link the
person may already be holding.

## After adding

The new member can read and edit rows in Central, which includes everything
`performance-tracker` touches. They will show as a pending invite until they
follow the link and set a password.

If the link is lost, there is no "resend" here — ask an admin to re-issue it in
NocoDB, or remove and re-add the person by hand. Running `add` again on an
existing member is refused by design.

## Notes

- **One person per call.** No bulk invite; adding three people is three calls.
- **The admin key is a third key**, separate from the read and write keys the
  other gateway skills use. `GRAVITAS_GATEWAY_KEY` and
  `GRAVITAS_GATEWAY_WRITE_KEY` both return 401 on this route. That split is
  deliberate: granting base membership is an authorization change, not a data
  edit, and should not come free with the ability to edit a task row.
- **Never paste gateway keys, NocoDB tokens or signup links into chat.**
- Access to Central is not access to client bases (Aeson Power, Suria KLCC,
  Prudential, CIMB…) or to `[PRIVATE] Internal`. Those stay manual.

## Two NocoDB behaviours that look like failures

Both are handled by the gateway; they are recorded here because they will
mislead anyone who bypasses it and calls NocoDB directly.

- **The invite request times out with a 504 and succeeds anyway.** NocoDB blocks
  on its mail step longer than Cloudflare will wait, so the write lands while
  the caller sees a gateway error. Never retry on a timeout — re-read the member
  list and check. The route already decides from the read-back rather than the
  status, which is why `add --apply` can report success after a slow call.
- **A freshly created user can come back with a null invite token**, which is
  indistinguishable from an *accepted* invite. The route forces a fresh token
  before returning, so `add` either hands you a link or says plainly that it
  could not mint one.

## Raw HTTP contract

Only needed if `member.mjs` is unavailable.

```bash
source ~/.gravitas-skills/.env

# Who has access
curl -s -H "x-api-key: $GRAVITAS_GATEWAY_ADMIN_KEY" \
  "$GRAVITAS_GATEWAY_URL/nocodb/base-user"

# Add one person (roles defaults to editor and is the only accepted value)
curl --fail-with-body -sS -X POST \
  -H "x-api-key: $GRAVITAS_GATEWAY_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$GRAVITAS_GATEWAY_URL/nocodb/base-user" \
  -d '{"email":"someone@gravitas.my"}'
```

Responses: `200` with `{ok, user, inviteUrl, note}`; `409 already_member`;
`400 invalid_email` or `400 role_not_allowed`; `502 invite_failed` when the
person genuinely was not added.
