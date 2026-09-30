#!/bin/bash
# Stop hook: typecheck the whole project + run the tests related to the change
# before finishing. The full suite belongs to CI; running it on every Stop made
# the gate slow and red for reasons unrelated to the change.
# Emits {"decision":"block","reason":...} to force Claude to fix failures.
INPUT=$(cat)

# Prevent infinite loop: if we're already inside a stop-hook cycle, exit clean.
[ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ] && exit 0

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$ROOT" || exit 0

# Skip gracefully if no package.json (nothing to verify).
[ -f package.json ] || exit 0

# Chat-only sessions have nothing to verify — running the gate would only
# pollute the verify-rate telemetry with events unrelated to any change.
# Exclude .claude/metrics: this hook's own telemetry write must not count as
# a dirty tree, or every Stop after the first re-runs the full gate.
IN_GIT=0
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  IN_GIT=1
  [ -z "$(git status --porcelain -- ':!.claude/metrics' 2>/dev/null)" ] && exit 0
fi

STEP=""
OUTPUT=""
STATUS=0

# 1) Typecheck, only for TypeScript projects.
if [ -f tsconfig.json ]; then
  OUTPUT=$(npx tsc --noEmit 2>&1); STATUS=$?
  [ $STATUS -ne 0 ] && STEP="tsc"
fi

# 2) Tests related to the changed files (tracked changes + new files).
#    --passWithNoTests: a change without related tests is not a failing gate.
#    --reporter=default: the 'basic' reporter was removed in Vitest 3.
if [ $STATUS -eq 0 ] && grep -q '"vitest"' package.json; then
  if [ $IN_GIT -eq 1 ]; then
    CHANGED=$( { git diff --name-only HEAD -- 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
      | grep -E '\.(c|m)?[jt]sx?$' | sort -u | while IFS= read -r f; do [ -f "$f" ] && printf '%s\n' "$f"; done)
    if [ -n "$CHANGED" ]; then
      OUTPUT=$(printf '%s\n' "$CHANGED" | tr '\n' '\0' | xargs -0 npx vitest related --run --reporter=default --passWithNoTests 2>&1); STATUS=$?
      [ $STATUS -ne 0 ] && STEP="vitest"
    fi
  else
    OUTPUT=$(npx vitest run --reporter=default --passWithNoTests 2>&1); STATUS=$?
    [ $STATUS -ne 0 ] && STEP="vitest"
  fi
fi

# Telemetry: record whether the change cleared the verify gate (a fit proxy),
# plus which step failed and the last lines of its output.
MDIR="$ROOT/.claude/metrics"
if mkdir -p "$MDIR" 2>/dev/null; then
  PASS=$([ $STATUS -eq 0 ] && echo true || echo false)
  TAIL=$([ $STATUS -eq 0 ] && echo "" || echo "$OUTPUT" | tail -20)
  jq -c -n --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
           --arg session "$(echo "$INPUT" | jq -r '.session_id // "unknown"')" \
           --argjson pass "$PASS" --arg step "$STEP" --arg tail "$TAIL" \
           '{ts:$ts, session:$session, kind:"verify", pass:$pass}
            + (if $step == "" then {} else {step:$step, tail:$tail} end)' \
    >> "$MDIR/events.jsonl" 2>/dev/null || true
fi

if [ $STATUS -ne 0 ]; then
  jq -n --arg step "$STEP" --arg out "$(echo "$OUTPUT" | tail -60)" \
    '{decision:"block", reason:("Verification gate failed (" + $step + "). Fix before finishing:\n" + $out)}'
fi
exit 0
