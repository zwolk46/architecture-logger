# Document schemas

The exact required structure of `.architecture/architecture.md` and
`.architecture/components/<module>.md`, and which regions sit inside
`ARCH-LOGGER` generated-block fences.

Load this file before writing or reconciling any record. The structures below
are the contract; `/arch_init`, `/arch_check` and `/arch_make_documentation` all
read and write against them.

---

## 0. The ownership model

Every generated region is wrapped in a matched pair of HTML comments:

```
<!-- ARCH-LOGGER:BEGIN <block-id> -->
...generated content...
<!-- ARCH-LOGGER:END <block-id> -->
```

- **Inside a fence — machine-owned.** Replaced wholesale on every run. Never
  append a second copy below an existing block; rewrite the block in place.
- **Outside every fence — human-owned.** Copied through byte-for-byte. Never
  edit, reflow, or relocate it.
- Block ids are unique **within a file**. The same id may appear in both
  document types (`purpose` does), because they are different files.
- A file we would normally generate that contains **no** fence markers is
  treated as entirely human-authored: say so, back it up, and ask before
  writing (Rule 2).

There are exactly seven block ids across the two documents:

| Block id | Document | Wraps |
|---|---|---|
| `purpose` | `architecture.md` | the two blockquote lines + `## Purpose` |
| `module-index` | `architecture.md` | `## Module index` + its table |
| `module-summaries` | `architecture.md` | `## Module summaries` + every `###` subsection |
| `purpose` | `components/<module>.md` | `**Scope:**` + `**Entry points:**` + `## Idea` |
| `key-symbols` | `components/<module>.md` | `## Key functions and classes` + its table |
| `interfaces` | `components/<module>.md` | `## Interfaces` + its prose |
| `dependencies` | `components/<module>.md` | `## Dependencies` + its prose |
| `drift-log` | `components/<module>.md` | the drift entries **only** — not the `## Drift log` heading |

Two consequences worth stating outright:

1. **The sync banner lives inside `purpose`.** Rule 2 requires that running
   `/arch_init` twice produce no diff *beyond the synced timestamp and commit
   SHA* — so those two blockquote lines must be machine-owned, and `purpose` is
   the block that covers the document preamble. Section headings of generated
   sections live inside their own fence.
2. **`## Drift log` is the one heading that sits outside its fence.** The
   commit hook creates the section that way (`scripts/commit_watch.py`
   `append_drift_log`) and inserts each new line immediately before
   `<!-- ARCH-LOGGER:END drift-log -->`. Keep the heading outside or the hook
   will build a second section beneath yours.

Human-owned in both documents, in every run:

- The `# ` H1 title line. The machine writes it once, when it creates the file;
  from then on it is outside every fence and is preserved byte-for-byte, so a
  human may retitle a record freely.
- The `## Drift log` heading line.
- Any prose, section, or note a human adds between, before, or after fenced
  blocks. Blank-line separation around fences exists so humans have somewhere
  to write.

---

## 1. `.architecture/architecture.md`

### 1.1 Required structure (brief §2.1), with fences annotated

Everything outside the `BEGIN`/`END` pairs below is human-owned.

````markdown
# Architecture — <repo name>

<!-- ARCH-LOGGER:BEGIN purpose -->
> Generated and maintained by `architecture-logger`.
> Last synced: <ISO-8601 timestamp> · commit `<short sha>`

## Purpose
<2–4 sentences: what this system does and for whom.>
<!-- ARCH-LOGGER:END purpose -->

<!-- ARCH-LOGGER:BEGIN module-index -->
## Module index
| Module | Detail file | Short description | Status |
|---|---|---|---|
| Usage | components/usage.md | … | current |
| Frontend | components/fe.md | … | current |
| Backend | components/be.md | … | drift |
| Database | components/db.md | … | current |
| API | components/api.md | … | current |
| Tests | components/tests.md | … | current |
<!-- ARCH-LOGGER:END module-index -->

<!-- ARCH-LOGGER:BEGIN module-summaries -->
## Module summaries
### Usage
<3–6 lines. What the module covers, its boundary, its one most important fact.>

### Frontend
…
<!-- ARCH-LOGGER:END module-summaries -->
````

### 1.2 Rules for this document

**Title.** `# Architecture — <repo name>`, em dash, one space either side.
`<repo name>` is the `[project] name` from `pyproject.toml`, falling back to the
repository directory name.

**The two blockquote lines.** Both are required, in this order, as two
consecutive blockquote lines with no blank line between them:

```
> Generated and maintained by `architecture-logger`.
> Last synced: <ISO-8601 timestamp> · commit `<short sha>`
```

