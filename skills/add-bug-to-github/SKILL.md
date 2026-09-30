---
name: add-bug-to-github
description: File a bug the user already knows about as ONE GitHub issue in the project's AI work queue — labeled with the queue label (default `ai`) + `bug` + `bug:<kind>` (data/ui/logic/integration/perf) + `severity:<level>` + optional scope labels, all as named in CLAUDE.md "## Issue tracking" — after checking the feature's intended behavior against the project's source of truth, pinning down title, symptom, where, repro and severity with the user, and de-duplicating against existing issues. Use when the user asks to "add a bug", "log a bug", "file a bug", "báo bug", "ghi nhận bug", "tạo issue bug", or reports broken behavior they want TRACKED but not fixed right now. Not for driving a fix (fix-from-github drains the queue; github-issue-flow owns issue → PR → close), and not for finding bugs by reviewing code (/code-review).
---

# File a bug into the AI work queue

This is a **producer** for the AI work queue: it files ONE well-formed issue and stops — no
branch, no code. The queue label (`<ai>`, default `ai`) marks it as work an agent can claim
later; `fix-from-github` is the consumer that claims, plan-gates and fixes it, and
`github-issue-flow` closes it after a human merges the fix. Filing and fixing are deliberately
separate so a bug reported at 11pm doesn't force an 11pm fix.

Project facts (repo, label names, attribution footer) come from `CLAUDE.md` `## Issue tracking` —
see `github-issue-flow` "Project facts" for the defaults and the `<repo>` / `<ai>` placeholders.
Same taxonomy as `github-issue-flow` (`bug` + scope labels), plus the queue dimension: `<ai>` +
`bug:<kind>` + `severity:<level>`.

## 1. Understand the feature FIRST — source-of-truth check

Before treating the report as a bug, load what the project *intends* to happen:

1. **Find the reference.** If CLAUDE.md `## Source of truth` names a feature reference doc, map
   the symptom to its section and read it (data models, flows, rules, key file paths). Without
   one, use the matching spec in `docs/superpowers/specs/`, then the code and its tests.
2. **Check known discrepancies** — if the reference doc has a known-discrepancies / known-issues
   section, the reported behavior may be a documented divergence, not a new bug. If so, tell the
   user and link it instead of filing.
3. **Verdict:** does the observed behavior actually violate a documented rule/flow?
   - **Violates the reference** → real bug. Quote the violated rule in the issue body
     ("<doc> §<section>: <rule> — observed: <behavior>"), and copy the section's key file paths
     into **Where** so the fix agent starts in the right place.
   - **Matches the reference** → it is intended behavior; what the user wants is a *change* →
     route to `github-issue-flow` as a `feature`, not a bug.
   - **Reference is silent or wrong** (running code is canonical) → still file the bug, and add
     a checklist item "update <reference> in the same PR".
   - **No reference exists** → the expected behavior is the user's; record it as such.

This step is what makes the ticket trustworthy: expected-vs-observed grounded in the documented
rule, not in a guess.

## 2. Classify the bug kind

Exactly one primary `bug:<kind>` label — it decides what evidence the ticket needs and how the
fix agent will approach it:

| Kind | Label | It is… | Evidence to capture in the issue |
|---|---|---|---|
| Data | `bug:data` | Wrong/missing/corrupt stored data, or code writing bad data (wrong foreign key, dangling reference, stale status) | The record path(s)/ids + offending field values — read **read-only**, through the project's sanctioned data access, and only after the user OKs touching live data — as a PII-stripped snippet. Note if a data-repair script will be needed alongside the code fix. |
| UI | `bug:ui` | Display/interaction wrong while data & API are correct (invisible text, dropped taps, layout, i18n) | Screenshot/recording, viewport + browser (mobile? iOS Safari?), the route. Cite which project UI/theming/a11y rule it violates, if any. |
| Logic | `bug:logic` | A business rule computed wrongly (pricing, ranking, permissions, status transitions) | Concrete input → wrong output → expected output per the reference rule. The smallest failing case. |
| Integration | `bug:integration` | A server-to-server / third-party flow broken (payment webhooks, external API sync, email delivery) | Provider/transaction ids, webhook/event id, sync-state fields, timestamps, the relevant log line. |
| Perf | `bug:perf` | Correct but unacceptably slow / hanging (page load, query fan-out) | Where it's slow, how slow, on what data size/network. |

