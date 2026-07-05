#!/usr/bin/env python3
"""
install.py — installs enforce-gate PreToolUse hook into Claude Code settings

Usage:
  python3 install.py [--scope global|local|repo]

Scopes:
  global  → ~/.claude/settings.json    (all Claude Code sessions)
  local   → .claude/settings.json      (current repo only)  ← DEFAULT
  repo    → .claude/settings.json      (alias for local)
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def _scope_to_settings_path(scope: str) -> Path:
    is_global = scope == "global"
    if is_global:
        return Path.home() / ".claude" / "settings.json"
    return Path(".claude") / "settings.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install enforce-gate PreToolUse hook into Claude Code settings"
    )
    parser.add_argument(
        "--scope",
        choices=["global", "local", "repo"],
        default="local",
        help="Where to register the hook (default: local)",
    )
    return parser.parse_args()


def _check_already_registered(pre_tool_use_list: list) -> bool:
    return any(
        "enforce-gate" in hook.get("command", "")
        for entry in pre_tool_use_list
        for hook in entry.get("hooks", [])
    )


def _build_hook_entry(hook_dest: Path) -> dict:
    hook_command = f"python3 {hook_dest}"
    hook_definition = {"type": "command", "command": hook_command}
    hook_entry = {"matcher": "", "hooks": [hook_definition]}
    return hook_entry


def main() -> None:
    args = _parse_args()
    scope = args.scope

    script_dir = Path(__file__).parent.resolve()
    hook_source = script_dir / "enforce-gate.py"
    hooks_dest_dir = Path.home() / ".claude" / "hooks"
    hook_dest = hooks_dest_dir / "enforce-gate.py"
    settings_file = _scope_to_settings_path(scope)

    print("🔧 Instalando enforce-gate hook...")
    print(f"   Scope    : {scope}")
    print(f"   Settings : {settings_file}")
    print(f"   Hook     : {hook_dest}")
    print()

    hook_source_missing = not hook_source.exists()
    if hook_source_missing:
        print(f"❌ enforce-gate.py não encontrado em: {hook_source}")
        sys.exit(1)

    hooks_dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(hook_source, hook_dest)
    hook_dest.chmod(0o755)
    print(f"✅ Hook script instalado: {hook_dest}")

    is_local_scope = scope != "global"
    if is_local_scope:
        settings_file.parent.mkdir(parents=True, exist_ok=True)

    settings_missing = not settings_file.exists()
    if settings_missing:
        settings_file.write_text("{}\n")
        print(f"📄 Criado: {settings_file}")

    try:
        settings = json.loads(settings_file.read_text())
    except json.JSONDecodeError:
        settings = {}

    hooks_section = settings.setdefault("hooks", {})
    pre_tool_use_list = hooks_section.setdefault("PreToolUse", [])

    is_already_registered = _check_already_registered(pre_tool_use_list)
    if is_already_registered:
        print("⚠️  enforce-gate já registrado em PreToolUse — sem alterações.")
    else:
        hook_entry = _build_hook_entry(hook_dest)
        pre_tool_use_list.insert(0, hook_entry)
        updated_content = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
        settings_file.write_text(updated_content)
        print(f"✅ PreToolUse hook registrado em: {settings_file}")

    print()
    print("🎉 enforce-gate instalado com sucesso!")
    print()
    print("Gates ativos:")
    print("  • *.styles.ts          → Checklist de 5 pontos (design token obrigatório)")
    print("  • components|ui/*.tsx  → Interrogação estruturada + AskUserQuestion gate")
    print()
    print("Variáveis de ambiente:")
    print("  CLAUDE_ENFORCE_GATE_BEHAVIOR=one-shot  (padrão) — alterna bloquear/liberar a cada tentativa")
    print("  CLAUDE_ENFORCE_GATE_BEHAVIOR=time      — libera após GATE_TIME segundos")
    print("  CLAUDE_ENFORCE_GATE_TIME=30            — segundos para modo time (padrão: 30)")
    print()
    print(f"Para desinstalar: remova a entrada 'enforce-gate' de PreToolUse em {settings_file}")


if __name__ == "__main__":
    main()
