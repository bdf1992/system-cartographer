# Releases

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
