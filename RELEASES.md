# Releases

## 2.0.0 (2026-07-18)

The replication-grade rewrite. The Graey full-repo run (1.2.4) proved the
scanner could walk 7,666 files and name real evidence — but its bundle still
shipped scan JSON, not the source files that evidence cited, because nothing
in the pipeline distinguished a glob candidate from a validated finding, or
planned what evidence a bundle actually needed before copying started. This
release is that missing layer, built as five new/changed pieces working
together rather than one big patch:

- **`scripts/structural_validators.py`** (new). One real check per concern
  that a candidate has to survive to become `structural` (parses against the
  concern's actual shape) or `behavioral` (demonstrates a real operation) —
  frontmatter + tool grant for agent, name+description+real body for skill,
  `meta.phases` + `phase()`/`pipeline()` calls or GH Actions `on:`+`jobs:`
  for workflow, a real client-call pattern (PyGithub/Slack SDK/jira-python/
  mcp tool call, not a bare word) for integrations, a manifest filename or
  install invocation for required-tools-repos, invocation+assertion for
  exemplars, a real failure marker (not just TODO) for issues, a real
  reachable channel URL for shareability, a path-reference proxy for
  memories. `code-scripts` gets a real fix, not a heuristic: Python imports
  are read via `ast.parse`, so a docstring line that merely *starts with*
  "from the..." can never become a bogus import the way the old regex read
  it — proven with the exact fixture this epic's acceptance test describes
  (a "derived from the original design" docstring; the old regex extracts
  `'the'` as an import, `ast.parse` correctly extracts none). JS/TS gets a
  tightened, comment-stripped, module-shape-anchored regex (no JS parser in
  stdlib) that rejects the same class of comment-borne false hit while still
  accepting a legitimate one-letter destructured import.
- **`scripts/lineage.py`** (new). Hashes every candidate file's raw bytes,
  groups exact byte-identical copies, nominates one canonical member per
  group (shortest path, then lexicographic), and classifies every
  candidate's `source_class` (source / configuration / generated / copy /
  archive / snapshot / cache / vendor / transcript / runtime-state /
  unknown) from path and content shape.
- **`cartographer_scan.py`**: wired additively. Every regex-graph concern's
  `scan_one` now also runs its structural validator and (for code-scripts)
  the import classifier, emitting a typed `findings[]` per concern
  (concern/file/evidence_stage/signal/locator, plus import_target/class for
  code). `evidenced_concern_coverage` is **redefined** — a file counts only
  on a real edge or a structural+ finding, never merely because a
  node-evidence concern's glob matched (the exact bug the epic opens with).
  Cross-cutting couplings are filtered the same way: a bare candidate shared
  across two concerns' globs is no longer a "coupling". Boundary-pointer
  grouping now keys on the canonicalized resolved target, not the literal
  reference string, so differently-cased/spelled references to the same
  real file land in one group (`reference_variants`), not several —
  verified live: the skill's own self-scan went from 5 boundary-pointer
  groups to 3 once two case-variant spellings of the same path folded
  together. `--follow-boundaries` now accepts `--boundary-dispositions` and
  never sub-scans a pointer already disposed excluded/deferred.
  `schema_version` bumped to 1.1 (additive: `findings`, `lineage`, node
  `source_class`/`canonical_rel`); `VALIDATORS_VERSION` folds into the cache
  signature so an old cache can't hide a validator change.
- **`scripts/build_export_manifest.py`** (new). Turns real findings into an
  `export-plan.json` — only structural+ findings ever earn a plan entry,
  copies are folded into their canonical source (stored once, referenced by
  every concern it supports), and the scan's own process trace
  (scan.json/patterns.json/lineage.json/environment.json) is always planned
  under a `process` slot, separate from evidence. `--profile handoff` caps
  per-concern, ranked by finding strength; `--profile replication` plans
  every evidenced source. Included boundary dispositions add their own
  entries.
- **`export_bundle.py`**: hardened. Accepts `--plan` (preferred) alongside
  the legacy `--manifest`. Hashes raw bytes, not decoded-with-errors-ignore
  text. Binary files (by extension or failed UTF-8 decode) are copied
  byte-for-byte, never secret-scanned. A collision on the export name gets a
  numbered suffix instead of a silent overwrite; a name attempting to escape
  the bundle (`../`, an absolute path) is refused per-entry with a reason,
  never written. Identical content across entries is written once and
  referenced by hash. Every write is re-hashed against what's actually on
  disk — and a real bug lived here: opening the destination in Windows
  text-mode without `newline=""` silently turns `\n` into `\r\n`, so every
  single text export failed its own post-write verification on this host,
  100% false-positive, until fixed. Caught by the verification feature
  itself, on its first real run.
