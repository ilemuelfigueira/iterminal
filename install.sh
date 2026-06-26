#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$REPO_DIR/scripts"

case "$SCOPE" in
  user|local) ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

# Resilient git pull
if ! command -v git &>/dev/null; then
  echo "==> git not found, skipping pull"
elif ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
  echo "==> not a git repo, skipping pull"
else
  echo "==> git pull"
  git -C "$REPO_DIR" pull || echo "  warning: git pull failed, continuing with local files" >&2
fi

bash "$SCRIPTS_DIR/sync-files.sh" "$SCOPE" "claude-themes"        "*.json" "themes"
bash "$SCRIPTS_DIR/sync-files.sh" "$SCOPE" "claude-output-styles"  "*.md"   "output-styles"
