---
description: Generate reader-facing docs from .architecture/components/ — root and per-folder README.md files plus a repository documentation.md.
disable-model-invocation: true
---

Publish reader-facing documentation from the architecture records.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/architecture-records/SKILL.md` and the
   reference files it points to. It governs everything below.

2. Read `.architecture/architecture.md` and every `.architecture/components/*.md`
   file. **These are the source of truth.** Do not re-analyse the code — this is
   a rendering pass over the records, not a second pass over the repository. If a
   record is thin, the documentation is thin; say so rather than inventing.

   If `.architecture/` is missing, stop and point at `/arch_init`. If any module
   is in `drift`, warn that you are publishing unverified records and offer
   `/arch_check` first.

3. Write these, applying the skill's fence contract (Rule 2):

   - **`README.md`** at the repository root — what the project is, how to install
     it with `uv sync`, and how to run it. Take the run command from the records'
     entry points, not from memory.
   - **`tests/README.md`** — how to run the suite, from the tests module record.
   - **A `README.md` in each other folder the records warrant** — a folder earns
     one when a component record owns it and has something a reader needs at that
     location. Do not blanket every directory.
   - **`documentation.md`** at the repository root — for a developer who must run
     and extend the project: setup, a walkthrough of each module, and how the
     parts fit together. Link out to the per-folder READMEs rather than repeating
     them.

4. Before writing over any existing file that contains **no** ARCH-LOGGER fence
   marker: treat it as hand-written. Say so explicitly, name the file, back it up
   as the skill requires, and **ask the user before writing**. Do not proceed on
   that file without an answer; carry on with the others meanwhile.

5. Report which files were created, which were updated in place, how many
   human-authored regions were preserved, and any file you left alone pending
   the user's answer.