- **`state.py`**: new hard gates, not just presence checks.
  `exported` now requires a profile-carrying manifest, an export-plan.json
  in the bundle, re-hashed export integrity, and no shipped
  `scan-cache.json`. `shared` (existing boundary-disposition gate kept)
  gains: an `included` boundary disposition must link to real exported or
  followed evidence, not just the label; and every secret warning needs a
  `secret-disposition` (new subcommand: resolved/accepted/non-secret).
  `carded` (new gate) requires the export plan and a `justify` record (new
  subcommand) for every planned source whose `source_class` needs one.
  `delivered` (new gate) re-verifies export integrity and requires `--note`
  naming a real destination. **A second real bug, more serious, found
  proving these**: `cmd_advance`'s existing skip-ahead mechanism (jump
  straight from `exported` to `carded`) silently bypassed every check
  `shared` would have enforced, because the new gates were keyed to the
  literal `target` argument, not to states skipped over on the way there —
  the same class of hole `elicited`'s existing skip-guard was built to
  close, just not yet extended to the newer gates. Fixed: every named gate
  now fires if its state is skipped over OR is the literal target.
  Reproduced the exact bypass (advance straight to `carded` with zero
  dispositions recorded) before the fix — it succeeded silently; after the
  fix, the same call correctly refuses on `shared`'s unresolved secrets.
- **`bundle_synopsis.py`**: rewritten to report candidate vs. structural vs.
  behavioral vs. observed vs. confirmed counts, never the unqualified
  "with evidence" for a bare glob match, plus lineage/dedup savings and a
  headline number: how many exported files are real source/configuration
  content (not scan output, not a copy) backing how many real findings —
  the actual answer to "how much of this bundle can a receiving team inspect
  without the original repo." New **`report.html`**: a single
  self-contained static dashboard (inline CSS, no external assets, no
  network calls) generated alongside README.md/handoff.json — bar charts for
  evidence-stage breakdown, per-concern coverage, and exported bytes by
  source class, a boundary-pointer table, and the secret-warning list with
  resolved ones struck through. It travels inside the bundle and opens
  directly in a browser on a machine with no path back to this one.

Verified live end to end, self-scan target (this skill's own ~49-file repo,
run three times over the course of building this — numbers below are the
final clean run): `state.py init` → `negotiated` → `elicited` (skipped,
documented, no builder present) → `cartographer_scan.py` (49 files, 47
candidates, **18 structurally-or-better evidenced**, 78 findings — 77
structural + 1 behavioral, 0 rejected, 0 duplicate groups on this target) →
`build_export_manifest.py --profile replication` (12 real sources planned,
plus the process-trace entries) → `export_bundle.py --plan` (12/12 exported,
0 failed post-write verification after the CRLF fix, real source `.py`/`.md`
files landing in `exports/`, not scan output) → `advance exported` (passed:
plan present, integrity verified, no cache shipped) → refused `advance
shared` twice for real reasons (missing README/handoff, then 50 undisposed
secret warnings — the process-trace files' own hashes trip the intentionally
noisy long-string tripwire) → all secret + the 3 boundary-pointer
dispositions recorded for real reasons → `advance shared` succeeded →
`advance carded` → `advance delivered` with a real destination note. Also
verified live: the two regressions above, reproduced broken before their
fix and correct after, on this same pipeline.

Not done in this pass, named rather than implied: the full 7,666-file/467MB
Graey-repo fitness run this epic's acceptance section asks for was not
re-run — this release is proven on a real but much smaller target, not yet
re-proven at that scale. Several of the epic's sixteen acceptance tests
(directory-move portability, deleted-original-repo validation, an `included`
boundary with no evidence blocking `shared` specifically) have the
mechanism built and gate-checked in code but no dedicated fixture run
against them yet. Both are the natural next dogfooding step, in the same
spirit every prior release here was earned by actually running the tool,
not by reading the code.

