# Module taxonomy

The canonical module set, the evidence that justifies claiming each module
exists, the evidence that means it is `missing`, and the Scope globs that define
file ownership.

Rule 4 governs everything here: **discover, never assume.** A module is claimed
because evidence was found, not because the slot exists. A module is `missing`
because evidence was looked for and not found — and the stub says what was
looked for.

---

## 0. Canonical and optional modules

**Canonical — always six files.** `usage`, `fe`, `be`, `db`, `api`, `tests`
each get a `components/<id>.md` file and a row in the module index on every
run, whether or not the repository has them. With no evidence, the file is a
`missing` stub (schemas.md §2.3) and the row's Status is `missing`.

**Optional — created only when warranted.** `infra`, `auth`, `cli` get a file
and an index row **only** when their positive evidence is present. No evidence
means no file and no row — not a `missing` stub. `missing` is a statement about
a module the reader expects; nobody expects a Terraform module in a library.

The module **id** is the filename stem and the key everything else keys off:
`components/be.md`, `pending.jsonl` `"module": "be"`, the hook's scope map. The
**display name** is what appears in the `# ` title and the index `Module` cell.

| Id | Display name | Class |
|---|---|---|
| `usage` | Usage | canonical |
| `fe` | Frontend | canonical |
| `be` | Backend | canonical |
| `db` | Database | canonical |
| `api` | API | canonical |
| `tests` | Tests | canonical |
| `infra` | Infrastructure | optional |
| `auth` | Auth | optional |
| `cli` | CLI | optional |

---

## 1. How to read the evidence lists

**Positive evidence** is what justifies claiming the module exists. One strong
signal is enough; a weak signal alone is not. Dependency evidence is read from
`pyproject.toml` (`[project] dependencies`, `optional-dependencies`,
dependency-groups) with versions resolved from `uv.lock`. Path evidence is
found by walking the repository, skipping `.git`, `.venv`, `venv`,
`node_modules`, `dist`, `build`, `__pycache__`, `.pytest_cache`,
`.architecture/.backups`, and anything `.gitignore` matches.

**Evidence of `missing`** is the *absence* of every positive signal — record it
that way in the stub's Idea section: "looked for X, Y, Z; found none". Never
write `missing` because a directory has an unfamiliar name; look inside first.

**Never name a framework that is not in the dependency set** (Rule 4). If there
is no FastAPI in `pyproject.toml`, no record mentions FastAPI.

---

## 2. Scope globs

The `**Scope:**` line of each component file is the authoritative statement of
what that module owns. The commit hook reads those lines back —
`load_module_scopes` in `scripts/commit_watch.py` — so the globs below are not
documentation of the hook; they *are* its configuration.

Mechanics that constrain how they are written:

- **One line.** The hook's regex is single-line (`^\*\*Scope:\*\*\s*(.+)$`).
  Globs pushed onto a second line are silently dropped and those files stop
  being watched. Comma-separated, backticks optional.
- **Paths are repo-relative, POSIX-separated**, matched against the full path
  as git reports it in `git show --name-only`.
- **`**` crosses directory separators; a single `*` does not.** `src/*.py`
  matches `src/main.py` but not `src/todo/main.py`. This is stricter than
  `fnmatch` and is deliberate.
- **The pattern must match the whole path.** `services/**` does not match
  `src/todo/services/tasks.py`; write `**/services/**`.
- Anchor a glob to a real directory whenever the layout allows it
  (`src/todo/api/**` beats `**/api/**`). Floating `**/` patterns are for
  layouts you could not pin down.
- `.architecture/**` is owned by nobody. Never put it in a Scope line — the
  records would flag themselves on every commit.

The tables below give the **discovery defaults**: what to write when the
evidence is present but the layout is generic. Replace them with anchored globs
once discovery has told you where things actually live.

---

## 3. The canonical six

### `usage` — Usage

