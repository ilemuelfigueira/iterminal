#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_DIR/.git/hooks"
HOOK_FILE="$HOOKS_DIR/pre-push"

if [[ ! -d "$HOOKS_DIR" ]]; then
  echo "  aviso: .git/hooks não encontrado — não é um repo git ou hooks desabilitados"
  exit 0
fi

cat > "$HOOK_FILE" << 'HOOK'
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> pre-push: validate"
bash "$REPO_DIR/scripts/validate.sh" || { echo "pre-push: abortado (validate falhou)"; exit 1; }

echo "==> pre-push: smoke-test"
bash "$REPO_DIR/scripts/smoke-test.sh" || { echo "pre-push: abortado (smoke-test falhou)"; exit 1; }

echo "==> pre-push: ok — push autorizado"
HOOK

chmod +x "$HOOK_FILE"
echo "==> hook instalado: $HOOK_FILE"
