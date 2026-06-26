# Install Copy Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace symlink creation with file copying in both link scripts and add a resilient `git pull` to `install.sh` so re-running it keeps `~/.claude/` in sync with the repo.

**Architecture:** Three bash script edits — `install.sh` gains a git pull preamble with guards, `link-claude-themes.sh` and `link-claude-output-styles.sh` drop symlink logic and use `cp -f` instead.

**Tech Stack:** Bash, git CLI

---

### Task 1: Update `link-claude-themes.sh` to copy instead of symlink

**Files:**
- Modify: `scripts/link-claude-themes.sh`

- [ ] **Step 1: Replace the script body**

Replace the full contents of `scripts/link-claude-themes.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$SCOPE" in
  user)  TARGET_DIR="$HOME/.claude/themes" ;;
  local) TARGET_DIR="$PWD/.claude/themes" ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

mkdir -p "$TARGET_DIR"

echo "==> claude themes -> $TARGET_DIR"
for file in "$REPO_DIR/claude-themes"/*.json; do
  target="$TARGET_DIR/$(basename "$file")"
  cp -f "$file" "$target"
  echo "  copied: $(basename "$file")"
done
```

- [ ] **Step 2: Verify the script runs without error**

```bash
bash scripts/link-claude-themes.sh user
```

Expected output contains lines like:
```
==> claude themes -> /Users/<you>/.claude/themes
  copied: root-loops.json
  ...
```

- [ ] **Step 3: Confirm files are real copies (not symlinks)**

```bash
ls -l ~/.claude/themes/
```

Expected: entries show `-rw-` permissions, not `l` (symlink).

- [ ] **Step 4: Commit**

```bash
git add scripts/link-claude-themes.sh
git commit -m "feat: copy theme files instead of symlinking"
```

---

### Task 2: Update `link-claude-output-styles.sh` to copy instead of symlink

**Files:**
- Modify: `scripts/link-claude-output-styles.sh`

- [ ] **Step 1: Replace the script body**

Replace the full contents of `scripts/link-claude-output-styles.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$SCOPE" in
  user)  TARGET_DIR="$HOME/.claude/output-styles" ;;
  local) TARGET_DIR="$PWD/.claude/output-styles" ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

mkdir -p "$TARGET_DIR"

echo "==> claude output-styles -> $TARGET_DIR"
for file in "$REPO_DIR/claude-output-styles"/*.md; do
  target="$TARGET_DIR/$(basename "$file")"
  cp -f "$file" "$target"
  echo "  copied: $(basename "$file")"
done
```

- [ ] **Step 2: Verify the script runs without error**

```bash
bash scripts/link-claude-output-styles.sh user
```

Expected output:
```
==> claude output-styles -> /Users/<you>/.claude/output-styles
  copied: architect.md
  ...
```

- [ ] **Step 3: Confirm files are real copies**

```bash
ls -l ~/.claude/output-styles/
```

Expected: entries show `-rw-` permissions, not `l`.

- [ ] **Step 4: Commit**

```bash
git add scripts/link-claude-output-styles.sh
git commit -m "feat: copy output-style files instead of symlinking"
```

---

### Task 3: Add resilient `git pull` to `install.sh`

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Replace the script body**

Replace the full contents of `install.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCOPE="${1:-user}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$REPO_DIR/scripts"

case "$SCOPE" in
  user|local) ;;
  *)
    echo "Usage: $0 [user|local]"
    exit 1
    ;;
esac

# Resilient git pull
if ! command -v git &>/dev/null; then
  echo "==> git not found, skipping pull"
elif ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
  echo "==> not a git repo, skipping pull"
else
  echo "==> git pull"
  git -C "$REPO_DIR" pull || echo "  warning: git pull failed, continuing with local files"
fi

bash "$SCRIPTS_DIR/link-claude-themes.sh" "$SCOPE"
bash "$SCRIPTS_DIR/link-claude-output-styles.sh" "$SCOPE"
```

- [ ] **Step 2: Run install.sh and verify full output**

```bash
bash install.sh user
```

Expected output (roughly):
```
==> git pull
Already up to date.
==> claude themes -> /Users/<you>/.claude/themes
  copied: root-loops.json
  ...
==> claude output-styles -> /Users/<you>/.claude/output-styles
  copied: architect.md
  ...
```

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: add resilient git pull to install.sh"
```
