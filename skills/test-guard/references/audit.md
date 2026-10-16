# audit — find tests that prove nothing

Goal: every remaining test can fail for a real reason, runs somewhere, and is not a duplicate.
Every finding carries evidence; every fix keeps or improves what the suite proves.

## 1. Inventory (read-only)
```
python3 -I scripts/test-smells.py scan <scope>          # add --weak for the noisy weak-assertion pass
```
Also collect: test count per layer, runtime per file (JUnit/`--reporter=json`/`--log-junit`),
which CI job runs each layer, coverage report if one exists, last-modified date per test file.

## 2. Classify each finding

| Class | Signal | Typical fix |
|---|---|---|
| Tautological | `expect(true).toBe(true)`, `assertTrue(true)`, literal vs literal, value vs itself | Assert the real outcome. For "does not throw": call it and assert the result/side effect; PHPUnit `expectNotToPerformAssertions()` only when "no exception" truly is the contract |
| Mock-echo | asserts the value a mock was told to return | Assert what the code under test does with it |
| Assertion-free | test cases, no `expect`/`assert` | Add the assertion the name promises, or delete |
| Disabled | `.skip`, `xit`, `markTestSkipped`, `@group skip` | Fix and re-enable, or delete with reason. Never leave skipped without an issue link + date |
| Env-gated | `test.skip(!process.env.X)` | Make sure SOME CI lane provides X; otherwise it never runs — treat as disabled |
| Commented-out | `// it(...)`, `// public function test_...` | Restore + fix, or delete. Commented code is not a backlog |
| Redundant | two tests fail for exactly the same mutations; e2e re-proving unit logic | Keep the cheapest one that still fails |
| Outdated | asserts behavior the spec no longer has; tests deleted code paths | Update to the current contract (cite it) or delete |
| Loosened gate | `|| true`, `--passWithNoTests`, retries > 0, `continue-on-error` on a test step | Remove; failures must fail the job |
| Flaky | different result on the same commit | Find the cause (time, order, shared state, network, animation). Quarantine only per § Flaky |
| Unsafe | hits prod services, real payment/email, shared mutable tenant | Point at emulator/sandbox, isolate data |

## 3. Proving a test is worthless (before deleting)
Deleting is allowed when ALL hold, and the evidence goes in the report:
1. It cannot fail for a behavior reason (tautological / mock-echo / assertion-free), **or** another
   test fails for every mutation this one catches (redundant), **or** the behavior no longer exists.
2. Removing it does not lower the mutation score of the files it covers (run the mutation tool on
   those files with and without it), or — without a mutation tool — hand-mutate the covered lines
   and show another test still goes red.
3. More than 10 deletions in one run, or any deletion in a security/payment/tenant-isolation path →
   `--interview` is mandatory: list them and wait for approval.

## 4. Flaky
- Reproduce: run the single test 20× (`--repeat-each=20`, `vitest --sequence.shuffle`,
  `phpunit --repeat`) and in random order; record the failure rate.
- Fix the cause when it is in reach (await the right condition instead of sleeping, freeze the
  clock, isolate data, stop depending on order).
- Quarantine (only with the user's approval): move it to a non-blocking `quarantine` lane, open an
  issue, write the issue link and an expiry date (≤ 14 days) next to it. The quarantine lane fails
  once an entry is past its expiry.

## 5. Apply
Without `--interview`, apply the evidence-backed fixes directly (test files only). CI/config
changes stay proposals (SKILL.md rule 4). Re-run the affected tests and `test-smells.py scan` on the
scope; the report shows smell counts and runtime before → after.

## 6. Keep it from coming back
Propose (do not silently add) a CI guard step — copy `scripts/test-smells.py` into the project, e.g.
`.github/scripts/test-smells.py`, and run on pull requests:
```yaml
- run: python3 -I .github/scripts/test-smells.py diff origin/${{ github.base_ref }}
```
It fails the PR when a diff adds a skip, a commented test, a tautology, a loosened gate or deletes a
test file. The override is a label only maintainers can add (e.g. `test-change-approved`):
```yaml
if: ${{ !contains(github.event.pull_request.labels.*.name, 'test-change-approved') }}
```
