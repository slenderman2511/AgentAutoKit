#!/bin/bash
# Log a pipeline event to .claude/metrics/events.jsonl (the proxy half of telemetry).
# The orchestrator calls this deterministically — it knows agent, model, and outcome.
#
# Usage:
#   kit-record.sh route agent=implementer model=sonnet task_type=feature
#   kit-record.sh escalation from=implementer to=deep-debugger task_type=bug
#   kit-record.sh review rounds=1
#   kit-record.sh verify pass=true
#
# Values are treated as strings unless they look like a number or true/false.
set -e
KIND="$1"; shift || true
[ -z "$KIND" ] && { echo "usage: kit-record.sh <kind> key=val..." >&2; exit 1; }

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MDIR="$ROOT/.claude/metrics"
mkdir -p "$MDIR"

JQ_ARGS=(--arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
         --arg session "${CLAUDE_SESSION_ID:-cli}" \
         --arg kind "$KIND")
FILTER='{ts:$ts, session:$session, kind:$kind}'
for kv in "$@"; do
  key="${kv%%=*}"; val="${kv#*=}"
  [ "$key" = "$kv" ] && continue           # skip args without '='
  if [[ "$val" =~ ^-?[0-9]+$ || "$val" == "true" || "$val" == "false" ]]; then
    FILTER="$FILTER + {\"$key\": $val}"     # numeric / boolean literal
  else
    JQ_ARGS+=(--arg "$key" "$val")
    FILTER="$FILTER + {\"$key\": \$$key}"
  fi
done

jq -c -n "${JQ_ARGS[@]}" "$FILTER" >> "$MDIR/events.jsonl"