| | |
|---|---|
| **Positive evidence** | `pyproject.toml` with a `[project]` table (always true for a Python + uv repo); `uv.lock`; `[project.scripts]` entry points; root `README.md`; `Makefile` / `justfile` / `taskfile.yml`; `.python-version`; a `__main__.py`; `.env.example`. |
| **`missing` when** | No `pyproject.toml` and no lockfile and no runnable entry point — i.e. not an installable project. In a Python + uv repository this should not happen; if it does, say exactly that in the stub rather than inventing a run recipe. |
| **Scope globs** | `pyproject.toml`, `uv.lock`, `README.md`, `Makefile`, `justfile`, `.python-version`, `.env.example`, `**/__main__.py`, `**/cli.py` |

`usage` is the "how do I run this" module: install, entry points,
configuration, environment variables. It owns project metadata, not source. If
a `cli` module exists, `cli` takes `**/cli.py` and `**/__main__.py` and `usage`
drops them from its Scope line — see §5.

### `fe` — Frontend

| | |
|---|---|
| **Positive evidence** | A `frontend/`, `web/`, `ui/`, or `client/` directory with a `package.json`; `*.jsx` / `*.tsx` / `*.vue` / `*.svelte` sources; `vite.config.*` / `next.config.*`; a server-rendered UI — `templates/` with `*.html` plus `static/`, and a template engine in the dependency set (`jinja2`, `django`); a `StaticFiles` mount or `Jinja2Templates` use in the Python source. |
| **`missing` when** | No JS/TS package manifest anywhere, no `templates/` or `static/` directory, no template-engine dependency, and no route that returns HTML. An API-only service. Say "API-only: no package.json, no templates, no HTML responses". |
| **Scope globs** | `frontend/**`, `web/**`, `ui/**`, `client/**`, `**/templates/**`, `**/static/**` |

The `fe` record describes the UI as a component of *this* system — how it
reaches the backend, what it assumes — not as a JavaScript project. Do not
enumerate npm dependencies; the Dependencies section is sourced from
`pyproject.toml` (schemas.md §2.2).

### `be` — Backend

| | |
|---|---|
| **Positive evidence** | A `services/`, `domain/`, `core/`, `logic/`, `use_cases/`, or `handlers/` package; modules that import the data layer but no HTTP framework symbols; functions that enforce rules rather than route or persist. |
| **`missing` when** | The repository is a library or CLI with no service layer, or all logic lives inside route handlers with nothing between routing and persistence. Both are real designs — record which one, and note that the logic is in `api` (or absent), rather than fabricating an empty layer. |
| **Scope globs** | `**/services/**`, `**/domain/**`, `**/core/**`, `**/use_cases/**` |

If the repository is a pure library, `be` is the right home for the library's
own logic package — say so explicitly in Idea, since "backend" would otherwise
imply a server.

### `db` — Database

| | |
|---|---|
| **Positive evidence** | A persistence dependency — `sqlalchemy`, `sqlmodel`, `psycopg`, `asyncpg`, `pymongo`, `redis`, `alembic`, `peewee`, `tortoise-orm`, `django`; a `db/`, `database/`, `models/`, `migrations/`, or `alembic/` directory; `alembic.ini`; a `*.sql` schema; declarative `Base`, `create_engine`, `sessionmaker`, or a `Session` dependency; a `DATABASE_URL` in `.env.example`. |
| **`missing` when** | No persistence dependency, no migration directory, no schema file, no ORM base class. State how the system holds state instead — in memory, on disk as JSON, not at all. |
| **Scope globs** | `**/db/**`, `**/database/**`, `**/models/**`, `**/migrations/**`, `**/alembic/**`, `alembic.ini`, `**/*.sql` |

`models/` belongs to `db` even when the models carry behaviour: the schema is
the thing that must not be described twice.

### `api` — API

