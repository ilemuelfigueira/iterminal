#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$SCOPE" in
  user)  TARGET_DIR="$HOME/.claude/themes" ;;
  local) TARGET_DIR="$PWD/.claude/themes" ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

mkdir -p "$TARGET_DIR"

echo "==> claude themes -> $TARGET_DIR"
for file in "$REPO_DIR/claude-themes"/*.json; do
  target="$TARGET_DIR/$(basename "$file")"
  if [ -L "$target" ]; then
    echo "  already linked: $(basename "$file")"
  elif [ -e "$target" ]; then
    echo "  skipped (file exists): $(basename "$file")"
  else
    ln -s "$file" "$target"
    echo "  linked: $(basename "$file")"
  fi
done
