#!/bin/bash
# PreToolUse hook (Edit|Write|MultiEdit): an edit that ADDS a way to silence a test — skip/only,
# a commented-out test, an always-true assertion, retries or `|| true` — is held for the user's
# approval instead of going through silently. Existing occurrences are not re-flagged: only what the
# edit adds (count in new text > count in replaced text) triggers the prompt.
# Output: permissionDecision "ask" JSON on stdout. Exit 0 always (never blocks on its own errors).
INPUT=$(cat)
command -v jq >/dev/null 2>&1 || { echo "test-guard: jq not found, hook skipped" >&2; exit 0; }

FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

case "$FILE" in
  *.test.* | *.spec.* | *.e2e.* | *_test.go | *_test.py | */test_*.py | *Test.php | \
  */tests/* | */test/* | */__tests__/* | \
  */vitest.config.* | */jest.config.* | */playwright.config.* | */phpunit.xml* | \
  */pytest.ini | */.github/workflows/*) ;;
  *) exit 0 ;;
esac

NEW=$(echo "$INPUT" | jq -r '[.tool_input.new_string, .tool_input.content, (.tool_input.edits // [] | .[].new_string)] | map(select(. != null)) | join("\n")')
OLD=$(echo "$INPUT" | jq -r '[.tool_input.old_string, (.tool_input.edits // [] | .[].old_string)] | map(select(. != null)) | join("\n")')
# Write replaces the whole file: compare against what is on disk now.
if [ -z "$OLD" ] && [ -f "$FILE" ] && echo "$INPUT" | jq -e '.tool_input.content != null' >/dev/null; then
  OLD=$(cat "$FILE")
fi

count() { printf '%s' "$1" | grep -cE "$2"; }

REASONS=""
check() {
  local label=$1 rx=$2
  if [ "$(count "$NEW" "$rx")" -gt "$(count "$OLD" "$rx")" ]; then
    REASONS="${REASONS}${REASONS:+; }$label"
  fi
}
check "disables a test (skip/only/todo/xit/markTestSkipped)" \
  '\b(it|test|describe)\.(skip|only|todo|fixme)\b|\b(xit|xdescribe|xtest|fit|fdescribe)\(|markTest(Skipped|Incomplete)\(|@pytest\.mark\.(skip|xfail)|unittest\.skip|t\.Skip(f|Now)?\('
check "comments out a test" \
  '^[[:space:]]*(//|#)[[:space:]]*((it|test|describe)(\.[a-z]+)?\(|(public[[:space:]]+)?function[[:space:]]+test|def[[:space:]]+test_|func[[:space:]]+Test)'
check "adds an assertion that cannot fail" \
  'expect\(true\)\.(toBe|toEqual)\(true\)|expect\(false\)\.(toBe|toEqual)\(false\)|expect\(1\)\.(toBe|toEqual)\(1\)|assert(True|False)\((true|false|True|False)\)|^[[:space:]]*assert[[:space:]]+True[[:space:]]*$'
check "loosens the gate (retries, passWithNoTests, || true, continue-on-error)" \
  'retries[[:space:]]*:[[:space:]]*[1-9]|retryTimes\([1-9]|passWithNoTests|continue-on-error:[[:space:]]*true|(test|vitest|jest|playwright|phpunit|pest|pytest)[^#]*\|\|[[:space:]]*(true|exit 0)'

[ -z "$REASONS" ] && exit 0

MSG="test-guard: this edit to $FILE $REASONS. Allowed only with the user's explicit approval and a stated reason (why the test is wrong/flaky, and the tracking issue). If the test fails, investigate and fix the code or update the test to the changed contract instead."
jq -n --arg r "$MSG" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
exit 0
