#!/usr/bin/env python3
"""Measure GitHub Actions cost for one repo — the baseline every `optimize` proposal starts from.

Usage:
  ci-usage.py OWNER/REPO [--since YYYY-MM-DD] [--days N] [--json]

Needs an authenticated `gh`. Read-only.

Reports:
  1. Billed minutes and money from the billing API (org or user), when the token can read it.
  2. Estimated billed minutes per (workflow, job): each job rounded UP to a whole minute,
     which is how GitHub bills, so many tiny jobs show their real cost.
  3. Per job: runs, average minutes, failure and cancel counts, triggering events.

Runs are fetched day by day: a single `created>=` query is capped at 1000 results.
"""
import argparse
import datetime as dt
import json
import math
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor


class RateLimited(Exception):
    pass


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode:
        if "rate limit" in (r.stderr + r.stdout).lower():
            raise RateLimited(path)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def parse(t):
    return dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")


def fetch_runs(repo, start, end):
    runs, day = [], start
    while day <= end:
        d, page = day.strftime("%Y-%m-%d"), 1
        while True:
            res = gh(f"repos/{repo}/actions/runs?created={d}&per_page=100&page={page}") or {}
            batch = res.get("workflow_runs", [])
            runs += batch
            if len(batch) < 100:
                break
            page += 1
        day += dt.timedelta(days=1)
    return runs


def billable(run):
    """Runs that never started a job cost nothing; skip their job lookups."""
    if run.get("conclusion") in ("skipped", "startup_failure", "action_required"):
        return False
    started, updated = run.get("run_started_at"), run.get("updated_at")
    return bool(started and updated and parse(updated) > parse(started))


def remaining_calls():
    res = gh("rate_limit") or {}
    core = res.get("resources", {}).get("core", {})
    return core.get("remaining"), core.get("reset")


def fetch_jobs(repo, run):
    res = gh(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100&filter=latest")
    return run, (None if res is None else res.get("jobs", []))


def billing(repo, start):
    owner, name = repo.split("/")
    out = defaultdict(lambda: [0.0, 0.0])
    months = sorted({(d.year, d.month) for d in (start, dt.datetime.utcnow())})
    for scope in (f"organizations/{owner}", f"users/{owner}"):
        got = False
        for y, m in months:
            res = gh(f"{scope}/settings/billing/usage?year={y}&month={m}")
            if not res or "usageItems" not in res:
                continue
            got = True
            for i in res["usageItems"]:
                if i.get("product") == "actions" and i.get("repositoryName") == name:
                    k = f"{y}-{m:02d} {i.get('sku')}"
                    out[k][0] += i.get("quantity", 0)
                    out[k][1] += i.get("netAmount", 0)
        if got:
            return dict(out)
    return None


def shard_key(name):
    # "PHPUnit (3/4)" and "test (ubuntu, 2)" style matrix names collapse to one row
    if "(" in name:
        return name.split("(")[0].strip() + " (matrix)"
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--since")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-runs", type=int, default=3000,
                    help="stop before fetching jobs for more runs than this (each run = 1 API call)")
    a = ap.parse_args()
    try:
        return run(a)
    except RateLimited:
        print("GitHub API rate limit exhausted — numbers would be incomplete, so nothing is reported. "
              "Check `gh api rate_limit` and retry after the reset, or narrow --days.", file=sys.stderr)
        return 3


def run(a):

    end = dt.datetime.utcnow()
    start = parse(a.since + "T00:00:00Z") if a.since else end - dt.timedelta(days=a.days)
    left, _ = remaining_calls()
    days = (end - start).days + 1
    if left is not None and left < days + 50:
        print(f"Only {left} GitHub API calls left this hour; need at least {days + 50}. Retry later.", file=sys.stderr)
        return 3
    all_runs = fetch_runs(a.repo, start.replace(hour=0, minute=0, second=0), end)
    runs = [r for r in all_runs if billable(r)]
    left, _ = remaining_calls()
    if len(runs) > a.max_runs or (left is not None and len(runs) > left - 20):
        print(f"{len(runs)} billable runs ({len(all_runs)} total) need {len(runs)} job lookups; "
              f"--max-runs={a.max_runs}, API calls left={left}. Narrow --days or raise --max-runs.", file=sys.stderr)
        return 3

    agg = defaultdict(lambda: {"jobs": 0, "billed": 0, "raw": 0.0, "fail": 0, "cancel": 0, "events": defaultdict(int)})
    dropped = 0
    with ThreadPoolExecutor(6) as ex:
        for run, jobs in ex.map(lambda r: fetch_jobs(a.repo, r), runs):
            if jobs is None:
                dropped += 1
                continue
            for j in jobs:
                if not j.get("started_at") or not j.get("completed_at"):
                    continue
                secs = (parse(j["completed_at"]) - parse(j["started_at"])).total_seconds()
                if secs <= 0:
                    continue
                r = agg[(run["name"], shard_key(j["name"]))]
                r["jobs"] += 1
                r["raw"] += secs / 60
                r["billed"] += math.ceil(secs / 60)
                r["fail"] += j.get("conclusion") == "failure"
                r["cancel"] += j.get("conclusion") == "cancelled"
                r["events"][run["event"]] += 1

    if dropped and dropped / max(len(runs), 1) > 0.02:
        print(f"{dropped} of {len(runs)} job lookups failed (API errors) — numbers would be under-reported, "
              "so nothing is reported. Retry later.", file=sys.stderr)
        return 3
    if dropped:
        print(f"warning: {dropped} job lookup(s) failed; totals slightly under-reported.", file=sys.stderr)
    total = sum(r["billed"] for r in agg.values())
    bill = billing(a.repo, start)
    rows = sorted(agg.items(), key=lambda x: -x[1]["billed"])

    if a.json:
        print(json.dumps({
            "repo": a.repo, "since": start.strftime("%Y-%m-%d"), "runs": len(all_runs), "billable_runs": len(runs),
            "estimated_billed_minutes": total, "billing_api": bill,
            "jobs": [{"workflow": w, "job": j, **{k: (dict(v) if k == "events" else v) for k, v in r.items()}}
                     for (w, j), r in rows],
        }, indent=1))
        return 0

    print(f"# CI usage — {a.repo} since {start:%Y-%m-%d} ({len(runs)} billable of {len(all_runs)} runs)\n")
    if bill:
        print("Billing API (actual):")
        for k, (q, usd) in sorted(bill.items()):
            print(f"  {k}: {q:,.0f} units, ${usd:,.2f} net")
    else:
        print("Billing API: not readable with this token (needs org admin / billing scope).")
    print(f"\nEstimated billed minutes (per-job round-up): {total:,}\n")
    print("| share | billed min | jobs | avg min | fail | cancel | workflow › job | events |")
    print("|---:|---:|---:|---:|---:|---:|---|---|")
    for (w, j), r in rows[:25]:
        share = 100 * r["billed"] / max(total, 1)
        print(f"| {share:.1f}% | {r['billed']:,} | {r['jobs']} | {r['raw'] / r['jobs']:.1f} | {r['fail']} | {r['cancel']} | {w} › {j} | {dict(r['events'])} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