| | |
|---|---|
| **Positive evidence** | An HTTP framework dependency — `fastapi`, `flask`, `django`, `starlette`, `litestar`, `sanic`, `aiohttp`, `bottle`; an `api/`, `routers/`, `routes/`, `endpoints/`, or `views/` directory; `APIRouter()`, `@app.get`, `@app.route`, `urlpatterns`; an ASGI/WSGI app object; `openapi.json` or an OpenAPI spec file. |
| **`missing` when** | No HTTP framework in the dependency set and no route decorators or URL table anywhere. A library or CLI with no network surface. Note that "has a `requests`/`httpx` dependency" is evidence of an API *client*, not of this module. |
| **Scope globs** | `**/api/**`, `**/routers/**`, `**/routes/**`, `**/endpoints/**`, `**/views/**`, `**/main.py`, `**/app.py`, `**/asgi.py`, `**/wsgi.py` |

`api` owns transport concerns only: routing, status codes, serialisation
schemas, middleware. When the same file both routes and decides, say so in
Interfaces rather than claiming a clean split that is not there.

### `tests` — Tests

| | |
|---|---|
| **Positive evidence** | A `tests/` or `test/` directory; `test_*.py` or `*_test.py` files anywhere; `pytest` / `unittest` / `hypothesis` / `coverage` / `tox` / `nox` in dev dependencies or a dependency group; `[tool.pytest.ini_options]`, `pytest.ini`, `tox.ini`, `noxfile.py`; a `conftest.py`. |
| **`missing` when** | No test files, no test runner dependency, no runner configuration. Say it plainly — an untested repository is a fact about the architecture, and the stub is the honest place to record it. |
| **Scope globs** | `tests/**`, `test/**`, `**/test_*.py`, `**/*_test.py`, `conftest.py`, `**/conftest.py`, `pytest.ini`, `tox.ini`, `noxfile.py` |

`tests` owns test files wherever they live, including tests inside a source
package — see the tie-break ladder in §5.

---

## 4. The optional three

### `infra` — Infrastructure

| | |
|---|---|
| **Positive evidence** | `Dockerfile`, `docker-compose.yml`/`.yaml`, `.dockerignore`; `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`; `*.tf` / `*.tfvars`; `k8s/`, `helm/`, `charts/`, `deploy/`, `infra/`; `Procfile`, `fly.toml`, `vercel.json`, `railway.json`, `serverless.yml`. |
| **Not created when** | None of the above. A repository that is only ever run locally has no infrastructure module; do not create a stub for it. |
| **Scope globs** | `Dockerfile*`, `docker-compose*`, `.dockerignore`, `.github/**`, `.gitlab-ci.yml`, `Jenkinsfile`, `**/*.tf`, `**/*.tfvars`, `k8s/**`, `helm/**`, `charts/**`, `deploy/**`, `infra/**`, `Procfile`, `fly.toml` |

### `auth` — Auth

| | |
|---|---|
| **Positive evidence** | An auth dependency — `passlib`, `bcrypt`, `argon2-cffi`, `python-jose`, `pyjwt`, `authlib`, `fastapi-users`, `python-multipart` alongside a login route, `django.contrib.auth`; an `auth/`, `security.py`, `permissions.py`, or `identity/` module; `OAuth2PasswordBearer`, `HTTPBearer`, `login_required`, a `get_current_user` dependency; `/login`, `/token`, `/register` routes; a `User` model with a password-hash column; `SECRET_KEY` / `JWT_*` in `.env.example`. |
| **Not created when** | No auth dependency, no credential handling, no session or token issuance. An open service is a design decision — record it in one line of the `api` record's Interfaces section instead of creating an empty module. |
| **Scope globs** | `**/auth/**`, `**/auth.py`, `**/security.py`, `**/permissions.py`, `**/identity/**` |

Auth is worth splitting out precisely because it cuts across `api`, `be` and
`db`. When you create it, take those files *away* from the other three modules'
Scope lines — see §5.

### `cli` — CLI

