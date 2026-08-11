---
description: Explain the repository in the terminal — purpose, then each module with its description and status — by rendering the architecture records read-only.
disable-model-invocation: true
---

Explain this repository to a new joiner. This command **writes no files** and
edits nothing.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/architecture-records/SKILL.md` and the
   reference files it points to, so you can read the records correctly.

2. Run:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_summary.py
   ```

   from the repository root. The script renders the records; it is the source of
   what you present. Do not re-derive the summary from the code, and do not
   rewrite what the script produced into your own words.

3. Present the output.
   - Short output: present it as one block.
   - Long output: present it section by section — purpose first, then the module
     index, then the per-module sections — pausing between sections rather than
     emitting one wall of text.

4. Mention once, at the end:

   > Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/arch_summary.py --page` in your
   > own terminal for a true `less`-style paged scroll.

   Explain why in a clause: a pager needs a real TTY, which a tool call does not
   have, so paging belongs to the user's terminal, not to this command.

5. If the script reports that `.architecture/` is missing, say the repository has
   no records yet and point at `/arch_init`. If it reports modules in `drift`,
   note that their descriptions are unverified and point at `/arch_check`.
