#!/bin/bash
# SubagentStop hook: measure speed + token cost of each subagent run.
# Reliable half of the telemetry — parsed straight from the session transcript.
# Never blocks; always exits 0.
set -o pipefail
INPUT=$(cat)

# Current Claude Code writes each subagent to its own transcript
# (<session>/subagents/agent-<id>.jsonl) and passes it as agent_transcript_path.
# Older versions kept sidechains inline in the main transcript_path.
TRANSCRIPT=$(echo "$INPUT" | jq -r '.agent_transcript_path // .transcript_path // empty')
SESSION=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
# agent_type names the agent that ran (e.g. "implementer"); drop a plugin
# namespace so plugin and template installs score under the same name.
# Only trusted with a per-agent transcript: an inline main transcript can hold
# several sidechains, and agent_type names just the one that stopped.
AGENT=$(echo "$INPUT" | jq -r 'if .agent_transcript_path then (.agent_type // "" | sub("^[^:]+:"; "")) else "" end')
[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

# Metrics dir: the main checkout's, shared by every worktree (see the lib).
# The lib sits at ../scripts/ in both the plugin and the template layout.
LIB="$(dirname "$0")/../scripts/kit-metrics-lib.sh"
if [ -f "$LIB" ]; then . "$LIB"; MDIR=$(kit_metrics_dir)
else MDIR="${CLAUDE_PROJECT_DIR:-$(pwd)}/.claude/metrics"; fi
mkdir -p "$MDIR"

# Parallel subagents fire this hook concurrently; serialize on a portable
# mkdir lock so two runs can't read the same cursor and double-count.
LOCKDIR="$MDIR/.metrics.lock"
LOCKED=0
for _ in 1 2 3 4 5; do
  if mkdir "$LOCKDIR" 2>/dev/null; then LOCKED=1; break; fi
  sleep 1
done
[ "$LOCKED" -eq 1 ] || exit 0   # best-effort: skip rather than risk double-counting
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

# Cursor: only process transcript lines we haven't seen yet. Snapshot the new
# chunk first so lines appended mid-run are neither lost nor counted twice.
CUR="$MDIR/.cursor-$(basename "$TRANSCRIPT")"
LAST=$(cat "$CUR" 2>/dev/null || echo 0)
CHUNK="$MDIR/.chunk-$$"
tail -n +"$((LAST + 1))" "$TRANSCRIPT" > "$CHUNK" 2>/dev/null
NEW=$(wc -l < "$CHUNK" | tr -d ' ')
if [ "$NEW" -eq 0 ]; then rm -f "$CHUNK"; exit 0; fi

# One record per sidechain (subagent run), reconstructed from the uuid →
# parentUuid chain. Grouping by chain root keeps parallel subagents on the
# same model apart, so durations aren't inflated by overlapping runs.
jq -cRs --arg session "$SESSION" --arg agent "$AGENT" '
  [ split("\n")[] | select(length > 0) | (fromjson? // empty) | select(type=="object") ] as $all
  | ($all | map(select(.uuid != null) | {key: .uuid, value: .parentUuid}) | from_entries) as $par
  | def root($u): ($par[$u] // null) as $p | if $p == null then $u else root($p) end;
  [ $all[]
    | select(.isSidechain == true and .type == "assistant" and (.message.model // "") != "<synthetic>")
    | {root: root(.uuid // "?"),
       model: (.message.model),
       ts: (.timestamp | gsub("\\.[0-9]+Z$"; "Z")),
       ti: (.message.usage.input_tokens // 0),
       to: (.message.usage.output_tokens // 0),
       cr: (.message.usage.cache_read_input_tokens // 0),
       cw: (.message.usage.cache_creation_input_tokens // 0)} ]
  | group_by(.root)[]
  | {ts: (now | todateiso8601), session: $session, kind: "subagent",
     model: .[0].model,
     agent: (if $agent == "" then null else $agent end),
     turns: length,
     tok_in: (map(.ti) | add), tok_out: (map(.to) | add),
     cache_read: (map(.cr) | add), cache_write: (map(.cw) | add),
     duration_ms: (
       ((map(.ts | fromdateiso8601) | max) - (map(.ts | fromdateiso8601) | min)) * 1000 | floor
     )
    }' "$CHUNK" 2>/dev/null \
  | while IFS= read -r rec; do
      [ -n "$rec" ] && printf '%s\n' "$rec" >> "$MDIR/events.jsonl"
    done

echo "$((LAST + NEW))" > "$CUR"
rm -f "$CHUNK"
exit 0
