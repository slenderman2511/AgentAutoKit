#!/bin/bash
# Shared helpers for AgentAutoKit metrics. Source this; do not run directly.
# All metrics live under $PROJECT/.claude/metrics/ and are git-ignored runtime data.

kit_metrics_dir() {
  local root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  echo "$root/.claude/metrics"
}

kit_events_file() { echo "$(kit_metrics_dir)/events.jsonl"; }

# Append one JSON event line. Usage: kit_append_event '<json object string>'
kit_append_event() {
  local dir; dir="$(kit_metrics_dir)"
  mkdir -p "$dir"
  printf '%s\n' "$1" >> "$dir/events.jsonl"
}

# Ordinal rank of a model tier, for ladder comparisons. Accepts aliases or pinned ids.
kit_model_rank() {
  case "$1" in
    *haiku*)  echo 1 ;;
    *sonnet*) echo 2 ;;
    *opus*)   echo 3 ;;
    *)        echo 0 ;;   # unknown / synthetic
  esac
}

# Canonical alias for a tier rank (used when rewriting frontmatter).
kit_rank_alias() {
  case "$1" in
    1) echo haiku ;;
    2) echo sonnet ;;
    3) echo opus ;;
    *) echo "" ;;
  esac
}
