#!/bin/bash
# Log a pipeline event to .claude/metrics/events.jsonl (the proxy half of telemetry).
# The orchestrator calls this deterministically — it knows agent, model, and outcome.
#
# Usage:
#   kit-record.sh route agent=implementer model=sonnet task_type=feature
#   kit-record.sh escalation from=implementer to=deep-debugger model=sonnet task_type=bug
#     (model = the tier the *from* agent was running when it escalated)
#   kit-record.sh review rounds=1
#   kit-record.sh verify pass=true
#
# Values are treated as strings unless they look like a number or true/false.
# Keys must match ^[A-Za-z_][A-Za-z0-9_]*$ — anything else is skipped, since
# the caller is an LLM and a malformed key would otherwise break the jq filter.
set -e
. "$(dirname "$0")/kit-metrics-lib.sh"

KIND="$1"; shift || true
[ -z "$KIND" ] && { echo "usage: kit-record.sh <kind> key=val..." >&2; exit 1; }

JQ_ARGS=(--arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
         --arg session "${CLAUDE_SESSION_ID:-cli}" \
         --arg kind "$KIND")
FILTER='{ts:$ts, session:$session, kind:$kind}'
for kv in "$@"; do
  key="${kv%%=*}"; val="${kv#*=}"
  [ "$key" = "$kv" ] && continue           # skip args without '='
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue  # skip unsafe keys
  if [[ "$val" =~ ^-?[0-9]+$ || "$val" == "true" || "$val" == "false" ]]; then
    FILTER="$FILTER + {\"$key\": $val}"     # numeric / boolean literal
  else
    JQ_ARGS+=(--arg "$key" "$val")
    FILTER="$FILTER + {\"$key\": \$$key}"
  fi
done

kit_append_event "$(jq -c -n "${JQ_ARGS[@]}" "$FILTER")"
