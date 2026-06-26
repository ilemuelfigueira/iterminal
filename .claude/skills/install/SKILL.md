---
name: install
description: Install components from the iterminal repo — Claude themes, output-styles, spinner verb packs, iTerm2 themes, tmux config, and Powerline font. Use when user says "install", "instalar", "setup", "configurar repo", "como instalar", "install themes", "install spinner verbs", "instalar temas".
---

# Install iterminal Components

Identify which component the user wants to install, then run the appropriate command below.

## 1 — Claude Themes + Output Styles

Copies JSON theme files to `~/.claude/themes/` and MD files to `~/.claude/output-styles/`.

```bash
./install.sh user    # installs to ~/.claude (global)
./install.sh local   # installs to ./.claude (current project)
```

Run from the repo root. Default scope is `user`.

## 2 — Spinner Verb Packs

Merges or replaces `spinnerVerbs` in `~/.claude/settings.json`.

```bash
cd claude-code-spinner-verbs

./install.sh --list                         # show available packs
./install.sh cassino                        # append cassino verbs
./install.sh naruto --mode replace          # replace all verbs with naruto pack
./install.sh filosofo-dev --preview        # preview without writing
```

Available packs: `cassino`, `naruto`, `filosofo-dev`.  
After installing, run `/clear` or start a new Claude session to apply.

## 3 — iTerm2 Themes

Double-click any `.itermcolors` file in `iterm-themes/`, or import via:
`iTerm2 → Preferences → Profiles → Colors → Color Presets → Import`

Available themes: `github-dark`, `gotham-default`, `moonfly-default`, `root-loops*`, `srcery-default`.

## 4 — tmux Config

Add to `~/.zshenv` (not `.zshrc` — must be available to non-interactive shells):

```bash
echo 'export TMUX_CONF_LOCAL="/path/to/iterminal/tmux.conf"' >> ~/.zshenv
```

Then open a new tmux session or reload with `Prefix + r`.

Also disable `Ctrl+S` freeze in `~/.zshrc`:
```bash
echo 'stty -ixon' >> ~/.zshrc
```

## 5 — Powerline Font

```bash
cp .fonts/PowerlineSymbols.otf ~/Library/Fonts/
```

Then select `PowerlineSymbols` in iTerm2 → Preferences → Profiles → Text → Non-ASCII Font.

---

When the user does not specify a component, ask which one they want before running any command.
