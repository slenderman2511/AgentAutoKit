---
title: Security
summary: Who can do what, where the trust boundaries are, and how secrets and personal data are handled.
status: draft
owner: <@login>
updated: <YYYY-MM-DD>
---

## 01 · Threat Model
_What we protect, from whom, and what would hurt most._

| Asset | Threat | Impact | Main control |
|---|---|---|---|
| <user data> | <another tenant reads it> | <high> | <scope check in service layer> |
| <payments> | <forged webhook> | <high> | <signature verification> |
| <admin panel> | <account takeover> | <…> | <2FA, rate limit> |

## 02 · Authentication
_How users prove who they are._

- **Method:** <email+password · magic link · OAuth · SSO>
- **OAuth / SSO providers:** <list, or "none">
- **Sessions:** <cookie / bearer token>, lifetime <n>, refresh <rule>, revoked on <events>
- **Rate limits:** login <n>/min per IP and per account

## 03 · Authorization & Roles
_Every role and what it may do. Checked on the server, never only in the UI._

| Role | Can | Cannot |
|---|---|---|
| <Owner> | <…> | — |
| <Member> | <…> | <…> |
| <Viewer> | read only | any write |

## 04 · Trust Boundaries
_Every place outside input enters, and how it is validated._

| Entry point | Validation | Notes |
|---|---|---|
| Public API `<path>` | <schema / zod / FormRequest> | <auth required?> |
| Webhook `<provider>` | signature + idempotency key | <…> |
| File upload | type + size allow-list, stored outside web root | <…> |

## 05 · Secrets Management
_Where secrets live and who can read them._

- Stored in <vault / platform env vars>; never in the repo, logs, or client bundles
- Rotation: <cadence>, on staff change, and immediately on leak
- Local dev: `<.env.example>` lists names only

## 06 · Data Protection
_Personal data: what we keep, how long, and who sees it._

- Encryption: TLS in transit; <at-rest setting>
- Logs and analytics never contain <PII fields / tokens>
- Retention and deletion: <policy, user deletion request flow>

## 07 · Dependencies & Supply Chain
_Third-party code we trust and how we keep it current._

- Lockfile committed; updates via <Dependabot / Renovate>; vulnerability scan <tool> in CI
- CI actions pinned to a commit SHA

## 08 · Incident Response & Checklist
_What to do when something goes wrong, and the pre-release checklist._

- Report to: <channel / person>; rotate affected secrets first, then investigate
- [ ] Every new route checks auth **and** scope
- [ ] Every webhook verifies its signature
- [ ] No secret or PII in logs, errors, or client code
- [ ] Security-sensitive diff reviewed by <reviewer / agent>
