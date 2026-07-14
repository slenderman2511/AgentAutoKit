#!/bin/bash
# Threshold-based auto-tuning of agent model tiers from the scorecard.
# Promotes an agent up the ladder (haiku < sonnet < opus) when it escalates too
# often, and (optionally) demotes an over-provisioned one. Dry-run by default.
#
# Only the scorecard row matching the agent's CURRENT tier is considered, so
# history from before a promotion never triggers a second promotion on its own.
# Demotion additionally requires the agent to have at least one escalation on
# record at any tier — an agent with no escalation path (scout, reviewer, ...)
# has a fit score pinned at 1.0, which says nothing about over-provisioning.
#
# Usage:
#   kit-tune.sh                 # show proposed changes, write nothing
#   kit-tune.sh --apply         # edit agent frontmatter + log the decision
#   kit-tune.sh --agents-dir DIR
#
# Thresholds live in .claude/metrics/tuning.json (defaults below).
set -e
. "$(dirname "$0")/kit-metrics-lib.sh"

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MDIR="$ROOT/.claude/metrics"
SCORE="$MDIR/scorecard.json"
AGENTS_DIR="$ROOT/.claude/agents"
APPLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --agents-dir) AGENTS_DIR="$2"; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
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

model_of() {  # read the model: line from an agent file's frontmatter block only
  local f="$AGENTS_DIR/$1.md"
  [ -f "$f" ] || { echo ""; return; }
  sed -n '1,/^---$/{s/^model:[[:space:]]*//p;}' "$f" | head -1 | tr -d '\r'
}

CHANGES=0
echo "AgentAutoKit auto-tune (min_samples=$MIN, promote<$PROMOTE, demote=$DEMOTE_ON)"
echo "agents dir: $AGENTS_DIR"
echo

# Rows: agent, tier the runs happened on, runs, fit at that tier,
# plus total escalations for the agent across ALL tiers (demote guard).
while IFS=$'\t' read -r agent tier runs fit total_esc; do
  [ -z "$agent" ] && continue
  cur=$(model_of "$agent"); [ -z "$cur" ] && continue
  cr=$(kit_model_rank "$cur"); [ "$cr" -eq 0 ] && continue

  # Ignore rows from a tier the agent is no longer on (pre-promotion history).
  tr_rank=$(kit_model_rank "$tier")
  [ "$tr_rank" -eq "$cr" ] || continue

  new_rank=""
  reason=""
  if [ "$runs" -ge "$MIN" ] && awk "BEGIN{exit !($fit < $PROMOTE)}" && [ "$cr" -lt 3 ]; then
    new_rank=$((cr + 1)); reason="fit $fit < $PROMOTE over $runs runs on $tier → promote"
  elif [ "$DEMOTE_ON" = "true" ] && [ "$runs" -ge "$MIN" ] && awk "BEGIN{exit !($fit >= $DEMOTE)}" && [ "$cr" -gt 1 ]; then
    if [ "$total_esc" -gt 0 ]; then
      new_rank=$((cr - 1)); reason="fit $fit ≥ $DEMOTE over $runs runs on $tier → demote"
    else
      echo "  $agent: keep $cur   (fit $fit but no escalation signal ever — demote skipped)"
      continue
    fi
  fi

  if [ -n "$new_rank" ]; then
    new_alias=$(kit_rank_alias "$new_rank")
    echo "  $agent: $cur → $new_alias   ($reason)"
    CHANGES=$((CHANGES + 1))
    if [ "$APPLY" -eq 1 ]; then
      f="$AGENTS_DIR/$agent.md"
      # Anchor the edit to the frontmatter block so a "model:" line in the
      # agent's markdown body can never be rewritten by accident.
      sed -i.bak "1,/^---\$/s/^model:.*/model: $new_alias/" "$f" && rm -f "$f.bak"
      printf '%s\t%s\t%s → %s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$agent" "$cur" "$new_alias" "$reason" \
        >> "$MDIR/tuning-log.md"
    fi
  else
    echo "  $agent: keep $cur   (runs=$runs, fit=$fit)"
  fi
done < <(jq -r '
  .agents as $rows
  | $rows[] | select(.fit_score != null) | . as $r
  | [ $r.agent, ($r.model // "unknown"), $r.runs, $r.fit_score,
      ([ $rows[] | select(.agent == $r.agent) | .escalations ] | add) ]
  | @tsv' "$SCORE")

echo
if [ "$CHANGES" -eq 0 ]; then
  echo "No changes proposed."
elif [ "$APPLY" -eq 1 ]; then
  echo "Applied $CHANGES change(s). Logged to $MDIR/tuning-log.md. Review the diff before committing."
else
  echo "$CHANGES change(s) proposed. Re-run with --apply to write them."
fi
