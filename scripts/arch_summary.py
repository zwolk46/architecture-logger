#!/usr/bin/env python3
"""
architecture-logger -- terminal renderer for .architecture/.

Reads the records and prints them as something a person actually wants to look
at: a boxed header, the repository's Purpose wrapped to the terminal, the
module index with a colour-coded Status column, and one summary block per
module separated by rules.

Two behaviours worth knowing about:

  Paging. When stdout is a terminal the rendering is piped through $PAGER (or
  `less -R`). When it is not -- a pipe, a file, a tool capturing output -- the
  same rendering is printed directly, followed by a hint that `--page` forces a
  real paged scroll. Nothing is ever written to disk: the rendering reaches the
  pager on stdin, so there is no temp file to place or clean up, in the
  repository or in $TMPDIR.

  Colour. Raw ANSI codes, matching the three-value Status vocabulary of the
  architecture-records skill: green `current`, yellow `drift`, red `missing`.
  Suppressed by --no-color or by NO_COLOR in the environment. Every column is
  padded on the *plain* text and coloured afterwards -- padding an already
  coloured string counts the nine invisible bytes of the escape sequence and
  bends the table out of alignment.

This command is read-only by contract. It writes no files anywhere.

Usage:
    python3 arch_summary.py [REPO_ROOT] [--page] [--no-color]

REPO_ROOT defaults to the current directory.

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCH_DIR_NAME = ".architecture"
COMPONENTS_DIR = "components"
INDEX_FILE = "architecture.md"

MIN_WIDTH = 48
MAX_WIDTH = 110

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
CYAN = "\x1b[36m"

STATUS_COLOURS = {"current": GREEN, "drift": YELLOW, "missing": RED}

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
ANY_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
KEY_FUNCS_HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s*key functions and classes\b", re.IGNORECASE)
DRIFT_HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s*drift log\b", re.IGNORECASE)
# `## Idea` is what schemas.md §2.1 actually calls a component's summary; the
# rest are tolerated synonyms so a hand-written record still renders.
SUMMARY_HEADING_RE = re.compile(
    r"^\s{0,3}#{2,6}\s*(idea|purpose|responsibilit(?:y|ies)|overview|summary|what it does)\b",
    re.IGNORECASE,
)
MODULE_SUMMARIES_HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s*module summaries\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------


class Style:
    """Colour helper. Every method is a no-op when colour is disabled."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def paint(self, text: str, *codes: str) -> str:
        if not self.enabled or not codes:
            return text
        return "".join(codes) + text + RESET

    def bold(self, text: str) -> str:
        return self.paint(text, BOLD)

    def dim(self, text: str) -> str:
        return self.paint(text, DIM)

    def status(self, value: str, width: int = 0) -> str:
        """Pad first, colour second -- see the module docstring."""
        padded = value.ljust(width) if width else value
        colour = STATUS_COLOURS.get(value.strip().lower())
        if colour is None:
            return self.dim(padded)
        return self.paint(padded, BOLD, colour)


# ---------------------------------------------------------------------------
# Small markdown helpers
# ---------------------------------------------------------------------------


def sanitize(text: str) -> str:
    """Drop control characters.

    They occupy no columns on screen but one each in `len()`, so a stray one in
    a malformed record silently bends every box and table it appears in.
    """
    return CONTROL_RE.sub("", text)


def clean_cell(raw: str) -> str:
    text = sanitize(raw).strip()
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").strip()
    # Paired asterisk emphasis only, and only when the payload does not itself
    # contain asterisks: `**/api/**, **/routers/**` is two globs, not a bolded
    # `/api/**, **/routers/`.
    for pattern in (r"\*\*(.+)\*\*", r"\*(.+)\*"):
        match = re.fullmatch(pattern, text, re.DOTALL)
        if match and "*" not in match.group(1):
            text = match.group(1).strip()
            break
    return text.strip()


