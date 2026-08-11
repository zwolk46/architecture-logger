#!/usr/bin/env python3
"""
architecture-logger -- traceability verifier.

Enforces Rule 1 of the architecture-records skill: every row of a
"## Key functions and classes" table in .architecture/components/*.md must cite
a real `relative/path.py:LINE`, and the symbol named in that row must actually
be there.

For each row it checks two things:

  (a) the cited file exists, relative to the repository root; and
  (b) the symbol from the Symbol cell appears within +/-5 lines of the cited
      line.

The window exists because line numbers age faster than symbols do. An edit
above a function shifts it by a line or two long before the record is wrong in
any way a reader would care about; a citation that is off by more than five
lines is no longer a citation. The tolerance is deliberately small and is
printed in the report header, so a failure is interpretable without reading
this source.

Exits 1 if any row fails, 0 otherwise -- so it can gate `/arch_init` and
`/arch_check` before either reports success.

Usage:
    python3 verify_traceability.py [REPO_ROOT]

REPO_ROOT defaults to the current directory. It is never derived from this
file's location: the script lives in the plugin, the repository it checks does
not.

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCH_DIR_NAME = ".architecture"
COMPONENTS_DIR = "components"

# How far from the cited line we are willing to look for the symbol.
WINDOW = 5

# "## Key functions and classes", at any heading depth, with or without
# trailing punctuation. Matched case-insensitively -- a record with a stray
# capital is a style problem, not a reason to skip verification.
HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s*key functions and classes\b", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")

# Generated-block fences (Rule 2) sit between the heading and the table.
HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")

# `relative/path.py:LINE`. Non-greedy path so a Windows-style drive letter or a
# stray colon in the path does not eat the line number.
CITATION_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)$")

# Cells are split on unescaped pipes, so a cell may legitimately contain `\|`.
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")

# Header keywords, in priority order, used to locate the two columns we need.
SYMBOL_HEADERS = ("symbol", "function", "class", "name")
LOCATION_HEADERS = ("location", "citation", "source", "path", "file", "where")


# ---------------------------------------------------------------------------
# Markdown table parsing
# ---------------------------------------------------------------------------


def is_table_row(line: str) -> bool:
    return line.strip().startswith("|")


def split_row(line: str) -> list[str]:
    """Split one markdown table row into its cells."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith(r"\|"):
        text = text[:-1]
    return [cell.replace(r"\|", "|").strip() for cell in CELL_SPLIT_RE.split(text)]


def is_separator_row(cells: list[str]) -> bool:
    """True for the `|---|:--:|` rule under a table header."""
    if not cells:
        return False
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def clean_cell(raw: str) -> str:
    """Strip the markdown a cell may be dressed in, without touching identifiers.

    Underscores are left alone on purpose: stripping "emphasis" from `__init__`
    would silently rename the symbol we are about to go looking for.
    """
    text = raw.strip()
    # [text](target) -> text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").strip()
    # Paired asterisk emphasis only, and only when the payload does not itself
    # contain asterisks: `**/api/**` is a glob, not a bolded `/api/`.
    for pattern in (r"\*\*(.+)\*\*", r"\*(.+)\*"):
        match = re.fullmatch(pattern, text, re.DOTALL)
        if match and "*" not in match.group(1):
            text = match.group(1).strip()
            break
    return text.strip()


def clean_symbol(raw: str) -> str:
    """Normalise a Symbol cell to a bare identifier or dotted path."""
    text = clean_cell(raw)
    # Drop a trailing signature: `create_task(db, payload)` -> `create_task`.
    text = re.sub(r"\s*\(.*\)\s*$", "", text, flags=re.DOTALL)
    # Drop a leading `def ` / `class ` / `async def `.
    text = re.sub(r"^(?:async\s+)?(?:def|class)\s+", "", text)
    return text.strip().rstrip(":")


