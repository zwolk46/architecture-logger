# Architecture — blankproj

<!-- ARCH-LOGGER:BEGIN purpose -->
> Generated and maintained by `architecture-logger`.
> Last synced: 2026-08-11T15:42:22Z · commit `baa9e8e`

## Purpose
blankproj is a freshly initialised uv Python project that has not yet acquired
an application. Its entire behaviour is one function in `main.py` that prints a
greeting; it declares no dependencies, pins Python 3.13, and has no package
directory, no lockfile and no tests. These records exist to state plainly what
is here so that the first commit that adds real code has an honest baseline to
drift from.
<!-- ARCH-LOGGER:END purpose -->

<!-- ARCH-LOGGER:BEGIN module-index -->
## Module index
| Module | Detail file | Short description | Status |
|---|---|---|---|
| Usage | components/usage.md | Project metadata and the single runnable script | current |
| Frontend | components/fe.md | No user interface of any kind | missing |
| Backend | components/be.md | No service, domain or logic layer | missing |
| Database | components/db.md | No persistence; the program holds no state | missing |
| API | components/api.md | No HTTP framework and no network surface | missing |
| Tests | components/tests.md | No test files, runner or runner configuration | missing |
<!-- ARCH-LOGGER:END module-index -->

<!-- ARCH-LOGGER:BEGIN module-summaries -->
## Module summaries
### Usage
How to run blankproj, and the only module that owns anything. Covers
`pyproject.toml`, `README.md`, `.python-version` and `main.py` — project
metadata plus the one script. The whole run recipe is `python main.py`: there is
no `[project.scripts]` console script, no `__main__.py`, and no `[build-system]`
table, so nothing here is installable as a package yet. No configuration file is
read and no environment variable is consulted.

### Frontend
Absent. Looked for a `package.json` anywhere in the tree, `frontend/`, `web/`,
`ui/` and `client/` directories, `.jsx`/`.tsx`/`.vue`/`.svelte` sources, a Vite
or Next config, and a `templates/`+`static/` pair backed by a template-engine
dependency. None exist. The only output path in the repository is `print()` to
stdout.

### Backend
Absent. Looked for `services/`, `domain/`, `core/`, `logic/`, `use_cases/` and
`handlers/` packages, and for modules that enforce rules rather than route or
persist. The repository contains exactly one Python file, whose one function
prints a constant string. There is no logic layer to describe and no library
package that would be one under another name.

### Database
Absent. Looked for a persistence dependency, a `db/`, `database/`, `models/`,
`migrations/` or `alembic/` directory, an `alembic.ini`, a `.sql` schema, a
declarative base or session factory, and a `DATABASE_URL`. None exist —
`[project] dependencies` is empty. The system holds no state at all: `main()`
prints and returns, keeping nothing between runs.

### API
Absent. Looked for an HTTP framework in the dependency set, `api/`, `routers/`,
`routes/`, `endpoints/` or `views/` directories, route decorators or a URL
table, an ASGI/WSGI application object, and an OpenAPI document. None exist.
blankproj has no network surface in either direction — it is neither a server
nor a client.

### Tests
Absent. Looked for a `tests/` or `test/` directory, `test_*.py` or `*_test.py`
files anywhere, a test runner in the dependencies or a dependency group, a
`conftest.py`, and runner configuration in `pytest.ini`, `tox.ini`, `noxfile.py`
or `[tool.pytest.ini_options]`. None exist; `pyproject.toml` contains a
`[project]` table and nothing else. The repository is entirely untested.
<!-- ARCH-LOGGER:END module-summaries -->