Major bump: `evidenced_concern_coverage`'s meaning changed (stricter, by
design), boundary-pointer `id`s changed (canonical-key grouping, not
literal-string grouping — an in-flight bundle's `boundary-dispositions.json`
from before this release won't match), and `state.py` now hard-refuses
transitions earlier releases allowed silently. `cartographer_run.py`'s
`export-source-evidence` task command updated to the plan-based two-step
flow.

## 1.3.0 (2026-07-18)

New `scripts/cartographer_run.py` — a first-touch run ledger, so an agent has a visible
work contract before the first environment probe instead of reconstructing the workflow
from this file's prose. `init` creates `<run>/work.json` (typed tasks: phase, owner,
`blocked_by`, a `completion_evidence` artifact + condition) and regenerates `TODO.md`
from it after every mutation — never hand-edited, the way any generated file isn't. The
seed task graph mirrors this skill's own phase list (negotiate → elicit → scan →
reconcile → cycle → assemble → share); every seed task's completion evidence points at
an artifact a different script in this skill already produces (`environment.json`,
`scan/scan.json`, `manifest.json`, `README.md`), so the ledger wraps existing mechanism
rather than inventing a parallel one. Two gates are real, not descriptive: `start`
refuses a task whose `blocked_by` isn't satisfied, and `complete` refuses to close a
task whose artifact doesn't exist — an agent's say-so is not evidence. A task marked
`skippable` (elicit, informed-rescan) can close via `--skip <reason>` instead, matching
the precedent 1.2.4 itself set (elicit explicitly skipped, no builder present). Discovered
work lands with `add-task --discovered-by <what surfaced it>` instead of being buried in
`patterns.json`.

Verified live end to end against this skill's own repo as target (`init` only stats the
target directory — no content read): status blocked `scan-target` on the real message
"blocked by unfinished task(s): elicit-blind-beliefs" before elicitation closed; `complete
confirm-roots` refused with "required artifact missing — environment.json" before the
probe had actually run, then succeeded once it had; skipping `elicit-blind-beliefs`
correctly unblocked `scan-target`, which then ran the real scanner and closed on its real
`scan/scan.json`; an `add-task --discovered-by boundary-pointer` landed mid-run and
appeared `ready` the moment its one blocker was already done; the regenerated `TODO.md`
correctly reported "Current phase:: Reconcile" with four tasks in `## Done` (one shown
skipped, with its reason) after that sequence. `state.py`'s own save-state ladder is
untouched by this addition — `init` calls its existing `cmd_init` once and nothing more;
the two ladders (fine-grained tasks, coarse save-states) stay independent, and finishing
a phase's tasks is the cue to call `state.py advance`, not a trigger that does it for you.
Minor bump: additive only, no existing script's contract changed.

## 1.2.4 (2026-07-18)

Full-scale run: a subagent actually played the System Cartographer role (Negotiate →
Scan → Join → Assemble → Share, per `SKILL.md`'s own phases, Elicit explicitly skipped
with a documented reason — no builder present for a real commissioning) against the
whole graey repo — 7666 files, not the 24-file `.claude/` slice 1.2.3 was proven on.
Reached `shared` for real, including one genuine reopen-and-refix cycle mid-run. Four
more bugs, all found by actually running the tool at this scale and all proven with a
live before/after re-run:

- **`DEFAULT_EXCLUDES` only matched at the scan root**, never nested — `"node_modules/**"`
  needs a target's *own* node_modules directly under the declared root; a repo this
  size has `workspace/viewport-ext/node_modules`, 168 stray `__pycache__` dirs, and a
  synthetic PC-crawl tree of fake vendor dirs several levels down, all silently walked
  anyway. Prefixed every default with `**/`. Edges dropped 17380 → 7683, and
  `hotspot_files` went from 100% vendored noise to real graey files.
