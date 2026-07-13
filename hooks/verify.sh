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

OUTPUT=$(npx tsc --noEmit 2>&1 && npx vitest run --reporter=basic 2>&1)
STATUS=$?

if [ $STATUS -ne 0 ]; then
  jq -n --arg out "$(echo "$OUTPUT" | tail -60)" \
    '{decision:"block", reason:("Verification gate failed (tsc/vitest). Fix before finishing:\n" + $out)}'
fi
exit 0
