# optimize — cheaper, faster CI from measurements

Goal: fewer billed minutes and shorter PR wait **without** losing what the suite proves.
Every proposal starts from numbers and ends with numbers.

## 1. Baseline (mandatory, read-only)
```
python3 -I scripts/ci-usage.py OWNER/REPO --days 30            # per workflow › job, billed minutes
gh api rate_limit --jq .resources.core                         # ci-usage needs ~1 call per run
```
- `ci-usage.py` estimates billed minutes per job (each job rounded up to a whole minute — how
  GitHub bills) and adds the billing API figures when the token can read them. On a real repo the
  estimate matched the billing API within 1%; if they differ by >10%, find out why before proposing.
- Repos with thousands of runs (issue/comment-triggered bots) can exhaust the 5,000 calls/hour
  limit: narrow `--days` first. The script refuses to print partial numbers.
- Also collect: the slowest test files (JUnit timings), setup time per job (checkout → first test),
  failure and cancel rate per job, and which events trigger each workflow.

Write the baseline table into the report before proposing anything:
`job | runs | avg min | billed min/30d | share | fail% | trigger`.

## 2. Find where the money goes — check in this order

| # | Smell (seen in real repos) | Check | Typical fix |
|---|---|---|---|
| 1 | Whole suite on every push regardless of what changed | Does a docs/frontend-only PR run backend tests? | Blast-radius lanes (`lanes.md`) |
| 2 | Tiny jobs billed as 1 minute each (report/metadata/notify/label jobs of 5–10 s) | Jobs with avg < 0.5 min and many runs | Fold them into the job that already runs, or one final `ci-gate` job |
| 3 | Per-shard setup dominates (DB service + install ~1.5 min per shard) | setup time × shards vs test time | Fewer, balanced shards (by timing file); cache deps; tmpfs DB |
| 4 | Duplicate runs | same SHA run by `push` and `pull_request`; no `concurrency` | `concurrency` + `cancel-in-progress`; run on one event |
| 5 | Expensive lanes on draft / WIP pushes | runs on `draft: true` PRs | skip drafts; heavy lanes on `ready_for_review`/label/merge queue |
| 6 | Event storms | workflows on `issues`, `issue_comment`, `schedule` with hundreds of runs, many cancelled | tighter `types:`, `if:` on labels/authors, debounce with `concurrency` |
| 7 | Deploy jobs rebuilding from scratch | deploy avg >> build cache-hit time | Docker layer cache (`cache-from: type=gha`), remote builder cache |
| 8 | No `timeout-minutes` | jobs without it (default 360) | set per job to ~2× p95 |
| 9 | Artifacts on success | `upload-artifact` without `if: failure()` | upload traces/videos on failure, `retention-days: 3–7` |
| 10 | Expensive runners | `macos-*` (~10× Linux), `windows-*` (~2×) | only where the platform is the thing tested; `ubuntu-24.04-arm` is cheaper than x64 |
| 11 | Failing-by-default jobs | job fails > 50% of runs | a gate everyone ignores is noise: fix it or make it not run (and say so) |

Sharding trades money for wall time: N shards × setup overhead. Only add shards when the PR wait
time matters more than the extra setup minutes — state both numbers.

## 3. Design the change
- Lanes and path filters: `references/lanes.md`.
- Keep a full-suite run somewhere that blocks shipping: merge queue (`merge_group`), the release
  branch, or the prod deploy gate — plus a nightly `schedule`. Lanes decide what runs **per PR**;
  they never decide that something runs **nowhere**.
- Order: cheap fail-fast jobs first (typecheck, lint, unit), expensive jobs `needs:` them.
- Estimate the saving per change from the baseline (e.g. "lane-filter PHPUnit: 64% of PRs touch no
  PHP → −0.64 × 11,000 = −7,000 min/30d"). Use the git history of merged PRs for the touch ratio:
  `git log --since=30.days --merges --name-only` or `gh pr list --state merged --json files`.

## 4. Deliver as a proposal
CI files are human-reviewed (SKILL.md rule 4). Produce:
1. The patch (`git diff` format) for `.github/workflows/**` and any lane manifest.
2. The baseline table, the estimated after-table, and the assumptions behind each estimate.
3. A verification plan: which PRs to watch, and `ci-usage.py --since <merge date>` after a week.
With `--interview`, present each change group (lanes / sharding / caching / triggers / cleanup)
separately and wait for approval of each.

## 5. After it ships
Re-run `ci-usage.py --since <merge date>` and report actual vs estimated. If a lane never ran in a
week where its paths changed, the filter is wrong — fix it before anything else.
