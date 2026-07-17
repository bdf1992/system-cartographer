# Orchestration: negotiate → elicit → scan → reconcile → cycle

## Contents

1. Invariants
2. Phase 0 — negotiate the environment
3. Phase 1 — elicit blind belief
4. Phases 2–3 — scan and join once
5. Phases 4–5 — reconcile and cycle
6. Phases 6–7 — assemble and deliver

## 1. Invariants

- Keep environment facts separate from target-system facts.
- Capture the builder's belief before exposing target evidence.
- Scan deterministically before asking a model to synthesize findings.
- Treat unknown capability as a question, not as absence.
- Use one filesystem walk for all registered regex concerns.
- Preserve the observation config, bounds, environment descriptor, and timing with the
  results. A pattern is partly a property of its instrument.
- Do not require parallel agents. If the user explicitly asks for delegated analysis,
  divide interpretation after the common scan; never duplicate the filesystem walk.

## 2. Phase 0 — negotiate the environment

Run only against an explicit root:

```bash
RUN=cartography-run
mkdir -p "$RUN"
python scripts/environment_probe.py \
  --root /path/to/target \
  --host <optional-host-id> \
  --provider <optional-provider> \
  --model <optional-model> \
  --out "$RUN/environment.json"
```

Read the emitted questions. Ask only those whose answers affect the run. Add declared
answers through repeated `--capability ID=STATUS` arguments and rerun the probe so the
contract, not chat memory, carries them.

This phase may detect the presence of runtime markers and executable names. It must not
read target contents, test network access, enumerate a home directory, or open session
stores. It therefore does not contaminate blind elicitation.

If an observation has no owner in the concern registry, record it as an environmental
signal. Do not register it yet; follow `references/environment-protocol.md`.

## 3. Phase 1 — elicit blind belief

Walk the active concerns from `references/concerns.registry.json` plus any chosen
overlay. Ask the registry question, then use the concern card only where the answer has
signal. Capture each answer as `described`, with `source: elicit-blind`, round number,
and whether the user skipped it.

Do not force equal airtime. A skipped, rushed, or over-explained concern is a process
observation. Do not show scan output because none should exist yet.

## 4. Phases 2–3 — scan and join once

Run the registry-driven scanner:

```bash
python scripts/cartographer_scan.py \
  --target /path/to/target \
  --target-name "human-readable name" \
  --environment "$RUN/environment.json" \
  --out-dir "$RUN/scan" \
  --cache "$RUN/scan-cache.json" \
  --max-files 50000 \
  --max-file-bytes 2097152 \
  --compact
```

For a project overlay, provide the maintained registry first and the overlay second:

```bash
python scripts/cartographer_scan.py \
  --target /path/to/target \
  --registry references/concerns.registry.json \
  --registry /path/to/project.concerns.json \
  --environment "$RUN/environment.json" \
  --out-dir "$RUN/scan" \
  --cache "$RUN/scan-cache.json"
```

The scanner writes:

- one evidence graph per active concern;
- `cross-cutting.json` from the common graph join;
- `patterns.json` with concern coverage, co-occurrence pairs, hotspot files, repeated
  edge targets, extensions, unclassified files, environment gaps, and
  **`boundary_pointers`** — every path-shaped reference the scan noticed pointing
  outside the declared root, named, classified (ancestor/sibling/cousin/unresolved),
  and given a cheap automatic peek. This runs by default, every scan; see
  `references/boundary-protocol.md` for the detection rules, the opt-in
  `--follow-boundaries` single-hop propagation, and the export-time disposition gate.
  Do not treat an empty root as fully self-contained without checking this field —
  it usually means the target genuinely has no outside dependents, but confirm rather
  than assume;
- `scan.json` containing the complete portable result;
- an optional cache keyed by file stat plus registry/config signature.

Read `patterns.json` as a question generator. High co-occurrence can mean healthy shared
substrate or accidental coupling. Hotspots deserve interrogation, not condemnation.
Unclassified files indicate instrument blind spots, not irrelevance. `boundary_pointers`
deserve interrogation too, but never silence — an export cannot advance to `shared`
while a resolved boundary pointer carries no disposition (`boundary-protocol.md`).

Interpret only supported evidence as `defined` or `discovered`. List unresolved items
as questions. The deterministic scan may run on GPT-, Grok-, Claude-, Ollama-, or
custom-model hosts because no model SDK participates in this phase.

## 5. Phases 4–5 — reconcile and cycle

Put the blind card and observed card side by side. Classify each delta as confirmed,
drift, undocumented, unevidenced, or aspiration. Spend conversation on the deltas and
environment gaps; confirmations get a nod.

Reconciliation may reveal:

- a legitimate evidence root that was out of scope — check `patterns.json`'s
  `boundary_pointers` first; the candidate roots are usually already named, classified,
  and peeked at, not something to rediscover by luck in conversation;
- an existing concern whose scan config needs informed vocabulary;
- an environmental signal that deserves a provisional typed concern;
- a capability the host cannot provide.

Every resolved boundary pointer needs a disposition before the bundle can advance to
`shared` (`references/boundary-protocol.md`) — include it (widen the root, or run
`--follow-boundaries` and fold the sub-scan in), exclude it with a reason, or defer it
as a named debt. This is a hard gate in `state.py`, not a suggestion.

For a narrowed cycle, rerun only affected concerns while reusing the shared cache:

```bash
python scripts/cartographer_scan.py \
  --target /path/to/target \
  --environment "$RUN/environment.json" \
  --concerns integrations,workflow,issues \
  --out-dir "$RUN/scan-round-2" \
  --cache "$RUN/scan-cache.json"
```

To propose a concern without hardcoding it into the skill:

```bash
python scripts/concern_registry.py propose \
  --id model-routing \
  --type environment \
  --title "Model routing" \
  --question "What selects a model, and which behavior changes with that selection?" \
  --signal "The host routes requests across local and remote models." \
  --requires filesystem.read \
  --produces evidence.routing \
  --out "$RUN/project.concerns.json"
```

Validate overlays before using them. Keep a proposal provisional until a real run
shows distinct evidence and the operator confirms that its boundary matters.

## 6. Phases 6–7 — assemble and deliver

Apply the replication test in `references/slot-protocol.md` to every fill. Build the
portable bundle with `scripts/export_bundle.py`; include the environment descriptor,
registry plus overlays, scan outputs, elicitation trace, fill provenance, and cycle
count under `exports/process/`. Review every secret warning before sharing.

Choose a destination from the filled Shareability and Integrations concerns. Confirm
external destinations and visibility before any upload or push. A local file handoff
is complete when no authorized remote channel exists.

Advance `scripts/state.py` at stable boundaries. The bundle and `state.json` must let a
different operator or model resume without reconstructing hidden context.
