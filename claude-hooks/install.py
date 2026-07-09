#!/usr/bin/env python3
"""
install.py — installs the enforce-gate YAML-driven hook into Claude Code

Steps:
  1. Ensure pyyaml is installed  (pip3 install pyyaml)
  2. Copy enforce-gate.py   →  ~/.claude/hooks/enforce-gate.py
  3. Copy enforce-gates.yml →  ~/.claude/enforce-gates.yml  (skip if already present)
  4. Detect all hook types used across enabled gates in enforce-gates.yml
  5. Register enforce-gate in each detected hook type in settings.json (idempotent)

Usage:
  python3 install.py [--scope global|local|repo]

Scopes:
  global  → ~/.claude/settings.json    (all Claude Code sessions)
  local   → .claude/settings.json      (current repo only)  <- DEFAULT
  repo    → .claude/settings.json      (alias for local)
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_HOOK_TYPES = ["PreToolUse"]


def _scope_to_settings_path(scope: str) -> Path:
    is_global = scope == "global"
    if is_global:
        return Path.home() / ".claude" / "settings.json"
    return Path(".claude") / "settings.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install enforce-gate YAML-driven hook into Claude Code"
    )
    parser.add_argument(
        "--scope",
        choices=["global", "local", "repo"],
        default="local",
        help="Where to register the hook (default: local)",
    )
    return parser.parse_args()


def _ensure_pyyaml() -> None:
    try:
        import yaml  # noqa: F401
        print("✅ pyyaml ja instalado")
        return
    except ImportError:
        pass

    print("📦 Instalando pyyaml...")

    pip_base = [sys.executable, "-m", "pip", "install", "pyyaml", "--quiet"]
    candidate_flags = [["--user"], ["--user", "--break-system-packages"]]

    for extra_flags in candidate_flags:
        result = subprocess.run(
            pip_base + extra_flags,
            capture_output=True,
            text=True,
        )
        is_success = result.returncode == 0
        if is_success:
            print("✅ pyyaml instalado com sucesso")
            return

    print("❌ Falha ao instalar pyyaml. Instale manualmente: pip3 install pyyaml --user")
    sys.exit(1)


def _collect_used_hook_types(gates_source: Path) -> list:
    try:
        import yaml
        with open(gates_source) as gates_file:
            config = yaml.safe_load(gates_file) or {}
    except Exception:
        return list(DEFAULT_HOOK_TYPES)

    used_hook_types: set = set()
    for gate in config.get("gates", []):
        is_enabled = gate.get("enabled", True)
        if not is_enabled:
            continue
        gate_hook_types = gate.get("hook_types", DEFAULT_HOOK_TYPES)
        used_hook_types.update(gate_hook_types)

    has_used_types = bool(used_hook_types)
    if not has_used_types:
        return list(DEFAULT_HOOK_TYPES)

    return sorted(used_hook_types)


def _check_already_registered(hook_type_list: list) -> bool:
    return any(
        "enforce-gate" in hook.get("command", "")
        for entry in hook_type_list
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
    gates_source = script_dir / "enforce-gates.yml"
    hooks_dest_dir = Path.home() / ".claude" / "hooks"
    hook_dest = hooks_dest_dir / "enforce-gate.py"
    gates_global_dest = Path.home() / ".claude" / "enforce-gates.yml"
    settings_file = _scope_to_settings_path(scope)

    print("🔧 Instalando enforce-gate hook...")
    print(f"   Scope    : {scope}")
    print(f"   Settings : {settings_file}")
    print(f"   Hook     : {hook_dest}")
    print(f"   Config   : {gates_global_dest}")
    print()

    # ── 1. pyyaml ────────────────────────────────────────────────────────────
    _ensure_pyyaml()

    # ── 2. Validate sources ───────────────────────────────────────────────────
    for required_source in (hook_source, gates_source):
        is_missing = not required_source.exists()
        if is_missing:
            print(f"❌ Arquivo nao encontrado: {required_source}")
            sys.exit(1)

    # ── 3. Copy hook script ───────────────────────────────────────────────────
    hooks_dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(hook_source, hook_dest)
    hook_dest.chmod(0o755)
    print(f"✅ Hook engine instalado: {hook_dest}")

    # ── 4. Copy YAML config (preserve existing customizations) ───────────────
    gates_config_exists = gates_global_dest.exists()
    if gates_config_exists:
        print(f"⚠️  Config ja existe, mantendo: {gates_global_dest}")
    else:
        shutil.copy2(gates_source, gates_global_dest)
        print(f"✅ Config instalada: {gates_global_dest}")

    # ── 5. Detect hook types used by enabled gates ────────────────────────────
    used_hook_types = _collect_used_hook_types(gates_source)
    print(f"🔍 Hook types detectados nos gates: {', '.join(used_hook_types)}")

    # ── 6. Ensure settings file exists ───────────────────────────────────────
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

    # ── 7. Register enforce-gate in each used hook type ───────────────────────
    hooks_section = settings.setdefault("hooks", {})
    registered_in = []
    skipped_in = []

    for hook_type in used_hook_types:
        hook_type_list = hooks_section.setdefault(hook_type, [])
        is_already_registered = _check_already_registered(hook_type_list)
        if is_already_registered:
            skipped_in.append(hook_type)
        else:
            hook_entry = _build_hook_entry(hook_dest)
            hook_type_list.insert(0, hook_entry)
            registered_in.append(hook_type)

    has_changes = bool(registered_in)
    if has_changes:
        updated_content = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
        settings_file.write_text(updated_content)
        for hook_type in registered_in:
            print(f"✅ {hook_type} hook registrado em: {settings_file}")

    for hook_type in skipped_in:
        print(f"⚠️  enforce-gate ja registrado em {hook_type} — sem alteracoes.")

    print()
    print("Instalacao concluida!")
    print()
    print("Gates carregados de (todos mergeados):")
    print("  ~/.claude/enforce-gates.yml  (global)")
    print("  .claude/enforce-gates.yml    (project-local, se existir)")
    print()
    print("Para adicionar gates: edite enforce-gates.yml e adicione entradas em 'gates:'")
    print("Para desinstalar: remova as entradas 'enforce-gate' dos hook types em:")
    print(f"  {settings_file}")


if __name__ == "__main__":
    main()
