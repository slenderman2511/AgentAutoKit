#!/usr/bin/env python3
"""Find tests that cannot fail, disabled tests, and loosened CI gates.

Usage:
  test-smells.py scan [PATH ...] [--weak]              whole files (default: .)
  test-smells.py diff BASE [--fail-on CATS] [--weak]   only lines ADDED since merge-base(BASE, HEAD),
                                                       working tree included

Categories:
  env-skip    skip gated on a condition/env var (runs nowhere if CI lacks the env — check it runs SOMEWHERE)
  disabled    skip / only / todo / fixme / xit / markTestSkipped / pytest skip / t.Skip
  commented   a test declaration commented out
  tautology   an assertion that compares a literal or a value with itself
  no-assert   a test file with test cases but no assertion at all (scan mode only)
  weak        assertion that proves almost nothing (bare toHaveBeenCalled, toBeDefined, ...) — only with --weak
  loosened    retries, --passWithNoTests, `|| true` after a test command
  soft-fail   `continue-on-error: true` in a workflow (legit for notify/deploy steps; check test steps)
  deleted     a test file removed (diff mode only)

Output: one line per finding `file:line  category  snippet`, then a summary.
Exit code: 0, or 1 in diff mode when a finding's category is in --fail-on
(default: disabled,commented,tautology,loosened). Heuristics: every finding needs a human/agent look.
"""
import os
import re
import subprocess
import sys

TEST_FILE = re.compile(
    r"(\.(test|spec|e2e)\.[cm]?[jt]sx?$)|(_test\.(go|py)$)|(^|/)test_[^/]*\.py$|Test\.php$|(^|/)tests?/.*\.(php|py|[cm]?[jt]sx?)$"
)
CI_FILE = re.compile(
    r"(^|/)\.github/workflows/.*\.ya?ml$|(^|/)(vitest|jest|playwright)\.config\.[cm]?[jt]s$|(^|/)phpunit\.xml(\.dist)?$|(^|/)(pytest\.ini|pyproject\.toml|package\.json)$"
)

RULES = [
    ("env-skip", re.compile(
        r"\b(test|it|describe)\.skip\(\s*[!\w(]"
        r"|@pytest\.mark\.skipif\b"
    )),
    ("disabled", re.compile(
        r"\b(it|test|describe|context|suite)\.(skip|only|todo|fixme)\b"
        r"|\b(xit|xdescribe|xtest|fit|fdescribe)\s*\("
        r"|\btest\.fixme\s*\("
        r"|\$this->mark(TestSkipped|TestIncomplete)\s*\("
        r"|->(skip|todo)\s*\("
        r"|#\[\s*(Skip|Ignore)\b|@group\s+(skip|ignore|disabled)\b"
        r"|@(pytest\.mark\.(skip|xfail)|unittest\.skip)\b"
        r"|\bt\.Skip(f|Now)?\s*\("
    )),
    ("commented", re.compile(
        r"^\s*(//|#|/\*)\s*(it|test|describe)(\.\w+)?\(\s*['\"`]"
        r"|^\s*(//|#)\s*(public\s+)?function\s+test\w*\s*\("
        r"|^\s*#\s*def\s+test_\w+\s*\("
        r"|^\s*//\s*func\s+Test\w+\s*\("
    )),
    ("tautology", re.compile(
        r"expect\(\s*(true|false|null|undefined|-?\d+(\.\d+)?|(['\"`])[^'\"`]*\3)\s*\)\s*\.(not\.)?(toBe|toEqual|toStrictEqual)\s*\("
        r"|expect\(\s*([\w.]+)\s*\)\s*\.(toBe|toEqual|toStrictEqual)\(\s*\6\s*\)"
        r"|assert(True|False)\(\s*(true|false|True|False)\s*\)"
        r"|assert(Equals|Same)\(\s*(?P<same>[^,()]+?)\s*,\s*(?P=same)\s*\)"
        r"|^\s*assert\s+(True|1|not\s+False)\s*$"
        r"|\bexpect\(\s*1\s*\)\.toBe\(\s*1\s*\)"
    )),
    ("weak", re.compile(
        r"\.toHaveBeenCalled\(\s*\)"
        r"|expect\([^)]*\)\.(toBeDefined|toBeTruthy|not\.toBeNull)\(\s*\)\s*;?\s*$"
        r"|assertNotNull\(\s*\$\w+\s*\)\s*;\s*$"
    )),
]

