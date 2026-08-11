# Context7 policy

The full boundary: tool names, when to call, when never to call, the call
budget, the caching rule, and what to do when Context7 is unreachable.

Context7 has exactly one job in this plugin: **resolving what a third-party
package's function or API actually does, instead of relying on the model's
memory.** It is not decorative and it is not a search engine. Everything below
follows from that one job.

---

## 1. The tools

The plugin declares Context7 in `.mcp.json` as an HTTP server named `context7`,
so Claude Code namespaces its tools as
`mcp__plugin_architecture-logger_context7__<tool>`. Two calls, always in this
order:

| Step | Tool | Role |
|---|---|---|
| 1. Resolve | `mcp__plugin_architecture-logger_context7__resolve-library-id` | Turn a package name from `pyproject.toml` into a Context7 library id, e.g. `fastapi` → `/tiangolo/fastapi`. |
| 2. Fetch | `mcp__plugin_architecture-logger_context7__get-library-docs` | Retrieve documentation for that library id. |

Never call the fetch step with a guessed id. `/tiangolo/fastapi` looks
memorable, but a wrong id fails silently into a confident-sounding answer about
a different package — which is exactly the failure this server exists to
prevent. Ids come from the resolve step or from the cache (§4), never from
recall.

Narrow the fetch to the thing you are documenting — the specific API, class, or
concept named in the Interfaces or Dependencies section you are writing — not
the library at large. One focused fetch answers the question; a broad one
returns a tour you then have to summarise from, which reintroduces the guessing.

---

## 2. When to call — the whole list

Call Context7 only in these situations:

1. **Writing a `## Dependencies` section** of a `components/*.md` file, when
   the record needs to say what a package *does for this module*, not merely
   that it is imported.
2. **Writing an `## Interfaces` section**, when the interface is defined by a
   third-party contract: what a framework's dependency-injection callable
   receives, what an ORM session guarantees at commit, what a migration
   operation does to the schema.
3. **Describing a repository symbol that is a thin wrapper over a library
   call** — a FastAPI dependency, a SQLAlchemy session pattern, an Alembic
   operation — where the `Idea` cell cannot be written honestly without knowing
   the library's behaviour.

Two preconditions apply to all three:

- **The package is in the dependency set.** Read it from `pyproject.toml`;
  resolve its version from `uv.lock` and use that version when fetching, so the
  documentation matches the code that is actually installed (Rule 4). A package
  that is not a dependency is not documented at all, so it is never resolved.
- **Reading the repository first has not answered the question.** Context7
  explains the library's side of the boundary. The repository's own code
  explains everything on this side of it.

---

## 3. When never to call

Never call Context7 for:

- **Symbols defined inside this repository.** Read the file. Rule 1 requires a
  real `path.py:LINE` citation obtained by reading, and no external source can
  supply one.
- **The Python standard library.** `pathlib`, `dataclasses`, `json`,
  `subprocess`, `asyncio` — none of these are third-party packages and none go
  in a `## Dependencies` section sourced from `pyproject.toml`.
- **General-purpose search.** "What is hexagonal architecture", "how should I
  structure a FastAPI project", "what does this error mean" — not this
  server's job, and not something an architecture record should contain.
- **Anything outside the Dependencies and Interfaces sections and the thin-
  wrapper case in §2.3.** The Purpose, Idea, Module index, and Module summaries
  regions describe *this* repository; a library lookup cannot inform them.
- **Filling a gap you could close by reading.** If you are unsure a symbol
  exists, read the file again or omit the row (Rule 1). Do not substitute
  library documentation for source you have not opened.
- **Packages absent from `pyproject.toml`.** Rule 4: never name a framework,
  library, or tool that does not appear in the dependency set. Resolving one is
  a sign the record is about to name it.

---

## 4. Budget and caching

**Budget: at most one resolve and one fetch per distinct library, per command
run.** A run of `/arch_init` that documents six modules importing FastAPI makes
**one** resolve and **one** fetch for FastAPI in total — not one per module.
Hold the resolved id and the fetched content in working memory for the rest of
the run and reuse them across every component file you write.

Under budget by design: if the answer is already in hand, do not spend the call.
A run that resolves nothing because every dependency was already cached is a
correct run, not a lazy one.

**Cache by writing the resolved id into the record.** The `## Dependencies`
section of the component file is the cache: record the library id next to the
package so a later run reads it out of the document and skips the resolve step
entirely, going straight to fetch. Format:

```markdown
## Dependencies
- `fastapi` 0.115.6 — routing, dependency injection and request validation for
  the module's routers. (context7: `/tiangolo/fastapi`)
- `sqlalchemy` 2.0.36 — `Session` type only, for objects handed in by the API
  module. (context7: `/sqlalchemy/sqlalchemy`)
```

The `(context7: /org/project)` suffix is the cache entry. Rules for it:

- Write it whenever a resolve succeeds, even if the fetch is what you actually
  needed.
- Read it before resolving: a cached id in **any** component file is valid for
  the whole repository, so scan the existing records before the first resolve
  of a run.
