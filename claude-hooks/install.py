#!/usr/bin/env python3
"""
install.py — installs the iterminal Claude Code hooks into settings.json

Registrar for a LIST of hooks (currently enforce-gate + pre-edit-lint):
  1. Ensure pyyaml is installed  (only if a hook needs it)
  2. Copy each hook script      →  ~/.claude/hooks/<name>.py
  3. Copy each hook's config     →  ~/.claude/<config>            (skip if present)
  4. Resolve the hook types each hook registers under
  5. Register every hook in each hook type in settings.json (idempotent)

Adding a new hook = one more HookDescriptor in HOOK_DESCRIPTORS.

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
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOOK_TYPES = ["PreToolUse"]
TOOL_BASED_HOOK_TYPES = frozenset({"PreToolUse", "PostToolUse"})


@dataclass(frozen=True)
class HookDescriptor:
    key: str
    source_name: str
    command_needle: str
    tool_matcher: str
    static_hook_types: tuple | None
    config_source_name: str | None
    needs_pyyaml: bool


enforce_gate_descriptor = HookDescriptor(
    key="enforce-gate",
    source_name="enforce-gate.py",
    command_needle="enforce-gate.py",
    tool_matcher="*",
    static_hook_types=None,
    config_source_name="enforce-gates.yml",
    needs_pyyaml=True,
)

pre_edit_lint_descriptor = HookDescriptor(
    key="pre-edit-lint",
    source_name="pre-edit-lint.py",
    command_needle="pre-edit-lint.py",
    tool_matcher="Edit|Write|MultiEdit",
    static_hook_types=("PreToolUse",),
    config_source_name=None,
    needs_pyyaml=False,
)

HOOK_DESCRIPTORS = [enforce_gate_descriptor, pre_edit_lint_descriptor]


def _scope_to_settings_path(scope: str, use_local_file: bool) -> Path:
    filename = "settings.local.json" if use_local_file else "settings.json"
    is_global = scope == "global"
    if is_global:
        return Path.home() / ".claude" / filename
    return Path(".claude") / filename


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install iterminal Claude Code hooks into settings.json"
    )
    parser.add_argument(
        "--scope",
        choices=["global", "local", "repo"],
        default="local",
        help="Where to register the hooks (default: local)",
    )
    parser.add_argument(
        "--local-file",
        action="store_true",
        help="Escreve em settings.local.json ao inves de settings.json",
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


def _collect_used_hook_types_from_yaml(config_source: Path) -> list:
    try:
        import yaml
        with open(config_source) as gates_file:
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


def _resolve_hook_types(descriptor: HookDescriptor, source_dir: Path) -> list:
    has_static_types = descriptor.static_hook_types is not None
    if has_static_types:
        return list(descriptor.static_hook_types)

    has_config = descriptor.config_source_name is not None
    if has_config:
        config_source = source_dir / descriptor.config_source_name
        return _collect_used_hook_types_from_yaml(config_source)

    return list(DEFAULT_HOOK_TYPES)


def _find_registered_entries(hook_type_list: list, command_needle: str) -> list:
    matching_entries = []
    for entry in hook_type_list:
        hooks = entry.get("hooks", [])
        has_needle = any(command_needle in hook.get("command", "") for hook in hooks)
        if has_needle:
            matching_entries.append(entry)
    return matching_entries


def _migrate_entry_matcher(entry: dict, hook_type: str, tool_matcher: str) -> bool:
    is_tool_based = hook_type in TOOL_BASED_HOOK_TYPES
    if is_tool_based:
        current_matcher = entry.get("matcher")
        is_correct = current_matcher == tool_matcher
        if is_correct:
            return False
        entry["matcher"] = tool_matcher
        return True

    has_stray_matcher = "matcher" in entry
    if has_stray_matcher:
        del entry["matcher"]
        return True
    return False


def _build_hook_entry(hook_dest: Path, hook_type: str, tool_matcher: str) -> dict:
    hook_command = f"python3 {hook_dest}"
    hook_definition = {"type": "command", "command": hook_command}
    is_tool_based = hook_type in TOOL_BASED_HOOK_TYPES
    if is_tool_based:
        hook_entry = {"matcher": tool_matcher, "hooks": [hook_definition]}
    else:
        hook_entry = {"hooks": [hook_definition]}
    return hook_entry


def _copy_hook_script(descriptor: HookDescriptor, source_dir: Path, hooks_dest_dir: Path) -> Path:
    hook_source = source_dir / descriptor.source_name
    is_missing = not hook_source.exists()
    if is_missing:
        print(f"❌ Arquivo nao encontrado: {hook_source}")
        sys.exit(1)

    hook_dest = hooks_dest_dir / descriptor.source_name
    shutil.copy2(hook_source, hook_dest)
    hook_dest.chmod(0o755)
    print(f"✅ Hook instalado: {hook_dest}")
    return hook_dest


def _copy_hook_config(descriptor: HookDescriptor, source_dir: Path) -> None:
    has_config = descriptor.config_source_name is not None
    if not has_config:
        return

    config_source = source_dir / descriptor.config_source_name
    is_missing = not config_source.exists()
    if is_missing:
        print(f"❌ Config nao encontrada: {config_source}")
        sys.exit(1)

    config_dest = Path.home() / ".claude" / descriptor.config_source_name
    config_exists = config_dest.exists()
    if config_exists:
        print(f"⚠️  Config ja existe, mantendo: {config_dest}")
    else:
        shutil.copy2(config_source, config_dest)
        print(f"✅ Config instalada: {config_dest}")


def _register_hook(
    descriptor: HookDescriptor,
    hook_dest: Path,
    hook_types: list,
    hooks_section: dict,
) -> tuple:
    registered_in = []
    skipped_in = []
    migrated_in = []
    for hook_type in hook_types:
        hook_type_list = hooks_section.setdefault(hook_type, [])
        existing_entries = _find_registered_entries(hook_type_list, descriptor.command_needle)
        is_already_registered = bool(existing_entries)
        if is_already_registered:
            was_migrated = False
            for entry in existing_entries:
                did_fix = _migrate_entry_matcher(entry, hook_type, descriptor.tool_matcher)
                if did_fix:
                    was_migrated = True
            if was_migrated:
                migrated_in.append(hook_type)
            else:
                skipped_in.append(hook_type)
        else:
            hook_entry = _build_hook_entry(hook_dest, hook_type, descriptor.tool_matcher)
            hook_type_list.insert(0, hook_entry)
            registered_in.append(hook_type)
    return registered_in, skipped_in, migrated_in


def main() -> None:
    args = _parse_args()
    scope = args.scope

    source_dir = Path(__file__).parent.resolve()
    hooks_dest_dir = Path.home() / ".claude" / "hooks"
    settings_file = _scope_to_settings_path(scope, args.local_file)

    print("🔧 Instalando iterminal Claude Code hooks...")
    print(f"   Scope    : {scope}")
    print(f"   Settings : {settings_file}")
    print(f"   Hooks dir: {hooks_dest_dir}")
    print(f"   Hooks    : {', '.join(d.key for d in HOOK_DESCRIPTORS)}")
    print()

    any_needs_pyyaml = any(descriptor.needs_pyyaml for descriptor in HOOK_DESCRIPTORS)
    if any_needs_pyyaml:
        _ensure_pyyaml()

    hooks_dest_dir.mkdir(parents=True, exist_ok=True)

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
    total_registered = []
    total_migrated = []

    for descriptor in HOOK_DESCRIPTORS:
        hook_dest = _copy_hook_script(descriptor, source_dir, hooks_dest_dir)
        _copy_hook_config(descriptor, source_dir)

        hook_types = _resolve_hook_types(descriptor, source_dir)
        print(f"🔍 {descriptor.key}: hook types → {', '.join(hook_types)}")

        registered_in, skipped_in, migrated_in = _register_hook(
            descriptor, hook_dest, hook_types, hooks_section
        )
        for hook_type in registered_in:
            print(f"✅ {descriptor.key} registrado em {hook_type}")
            total_registered.append((descriptor.key, hook_type))
        for hook_type in migrated_in:
            print(f"🔧 {descriptor.key} em {hook_type}: matcher corrigido (migracao).")
            total_migrated.append((descriptor.key, hook_type))
        for hook_type in skipped_in:
            print(f"⚠️  {descriptor.key} ja registrado em {hook_type} — sem alteracoes.")
        print()

    has_changes = bool(total_registered) or bool(total_migrated)
    if has_changes:
        updated_content = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
        settings_file.write_text(updated_content)

    print("Instalacao concluida!")
    print()
    print("Config enforce-gate carregada de (todas mergeadas):")
    print("  ~/.claude/enforce-gates.yml  (global)")
    print("  .claude/enforce-gates.yml    (project-local, se existir)")
    print()
    print("Para desinstalar: remova as entradas dos hooks em:")
    print(f"  {settings_file}")


if __name__ == "__main__":
    main()
