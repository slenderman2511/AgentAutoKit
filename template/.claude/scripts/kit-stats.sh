#!/bin/bash
# Aggregate .claude/metrics/events.jsonl into a scorecard (JSON + Markdown).
#   - Per model          : throughput + token cost (measured from the transcript)
#   - Per (agent, tier)  : fit score from escalation rate (pipeline proxy)
#   - Global             : verify first-pass rate, review rounds per PR
# Fit is grouped by the tier the agent was running at the time, so history
# from before a promotion/demotion never pollutes the current tier's score.
# Escalations and review rounds come from kit-record.sh when the orchestrator
# logs them; otherwise they are derived from the order of runs in a session
# (implementer → deep-debugger; code-reviewer runs before each opened PR).
# Usage: kit-stats.sh          (writes scorecard.{json,md}, prints the Markdown)
set -e
. "$(dirname "$0")/kit-metrics-lib.sh"
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MDIR="$(kit_metrics_dir)"   # the main checkout's, shared by every worktree
EVENTS="$MDIR/events.jsonl"

if [ ! -s "$EVENTS" ]; then
  echo "No metrics yet at $EVENTS — run some /init-kit tasks first." >&2
  exit 0
fi

# Token prices (USD per 1M tokens). Override with .claude/metrics/pricing.json:
#   {"haiku":{"in":1,"out":5,"cache_read":0.1,"cache_write":1.25}, ...}
# cache_read / cache_write default to 0.1x / 1.25x of "in" when omitted, so an
# older pricing.json without cache rates keeps working.
# Defaults match the pinned models: Haiku 4.5, Sonnet 5.5, Opus 5.5 (Opus 5.5
# cache reads are 0.05x of "in", not the usual 0.1x).
PRICING="$MDIR/pricing.json"
DEFAULT_PRICING='{
  "haiku":  {"in": 1, "out": 5,  "cache_read": 0.1, "cache_write": 1.25},
  "sonnet": {"in": 2, "out": 10, "cache_read": 0.2, "cache_write": 2.5},
  "opus":   {"in": 4, "out": 20, "cache_read": 0.2, "cache_write": 5}
}'
RATES=$([ -f "$PRICING" ] && cat "$PRICING" || echo "$DEFAULT_PRICING")

