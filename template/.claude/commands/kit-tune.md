---
description: Propose (or apply) model-tier changes from the routing scorecard
argument-hint: [--apply]
allowed-tools: Bash(.claude/scripts/kit-stats.sh:*), Bash(.claude/scripts/kit-tune.sh:*), Read, Bash(git diff:*)
---
Auto-tune agent model tiers from measured performance. Thresholds live in
`.claude/metrics/tuning.json` (min samples, promote-below-fit, demote toggle).

1. Refresh the scorecard first:
   ```
   .claude/scripts/kit-stats.sh
   ```
2. Show the **dry-run** proposal (writes nothing):
   ```
   .claude/scripts/kit-tune.sh
   ```
3. Summarize the proposed promotions/demotions and the evidence (runs + fit).
4. Only if the user passed `--apply` (or confirms), run:
   ```
   .claude/scripts/kit-tune.sh --apply
   ```
   Then show `git diff` of the changed agent files so the human reviews before committing.

Never promote/demote without enough samples — the script enforces `min_samples`, but call it out if a proposal is based on thin data.
