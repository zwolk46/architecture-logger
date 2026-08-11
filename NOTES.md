# NOTES

Design decisions, trade-offs and limitations, written for a reviewer.

## What works

All four commands are implemented and load: `/arch_init`, `/arch_check`,
`/arch_summary`, `/arch_make_documentation`. `claude plugin validate --strict`
passes, and `claude plugin details` reports five skills (four commands plus the
knowledge skill), one `PostToolUse` hook and one MCP server.

The commit hook fires, distinguishes a real commit from a command that merely
mentions one, maps changed files onto modules, queues them in `pending.jsonl`
and flips their Status to `drift`. `/arch_check` drains that queue, reconciles
only the implicated modules and reports a changelog of the records rather than a
diff.

Traceability is enforced mechanically, not by instruction. `verify_traceability.py`
parses every "Key functions and classes" table, extracts each `path:line`
citation, and checks the symbol is really within five lines of it. Both
`/arch_init` and `/arch_check` gate their own success on it exiting zero.

Context7 is declared, connects, and is consulted only inside the boundary the
skill defines.

Module classification was checked against a negative case as well as a positive
one. Run against a bare `uv init` project, `/arch_init` returns `fe`, `be`, `db`,
`api` and `tests` as `missing`, each stub enumerating the evidence that was
looked for and not found, and creates no `infra` module at all — nothing is
fabricated to fill a slot. Run against the demo application, `/arch_check`
reconciled a real change and surfaced two defects nobody asked it to look for: a
new `EmptyTitleError` that is never re-exported, so the API layer has no `except`
clause for it and a whitespace-only title becomes a 500 where the parallel
`DueDateInPastError` becomes a 422; and a module docstring still describing the
old single-invariant design.

The plugin adds roughly 275 tokens to every session, all of it skill and command
listing text; the hook costs nothing in model context because it runs in the
harness.

## The hook trade-off

Claude Code has no git-commit event, so the hook subscribes to `PostToolUse`
matching the Bash tool and fires after every Bash call in the session. Two
approaches were available.

**Flag and defer** — a `command` hook that records suspicion and stops — is what
I built. It is deterministic, costs no tokens, adds no latency worth measuring,
and can be unit-tested by piping JSON at it, which matters a great deal for
something that runs after every Bash call. Its cost is real: the records are
stale between a commit and the next `/arch_check`.

**Update immediately** — an `agent` or `prompt` hook that rewrites the affected
records on the spot — would keep the documentation perpetually accurate. It pays
for that with tokens and several seconds on every commit, with non-deterministic
output, and with a stream of noisy single-commit rewrites in place of one
coherent changelog when the user is actually ready to read one.

I took flag-and-defer and mitigated its weakness rather than pretending it away:
the staleness is *visible*, because `drift` sits in the Status column of the
module index where any reader sees it, and the hook prints a one-line
`systemMessage` naming the affected modules and telling the user to run
`/arch_check`.

### Why there is no `if` pre-filter

Claude Code offers an `if` field on hook handlers — a declarative pattern such as
`Bash(git commit *)` that stops the hook process from spawning unless the command
matches. I wrote it in, then removed it.

It is an optimisation, not a detection mechanism: the brief requires the script
to inspect the tool input, and mine does. But `if` fails *closed* on invocations
that do not match the literal pattern — `git -C . commit`, a commit behind an
alias — and a hook that silently never fires is indistinguishable from a broken
one. Roughly 40ms of process spawn on unrelated Bash calls is invisible; a
missed commit during a demo is not. Correctness over the microoptimisation.

## Why commands are flat files and knowledge is a skill

The four commands live in `commands/*.md`; the schemas, traceability rule,
module taxonomy and Context7 policy live once in
`skills/architecture-records/`, with detail in `references/`.

Commands are the verbs. They are user-triggered, they have side effects on the
user's files, and every one carries `disable-model-invocation: true` so the
model can never decide on its own to regenerate somebody's README. They belong
in the slash menu with a description.

The skill is the reference manual. All four commands need the same body of
rules, and four copies of a document schema drift apart the moment one is
edited. Each command's first instruction is to read the skill; none of them
restates a schema. The knowledge skill carries `user-invocable: false`, because
loading a reference document is not an action a user takes.

This split is also what makes the records byte-compatible across commands:
`/arch_make_documentation` can treat `components/*.md` as a source of truth
precisely because `/arch_init` and `/arch_check` wrote them to a schema neither
of them owns.

## Idempotency and not destroying human writing

Generated regions are fenced with HTML comments:

```
<!-- ARCH-LOGGER:BEGIN module-index -->
...generated...
<!-- ARCH-LOGGER:END module-index -->
```

Inside a matched fence is machine territory and is replaced wholesale. Outside
any fence is human territory and is copied through byte-for-byte. The comments
are invisible in rendered Markdown, so a reader on GitHub sees nothing unusual.

Three things follow. Running `/arch_init` twice produces no duplicated sections,
because the second run replaces a fence's contents rather than appending below
it. A paragraph a colleague adds outside the fences survives every subsequent
run. And a file that exists with *no* fence markers is treated as entirely
hand-written: the command says so, backs it up, and asks before writing — which
is how `/arch_make_documentation` handles an existing `README.md`.

