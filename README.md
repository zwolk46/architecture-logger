# architecture-logger

A Claude Code plugin that treats architecture documentation as a living,
machine-maintained artifact: generated from the repository, flagged as the code
moves, and reconciled on demand.

Architecture docs rot because a human writes them once and never returns. This
plugin splits the job into three moments — **create** the records by reading the
repository, **notice** when the code has moved out from under them, and
**reconcile** the difference when asked — and automates all three.

Targets Python repositories managed by [uv](https://docs.astral.sh/uv/). The
layout of the repository is discovered, never assumed.

## Install

The plugin runs from a directory; no marketplace install is required.

```bash
claude --plugin-dir /path/to/architecture-logger
```

Run that from the repository you want documented. Verify it loaded with:

```bash
claude plugin validate /path/to/architecture-logger --strict
```

## Commands

| Command | What it does |
|---|---|
| `/arch_init` | Analyses the repository and writes the initial `.architecture/` records. |
| `/arch_check` | Reports what drifted, reconciles the affected records against the code, and prints a changelog of how the records changed. |
| `/arch_summary` | Renders the repository in the terminal — purpose, then each module with its description and status. Writes nothing. |
| `/arch_make_documentation` | Generates reader-facing `README.md` files and a repository `documentation.md` from the records. |

Commands appear namespaced as `/architecture-logger:arch_init` and so on; the
bare form works too unless another command has claimed the name.

## What it produces

```
.architecture/
├── architecture.md      the map: purpose, module index, one summary per module
├── components/          the territory: one detailed record per module
│   ├── usage.md
│   ├── fe.md
│   ├── be.md
│   ├── db.md
│   ├── api.md
│   └── tests.md
└── pending.jsonl        drift queue, written by the commit hook, drained by /arch_check
```

`architecture.md` answers "what is this system and what are its parts?" in under
two minutes. `components/*.md` carry the detail: scope, entry points, the design
idea, a table of key symbols with verified `path:line` citations, interfaces,
dependencies, and a drift log.

Three hidden files support the machinery and are gitignored:
`.architecture/.state.json` (the last commit the hook processed),
`.architecture/.backups/` (copies taken before any rewrite), and
`.architecture/.hook.log`.

## How drift is detected

A `PostToolUse` hook matching the Bash tool watches for commits. Claude Code has
no git-commit event, so the hook fires after **every** Bash call and filters
itself down through four guards: is this Bash, does the command plausibly
commit, does this repository have records, and — decisively — has the commit
hash actually changed since the last one processed. That last guard is what
distinguishes a real commit from `echo "git commit"`, from a commit that failed,
and from a re-fire for a commit already seen.

On a real commit the hook maps the changed files onto modules using the
`**Scope:**` globs declared in the component records themselves, appends to
`pending.jsonl`, writes a dated drift-log entry, and flips those modules to
`drift` in the index. It never rewrites documentation — see NOTES.md for why.

## Components

| Path | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Manifest. Nothing else lives in this directory. |
| `commands/*.md` | The four user-invoked commands. |
| `skills/architecture-records/` | The document schemas, traceability rule, module taxonomy and Context7 policy, shared by all four commands. |
| `hooks/hooks.json` | The `PostToolUse` commit watcher. |
| `scripts/commit_watch.py` | The hook implementation. Standard library only. |
| `scripts/verify_traceability.py` | Checks every cited symbol really exists at its cited line. Exits non-zero on any failure. |
| `scripts/arch_summary.py` | Renders the records for the terminal. |
| `.mcp.json` | Declares Context7. |

## Context7

The plugin declares one MCP server, [Context7](https://context7.com), as an HTTP
endpoint requiring no authentication. It has exactly one job: resolving what a
**third-party** package's API actually does, rather than relying on the model's
memory, when writing the Dependencies and Interfaces sections. It is never
consulted for symbols defined inside the repository, for the standard library,
or as a general search engine. The boundary is encoded in
`skills/architecture-records/references/context7-policy.md`.

If Context7 is unreachable, affected sections say so explicitly rather than
falling back on recall.

## Traceability

Every row of a "Key functions and classes" table must cite a real
`relative/path.py:LINE`. This is enforced mechanically rather than by
instruction:

```bash
python3 scripts/verify_traceability.py /path/to/repo
```

`/arch_init` and `/arch_check` both run it and refuse to report success while it
fails.

## Demo repository

A worked example — a small FastAPI + uv TODO application with generated records
and documentation — lives at DEMO_REPO_URL.

## Notes

Design decisions, trade-offs, known limitations and what I would do next are in
[NOTES.md](NOTES.md).
