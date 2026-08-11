# Example — a repository with almost nothing in it

The brief asks that a repository with no frontend get an `fe.md` marked
`missing`, *not* a fabricated one. That behaviour is encoded in the skill
(Rule 3) and in `references/module-taxonomy.md`, but the main demo repository
happens to contain every module, so a run against it cannot exercise it.

This folder is the captured output of `/arch_init` against a bare project
created with `uv init` — one `pyproject.toml`, one `main.py` containing a
`print()`, and nothing else.

## What the run produced

Five of the six canonical modules came back `missing`:

| Module | Status |
|---|---|
| Usage | `current` — a bare uv project genuinely has project metadata |
| Frontend | `missing` |
| Backend | `missing` |
| Database | `missing` |
| API | `missing` |
| Tests | `missing` |

No `infra` module was created at all. `infra` is optional in the taxonomy, so
absent evidence means no file and no index row — `missing` is reserved for
modules a reader would expect to find. Nothing was fabricated anywhere.

## Files here

- `architecture.md` — the index, showing the five `missing` rows.
- `fe.md` — a representative stub. Its `## Idea` section enumerates the evidence
  that was looked for and not found: no `package.json` at any depth, no
  `frontend/`/`web/`/`ui/`/`client/` directory, no `.jsx`/`.tsx`/`.vue`/`.svelte`
  sources, no `vite.config.*`, no `templates/` plus `static/` backed by a
  template engine in the dependency set, and no `StaticFiles` or
  `Jinja2Templates` use in the Python source.

Its symbol, interface and dependency sections are empty by construction rather
than by omission, and say so.

## The tripwire

A `missing` stub declares `**Scope:** none`, which yields no globs. The commit
hook then falls back to its built-in defaults for that module id. Nothing
matches today — that is why the module is missing — but if a `frontend/`
directory ever appears, the next commit flags `fe` as `drift` and `/arch_check`
gets the chance to promote the stub into a real record.