- Re-resolve only when the package name changes, when the recorded id fails, or
  when the cached line is absent. A version bump in `uv.lock` does not
  invalidate the id — the id identifies the project, the version scopes the
  fetch.
- Do not write a cache suffix for a package you never resolved. An unverified
  id in the cache is worse than no cache, because the next run will trust it.

---

## 5. When Context7 is unreachable

If the server is down, the tool errors, or the resolve returns no match:
**say so in the document. Do not write the description from memory.**

The whole point of the boundary is that memory is not a source. A record that
silently falls back to recall is indistinguishable from one that consulted the
docs, which makes every other line in it less trustworthy.

Write the affected section like this:

```markdown
## Dependencies
- `alembic` 1.14.0 — imported by `src/todo/db/migrations/env.py:12`; used for
  schema migrations.

> Context7 was unreachable at 2026-08-11T09:41:07Z, so `alembic`'s behaviour is
> described here only from this repository's own usage of it and has not been
> verified against upstream documentation.
```

- Keep every claim that came from reading the repository — imports, call sites,
  versions, paths. Those are observed and still true.
- Drop the claims that would have needed the docs. An omitted sentence is a
  smaller defect than a wrong one.
- State it once per affected section, with the timestamp, inside the generated
  fence, so the next successful run replaces the note along with the content.
- Report it in the command's closing summary too, so the user knows which
  sections are provisional.
- Do not retry in a loop. One failed resolve for a library is the budget for
  that library in that run.

---

## 6. Worked examples

### DO

**DO 1 — a framework contract in `## Interfaces`.**
Writing `components/api.md` for a repo whose `pyproject.toml` pins
`fastapi 0.115.6`. The routers use `Depends(get_db)` and the record needs to
state when the session is closed relative to the response.

- Resolve `fastapi` → `/tiangolo/fastapi`, fetch scoped to dependencies with
  `yield`.
- Write the resolved behaviour into `## Interfaces`, cache
  `(context7: /tiangolo/fastapi)` in `## Dependencies`.
- **Why it qualifies:** the fact needed is the framework's teardown ordering —
  it lives on FastAPI's side of the boundary and the repository's code does not
  state it anywhere.

**DO 2 — a thin wrapper whose `Idea` cell is otherwise a guess.**
`components/db.md` has a row for `` `get_session()` `` at
`src/todo/db/session.py:28`. The function is four lines: it wraps
`sessionmaker(bind=engine, expire_on_commit=False)`. The Idea cell should
explain what `expire_on_commit=False` buys this system.

- One resolve for `sqlalchemy` (or the cached `/sqlalchemy/sqlalchemy`), one
  fetch scoped to session configuration.
- **Why it qualifies:** §2.3 exactly — the repository symbol is a thin wrapper,
  and the decision it embodies is a decision about library behaviour. The
  `Location` cell still comes from reading `session.py`.

**DO 3 — one resolve serving several modules.**
`/arch_init` on a repo where `api`, `be` and `db` all import `pydantic`.

- Resolve `pydantic` once, fetch once scoped to validators, then write all
  three Dependencies sections from that single fetch, caching the id in each.
- **Why it qualifies:** it is the budget rule working as intended — per distinct
  library per run, not per section.

### DON'T

**DON'T 1 — a repo-defined symbol.**
Writing the `Idea` cell for `` `create_task()` `` at
`src/todo/services/tasks.py:41` and reaching for Context7 to find out what it
does.

- **Why it is forbidden:** the symbol is defined in this repository. §3, first
  bullet. Read `src/todo/services/tasks.py`. Nothing Context7 returns could
  produce the `:41` citation Rule 1 requires, and a plausible-sounding
  description of a function you have not read is precisely the "invented
  function" that fails the section.

**DON'T 2 — the standard library, or a package that is not a dependency.**
`components/usage.md` documents an entry point built on `argparse`, and the
draft reaches for Context7 to describe subparsers. Or: the summary is about to
mention Celery because the module looks queue-shaped, and Context7 is called to
check what Celery does.

- **Why it is forbidden:** `argparse` is the standard library — §3, second
  bullet — and Celery is not in `pyproject.toml`, so Rule 4 forbids naming it
  at all. The second case is the more dangerous one: the resolve call is the
  moment to notice you are about to document a package this repository does not
  have.

**DON'T 3 — general search, and per-module re-resolution.**
Two shapes of the same waste: fetching FastAPI docs to decide how to split the
`api` and `be` modules, and resolving `sqlalchemy` afresh in each of the four
component files that import it.

- **Why it is forbidden:** the first is general-purpose search (§3, third
  bullet) — module boundaries are established by discovery (Rule 4) and the
  taxonomy, not by a framework's opinions. The second blows the budget (§4):
  one resolve, one fetch, per distinct library, per run — and the cached
  `(context7: /sqlalchemy/sqlalchemy)` in the first file's Dependencies section
  is there so the remaining three skip the resolve entirely.