Every rewrite is preceded by a copy into `.architecture/.backups/<timestamp>/`,
and each command reports how many human-authored regions it preserved, so the
contract is observable rather than merely promised.

### Structurally idempotent, not byte-identical

Running `/arch_init` twice leaves the structure fixed — no duplicated sections,
no lost human prose, the same headings and tables in the same order — but the
generated prose inside a fence is regenerated and will differ between runs.

This is the intended behaviour rather than a gap. On the second run against the
demo repository, two of the four changed files were corrections: a citation moved
from `docker-compose.yml:14-17` to `:15-17`, and a claim that the ORM and the
migration disagreed about column nullability was retracted once the second pass
established that they agree and the real divergence is in defaults. A record that
refuses to change cannot correct itself. The brief requires that a second run not
duplicate sections and not discard human writing; it does not require byte
equality, and byte equality would cost the ability to improve.

## The `/arch_summary` pager

The brief asks for a `less`-style scroll. Claude Code's Bash tool is
non-interactive and has no controlling terminal, so an interactive pager cannot
be driven from inside a session — there is no keyboard attached to it.

`scripts/arch_summary.py` therefore detects whether stdout is a TTY. Run by a
human, it pipes its rendering through `$PAGER` or `less -R` and you get a real
scroll. Run by Claude Code, it prints the same aligned, colour-coded rendering
directly, and the command presents it section by section rather than as one
block — the "rendering in chunks" the brief permits. The command closes by
telling the user that `--page` from their own terminal gives the true pager.

I would rather name this limitation than paper over it.

## Context7 boundary

Context7 answers one question: what does a third-party package's API actually
do. It is consulted when writing the Dependencies and Interfaces sections of a
component record, and when a repository symbol is a thin wrapper over a library
call whose behaviour the Idea column cannot honestly describe without it.

It is never called for symbols defined inside the repository — those are read,
and Rule 1 requires a `path:line` citation that no external source could supply
— never for the standard library, and never as a general search engine.

The budget is one resolve and one fetch per distinct library per command run.
Resolved library ids are cached by writing them into the record itself, as a
`(context7: /org/project)` suffix in the Dependencies section, so later runs skip
the resolve step. If the server is unreachable, the affected section keeps every
claim that came from reading the repository, drops the ones that needed the docs,
and says so with a timestamp inside the fence.

## Known limitations

The module taxonomy is opinionated: six canonical modules plus three optional
ones. A repository organised along genuinely different lines gets a reasonable
but imperfect fit, and the Scope globs would need hand-editing.

Scope globs must sit on one line, because the hook's parser is single-line. The
taxonomy reference says so explicitly, but it is a sharp edge — globs pushed onto
a second line are silently dropped and those files stop being watched.

Disjointness of Scope globs is the author's responsibility. The hook records
every module whose globs match a changed path, so overlapping scopes double-flag.
The taxonomy gives a tie-break ladder for writing them; nothing enforces it.

The traceability verifier allows a five-line window around a citation, on the
grounds that an edit above a function shifts it before the record is wrong in any
way a reader cares about. That tolerance is a judgement call, and it is printed
in the report header so a failure is interpretable.

The hook only knows a module is *unverified*, never that it is wrong. That is a
deliberate limit of the flag-and-defer design, and it is why `drift` means "not
checked since the code moved" rather than "incorrect".

`/arch_check` reconciles only the modules named in the queue, which is what keeps
it cheap — but repo-level prose in `architecture.md` sits outside every module
and can therefore lag a reconciled record. In the demo run, the Backend record
and its index row both learned about a second invariant while the Purpose
paragraph still said the system had one. `/arch_init` regenerates that paragraph;
`/arch_check` should widen to it when a reconciled module's summary changes, and
does not yet.

Protecting a hand-written file is permanent, and deliberately so. A `README.md`
with no fence markers is treated as entirely human-authored, so declining the
overwrite once means every later run asks again rather than updating it — the
facts in that file become the author's to maintain. The alternative, injecting
fences into somebody's prose so the tool can claim part of it, is worse: it edits
writing the user did not offer up. `documentation.md` stays machine-maintained
and carries the same facts, so nothing is lost except the automation of one file
the user asked to keep.

## With another hour

I would write `pending.jsonl` entries with a per-file rather than per-module
granularity, so `/arch_check` could tell a comment-only change from a signature
change and skip modules that provably did not need reconciling.

I would add a `SessionStart` hook that reports outstanding drift at the top of a
session, so the queue surfaces without the user having to remember to look.

I would teach `verify_traceability.py` to *repair* rather than only report:
finding a symbol at a different line than cited is a fixable condition, and the
script already knows the right answer.

And I would build a small eval — a handful of deliberately awkward repositories,
including one with no frontend and one with no tests, run through `/arch_init`
with assertions on which modules come back `missing` — because "the model
classified this correctly" is a claim that deserves a test rather than a
demonstration.
