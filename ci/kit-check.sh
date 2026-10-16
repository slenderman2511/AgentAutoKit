#!/usr/bin/env bash
# Kit build-test runner: automates CLAUDE.md "Verify before claiming done".
# Run it locally before a PR; ci/kit-ci.workflow.yml runs the same steps in GitHub Actions.
#
# Usage: ci/kit-check.sh [step ...]     (default: every step, in order)
# Steps: syntax json surfaces validate install selftest
#
# A step whose tool is missing is SKIPPED locally and FAILS in CI (KIT_CI=1 or GITHUB_ACTIONS=true).
# Prints a PASS/FAIL/SKIP table; in GitHub Actions it is also appended to the job summary.
# Exit: 0 when no step failed, 1 otherwise.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
STRICT=0
{ [ "${KIT_CI:-}" = 1 ] || [ "${GITHUB_ACTIONS:-}" = true ]; } && STRICT=1
ALL_STEPS=(syntax json surfaces validate install selftest)
RESULTS=()
FAILED=0

need() {  # $1=tool — 0 if present; otherwise SKIP locally (1) or FAIL in CI (2)
  command -v "$1" >/dev/null 2>&1 && return 0
  if [ "$STRICT" -eq 1 ]; then echo "missing tool: $1" >&2; return 2; fi
  echo "SKIP: $1 not installed" >&2; return 1
}

step_syntax() {
  local f rc=0
  while IFS= read -r -d '' f; do bash -n "$f" || { echo "bash -n failed: $f"; rc=1; }; done < <(git ls-files -z '*.sh')
  need python3; case $? in 1) return 3 ;; 2) return 1 ;; esac
  # compile() only: py_compile would drop __pycache__/ into the tree.
  while IFS= read -r -d '' f; do
    python3 -c 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")' "$f" \
      || { echo "python syntax error: $f"; rc=1; }
  done < <(git ls-files -z '*.py')
  return $rc
}

step_json() {
  need jq; case $? in 1) return 3 ;; 2) return 1 ;; esac
  local f rc=0
  while IFS= read -r -d '' f; do jq -e . "$f" >/dev/null || { echo "invalid JSON: $f"; rc=1; }; done < <(git ls-files -z '*.json')
  return $rc
}

step_surfaces() {
  # Plugin and template surfaces stay byte-identical; the only by-design differences are the
  # script paths in kit-stats.md / kit-tune.md, hooks/hooks.json (plugin-only) and init.sh (kit-only).
  local x=(-x .DS_Store -x __pycache__ -x node_modules) rc=0 f
  diff -rq "${x[@]}" agents template/.claude/agents || rc=1
  diff -rq "${x[@]}" -x kit-stats.md -x kit-tune.md commands template/.claude/commands || rc=1
  diff -rq "${x[@]}" -x hooks.json hooks template/.claude/hooks || rc=1
  diff -rq "${x[@]}" skills template/.claude/skills || rc=1
  diff -rq "${x[@]}" -x init.sh scripts template/.claude/scripts || rc=1
  for f in commands/kit-stats.md commands/kit-tune.md template/.claude/commands/kit-stats.md template/.claude/commands/kit-tune.md; do
    [ -f "$f" ] || { echo "missing: $f"; rc=1; }
  done
  return $rc
}

