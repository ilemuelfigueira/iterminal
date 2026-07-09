#!/usr/bin/env python3
"""
enforce-gate.py — YAML-driven generic Claude Code hook engine

Supports all Claude Code hook types: PreToolUse, PostToolUse,
UserPromptSubmit, Stop, Notification (and any future types).

Config resolution — ALL found sources are merged (no "first wins"):
  1. ~/.claude/enforce-gates.yml     (global/user, weakest)
  2. .claude/enforce-gates.yml       (project-local overlay)
  3. $CLAUDE_ENFORCE_GATE_CONFIG     (explicit override, strongest)

Merge rules:
  defaults  → shallow merge; stronger source wins per key
  gates     → concatenated; gates with same id: stronger source replaces weaker

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
DEFAULT_HOOK_TYPES = ["PreToolUse"]
DEFAULT_BLOCK_EXIT_CODE = 2
VALID_BEHAVIORS = frozenset({"one-shot", "time"})

HOOK_TYPE_ENV_VAR = "CLAUDE_HOOK_TYPE"


# ── Config resolution (merge) ─────────────────────────────────────────────────

def _collect_config_sources() -> list:
    sources = []

    global_config = Path.home() / ".claude" / "enforce-gates.yml"
    is_global_present = global_config.exists()
    if is_global_present:
        sources.append(global_config)

    project_local = Path(".claude") / "enforce-gates.yml"
    is_project_local_present = project_local.exists()
    if is_project_local_present:
        sources.append(project_local)

    env_path = os.environ.get("CLAUDE_ENFORCE_GATE_CONFIG", "")
    has_env_path = bool(env_path)
    if has_env_path:
        candidate = Path(env_path)
        is_env_path_valid = candidate.exists()
        if is_env_path_valid:
            sources.append(candidate)

    return sources


def _load_raw_config(config_path: Path) -> dict:
    with open(config_path) as config_file:
        return yaml.safe_load(config_file) or {}


def _load_merged_config() -> dict | None:
    sources = _collect_config_sources()
    has_sources = bool(sources)
    if not has_sources:
        return None

    merged_defaults = {}
    gates_by_id: dict = {}

    for config_path in sources:
        raw = _load_raw_config(config_path)
        merged_defaults.update(raw.get("defaults", {}))
        for gate in raw.get("gates", []):
            gate_id = gate.get("id", str(id(gate)))
            gates_by_id[gate_id] = gate

    merged_config = {
        "defaults": merged_defaults,
        "gates": list(gates_by_id.values()),
    }
    return merged_config


# ── Hook type detection ───────────────────────────────────────────────────────

def _detect_hook_type(payload: dict) -> str:
    env_hook_type = os.environ.get(HOOK_TYPE_ENV_VAR, "")
    has_env_hook_type = bool(env_hook_type)
    if has_env_hook_type:
        return env_hook_type

    has_tool_name = "tool_name" in payload
    has_tool_response = "tool_response" in payload

    is_post_tool_use = has_tool_name and has_tool_response
    if is_post_tool_use:
        return "PostToolUse"

    is_pre_tool_use = has_tool_name and not has_tool_response
    if is_pre_tool_use:
        return "PreToolUse"

    has_prompt = "prompt" in payload
    if has_prompt:
        return "UserPromptSubmit"

    has_stop_reason = "stop_reason" in payload
    if has_stop_reason:
        return "Stop"

    has_notification_type = "notification_type" in payload
    if has_notification_type:
        return "Notification"

    return "Unknown"


# ── Trigger value extraction ──────────────────────────────────────────────────

def _extract_trigger_value(hook_type: str, payload: dict, gate: dict) -> str:
    trigger = gate.get("trigger", {})
    trigger_field = trigger.get("field", "")

    has_explicit_field = bool(trigger_field)
    if has_explicit_field:
        return str(payload.get(trigger_field, ""))

    is_pre_tool_use = hook_type == "PreToolUse"
    is_post_tool_use = hook_type == "PostToolUse"
    is_file_based = is_pre_tool_use or is_post_tool_use
    if is_file_based:
        tool_input = payload.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        return file_path

    is_user_prompt_submit = hook_type == "UserPromptSubmit"
    if is_user_prompt_submit:
        return str(payload.get("prompt", ""))

    is_stop = hook_type == "Stop"
    if is_stop:
        return str(payload.get("stop_reason", ""))

    is_notification = hook_type == "Notification"
    if is_notification:
        return str(payload.get("notification_type", ""))

    return ""


# ── Gate matching ─────────────────────────────────────────────────────────────

def _matches_glob(pattern: str, value: str) -> bool:
    has_path_separator = "/" in pattern
    if has_path_separator:
        return fnmatch.fnmatch(value, pattern)
    return fnmatch.fnmatch(os.path.basename(value), pattern)


def _resolve_pattern(gate: dict) -> str:
    trigger = gate.get("trigger", {})
    trigger_pattern = trigger.get("pattern", "")
    has_trigger_pattern = bool(trigger_pattern)
    if has_trigger_pattern:
        return trigger_pattern
    return gate.get("matcher", "")


def _resolve_matcher_type(gate: dict) -> str:
    trigger = gate.get("trigger", {})
    trigger_matcher_type = trigger.get("matcher_type", "")
    has_trigger_matcher_type = bool(trigger_matcher_type)
    if has_trigger_matcher_type:
        return trigger_matcher_type.lower()
    return gate.get("matcher_type", "glob").lower()


def _matches_gate(gate: dict, trigger_value: str) -> bool:
    pattern = _resolve_pattern(gate)
    matcher_type = _resolve_matcher_type(gate)

    is_regex = matcher_type == "regex"
    if is_regex:
        return bool(re.search(pattern, trigger_value))
    return _matches_glob(pattern, trigger_value)


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


def _value_key(trigger_value: str) -> str:
    return hashlib.md5(trigger_value.encode()).hexdigest()[:16]


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


def _resolve_block_exit_code(gate: dict, defaults: dict) -> int:
    raw = gate.get("block_exit_code", defaults.get("block_exit_code", DEFAULT_BLOCK_EXIT_CODE))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_BLOCK_EXIT_CODE


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


def _apply_gate(gate: dict, defaults: dict, trigger_value: str) -> None:
    gate_id = gate.get("id", "unknown")
    behavior = _resolve_behavior(gate, defaults)
    gate_time = _resolve_gate_time(gate, defaults)
    block_exit_code = _resolve_block_exit_code(gate, defaults)
    message = gate.get("message", f"[enforce-gate] Gate '{gate_id}' bloqueou esta acao.")

    value_hash = _value_key(trigger_value)
    state_path = _state_dir() / f"{gate_id}_{value_hash}.json"

    is_blocked = _evaluate_and_update(state_path, behavior, gate_time)
    if is_blocked:
        print(message.rstrip())
        sys.exit(block_exit_code)
    sys.exit(0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    hook_type = _detect_hook_type(payload)

    config = _load_merged_config()
    has_config = config is not None
    if not has_config:
        sys.exit(0)

    defaults = config.get("defaults", {})
    default_tools = defaults.get("tools", list(DEFAULT_TOOLS))

    is_tool_based_hook = hook_type in ("PreToolUse", "PostToolUse")
    if is_tool_based_hook:
        tool_name = payload.get("tool_name", "")
        is_intercepted_tool = tool_name in default_tools
        if not is_intercepted_tool:
            sys.exit(0)

    for gate in config.get("gates", []):
        is_enabled = gate.get("enabled", True)
        if not is_enabled:
            continue

        gate_hook_types = gate.get("hook_types", DEFAULT_HOOK_TYPES)
        is_hook_type_in_scope = hook_type in gate_hook_types
        if not is_hook_type_in_scope:
            continue

        if is_tool_based_hook:
            tool_name = payload.get("tool_name", "")
            gate_tools = gate.get("tools", default_tools)
            is_tool_in_gate_scope = tool_name in gate_tools
            if not is_tool_in_gate_scope:
                continue

        trigger_value = _extract_trigger_value(hook_type, payload, gate)
        has_trigger_value = bool(trigger_value)
        if not has_trigger_value:
            continue

        is_match = _matches_gate(gate, trigger_value)
        if is_match:
            _apply_gate(gate, defaults, trigger_value)


if __name__ == "__main__":
    main()
