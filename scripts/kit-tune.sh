#!/bin/bash
# Threshold-based auto-tuning of agent model tiers from the scorecard.
# Promotes an agent up the ladder (haiku < sonnet < opus) when it escalates too
# often, and (optionally) demotes an over-provisioned one. Dry-run by default.
#
# Usage:
#   kit-tune.sh                 # show proposed changes, write nothing
#   kit-tune.sh --apply         # edit agent frontmatter + log the decision
#   kit-tune.sh --agents-dir DIR
#
# Thresholds live in .claude/metrics/tuning.json (defaults below).
set -e
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MDIR="$ROOT/.claude/metrics"
SCORE="$MDIR/scorecard.json"
AGENTS_DIR="$ROOT/.claude/agents"
APPLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --agents-dir) AGENTS_DIR="$2"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

[ -f "$SCORE" ] || { echo "No scorecard. Run kit-stats.sh first." >&2; exit 1; }

CFG="$MDIR/tuning.json"
DEFAULT_CFG='{"min_samples":20,"promote_if_fit_below":0.6,"enable_demote":false,"demote_if_fit_above":0.97}'
CONF=$([ -f "$CFG" ] && cat "$CFG" || echo "$DEFAULT_CFG")
MIN=$(echo "$CONF"     | jq -r '.min_samples // 20')
PROMOTE=$(echo "$CONF" | jq -r '.promote_if_fit_below // 0.6')
DEMOTE_ON=$(echo "$CONF"| jq -r '.enable_demote // false')
DEMOTE=$(echo "$CONF"  | jq -r '.demote_if_fit_above // 0.97')

rank() { case "$1" in *haiku*) echo 1;; *sonnet*) echo 2;; *opus*) echo 3;; *) echo 0;; esac; }
alias_of() { case "$1" in 1) echo haiku;; 2) echo sonnet;; 3) echo opus;; *) echo "";; esac; }
model_of() {  # read current model: line from an agent file
  local f="$AGENTS_DIR/$1.md"
  [ -f "$f" ] && grep -m1 '^model:' "$f" | sed 's/^model:[[:space:]]*//' | tr -d '\r' || echo ""
}

CHANGES=0
echo "AgentAutoKit auto-tune (min_samples=$MIN, promote<$PROMOTE, demote=$DEMOTE_ON)"
echo "agents dir: $AGENTS_DIR"
echo

while IFS=$'\t' read -r agent runs fit; do
  [ -z "$agent" ] && continue
  cur=$(model_of "$agent"); [ -z "$cur" ] && continue
  cr=$(rank "$cur"); [ "$cr" -eq 0 ] && continue

  new_rank=""
  reason=""
  if [ "$runs" -ge "$MIN" ] && awk "BEGIN{exit !($fit < $PROMOTE)}" && [ "$cr" -lt 3 ]; then
    new_rank=$((cr + 1)); reason="fit $fit < $PROMOTE over $runs runs → promote"
  elif [ "$DEMOTE_ON" = "true" ] && [ "$runs" -ge "$MIN" ] && awk "BEGIN{exit !($fit >= $DEMOTE)}" && [ "$cr" -gt 1 ]; then
    new_rank=$((cr - 1)); reason="fit $fit ≥ $DEMOTE over $runs runs → demote"
  fi

  if [ -n "$new_rank" ]; then
    new_alias=$(alias_of "$new_rank")
    echo "  $agent: $cur → $new_alias   ($reason)"
    CHANGES=$((CHANGES + 1))
    if [ "$APPLY" -eq 1 ]; then
      f="$AGENTS_DIR/$agent.md"
      sed -i.bak "s/^model:.*/model: $new_alias/" "$f" && rm -f "$f.bak"
      printf '%s\t%s\t%s → %s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$agent" "$cur" "$new_alias" "$reason" \
        >> "$MDIR/tuning-log.md"
    fi
  else
    echo "  $agent: keep $cur   (runs=$runs, fit=$fit)"
  fi
done < <(jq -r '.agents[] | select(.fit_score != null) | [.agent, .runs, .fit_score] | @tsv' "$SCORE")

echo
if [ "$CHANGES" -eq 0 ]; then
  echo "No changes proposed."
elif [ "$APPLY" -eq 1 ]; then
  echo "Applied $CHANGES change(s). Logged to $MDIR/tuning-log.md. Review the diff before committing."
else
  echo "$CHANGES change(s) proposed. Re-run with --apply to write them."
fi
