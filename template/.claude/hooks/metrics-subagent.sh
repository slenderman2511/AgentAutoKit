#!/bin/bash
# SubagentStop hook: measure speed + token cost of each subagent run.
# Reliable half of the telemetry — parsed straight from the session transcript.
# Never blocks; always exits 0.
set -o pipefail
INPUT=$(cat)

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')
SESSION=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

# Resolve metrics dir without sourcing (hook may run detached).
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MDIR="$ROOT/.claude/metrics"
mkdir -p "$MDIR"

# Cursor: only process transcript lines we haven't seen yet.
CUR="$MDIR/.cursor-$(basename "$TRANSCRIPT")"
LAST=$(cat "$CUR" 2>/dev/null || echo 0)
TOTAL=$(wc -l < "$TRANSCRIPT" | tr -d ' ')
[ "$TOTAL" -le "$LAST" ] && exit 0

# New sidechain (subagent) turns only, grouped by model → one record each.
tail -n +"$((LAST + 1))" "$TRANSCRIPT" \
  | jq -c 'select(.type=="assistant" and .isSidechain==true and (.message.model // "") != "<synthetic>")
           | {model:(.message.model),
              ts:(.timestamp | gsub("\\.[0-9]+Z$";"Z")),
              ti:(.message.usage.input_tokens // 0),
              to:(.message.usage.output_tokens // 0),
              cr:(.message.usage.cache_read_input_tokens // 0)}' \
  | jq -c -s --arg session "$SESSION" '
      group_by(.model)[]
      | {ts:(now|todateiso8601), session:$session, kind:"subagent",
         model:.[0].model,
         turns:length,
         tok_in:(map(.ti)|add), tok_out:(map(.to)|add), cache_read:(map(.cr)|add),
         duration_ms:(
           (map(.ts|fromdateiso8601)|max) - (map(.ts|fromdateiso8601)|min)
         ) * 1000 | floor
        }' 2>/dev/null \
  | while IFS= read -r rec; do
      [ -n "$rec" ] && printf '%s\n' "$rec" >> "$MDIR/events.jsonl"
    done

echo "$TOTAL" > "$CUR"
exit 0