- **The boundary scanner only recognized forward-slash paths** — every Windows
  absolute path (`C:\Users\...`) was invisible to it, including one this repo's own
  `domains/Qualia/engine/MISSION-PROMPT.md` explicitly names as load-bearing ("the
  mother lode"). Added a `win_abs_path` pattern to `boundary.scan.json`; pointers went
  0 → 589 real on a repo where they should obviously have been nonzero.
- **That fix exposed a case-sensitivity bug in `classify_relation`**: a lowercase-drive
  path (`c:\Users\...`, written that way in one real `.workflow.js` file) compared
  unequal to the uppercase-drive scan root, misclassifying an internal file as an
  external "cousin". Fixed with `os.path.normcase`; count dropped 589 → 572, exactly
  the false positives, verified by pointer id.
- **`bundle_synopsis.py` read the wrong JSON shape for git history.** The scan's own
  `session-quality` concern nests commit data under `["analysis"]`; the synopsis script
  only ever checked `["git_analysis"]` (the shape `session_telemetry.py` produces
  separately) — so a bundle built from the scan's own evidence *always* reported "no
  git history found," even with 200 real commits sitting right there. Added a
  shape-normalizing helper; the README now correctly reads "200 commit(s) spanning
  2026-07-13–2026-07-17."

Read the resulting bundle's `README.md` critically, the way a human recipient would:
"Points beyond this map" correctly identifies `C:\Users\bdf19\.claude` as a genuine
load-bearing dependency (the global Claude Code home this very tool runs from) and
correctly bulk-excludes PC-wide filesystem-inventory noise (vendored HuggingFace/Ollama
model blobs, `pagefile.sys`) with specific, defensible reasoning per class, rather than
either drowning in it or silently dropping it. Of 572 real pointers, 10 got individual
reasoning after reading their actual source files, 544 were bulk-dispositioned across
two genuinely coherent classes (a PC-wide crawl domain, a local-projects discovery
audit) with the methodology stated plainly, and 18 stayed honestly `deferred` rather
than guessed — the replication test this tool holds everything else to, applied to its
own output.

## 1.2.3 (2026-07-17)

Premise check: does the tool actually map a real agentic system, not just run without
crashing? Pointed it at `graey/.claude/` — 15 real Claude Code subagent definitions, a
`settings.json` with real hooks, real commands — the exact evidence set
`host-environments.md`'s own Claude Code row names. First result: **zero edges across
all eleven concerns.** Two compounding bugs, both load-bearing:

- **`agent`'s `tool_grant` pattern never matched real Claude Code frontmatter.** It
  required bracket syntax (`tools: [Read, Write]`); every real subagent file in this
  repo (and, per `host-environments.md`, this tool's own native host) writes a bare
  comma list (`tools: Read, Write, Edit, Bash, Grep, Glob`) instead. The concern found
  all 15 files as candidates and extracted zero tool grants from any of them — "Agent",
  one of the three first-class object types `SKILL.md` opens with, silently couldn't
  do its one job against the most common real-world case. Regex now accepts both forms
  (`\[?([^\]\n]+)\]?`), verified to still handle the bracketed form unchanged.
- **`workflow` and `memories` found zero candidate files at all**, because their
  configs anchor on `**/.claude/...` — written assuming `.claude/` is a *nested*
  ancestor of the scan root (a repo-root scan). Point `--target` at `.claude/` itself
  — a natural, common choice, the row directly above in the same doc — and the anchor
  segment is consumed by being the root, so it can never appear in a relative path
  again. `workflow` gained root-relative fallbacks (`commands/*`, `settings.json`)
  alongside the nested forms; `memories` gained a scoped, justified addition
  (`settings.local.json`, matching its own interrogation question — session-local
  config, different authority than the shared file) rather than a blanket `**`, which
  would fix this one target shape by breaking every other target's specificity.
  `host-environments.md` now names the remaining gap honestly instead of implying it's
  fully solved.

Verified live, against ground truth already visible earlier in this exact session: the
scan's extracted tool grants for `agents/analytical-admin.md`
(`Read, Bash, Grep, Glob, Agent`) match the real agent roster shown at session start,
and the extracted hook names (`SessionStart, UserPromptSubmit, PreToolUse,
PostToolUse`) match hooks that actually fired earlier in this conversation. Built the
full bundle end to end: `agent`/`workflow`/`memories` went from 0/0/0 to 15/8/1
evidenced files and 0 to 18 real edges; `cross-cutting` now correctly flags
`settings.json` as coupling three concerns at once; the README's "Points beyond this
map" section correctly surfaces that the 15 agent-role prompts all point outward to the
real enforcement machinery in `tools/session/`, `tools/sign/`, and
`workspace/descent/` — which is the actual premise this tool exists for.

## 1.2.2 (2026-07-17)

Cut the boundary-pointer false-positive noise two ways — a small regex improvement,
then the actual fix underneath it.

The real fix: `cartographer_scan.py` was emitting every regex candidate into
`patterns.json["boundary_pointers"]`, including ones that never resolved to anything on
disk — the tool already computes ground truth (`resolve_boundary_target` checks the real
filesystem) but wasn't using it to decide what to report, only what to gate on. It now
does: unresolved candidates (prose false positives — never real paths, never load-
bearing, never gated on) are dropped from the emitted list by default, with the dropped
count reported plainly (`summary.boundary_pointers_unresolved_dropped`) rather than
hidden — nothing silently vanishes, it's just no longer mixed in with actual findings.
`--include-unresolved-boundary-pointers` opts back into the full noisy list, for anyone
tuning `--boundary-config` who needs to see what the patterns are over/under-matching.
Verified live on `workspace/reception`: default output went from 84 boundary pointers
(38 real + 46 noise) to exactly 38 — 100% signal — with the flag reproducing the
original 84. The 38 real, gate-relevant pointers are byte-for-byte unchanged; every
downstream consumer (`state.py`'s `shared` gate, `bundle_synopsis.py`'s README) already
filtered on resolution status internally, so nothing downstream had to change.

Smaller, first-pass improvement, kept because it still helps the (now opt-in) full
list: tightened `path_dir_token` in `references/boundary.scan.json`, the noisiest of
the three detection patterns, which previously matched any `word/word` shape regardless
of case or context. Every segment must now start lowercase (real directory names in
this ecosystem are lowercase; kills Title-Case/ALL-CAPS prose lists like
`Agents/Skills/Workflows` or `TODO/FIXME` outright), and a match immediately followed by
a copula (`mode/value/status **are** filled by...`) is rejected. What's left
(`blocker/fork`, `claim/file` — lowercase English word-pairs used as shorthand for "or")
is genuinely undecidable from a real path by regex alone, since real kebab-case
directory names have the identical shape — `boundary-protocol.md` says so explicitly
now instead of citing a since-fixed example. This mattered more before the real fix
above (it shrank the noise that used to ship by default); now it just shrinks what
`--include-unresolved-boundary-pointers` shows.

No contract change to the `shared` gate either way: unresolved pointers never blocked
it before this release and still don't.

## 1.2.1 (2026-07-17)

Release-readiness pass — no behavior contract changes, patch bump. Found by driving the
whole phase lifecycle for real (self-scan plus a second live run against
`workspace/reception` in the graey repo, through probe, scan, telemetry, every state
transition, disposition, `--follow-boundaries`, and the registry validate/propose
commands) rather than reading the code. Five fixes, all bugs the dogfooding actually
hit, none design changes:

- **Bundle paths were not portable.** `export_bundle.py` wrote `manifest.json`'s
  `export` field with `os.path.join`, which emits backslashes on Windows — baked
  straight into `README.md` and `handoff.json` too. A bundle whose entire purpose is
  "content that travels" (`SKILL.md`) shipped Windows-only relative paths by default.
  Now always forward-slash, OS-independent.
- **The skill's own quickstart crashed on first use.** `environment_probe.py --out
  <run>/environment.json` — the literal first command in `SKILL.md` — raised a raw
  `FileNotFoundError` traceback whenever `<run>` hadn't been created yet, instead of
  creating it like `cartographer_scan.py`'s writer already does. `session_telemetry.py
  --out` had the same gap. Both now create the parent directory first.
- **Inconsistent text encoding.** `state.py`, `session_telemetry.py`,
  `bundle_synopsis.py`, and `export_bundle.py` had file reads/writes with no explicit
  `encoding="utf-8"`, unlike the rest of the codebase. Latent: this host's Python
  defaults to UTF-8 mode so it didn't reproduce here, but the generated docs contain
  non-ASCII punctuation (em dashes, arrows) and the tool's whole premise is running
  across arbitrary hosts — a legacy-codepage Windows box would mojibake or crash on
  its own README. Normalized to the `encoding="utf-8"` convention already used
  elsewhere.
- **`state.py disposition <id>` didn't strip its argument.** A trailing CR/whitespace
  on the id (easy to pick up from Windows text tooling) silently recorded the
  disposition under the wrong key, so `advance shared` kept reporting the pointer as
  undispositioned with no clue why the disposition that was just recorded didn't
  count. Now stripped before use.

Verified live: fresh runs of the full pipeline (uncreated run dir → probe → scan →
telemetry → init → negotiate → elicit(skip) → export → synopsis → exported →
`shared` blocked on 38 real undispositioned pointers → disposition each → `shared`
succeeds → synopsis regenerated with dispositions shown) against two targets, plus
`--follow-boundaries` (capped hop confirmed, file-type pointers correctly left
unexpanded) and `concern_registry.py validate`/`propose`. Confirmed as design, not
touched: the noisy `path_dir_token` boundary-pointer false-positive rate on prose
(`boundary-protocol.md` already documents and contains it — never blocks the gate,
never shown in `README.md`) and the "scan's own launch directory" resolution base
(works exactly as documented when the scan is launched from the target's repo root,
reproduced both the miss and the hit).

## 1.2.0 (2026-07-17)

Boundary pointers. A live run against `workspace/reception` in the graey repo (a real
QA-agent commissioning) surfaced a structural gap by luck: the target's own docs named
the code that actually implements it (`tools/session/{claim,route}.py` and the
SessionStart hook chain), but that code lives outside the declared root and the scan
never said so — a card built from that run would have silently omitted what its target
depends on, failing the replication test it's supposed to pass. `cartographer_scan.py`
now detects this by default, every run, at no extra walk: every file already read for
any concern is also checked against `references/boundary.scan.json`'s path-reference
patterns, each match resolved and classified relative to the target root (ancestor /
sibling / cousin / unresolved), deduplicated, and given a cheap automatic peek —
emitted as `patterns.json["boundary_pointers"]`. Naming is unconditional; actually
scanning what a pointer names is a separate, explicit opt-in (`--follow-boundaries`,
capped by `--max-boundary-follow`, exactly one hop, no crawl) — this is the resolution
of the tension between "the map must say what it doesn't cover" and "never read outside
the declared root by surprise" (`environment-protocol.md`'s authority boundary).
`state.py` gained a `disposition` subcommand and now refuses to advance a bundle to
`shared` while any resolved boundary pointer carries none (included / excluded /
deferred, with a reason) — the same enforcement shape it already used for
README.md/handoff.json and secret warnings, not a new mechanism. `bundle_synopsis.py`
surfaces the same list as a "Points beyond this map" section and a hard-gated
`handoff.json` action. New: `references/boundary-protocol.md`. Minor bump: additive
fields only (`boundary_pointers` in patterns.json, new CLI flags default to current
behavior when omitted except the new hard gate at `shared`, which only fires when a
bundle actually carries boundary evidence) — no existing fills or concern contracts
invalidated.

## 1.1.0 (2026-07-17)

Bundle review surfaces. New `scripts/bundle_synopsis.py` generates `README.md` (human
synopsis: state history, findings at a glance, review items, next actions) and
`handoff.json` (agent surface: typed actions with owner human|agent and commands where
mechanical, pending states, unresolved secret warnings, artifact index) from the
bundle's own contents. `state.py` now refuses to advance a bundle to `shared` unless
both surfaces exist. Minor bump: no existing fills or contracts invalidated.

## 1.0.0 — "First Light" (2026-07-17)

First versioned release, cut after the inaugural commissioning run (the cartographer
pointed at its own tree — first light verifies the optics on a known object; it is not
a survey). Lineage: v0.x iterations in-conversation (Cowork/Claude), architectural fork
(registry-driven concerns, environment negotiation, single-pass scanner), then this
polish: session-quality instrument restored (`scripts/session_telemetry.py`),
`produced_by` stamping on every emitted artifact, versioning semantics written down,
founding concern statuses made honest (provisional until evidenced by a real run, per
the registry's own promotion rule).

## Versioning semantics

- **Skill version** lives in `VERSION` (semver). Every artifact the skill emits — scan
  results, telemetry, bundle manifests, state transitions — carries a `produced_by`
  block with the skill version (and, where computed, the registry signature). A
  resuming or receiving agent compares those stamps against its own copies before
  trusting fills; a mismatch is drift to reconcile, not to ignore.
- **Concern versions** (X.Y in the registry): bump **minor** for changes that do not
  invalidate existing fills (glob/config widening, prose clarification, added edge
  patterns). Bump **major** (X) when the interrogation question's meaning, the type, or
  cares_about changes — existing fills recorded under the old version become
  `discovered`-at-best and must be re-elicited. Per-fill provenance records
  `concern@version` so this is checkable mechanically.
- **Status ladder** (`provisional` → `stable`): a concern is promoted only after it has
  survived a real run — produced evidence, or a defensible structured absence, against
  a real target. The founding twelve entered 1.0.0 as provisional; those evidenced by
  the First Light commissioning run were promoted in this release, the rest remain
  provisional until the first field run (the QA-agent cartography) exercises them.
- **Registry schema_version** changes only with breaking contract changes and requires
  a migration note here.
