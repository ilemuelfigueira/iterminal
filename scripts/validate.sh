#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERRORS=0

# Gate 1: shellcheck
echo "==> shellcheck"
if command -v shellcheck &>/dev/null; then
  while IFS= read -r -d '' file; do
    if ! shellcheck "$file"; then
      ERRORS=$((ERRORS + 1))
    fi
  done < <(find "$REPO_DIR" -name "*.sh" -not -path "*/.git/*" -print0)
else
  echo "  aviso: shellcheck não encontrado — pulando (brew install shellcheck)"
fi

# Gate 2: spinner verb packs
echo "==> spinner verb packs"
for file in "$REPO_DIR/claude-code-spinner-verbs/packs"/*.json; do
  [[ -f "$file" ]] || continue
  pack_name="$(basename "$file")"

  if ! jq empty "$file" 2>/dev/null; then
    echo "  FAIL: $pack_name — JSON inválido"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  for field in name description verbs; do
    if ! jq -e ".$field" "$file" > /dev/null 2>&1; then
      echo "  FAIL: $pack_name — campo '$field' ausente"
      ERRORS=$((ERRORS + 1))
    fi
  done

  while IFS= read -r verb; do
    if [[ -z "$verb" ]]; then
      echo "  FAIL: $pack_name — verb vazio"
      ERRORS=$((ERRORS + 1))
      continue
    fi
    word_count=$(echo "$verb" | wc -w | tr -d '[:space:]')
    if [[ "$word_count" -gt 4 ]]; then
      echo "  FAIL: $pack_name — verb '$verb' excede 4 palavras ($word_count)"
      ERRORS=$((ERRORS + 1))
    fi
  done < <(jq -r '.verbs[]' "$file")
done

# Gate 3: output styles
echo "==> output styles"
for file in "$REPO_DIR/claude-output-styles"/*.md; do
  [[ -f "$file" ]] || continue
  style_name="$(basename "$file")"

  if ! grep -q '^name:' "$file"; then
    echo "  FAIL: $style_name — frontmatter 'name' ausente"
    ERRORS=$((ERRORS + 1))
  fi

  if ! grep -q '^description:' "$file"; then
    echo "  FAIL: $style_name — frontmatter 'description' ausente"
    ERRORS=$((ERRORS + 1))
  else
    desc=$(grep '^description:' "$file" | head -1 | sed 's/^description:[[:space:]]*//')
    desc_len=${#desc}
    if [[ "$desc_len" -gt 120 ]]; then
      echo "  FAIL: $style_name — description excede 120 chars ($desc_len)"
      ERRORS=$((ERRORS + 1))
    fi
  fi

  body_lines=$(awk '/^---$/{count++; if(count==2){found=1; next}} found{print}' "$file" | wc -l | tr -d '[:space:]')
  if [[ "$body_lines" -gt 80 ]]; then
    echo "  FAIL: $style_name — body excede 80 linhas ($body_lines)"
    ERRORS=$((ERRORS + 1))
  fi

  for marker in "Sure" "Of course" "Certainly" "Absolutely"; do
    if grep -q "^${marker}" "$file"; then
      echo "  FAIL: $style_name — marcador de sycophancy '$marker' no início de linha"
      ERRORS=$((ERRORS + 1))
    fi
  done
done

echo ""
if [[ "$ERRORS" -gt 0 ]]; then
  echo "validate: $ERRORS erro(s) encontrado(s)"
  exit 1
fi
echo "validate: ok"
