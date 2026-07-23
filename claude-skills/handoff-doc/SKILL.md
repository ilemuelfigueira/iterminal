---
name: handoff-doc
description: Write a handoff document compacting the current conversation so a fresh agent can continue the work. Use when another skill needs to produce a handoff, or when the user wants the current session compacted, summarised for a successor, or continued elsewhere.
argument-hint: "What will the next session be used for?"
user-invocable: false
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save it to the temporary directory of the user's OS, leaving the workspace untouched.

Include a "suggested skills" section naming the skills the next agent should invoke.

Reference content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs) by path or URL, keeping the document to what only this conversation holds.

Redact sensitive information, such as API keys, passwords, or personally identifiable information.

Treat any arguments passed as a description of what the next session will focus on, and tailor the document accordingly.

Report the absolute path of the file you wrote — callers depend on it.
