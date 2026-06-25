#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" && pwd)"

case "$SCOPE" in
  user|local) ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

bash "$SCRIPTS_DIR/link-claude-themes.sh" "$SCOPE"
bash "$SCRIPTS_DIR/link-claude-output-styles.sh" "$SCOPE"
