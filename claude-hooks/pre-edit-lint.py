#!/usr/bin/env python3
"""
pre-edit-lint.py — PreToolUse hook that lints PROPOSED content before
Edit/Write/MultiEdit is applied to disk.

Writes the proposed content to a temp file in the same directory as the
target (so ESLint resolves the project config correctly), lints it, then
deletes the temp file. Blocks the tool call with exit 2 on any ESLint error.

Note: --stdin with @typescript-eslint/parser + parserOptions.project is
ignored — the parser reads from disk regardless of stdin. A real temp file
in the same directory is the only reliable approach for project-aware rules.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Configuration (env vars — all optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ESLINT_HOOK_DISABLED        Set to "1" to skip entirely.
  ESLINT_HOOK_MODE            "stdin" (default) or "tempfile".
                              stdin: pipes content via --stdin with ESLINT_HOOK=1
                                     env so .eslintrc.js can skip parserOptions.project.
                              tempfile: writes a real temp file (legacy; use when the
                                     project .eslintrc does not support ESLINT_HOOK).
  ESLINT_HOOK_EXTENSIONS      Comma-separated extensions to lint.
                              Default: .ts,.tsx,.js,.jsx,.mts,.cts,.mjs,.cjs
  ESLINT_HOOK_BIN             Explicit path to eslint binary.
  ESLINT_HOOK_MAX_WARNINGS    Warnings allowed before blocking. Default: -1.
  ESLINT_HOOK_TIMEOUT         Seconds before giving up. Default: 15.
  ESLINT_HOOK_EXTRA_ARGS      Extra flags appended to the eslint command.
  ESLINT_HOOK_WORKING_DIR     Override cwd for binary discovery.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Exit codes (PreToolUse)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  0 — allow edit
  2 — BLOCK edit (ESLint found errors in the proposed content)

  Exit 1 is intentionally avoided: Claude Code treats it as non-blocking
  in PreToolUse context, allowing the edit to proceed anyway.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_EXTENSIONS: frozenset[str] = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"}
)
DEFAULT_TIMEOUT_SECONDS: int = 15
DEFAULT_MAX_WARNINGS: int = -1


def _load_project_env(project_root: Path) -> None:
    env_file = project_root / ".claude" / "lint-hook.env"
    is_present = env_file.is_file()
    if not is_present:
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        is_comment = stripped.startswith("#")
        is_empty = not stripped
        if is_comment or is_empty:
            continue
        has_equals = "=" in stripped
        if not has_equals:
            continue
        key, _, value = stripped.partition("=")
        is_already_set = key.strip() in os.environ
        if not is_already_set:
            os.environ[key.strip()] = value.strip()


def _env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    is_empty = not raw
    if is_empty:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _find_eslint_bin(working_dir: Path) -> str | None:
    explicit_bin = _env_str("ESLINT_HOOK_BIN")
    is_explicit = bool(explicit_bin)
    if is_explicit:
        is_executable = os.access(explicit_bin, os.X_OK)
        return explicit_bin if is_executable else None

    current = working_dir.resolve()
    while True:
        candidate = current / "node_modules" / ".bin" / "eslint"
        is_found = candidate.is_file() and os.access(str(candidate), os.X_OK)
        if is_found:
            return str(candidate)
        parent = current.parent
        is_root = parent == current
        if is_root:
            break
        current = parent

    return shutil.which("eslint")


def _build_extensions(raw: str) -> frozenset[str]:
    is_empty = not raw.strip()
    if is_empty:
        return DEFAULT_EXTENSIONS
    parts = {ext.strip().lstrip("*") for ext in raw.split(",") if ext.strip()}
    normalized = {ext if ext.startswith(".") else f".{ext}" for ext in parts}
    return frozenset(normalized)


def _is_lintable(file_path: Path, extensions: frozenset[str]) -> bool:
    return file_path.suffix in extensions


def _apply_edit(content: str, old_string: str, new_string: str) -> str:
    return content.replace(old_string, new_string, 1)


def _resolve_proposed_content(tool_input: dict, file_path: Path) -> str:
    is_write = "content" in tool_input
    if is_write:
        return tool_input["content"]

    current_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""

    is_multi_edit = "edits" in tool_input
    if is_multi_edit:
        proposed = current_content
        for edit in tool_input.get("edits", []):
            proposed = _apply_edit(proposed, edit.get("old_string", ""), edit.get("new_string", ""))
        return proposed

    return _apply_edit(
        current_content,
        tool_input.get("old_string", ""),
        tool_input.get("new_string", ""),
    )


ESLINT_HOOK_MODE_STDIN: str = "stdin"
ESLINT_HOOK_MODE_TEMPFILE: str = "tempfile"


def _run_eslint_via_stdin(
    eslint_bin: str,
    file_path: Path,
    proposed_content: str,
    max_warnings: int,
    timeout: int,
    extra_args: list[str],
    working_dir: Path,
) -> tuple[int, str, str]:
    """
    Pipe proposed_content to ESLint via stdin with ESLINT_HOOK=1 in the
    subprocess environment. That env var causes .eslintrc.js to skip
    parserOptions.project, allowing the @typescript-eslint/parser to parse
    stdin directly without needing a real file on disk.
    """
    stdin_filename = str(file_path) if file_path.is_absolute() else str(working_dir / file_path)

    command: list[str] = [
        eslint_bin,
        "--stdin",
        f"--stdin-filename={stdin_filename}",
        "--format",
        "stylish",
    ]

    has_max_warnings_flag = max_warnings >= 0
    if has_max_warnings_flag:
        command += ["--max-warnings", str(max_warnings)]

    has_extra_args = bool(extra_args)
    if has_extra_args:
        command += extra_args

    hook_env = {**os.environ, "ESLINT_HOOK": "1"}

    try:
        result = subprocess.run(
            command,
            input=proposed_content,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(working_dir),
            env=hook_env,
        )
        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        return 0, "", f"[pre-edit-lint] ESLint timed out after {timeout}s — allowing edit."
    except FileNotFoundError:
        return 0, "", f"[pre-edit-lint] Binary not found — allowing edit."
    except OSError as exc:
        return 0, "", f"[pre-edit-lint] Failed to run ESLint: {exc} — allowing edit."


def _run_eslint_via_tempfile(
    eslint_bin: str,
    file_path: Path,
    proposed_content: str,
    max_warnings: int,
    timeout: int,
    extra_args: list[str],
    working_dir: Path,
) -> tuple[int, str, str]:
    """
    Write proposed_content to a temp file in the same directory as file_path,
    run ESLint on it, then delete it. Fallback for projects whose .eslintrc
    does not support ESLINT_HOOK env-based project bypass.
    """
    target_dir = file_path.parent if file_path.parent.exists() else working_dir
    name = file_path.name
    first_dot = name.find(".")
    suffix = name[first_dot:] if first_dot >= 0 else (file_path.suffix or ".ts")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            dir=str(target_dir),
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(proposed_content)
            tmp_path = tmp.name

        command: list[str] = [eslint_bin, tmp_path, "--format", "stylish"]

        has_max_warnings_flag = max_warnings >= 0
        if has_max_warnings_flag:
            command += ["--max-warnings", str(max_warnings)]

        has_extra_args = bool(extra_args)
        if has_extra_args:
            command += extra_args

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(working_dir),
        )
        clean_stdout = result.stdout.replace(tmp_path, str(file_path))
        return result.returncode, clean_stdout, result.stderr

    except subprocess.TimeoutExpired:
        return 0, "", f"[pre-edit-lint] ESLint timed out after {timeout}s — allowing edit."
    except FileNotFoundError:
        return 0, "", f"[pre-edit-lint] Binary not found — allowing edit."
    except OSError as exc:
        return 0, "", f"[pre-edit-lint] Failed to run ESLint: {exc} — allowing edit."
    finally:
        is_tmp_exists = tmp_path is not None and os.path.exists(tmp_path)
        if is_tmp_exists:
            os.unlink(tmp_path)


def _run_eslint(
    eslint_bin: str,
    file_path: Path,
    proposed_content: str,
    max_warnings: int,
    timeout: int,
    extra_args: list[str],
    working_dir: Path,
    mode: str,
) -> tuple[int, str, str]:
    is_tempfile_mode = mode == ESLINT_HOOK_MODE_TEMPFILE
    if is_tempfile_mode:
        return _run_eslint_via_tempfile(
            eslint_bin, file_path, proposed_content, max_warnings, timeout, extra_args, working_dir
        )
    return _run_eslint_via_stdin(
        eslint_bin, file_path, proposed_content, max_warnings, timeout, extra_args, working_dir
    )


def _parse_hook_context() -> tuple[Path | None, dict, Path]:
    try:
        raw = sys.stdin.read()
        context = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return None, {}, Path(os.getcwd())

    tool_input: dict = context.get("tool_input", {})
    cwd_str: str = context.get("cwd", "")
    working_dir = Path(cwd_str) if cwd_str else Path(os.getcwd())
    raw_path: str = tool_input.get("file_path", "")

    is_path_empty = not raw_path
    if is_path_empty:
        return None, tool_input, working_dir

    return Path(raw_path), tool_input, working_dir


def main() -> None:
    is_disabled = _env_str("ESLINT_HOOK_DISABLED") == "1"
    if is_disabled:
        sys.exit(0)

    file_path, tool_input, working_dir = _parse_hook_context()

    _load_project_env(working_dir)

    override_wd = _env_str("ESLINT_HOOK_WORKING_DIR")
    has_override_wd = bool(override_wd)
    if has_override_wd:
        working_dir = Path(override_wd)

    extensions = _build_extensions(_env_str("ESLINT_HOOK_EXTENSIONS"))
    timeout = _env_int("ESLINT_HOOK_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)
    max_warnings = _env_int("ESLINT_HOOK_MAX_WARNINGS", DEFAULT_MAX_WARNINGS)
    raw_extra = _env_str("ESLINT_HOOK_EXTRA_ARGS")
    extra_args = shlex.split(raw_extra) if raw_extra else []
    raw_mode = _env_str("ESLINT_HOOK_MODE", ESLINT_HOOK_MODE_STDIN)
    mode = raw_mode if raw_mode in (ESLINT_HOOK_MODE_STDIN, ESLINT_HOOK_MODE_TEMPFILE) else ESLINT_HOOK_MODE_STDIN

    is_no_file = file_path is None
    if is_no_file:
        sys.exit(0)

    is_not_lintable = not _is_lintable(file_path, extensions)
    if is_not_lintable:
        sys.exit(0)

    eslint_bin = _find_eslint_bin(working_dir)
    is_bin_missing = eslint_bin is None
    if is_bin_missing:
        sys.exit(0)

    proposed_content = _resolve_proposed_content(tool_input, file_path)

    returncode, stdout, stderr = _run_eslint(
        eslint_bin=eslint_bin,
        file_path=file_path,
        proposed_content=proposed_content,
        max_warnings=max_warnings,
        timeout=timeout,
        extra_args=extra_args,
        working_dir=working_dir,
        mode=mode,
    )

    has_stderr_message = bool(stderr.strip())
    if has_stderr_message:
        print(stderr.strip(), file=sys.stderr)

    has_error = returncode != 0
    if has_error:
        has_output = bool(stdout.strip())
        if has_output:
            print(stdout.strip(), file=sys.stderr)
        print(
            f"\n🚫 [pre-edit-lint] ESLint bloqueou a edição de {file_path.name}. "
            "Corrija os erros acima antes de continuar.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
