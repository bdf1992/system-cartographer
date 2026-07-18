---
name: system-cartographer
description: Reverse-engineer and formally describe a tacit Agent, Skill, Workflow, or AI-native system across GPT, Claude, Grok, Ollama, custom harnesses, IDE agents, and repository environments. Negotiate the host's model, runtime, tools, authority, evidence roots, and constraints; elicit the builder's model before scanning; run a bounded registry-driven scan; reconcile belief against evidence; and produce typed cards, a pattern map, deltas, and tending potential. Use for requests to document, formalize, audit, port, hand off, compare, or understand a manually built system, including “capture how this actually works,” “what is my agent doing,” “make this portable across models,” and “help me understand our patterns.”
---

# System Cartographer

Turn a tacit system into a portable description of the object **and the apparatus that
observed it**. Show its builder the gap between the system they think they have and the
one the evidence supports. Discover, ask, and classify. Never build, fix, or fill on
the owner's behalf.

**What done means:** a card a dev team with no priors could rebuild an equivalent
object from — capabilities and requirements (what it affects and effects, what it
needs), not mechanism, not pointers into the source system. Pointers ride along as
`priors` for teams that do have access. The replication test in
`references/slot-protocol.md` is the acceptance criterion for every fill.

## Object and environment model

Three first-class types, used in conjunction, never collapsed:

- **Agent** — acting entity with tool access and scope.
- **Skill** — packaged, invocable instructions; inert until triggered.
- **Workflow** — defined sequence: trigger, steps, branching, exit.

Real systems compose all three. Describe the composition too (`references/cross-cutting/`).

Keep **model**, **host**, **runtime**, **capabilities**, **authority**, and **evidence
roots** separate. A model name is never a sufficient environment description. Read
`references/environment-protocol.md` before running in an unfamiliar host.

Concerns are registered data, not hardcoded branches. The maintained registry is
`references/concerns.registry.json`; its contract is
`references/schemas/concern.schema.json`. A run may add overlay registries. When the
environment reveals something no concern owns, escalate it through signal → question →
provisional concern → registered concern. Do not grow the permanent registry merely
because a host has a novel tool name.

## Slots

Each of the twelve concerns is a typed slot: the skill authors the static half (name,
type, cares_about, interrogation question); the target's builder/agent authors the
dynamic half (mode, value, status). Full fill rules, the five-state status ladder, the
ask-twice protocol, and the delta taxonomy live in `references/slot-protocol.md` — read
it before the first question.

| Concern | Folder | Asking |
|---|---|---|
| Code/Scripts | `code-scripts` | What implements the actual behavior |
| Required Tools & Repos | `required-tools-repos` | What tools/repos/knowledge it needs |
| Agent | `agent` | Is this an actor; what scope |
| Skill | `skill` | Is this invoked; what triggers it |
| Workflow | `workflow` | Trigger, steps, exit |
| Integrations | `integrations` | External systems, read/write |
| Memories | `memories` | Persistent context across runs |
| Cross-cutting | `cross-cutting` | What must hold about neighboring objects |
| Session count/quality | `session-quality` | Usage history as trend, never a headcount |
| Exemplars | `exemplars` | One real run that worked |
| Issues | `issues` | Known breaks; which invariant they violated |
| Shareability | `shareability` | Who else receives this knowledge, through what channel |

Two behave differently: **session-quality** scans stop at structured inputs (commit
buckets, recency, fix/revert ratio) — the trend read is synthesis, done in conversation,
never printed by the script. **cross-cutting** joins the other eleven scans' outputs; it
runs after them, never standalone.

## The two rules that hold everything

**Authority boundary.** Filling the card is the target's job. The skill proposes schema,
runs scans, asks questions, classifies answers. If you catch yourself writing a
plausible value nobody gave you — stop. That is the failure mode this rule exists for.

**Belief before evidence.** The builder's mental model is captured blind, before any
scan output is shown. Show them the scan first and you've contaminated the most
valuable measurement this skill makes: the distance between their model and their
system. The deltas are the product.

## Phases

Full orchestration detail: `references/workflow-template.md`.

0. **Negotiate environment** (read-only, pre-evidence) — probe only the explicit target
   root and declared capabilities. Ask the unresolved environment questions. This
   describes the apparatus and does not inspect target contents.
1. **Elicit** (conversation, blind) — walk the concerns with the user; capture their
   believed card. Light touch: let them talk, follow their energy, note what they skip.
   Depth follows signal — see the pacing rule in slot-protocol.md.
2. **Scan** (deterministic, single pass) — walk the target once, classify files across
   registered concerns, and emit per-concern graphs plus `patterns.json`. Respect
   environment authority and bounds. Interpretation may happen afterward; scanning
   does not require subagents. Every scan also names, classifies, and peeks at any
   path-shaped reference the target's own files point outside the declared root
   (`boundary_pointers`; `references/boundary-protocol.md`) — automatic and unconditional,
   because a card that silently omits what its target depends on fails its own
   replication test. Widening scope to follow one is opt-in (`--follow-boundaries`);
   naming it never is.
3. **Join** — derive cross-cutting couplings and pattern hotspots from the shared scan.
4. **Reconcile** (conversation) — diff believed vs observed per slot; tag each delta
   confirmed / drift / undocumented / unevidenced / aspiration; interrogate the deltas,
   not the confirmations.
5. **Cycle** — answers open new ground (a repo the scan never walked, a covariate that
   now applies). Rescan only affected concerns; repeat until a round adds nothing.
