---
name: architecture-records
description: Schemas, rules and conventions for creating and maintaining .architecture/ records in a Python + uv repository. Load before writing or reconciling any architecture record.
user-invocable: false
---

# Architecture records

The knowledge base behind `/arch_init`, `/arch_check`, `/arch_summary` and
`/arch_make_documentation`. Every one of those commands loads this file first.
The rules below are non-negotiable and apply to all four. Detail lives in the
reference files listed at the bottom; load them when the task calls for them.

## What we are producing and why

`.architecture/` is a set of records that describe a repository as it actually
is, maintained by machine so it does not rot. `architecture.md` is the map: a
reader answers "what is this system and what are its parts?" from it alone in
under two minutes. `components/*.md` are the territory: one detailed record per
module. `pending.jsonl` is a queue of drift signals written by the commit hook
and drained by `/arch_check`.

## Rule 1 — Traceability

Every claim in a `components/*.md` file must be traceable to a real path or
symbol in the repository.

- Each row of a **Key functions and classes** table cites `relative/path.py:LINE`.
  Obtain that citation by actually reading the file. Never infer a line number.
- The **Idea** column is the only place interpretation belongs. It explains
  *why* the symbol exists and what invariant or decision it embodies, and it may
  be inferred. Everything else must be observed.
- An invented function is a failed section. If you are unsure a symbol exists,
  read the file again or omit the row.
- Before reporting success, run
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_traceability.py` from the
  repository root and fix every finding. Do not declare the command complete
  while it exits non-zero.

## Rule 2 — Never destroy human writing

Generated regions are fenced with HTML comments:

```
<!-- ARCH-LOGGER:BEGIN <block-id> -->
...generated content...
<!-- ARCH-LOGGER:END <block-id> -->
```

- Text **inside** a matched fence is machine-owned and is replaced wholesale on
  every run.
- Text **outside** any fence is human-owned and is copied through byte-for-byte.
  Never edit, reflow, or relocate it.
- Before rewriting any existing file, copy it to
  `.architecture/.backups/<ISO8601-timestamp>/` preserving its relative path.
- After writing, report how many human-authored regions were preserved.
- If a file that we would normally generate already exists and contains **no**
  fence markers, treat the whole file as human-authored: say so explicitly,
  back it up, and ask before writing.

This is what makes the commands idempotent: a second run replaces the contents
of a fence rather than appending a second copy beneath it. Running `/arch_init`
twice must produce no duplicated sections and no diff beyond the synced
timestamp and commit SHA.

## Rule 3 — Status vocabulary

Exactly three values, used in the Status column of the module index:

| Value | Meaning | Who sets it |
|---|---|---|
| `current` | Verified against the code as of the last sync | `/arch_init`, `/arch_check` |
| `drift` | Code owned by this module changed; the record is unverified | the commit hook only |
| `missing` | This module does not exist in this repository | `/arch_init` |

`drift` does not mean "wrong". It means "nobody has checked this since the code
moved". Only `/arch_check` may clear it.

`missing` modules get a short stub file stating that the repository has no such
module and what evidence was looked for. Never fabricate a module to fill a slot.

## Rule 4 — Discover, never assume

The plugin must work on any Python + uv repository, so no layout is ever
hardcoded.

- Walk the repository to establish structure. Skip `.git`, `.venv`, `venv`,
  `node_modules`, `dist`, `build`, `__pycache__`, `.pytest_cache`,
  `.architecture/.backups`, and anything matched by `.gitignore`.
- Detect the stack from `pyproject.toml`: `[project]` name, description,
  dependencies and optional-dependencies; `[project.scripts]` entry points;
  `[tool.*]` sections for tooling; the build backend.
- Use `uv.lock` for resolved versions, which matter when asking Context7 for
  version-specific documentation.
- Never name a framework, library, or tool that does not appear in the
  dependency set. If the repository has no FastAPI, it has no FastAPI section.

## Rule 5 — When to reach for Context7

Context7 has exactly one job here: resolving what a **third-party** package's
function or API actually does, instead of relying on memory.

Consult it when writing the **Dependencies** and **Interfaces** sections of a
component file, and when a key repository symbol is a thin wrapper over a
library call whose behaviour needs explaining — a FastAPI dependency, a
SQLAlchemy session pattern, an Alembic operation.

Never consult it for symbols defined inside this repository, for the standard
library, or as a general-purpose search engine. Read the code instead.

Full protocol, tool names, budget and caching: see
[references/context7-policy.md](references/context7-policy.md).

## Working order

1. Load this file. Load the reference files the task needs.
2. Discover the repository (Rule 4). Record evidence as you go.
3. Classify modules; decide which are present and which are `missing`.
4. Read the actual source for each present module before writing about it.
5. Consult Context7 for third-party behaviour only (Rule 5).
6. Write records to the schemas, inside fences (Rule 2).
7. Run the traceability verifier and fix every finding (Rule 1).
8. Report what was created, what was updated in place, and how many
   human-authored regions were preserved.

## Reference files

- [references/schemas.md](references/schemas.md) — the exact required structure
  of `architecture.md` and `components/<module>.md`, and which regions sit
  inside generated-block fences.
- [references/module-taxonomy.md](references/module-taxonomy.md) — the canonical
  module set, the evidence that justifies claiming each one exists, the evidence
  that means it is `missing`, and the Scope globs that define ownership.
- [references/context7-policy.md](references/context7-policy.md) — the Context7
  boundary in full: tool names, call budget, caching, and fallback behaviour.
