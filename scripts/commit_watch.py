#!/usr/bin/env python3
"""
architecture-logger -- commit watcher.

Registered as a PostToolUse hook with matcher "Bash". Claude Code therefore
invokes this script after EVERY successful Bash tool call in a session, handing
it a JSON payload on stdin. The overwhelming majority of those calls have
nothing to do with git, so the script is built as a funnel of cheap guards that
exit silently. Only when a commit has genuinely landed does it do any work.

What it does when a commit lands:
  1. Asks git which files that commit touched.
  2. Maps those files onto architecture modules, using the "**Scope:**" globs
     declared in each .architecture/components/<module>.md file.
  3. Appends one JSON line per affected module to .architecture/pending.jsonl
     (the queue that /arch_check drains).
  4. Appends a dated entry to that component's "## Drift log" section.
  5. Flips that module's Status cell to `drift` in architecture.md.
  6. Prints a one-line nudge telling the user to run /arch_check.

Design note (the trade-off named in NOTES.md): this is the "flag and defer"
approach. The hook records suspicion; it never rewrites documentation itself.
That keeps it deterministic, free, and fast enough to run after every Bash call.
The cost is that records are stale between the commit and the next /arch_check,
which we mitigate by making the staleness visible in the Status column.

Requires only the Python standard library.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCH_DIR_NAME = ".architecture"
STATE_FILE = ".state.json"
QUEUE_FILE = "pending.jsonl"
LOG_FILE = ".hook.log"
INDEX_FILE = "architecture.md"
COMPONENTS_DIR = "components"

DRIFT_FENCE_BEGIN = "<!-- ARCH-LOGGER:BEGIN drift-log -->"
DRIFT_FENCE_END = "<!-- ARCH-LOGGER:END drift-log -->"

# A Bash command counts as a commit attempt when `git ... commit` appears as an
# actual command, not merely as text inside an echo. This is only a cheap
# pre-filter -- guard 4 below is what actually establishes that a commit landed.
COMMIT_PATTERN = re.compile(r"(?:^|[\s;&|(])git\s+(?:-[^\s]+\s+)*commit\b")

# Fallback module map, used only when a components/ file omits its Scope line.
DEFAULT_SCOPES = {
    "api": ["**/api/**", "**/routers/**", "**/routes/**"],
    "be": ["**/services/**", "**/domain/**", "**/core/**"],
    "db": ["**/db/**", "**/models/**", "**/migrations/**", "**/alembic/**"],
    "fe": ["frontend/**", "web/**", "ui/**", "**/templates/**", "**/static/**"],
    "tests": ["tests/**", "**/test_*.py", "**/*_test.py"],
    "infra": ["Dockerfile*", "docker-compose*", ".github/**", "**/*.tf"],
    "usage": ["pyproject.toml", "uv.lock", "Makefile", "**/__main__.py", "**/cli.py"],
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def run_git(repo_root: Path, *args: str) -> str:
    """Run a git command in repo_root and return stdout, or "" on any failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a path glob into a regex.

    `**` crosses directory separators; a single `*` does not. This is stricter
    and more predictable than fnmatch, where `*` would also swallow slashes.
    """
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                if i < len(pattern) and pattern[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def log_error(arch_dir: Path, message: str) -> None:
    """Never raise. A hook that fails loudly is worse than one that fails quietly."""
    try:
        with (arch_dir / LOG_FILE).open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now()} {message}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Reading the architecture records
# ---------------------------------------------------------------------------


def load_module_scopes(arch_dir: Path) -> dict[str, list[re.Pattern]]:
    """Read the `**Scope:**` line out of every components/<module>.md file.

    The records themselves declare which paths each module owns, so the hook
    stays in sync with the documentation instead of hardcoding a layout.
    """
    scopes: dict[str, list[re.Pattern]] = {}
    components = arch_dir / COMPONENTS_DIR
    if not components.is_dir():
        return scopes

    for path in sorted(components.glob("*.md")):
        module = path.stem
        patterns: list[str] = []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        match = re.search(r"^\*\*Scope:\*\*\s*(.+)$", text, re.MULTILINE)
        if match:
            raw = match.group(1)
            # Accept comma-separated globs, with or without backticks.
            for token in re.split(r"[,\s]+", raw):
                token = token.strip().strip("`").strip()
                if token and token not in {"-", "--", "n/a", "N/A", "none"}:
                    patterns.append(token)
        if not patterns:
            patterns = DEFAULT_SCOPES.get(module, [])
        if patterns:
            scopes[module] = [glob_to_regex(p) for p in patterns]
    return scopes


def map_files_to_modules(
    files: list[str], scopes: dict[str, list[re.Pattern]]
) -> dict[str, list[str]]:
    """Return {module: [files it owns]} for the changed files."""
    hits: dict[str, list[str]] = {}
    for path in files:
        for module, patterns in scopes.items():
            if any(pattern.match(path) for pattern in patterns):
                hits.setdefault(module, []).append(path)
    return hits


# ---------------------------------------------------------------------------
# Writing the drift signals
# ---------------------------------------------------------------------------


def append_drift_log(component_path: Path, entry: str) -> None:
    """Add one line inside the fenced drift-log block of a component file.

    The fence exists so /arch_check can clear these entries deterministically
    without touching anything a human wrote.
    """
    try:
        text = component_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return

    line = f"- {entry}\n"

    if DRIFT_FENCE_END in text:
        text = text.replace(DRIFT_FENCE_END, line + DRIFT_FENCE_END, 1)
    elif re.search(r"^##\s+Drift log\s*$", text, re.MULTILINE):
        text = re.sub(
            r"^(##\s+Drift log\s*)$",
            r"\1\n\n" + DRIFT_FENCE_BEGIN + "\n" + line + DRIFT_FENCE_END,
            text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += (
            "\n## Drift log\n\n"
            + DRIFT_FENCE_BEGIN
            + "\n"
            + line
            + DRIFT_FENCE_END
            + "\n"
        )

    try:
        component_path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def flip_status_to_drift(index_path: Path, modules: list[str]) -> list[str]:
    """Set Status to `drift` for each module's row in the module index table.

    Rows are located by their detail-file cell (components/<module>.md), which
    is stable regardless of what display name the module was given.
    """
    flipped: list[str] = []
    try:
        text = index_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return flipped

    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        for module in modules:
            needle = f"{COMPONENTS_DIR}/{module}.md"
            if needle not in stripped:
                continue
            cells = stripped.strip("|").split("|")
            if len(cells) < 4:
                continue
            if cells[-1].strip() == "drift":
                flipped.append(module)
                break
            cells[-1] = " drift "
            lines[i] = "|" + "|".join(cells) + "|\n"
            flipped.append(module)
            break

    try:
        index_path.write_text("".join(lines), encoding="utf-8")
    except Exception:
        return flipped
    return flipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # ---- Read the payload -------------------------------------------------
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0

    # ---- Guard 1: is this even a Bash call? -------------------------------
    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(command, str):
        return 0

    # ---- Guard 2: does the command plausibly commit? ----------------------
    # Cheap text filter. Deliberately not trusted on its own: `echo "git commit"`
    # would slip past a naive version of this, and a failed commit would too.
    if not COMMIT_PATTERN.search(command):
        return 0
    if "--dry-run" in command:
        return 0

    # ---- Locate the repository and its records ----------------------------
    cwd = payload.get("cwd") or os.getcwd()
    repo_root_str = run_git(Path(cwd), "rev-parse", "--show-toplevel")
    if not repo_root_str:
        return 0
    repo_root = Path(repo_root_str)

    arch_dir = repo_root / ARCH_DIR_NAME
    # ---- Guard 3: has this repo been initialised by /arch_init? -----------
    if not arch_dir.is_dir():
        return 0

    try:
        # ---- Guard 4: did a commit ACTUALLY land? -------------------------
        # This is the decisive test. It defeats three failure modes at once:
        # a command that merely mentions committing, a commit that failed, and
        # a re-fire for a commit already processed.
        head = run_git(repo_root, "rev-parse", "HEAD")
        if not head:
            return 0

        state_path = arch_dir / STATE_FILE
        state: dict = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        if state.get("last_seen_sha") == head:
            return 0

        # ---- What changed in that commit? --------------------------------
        raw = run_git(
            repo_root, "show", "--name-only", "--pretty=format:", head
        )
        if not raw:
            raw = run_git(
                repo_root,
                "diff-tree",
                "--root",
                "-r",
                "-m",
                "--no-commit-id",
                "--name-only",
                head,
            )
        changed = [line.strip() for line in raw.splitlines() if line.strip()]

        subject = run_git(repo_root, "log", "-1", "--pretty=format:%s", head)
        short_sha = head[:7]

        # Record the SHA immediately, so an error further down can never cause
        # the same commit to be processed twice.
        try:
            state["last_seen_sha"] = head
            state["last_seen_at"] = utc_now()
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

        if not changed:
            return 0

        # ---- Which modules are now suspect? ------------------------------
        scopes = load_module_scopes(arch_dir)
        if not scopes:
            return 0
        affected = map_files_to_modules(changed, scopes)
        if not affected:
            return 0

        timestamp = utc_now()

        # ---- Append to the queue /arch_check will drain ------------------
        queue_path = arch_dir / QUEUE_FILE
        try:
            with queue_path.open("a", encoding="utf-8") as handle:
                for module, files in sorted(affected.items()):
                    handle.write(
                        json.dumps(
                            {
                                "ts": timestamp,
                                "commit": short_sha,
                                "subject": subject,
                                "module": module,
                                "detail_file": f"{COMPONENTS_DIR}/{module}.md",
                                "files": sorted(files),
                                "reason": "files owned by this module changed in a commit",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
        except Exception as exc:
            log_error(arch_dir, f"queue write failed: {exc!r}")

        # ---- Append to each component's Drift log ------------------------
        for module, files in sorted(affected.items()):
            component_path = arch_dir / COMPONENTS_DIR / f"{module}.md"
            if component_path.exists():
                append_drift_log(
                    component_path,
                    f"{timestamp} - commit `{short_sha}` ({subject}) touched: "
                    + ", ".join(f"`{f}`" for f in sorted(files)),
                )

        # ---- Flip Status cells in the index ------------------------------
        index_path = arch_dir / INDEX_FILE
        if index_path.exists():
            flip_status_to_drift(index_path, sorted(affected.keys()))

        # ---- Tell the user, without interrupting them --------------------
        names = ", ".join(sorted(affected.keys()))
        count = len(affected)
        message = (
            f"architecture-logger: {count} module(s) marked drift "
            f"({names}) after commit {short_sha}. Run /arch_check to reconcile."
        )
        print(
            json.dumps(
                {
                    "systemMessage": message,
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": (
                            f"Architecture records are now unverified for: {names}. "
                            "The user may want to run /arch_check."
                        ),
                    },
                }
            )
        )
    except Exception as exc:  # noqa: BLE001 -- a hook must never fail loudly
        log_error(arch_dir, f"unhandled: {exc!r}")

    # Always exit 0. A non-zero exit surfaces a hook-error notice to the user
    # on what may be an entirely ordinary Bash call.
    return 0


if __name__ == "__main__":
    sys.exit(main())
