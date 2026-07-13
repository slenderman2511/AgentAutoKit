#!/bin/bash
# AgentAutoKit status line: shows the model, git branch, and any subagents
# currently running (a Task tool_use with no matching tool_result yet).
# Claude Code feeds session JSON on stdin and renders whatever we print.
set -o pipefail
INPUT=$(cat)

MODEL=$(echo "$INPUT" | jq -r '.model.display_name // .model.id // "?"')
CWD=$(echo "$INPUT" | jq -r '.workspace.current_dir // .cwd // "."')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')

DIR=$(basename "$CWD")
BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null)

# ANSI (dim/color). Disabled automatically if stdout is not a terminal-ish sink.
C_DIM=$'\033[2m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RESET=$'\033[0m'

ACTIVE=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  # Task launches (id → subagent_type) minus completed tool_use_ids = still running.
  TASKS=$(grep -F '"name":"Task"' "$TRANSCRIPT" 2>/dev/null \
    | jq -r '.message.content[]? | select(.type=="tool_use" and .name=="Task")
             | "\(.id)\t\(.input.subagent_type // "agent")"' 2>/dev/null)
  if [ -n "$TASKS" ]; then
    DONE=$(grep -F '"tool_use_id"' "$TRANSCRIPT" 2>/dev/null \
      | jq -r '.message.content[]? | select(.type=="tool_result") | .tool_use_id' 2>/dev/null | sort -u)
    while IFS=$'\t' read -r id name; do
      [ -z "$id" ] && continue
      printf '%s\n' "$DONE" | grep -qx "$id" || ACTIVE="$ACTIVE ${name}"
    done <<< "$TASKS"
    ACTIVE=$(echo "$ACTIVE" | tr ' ' '\n' | grep -v '^$' | sort | uniq -c \
      | awk '{ if ($1>1) printf "%s×%s ", $2, $1; else printf "%s ", $2 }' | sed 's/ $//')
  fi
fi

LINE="${C_CYAN}▸ ${MODEL}${C_RESET}  ${C_DIM}${DIR}${C_RESET}"
[ -n "$BRANCH" ] && LINE="$LINE  ${C_DIM}⎇ ${BRANCH}${C_RESET}"
if [ -n "$ACTIVE" ]; then
  LINE="$LINE  ${C_GREEN}🤖 ${ACTIVE}${C_RESET}"
else
  LINE="$LINE  ${C_DIM}·idle·${C_RESET}"
fi
printf '%s' "$LINE"