- Line 1 is fixed text. `architecture-logger` is in backticks.
- The separator between the two halves of line 2 is a middle dot with a single
  space either side: ` · ` (U+00B7). Not a hyphen, not an en dash.
- **Timestamp format:** UTC, second precision, `Z` suffix —
  `YYYY-MM-DDTHH:MM:SSZ`, e.g. `2026-08-11T09:41:07Z`. This is what
  `utc_now()` in `scripts/commit_watch.py` emits, so command-written and
  hook-written timestamps sort against each other.
- **Short-sha format:** exactly 7 lowercase hex characters, wrapped in
  backticks — `git rev-parse --short=7 HEAD`. On a repository with no commits
  yet, write `` `unborn` `` rather than inventing a sha.

**Purpose.** 2–4 sentences. What the system does and for whom. Not a feature
list, not a directory tour.

**Module index table.** Four columns, in this order, with these exact names:

| Module | Detail file | Short description | Status |

- Four columns, **Status last** — non-negotiable. The commit hook rewrites the
  last cell of a row it matches and skips any row with fewer than four cells
  (`flip_status_to_drift` in `scripts/commit_watch.py`).
- Separator row is `|---|---|---|---|`.
- `Module` is the module's **display name** (Usage, Frontend, …), not its id.
- `Detail file` is the repo-relative-to-`.architecture/` path
  `components/<module-id>.md`. The hook locates a row by this cell, so it must
  match the filename exactly; it is the only stable key in the table.
- `Short description` is one line — a clause, not a paragraph.
- `Status` is exactly one of `current` | `drift` | `missing` (Rule 3). Rows for
  `missing` modules stay in the table; they are never dropped.
- One row per module that has a file in `components/`, in a stable order:
  the canonical six first (`usage`, `fe`, `be`, `db`, `api`, `tests`), then any
  optional modules alphabetically.

**Module summaries.** One `###` subsection per module, in the same order as the
index table, with the same display name as the `Module` cell. 3–6 lines each:
what the module covers, its boundary, its one most important fact. A `missing`
module gets a summary too — one that says it is absent and what was looked for.

**The two-minute test.** A reader answers "what is this system and what are its
parts?" from this file alone, in under two minutes. If a summary needs a
seventh line, that detail belongs in the component file.

### 1.3 Worked example

Illustrative: the values below are for the hypothetical `todo-app` target
repository of brief §1, not for any repository in this working tree.

````markdown
# Architecture — todo-app

<!-- ARCH-LOGGER:BEGIN purpose -->
> Generated and maintained by `architecture-logger`.
> Last synced: 2026-08-11T09:41:07Z · commit `7993ece`

## Purpose
todo-app is a small task tracker that stores TODO items and exposes them over a
JSON HTTP API and a minimal web UI. It exists as a teaching-sized reference
system: one write path per entity, no background jobs, no queues. Its users are
developers reading it to understand how the parts of a uv-managed Python
service fit together.
<!-- ARCH-LOGGER:END purpose -->

<!-- ARCH-LOGGER:BEGIN module-index -->
## Module index
| Module | Detail file | Short description | Status |
|---|---|---|---|
| Usage | components/usage.md | Install, run and configure the app | current |
| Frontend | components/fe.md | Vite + React single-page UI | current |
| Backend | components/be.md | Task and list business rules | drift |
| Database | components/db.md | SQLAlchemy models, session, migrations | current |
| API | components/api.md | FastAPI routers and request schemas | current |
| Tests | components/tests.md | pytest suite and fixtures | current |
<!-- ARCH-LOGGER:END module-index -->

<!-- ARCH-LOGGER:BEGIN module-summaries -->
## Module summaries
### Usage
How to install, run and configure todo-app. Owns `pyproject.toml`, `uv.lock`
and the root `README.md`. `uv sync` then `uv run uvicorn todo.main:app` is the
whole story; there is no build step for the Python side. Configuration is
environment variables only — no config file is read at any point.

### Frontend
The `frontend/` Vite + React app. Owns everything under that directory and
nothing else. It talks to the service only through `/api/v1`, so it can be
served from any origin; there is no server-side rendering and no shared code
with the Python packages.

### Backend
Business rules for tasks and lists, under `src/todo/services/`. This is the
only layer allowed to mutate state: routers call into it, it calls into the
database module, and nothing calls back out. The due-date invariant — a task
may not be completed before it is created — is enforced here rather than in the
schema, because it needs the clock.

### Database
SQLAlchemy models, the session factory and Alembic migrations under
`src/todo/db/` and `src/todo/models/`. Owns the schema and nothing above it: no
query in this module knows why it is being run. Sessions are request-scoped and
handed out by a FastAPI dependency.