def split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith(r"\|"):
        text = text[:-1]
    return [cell.replace(r"\|", "|").strip() for cell in CELL_SPLIT_RE.split(text)]


def is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def find_tables(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    """Return every markdown table in the file as (header, rows)."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        header = split_row(lines[i])
        rows: list[list[str]] = []
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if HTML_COMMENT_RE.match(line):
                j += 1
                continue
            if not line.strip().startswith("|"):
                break
            cells = split_row(line)
            if not is_separator_row(cells):
                rows.append(cells)
            j += 1
        tables.append((header, rows))
        i = j if j > i else i + 1
    return tables


def section_body(lines: list[str], heading_re: re.Pattern) -> list[str]:
    """Text under the first heading matching `heading_re`, up to the next heading."""
    for i, line in enumerate(lines):
        if not heading_re.match(line):
            continue
        body: list[str] = []
        for candidate in lines[i + 1 :]:
            if ANY_HEADING_RE.match(candidate):
                break
            if HTML_COMMENT_RE.match(candidate):
                continue
            body.append(candidate)
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        return body
    return []


def section_body_until_same_level(lines: list[str], heading_re: re.Pattern) -> list[str]:
    """Like `section_body`, but keeps nested subsections.

    Stops at the next heading of the same or higher level, so `## Module
    summaries` returns all of its `###` children rather than stopping at the
    first one.
    """
    for i, line in enumerate(lines):
        if not heading_re.match(line):
            continue
        opening = ANY_HEADING_RE.match(line)
        level = len(opening.group(1)) if opening else 2
        body: list[str] = []
        for candidate in lines[i + 1 :]:
            nested = ANY_HEADING_RE.match(candidate)
            if nested and len(nested.group(1)) <= level:
                break
            if HTML_COMMENT_RE.match(candidate):
                continue
            body.append(candidate)
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        return body
    return []


def first_paragraph(body: list[str]) -> str:
    chunk: list[str] = []
    for line in body:
        if not line.strip():
            if chunk:
                break
            continue
        if line.strip().startswith("|"):
            break
        chunk.append(line.strip())
    return " ".join(chunk).strip()


def parse_sync_banner(lines: list[str]) -> tuple[str, str]:
    """Pull (timestamp, commit) out of the two-line blockquote banner.

    schemas.md 1.2 fixes the format as a blockquote carrying both halves on one
    line, separated by a middle dot:

        > Last synced: 2026-08-11T09:41:07Z · commit `7993ece`

    so neither value can be read as a plain `**Label:** value` line.
    """
    for raw in lines:
        line = sanitize(raw).strip()
        if line.startswith(">"):
            line = line.lstrip(">").strip()
        line = line.replace("`", "")
        match = re.search(r"last\s+synced\s*:\s*(.+)$", line, re.IGNORECASE)
        if not match:
            continue
        rest = match.group(1).strip()
        halves = re.split(r"\s*[·•]\s*|\s+[-–—|]\s+", rest, maxsplit=1)
        synced = halves[0].strip()
        commit = ""
        if len(halves) > 1:
            commit_match = re.search(r"commit\s*:?\s*(\S+)", halves[1], re.IGNORECASE)
            commit = commit_match.group(1).strip() if commit_match else halves[1].strip()
        return synced, commit
    return "", ""


def module_summaries(lines: list[str]) -> dict[str, str]:
    """Map display name -> prose from the `## Module summaries` section."""
    body = section_body_until_same_level(lines, MODULE_SUMMARIES_HEADING_RE)
    summaries: dict[str, str] = {}
    name = ""
    chunk: list[str] = []
    for line in body:
        match = ANY_HEADING_RE.match(line)
        if match and len(match.group(1)) >= 3:
            if name:
                summaries[name.lower()] = " ".join(chunk).strip()
            name = clean_cell(match.group(2))
            chunk = []
            continue
        if line.strip():
            chunk.append(line.strip())
    if name:
        summaries[name.lower()] = " ".join(chunk).strip()
    return summaries


def labelled_value(lines: list[str], label: str) -> str:
    """Read a `**Label:** value` line, however it happens to be emphasised."""
    pattern = re.compile(
        rf"^\s*>?\s*(?:[-*+]\s*)?\**\s*{label}\s*:?\s*\**\s*:?\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.match(line)
        if match:
            value = clean_cell(match.group(1))
            if value:
                return value
    return ""


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []


def visible_len(text: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


def truncate(text: str, width: int) -> str:
    text = sanitize(text)
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


# ---------------------------------------------------------------------------
# Reading the records
# ---------------------------------------------------------------------------


class Module:
    __slots__ = (
        "key", "name", "description", "detail_file", "status",
        "scope", "entry_points", "summary", "cited", "drift_entries",
        "record_exists",
    )

    def __init__(self, key: str) -> None:
        self.key = key
        self.name = key
        self.description = ""
        self.detail_file = f"{COMPONENTS_DIR}/{key}.md"
        self.status = "unknown"
        self.scope = ""
        self.entry_points = ""
        self.summary = ""
        self.cited = 0
        self.drift_entries = 0
        self.record_exists = False


def pick_module_table(tables: list[tuple[list[str], list[list[str]]]]):
    """The module index is the table whose rows point at components/*.md."""
    best = None
    best_hits = 0
    for header, rows in tables:
        hits = sum(1 for row in rows if any(f"{COMPONENTS_DIR}/" in cell for cell in row))
        if hits > best_hits:
            best, best_hits = (header, rows), hits
    return best


def load_index(arch_dir: Path) -> dict:
    """Parse architecture.md. Every field degrades to a placeholder."""
    index_path = arch_dir / INDEX_FILE
    info = {
        "exists": index_path.is_file(),
        "repo_name": "",
        "synced": "",
        "commit": "",
        "purpose": "",
        "header": [],
        "rows": [],
        "summaries": {},
    }
    if not info["exists"]:
        return info

    lines = read_lines(index_path)

    for line in lines:
        match = ANY_HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            title = clean_cell(match.group(2))
            # schemas.md 1.2 fixes the title as `# Architecture — <repo name>`,
            # em dash. Accept the other dashes too rather than displaying the
            # boilerplate back at the reader.
            info["repo_name"] = re.sub(
                r"^architecture\s*[—–\-:]\s*", "", title, flags=re.I
            ).strip()
            break

    if not info["repo_name"]:
        info["repo_name"] = labelled_value(lines, "repository") or labelled_value(lines, "repo")

    banner_synced, banner_commit = parse_sync_banner(lines)
    info["synced"] = banner_synced or labelled_value(lines, "synced") or labelled_value(
        lines, "generated"
    )
    info["commit"] = (
        banner_commit
        or labelled_value(lines, "commit")
        or labelled_value(lines, "synced at commit")
        or labelled_value(lines, "sha")
    )
    info["summaries"] = module_summaries(lines)

    purpose_body = section_body(lines, re.compile(r"^\s{0,3}#{2,6}\s*purpose\b", re.IGNORECASE))
    if purpose_body:
        info["purpose"] = "\n".join(purpose_body).strip()
    else:
        info["purpose"] = labelled_value(lines, "purpose")

    table = pick_module_table(find_tables(lines))
    if table:
        info["header"], info["rows"] = table

    return info


def load_modules(arch_dir: Path, index: dict) -> list[Module]:
    """Build the module list from the index table, backfilled from components/."""
    components_dir = arch_dir / COMPONENTS_DIR
    modules: list[Module] = []
    seen: set[str] = set()

    detail_re = re.compile(rf"{re.escape(COMPONENTS_DIR)}/([^/\s`|)\]]+)\.md")

    for row in index["rows"]:
        key = ""
        for cell in row:
            match = detail_re.search(cell)
            if match:
                key = match.group(1)
                break
        if not key:
            # A row without a detail-file cell still deserves to be shown.
            key = clean_cell(row[0]) if row else ""
            if not key:
                continue
        if key in seen:
            continue
        seen.add(key)

        module = Module(key)
        cells = [clean_cell(cell) for cell in row]
        if cells:
            module.name = cells[0] or key
        # Status is the last cell -- the same convention commit_watch.py uses
        # when it flips a module to `drift`.
        if len(cells) >= 2:
            module.status = cells[-1] or "unknown"
        # The description is the widest non-status, non-detail-file cell.
        candidates = [
            cell for cell in cells[1:-1]
            if cell and f"{COMPONENTS_DIR}/" not in cell
        ]
        if candidates:
            module.description = max(candidates, key=len)
        modules.append(module)

    if components_dir.is_dir():
        for path in sorted(components_dir.glob("*.md")):
            if path.stem not in seen:
                seen.add(path.stem)
                modules.append(Module(path.stem))

    summaries = index.get("summaries") or {}
    for module in modules:
        enrich(module, components_dir, summaries)

    return modules


def enrich(module: Module, components_dir: Path, summaries: dict[str, str]) -> None:
    path = components_dir / f"{module.key}.md"
    lines = read_lines(path) if path.is_file() else []
    module.record_exists = bool(lines)

    for line in lines:
        match = ANY_HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            title = clean_cell(match.group(2))
            if title and module.name == module.key:
                module.name = title
            break

    module.scope = labelled_value(lines, "scope")
    module.entry_points = labelled_value(lines, "entry points")

    if module.status in ("", "unknown"):
        module.status = labelled_value(lines, "status") or "unknown"

    # Prefer the component's own `## Idea`; fall back to the module summary in
    # architecture.md, then to the index's one-line description.
    summary = first_paragraph(section_body(lines, SUMMARY_HEADING_RE))
    if not summary:
        summary = summaries.get(module.name.lower()) or summaries.get(module.key.lower(), "")
    if not summary:
        summary = module.description
    module.summary = summary

    # Count data rows, discarding one header per table. A file may carry more
    # than one Key-functions section, so the header has to be dropped per table
    # rather than once overall.
    in_key_table = False
    header_seen = False
    for line in lines:
        if KEY_FUNCS_HEADING_RE.match(line):
            in_key_table = True
            header_seen = False
            continue
        if not in_key_table:
            continue
        if ANY_HEADING_RE.match(line):
            in_key_table = False
            continue
        if not line.strip().startswith("|"):
            continue
        cells = split_row(line)
        if is_separator_row(cells) or not any(cell.strip() for cell in cells):
            continue
        if not header_seen:
            header_seen = True
            continue
        module.cited += 1

    drift_body = section_body(lines, DRIFT_HEADING_RE)
    module.drift_entries = sum(1 for line in drift_body if line.strip().startswith("-"))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_box(title: str, rows: list[tuple[str, str]], width: int, style: Style) -> list[str]:
    label_w = max((len(label) for label, _ in rows), default=0)
    body = [f"{label:<{label_w}}  {value}" for label, value in rows]
    inner = max([len(title)] + [len(line) for line in body])
    inner = max(inner, MIN_WIDTH - 4)
    inner = min(inner, width - 4)

    out = ["┌─" + "─" * inner + "─┐"]
    out.append("│ " + style.bold(truncate(title, inner).ljust(inner)) + " │")
    if body:
        out.append("├─" + "─" * inner + "─┤")
    for label, value in rows:
        text = f"{label:<{label_w}}  {value}"
        text = truncate(text, inner)
        padded = text.ljust(inner)
        # Colour the label only, after padding the whole line.
        coloured = style.dim(padded[:label_w]) + padded[label_w:]
        out.append("│ " + coloured + " │")
    out.append("└─" + "─" * inner + "─┘")
    return out


def render_module_table(modules: list[Module], width: int, style: Style) -> list[str]:
    headers = ["MODULE", "DESCRIPTION", "RECORD", "STATUS"]
    rows = [
        [
            module.name,
            module.description or module.summary or "-",
            module.detail_file,
            module.status,
        ]
        for module in modules
    ]

    widths = [
        max(len(headers[i]), max((len(row[i]) for row in rows), default=0))
        for i in range(len(headers))
    ]

    # Shrink the description until the table fits the terminal.
    gap = 2
    def total() -> int:
        return sum(widths) + gap * (len(widths) - 1)

    while total() > width and widths[1] > 12:
        widths[1] -= 1
    while total() > width and widths[2] > 10:
        widths[2] -= 1
    while total() > width and widths[0] > 8:
        widths[0] -= 1

    out: list[str] = []
    header_line = (gap * " ").join(
        headers[i].ljust(widths[i]) for i in range(len(headers))
    )
    out.append(style.bold(header_line.rstrip()))
    out.append(style.dim((gap * " ").join("─" * w for w in widths)))

    for row in rows:
        cells = []
        for i, value in enumerate(row):
            text = truncate(value, widths[i]).ljust(widths[i])
            if headers[i] == "STATUS":
                cells.append(style.status(truncate(value, widths[i]), widths[i]))
            elif headers[i] == "MODULE":
                cells.append(style.paint(text, CYAN))
            elif headers[i] == "RECORD":
                cells.append(style.dim(text))
            else:
                cells.append(text)
        line = (gap * " ").join(cells)
        out.append(line.rstrip() if visible_len(line) else line)
    return out


def render_module_block(module: Module, width: int, style: Style) -> list[str]:
    out: list[str] = []
    heading = style.paint(module.name, BOLD, CYAN) + "  " + style.status(module.status)
    out.append(heading)

    meta: list[str] = []
    if module.detail_file:
        meta.append(module.detail_file)
    if module.record_exists:
        meta.append(f"{module.cited} cited symbol(s)")
        if module.drift_entries:
            meta.append(f"{module.drift_entries} drift entr(y/ies)")
    else:
        meta.append("no component record on disk")
    out.append(style.dim(truncate("  ".join(meta), width)))

    for label, value in (("Scope: ", module.scope), ("Entry: ", module.entry_points)):
        if not value:
            continue
        pad = " " * len(label)
        wrapped = textwrap.wrap(value, width=max(20, width - len(label))) or [""]
        for i, line in enumerate(wrapped):
            out.append((style.dim(label) if i == 0 else pad) + line)

    text = module.summary or module.description
    if text:
        out.append("")
        out.extend(textwrap.wrap(text, width=width) or [""])
    return out


def render(repo_root: Path, arch_dir: Path, width: int, style: Style) -> str:
    index = load_index(arch_dir)
    modules = load_modules(arch_dir, index)

    out: list[str] = []

    repo_name = index["repo_name"] or repo_root.name
    header_rows = [
        ("Last synced:", index["synced"] or "not recorded"),
        ("Commit:", index["commit"] or "not recorded"),
        ("Records:", str(arch_dir)),
    ]
    out.extend(render_box(repo_name, header_rows, width, style))
    out.append("")

    if not index["exists"]:
        out.append(style.paint(f"! {INDEX_FILE} is missing from {ARCH_DIR_NAME}/.", YELLOW))
        out.append(
            style.dim("  Showing what could be read from components/ alone. "
                      "Run /arch_init to rebuild the index.")
        )
        out.append("")

    out.append(style.bold("PURPOSE"))
    out.append(style.dim("─" * min(width, 40)))
    purpose = index["purpose"]
    if purpose:
        for paragraph in re.split(r"\n\s*\n", purpose):
            paragraph = " ".join(line.strip() for line in paragraph.splitlines()).strip()
            if not paragraph:
                continue
            if paragraph.startswith(("-", "*", "+")):
                out.extend(paragraph.splitlines())
            else:
                out.extend(textwrap.wrap(paragraph, width=width) or [""])
            out.append("")
    else:
        out.append(style.dim("No Purpose section recorded."))
        out.append("")

    out.append(style.bold("MODULES"))
    out.append(style.dim("─" * min(width, 40)))
    if modules:
        out.extend(render_module_table(modules, width, style))
    else:
        out.append(style.dim("No modules recorded."))
    out.append("")

    legend = (
        style.paint("current", GREEN) + style.dim(" verified   ")
        + style.paint("drift", YELLOW) + style.dim(" unchecked since the code moved   ")
        + style.paint("missing", RED) + style.dim(" not present in this repository")
    )
    out.append(legend)
    out.append("")

    if modules:
        out.append(style.bold("DETAIL"))
        out.append("")
        for i, module in enumerate(modules):
            if i:
                out.append(style.dim("─" * width))
                out.append("")
            out.extend(render_module_block(module, width, style))
            out.append("")

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def pager_argv(colour: bool) -> list[str]:
    """$PAGER if set to something non-empty, else `less -R`.

    `.get("PAGER", "less -R")` is not good enough: an exported-but-empty PAGER
    is common, and it yields "" rather than the default.
    """
    raw = os.environ.get("PAGER") or "less -R"
    try:
        argv = shlex.split(raw)
    except ValueError:
        argv = ["less", "-R"]
    if not argv:
        argv = ["less", "-R"]
    # A pager the user configured without -R would print our escape codes as
    # literal text, so add it for the pagers we know understand it.
    if colour and Path(argv[0]).name in {"less", "more"}:
        if not any(flag in argv for flag in ("-R", "-r", "--RAW-CONTROL-CHARS")):
            argv.append("-R")
    return argv


def page(text: str, colour: bool) -> bool:
    """Send `text` to the pager on stdin. No temp file, nothing to clean up."""
    argv = pager_argv(colour)
    try:
        subprocess.run(argv, input=text, text=True, check=False)
    except (FileNotFoundError, PermissionError, OSError):
        return False
    except (BrokenPipeError, KeyboardInterrupt):
        return True
    return True


def emit(text: str) -> None:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arch_summary.py",
        description="Render .architecture/ as an aligned, colour-coded terminal view.",
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="repository root to summarise (default: the current directory)",
    )
    parser.add_argument(
        "--page",
        action="store_true",
        help="force paging through $PAGER even when stdout is not a terminal",
    )
    parser.add_argument(
        "--no-color",
        "--no-colour",
        dest="no_color",
        action="store_true",
        help="disable ANSI colour",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser()
    if not repo_root.is_dir():
        print(f"Not a directory: {repo_root}", file=sys.stderr)
        return 2
    repo_root = repo_root.resolve()

    arch_dir = repo_root / ARCH_DIR_NAME
    if not arch_dir.is_dir():
        print(f"No {ARCH_DIR_NAME}/ directory found in {repo_root}")
        print("There is nothing to summarise yet. Run /arch_init to create the records.")
        return 0

    colour = not args.no_color and not os.environ.get("NO_COLOR")
    style = Style(colour)

    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    width = max(MIN_WIDTH, min(MAX_WIDTH, width - 1))

    try:
        text = render(repo_root, arch_dir, width, style)
    except Exception as exc:  # noqa: BLE001 -- a viewer must not traceback
        print(f"Could not render {ARCH_DIR_NAME}/: {exc}", file=sys.stderr)
        print("The records may be malformed. Run /arch_check to reconcile them.", file=sys.stderr)
        return 0

    if args.page or sys.stdout.isatty():
        if page(text, colour):
            return 0
        # Pager unavailable -- fall through and print directly rather than
        # showing the user nothing.

    emit(text)

    if not sys.stdout.isatty() and not args.page:
        emit(
            "\n"
            + style.dim(
                "(stdout is not a terminal, so this was printed directly. "
                "Re-run with --page for a real paged scroll.)"
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
