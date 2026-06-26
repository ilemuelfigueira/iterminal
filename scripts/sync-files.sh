#!/usr/bin/env bash
set -euo pipefail

SCOPE="$1"
SRC_SUBDIR="$2"
GLOB="$3"
TARGET_SUBDIR="$4"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$SCOPE" in
  user)  TARGET_DIR="$HOME/.claude/$TARGET_SUBDIR" ;;
  local) TARGET_DIR="$PWD/.claude/$TARGET_SUBDIR" ;;
esac

if [ -L "$TARGET_DIR" ]; then
  rm "$TARGET_DIR"
fi
mkdir -p "$TARGET_DIR"

echo "==> $SRC_SUBDIR -> $TARGET_DIR"
shopt -s nullglob
for file in "$REPO_DIR/$SRC_SUBDIR"/$GLOB; do
  target="$TARGET_DIR/$(basename "$file")"
  cp "$file" "$target"
  echo "  copied: $(basename "$file")"
done
