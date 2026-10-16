---
name: grill-me
description: Use BEFORE planning a feature bigger than a day, or whenever a spec/plan still has open decisions — interview the user in ROUNDS, each round asking every decision whose prerequisites are already answered, each question carrying Claude's recommended answer so the user can reply "Q1 yes, Q2 no, Q3 rolling 7 days". Facts are looked up by subagents, never asked; only real decisions reach the user. Done when nothing is silently assumed. Triggers: "grill me", "hỏi kỹ trước khi plan", "chốt quyết định", "interview me before we plan", an M/L task with open ⏳ decisions.
---

# grill-me — decisions in rounds, each with a recommendation

**Core idea:** the questions you cannot answer before building are the ones that bite mid-build.
Surface ALL of them up front, but make answering cheap: batch them, recommend an answer for each,
and never ask the user something a subagent can look up.

Not a replacement for `brainstorming` (shaping a fuzzy idea) — grill-me starts once the idea is
named and turns it into locked decisions. Output language follows the project `CLAUDE.md`.

## Step 1 — Map the decision tree (silently)

From the request + the source-of-truth doc named in `CLAUDE.md` + the code, list every decision the
build depends on: data shape, scope edges, defaults, error/empty behavior, permissions, rollout,
migration of existing data, cost. Mark each one's prerequisites (Q5 only makes sense after Q2).

**Split facts from decisions.** "Where is X configured?", "how many docs does Y have?", "what does
the current flow do on Z?" are FACTS → send `code-scout` (batched in ONE message) and use the answer.
Only choices a human owns (product, UX, money, risk, rollout) stay on the list.

## Step 2 — Ask the frontier, one round at a time

The frontier = every open decision whose prerequisites are answered. Ask all of it in ONE message,
plain markdown (not `AskUserQuestion` — its 4-question cap is the problem this skill solves):

```
Round 1 — 4 decisions

Q1 · Denominator: every document on the site, or only the ones found?
  ➡️ Recommend: only the ones found; report misses as their own number — no inflated % on a short crawl.
Q2 · Per run, or a rolling average?
  ➡️ Recommend: rolling 7 days — one bad run doesn't swing the report.
…
Reply tersely: "Q1 ok, Q2 = per run, Q3 ok".
```

- Each question: one line, the options when they are discrete, then `➡️` + recommendation + a
  one-clause reason. A recommendation you would not defend is a fact you haven't looked up yet.
- Order by blast radius: data/money/permission decisions first, copy/cosmetics last.
- An answer that opens new branches → they join the NEXT round's frontier. Never re-ask an answered one.
- Only an explicit answer locks a decision ("ok" = the recommendation). A question the user skipped
  stays open and is asked again at the top of the next round — never assume it silently.

## Step 3 — Done check

Stop when no open decision remains and nothing in the plan rests on an assumption the user never
saw. Post a recap table — `#` · decision · chosen value · (recommended / overridden) — then write
the locked values into the planning doc: the spec/plan's decisions section (for a 9-step template,
§6 "decisions to lock" — replace each ⏳ with the chosen value). Then continue the normal flow
(plan → build), not before.

## Common mistakes

| Mistake | Fix |
|---|---|
| Asking the user a fact ("which file handles X?") | `code-scout` it, state the fact, move on |
| One question per message | The whole frontier per round |
| Question without a recommendation | Always `➡️` + reason — the user should mostly reply "ok" |
| Asking Q5 before its prerequisite Q2 is answered | Frontier = prerequisites answered only |
| Decisions live only in the chat | Write them into the plan/spec doc before building |