Mixed cases: pick the **root** kind (a UI symptom caused by bad data is `bug:data`) — the symptom
layer goes in the body, not the label.

## 3. Draw the bug out — and confirm before filing

Work with the user until each of these is concrete. If something is missing, **ask — do not
guess and file**. "X is broken" alone is not an actionable ticket:

- **Title** — one line, the defect itself, not the area ("checkout drops the coupon on retry",
  not "checkout bug").
- **Symptom** — expected vs observed behavior.
- **Where** — page/route/file if known; the fix agent should start at the right place. If the
  user can name the feature, map it to its reference section (step 1).
- **Repro / scenario** — steps, inputs, or the state that exposes it, with the relevant record ids.
- **Severity** — agree it explicitly (rubric below); it orders the queue.
- **Scope** — only if `## Issue tracking` defines scope labels: which one(s) apply (umbrella +
  namespaced pair when the project uses them). Project-wide → no scope labels.

**Read the confirmed set back to the user and get an explicit yes before filing.** An
unconfirmed or unreproducible report is queue noise. One ticket per bug — several bugs in one
conversation become several confirmed tickets.

**Severity rubric:**
- `severity:critical` — data loss, a data-isolation/security breach (cross-tenant or cross-user
  leak), a payment/money path broken, or a whole feature down with no workaround.
- `severity:high` — a user-facing flow broken or producing wrong results on a normal path.
- `severity:medium` — real defect with a workaround or bounded blast radius.
- `severity:low` — cosmetic, latent (correct today but fragile), or a narrow edge case.

## 4. De-duplicate

Search before filing — the queue may already have it (from a human or a review):

```bash
gh issue list --repo <repo> --state all --search "<keywords> in:title,body" --limit 20 \
  --json number,title,state,closedAt
```

Try 2–3 keyword combinations, not just the exact title; check open AND recently closed. If a
match exists, surface `#N <state> <title>` to the user and stop — optionally add the new repro
details as a comment (`gh issue comment <N> --repo <repo>`) instead of a new issue.

## 5. File it

**Title:** `bug: <concise defect>` — same convention as `github-issue-flow`.

**Labels:** `<ai>,bug,bug:<kind>,severity:<sev>[,<scope>…]` — e.g. `ai,bug,bug:data,severity:high`.
⚠️ `gh issue create` fails the whole call if any label doesn't exist — run the idempotent label
bootstrap in `github-issue-flow` Step 0 first. If you can't create labels (no write/triage
permission), file with the labels that exist and list the missing ones in the body — never block
filing on label plumbing.

**Body** — reuse the `github-issue-flow` Step 1 template (Context / Type & scope / Problem /
Task sizing / Plan checklist / Acceptance criteria) with Type `bug`, so the consumer can resume
it without reshaping. End with the attribution footer if `## Issue tracking` defines one, then
the machine-readable footer on the very last line:

```
<!-- queue:<ai> kind:<data|ui|logic|integration|perf> severity:<sev> scope:<label|none> ref:<section|spec|n/a> source:add-bug-to-github -->
```

```bash
gh issue create --repo <repo> --title "bug: <defect>" \
  --label <ai>,bug,bug:<kind>,severity:<sev> --body-file - <<'EOF'
<body>
EOF
```

## 6. Report

Give the user the issue URL and state that it now sits in the `<ai>` queue: `fix-from-github` (or
a future session) will claim it, plan-gate, implement, and open a draft PR to the integration
branch; after a human merges, `github-issue-flow` Step 4 closes it (a PR basing a non-default
integration branch never auto-closes its issue).

## Notes

- **This skill never starts the fix.** If the user says "báo bug này và sửa luôn" / "file it and
  fix it", file the issue here, then hand off in the same session to `fix-from-github #N` (claim +
  plan gate) or `github-issue-flow` Step 2.
- Severity is the queue's ordering key; scope labels are its routing key (where the eventual fix
  must be verified and deployed). Both matter — don't skip them.
- Issues are visible to everyone with repo access — strip PII, secrets and tokens from pasted
  data, logs and screenshots.
- Only file bugs the user stands behind. Vague reports go back to step 1, not into the queue.
