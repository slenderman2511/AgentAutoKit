# create — coverage around real behavior

Goal: the smallest set of tests that fails when the behavior in scope breaks. Not a coverage number.

## 1. Scout (read-only)
- Scope = the argument, else the current diff (`git diff --stat <integration-branch>...HEAD`).
- Read the changed code, its callers (one hop), the spec/issue/PR that motivated it, and the
  existing tests for those files. Delegate the sweep to a read-only scout agent when it spans many files.
- Find the project's test commands and layers: `package.json` scripts, `vitest`/`jest`/`playwright`
  config, `phpunit.xml` testsuites, `pytest.ini`, CI workflows. Note how long each layer takes.

## 2. Coverage matrix — write it before any test

| Behavior (observable) | Failure modes | Already proven by | Lowest trustworthy layer | Action |
|---|---|---|---|---|
| Refund rounds to 2 dp in VND=0 dp | VND gets decimals; negative refund | `refund.test.ts › rounds usd` (USD only) | unit | add 1 case (VND), 1 case (negative) |
| Admin of tenant A cannot read tenant B | missing tenant filter | none | integration (DB + rules) | add 1 test |
| Checkout happy path | — | `checkout.spec.ts` e2e | — | nothing |

Rules for the matrix:
- One row per behavior, not per function. Private helpers are covered through the behavior that uses them.
- "Already proven by" must name a test that would FAIL if that behavior broke. If unsure, run
  `red-check.sh` against it or mutate the line by hand and run it.
- Pick the layer from the bottom: pure logic → unit; anything crossing a DB, queue, HTTP contract,
  security rule or framework wiring → integration (real DB/emulator, not mocks of it); e2e only for a
  user journey whose value is the wiring of many parts and which no lower layer proves.
- Empty "Action" is the best outcome. Say so in the report.

## 3. Write the tests
- Arrange–act–assert on the outcome: returned value, persisted row, emitted event, rendered state,
  HTTP status + body. Assert exact values; a broad matcher needs a reason.
- Mock only what you do not own or cannot run (third-party HTTP, clock, randomness). Never mock the
  unit under test or the thing whose behavior the test claims to prove.
- Name tests as the behavior: `refunds in VND are whole numbers`, not `test refund 2`.
- Fixtures/factories over hand-built objects copied across files.
- Keep e2e count flat: if an e2e test is needed, prefer extending an existing journey with one
  assertion over a new spec file (each e2e file costs browser + seed + login).

## 4. Prove each test can fail
```
bash scripts/red-check.sh <integration-branch> -- <single-test command>
```
- Exit 0 + failure on an assertion → keep.
- Exit 1 (still green) → the test does not prove the change: strengthen the assertion or delete it.
- For a test of pre-existing behavior (no source diff to revert), mutate the guarded line by hand
  (flip a comparison, drop a filter), run the test, confirm red, restore. Record what you mutated.
- Optional, stronger: mutation testing on the changed files only (Stryker `--mutate <files>
  --incremental` for JS/TS, Infection `--filter=<files>` for PHP, mutmut `--paths-to-mutate` for
  Python). Report the score for the changed files.

## 5. Report
The coverage matrix (with the Action column filled), tests added per layer, `red-check` result per
test, runtime added to the suite (seconds) and which CI lane will run them (`references/lanes.md`).
