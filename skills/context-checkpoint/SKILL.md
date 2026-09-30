---
name: context-checkpoint
description: Keep a long Claude Code session healthy — persist durable state, prompt a compaction at a safe idle point, and run the save-memory → update-SOT → clear → resume ritual when a session ends or the work switches to a new feature/task. Use when context is getting heavy (~half full) and you've just reached a natural stopping point, when the user says "compact", "clear context", "save memory and clear", "switch to a new task/feature", "end the session", or when you're about to pivot from one feature/task to an unrelated one. Reach for it proactively at the end of any substantial chunk of work before starting the next. HARD LIMIT (read the body) — an agent CANNOT run `/compact` or `/clear` itself — this skill does the automatable half (persist state, update plan/SOT/rules, commit) and hands the two keystrokes to the user at exactly the right moment. Not for mid-task use — never checkpoint while a task is in flight. Not a planning skill — plans are written by superpowers `writing-plans`; this skill only brings them up to date.
---

# Context checkpoint: persist → compact/clear → resume

Long sessions rot: context fills, older tool output gets summarized, and if you `/clear`
without saving, in-flight state is gone (conversation history does NOT survive `/clear` —
only files on disk do). This skill keeps a session healthy by making the **durable state**
explicit before any reset, and by nudging the two context commands at the right time.

## The one hard limit — do not pretend otherwise

**An agent cannot self-trigger `/compact` or `/clear`.** They are interactive commands the
**user** types; there is no tool, no text you can emit, no hook that initiates them (a
`PreCompact`/`Stop` hook can only *block*, never *start*). Claude Code's built-in auto-compact
fires on its own near the context limit, on the harness's schedule, not yours. So this skill
never *runs* a compaction — it **persists state and tells the user the exact command to run**.
Claiming "I compacted/cleared the context" would be a lie; say "state saved — run `/compact`"
(or `/clear`) instead.

## Rule 0 — never checkpoint mid-task

Only act at a **natural stopping point**: a task or subtask just finished, `tsc`/tests are
green, and you're waiting on the user or between independent steps. **Never** interrupt work in
flight to compact/clear — you'd strand half-done state and block progress. If a task is
running, finish it (or reach a clean, committed boundary) first. This is a hard constraint, not
a preference.

## Trigger A — mid-session compaction nudge (~half full, idle only)

When context is getting heavy (roughly half) **and** Rule 0 is satisfied:

1. Write a one-paragraph **resume note** into the active plan file under
   `docs/superpowers/plans/` (what's done, what's next, key facts discovered — file paths, root
   causes, decisions) — so a compact or clear can't lose the thread. If no plan file exists and
   the work is non-trivial (M/L tier in `.claude/rules/workflow.md`), create a short one; for
   S-tier work, a chat summary is enough.
2. Tell the user plainly: *"Context ~50% and we're at a clean point — good moment to `/compact`.
   Run it and I'll keep going."* Then **keep working** if they don't — this is a suggestion, not
   a stop. (Auto-compact will also kick in on its own near the limit.)

`/compact` keeps the conversation (summarized); prefer it mid-feature. `/clear` wipes it; save
that for a real boundary — Trigger B.

## Trigger B — session end / feature or task switch (the important one)

Before ending the session or pivoting to an unrelated feature/task, run these **in order** —
this is what makes a `/clear` safe:

1. **Save memory (durable state).** Update or create the plan file in
   `docs/superpowers/plans/` — tick only steps that are verified (plans are the kit's durable
   state machine), and write the next step first so a fresh session resumes from the first
   unticked box. Fold any lasting convention you discovered into the root `CLAUDE.md` (project
   facts) or a project-owned `.claude/rules/<topic>.md` — never into the kit-managed
   `workflow.md`/`general.md`, which are re-synced on upgrade. Those files reload every session;
   conversation history does not. Machine-local scratch notes go in `CLAUDE.local.md` (keep it
   gitignored).
2. **Update the SOT if a feature changed.** If `CLAUDE.md` has a "## Source of truth" section
   naming a feature reference doc, and the finished work altered a data model, flow, status,
   permission, or business rule, update the matching section of that doc in the same breath.
   No such section/doc, or no feature change → skip. In an epic (`.claude/rules/epic-flow.md`)
   the same applies per lane: data changed → update the data-contract `.md`; a UX decision
   changed → update the prototype and its issue (`ui-prototype`). (Skipping the SOT is the most
   common way the next session starts from a wrong mental model.)
3. **Commit the durable artifacts** (plan / SOT / CLAUDE.md / rules) so nothing lives only in
   this context. Follow `.claude/rules/general.md` — commit on the task's feature branch (inside
   its worktree), never directly on the integration branch or `main`.
4. **Hand off.** Tell the user: *"State saved (plan + SOT committed). Safe to `/clear` now.
   After clearing, resume with: `<one-line resume prompt>`."* Give the **exact** next prompt so
   the new session starts productively — e.g. "Continue `docs/superpowers/plans/<date>-<slug>.md`
   from the first unticked step, in worktree `.claude/worktrees/<branch-slug>`." Name the
   worktree: a fresh session starts in the shared checkout.
5. **After the user clears and sends the resume prompt, continue.** The fresh context
   auto-loads `CLAUDE.md` and `.claude/rules/*`; you re-read the plan file (and the SOT section
   for the area you're touching), work inside the named worktree, and pick up at the first
   unticked step. Nothing important was in the discarded history — you put it on disk.

## What good looks like

- Nothing you needed survived only in chat — it's in a plan file, the SOT, or CLAUDE.md/rules.
- The user ran `/clear` (or `/compact`) knowing exactly what was saved and how to resume.
- You never claimed to have compacted/cleared; you saved state and named the command.
- You never did any of this while a task was still running.

## Quick reference

| Moment | Do | Then tell the user |
|---|---|---|
| ~50% context, idle | resume-note → plan file | "good point to `/compact`" |
| End of a feature/task | plan + SOT (if any) + CLAUDE.md/rules → commit | "safe to `/clear`, resume with: …" |
| Mid-task (any %) | **nothing** — finish first | — |
