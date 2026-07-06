#!/usr/bin/env python3
"""
enforce-gate.py ��� YAML-driven PreToolUse hook engine

Loads gate definitions from enforce-gates.yml and applies them to every
file-editing tool call made by Claude Code.

Config resolution order (first found wins):
  1. $CLAUDE_ENFORCE_GATE_CONFIG   (env var)
  2. .claude/enforce-gates.yml     (project-local)
  3. ~/.claude/enforce-gates.yml   (global)

See enforce-gates.yml for the full schema reference.
"""

import fcntl
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "[enforce-gate] pyyaml nao encontrado. "
        "Execute: pip3 install pyyaml\n"
        "O gate foi desativado ate a instalacao.",
        file=sys.stderr,
    )
    sys.exit(0)


DEFAULT_BEHAVIOR = "one-shot"
DEFAULT_GATE_TIME = 30
DEFAULT_TOOLS = frozenset({"Edit", "Write", "MultiEdit"})
VALID_BEHAVIORS = frozenset({"one-shot", "time"})


# ── Config resolution ─────────────────────────────────────────────────────────

def _find_config() -> Path | None:
    env_path = os.environ.get("CLAUDE_ENFORCE_GATE_CONFIG", "")
    has_env_path = bool(env_path)
    if has_env_path:
        candidate = Path(env_path)
        is_env_path_valid = candidate.exists()
        if is_env_path_valid:
            return candidate

    project_local = Path(".claude") / "enforce-gates.yml"
    is_project_local_present = project_local.exists()
    if is_project_local_present:
        return project_local

    global_config = Path.home() / ".claude" / "enforce-gates.yml"
    is_global_present = global_config.exists()
    if is_global_present:
        return global_config

    return None


def _load_config(config_path: Path) -> dict:
    with open(config_path) as config_file:
        return yaml.safe_load(config_file) or {}


# ── Gate matching ─────────────────────────────────────────────────────────────

def _matches_glob(pattern: str, file_path: str) -> bool:
    has_path_separator = "/" in pattern
    if has_path_separator:
        return fnmatch.fnmatch(file_path, pattern)
    return fnmatch.fnmatch(os.path.basename(file_path), pattern)


def _matches_gate(gate: dict, file_path: str) -> bool:
    matcher = gate.get("matcher", "")
    matcher_type = gate.get("matcher_type", "glob").lower()

    is_regex = matcher_type == "regex"
    if is_regex:
        return bool(re.search(matcher, file_path))
    return _matches_glob(matcher, file_path)


# ── Session + state ───────────────────────────────────────────────────────────

def _resolve_session_key() -> str:
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    has_session_id = bool(session_id)
    if has_session_id:
        return session_id

    ppid = os.getppid()
    tmp = Path(tempfile.gettempdir())
    uuid_file = tmp / f".claude-session-{ppid}"

    has_existing_uuid = uuid_file.exists()
    if has_existing_uuid:
        stored = uuid_file.read_text().strip()
        is_stored_valid = bool(stored)
        if is_stored_valid:
            return stored

    new_key = uuid.uuid4().hex[:24]
    try:
        uuid_file.write_text(new_key)
    except OSError:
        return f"ppid_{ppid}"
    return new_key


def _state_dir() -> Path:
    tmp = Path(tempfile.gettempdir())
    session_key = _resolve_session_key()
    state_dir = tmp / ".claude-enforce-gate" / session_key
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _file_key(file_path: str) -> str:
    return hashlib.md5(file_path.encode()).hexdigest()[:16]


# ── Gate evaluation ───────────────────────────────────────────────────────────

def _resolve_behavior(gate: dict, defaults: dict) -> str:
    raw = gate.get("behavior", defaults.get("behavior", DEFAULT_BEHAVIOR))
    normalized = str(raw).lower().strip()
    is_known = normalized in VALID_BEHAVIORS
    return normalized if is_known else DEFAULT_BEHAVIOR


def _resolve_gate_time(gate: dict, defaults: dict) -> int:
    raw = gate.get("gate_time", defaults.get("gate_time", DEFAULT_GATE_TIME))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_GATE_TIME


def _compute_block_decision(state: dict, behavior: str, gate_time: int) -> bool:
    is_time_mode = behavior == "time"
    if is_time_mode:
        elapsed = time.time() - state.get("last_blocked_at", 0.0)
        should_block = elapsed >= gate_time
        return should_block
    attempts_so_far = state.get("attempts", 0)
    should_block = attempts_so_far % 2 == 0
    return should_block


def _build_updated_state(state: dict, behavior: str, did_block: bool) -> dict:
    updated_state = dict(state)
    is_time_mode = behavior == "time"
    if is_time_mode:
        if did_block:
            updated_state["last_blocked_at"] = time.time()
    else:
        updated_state["attempts"] = state.get("attempts", 0) + 1
    return updated_state


def _evaluate_and_update(state_path: Path, behavior: str, gate_time: int) -> bool:
    """
    Atomically read state, decide whether to block, persist updated state.
    Uses fcntl.flock for atomic read-modify-write on Unix/macOS.
    Returns True when this attempt should be blocked.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with open(state_path, "a+") as state_file:
        fcntl.flock(state_file, fcntl.LOCK_EX)
        state_file.seek(0)
        raw_content = state_file.read().strip()

        is_empty = not raw_content
        default_state = {"attempts": 0, "last_blocked_at": 0.0}
        state = default_state if is_empty else json.loads(raw_content)

        do_block = _compute_block_decision(state, behavior, gate_time)
        new_state = _build_updated_state(state, behavior, do_block)

        state_file.seek(0)
        state_file.truncate()
        json.dump(new_state, state_file)

    return do_block


def _apply_gate(gate: dict, defaults: dict, file_path: str) -> None:
    gate_id = gate.get("id", "unknown")
    behavior = _resolve_behavior(gate, defaults)
    gate_time = _resolve_gate_time(gate, defaults)
    message = gate.get("message", f"[enforce-gate] Gate '{gate_id}' bloqueou este arquivo.")

    file_hash = _file_key(file_path)
    state_path = _state_dir() / f"{gate_id}_{file_hash}.json"

    is_blocked = _evaluate_and_update(state_path, behavior, gate_time)
    if is_blocked:
        print(message.rstrip())
        sys.exit(1)
    sys.exit(0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    has_file_path = bool(file_path)
    if not has_file_path:
        sys.exit(0)

    config_path = _find_config()
    has_config = config_path is not None
    if not has_config:
        sys.exit(0)

    config = _load_config(config_path)
    defaults = config.get("defaults", {})

    default_tools = defaults.get("tools", list(DEFAULT_TOOLS))
    is_intercepted_tool = tool_name in default_tools
    if not is_intercepted_tool:
        sys.exit(0)

    for gate in config.get("gates", []):
        is_enabled = gate.get("enabled", True)
        if not is_enabled:
            continue

        gate_tools = gate.get("tools", default_tools)
        is_tool_in_gate_scope = tool_name in gate_tools
        if not is_tool_in_gate_scope:
            continue

        is_match = _matches_gate(gate, file_path)
        if is_match:
            _apply_gate(gate, defaults, file_path)


if __name__ == "__main__":
    main()