### API
FastAPI routers and Pydantic request/response schemas under `src/todo/api/`.
Owns HTTP concerns only — routing, status codes, serialisation, auth headers —
and delegates every decision to the backend module. Versioned under `/api/v1`;
adding a v2 means a new router package, not edits to this one.

### Tests
The pytest suite under `tests/`. Covers the service layer directly and the API
through `TestClient`; the frontend is not covered here. Fixtures build a
throwaway SQLite database per test session, so the suite needs no running
service and no network.
<!-- ARCH-LOGGER:END module-summaries -->
````

---

## 2. `.architecture/components/<module>.md`

One file per module, named for the module **id** (`usage.md`, `fe.md`, `be.md`,
`db.md`, `api.md`, `tests.md`, plus any optional module the repo warrants).
See [module-taxonomy.md](module-taxonomy.md) for ids, display names and scopes.

Component files carry **no** sync banner — the brief's §2.2 structure has none,
and the drift log already carries dated entries.

### 2.1 Required structure (brief §2.2), with fences annotated

Everything outside the `BEGIN`/`END` pairs below is human-owned.

````markdown
# <Module name>

<!-- ARCH-LOGGER:BEGIN purpose -->
**Scope:** <which paths/globs this module owns>
**Entry points:** <files or symbols where execution enters this module>

## Idea
<Why this module exists and what design decision it embodies. Not a file listing.>
<!-- ARCH-LOGGER:END purpose -->

<!-- ARCH-LOGGER:BEGIN key-symbols -->
## Key functions and classes
| Symbol | Location | Idea |
|---|---|---|
| `create_task()` | `src/todo/services/tasks.py:41` | Single write path for tasks; enforces the due-date invariant. |
<!-- ARCH-LOGGER:END key-symbols -->

<!-- ARCH-LOGGER:BEGIN interfaces -->
## Interfaces
<What it consumes, what it exposes — other modules, HTTP routes, tables, env vars.>
<!-- ARCH-LOGGER:END interfaces -->

<!-- ARCH-LOGGER:BEGIN dependencies -->
## Dependencies
<Relevant third-party packages, sourced from pyproject.toml.>
<!-- ARCH-LOGGER:END dependencies -->

## Drift log

<!-- ARCH-LOGGER:BEGIN drift-log -->
<Appended by the commit hook. Cleared by /arch_check.>
<!-- ARCH-LOGGER:END drift-log -->
````

### 2.2 Rules for this document

**Title.** `# <Module name>` — the display name, matching the `Module` cell of
the index row exactly.

**`**Scope:**` — one line, always.** The commit hook reads it with a
single-line regex (`^\*\*Scope:\*\*\s*(.+)$`); globs pushed onto a second line
are silently lost and those files stop being watched. Comma-separated globs,
backticks optional but conventional:

