# Workflow

Concern slug: `workflow`

## What this cares about

The sequence this object follows — trigger, steps, branching, exit.

## Type

`structured (trigger, steps, exit)`

## Interrogation

What triggers this, what are the steps in order, what tells it to stop?

## Scan notes

Two populations, treated differently:

**Existing (formalized)** — Workflow scripts (`phase()`/`pipeline()` dialect), scheduled
tasks and cron expressions, CI pipelines (.github/workflows), slash commands, hooks in
settings. The preliminary config finds these directly; they classify as `defined`.

**Latent (habitual, formalized nowhere)** — the sequence the builder just *does*: "then
I always rerun the suite, then I move the ticket." These are the prize — a defined
workflow is already safe, the latent one is what needs lifting. They leave evidence as
*recurrence*, not artifacts: repeated action sequences across session transcripts,
rhythmic commit patterns in git history, the builder's own "then I..." narration at
elicitation. The preliminary scan can't see recurrence; the informed rescan
(slot-protocol.md) can — once elicitation names a habitual sequence, derive patterns
from its vocabulary and grep transcripts/history for it. Classify latent workflows as
`described` or `absent:needs_lifting`, and route every one to Tending as a lift
candidate.

This is also the object type this skill itself instantiates when it runs — see
references/workflow-template.md for the phased/cycled orchestration.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns workflow`
