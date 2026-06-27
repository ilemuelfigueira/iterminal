# iterminal Style Specification

Regras verificáveis para todos os assets de Claude Code neste repo.
Body = conteúdo após o segundo `---` delimitador YAML no frontmatter.

## Tom

Técnico direto. Sem prólogo, sem rodapé, sem sycophancy.
Regras verificáveis estão nas tabelas abaixo.

## Regras por tipo de asset

### Output styles (`claude-output-styles/*.md`)

| Campo | Regra |
|---|---|
| `name` | Obrigatório, string não vazia |
| `description` | Obrigatório, ≤ 120 chars |
| body | ≤ 80 linhas |
| sycophancy | Nenhuma linha começa com Sure / Of course / Certainly / Absolutely |

### Spinner verb packs (`claude-code-spinner-verbs/packs/*.json`)

| Campo | Regra |
|---|---|
| `name` | Obrigatório, string não vazia |
| `description` | Obrigatório |
| `verbs` | Array de strings, cada item não vazio e ≤ 4 palavras |
| locale | Strings em PT-BR |
