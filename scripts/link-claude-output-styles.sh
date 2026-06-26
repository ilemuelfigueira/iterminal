#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$SCOPE" in
  user)  TARGET_DIR="$HOME/.claude/output-styles" ;;
  local) TARGET_DIR="$PWD/.claude/output-styles" ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

if [ -L "$TARGET_DIR" ]; then
  rm "$TARGET_DIR"
fi
mkdir -p "$TARGET_DIR"

echo "==> claude output-styles -> $TARGET_DIR"
shopt -s nullglob
for file in "$REPO_DIR/claude-output-styles"/*.md; do
  target="$TARGET_DIR/$(basename "$file")"
  rm -f "$target"
  cp "$file" "$target"
  echo "  copied: $(basename "$file")"
done
