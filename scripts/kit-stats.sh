#!/bin/bash
# Aggregate .claude/metrics/events.jsonl into a scorecard (JSON + Markdown).
#   - Per model          : throughput + token cost (measured from the transcript)
#   - Per (agent, tier)  : fit score from escalation rate (pipeline proxy)
#   - Global             : verify first-pass rate, avg review rounds
# Fit is grouped by the tier the agent was running at the time, so history
# from before a promotion/demotion never pollutes the current tier's score.
# Usage: kit-stats.sh          (writes scorecard.{json,md}, prints the Markdown)
set -e
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MDIR="$ROOT/.claude/metrics"
EVENTS="$MDIR/events.jsonl"

if [ ! -s "$EVENTS" ]; then
  echo "No metrics yet at $EVENTS — run some /init-kit tasks first." >&2
  exit 0
fi

# Token prices (USD per 1M tokens). Override with .claude/metrics/pricing.json:
#   {"haiku":{"in":1,"out":5,"cache_read":0.1,"cache_write":1.25}, ...}
# cache_read / cache_write default to 0.1x / 1.25x of "in" when omitted, so an
# older pricing.json without cache rates keeps working.
PRICING="$MDIR/pricing.json"
DEFAULT_PRICING='{
  "haiku":  {"in": 1,  "out": 5,  "cache_read": 0.1, "cache_write": 1.25},
  "sonnet": {"in": 3,  "out": 15, "cache_read": 0.3, "cache_write": 3.75},
  "opus":   {"in": 15, "out": 75, "cache_read": 1.5, "cache_write": 18.75}
}'
RATES=$([ -f "$PRICING" ] && cat "$PRICING" || echo "$DEFAULT_PRICING")

JSON=$(jq -c -s --argjson rates "$RATES" '
  def pct(p): if length==0 then 0 else (sort as $s | $s[ ((length-1)*p) | floor ]) end;
  def tier: if test("haiku") then "haiku" elif test("sonnet") then "sonnet" elif test("opus") then "opus" else "other" end;

  {
    generated_at: (now|todateiso8601),

    models: (
      [ .[] | select(.kind=="subagent") ] | group_by(.model) | map(
        (.[0].model) as $m
        | ($m | tier) as $t
        | (map(.tok_in // 0)      | add) as $ti
        | (map(.tok_out // 0)     | add) as $to
        | (map(.cache_read // 0)  | add) as $cr
        | (map(.cache_write // 0) | add) as $cw
        | (map(.duration_ms)) as $durs
        | {
            model: $m,
            records: length,
            tok_in: $ti, tok_out: $to,
            cache_read: $cr, cache_write: $cw,
            dur_p50_ms: ($durs | pct(0.50)),
            dur_p95_ms: ($durs | pct(0.95)),
            est_cost_usd: (((
              (($rates[$t].in  // 0) * $ti / 1000000)
              + (($rates[$t].out // 0) * $to / 1000000)
              + (($rates[$t].cache_read  // (($rates[$t].in // 0) * 0.1))  * $cr / 1000000)
              + (($rates[$t].cache_write // (($rates[$t].in // 0) * 1.25)) * $cw / 1000000)
            ) * 100 | round) / 100)
          }
      )
    ),

    agents: (
      ([ .[] | select(.kind=="route") ]) as $routes
      # Escalations recorded without a model (older data) inherit the model of
      # the latest earlier route for the same agent in the same session.
      | ([ .[] | select(.kind=="escalation")
           | . as $e
           | .model = (.model // (
               [ $routes[] | select(.agent==$e.from and .session==$e.session and .ts <= $e.ts) ]
               | sort_by(.ts) | last | .model // "unknown"
             ))
         ]) as $esc
      | ($routes | group_by([.agent, (.model // "unknown")])) as $groups
      | $groups | map(
          (.[0].agent) as $a
          | ((.[0].model) // "unknown") as $m
          | length as $runs
          | ($esc | map(select(.from==$a and .model==$m)) | length) as $e
          | {
              agent: $a,
              model: $m,
              runs: $runs,
              escalations: $e,
              escalation_rate: (if $runs==0 then 0 else (($e/$runs)*100|round)/100 end),
              fit_score: (if $runs==0 then null else (((1 - $e/$runs)*100|round)/100) end)
            }
        )
    ),

    global: (
      ([ .[] | select(.kind=="verify") ]) as $v
      | ([ .[] | select(.kind=="review") ]) as $r
      | {
          verify_total: ($v|length),
          verify_pass: ($v | map(select(.pass==true)) | length),
          verify_pass_rate: (if ($v|length)==0 then null else (($v|map(select(.pass==true))|length) / ($v|length) * 100 | round)/100 end),
          review_avg_rounds: (if ($r|length)==0 then null else ((($r|map(.rounds)|add) / ($r|length))*100|round)/100 end)
        }
    )
  }
' "$EVENTS")

echo "$JSON" > "$MDIR/scorecard.json"

# A plugin-only install ships the SubagentStop hook but not the orchestrator
# route logging — flag it so an empty Agents table is not mistaken for a bug.
MODELS_N=$(echo "$JSON" | jq '.models | length')
AGENTS_N=$(echo "$JSON" | jq '.agents | length')
ROUTE_WARN=""
if [ "$MODELS_N" -gt 0 ] && [ "$AGENTS_N" -eq 0 ]; then
  ROUTE_WARN="> **No route/escalation events found.** Model speed/cost is being measured, but per-agent fit needs the orchestrator to call \`kit-record.sh\` (template install carries it in \`.claude/scripts/\`). Without it, \`/kit-tune\` has nothing to act on."
  echo "warning: subagent events exist but no route events — orchestrator logging is not reaching kit-record.sh" >&2
fi

# Render Markdown.
{
  echo "# AgentAutoKit routing scorecard"
  echo
  echo "_Generated: $(echo "$JSON" | jq -r '.generated_at')_"
  echo
  echo "## Models — speed & cost"
  echo
  echo "| Model | Runs | p50 dur (s) | p95 dur (s) | Tok in | Tok out | Cache read | Cache write | Est. cost (USD) |"
  echo "|-------|-----:|------------:|------------:|-------:|--------:|-----------:|------------:|----------------:|"
  echo "$JSON" | jq -r '.models[] | "| \(.model) | \(.records) | \((.dur_p50_ms/1000*10|round)/10) | \((.dur_p95_ms/1000*10|round)/10) | \(.tok_in) | \(.tok_out) | \(.cache_read) | \(.cache_write) | \(.est_cost_usd) |"'
  echo
  echo "## Agents — fit score per tier (1.0 = never escalated)"
  echo
  echo "| Agent | Tier | Runs | Escalations | Escalation rate | Fit score |"
  echo "|-------|------|-----:|------------:|----------------:|----------:|"
  echo "$JSON" | jq -r '.agents[] | "| \(.agent) | \(.model) | \(.runs) | \(.escalations) | \(.escalation_rate) | \(.fit_score // "n/a") |"'
  echo
  echo "## Pipeline health"
  echo
  echo "$JSON" | jq -r '.global | "- Verify first-pass rate: \(if .verify_pass_rate==null then "n/a" else "\(.verify_pass_rate) (\(.verify_pass)/\(.verify_total))" end)\n- Avg review rounds: \(.review_avg_rounds // "n/a")"'
  echo
  if [ -n "$ROUTE_WARN" ]; then
    echo "$ROUTE_WARN"
    echo
  fi
  echo "> Prices are placeholders in \`.claude/metrics/pricing.json\` — set your real per-model rates."
} > "$MDIR/scorecard.md"

cat "$MDIR/scorecard.md"
