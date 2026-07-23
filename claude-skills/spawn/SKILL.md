---
name: spawn
description: Hand off the current conversation and open it in a fresh Claude session in a new tmux pane.
argument-hint: "What the spawned session should work on"
disable-model-invocation: true
---

Spawn a fresh session that continues this work in a new tmux pane.

Arguments do double duty: they focus the handoff, and become the spawned session's opening prompt.

## Steps

1. **Produce the handoff.** Invoke the `handoff-doc` skill via the Skill tool, passing the arguments through as the next session's focus. It writes the document to the OS temp directory and reports the path.
   - Done when: you hold the absolute path to the handoff file it wrote.

2. **Spawn the pane.** Split a new tmux pane and start `claude` there with a system prompt concatenating `~/.claude/contexts/dev.md` and the handoff, passing the arguments as its opening prompt — see [references/spawn-pane.md](references/spawn-pane.md) for the command sequence.
   - Done when: the split pane exists and `claude` has started on the opening prompt.
