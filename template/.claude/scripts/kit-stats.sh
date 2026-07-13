#!/bin/bash
# Aggregate .claude/metrics/events.jsonl into a scorecard (JSON + Markdown).
#   - Per model : throughput + token cost (measured from the transcript)
#   - Per agent : fit score from escalation rate (pipeline proxy)
#   - Global    : verify first-pass rate, avg review rounds
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
#   {"haiku":{"in":1,"out":5},"sonnet":{"in":3,"out":15},"opus":{"in":15,"out":75}}
PRICING="$MDIR/pricing.json"
DEFAULT_PRICING='{"haiku":{"in":1,"out":5},"sonnet":{"in":3,"out":15},"opus":{"in":15,"out":75}}'
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
        | (map(.tok_in)  | add) as $ti
        | (map(.tok_out) | add) as $to
        | (map(.duration_ms)) as $durs
        | {
            model: $m,
            records: length,
            tok_in: $ti, tok_out: $to,
            dur_p50_ms: ($durs | pct(0.50)),
            dur_p95_ms: ($durs | pct(0.95)),
            est_cost_usd: (
              (($rates[$t].in  // 0) * $ti / 1000000)
              + (($rates[$t].out // 0) * $to / 1000000)
            ) * 100 | round | . / 100
          }
      )
    ),

    agents: (
      ([ .[] | select(.kind=="route") ]) as $routes
      | ([ .[] | select(.kind=="escalation") ]) as $esc
      | ($routes | map(.agent) | unique) as $names
      | $names | map(
          . as $a
          | ($routes | map(select(.agent==$a)) | length) as $runs
          | ($esc | map(select(.from==$a)) | length) as $e
          | {
              agent: $a,
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

# Render Markdown.
{
  echo "# AgentAutoKit routing scorecard"
  echo
  echo "_Generated: $(echo "$JSON" | jq -r '.generated_at')_"
  echo
  echo "## Models — speed & cost"
  echo
  echo "| Model | Runs | p50 dur (s) | p95 dur (s) | Tok in | Tok out | Est. cost (USD) |"
  echo "|-------|-----:|------------:|------------:|-------:|--------:|----------------:|"
  echo "$JSON" | jq -r '.models[] | "| \(.model) | \(.records) | \((.dur_p50_ms/1000*10|round)/10) | \((.dur_p95_ms/1000*10|round)/10) | \(.tok_in) | \(.tok_out) | \(.est_cost_usd) |"'
  echo
  echo "## Agents — fit score (1.0 = never escalated)"
  echo
  echo "| Agent | Runs | Escalations | Escalation rate | Fit score |"
  echo "|-------|-----:|------------:|----------------:|----------:|"
  echo "$JSON" | jq -r '.agents[] | "| \(.agent) | \(.runs) | \(.escalations) | \(.escalation_rate) | \(.fit_score // "n/a") |"'
  echo
  echo "## Pipeline health"
  echo
  echo "$JSON" | jq -r '.global | "- Verify first-pass rate: \(if .verify_pass_rate==null then "n/a" else "\(.verify_pass_rate) (\(.verify_pass)/\(.verify_total))" end)\n- Avg review rounds: \(.review_avg_rounds // "n/a")"'
  echo
  echo "> Prices are placeholders in \`.claude/metrics/pricing.json\` — set your real per-model rates."
} > "$MDIR/scorecard.md"

cat "$MDIR/scorecard.md"
