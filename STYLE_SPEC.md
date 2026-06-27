# iterminal Style Specification

Regras verificáveis para todos os assets de Claude Code neste repo.

## Tom

Técnico direto. Sem prólogo, sem rodapé, sem sycophancy.
Sem frases iniciando linha com: `Sure`, `Of course`, `Certainly`, `Absolutely`.

## Comprimento

Output styles: body (após o segundo `---`) ≤ 80 linhas.

## Locale

Spinner verbs em PT-BR. Máx 4 palavras por verb.

## Regras por tipo de asset

### Output styles (`claude-output-styles/*.md`)

| Campo | Regra |
|---|---|
| `name` | Obrigatório no frontmatter |
| `description` | Obrigatório no frontmatter, ≤ 120 chars |
| body | ≤ 80 linhas |
| sycophancy | Nenhuma linha começa com Sure / Of course / Certainly / Absolutely |

### Spinner verb packs (`claude-code-spinner-verbs/packs/*.json`)

| Campo | Regra |
|---|---|
| `name` | Obrigatório |
| `description` | Obrigatório |
| `verbs` | Array de strings, cada item não vazio e ≤ 4 palavras |
