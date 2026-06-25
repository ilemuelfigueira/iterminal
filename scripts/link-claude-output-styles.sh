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

mkdir -p "$TARGET_DIR"

echo "==> claude output-styles -> $TARGET_DIR"
for file in "$REPO_DIR/claude-output-styles"/*.md; do
  target="$TARGET_DIR/$(basename "$file")"
  if [ -L "$target" ]; then
    echo "  already linked: $(basename "$file")"
  elif [ -e "$target" ]; then
    echo "  replacing with symlink: $(basename "$file")"
    rm "$target"
    ln -s "$file" "$target"
  else
    ln -s "$file" "$target"
    echo "  linked: $(basename "$file")"
  fi
done
