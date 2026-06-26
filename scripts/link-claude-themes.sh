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

if [ -L "$TARGET_DIR" ]; then
  rm "$TARGET_DIR"
  mkdir -p "$TARGET_DIR"
fi

echo "==> claude themes -> $TARGET_DIR"
shopt -s nullglob
for file in "$REPO_DIR/claude-themes"/*.json; do
  target="$TARGET_DIR/$(basename "$file")"
  rm -f "$target"
  cp "$file" "$target"
  echo "  copied: $(basename "$file")"
done