```
**Scope:** `src/todo/services/**`, `src/todo/domain/**`
```

For a `missing` module write exactly `**Scope:** none`.

**`**Entry points:**`** — the files or symbols where execution enters this
module: an ASGI app object, a router include, a console script, a test command.
"None — this module is only called by others" is a legitimate answer.

**`## Idea`** — why the module exists and what design decision it embodies. Not
a file listing, not a re-statement of the scope globs. This section and the
`Idea` column are the only places interpretation belongs.

**`## Key functions and classes`** — three columns, in this order, with these
exact names:

| Symbol | Location | Idea |

- Separator row is `|---|---|---|`.
- `Symbol` — the name as written in the source, in backticks, with `()` for
  callables: `` `create_task()` ``, `` `TaskRepository` ``.
- `Location` — `` `relative/path.py:LINE` `` in backticks, repo-relative,
  POSIX separators. Obtained by **reading the file**. Never inferred, never
  carried over from a previous run without re-reading. An invented row is a
  failed section (Rule 1).
- `Idea` — one sentence on why the symbol exists and what invariant or decision
  it embodies. The only inferable cell in the table.
- No fixed row count; include what a reader needs to navigate the module, not
  every public name.

**`## Interfaces`** — what it consumes and what it exposes: other modules, HTTP
routes, tables, env vars. Third-party behaviour described here is subject to
[context7-policy.md](context7-policy.md).

**`## Dependencies`** — relevant third-party packages, sourced from
`pyproject.toml`, with versions resolved from `uv.lock`. Only packages this
module actually imports. This section is also where resolved Context7 library
ids are cached — see [context7-policy.md](context7-policy.md).

**`## Drift log`** — heading outside the fence, entries inside it. Written by
the commit hook, cleared by `/arch_check`. The hook's line format is:

```
- <ISO-8601 timestamp> - commit `<short sha>` (<commit subject>) touched: `<path>`, `<path>`
```

for example:

```
- 2026-08-11T09:41:07Z - commit `7993ece` (feat: add due-date invariant) touched: `src/todo/services/tasks.py`
```

`/arch_check` parses these entries together with `.architecture/pending.jsonl`,
reports what drifted **before** changing anything, then empties the block back
to a single placeholder line and flips the module's Status to `current`. It
never deletes the section or the fence.

**Line-count guidance.** §2.2 states none, and none is imposed: component files
are as long as traceability requires. The numeric guidance in this plugin
applies to `architecture.md` only — 2–4 sentences of Purpose, 3–6 lines per
module summary. If a component file is short because the module is small, that
is a correct outcome; padding it is not.

### 2.3 The `missing` stub

A canonical module with no evidence in the repository still gets a file, so its
index row has somewhere to point (Rule 3). The stub keeps the full skeleton and
every fence — `/arch_init` must be able to fill it in later without a
structural rewrite — and changes only what it can honestly say:

- `**Scope:** none`
- `**Entry points:** none`
- `## Idea` — states plainly that the repository has no such module, and lists
  the evidence that was looked for and not found (see
  [module-taxonomy.md](module-taxonomy.md) for the per-module evidence lists).
- `## Key functions and classes` — the heading and an italic
  `_No symbols: this module does not exist in this repository._` **No table.**
  An empty table invites a fabricated row.
- `## Interfaces`, `## Dependencies` — `_None._`
- `## Drift log` — the fence, empty.
- Index row Status is `missing`.

Never fabricate a module to fill a slot. Optional modules do **not** get stubs:
if the evidence is absent, the file is simply not created.

### 2.4 Worked example

Illustrative: `src/todo/...` paths and line numbers below are for the
hypothetical `todo-app` target repository, and the `create_task()` row is the
brief's own. In real output every `Location` is read from the file it cites
(Rule 1).

````markdown
# Backend

<!-- ARCH-LOGGER:BEGIN purpose -->
**Scope:** `src/todo/services/**`, `src/todo/domain/**`
**Entry points:** `src/todo/services/tasks.py` and `src/todo/services/lists.py`,
called from the API routers; nothing else imports this package.

## Idea
The only layer permitted to change state. Routers translate HTTP into calls
here, this module decides whether the change is legal, and the database module
performs it. The rule that keeps the system small is one write path per entity:
there is exactly one function that creates a task and exactly one that
completes it, so an invariant added to that function cannot be bypassed by a
second caller. Invariants that need the clock or another row live here rather
than in the schema, because the schema cannot see them.
<!-- ARCH-LOGGER:END purpose -->

<!-- ARCH-LOGGER:BEGIN key-symbols -->
## Key functions and classes
| Symbol | Location | Idea |
|---|---|---|
| `create_task()` | `src/todo/services/tasks.py:41` | Single write path for tasks; enforces the due-date invariant. |
| `complete_task()` | `src/todo/services/tasks.py:78` | Idempotent completion — a second call is a no-op, so a retried request cannot double-count. |
| `TaskNotFound` | `src/todo/services/errors.py:12` | Domain-level absence, translated to a 404 by the API module so services never import HTTP types. |
| `list_tasks()` | `src/todo/services/lists.py:23` | Read path with pagination applied in SQL rather than in Python, to keep response time flat as the table grows. |
<!-- ARCH-LOGGER:END key-symbols -->

<!-- ARCH-LOGGER:BEGIN interfaces -->
## Interfaces
Consumes: the Database module — `Session` from `src/todo/db/session.py`, and
the `Task` and `TaskList` models. Every function takes a `Session` as its first
argument; this module never opens or closes one, so transaction boundaries stay
with the caller.

Exposes: the functions in the Key functions and classes table, imported by the
API module only. Raises `TaskNotFound` and `InvalidDueDate` from
`src/todo/services/errors.py` — the API module owns the mapping from those to
status codes.

Environment variables: none. Reads no configuration and no clock other than
`datetime.now(timezone.utc)`.
<!-- ARCH-LOGGER:END interfaces -->

<!-- ARCH-LOGGER:BEGIN dependencies -->
## Dependencies
- `sqlalchemy` 2.0.36 — `Session` type only, for the objects handed in by the
  API module. (context7: `/sqlalchemy/sqlalchemy`)

No other third-party package is imported here. Pydantic models stay in the API
module and ORM models stay in the Database module, which is what allows this
layer to be tested without either.
<!-- ARCH-LOGGER:END dependencies -->

## Drift log

<!-- ARCH-LOGGER:BEGIN drift-log -->
- 2026-08-11T09:41:07Z - commit `7993ece` (feat: add due-date invariant) touched: `src/todo/services/tasks.py`
<!-- ARCH-LOGGER:END drift-log -->
````
