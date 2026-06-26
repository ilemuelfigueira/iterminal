#!/usr/bin/env bash
set -euo pipefail

AGENTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${CLAUDE_AGENTS_DIR:-$HOME/.claude/agents}"

usage() {
  cat <<EOF
Usage:
  ./install.sh [--list] [agent-name]

Options:
  --list        Show available agents
  agent-name    Install a specific agent (default: install all)

Examples:
  ./install.sh
  ./install.sh rule-knight
  ./install.sh --list
EOF
  exit 1
}

list_agents() {
  echo ""
  echo "Available agents:"
  echo ""
  for file in "$AGENTS_DIR"/*.md; do
    local name
    name=$(basename "$file" .md)
    local description
    description=$(grep -m1 '^description:' "$file" | sed 's/description: *//' | tr -d '"' | cut -c1-80)
    printf "  %-20s %s\n" "$name" "$description"
  done
  echo ""
}

install_agent() {
  local agent_name="$1"
  local source_file="$AGENTS_DIR/$agent_name.md"

  if [[ ! -f "$source_file" ]]; then
    echo "Error: agent '$agent_name' not found"
    exit 1
  fi

  mkdir -p "$TARGET_DIR"
  cp "$source_file" "$TARGET_DIR/$agent_name.md"
  echo "  installed: $agent_name -> $TARGET_DIR/$agent_name.md"
}

install_all() {
  mkdir -p "$TARGET_DIR"
  echo "==> Installing all agents to $TARGET_DIR"
  for file in "$AGENTS_DIR"/*.md; do
    local name
    name=$(basename "$file" .md)
    cp "$file" "$TARGET_DIR/$name.md"
    echo "  installed: $name"
  done
}

case "${1:-}" in
  --list) list_agents; exit 0 ;;
  --help|-h) usage ;;
  "")  install_all ;;
  -*) echo "Unknown option: $1"; usage ;;
  *)  install_agent "$1" ;;
esac
