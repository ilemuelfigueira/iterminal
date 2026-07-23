# Spawning the pane

Run inside an existing tmux session. Substitute `<HANDOFF_PATH>` with the path from step 1 and `<PROMPT>` with the spawn arguments:

```bash
tmux split-window -h -c "#{pane_current_path}"
tmux send-keys 'claude --system-prompt "$(cat ~/.claude/contexts/dev.md; echo; cat <HANDOFF_PATH>)" "<PROMPT>"' Enter
```

The new session boots with the dev context and the handoff already in its system prompt, then acts on `<PROMPT>` as its first instruction.

## Why send-keys

Single-quote the `send-keys` argument so `$(cat …)` reaches the new pane's shell unexpanded and is substituted there. This keeps the multi-line system prompt out of the `tmux` command line, where quoting it would break.

## Variations

- Omit the trailing `"<PROMPT>"` when spawn received no arguments — the session opens on the handoff and waits.
- `-h` splits side by side; `-v` stacks the panes.
- `-c "#{pane_current_path}"` keeps the new pane in the same working directory.
- Escape any double quote inside `<PROMPT>` as `\"` so it survives the shell.

Outside tmux (`tmux display-message -p '#S'` errors), start a session first: `tmux new-session -d -s spawn`, and target it with `-t spawn`.
