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
  if [ -L "$file" ]; then
    echo "  error: source is a symlink, skipping: $(basename "$file")" >&2
    continue
  fi
  target="$TARGET_DIR/$(basename "$file")"
  if [ -L "$target" ] && [ "$(readlink "$target")" = "$file" ]; then
    echo "  already linked: $(basename "$file")"
  else
    ln -sf "$file" "$target"
    echo "  linked: $(basename "$file")"
  fi
done
