#!/bin/bash
# Stop hook: run tsc --noEmit + vitest on the whole diff before finishing.
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
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  [ -z "$(git status --porcelain 2>/dev/null)" ] && exit 0
fi

# --passWithNoTests: a project without test files is not a failing gate.
OUTPUT=$(npx tsc --noEmit 2>&1 && npx vitest run --reporter=basic --passWithNoTests 2>&1)
STATUS=$?

# Telemetry: record whether the change cleared the verify gate (a fit proxy).
MDIR="$ROOT/.claude/metrics"
if mkdir -p "$MDIR" 2>/dev/null; then
  PASS=$([ $STATUS -eq 0 ] && echo true || echo false)
  jq -c -n --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
           --arg session "$(echo "$INPUT" | jq -r '.session_id // "unknown"')" \
           --argjson pass "$PASS" \
           '{ts:$ts, session:$session, kind:"verify", pass:$pass}' \
    >> "$MDIR/events.jsonl" 2>/dev/null || true
fi

if [ $STATUS -ne 0 ]; then
  jq -n --arg out "$(echo "$OUTPUT" | tail -60)" \
    '{decision:"block", reason:("Verification gate failed (tsc/vitest). Fix before finishing:\n" + $out)}'
fi
exit 0
