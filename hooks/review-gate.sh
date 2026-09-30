#!/bin/bash
# PreToolUse (Bash) hook: right before a PR is opened, remind the agent of the
# mandatory review gate. Non-blocking — it injects context, the agent decides.
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

case "$CMD" in
  *"gh pr create"*)
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse", additionalContext:
      "REVIEW GATE (mandatory before this PR): confirm on the FULL diff — (a) code-reviewer ran once (skip only when the diff touches docs or UI copy only); (b) security-auditor ran once IF the diff touches API routes, webhooks, auth, permissions or security rules, admin pages, payments, or any path CLAUDE.md lists as security-sensitive; (c) npx tsc --noEmit is green. Run code-reviewer and security-auditor in parallel. If any is missing, cancel this PR, run it, then retry."}}'
    ;;
esac
exit 0
