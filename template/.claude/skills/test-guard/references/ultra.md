# --ultra — five independent designs, one verified winner

Use for `optimize` (and `create`/`audit` on large scopes) when the decision is expensive to get
wrong. It costs roughly six agent runs; say so before starting.

## Procedure
1. Build the shared brief once: scope, baseline numbers (`ci-usage.py`, JUnit timings,
   `test-smells.py`), constraints (what must keep running before ship, approval rules), and the
   scoring rubric below. Every candidate gets the same brief.
2. Dispatch **five read-only candidates in one parallel wave**, each with a different assigned
   strategy so they do not converge on the same answer. For `optimize`:
   - A. Blast-radius lanes (path filters + lane manifest)
   - B. Test-level selection inside the existing jobs (related/changed-only runners)
   - C. Execution efficiency (sharding balance, caching, DB/tmpfs, runner type)
   - D. Suite reduction (redundant/low-value tests, moving e2e checks down a layer)
   - E. Trigger hygiene (events, drafts, merge queue, nightly, tiny-job consolidation)
   For `create`: candidates differ by layer emphasis. For `audit`: by smell family.
   Each candidate returns: the patch or test list, the estimated saving with arithmetic from the
   baseline, the coverage risk, and how to verify it.
3. A failed candidate is retried once. Fewer than five usable results after the retry → stop and
   report (fail closed); do not pick from a partial field.
4. Verifier (a separate agent that did not author a candidate) scores each on:
   | Criterion | Weight |
   |---|---|
   | Measured/estimated saving (billed minutes and PR wait time), arithmetic checks out | 35% |
   | Coverage risk — can a breaking change reach the integration branch untested? | 35% |
   | Effort and blast radius of the change itself | 15% |
   | Verifiability — clear metric to confirm after shipping | 15% |
   Any candidate that lets some test run nowhere before ship scores 0 on coverage risk.
5. Result:
   - `optimize` / `create`: the single highest-scoring design, applied as-is (no Frankenstein
     merging — mixed designs lose the verifier's guarantees). Mention runner-up ideas that are
     independent and could follow as separate changes.
   - `audit`: the union of findings that the verifier confirmed with evidence, deduplicated.
6. Report the score table, why the winner won, and the rejected candidates in one line each.
