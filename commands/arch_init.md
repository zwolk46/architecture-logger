---
description: Analyze the repository and bootstrap .architecture/ with architecture.md plus the per-module components/ records.
disable-model-invocation: true
---

Bootstrap the architecture records for the repository you are currently in.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/architecture-records/SKILL.md` and the
   reference files it points to. It governs everything below; where this
   procedure and the skill differ, the skill wins.

2. Discover the repository as the skill's discovery rule requires. Do not assume
   any layout — walk it and record the evidence you find.

3. Detect the stack from `pyproject.toml` and `uv.lock`. Name only frameworks,
   libraries and tools that actually appear in the resolved dependency set.

4. Classify the modules using `references/module-taxonomy.md`: decide which ones
   this repository genuinely has and which are `missing`. Fabricating a module
   to fill a slot is a failure; so is silently dropping one the taxonomy covers.

5. Read the real source of every present module before writing about it. Consult
   Context7 within the boundary the skill sets — no wider.

6. Write `.architecture/architecture.md` and the full `.architecture/components/`
   set to the structures in `references/schemas.md`, applying the skill's fence
   contract (Rule 2) in full — including what it requires when an existing file
   has no fence markers.

7. Create `.architecture/pending.jsonl` as an empty file if it does not already
   exist. Leave an existing queue alone — draining it is `/arch_check`'s job.

8. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_traceability.py` from the
   repository root. Fix every finding and re-run until it exits zero. Do not
   report success while it is still failing.

9. Only then report, in three parts:
   - files **created**,
   - files **updated in place**,
   - the count of human-authored regions preserved.

   List which modules were marked `missing` and the evidence that decided it.
   Close by suggesting `/arch_summary` to read the result.
