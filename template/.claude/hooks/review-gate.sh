#!/bin/bash
# Bash hook around `gh pr create`. Never blocks.
#   PreToolUse  — remind the agent of the mandatory review gate (injects context).
#   PostToolUse — once the PR exists, log a "pr" event; kit-stats counts the
#                 code-reviewer runs before it as that PR's review rounds.
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
case "$CMD" in *"gh pr create"*) ;; *) exit 0 ;; esac

if [ "$(echo "$INPUT" | jq -r '.hook_event_name // empty')" = "PostToolUse" ]; then
  # Only a PR URL on stdout proves the PR was created: a failed attempt prints
  # none, and "already exists" names the old PR on stderr. kit-stats also
  # counts each URL once.
  URL=$(echo "$INPUT" | jq -r '.tool_response | if type == "object" then (.stdout // "") else tostring end' \
    | grep -oE 'https://github\.com/[^/[:space:]"]+/[^/[:space:]"]+/pull/[0-9]+' | head -1)
  [ -n "$URL" ] || exit 0
  LIB="$(dirname "$0")/../scripts/kit-metrics-lib.sh"
  [ -f "$LIB" ] || exit 0
  . "$LIB"
  kit_append_event "$(jq -c -n --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg session "$(echo "$INPUT" | jq -r '.session_id // "unknown"')" --arg url "$URL" \
    '{ts:$ts, session:$session, kind:"pr", url:$url}')" 2>/dev/null
  exit 0
fi

jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse", additionalContext:
  "REVIEW GATE (mandatory before this PR): confirm on the FULL diff — (a) code-reviewer ran once (skip only when the diff touches docs or UI copy only); (b) security-auditor ran once IF the diff touches API routes, webhooks, auth, permissions or security rules, admin pages, payments, or any path CLAUDE.md lists as security-sensitive; (c) api-data-reviewer ran once IF the diff touches API routes, a persisted data type/schema, index definitions, or adds a collection/table/field/query; (d) npx tsc --noEmit is green. Run the applicable reviewers in parallel. If any is missing, cancel this PR, run it, then retry."}}'
exit 0
