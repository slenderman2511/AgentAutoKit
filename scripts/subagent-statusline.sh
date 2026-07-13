#!/bin/bash
# subagentStatusLine: custom row for each subagent shown in the agent panel.
# Claude Code passes { columns, tasks:[{id,name,status,model,tokenCount,
# contextWindowSize,...}], ...base } on stdin, once per refresh tick.
# We print one JSON line per row: {"id": "<task id>", "content": "<row>"}.
# Plugin-shippable (unlike the main statusLine).
set -o pipefail
cat | jq -c '
  def esc: [27] | implode;                 # ESC built at runtime so jq escapes it in output
  def c($n): esc + "[" + $n + "m";         # ANSI SGR open
  def reset: esc + "[0m";
  def shortmodel:
    if . == null or . == "" then "?"
    elif test("haiku") then "haiku"
    elif test("sonnet") then "sonnet"
    elif test("opus") then "opus"
    else . end;

  .tasks[]?
  | (.model // "" | shortmodel) as $m
  | (.tokenCount // 0) as $tok
  | (.contextWindowSize // 0) as $ctx
  | (if $ctx > 0 then (($tok / $ctx * 100) | floor | tostring) + "% ctx"
     else ($tok | tostring) + " tok" end) as $usage
  | (.status // "") as $st
  | (if   $st == "running"   then "32"
     elif $st == "failed"    then "31"
     elif $st == "completed" then "2"
     else "33" end) as $col
  | {
      id: .id,
      content: (
        c($col) + "🤖 " + (.name // "agent") + reset + " "
        + c("2") + $m + " · " + $usage + reset
        + (if $st != "" then " " + c("2") + "[" + $st + "]" + reset else "" end)
      )
    }
' 2>/dev/null
