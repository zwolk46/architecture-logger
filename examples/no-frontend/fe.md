# Frontend

<!-- ARCH-LOGGER:BEGIN purpose -->
**Scope:** none
**Entry points:** none

## Idea
This repository has no frontend module. blankproj presents no user interface of
any kind — not a JavaScript application, not a server-rendered one.

Evidence looked for and not found:

- a `package.json` anywhere in the tree — the repository contains no JavaScript
  or TypeScript manifest at any depth;
- `frontend/`, `web/`, `ui/` or `client/` directories — none exist;
- `.jsx`, `.tsx`, `.vue` or `.svelte` sources — none exist;
- a `vite.config.*` or `next.config.*` — none exist;
- a server-rendered UI: a `templates/` directory of `.html` files with a
  `static/` directory beside it, backed by a template engine in the dependency
  set — none of the three are present, and `[project] dependencies` is empty;
- a `StaticFiles` mount or `Jinja2Templates` use in the Python source — the only
  Python file is `main.py`, which has no imports.

The repository's sole output path is a `print()` call to stdout.
<!-- ARCH-LOGGER:END purpose -->

<!-- ARCH-LOGGER:BEGIN key-symbols -->
## Key functions and classes
_No symbols: this module does not exist in this repository._
<!-- ARCH-LOGGER:END key-symbols -->

<!-- ARCH-LOGGER:BEGIN interfaces -->
## Interfaces
_None._
<!-- ARCH-LOGGER:END interfaces -->

<!-- ARCH-LOGGER:BEGIN dependencies -->
## Dependencies
_None._
<!-- ARCH-LOGGER:END dependencies -->

## Drift log

<!-- ARCH-LOGGER:BEGIN drift-log -->
<!-- ARCH-LOGGER:END drift-log -->
