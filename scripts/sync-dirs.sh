#!/usr/bin/env bash
set -euo pipefail

SCOPE="$1"
SRC_SUBDIR="$2"
TARGET_SUBDIR="$3"
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
for dir in "$REPO_DIR/$SRC_SUBDIR"/*/; do
  name="$(basename "$dir")"
  rm -rf "${TARGET_DIR:?}/$name"
  cp -R "$dir" "$TARGET_DIR/$name"
  echo "  copied: $name/"
done
