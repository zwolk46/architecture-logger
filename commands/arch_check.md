---
description: Reconcile the .architecture/ records against the current code, update the ones that disagree, and notify the user of what changed.
disable-model-invocation: true
---

Drain the drift queue and reconcile the records with the code.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/architecture-records/SKILL.md` and the
   reference files it points to. It governs everything below.

2. **Before changing anything at all**, read `.architecture/pending.jsonl` and
   report what drifted and why: which modules, which commits, which files, when.
   Group by module. Write nothing during this step — not a file, not a status
   cell, not the queue. The user sees the situation before you act on it.

   If `.architecture/` does not exist, say so and point at `/arch_init`. If the
   queue is absent or empty, say nothing is queued, confirm the module index
   shows no `drift`, and stop — do not launch a full re-analysis.

3. Re-analyse **only the modules named in the queue**. Read the changed files
   and the current state of the code they belong to. Leave every other module
   untouched.

4. Update those records wherever they disagree with the code — symbols, line
   citations, interfaces, dependencies, the module's Idea if the design moved.
   Follow `references/schemas.md` and the skill's fence contract (Rule 2),
   exactly as `/arch_init` does.

5. Flip the Status cell of each reconciled module back to `current` in
   `.architecture/architecture.md`, and refresh the synced timestamp and commit
   SHA. Modules you did not reconcile keep the status they had.

6. Empty `.architecture/pending.jsonl` — truncate it, do not delete it — and
   clear the fenced drift-log block in each reconciled component file, leaving
   the fence itself in place for the hook to write into again.

7. Re-run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_traceability.py` from
   the repository root and fix every finding before reporting.

8. Finish with a short changelog of how the **records** changed, one line per
   change, in prose a reader can skim:

   > Backend: `create_task()` now validates list capacity; row updated.
   > Database: no change — the commit touched comments only.

   Never dump a diff, and never paste file contents. If a module needed no
   change, say so in one line and move on.
