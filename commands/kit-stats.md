---
description: Summarize AgentAutoKit run metrics into a routing scorecard
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kit-stats.sh:*), Read
---
Generate the routing scorecard from collected metrics.

Run:
```
"${CLAUDE_PLUGIN_ROOT}"/scripts/kit-stats.sh
```

Then read `.claude/metrics/scorecard.md` and give the user a short read:
- Which model is fastest / cheapest per run.
- Any agent whose fit score is low (escalates often) — a candidate for a higher tier.
- Overall verify first-pass rate and average review rounds (pipeline health).
Do not change any agent config here — that is `/kit-tune`'s job.
