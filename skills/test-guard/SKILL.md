---
name: test-guard
description: Keep a test suite honest and CI cheap. Use when creating tests for a change (`create`), auditing an existing suite for tests that cannot fail, skipped/commented tests and redundant cases (`audit`), or cutting GitHub Actions minutes and wall-time with measured, blast-radius test lanes (`optimize`, optionally `--ultra`). Also use whenever a test fails and the temptation is to skip, comment out, loosen or delete it; when someone asks "is this test useful?", "why is CI so slow/expensive?", "which tests should run for this PR?"; or before adding retries, `.skip`, `|| true` or `continue-on-error` anywhere near tests.
---

# test-guard

Tests exist to catch a broken app. A test that cannot fail, a test nobody runs and a suite that
burns 30 minutes per push all cost money and prove nothing. This skill makes every test earn its
place and every CI minute buy signal.

```
/test-guard create   [scope]            build missing coverage around real behavior
/test-guard audit    [scope]            find tests that prove nothing; fix or remove with evidence
/test-guard optimize [scope] [--ultra]  cheaper/faster CI from measurements, via blast-radius lanes
```

No argument → ask which operation. Any operation accepts `--interview`: present each change group
and wait for approval before editing. Load the reference for the operation before starting:
`references/create.md`, `references/audit.md`, `references/optimize.md` (+ `references/lanes.md`
for lane design and GitHub Actions patterns, `references/ultra.md` for `--ultra`).

## Rules that apply to every operation

### 1. Reason before writing a single test
Answer these in the working notes (and the PR body) for each behavior in scope:

| Question | What a good answer looks like |
|---|---|
| What behavior actually changed? | An observable outcome: input → output, state transition, API contract, UI state. Not "the function was refactored". |
| What can break? | Concrete failure modes: boundary, null/empty, permission, concurrency, money rounding, timezone, tenant isolation. |
| Which existing tests already prove it? | File:test names. If they already fail when the behavior breaks, **write nothing new**. |
| What is the lowest layer that can prove it with confidence? | Unit for pure logic, integration for DB/queue/contract, e2e only for a user journey no lower layer can prove. |
| Do we need one more test at all? | Yes only if a real failure mode is unguarded. Count is not a goal. |

### 2. A test must be able to fail
- Every new or changed test passes `scripts/red-check.sh BASE -- <test command>`: with the source
  change reverted the test must fail **on an assertion about behavior** (not on an import error).
  A test that stays green without the change does not ship.
- Never assert a literal against itself, a mock against the value the mock was told to return,
  or "did not throw" via `assertTrue(true)` / `expect(true).toBe(true)`. Assert the result.
- Snapshot-only tests and bare `toHaveBeenCalled()` are allowed only next to an assertion on the
  outcome they cause.

### 3. When a test fails: investigate, never weaken
1. Read the failure and reproduce it locally with the single failing test.
2. Decide which side is wrong — the code or the test — **and say why, with evidence** (spec,
   issue, commit that changed the contract).
3. Code wrong → fix the code. Test outdated because the contract legitimately changed → update
   the assertion to the new contract and cite where the contract changed.
4. Forbidden without the user's explicit approval in chat: `.skip`/`.only`/`xit`/`markTestSkipped`,
   commenting a test out, deleting it, loosening an assertion (`toEqual` → `toBeDefined`, exact →
   `toContain`), raising timeouts/retries, lowering coverage thresholds, `|| true`,
   `continue-on-error`, `--passWithNoTests`. "Unrelated to my change, will fix later" is not a
   reason — it is a bug report: file it (issue) and tell the user, the test stays as is.
5. Flaky (passes and fails on the same commit): do not retry-loop. Quarantine per
   `references/audit.md` § Flaky — tracked issue + expiry date — only with approval.

### 4. Changes to CI and test config are proposals
`.github/workflows/**`, test runner config, coverage thresholds and `CODEOWNERS` are reviewed by a
human. Write the proposed change as a patch plus the measured before/after, and let the user apply
or approve it. Never route around a protect-files block with Bash.

### 5. Evidence or it did not happen
Every claim in the report carries its proof: command + exit code, `red-check` output, mutation
score, `scripts/ci-usage.py` numbers, `scripts/test-smells.py` findings. No "should be faster".

## Tools in this skill

| Script | Use |
|---|---|
| `scripts/test-smells.py scan [paths]` | Find disabled, commented, tautological, assertion-free tests and loosened gates in a tree |
| `scripts/test-smells.py diff BASE` | Same, only for lines added since BASE; exit 1 on blocking categories — usable as a CI guard |
| `scripts/red-check.sh BASE -- <cmd>` | Prove a test fails without the source change |
| `scripts/ci-usage.py OWNER/REPO [--days N]` | Billed minutes per workflow/job (per-job round-up) + billing API; the baseline for `optimize` |

Run scripts from the target project's root with `python3 -I` / `bash`; they are read-only except
`red-check.sh`, which reverts and restores the working tree and refuses to continue if it cannot.

## Report format (all operations)

```
## test-guard <operation> — <scope>
Baseline:   <numbers: tests, runtime, billed min/month, mutation score, smells> (+ commands)
Changes:    <grouped list: added / rewritten / removed / CI proposals>, each with its evidence
Result:     <same numbers after>, delta
Not done:   <what was skipped and why; anything awaiting approval>
```
