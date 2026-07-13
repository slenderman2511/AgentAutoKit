---
description: Propose (or apply) model-tier changes from the routing scorecard
argument-hint: [--apply]
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kit-stats.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kit-tune.sh:*), Read, Bash(git diff:*)
---
Auto-tune agent model tiers from measured performance. Thresholds live in
`.claude/metrics/tuning.json` (min samples, promote-below-fit, demote toggle).

1. Refresh the scorecard first:
   ```
   "${CLAUDE_PLUGIN_ROOT}"/scripts/kit-stats.sh
   ```
2. Show the **dry-run** proposal (writes nothing):
   ```
   "${CLAUDE_PLUGIN_ROOT}"/scripts/kit-tune.sh --agents-dir "$CLAUDE_PROJECT_DIR/.claude/agents"
   ```
3. Summarize the proposed promotions/demotions and the evidence (runs + fit).
4. Only if the user passed `--apply` (or confirms), run:
   ```
   "${CLAUDE_PLUGIN_ROOT}"/scripts/kit-tune.sh --apply --agents-dir "$CLAUDE_PROJECT_DIR/.claude/agents"
   ```
   Then show `git diff` of the changed agent files so the human reviews before committing.

Never promote/demote without enough samples — the script enforces `min_samples`, but call it out if a proposal is based on thin data.