def find_key_function_tables(lines: list[str]) -> list[tuple[int, list[str], list[tuple[int, list[str]]]]]:
    """Locate every "Key functions and classes" table in one component file.

    Returns a list of (heading_lineno, header_cells, [(lineno, cells), ...]).
    Line numbers are 1-indexed, for pointing the user at the row to fix.
    """
    tables: list[tuple[int, list[str], list[tuple[int, list[str]]]]] = []
    i = 0
    total = len(lines)

    while i < total:
        if not HEADING_RE.match(lines[i]):
            i += 1
            continue

        heading_lineno = i + 1
        j = i + 1

        # Walk past blank lines and generated-block fences to reach the table.
        while j < total:
            line = lines[j]
            if line.strip() == "" or HTML_COMMENT_RE.match(line):
                j += 1
                continue
            break

        if j >= total or not is_table_row(lines[j]) or ANY_HEADING_RE.match(lines[j]):
            # A section with prose but no table is not an error; there is simply
            # nothing to verify.
            i = j if j > i else i + 1
            continue

        header = split_row(lines[j])
        rows: list[tuple[int, list[str]]] = []
        k = j + 1

        while k < total:
            line = lines[k]
            if HTML_COMMENT_RE.match(line):
                k += 1
                continue
            if not is_table_row(line):
                break
            cells = split_row(line)
            if not is_separator_row(cells):
                rows.append((k + 1, cells))
            k += 1

        tables.append((heading_lineno, header, rows))
        i = k

    return tables


def resolve_columns(header: list[str]) -> tuple[int | None, int | None]:
    """Map the header row onto (symbol_index, location_index) by name.

    Column *order* is not assumed -- only that the columns are named something
    recognisable. A record that renames "Location" to "Source" still verifies.
    """
    lowered = [cell.lower() for cell in header]

    def find(keywords: tuple[str, ...]) -> int | None:
        for keyword in keywords:
            for index, cell in enumerate(lowered):
                if keyword in cell:
                    return index
        return None

    return find(SYMBOL_HEADERS), find(LOCATION_HEADERS)


# ---------------------------------------------------------------------------
# The two checks
# ---------------------------------------------------------------------------


def parse_citation(raw: str) -> tuple[str, int] | None:
    text = clean_cell(raw)
    # Tolerate a trailing column number: path.py:42:8
    text = re.sub(r":(\d+):\d+$", r":\1", text)
    match = CITATION_RE.match(text)
    if not match:
        return None
    try:
        line = int(match.group("line"))
    except ValueError:
        return None
    if line < 1:
        return None
    return match.group("path").strip(), line


def read_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None


def symbol_in_window(symbol: str, lines: list[str], cited: int) -> bool:
    """Is `symbol` within +/-WINDOW lines of `cited` (1-indexed, clamped)?"""
    start = max(1, cited - WINDOW)
    end = min(len(lines), cited + WINDOW)
    if start > end:
        return False
    haystack = "\n".join(lines[start - 1 : end])

    candidates = [symbol]
    # `TaskService.create_task` also matches on the method name alone, which is
    # what actually appears on the `def` line.
    if "." in symbol:
        tail = symbol.rsplit(".", 1)[-1]
        if tail:
            candidates.append(tail)

    for candidate in candidates:
        if not candidate:
            continue
        if re.search(rf"(?<![\w.]){re.escape(candidate)}\b", haystack):
            return True
    # Last resort: a plain substring, for symbols carrying decorators or
    # unusual punctuation we did not anticipate.
    return any(candidate and candidate in haystack for candidate in candidates)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


class Result:
    __slots__ = ("component", "row_line", "symbol", "location", "ok", "reason")

    def __init__(
        self,
        component: str,
        row_line: int,
        symbol: str,
        location: str,
        ok: bool,
        reason: str = "",
    ) -> None:
        self.component = component
        self.row_line = row_line
        self.symbol = symbol
        self.location = location
        self.ok = ok
        self.reason = reason


def check_row(
    repo_root: Path,
    component: str,
    row_line: int,
    symbol_raw: str,
    location_raw: str,
) -> Result:
    symbol = clean_symbol(symbol_raw)
    location = clean_cell(location_raw) or "(empty)"

    if not symbol:
        return Result(component, row_line, "(empty)", location, False, "empty Symbol cell")

    citation = parse_citation(location_raw)
    if citation is None:
        return Result(
            component,
            row_line,
            symbol,
            location,
            False,
            "unparseable citation (expected `relative/path.py:LINE`)",
        )

    rel_path, cited_line = citation

    if Path(rel_path).is_absolute():
        return Result(
            component, row_line, symbol, location, False,
            "citation is not repo-relative",
        )
    if ".." in Path(rel_path).parts:
        return Result(
            component, row_line, symbol, location, False,
            "citation escapes the repository root",
        )

    target = repo_root / rel_path
    if not target.is_file():
        return Result(component, row_line, symbol, location, False, "file does not exist")

    lines = read_lines(target)
    if lines is None:
        return Result(component, row_line, symbol, location, False, "file could not be read")

    if cited_line > len(lines):
        return Result(
            component, row_line, symbol, location, False,
            f"cited line {cited_line} is past end of file ({len(lines)} lines)",
        )

    if not symbol_in_window(symbol, lines, cited_line):
        return Result(
            component, row_line, symbol, location, False,
            f"symbol not found within +/-{WINDOW} lines of line {cited_line}",
        )

    return Result(component, row_line, symbol, location, True)