6. **Assemble & hand back** — final card per object, every slot at a terminal status.
   Close with **Tending**: what this system could be if tended to — every
   `needs_lifting` item, every aspiration delta, every drift worth repairing, framed as
   potential rather than defect. Anything unfilled is named and handed to the owner,
   not filled for them.
7. **Share & deliver** — the bundle goes where its audience can reach it, through a
   channel chosen from what the run itself discovered (GitHub access found by the
   Integrations scan → offer a private repo; wiki found by Shareability → offer a
   page). Secret warnings become a hard gate here; destinations are confirmed before
   any push and recorded in the trace. Detail: workflow-template.md, Phase 6.

## Save states & handoff

The phases above checkpoint into named save states — `negotiated → elicited → exported → shared →
reconciled → carded → delivered` — managed by `scripts/state.py` and described in
`references/save-states.md`. The bundle plus `state.json` is a complete handoff: the
run can stop at any boundary and a different person or agent continues from there, on
their own token budget. Canonical split: the builder does elicit + export + share
(cheap, and elicitation only *they* can do — blind belief capture is unrecoverable
once they've seen evidence); a receiving agent does reconcile + card + deliver
(expensive judgment, needs no builder presence except a compact question list sent
back for the deltas only the builder can resolve). Sharing is therefore not only the
final phase — it's a transition available at every state boundary, and sharing raw
evidence early (`shared` after `exported`) is a first-class outcome, not an
incomplete run.

## First touch: the run ledger

Before any environment probe, `scripts/cartographer_run.py init` creates the run directory
and a work ledger — `work.json` (typed tasks: phase, owner, `blocked_by`, a
`completion_evidence` artifact and condition) plus `TODO.md`, a human-readable view
**always regenerated from `work.json`**, never hand-edited. It touches nothing but a
directory-existence stat on the target (no content read) and mirrors this file's own
phase list as a seed task graph, each task's completion evidence pointing at a real
artifact another script in this skill already produces — the ledger wraps existing
mechanism, it does not invent a parallel one. `complete` refuses to close a task whose
artifact doesn't exist yet; `start` refuses a task whose `blocked_by` isn't satisfied
(this is what makes "scan before elicit is terminal" a mechanical refusal, not a prose
warning to remember). Discovered work — a boundary pointer, a secret finding, an
oversized file — lands with `add-task --discovered-by <what surfaced it>` instead of
being buried in `patterns.json`.

```bash
RUN=cartography-run
python scripts/cartographer_run.py init --target /path/to/target --run "$RUN" --actor <you>
python scripts/cartographer_run.py status --run "$RUN"        # what's ready, what's blocked, why
```

A fresh agent resumes by reading `$RUN/TODO.md`, not by reconstructing the workflow from
this file's prose. `work.json` is the source of truth; `sync` recomputes every task's
status from its `blocked_by` graph, so a run directory alone (no chat history) is enough
to reconstruct exactly what's owed. This ledger tracks finer-grained work *between*
`scripts/state.py`'s coarser save-state checkpoints — finishing a phase's tasks is the
cue to call `state.py advance <name>`, not a replacement for it.

## Host environment & the shipped bundle

Start every unfamiliar host with:

```bash
python scripts/environment_probe.py --root <target> --out <run>/environment.json
python scripts/cartographer_scan.py --target <target> --environment <run>/environment.json \
  --out-dir <run>/scan --cache <run>/scan-cache.json --compact
```

Launch these from the target's repo root (or nearest shared ancestor), not from
wherever the skill happens to live — boundary-pointer resolution uses the launch
directory as one of its candidate bases (`references/boundary-protocol.md`), and a
mismatched cwd silently drops real pointers into `unresolved`.

Use `--registry <base> --registry <overlay>` to add project- or host-specific concerns,
`--concerns` for a narrowed cycle, and scan bounds (`--max-files`,
`--max-file-bytes`, `--exclude`) to fit the target. The standard-library scanner works
without vendor SDKs. `references/host-environments.md` maps common hosts without making
their paths universal.

The deliverable is a **bundle**, not a bare card: `scripts/export_bundle.py` copies or
excerpts the actual evidence into `exports/<slot>/` with a manifest, so priors point at
content that travels rather than paths that die off-machine. Every bundle carries two
generated review surfaces — `README.md` for the human (synopsis, findings, review
items, next actions) and `handoff.json` for the next agent (typed actions with
commands, pending states, unresolved warnings) — produced by
`scripts/bundle_synopsis.py`; `state.py` refuses to mark a bundle `shared` without
them, because a bundle that can't be read on arrival isn't a handoff, it's homework.
`state.py` also refuses `shared` while any resolved boundary pointer carries no
disposition (`scripts/state.py disposition`; `references/boundary-protocol.md`) — a
bundle that ships silently omitting what its own target points at outside its root
isn't a handoff either, it's a card that fails its own replication test. The bundle also carries the
**process trace** (`exports/process/`): every scan stamps a `run` block (config, timing),
elicitation runs through structured question tools so answers land as data points, and
each fill records its provenance — because how the run went (slow scans, skipped
questions, cycles to converge) is itself a finding about the system. Review the
bundler's secret warnings before a bundle leaves the machine.

## Extending

Prefer a registry overlay over changing the maintained registry. Create a provisional
entry with `scripts/concern_registry.py propose`, then validate base plus overlay with
`scripts/concern_registry.py validate`. A concern earns promotion only when it asks a
distinct question, owns distinct evidence, declares its capability needs, changes the
replication or handoff result, and has survived a real run.

Use `scripts/cartographer_scan.py` for scans. It walks once, reads each relevant file
once, caches by stat plus registry signature, and computes cross-concern patterns from
the same observation pass. Extend behavior through registry/config overlays rather than
adding one wrapper script per concern.
