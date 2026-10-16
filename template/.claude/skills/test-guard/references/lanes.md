# Blast-radius lanes + GitHub Actions patterns

A lane is a group of tests that runs only when files that can break it change. Per PR you run the
lanes the diff can reach; the full suite still runs before shipping.

## 1. Lane manifest — one source of truth
Keep it in the repo, e.g. `.github/test-lanes.yml`, and make CI read it (dorny/paths-filter reads
this format directly via `filters: .github/test-lanes.yml`):

```yaml
# Lane → globs that can break it. A file may belong to several lanes.
core:            # any change here runs EVERYTHING
  - package.json
  - package-lock.json
  - composer.lock
  - .github/workflows/**
  - .github/test-lanes.yml
  - src/lib/shared/**
  - phpunit.xml
backend-unit:
  - app/**
  - tests/Unit/**
backend-feature:
  - app/**
  - routes/**
  - database/**
  - tests/Feature/**
frontend:
  - resources/js/**
  - src/components/**
  - "**/*.test.ts"
e2e-booking:
  - app/Http/Controllers/Booking/**
  - resources/js/pages/booking/**
  - tests/e2e/booking/**
```

Building the manifest:
1. Start from the test directory layout and the import graph (`madge --json` / `dependency-cruiser`
   for JS/TS; PSR-4 namespaces for PHP; package imports for Python/Go).
2. Check it against history: for the last 30–90 days of merged PRs, compute which lanes each PR
   would trigger and whether any PR that broke a test on the integration branch would have skipped
   the lane containing that test. Any miss → widen the lane.
3. **Coverage check**: every source file must match at least one lane. A file matching no lane is
   treated as `core` (run everything) — write that rule into the CI step, not just the doc.

## 2. Finer selection inside a lane (optional)
- Vitest: `vitest related <changed files> --run` or `vitest --changed origin/<base>`.
- Jest: `--findRelatedTests <files>` / `--changedSince=origin/<base>`.
- Playwright: `--only-changed=origin/<base>` (spec files changed or importing changed files).
- PHPUnit: no built-in impact analysis — select testsuites/groups per lane; split by directory.
- pytest: `pytest-testmon`. Go: `go test` per changed package and its reverse deps.
Use these to speed up a lane, never as the only gate — they miss non-import dependencies
(config, DB schema, env).

## 3. Workflow skeleton

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  merge_group:            # full suite before merge when a merge queue is enabled
  schedule:
    - cron: "17 2 * * *"  # nightly full suite

concurrency:
  group: tests-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  changes:
    if: github.event_name != 'pull_request' || !github.event.pull_request.draft
    runs-on: ubuntu-latest
    timeout-minutes: 3
    outputs:
      lanes: ${{ steps.f.outputs.changes }}
      full: ${{ steps.full.outputs.full }}
    steps:
      - uses: actions/checkout@v4
      - id: f
        uses: dorny/paths-filter@v3
        with:
          filters: .github/test-lanes.yml
      - id: full
        run: |
          if [ "${{ github.event_name }}" != "pull_request" ] || [ "${{ steps.f.outputs.core }}" = "true" ]; then
            echo "full=true" >> "$GITHUB_OUTPUT"; else echo "full=false" >> "$GITHUB_OUTPUT"; fi

  backend-unit:
    needs: changes
    if: needs.changes.outputs.full == 'true' || contains(fromJSON(needs.changes.outputs.lanes), 'backend-unit')
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps: [...]

  # ...one job per lane...

  ci-gate:                      # the ONLY required status check
    if: always()
    needs: [changes, backend-unit, backend-feature, frontend, e2e-booking]
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - run: |
          echo '${{ toJSON(needs) }}' | jq -e 'to_entries | all(.value.result == "success" or .value.result == "skipped")'
```

Why `ci-gate`: a required check on a job that a path filter skipped stays "pending" forever and
blocks merging. Require only `ci-gate`; it passes when every lane succeeded or was legitimately
skipped, and fails when any lane failed or was cancelled. Put report/notify steps inside it instead
of separate tiny jobs — each extra job is billed as at least one minute.

## 4. Cost rules of thumb
- Every job is billed rounded up to a whole minute, plus its own checkout/setup. Ten 20-second jobs
  cost 10 minutes; one 3-minute job costs 3.
- Shards: total cost ≈ shards × (setup + test/shards). They cut wall time, not money. Balance by a
  timings file regenerated from JUnit, not by file count.
- Cache: `actions/setup-node` `cache: npm`, `shivammathur/setup-php` + `actions/cache` for
  `vendor/` keyed on `composer.lock`, `~/.cache/ms-playwright` keyed on the Playwright version,
  Docker `cache-from: type=gha`. A cache that misses on most runs is a cost, check its hit rate.
- Databases in CI: service containers with `--tmpfs` for the data dir and durability off
  (`innodb_flush_log_at_trx_commit=0`, `fsync=off` for Postgres) — test data does not need to survive.
- Drafts skip heavy lanes; `ready_for_review` triggers them.
- Never let `continue-on-error` or `|| true` touch a test step; use it only for notifications.