step_validate() {
  need claude; case $? in 1) return 3 ;; 2) return 1 ;; esac
  need jq; case $? in 1) return 3 ;; 2) return 1 ;; esac
  # Same bar as `claude plugin validate . --strict`, minus one known warning: newer CLIs flag a
  # root CLAUDE.md as "not loaded as project context". Ours is dev-only by design (it documents
  # the kit for sessions working ON it), so that warning is expected; any other warning fails.
  local out
  out=$(claude plugin validate . --json) || { echo "$out"; return 1; }
  echo "$out" | jq -e '
    ([.manifest] + (.contents // [])) as $parts
    | ([$parts[].errors[]?] | length) == 0
      and ([$parts[].warnings[]? | select(.message | startswith("CLAUDE.md at the plugin root") | not)] | length) == 0
      and .success
  ' >/dev/null || { echo "$out"; return 1; }
  claude plugin validate .claude-plugin/plugin.json >/dev/null || { claude plugin validate .claude-plugin/plugin.json; return 1; }
}

step_install() {
  need git; case $? in 1) return 3 ;; 2) return 1 ;; esac
  local tmp out rc=0 ver f
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/kit-install.XXXXXX")
  git -C "$tmp" init -q
  # Dry run must not write anything.
  scripts/init.sh "$tmp" --dry-run >/dev/null || { echo "dry-run failed"; rc=1; }
  [ -e "$tmp/.claude" ] || [ -e "$tmp/CLAUDE.md" ] && { echo "dry-run wrote files"; rc=1; }
  # Real install.
  scripts/init.sh "$tmp" >/dev/null || { echo "install failed"; rc=1; }
  for f in CLAUDE.md .claude/settings.json .claude/agents/orchestrator.md .claude/commands/init-kit.md \
           .claude/hooks/protect-files.sh .claude/rules/workflow.md .claude/ci/ci.workflow.yml; do
    [ -f "$tmp/$f" ] || { echo "not installed: $f"; rc=1; }
  done
  [ -e "$tmp/.claude/CLAUDE.md" ] && { echo ".claude/CLAUDE.md should not exist"; rc=1; }
  [ -x "$tmp/.claude/hooks/verify.sh" ] || { echo "hooks not executable"; rc=1; }
  ver=$(jq -r .version .claude-plugin/plugin.json 2>/dev/null)
  [ "$(cat "$tmp/.claude/.agentautokit-version" 2>/dev/null)" = "$ver" ] || { echo "version stamp != $ver"; rc=1; }
  for f in .claude/settings.local.json .claude/metrics/ .claude/worktrees/; do
    grep -qxF "$f" "$tmp/.gitignore" || { echo ".gitignore lacks $f"; rc=1; }
  done
  # Re-running is a no-op.
  out=$(scripts/init.sh "$tmp") || { echo "re-run failed"; rc=1; }
  echo "$out" | grep -q "Done: 0 installed, 0 updated" || { echo "re-run not idempotent:"; echo "$out"; rc=1; }
  rm -rf "$tmp"
  return $rc
}

step_selftest() {
  local rc=0 ran=0 tmp out
  if [ -f skills/launch-check/scripts/selftest.mjs ]; then
    need node; case $? in 1) ;; 2) rc=1 ;; *) ran=1; node skills/launch-check/scripts/selftest.mjs || rc=1 ;; esac
  fi
  # test-guard has no selftest of its own: smoke its two scripts on throwaway fixtures.
  if need python3 && need git; then
    ran=1
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/kit-selftest.XXXXXX")
    printf "it.skip('a', () => { expect(1).toBe(1) })\n" > "$tmp/a.test.ts"
    out=$(python3 skills/test-guard/scripts/test-smells.py scan "$tmp")
    echo "$out" | grep -q disabled || { echo "test-smells missed it.skip:"; echo "$out"; rc=1; }
    echo "$out" | grep -q tautology || { echo "test-smells missed a tautology:"; echo "$out"; rc=1; }
    # red-check: the test must fail once the source change is reverted, and the tree comes back.
    git -C "$tmp" init -q && echo old > "$tmp/src.txt" \
      && git -C "$tmp" add src.txt && git -C "$tmp" -c user.email=ci@kit -c user.name=ci commit -qm base
    echo new > "$tmp/src.txt"
    (cd "$tmp" && bash "$ROOT/skills/test-guard/scripts/red-check.sh" HEAD -- grep -q new src.txt) >/dev/null 2>&1 \
      || { echo "red-check did not report a guarding test"; rc=1; }
    [ "$(cat "$tmp/src.txt")" = new ] || { echo "red-check did not restore the tree"; rc=1; }
    rm -rf "$tmp"
  elif [ "$STRICT" -eq 1 ]; then rc=1
  fi
  [ "$rc" -eq 0 ] && [ "$ran" -eq 0 ] && return 3
  return $rc
}

steps=("$@")
[ ${#steps[@]} -eq 0 ] && steps=("${ALL_STEPS[@]}")
for s in "${steps[@]}"; do
  if ! declare -F "step_$s" >/dev/null; then echo "unknown step: $s (steps: ${ALL_STEPS[*]})" >&2; exit 2; fi
  echo "== $s"
  "step_$s"; rc=$?
  case $rc in
    0) RESULTS+=("| $s | PASS |") ;;
    3) RESULTS+=("| $s | SKIP |") ;;
    *) RESULTS+=("| $s | FAIL |"); FAILED=1 ;;
  esac
done

report=$(printf '| step | result |\n|---|---|\n'; printf '%s\n' "${RESULTS[@]}")
echo; echo "$report"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$report" >> "$GITHUB_STEP_SUMMARY"
exit $FAILED
