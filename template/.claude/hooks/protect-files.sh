#!/bin/bash
# PreToolUse hook: block edits to protected files.
# Exit 2 = block (stderr is fed back to Claude). Exit 0 = allow.
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[ -z "$FILE" ] && exit 0

case "$FILE" in
  *.env|*.env.*|*.pem|*.key|\
  secrets/*|*/secrets/*|\
  .github/workflows/*|*/.github/workflows/*|\
  migrations/*|*/migrations/*)
    echo "Blocked: '$FILE' is a protected path (secrets/CI/migrations). Edit it manually if intended." >&2
    exit 2
    ;;
esac
exit 0
