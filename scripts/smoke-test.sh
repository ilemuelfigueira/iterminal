#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "==> smoke-test: rodando install.sh local em $TMP_DIR"
# HOME=$TMP_DIR isola a cópia dos hook scripts (install.py escreve em ~/.claude/hooks)
(cd "$TMP_DIR" && HOME="$TMP_DIR" bash "$REPO_DIR/install.sh" local 2>&1)

ERRORS=0

echo "==> smoke-test: verificando themes"
for file in "$REPO_DIR/claude-themes"/*.json; do
  [[ -f "$file" ]] || continue
  target="$TMP_DIR/.claude/themes/$(basename "$file")"
  if [[ ! -f "$target" ]]; then
    echo "  FAIL: themes/$(basename "$file") não foi copiado"
    ERRORS=$((ERRORS + 1))
  fi
done

echo "==> smoke-test: verificando output-styles"
for file in "$REPO_DIR/claude-output-styles"/*.md; do
  [[ -f "$file" ]] || continue
  target="$TMP_DIR/.claude/output-styles/$(basename "$file")"
  if [[ ! -f "$target" ]]; then
    echo "  FAIL: output-styles/$(basename "$file") não foi copiado"
    ERRORS=$((ERRORS + 1))
  fi
done

echo "==> smoke-test: verificando hook scripts copiados"
for hook in enforce-gate.py pre-edit-lint.py; do
  target="$TMP_DIR/.claude/hooks/$hook"
  if [[ ! -f "$target" ]]; then
    echo "  FAIL: hooks/$hook não foi copiado"
    ERRORS=$((ERRORS + 1))
  fi
done

echo "==> smoke-test: verificando registro no settings.json"
SETTINGS="$TMP_DIR/.claude/settings.json"
if [[ ! -f "$SETTINGS" ]]; then
  echo "  FAIL: settings.json não foi criado"
  ERRORS=$((ERRORS + 1))
else
  for hook in enforce-gate.py pre-edit-lint.py; do
    if ! jq -e --arg h "$hook" \
      '[.hooks[]?[]?.hooks[]?.command | select(type == "string") | select(contains($h))] | length > 0' \
      "$SETTINGS" > /dev/null 2>&1; then
      echo "  FAIL: $hook não registrado em settings.json"
      ERRORS=$((ERRORS + 1))
    fi
  done
fi

echo ""
if [[ "$ERRORS" -gt 0 ]]; then
  echo "smoke-test: $ERRORS falha(s)"
  exit 1
fi
echo "smoke-test: ok"
