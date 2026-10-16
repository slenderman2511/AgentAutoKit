#!/usr/bin/env bash
# Prove a new/changed test can fail: temporarily revert the NON-test source changes since BASE,
# run the test command, then restore the working tree exactly.
#
# Usage: red-check.sh BASE -- <test command ...>
#   e.g. red-check.sh origin/dev -- npx vitest run src/lib/price.test.ts
#        red-check.sh origin/dev -- ./vendor/bin/phpunit --filter PriceTest
#
# Exit: 0 = test FAILED without the change (good: it guards the behavior)
#       1 = test PASSED without the change (it does not prove the change — rewrite or drop it)
#       2 = setup error (nothing reverted, or the tree could not be restored — see message)
#
# Read the red output: a failure from a missing import/new file is NOT proof; the test must fail on
# an assertion about behavior. Untracked files are left in place.
set -uo pipefail

[ "${2:-}" = "--" ] || { echo "usage: red-check.sh BASE -- <test command>" >&2; exit 2; }
BASE=$1; shift 2
[ $# -gt 0 ] || { echo "missing test command" >&2; exit 2; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repository" >&2; exit 2; }
MB=$(git merge-base "$BASE" HEAD 2>/dev/null) || { echo "cannot resolve merge-base of $BASE and HEAD" >&2; exit 2; }

TEST_RX='(\.(test|spec|e2e)\.[cm]?[jt]sx?$)|(_test\.(go|py)$)|(^|/)test_[^/]*\.py$|Test\.php$|(^|/)tests?/'
SRC=()
while IFS= read -r f; do SRC+=("$f"); done < <(git diff --name-only "$MB" | grep -Ev "$TEST_RX" | grep -Ev '(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|composer\.lock)$')
[ ${#SRC[@]} -gt 0 ] || { echo "no non-test changes since $BASE — nothing to revert" >&2; exit 2; }

PATCH=$(mktemp "${TMPDIR:-/tmp}/red-check.XXXXXX.patch")
git diff --binary "$MB" -- "${SRC[@]}" > "$PATCH"
BEFORE=$(git diff --binary "$MB" -- "${SRC[@]}" | git hash-object --stdin)

RESTORED=""
restore() {
  [ -n "$RESTORED" ] && return 0
  RESTORED=1
  trap - EXIT INT TERM
  git apply --whitespace=nowarn "$PATCH" 2>/dev/null
  AFTER=$(git diff --binary "$MB" -- "${SRC[@]}" | git hash-object --stdin)
  if [ "$AFTER" != "$BEFORE" ]; then
    echo "!! working tree NOT restored. Re-apply manually: git apply $PATCH" >&2
    exit 2
  fi
  rm -f "$PATCH"
}
trap restore EXIT
trap 'restore; exit 130' INT TERM

git apply -R --whitespace=nowarn "$PATCH" || { trap - EXIT; rm -f "$PATCH"; echo "could not revert source changes" >&2; exit 2; }
echo "== reverted ${#SRC[@]} source file(s) to $BASE: ${SRC[*]}"
echo "== running: $*"
"$@"
CODE=$?

if [ $CODE -ne 0 ]; then
  echo "== RED (exit $CODE): the test fails without the change — check above that it failed on an assertion."
  RESULT=0
else
  echo "== STILL GREEN without the change: this test does not prove the new behavior."
  RESULT=1
fi
restore
exit $RESULT