| | |
|---|---|
| **Positive evidence** | `[project.scripts]` entry points pointing at a command module; `typer`, `click`, `rich-click`, `argparse`-driven `main()`, `cyclopts`, `fire` in dependencies; a `cli/` package, `cli.py`, or `__main__.py` that parses arguments; a `commands/` package of subcommands. |
| **Not created when** | No console-script entry point and no argument-parsing module. `python -m package` with no parser is not a CLI; that is `usage`. |
| **Scope globs** | `**/cli/**`, `**/cli.py`, `**/__main__.py`, `**/commands/**` |

---

## 5. One file, one owner

**The rule: every file in the repository is owned by at most one module, and no
file is owned by two.**

This is enforced when the Scope lines are written, not afterwards. The commit
hook does not arbitrate — `map_files_to_modules` in `scripts/commit_watch.py`
tests each changed path against every module's globs and records **every**
match, so overlapping Scope lines flag two modules for one file, put two rows
into `pending.jsonl`, and make `/arch_check` reconcile a module that did not
change. Disjointness is the author's job.

"At most one" rather than "exactly one": files legitimately owned by nobody
exist and are fine — `.architecture/**`, `.git/**`, `.gitignore`, editor
config, anything `.gitignore` matches. Do not invent a module to absorb them.
But a *source* file with no owner is a discovery gap: either widen the right
module's Scope or say in that module's Idea why the file sits outside it.

### Breaking ties

When two modules' globs both match a path, apply these in order and stop at the
first that decides:

1. **Anchored beats floating.** A glob with a real directory prefix wins over
   one that starts with `**/`. `src/todo/api/**` beats `**/routers/**`.
2. **Longer literal prefix wins.** Between two anchored globs, the one with
   more matched literal path segments before its first wildcard wins.
   `src/todo/db/models/**` beats `src/todo/**`.
3. **Fewer wildcards wins.** An exact filename beats a pattern:
   `pyproject.toml` beats `**/*.toml`.
4. **The specialisation ladder**, highest priority first:

   `tests` › `infra` › `cli` › `auth` › `api` › `db` › `fe` › `be` › `usage`

   The ordering principle: cross-cutting concerns claim their files from the
   layers they cut across, and `usage` is last because it is the catch-all for
   project-level files. Worked cases:

   - `tests/test_api.py` → `tests`, not `api`. Test-ness beats subject matter,
     always; this is why `tests` is at the top.
   - `src/todo/services/auth.py` → `auth`, not `be`, when an `auth` module
     exists; otherwise `be`.
   - `src/todo/cli.py` → `cli`, not `usage`, when a `cli` module exists;
     otherwise `usage`.
   - `.github/workflows/test.yml` → `infra`, not `tests`. Rule 1 decides it
     first — `.github/**` is anchored, `**/test_*.py` does not match — and the
     ladder agrees for the CI file that *runs* the suite.
   - `src/todo/api/deps.py` holding a `get_current_user` dependency → `auth`
     when that module exists; the `api` Scope line then excludes it explicitly.

5. **Still tied?** The globs are wrong. Rewrite the losing module's Scope line
   so it no longer matches, and note the boundary in one line of that module's
   Interfaces section — "authentication dependencies under `api/` belong to the
   Auth module". Never leave a file matched by two Scope lines because the
   ladder happens to resolve it; the hook does not run the ladder.

### When creating an optional module

Creating `auth`, `cli`, or `infra` **narrows** the canonical modules. In the
same run, edit the Scope lines of every module that previously matched those
paths, so the union stays disjoint. An optional module added without that edit
double-flags every commit that touches it.

### `missing` modules and the hook's fallback

A `missing` module's `**Scope:** none` yields no globs. The hook then falls back
to its built-in `DEFAULT_SCOPES` entry for that module id
(`scripts/commit_watch.py`), which exists for `usage`, `fe`, `be`, `db`, `api`,
`tests` and `infra`, but **not** for `auth` or `cli`.

For the six canonical modules this is useful rather than harmful: nothing
matches today — that is why the module is `missing` — but if a `frontend/`
directory ever appears, the next commit flags `fe` as `drift` and `/arch_check`
gets a chance to promote the stub into a real record. Treat it as a tripwire,
and do not try to defeat it by writing decoy globs.
