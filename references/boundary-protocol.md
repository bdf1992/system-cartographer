# Boundary pointers — what a target's own evidence names outside its root

## Why this exists

The card's replication test (`slot-protocol.md`) asks whether a competent dev team
could rebuild an equivalent capability from the card alone. A target scanned in
isolation can pass every concern and still fail that test, if the code or docs that
actually implement it live outside the declared root and the scan never says so. A
workstation folder full of tickets and role prose, whose real enforcement code sits in
a sibling directory the scan never touched, is the common shape of this failure — and
it is silent by default, because a single-root scan has no way to notice what it didn't
walk. Boundary-pointer detection exists to make that noticing automatic, not something
the operator has to stumble into during reconcile.

## What it does

Every file the scan already reads (for any concern) is also checked against
`references/boundary.scan.json`'s path-shaped-token patterns: bare relative *file*
paths with an extension (`tools/session/route.py`), markdown link targets
(`[x](path/to/y.md)`), and bare relative *directory* paths with no extension
(`workspace/descent`) — the last of these is what lets a directory-shaped mention (a
peer workstation named in prose, not linked) become a followable pointer at all. Each
match is resolved against three candidate bases, in order: the referencing file's own
directory, the target root, and the scan's launch directory. The first that lands on a
real file or directory wins.

The third base matters in practice: most real docs write references relative to the
*repo* root, not the declared scan target (which is often a subdirectory, e.g. one
workstation folder in a larger monorepo). Launch the scan from the target's repo root
(or nearest shared ancestor) so that base actually resolves those — launching from
somewhere else (the skill's own directory, an unrelated cwd) silently drops otherwise-
real pointers into `unresolved` with no error, since `os.getcwd()` is the only source
for that third base. Confirmed live: the same `workspace/reception` scan surfaced 0
resolved pointers launched from elsewhere and 38 launched from the graey repo root.

The directory-token pattern is the noisiest of the three by construction — it has no
extension to anchor on, so ordinary slash-separated prose ("Read/Glob/Grep",
"blocker/fork") matches the same shape a real path does. This is deliberately still
included: false hits resolve to nothing on disk and land in the `unresolved` bucket,
which never blocks the export gate (only pointers that actually resolved to something
real do). Expect `unresolved` to run noisy and treat it as a hint list, not a findings
list — consistent with `slot-protocol.md`'s framing of the shipped configs as naive
first-contact instruments.

Every resolved-outside-root (or unresolved) reference is named in
`patterns.json["boundary_pointers"]`, deduplicated by `(reference, resolved_path)` and
tagged with a stable `id`, every file that named it, a cheap automatic peek (a
directory's immediate entries, or a file's size and first non-blank line — metadata
and one line, never a content dump), and a classification relative to the declared
root:

| relation | meaning |
|---|---|
| `ancestor` | the reference resolves to a directory that *contains* the target root |
| `sibling` | the reference resolves under the same immediate parent as the target root |
| `cousin` | the reference resolves to a real path elsewhere reachable from the scan (most common in a large repo — shares some more distant ancestor) |
| `unresolved` | looks path-shaped, didn't land on anything real from any candidate base — could be a stale/broken pointer, could be a false-positive token; lower confidence, still named |
| (not reported) | `self` / `descendant` — resolves inside the declared root, i.e. not a boundary at all |

This runs by default, every scan, at no extra cost beyond a regex pass over text
already in memory — it is not a second walk. Disable it with `--no-boundary-scan` if a
target is truly self-contained and the noise isn't worth it; override the pattern set
with `--boundary-config <path>` for a host whose reference style the shipped patterns
miss.

## Taking the hop: `--follow-boundaries`

Naming a pointer is cheap and automatic. Actually scanning what it points at is a real
read against something outside the declared root, so it stays opt-in: pass
`--follow-boundaries` (capped by `--max-boundary-follow`, default 8) and every
`ancestor`/`sibling`/`cousin` pointer that resolved to a real **directory** gets exactly
**one** additional real sub-scan — never a crawl. The sub-scan runs with its own
boundary detection (so it still names *its* out-of-root references) but never follows
them itself; hop depth is fixed at one. Results land under
`<out-dir>/boundary/<id>-<slug>/` and a summary is folded back onto the pointer as
`pointer["followed"]`.

Only directory-shaped pointers are eligible — a pointer that resolves to a single
*file* is never expanded to "scan its containing folder." That fallback existed in an
earlier draft and was caught live: a target's own reference to `CLAUDE.md` at a repo
root resolved to that file, the follow step expanded it to the file's directory to
find something scannable, and that directory was the entire 8,300-file repo — a
20-second, fully unbounded scan triggered by the single most common kind of reference
in any project. A file-type pointer is still named, classified, and peeked (one line
of content, not zero); going deeper on it is a deliberate, targeted read — a subagent
told to read that one file, or a manually widened root — never an automatic directory
expansion, because the file's containing directory is not implied by the reference in
any bounded way.

This is the deliberate middle ground between two failure modes: silently ignoring
what's outside the root (fails the replication test) and silently crawling everything
reachable (violates the "run only against an explicit root" authority boundary in
`environment-protocol.md` — the thing that stops a run from wandering into `$HOME` or a
credential store uninvited). Detection is unconditional; following is a bounded,
named, operator-triggered action.

## Disposition — the export-time gate

A named pointer is not the same as a resolved one. Every `ancestor`/`sibling`/`cousin`
pointer that actually resolved to something real needs a **disposition** before a
bundle carrying it can advance to `shared`:

```bash
python scripts/state.py --bundle <bundle> disposition <pointer-id> \
  --status included|excluded|deferred --actor <who> --note "<why>"
```

- **included** — pulled into the card's evidence (via a `--follow-boundaries` sub-scan,
  a widened root on the next cycle, or a manually curated export entry).
- **excluded** — genuinely out of scope for this object, with a stated reason (e.g. a
  reference to a shared floor/constitution doc every object in the repo cites, not
  specific to this one).
- **deferred** — real and relevant, not resolved this cycle; carried forward as a named
  debt, not dropped.

`state.py advance shared` refuses when any resolved, non-unresolved pointer has no
disposition recorded (`boundary-dispositions.json` at the bundle root, or a
`disposition` value already set on the pointer). `bundle_synopsis.py` surfaces the same
list in `README.md`'s "Points beyond this map" section and as an `owner: human` action
in `handoff.json` — this is the same enforcement pattern the bundle already uses for
secret warnings and the README/handoff.json pair, not a new mechanism bolted beside
them.

## How this changes Phase 0 and Phase 4-5

`environment-protocol.md`'s root-negotiation question 2 — "which other roots are
legitimate evidence?" — used to be askable only blind, before any evidence existed, so
the operator had to already know the answer. Boundary pointers make that question
scan-informed: by the time Phase 4-5 reconciles, `patterns.json` already lists the
candidates by name, classification, and a peek at what's there. "A legitimate evidence
root that was out of scope" (a reconciliation outcome `workflow-template.md` already
names) is now something the instrument surfaces, not something discovered by luck in
conversation.
