# Install Script — Copy Sync Design

**Date:** 2026-06-25

## Goal

Replace symlink creation with file copying in both link scripts so that `~/.claude/themes/` and `~/.claude/output-styles/` always reflect the latest repo state after running `install.sh`. Add a resilient `git pull` at the top of `install.sh`.

## Behavior

Running `install.sh` will:
1. Pull the latest repo changes (if `git` is available and the directory is a git repo)
2. Copy all `.json` files from `claude-themes/` into `~/.claude/themes/`
3. Copy all `.md` files from `claude-output-styles/` into `~/.claude/output-styles/`

Files in the target directories are always overwritten so re-running `install.sh` after a `git pull` keeps Claude config in sync.

## Changes

### `install.sh`

Prepend a resilient git pull block:
- Check `command -v git` — skip pull entirely if git is not installed (warn only)
- Check `git -C "$REPO_DIR" rev-parse --is-inside-work-tree` — skip if not a git repo (warn only)
- Run `git -C "$REPO_DIR" pull` — on failure, warn and continue (do not abort install)

Then run both scripts as before.

### `scripts/link-claude-themes.sh`

- Remove: symlink creation (`ln -s`), "already linked" branch, "skipped (file exists)" branch, source-symlink guard
- Add: `cp -f "$file" "$target"` with a "copied" log line
- Log label change: "linked" → "copied"

### `scripts/link-claude-output-styles.sh`

- Remove: symlink creation (`ln -sf`), "already linked" check, source-symlink guard
- Add: `cp -f "$file" "$target"` with a "copied" log line
- Log label change: "linked" → "copied"

## Non-goals

- No diff/checksum comparison before copying (always overwrite)
- No backup of existing target files before overwrite
- No support for scopes beyond `user` and `local`
