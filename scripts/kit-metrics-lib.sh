#!/bin/bash
# Shared helpers for AgentAutoKit metrics. Source this; do not run directly.
# All metrics live under <main checkout>/.claude/metrics/ and are git-ignored runtime data.

# The repo's MAIN checkout, even when called from a linked worktree. Metrics are
# anchored there so every worktree appends to one events.jsonl: a worktree is
# removed after its PR merges, and data kept inside it would go with it.
# Outside git (or in a submodule / bare layout) this is the project dir itself.
kit_main_root() {
  local root="${CLAUDE_PROJECT_DIR:-$(pwd)}" common
  common=$(git -C "$root" rev-parse --git-common-dir 2>/dev/null) || { echo "$root"; return; }
  case "$common" in /*) ;; *) common="$root/$common" ;; esac
  if [ "$(basename "$common")" = ".git" ] && [ -d "$common" ]; then
    (cd "$(dirname "$common")" && pwd -P)
  else
    echo "$root"
  fi
}

kit_metrics_dir() { echo "$(kit_main_root)/.claude/metrics"; }

# Create a metrics dir that git ignores from the inside. A plugin install writes
# into projects whose .gitignore never heard of .claude/metrics/, and a
# "stage everything" commit would otherwise sweep the log into the repo.
# Usage: kit_ensure_dir <dir>   (returns non-zero if the dir cannot be created)
kit_ensure_dir() {
  mkdir -p "$1" 2>/dev/null || return 1
  [ -f "$1/.gitignore" ] || printf '*\n' > "$1/.gitignore" 2>/dev/null
  return 0
}

kit_events_file() { echo "$(kit_metrics_dir)/events.jsonl"; }

# Append one JSON event line. Usage: kit_append_event '<json object string>'
kit_append_event() {
  local dir; dir="$(kit_metrics_dir)"
  kit_ensure_dir "$dir" || return 0
  printf '%s\n' "$1" >> "$dir/events.jsonl"
}

# The model: line of an agent file, read from its frontmatter block only.
# A file that does not open with "---" has no frontmatter: no model.
kit_agent_model() {
  [ -f "$1" ] || { echo ""; return; }
  sed -n -e '1{/^---[[:space:]]*$/!q;}' -e '1,/^---$/{s/^model:[[:space:]]*//p;}' "$1" \
    | head -1 | tr -d '\r'
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

# Canonical model for a tier rank (used when rewriting frontmatter).
# All tiers are pinned model IDs so a promotion keeps the kit's pinning policy.
kit_rank_alias() {
  case "$1" in
    1) echo claude-haiku-5-5 ;;
    2) echo claude-sonnet-5-5 ;;
    3) echo claude-opus-5-5 ;;
    *) echo "" ;;
  esac
}
