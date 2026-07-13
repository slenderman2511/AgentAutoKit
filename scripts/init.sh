#!/bin/bash
# AgentAutoKit init: copy the .claude/ template into a target project.
# Usage: ./init.sh /path/to/your/project
set -e

TARGET="${1:-.}"
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$KIT_DIR/template/.claude"

if [ ! -d "$SRC" ]; then
  echo "Error: template not found at $SRC" >&2
  exit 1
fi

DEST="$TARGET/.claude"
if [ -d "$DEST" ]; then
  echo "A .claude/ directory already exists in $TARGET."
  read -p "Overwrite agents/commands/hooks/settings? [y/N] " ans
  [ "$ans" = "y" ] || { echo "Aborted."; exit 0; }
fi

mkdir -p "$DEST"
cp -r "$SRC/." "$DEST/"
chmod +x "$DEST/hooks/"*.sh 2>/dev/null || true

# Place CLAUDE.md at project root (Claude Code reads it there) if not present.
if [ ! -f "$TARGET/CLAUDE.md" ]; then
  cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"
  echo "Created CLAUDE.md at project root — edit <PROJECT_NAME>."
fi
# The canonical CLAUDE.md lives at the project root; drop the copy nested in .claude/.
rm -f "$DEST/CLAUDE.md"

# Ensure personal settings + runtime metrics are gitignored.
GI="$TARGET/.gitignore"
touch "$GI"
grep -q ".claude/settings.local.json" "$GI" || echo ".claude/settings.local.json" >> "$GI"
grep -q ".claude/metrics/" "$GI"            || echo ".claude/metrics/" >> "$GI"

echo "AgentAutoKit installed into $TARGET/.claude"
echo "Next: verify with 'jq . $DEST/settings.json' and try '/init-kit <task>' in Claude Code."