# Pinned model per kit agent: the kit's own agents (../agents next to this
# script, i.e. the plugin root or .claude/), overridden by the project's
# .claude/agents. Only these agents get a fit row; any other subagent
# (Explore, other plugins' agents) still counts toward per-model cost.
PINS='{}'
for d in "$(dirname "$0")/../agents" "$ROOT/.claude/agents"; do
  for f in "$d"/*.md; do
    [ -f "$f" ] || continue
    m=$(kit_agent_model "$f"); [ -n "$m" ] || continue
    PINS=$(jq -c --arg a "$(basename "$f" .md)" --arg m "$m" '. + {($a): $m}' <<<"$PINS")
  done
done

JSON=$(jq -c -s --argjson rates "$RATES" --argjson pins "$PINS" '
  def pct(p): if length==0 then null else (sort as $s | $s[ ((length-1)*p) | floor ]) end;
  def tier: if test("haiku") then "haiku" elif test("sonnet") then "sonnet" elif test("opus") then "opus" else "other" end;
  def kit_agent: ($pins | length) == 0 or $pins[.] != null;
  def not_in($sessions): .session as $s | $sessions | index($s) | not;

  # Chronological; sort_by is stable, so same-second events keep append order.
  (sort_by(.ts)) as $ev
  | ([ $ev[] | select(.kind=="subagent" and (.agent // null) != null) ]) as $tagged

  # A run is either a route logged by the orchestrator (older data) or a
  # subagent record the SubagentStop hook tagged with its agent_type. Models
  # are normalized to a tier so pinned IDs (claude-sonnet-5-5) and aliases
  # (sonnet) score in the same bucket.
  | ([ $ev[] | select(.kind=="route" or (.kind=="subagent" and (.agent // null) != null))
         | select(.agent | kit_agent)
         | .model = ((.model // "unknown") | tier) ]) as $routes

  # Escalations logged by the orchestrator (kit-record.sh). Older records
  # without a model inherit the latest earlier route of that agent.
  | ([ $ev[] | select(.kind=="escalation")
         | . as $e
         | .model = ((.model // (
             [ $routes[] | select(.agent==$e.from and .session==$e.session and .ts <= $e.ts) ]
             | last | .model // "unknown"
           )) | tier)
       ]) as $esc_logged
  | ([ $esc_logged[] | .session ] | unique) as $esc_sessions
  # Sessions with nothing logged: derive escalations from run order. An
  # implementer run counts as escalated when deep-debugger runs after it,
  # before the next implementer run of the same session.
  | ([ [ $tagged[] | select(not_in($esc_sessions)) ]
       | group_by(.session)[]
       | . as $runs
       | [ $runs[] | select(.agent=="implementer") ] as $imps
       | range(0; $imps | length) as $i
       | $imps[$i] as $run
       | (if $i + 1 < ($imps | length) then $imps[$i + 1].ts else "9999" end) as $next
       | select(any($runs[]; .agent=="deep-debugger" and .ts > $run.ts and .ts <= $next))
       | {kind: "escalation", from: "implementer", to: "deep-debugger",
          model: ($run.model | tier), session: $run.session, ts: $run.ts, derived: true}
     ]) as $esc_derived
  | ($esc_logged + $esc_derived) as $esc

  # Review rounds logged by the orchestrator (kit-record.sh review rounds=n).
  | ([ $ev[] | select(.kind=="review") ]) as $rev_logged
  | ([ $rev_logged[] | .session ] | unique) as $rev_sessions
  # Sessions with nothing logged: the rounds of each opened PR (a "pr" event
  # from review-gate.sh, first one per URL) are the code-reviewer runs since
  # the previous PR of the same session; 0 means it was opened without one.
  | (reduce ($ev[] | select(.kind=="pr")) as $p ({seen: {}, list: []};
       ($p.url // "\($p.session) \($p.ts)") as $k
       | if .seen[$k] then . else .seen[$k] = true | .list += [$p] end)
     | .list) as $pr_first
  | ([ [ ($ev[] | select(.kind=="subagent" and .agent=="code-reviewer")), $pr_first[]
       | select(not_in($rev_sessions)) ]
       # same second: the review ran before the PR it gated
       | sort_by(.ts, (if .kind=="pr" then 1 else 0 end))
       | group_by(.session)[]
       | foreach .[] as $e ({n: 0, out: null};
           if $e.kind=="pr" then {n: 0, out: {rounds: .n, url: $e.url}}
           else {n: (.n + 1), out: null} end;
           .out | select(. != null))
     ]) as $prs
  # Average over reviewed PRs only; unreviewed ones are counted separately.
  | ([ $rev_logged[] | .rounds | numbers | select(. > 0) ]
     + [ $prs[] | select(.rounds > 0) | .rounds ]) as $rounds

  | {
    generated_at: (now|todateiso8601),

    models: (
      [ $ev[] | select(.kind=="subagent") ] | group_by(.model) | map(
        (.[0].model) as $m
        | ($m | tier) as $t
        | (map(.tok_in // 0)      | add) as $ti
        | (map(.tok_out // 0)     | add) as $to
        | (map(.cache_read // 0)  | add) as $cr
        | (map(.cache_write // 0) | add) as $cw
        | (map(.duration_ms | numbers)) as $durs   # older/partial records may lack it
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
      $routes | group_by([.agent, .model]) | map(
        (.[0].agent) as $a
        | (.[0].model) as $m
        | length as $runs
        | ($esc | map(select(.from==$a and .model==$m)) | length) as $e
        | {
            agent: $a,
            model: $m,
            pinned: (($pins[$a] // "") | tier),
            runs: $runs,
            escalations: $e,
            escalation_rate: (if $runs==0 then 0 else (($e/$runs)*100|round)/100 end),
            fit_score: (if $runs==0 then null else (((1 - $e/$runs)*100|round)/100) end)
          }
      )
    ),

    global: (
      ([ $ev[] | select(.kind=="verify") ]) as $v
      | {
          verify_total: ($v|length),
          verify_pass: ($v | map(select(.pass==true)) | length),
          verify_pass_rate: (if ($v|length)==0 then null else (($v|map(select(.pass==true))|length) / ($v|length) * 100 | round)/100 end),
          review_avg_rounds: (if ($rounds|length)==0 then null else ((($rounds|add) / ($rounds|length))*100|round)/100 end),
          prs_logged: ($prs|length),
          prs_unreviewed: ([ $prs[] | select(.rounds==0) ] | length),
          escalations_logged: ($esc_logged|length),
          escalations_derived: ($esc_derived|length)
        }
    )
  }
' "$EVENTS")

echo "$JSON" > "$MDIR/scorecard.json"

# Subagent runs measured but none attributable to a kit agent: either Claude
# Code is too old to pass agent_type, or no kit agent has run yet.
MODELS_N=$(echo "$JSON" | jq '.models | length')
AGENTS_N=$(echo "$JSON" | jq '.agents | length')
ROUTE_WARN=""
if [ "$MODELS_N" -gt 0 ] && [ "$AGENTS_N" -eq 0 ]; then
  ROUTE_WARN="> **No kit-agent runs found.** Model speed/cost is being measured, but no subagent record names a kit agent — update Claude Code (the SubagentStop hook needs \`agent_type\`) or run a task through \`/init-kit\`. Until then \`/kit-tune\` has nothing to act on."
  echo "warning: subagent events exist but none is tagged with a kit agent" >&2
fi

# Runs on a tier other than the agent's pinned one: a caller passed "model" to
# the Agent tool (which overrides the frontmatter pin), or the history predates
# a re-tier. Either way those runs are not evidence about the pinned tier.
OFF_PIN=$(echo "$JSON" | jq -r '.agents[]
  | select((.pinned | IN("haiku","sonnet","opus")) and (.model | IN("haiku","sonnet","opus")) and .model != .pinned)
  | "- `\(.agent)` ran \(.runs)× on **\(.model)** but is pinned to **\(.pinned)**."')

# Render Markdown.
{
  echo "# AgentAutoKit routing scorecard"
  echo
  echo "_Generated: $(echo "$JSON" | jq -r '.generated_at')_ · _Events: \`$EVENTS\`_"
  echo
  echo "## Models — speed & cost"
  echo
  echo "| Model | Runs | p50 dur (s) | p95 dur (s) | Tok in | Tok out | Cache read | Cache write | Est. cost (USD) |"
  echo "|-------|-----:|------------:|------------:|-------:|--------:|-----------:|------------:|----------------:|"
  echo "$JSON" | jq -r '.models[] | "| \(.model) | \(.records) | \(if .dur_p50_ms == null then "n/a" else (.dur_p50_ms/1000*10|round)/10 end) | \(if .dur_p95_ms == null then "n/a" else (.dur_p95_ms/1000*10|round)/10 end) | \(.tok_in) | \(.tok_out) | \(.cache_read) | \(.cache_write) | \(.est_cost_usd) |"'
  echo
  echo "## Agents — fit score per tier (1.0 = never escalated)"
  echo
  echo "| Agent | Tier | Pinned | Runs | Escalations | Escalation rate | Fit score |"
  echo "|-------|------|--------|-----:|------------:|----------------:|----------:|"
  echo "$JSON" | jq -r '.agents[] | "| \(.agent) | \(.model) | \(if .pinned == "other" then "-" else .pinned end) | \(.runs) | \(.escalations) | \(.escalation_rate) | \(.fit_score // "n/a") |"'
  echo
  echo "$JSON" | jq -r '.global | "_Escalations: \(.escalations_logged) logged by the orchestrator, \(.escalations_derived) derived from run order (implementer → deep-debugger)._"'
  echo
  if [ -n "$OFF_PIN" ]; then
    echo "**Off-pin runs** — the Agent tool call passed a \`model\` that overrides the frontmatter pin (or the runs predate a re-tier):"
    echo
    echo "$OFF_PIN"
    echo
  fi
  echo "## Pipeline health"
  echo
  echo "$JSON" | jq -r '.global | "- Verify first-pass rate: \(if .verify_pass_rate==null then "n/a" else "\(.verify_pass_rate) (\(.verify_pass)/\(.verify_total))" end)\n- Avg review rounds per reviewed PR: \(.review_avg_rounds // "n/a")\n- PRs opened: \(.prs_logged) (without a code-reviewer run: \(.prs_unreviewed))"'
  echo
  if [ -n "$ROUTE_WARN" ]; then
    echo "$ROUTE_WARN"
    echo
  fi
  echo "> Costs use list prices for Haiku 4.5 / Sonnet 5.5 / Opus 5.5 by tier — override in \`.claude/metrics/pricing.json\`."
} > "$MDIR/scorecard.md"

cat "$MDIR/scorecard.md"
