#!/usr/bin/env bash
# enforce-gate.sh — PreToolUse hook: file-edit gates
#
# Gate 1  *.styles.ts          → block + design-system checklist (5 points)
# Gate 2  components|ui/*.tsx  → structured interrogation + AskUserQuestion gate
#
# Behaviour: blocks the FIRST attempt per file per session, outputs the gate
# message, then clears the gate so the next attempt passes (agent had a chance
# to read and comply with the rules).

set -euo pipefail

INPUT=$(cat)

parse_json_field() {
  local field="$1"
  echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('$field', '') or '')
"
}

parse_file_path() {
  echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
result = ti.get('file_path') or ti.get('path') or ''
print(result)
"
}

TOOL_NAME=$(parse_json_field "tool_name" 2>/dev/null) || TOOL_NAME=""
FILE_PATH=$(parse_file_path 2>/dev/null) || FILE_PATH=""

# Only intercept file-editing tools
case "$TOOL_NAME" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

[[ -z "$FILE_PATH" ]] && exit 0

# ── State management (per-session, per-file) ─────────────────────────────────
# Use CLAUDE_SESSION_ID when available; otherwise generate a UUID once per
# PPID lifecycle stored in a temp file (avoids PPID collision across sessions).
ENFORCE_GATE_TMP="${TMPDIR:-/tmp}"
SESSION_UUID_FILE="$ENFORCE_GATE_TMP/.claude-session-${PPID:-0}"
if [[ -z "${CLAUDE_SESSION_ID:-}" ]]; then
  if [[ ! -f "$SESSION_UUID_FILE" ]]; then
    python3 -c "import uuid; print(uuid.uuid4().hex[:24])" > "$SESSION_UUID_FILE" 2>/dev/null \
      || echo "ppid_${PPID:-0}" > "$SESSION_UUID_FILE"
  fi
  SESSION_KEY=$(cat "$SESSION_UUID_FILE" 2>/dev/null || echo "ppid_${PPID:-0}")
else
  SESSION_KEY="$CLAUDE_SESSION_ID"
fi
STATE_DIR="$ENFORCE_GATE_TMP/.claude-enforce-gate/$SESSION_KEY"
mkdir -p "$STATE_DIR"

FILE_KEY=$(echo -n "$FILE_PATH" | python3 -c "
import sys, hashlib
print(hashlib.md5(sys.stdin.read().encode()).hexdigest()[:16])
" 2>/dev/null) || FILE_KEY=$(echo -n "$FILE_PATH" | cksum | awk '{print $1}')

# ── GATE 1: *.styles.ts ──────────────────────────────────────────────────────
if echo "$FILE_PATH" | grep -qE '\.styles\.ts$'; then
  GATE_LOCK="$STATE_DIR/styles_${FILE_KEY}"
  # mkdir is atomic: succeeds only once, concurrent calls safely see EEXIST
  if mkdir "$GATE_LOCK" 2>/dev/null; then
    cat <<'MSG'
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
Ignorar estas perguntas é uma violação de Claude rules.
MSG
    exit 1
  fi
  exit 0
fi

# ── GATE 2: components|ui/*.tsx ──────────────────────────────────────────────
if echo "$FILE_PATH" | grep -qE '(components|ui)/[^/]+\.tsx$'; then
  GATE_LOCK="$STATE_DIR/ui_${FILE_KEY}"
  if mkdir "$GATE_LOCK" 2>/dev/null; then
    cat <<'MSG'
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
Na próxima tentativa este gate será liberado para esta sessão.
MSG
    exit 1
  fi
  exit 0
fi

exit 0