def verify(repo_root: Path) -> int:
    arch_dir = repo_root / ARCH_DIR_NAME

    if not arch_dir.is_dir():
        print(f"No {ARCH_DIR_NAME}/ directory found in {repo_root}")
        print("Nothing to verify. Run /arch_init to create the records first.")
        return 0

    components_dir = arch_dir / COMPONENTS_DIR
    if not components_dir.is_dir():
        print(f"No {ARCH_DIR_NAME}/{COMPONENTS_DIR}/ directory found in {repo_root}")
        print("Nothing to verify. Run /arch_init to create the component records.")
        return 0

    component_files = sorted(components_dir.glob("*.md"))
    if not component_files:
        print(f"No component records in {ARCH_DIR_NAME}/{COMPONENTS_DIR}/")
        print("Nothing to verify.")
        return 0

    print(f"Traceability check  --  repo root: {repo_root}")
    print(
        f"Rule: cited file must exist, and the Symbol must appear within "
        f"+/-{WINDOW} lines of the cited line."
    )
    print("")

    results: list[Result] = []
    structural_problems: list[str] = []

    for component_path in component_files:
        component = component_path.name
        text = read_lines(component_path)
        if text is None:
            structural_problems.append(f"{component}: could not be read")
            continue

        tables = find_key_function_tables(text)
        if not tables:
            continue

        for heading_lineno, header, rows in tables:
            symbol_idx, location_idx = resolve_columns(header)

            if symbol_idx is None:
                structural_problems.append(
                    f"{component}:{heading_lineno}: table has no Symbol column "
                    f"(header: {' | '.join(header)})"
                )
                continue

            for row_line, cells in rows:
                if not any(cell.strip() for cell in cells):
                    continue
                if symbol_idx >= len(cells):
                    results.append(
                        Result(component, row_line, "(malformed)", "(malformed)", False,
                               "row has fewer cells than the header")
                    )
                    continue

                if location_idx is not None and location_idx < len(cells):
                    location_raw = cells[location_idx]
                else:
                    # No named Location column: fall back to the first cell in
                    # the row that looks like a citation.
                    location_raw = ""
                    for cell in cells:
                        if parse_citation(cell) is not None:
                            location_raw = cell
                            break

                results.append(
                    check_row(repo_root, component, row_line, cells[symbol_idx], location_raw)
                )

    if not results and not structural_problems:
        print("0 rows checked -- no 'Key functions and classes' tables found.")
        return 0

    # ---- One line per checked row ----------------------------------------
    if results:
        comp_w = max(len(r.component) for r in results)
        sym_w = min(36, max(len(r.symbol) for r in results))
        loc_w = min(48, max(len(r.location) for r in results))

        for result in results:
            status = "PASS" if result.ok else "FAIL"
            line = (
                f"{status}  {result.component:<{comp_w}}  "
                f"L{result.row_line:<5} {result.symbol:<{sym_w}}  "
                f"{result.location:<{loc_w}}"
            ).rstrip()
            if not result.ok:
                line += f"  <-- {result.reason}"
            print(line)

    # ---- Summary ----------------------------------------------------------
    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    components_seen = len({r.component for r in results})

    print("")
    print(
        f"Summary: {len(results)} row(s) checked across {components_seen} "
        f"component record(s) -- {passed} passed, {failed} failed."
    )

    # ---- Failures, spelled out -------------------------------------------
    if failed or structural_problems:
        print("")
        print("Failures:")
        for result in results:
            if result.ok:
                continue
            print(f"  {result.component}:{result.row_line}")
            print(f"      symbol:   {result.symbol}")
            print(f"      cited:    {result.location}")
            print(f"      reason:   {result.reason}")
        for problem in structural_problems:
            print(f"  {problem}")
            print("      reason:   table could not be verified")
        print("")
        print("Fix each row by reading the file and citing the line the symbol is on,")
        print("or remove the row if the symbol no longer exists.")
        return 1

    print("All cited symbols were found at their recorded locations.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_traceability.py",
        description=(
            "Verify that every 'Key functions and classes' row in "
            ".architecture/components/*.md cites a file that exists and a "
            "symbol that is really there."
        ),
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="repository root to check (default: the current directory)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser()
    if not repo_root.is_dir():
        print(f"Not a directory: {repo_root}", file=sys.stderr)
        return 2
    repo_root = repo_root.resolve()

    try:
        return verify(repo_root)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
