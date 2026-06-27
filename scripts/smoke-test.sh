#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "==> smoke-test: rodando install.sh local em $TMP_DIR"
(cd "$TMP_DIR" && bash "$REPO_DIR/install.sh" local 2>&1)

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

echo ""
if [[ "$ERRORS" -gt 0 ]]; then
  echo "smoke-test: $ERRORS arquivo(s) não copiado(s)"
  exit 1
fi
echo "smoke-test: ok"
