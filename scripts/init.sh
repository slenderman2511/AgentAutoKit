#!/bin/bash
# AgentAutoKit init/upgrade: merge the .claude/ template into a target project.
#
# Idempotent and upgrade-safe:
#   - missing files are INSTALLED
#   - identical files are SKIPPED
#   - differing files are UPDATED to the kit's version (sync), and listed so
#     you can review `git diff` — never edit blindly after an upgrade
#   - files the project added itself (extra skills, agents, ...) are NEVER touched
#   - settings.json is DEEP-MERGED, not overwritten: your permission rules,
#     hooks, enabledPlugins and marketplaces are kept; the kit only fills gaps
#     (union for permission lists and plugin/marketplace maps)
#
# Usage:
#   ./init.sh /path/to/your/project            # install or upgrade
#   ./init.sh /path/to/your/project --dry-run  # show what would change
set -e

TARGET="${1:-.}"
DRY=0
if [ "$1" = "--dry-run" ]; then TARGET="."; DRY=1; fi
[ "$2" = "--dry-run" ] && DRY=1

KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$KIT_DIR/template/.claude"
KIT_VERSION=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$KIT_DIR/.claude-plugin/plugin.json" 2>/dev/null | head -1)

if [ ! -d "$SRC" ]; then
  echo "Error: template not found at $SRC" >&2
  exit 1
fi

DEST="$TARGET/.claude"
INSTALLED=0; UPDATED=0; SKIPPED=0

do_copy() {  # $1=src file  $2=dest file
  [ "$DRY" -eq 1 ] && return 0
  mkdir -p "$(dirname "$2")"
  cp "$1" "$2"
}

# Deep-merge kit settings.json into the project's. Project values win on
# conflicts; permission lists are unioned; plugin/marketplace maps keep the
# project's entries and add the kit's missing ones — so a plugin the project
# already enabled is never re-added, duplicated, or version-fought.
merge_settings() {  # $1=kit settings  $2=project settings (exists)
  [ "$DRY" -eq 1 ] && return 0
  local tmp; tmp=$(mktemp)
  jq -s '
    .[0] as $kit | .[1] as $proj
    | ($kit * $proj)
    | .permissions.allow = ((($kit.permissions.allow // []) + ($proj.permissions.allow // [])) | unique)
    | .permissions.deny  = ((($kit.permissions.deny  // []) + ($proj.permissions.deny  // [])) | unique)
    | .permissions.ask   = ((($kit.permissions.ask   // []) + ($proj.permissions.ask   // [])) | unique)
    | .enabledPlugins         = (($kit.enabledPlugins // {})         + ($proj.enabledPlugins // {}))
    | .extraKnownMarketplaces = (($kit.extraKnownMarketplaces // {}) + ($proj.extraKnownMarketplaces // {}))
  ' "$1" "$2" > "$tmp" && mv "$tmp" "$2"
}

echo "AgentAutoKit ${KIT_VERSION:-?} → $TARGET$([ "$DRY" -eq 1 ] && echo '  (dry-run)')"
echo

while IFS= read -r src_file; do
  rel="${src_file#"$SRC"/}"
  dest_file="$DEST/$rel"

  # CLAUDE.md is placed at the project root (handled below), never in .claude/.
  [ "$rel" = "CLAUDE.md" ] && continue

  if [ ! -f "$dest_file" ]; then
    do_copy "$src_file" "$dest_file"
    INSTALLED=$((INSTALLED + 1))
    echo "  install  $rel"
  elif [ "$rel" = "settings.json" ]; then
    if cmp -s "$src_file" "$dest_file"; then
      SKIPPED=$((SKIPPED + 1))
    else
      merge_settings "$src_file" "$dest_file"
      UPDATED=$((UPDATED + 1))
      echo "  merge    $rel   (project values kept; kit fills gaps)"
    fi
  elif cmp -s "$src_file" "$dest_file"; then
    SKIPPED=$((SKIPPED + 1))
  else
    do_copy "$src_file" "$dest_file"
    UPDATED=$((UPDATED + 1))
    echo "  update   $rel"
  fi
done < <(find "$SRC" -type f | sort)

if [ "$DRY" -eq 0 ]; then
  chmod +x "$DEST/hooks/"*.sh "$DEST/scripts/"*.sh 2>/dev/null || true
fi

# Place CLAUDE.md at project root (Claude Code reads it there) if not present.
# Never overwrite an existing one — it carries project-specific knowledge.
if [ ! -f "$TARGET/CLAUDE.md" ] && [ -f "$SRC/CLAUDE.md" ]; then
  [ "$DRY" -eq 0 ] && cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"
  echo "  install  CLAUDE.md (project root) — edit <PROJECT_NAME>"
fi
# The canonical CLAUDE.md lives at the project root; drop the copy nested in .claude/.
[ "$DRY" -eq 0 ] && rm -f "$DEST/CLAUDE.md"

# Ensure personal settings + runtime metrics are gitignored.
if [ "$DRY" -eq 0 ]; then
  GI="$TARGET/.gitignore"
  touch "$GI"
  grep -q ".claude/settings.local.json" "$GI" || echo ".claude/settings.local.json" >> "$GI"
  grep -q ".claude/metrics/" "$GI"            || echo ".claude/metrics/" >> "$GI"
  # Stamp the installed kit version for future upgrades.
  [ -n "$KIT_VERSION" ] && echo "$KIT_VERSION" > "$DEST/.agentautokit-version"
fi

echo
echo "Done: $INSTALLED installed, $UPDATED updated, $SKIPPED unchanged."
if [ "$UPDATED" -gt 0 ] && [ "$DRY" -eq 0 ]; then
  echo "Review what changed before committing: git -C $TARGET diff .claude/"
fi
echo
echo "Note: if this project ALSO has the agent-auto-kit plugin installed,"
echo "keep only one surface (plugin or template) — otherwise agents, commands"
echo "and skills load twice under the same names."
