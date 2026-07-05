#!/usr/bin/env python3
"""
enforce-gate.py — PreToolUse hook: file-edit gates

Gate 1: *.styles.ts          → design-system checklist (5 points)
Gate 2: components|ui/*.tsx  → structured interrogation + AskUserQuestion gate

Environment variables:
  CLAUDE_ENFORCE_GATE_BEHAVIOR  one-shot (default) | time
  CLAUDE_ENFORCE_GATE_TIME      seconds until gate resets in time mode (default: 30)

Behaviors:
  one-shot  block → pass → block → pass → ... (alternates per file per session)
  time      block, pass until GATE_TIME seconds elapse since last block, then block again
"""

import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

GATE1_MSG = """\
╔══════════════════════════════════════════════════════════════════════╗
║  🚫  ENFORCE GATE — Arquivo de Estilos Protegido (*.styles.ts)      ║
╚══════════════════════════════════════════════════════════════════════╝

Edição BLOQUEADA nesta tentativa. Antes de tentar novamente, você DEVE
responder os 5 pontos abaixo no seu próximo turno:

  1. FATOS    → Quais fatos concretos justificam editar este arquivo agora?
  2. MOTIVO   → Qual é o motivo específico e preciso da modificação?
  3. REGRAS   → Esta edição quebra alguma Claude rule?
                Liste explicitamente cada rule afetada.
  4. CERTEZA  → Você tem certeza absoluta que este arquivo precisa ser alterado?
  5. TOKEN    → ⚠️  Estilos inline NÃO são permitidos.
                 Qual token do design system será utilizado?
                 (ex: colors.primary.500, spacing.md, typography.heading.lg)

Na próxima tentativa este gate será liberado para esta sessão.
Ignorar estas perguntas é uma violação de Claude rules."""

GATE2_MSG = """\
╔══════════════════════════════════════════════════════════════════════╗
║  🔍  ENFORCE GATE — Componente UI Protegido (components|ui/*.tsx)   ║
╚══════════════════════════════════════════════════════════════════════╝

Edição BLOQUEADA nesta tentativa. Antes de tentar novamente, você DEVE:

  a) MOTIVO     → Qual é o motivo da modificação neste componente?
                  (responda diretamente no próximo turno)

  b) IMPACTO    → Quais outros arquivos/componentes serão impactados?
                  (liste cada caminho explicitamente)

  c) REGRAS     → Esta alteração quebra alguma Claude rule?
                  ⚠️  Se SIM → use AskUserQuestion AGORA para obter
                      consentimento explícito antes de prosseguir.
                      NÃO edite sem resposta afirmativa do usuário.

  d) DESIGN     → Esta modificação está prevista no design system?
                  ✅ Se SIM  → informe o token do design system a usar.
                               (ex: Button.variant.primary, Card.shadow.md)
                  ❌ Se NÃO → trate como quebra de regra (→ item c):
                               use AskUserQuestion antes de continuar.

Responda a) e b) no próximo turno.
Para c) e d), acione AskUserQuestion conforme indicado acima.
Na próxima tentativa este gate será liberado para esta sessão."""

EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit"})
VALID_BEHAVIORS = frozenset({"one-shot", "time"})
DEFAULT_GATE_TIME_SECONDS = 30
DEFAULT_BEHAVIOR = "one-shot"


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
    Returns True when the gate should block this attempt.
    Uses fcntl.flock for atomic read-modify-write on Unix/macOS.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with open(state_path, "a+") as state_file:
        fcntl.flock(state_file, fcntl.LOCK_EX)
        state_file.seek(0)
        raw_content = state_file.read().strip()

        is_state_empty = not raw_content
        default_state = {"attempts": 0, "last_blocked_at": 0.0}
        state = default_state if is_state_empty else json.loads(raw_content)

        do_block = _compute_block_decision(state, behavior, gate_time)
        new_state = _build_updated_state(state, behavior, do_block)

        state_file.seek(0)
        state_file.truncate()
        json.dump(new_state, state_file)

    return do_block


def _run_gate(gate_prefix: str, message: str, behavior: str, gate_time: int) -> None:
    state_path = _state_dir() / f"{gate_prefix}.json"
    is_blocked = _evaluate_and_update(state_path, behavior, gate_time)
    if is_blocked:
        print(message)
        sys.exit(1)
    sys.exit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    is_edit_tool = tool_name in EDIT_TOOLS
    if not is_edit_tool:
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    has_file_path = bool(file_path)
    if not has_file_path:
        sys.exit(0)

    raw_behavior = os.environ.get("CLAUDE_ENFORCE_GATE_BEHAVIOR", DEFAULT_BEHAVIOR).lower().strip()
    is_known_behavior = raw_behavior in VALID_BEHAVIORS
    behavior = raw_behavior if is_known_behavior else DEFAULT_BEHAVIOR

    gate_time = DEFAULT_GATE_TIME_SECONDS
    is_time_mode = behavior == "time"
    if is_time_mode:
        try:
            gate_time = int(os.environ.get("CLAUDE_ENFORCE_GATE_TIME", str(DEFAULT_GATE_TIME_SECONDS)))
        except ValueError:
            gate_time = DEFAULT_GATE_TIME_SECONDS

    file_hash = _file_key(file_path)

    is_styles_file = bool(re.search(r"\.styles\.ts$", file_path))
    if is_styles_file:
        _run_gate(f"styles_{file_hash}", GATE1_MSG, behavior, gate_time)

    is_ui_component = bool(re.search(r"(components|ui)/[^/]+\.tsx$", file_path))
    if is_ui_component:
        _run_gate(f"ui_{file_hash}", GATE2_MSG, behavior, gate_time)


if __name__ == "__main__":
    main()
