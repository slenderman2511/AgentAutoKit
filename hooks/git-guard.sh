#!/bin/bash
# PreToolUse (Bash) hook: enforce the git workflow instead of just stating it.
#   - `gh pr create` must base the integration branch (the only exception is the
#     promotion PR: --head <integration> --base main|master).
#   - `git push` must not target the integration branch, main or master
#     (bare push from them, `HEAD:dev`, `+main`, `--delete dev`, --all/--mirror).
# Integration branch = "Integration branch: `X`" in the repo's CLAUDE.md, else
# `dev`; enforced only when origin really has that branch (main-only repos and a
# template CLAUDE.md left at `dev` are not enforced).
# Only real commands count: a segment STARTING with git … push / gh pr create.
# Heredoc bodies and quoted text with spaces (messages, titles, grep patterns)
# are data. `cd <dir>` and `git -C <dir>` pick the repo the command runs in.
# Exit 2 = block (stderr is fed back to Claude). KIT_GIT_GUARD=off disables it.
[ "${KIT_GIT_GUARD:-on}" = off ] && exit 0
set -f   # word-split command text without glob expansion
INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
case "$CMD" in *push*|*"pr create"*) ;; *) exit 0 ;; esac
DIR=$(printf '%s' "$INPUT" | jq -r '.cwd // empty'); [ -n "$DIR" ] || DIR=$PWD

BODYLESS=$(printf '%s\n' "$CMD" | awk -v q="'" '
  hd != "" { l = $0; sub(/^[ \t]+/, "", l); if (l == hd) hd = ""; next }
  { if (match($0, "<<-?[ \t]*[\"" q "]?[A-Za-z_][A-Za-z0-9_]*")) {
      t = substr($0, RSTART, RLENGTH); sub("^<<-?[ \t]*[\"" q "]?", "", t); hd = t
      print substr($0, 1, RSTART - 1) } else print }')
unquote() { sed -E "s/\"[^\"]*[[:space:]][^\"]*\"/Q/g; s/'[^']*[[:space:]][^']*'/Q/g; s/[\"']//g"; }
SEGS=$(printf '%s\n' "$BODYLESS" | unquote | awk '{ gsub(/&&|\|\||\$\(|[;|()`]/, "\n"); print }')

block() { echo "Blocked by git-guard: $1 (integration branch: '$INT'). If this is a deliberate release step, ask the user to run it, or use the project's release script." >&2; exit 2; }
is_protected() { case "$1" in "$INT"|main|master) return 0 ;; esac; return 1; }
resolve() { case "$1" in /*) echo "$1" ;; "~"*) echo "$HOME${1#\~}" ;; *) echo "$DIR/$1" ;; esac; }

ctx() {  # $1 = dir → INT, CUR; non-zero = not enforced there
  INT=""; CUR=""
  local top; top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
  INT=$(grep -m1 -oE 'Integration branch: `[^`]+`' "$top/CLAUDE.md" 2>/dev/null | sed -E 's/.*`([^`]+)`/\1/')
  [ -n "$INT" ] || INT=dev
  git -C "$1" rev-parse -q --verify "refs/remotes/origin/$INT" >/dev/null || return 1
  CUR=$(git -C "$1" symbolic-ref --short -q HEAD)
}

check_push() {  # $1 = dir, rest = args after `push`
  ctx "$1" || return 0; shift
  local remote="" refs="" tags="" skip="" t r dst
  for t in "$@"; do
    if [ -n "$skip" ]; then skip=""; continue; fi
    case "$t" in
      --all|--mirror) block "git push $t pushes protected branches" ;;
      --tags) tags=1 ;;
      --repo|--push-option|-o|--receive-pack|--exec) skip=1 ;;
      -*) ;;
      *'>'|*'<') skip=1 ;;      # `2>` / `>` file: the redirect target is the next word
      *'>'*|*'<'*) ;;           # `2>&1`, `>/dev/null`
      *) if [ -z "$remote" ]; then remote=$t; else refs="$refs $t"; fi ;;
    esac
  done
  if [ -z "$refs" ]; then
    if [ -z "$tags" ] && is_protected "$CUR"; then block "bare git push from '$CUR'"; fi
    return 0
  fi
  for r in $refs; do
    r=${r#+}; dst=${r##*:}
    case "$dst" in HEAD|@) dst=$CUR ;; esac
    dst=${dst#refs/heads/}
    if is_protected "$dst"; then block "git push to '$dst' — open a PR into $INT instead"; fi
  done
}

check_pr() {  # $1 = dir; flags are read from the text after `gh pr create` only
  ctx "$1" || return 0
  local pr base head
  pr=$(printf '%s' "$BODYLESS" | tr '\n' ' ' | unquote | sed -E 's/.*gh[[:space:]]+pr[[:space:]]+create//; s/(&&|\|\||;|\|).*//')
  case " $pr " in *" --repo"*|*" -R "*) return 0 ;; esac   # another repo: its branches are unknown here
  flag() { printf '%s' "$pr" | grep -oE -- "(^|[[:space:]])($1)[ =]+[^[:space:])]+" | head -1 | sed -E "s/^[[:space:]]*($1)[ =]+//"; }
  base=$(flag '--base|-B'); [ -n "$base" ] || base=$(git -C "$1" symbolic-ref --short -q refs/remotes/origin/HEAD | sed 's#^origin/##')
  head=$(flag '--head|-H'); [ -n "$head" ] || head=$CUR
  [ "$base" = "$INT" ] && return 0
  case "$base" in main|master) [ "$head" = "$INT" ] && return 0 ;; esac
  block "PR would base '${base:-<repo default>}' — pass --base $INT"
}

while IFS= read -r seg; do
  set -- $seg
  while [ $# -gt 0 ]; do case "$1" in [A-Za-z_]*=*) shift ;; *) break ;; esac; done   # VAR=x cmd
  case "$1" in
    cd) DIR=$(resolve "${2:-$HOME}") ;;
    git) shift; gdir=$DIR
      while [ $# -gt 0 ]; do
        case "$1" in -C) gdir=$(resolve "$2"); shift 2 ;; -c) shift 2 ;; -*) shift ;; *) break ;; esac
      done
      [ "$1" = push ] && { shift; check_push "$gdir" "$@"; } ;;
    gh) [ "$2 $3" = "pr create" ] && check_pr "$DIR" ;;
  esac
done <<< "$SEGS"
exit 0
