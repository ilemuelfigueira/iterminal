# tmux-conf

Configurações pessoais do tmux baseadas no framework [gpakosz/.tmux](https://github.com/gpakosz/.tmux).

## Como funciona

O gpakosz/.tmux lê um arquivo `.local` ao iniciar. Este repo **é** esse arquivo local.
A variável `TMUX_CONF_LOCAL` diz ao gpakosz onde encontrá-lo — sem precisar de um
arquivo `~/.config/tmux/tmux.conf.local` em disco.

## Instalação

### 1. Instalar gpakosz/.tmux

Siga o [README oficial](https://github.com/gpakosz/.tmux#installation). O resultado esperado:

```sh
~/.config/tmux/tmux.conf -> /path/to/oh-my-tmux/.tmux.conf
```

### 2. Clonar este repo

```sh
git clone https://github.com/ilemuelfigueira/tmux-conf ~/projetos/ilemuelfigueira/tmux-conf
```

Pode clonar em qualquer caminho — ajuste o `TMUX_CONF_LOCAL` no passo seguinte.

### 3. Configurar TMUX_CONF_LOCAL

Adicionar no `~/.zshenv` (não `.zshrc` — precisa estar disponível para shells não-interativos):

```sh
echo 'export TMUX_CONF_LOCAL="$HOME/projetos/ilemuelfigueira/tmux-conf/tmux.conf"' >> ~/.zshenv
```

### 4. Evitar conflito do prefix2 C-s

O `prefix2 C-s` usa `Ctrl+S`, que por padrão congela o terminal (XOFF).
Desabilitar no `~/.zshrc`:

```sh
echo 'stty -ixon' >> ~/.zshrc
```

### 5. Aplicar

Abrir nova sessão tmux ou recarregar: `Prefix + r`

## O que está configurado

| Setting | Valor |
|---|---|
| `prefix2` | `C-s` (além do `C-b` padrão e `C-a` do gpakosz) |
| `escape-time` | 10ms (sem delay do Esc no vim) |
| `history-limit` | 50.000 linhas |
| `allow-passthrough` | on (protocolos de imagem e OSC sequences) |
| `xterm-keys` | on |
| `Alt+Esquerda/Direita` | pular palavra no terminal |
| Borda ativa | magenta (`colour_10 = #ff00af`) |
| Borda inativa | cyan (`colour_4 = #00afff`) |