LOOSENED = re.compile(
    r"\bretries\s*:\s*[1-9]"
    r"|retryTimes\s*\(\s*[1-9]"
    r"|--passWithNoTests\b|passWithNoTests\s*:\s*true"
    r"|\b(test|vitest|jest|playwright|phpunit|pest|pytest|go test)\b[^\n#]*\|\|\s*(true|exit 0|:)\s*$"
    r"|--(bail|max-failures)=0\b"
    r"|failOnRisky\s*=\s*\"false\"|stopOnFailure\s*=\s*\"false\""
)
SKIP_DIRS = {"node_modules", "vendor", ".git", "dist", "build", ".next", "coverage", "storage",
             ".claude", ".worktrees", "worktrees", ".omc", "playwright-report", "test-results", ".venv"}
ASSERT = re.compile(r"\b(expect|assert\w*|should|t\.(Error|Fatal|Fail)\w*|require\.\w+|toMatch\w*)\b|\$this->assert")
CASE = re.compile(r"\b(it|test)\s*\(\s*['\"`]|function\s+test\w*\s*\(|def\s+test_\w+|func\s+Test\w+\s*\(|#\[\s*Test\s*\]")


SOFT_FAIL = re.compile(r"^\s*continue-on-error\s*:\s*true")


def classify(path, line, weak=False):
    hits = []
    if TEST_FILE.search(path):
        for cat, rx in RULES:
            if cat == "weak" and not weak:
                continue
            if cat == "disabled" and "env-skip" in hits:
                continue
            if rx.search(line):
                hits.append(cat)
    if (TEST_FILE.search(path) or CI_FILE.search(path)) and LOOSENED.search(line):
        hits.append("loosened")
    if CI_FILE.search(path) and SOFT_FAIL.search(line):
        hits.append("soft-fail")
    return hits


def scan(paths, weak=False):
    findings = []
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
            continue
        for root, dirs, names in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            files += [os.path.join(root, n) for n in names]
    for f in files:
        rel = os.path.relpath(f)
        if not (TEST_FILE.search(rel) or CI_FILE.search(rel)):
            continue
        try:
            lines = open(f, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for cat in classify(rel, line, weak):
                findings.append((rel, i, cat, line.strip()))
        if TEST_FILE.search(rel):
            body = "\n".join(lines)
            if CASE.search(body) and not ASSERT.search(body):
                findings.append((rel, 1, "no-assert", f"{len(CASE.findall(body))} test case(s), no assertion found"))
    return findings


def added_lines(base):
    """Yield (path, line_no, text) for lines added since BASE, including uncommitted work."""
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", "--no-ext-diff", base],
        capture_output=True, text=True, check=True,
    ).stdout
    path, n = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            n = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            yield path, n, raw[1:]
            n += 1


def deleted_tests(base):
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", base],
                         capture_output=True, text=True, check=True).stdout
    return [line.split("\t", 1)[1] for line in out.splitlines()
            if line.startswith("D\t") and TEST_FILE.search(line.split("\t", 1)[1])]


def main():
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    mode = args.pop(0)
    fail_on = {"disabled", "commented", "tautology", "loosened"}
    weak = "--weak" in args
    if weak:
        args.remove("--weak")
    if "--fail-on" in args:
        i = args.index("--fail-on")
        fail_on = set(args[i + 1].split(","))
        del args[i:i + 2]

    if mode == "scan":
        findings = scan(args or ["."], weak)
    elif mode == "diff":
        if not args:
            print("diff needs a BASE ref", file=sys.stderr)
            return 2
        if args[0].startswith("-"):
            print(f"BASE must be a git ref, not an option: {args[0]}", file=sys.stderr)
            return 2
        merge_base = subprocess.run(["git", "merge-base", args[0], "HEAD"],
                                    capture_output=True, text=True).stdout.strip() or args[0]
        findings = [(p, n, c, t.strip()) for p, n, t in added_lines(merge_base) for c in classify(p, t, weak)]
        findings += [(p, 0, "deleted", "test file deleted") for p in deleted_tests(merge_base)]
        fail_on.add("deleted")
    else:
        print(__doc__)
        return 2

    by_cat = {}
    for path, line, cat, text in findings:
        by_cat[cat] = by_cat.get(cat, 0) + 1
        print(f"{path}:{line}\t{cat}\t{text[:160]}")
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())) or "none"
    print(f"\n{len(findings)} finding(s): {summary}")
    if mode == "diff" and any(c in fail_on for c in by_cat):
        print("FAIL: blocked categories present — explain each one in the PR or get explicit approval.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
