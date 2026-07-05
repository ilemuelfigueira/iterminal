#!/usr/bin/env bash
# install.sh — installs enforce-gate PreToolUse hook into Claude Code settings
#
# Usage:
#   bash install.sh [--scope global|local|repo]
#
# Scopes:
#   global  → ~/.claude/settings.json        (affects all Claude Code sessions)
#   local   → .claude/settings.json          (current repo only)  ← DEFAULT
#   repo    → .claude/settings.json          (alias for local)

set -euo pipefail

SCOPE="local"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)
      SCOPE="$2"
      shift 2
      ;;
    --scope=*)
      SCOPE="${1#*=}"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--scope global|local|repo]"
      echo ""
      echo "Scopes:"
      echo "  global  → ~/.claude/settings.json  (all sessions)"
      echo "  local   → .claude/settings.json    (current repo, default)"
      echo "  repo    → .claude/settings.json    (alias for local)"
      exit 0
      ;;
    *)
      echo "⚠️  Argumento desconhecido: $1"
      shift
      ;;
  esac
done

case "$SCOPE" in
  global)
    SETTINGS_FILE="$HOME/.claude/settings.json"
    ;;
  local|repo)
    SETTINGS_FILE=".claude/settings.json"
    ;;
  *)
    echo "❌ Scope inválido: '$SCOPE'. Use: global, local, repo"
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SOURCE="$SCRIPT_DIR/enforce-gate.sh"
HOOKS_DEST_DIR="$HOME/.claude/hooks"
HOOK_DEST="$HOOKS_DEST_DIR/enforce-gate.sh"

echo "🔧 Instalando enforce-gate hook..."
echo "   Scope    : $SCOPE"
echo "   Settings : $SETTINGS_FILE"
echo "   Hook     : $HOOK_DEST"
echo ""

# ── 1. Validate source exists ────────────────────────────────────────────────
if [[ ! -f "$HOOK_SOURCE" ]]; then
  echo "❌ enforce-gate.sh não encontrado em: $HOOK_SOURCE"
  exit 1
fi

# ── 2. Copy hook script to ~/.claude/hooks/ ──────────────────────────────────
mkdir -p "$HOOKS_DEST_DIR"
cp "$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_DEST"
echo "✅ Hook script instalado: $HOOK_DEST"

# ── 3. Ensure settings file exists ───────────────────────────────────────────
if [[ "$SCOPE" != "global" ]]; then
  mkdir -p ".claude"
fi

if [[ ! -f "$SETTINGS_FILE" ]]; then
  echo "{}" > "$SETTINGS_FILE"
  echo "📄 Criado: $SETTINGS_FILE"
fi

# ── 4. Inject PreToolUse hook into settings.json ─────────────────────────────
python3 - "$SETTINGS_FILE" "$HOOK_DEST" <<'PYEOF'
import sys, json

settings_path = sys.argv[1]
hook_dest = sys.argv[2]
hook_command = f"bash {hook_dest}"

with open(settings_path, 'r') as settings_file:
    settings = json.load(settings_file)

hooks_section = settings.setdefault('hooks', {})
pre_tool_use_list = hooks_section.setdefault('PreToolUse', [])

already_registered = any(
    'enforce-gate' in hook.get('command', '')
    for entry in pre_tool_use_list
    for hook in entry.get('hooks', [])
)

if already_registered:
    print(f"⚠️  enforce-gate já registrado em PreToolUse — sem alterações.")
    sys.exit(0)

enforce_gate_entry = {
    "matcher": "",
    "hooks": [
        {
            "type": "command",
            "command": hook_command
        }
    ]
}
pre_tool_use_list.insert(0, enforce_gate_entry)

with open(settings_path, 'w') as settings_file:
    json.dump(settings, settings_file, indent=2, ensure_ascii=False)
    settings_file.write('\n')

print(f"✅ PreToolUse hook registrado em: {settings_path}")
PYEOF

echo ""
echo "🎉 enforce-gate instalado com sucesso!"
echo ""
echo "Gates ativos:"
echo "  • *.styles.ts          → Checklist de 5 pontos (design token obrigatório)"
echo "  • components|ui/*.tsx  → Interrogação estruturada + AskUserQuestion gate"
echo ""
echo "Para desinstalar: remova a entrada 'enforce-gate' de PreToolUse em $SETTINGS_FILE"
