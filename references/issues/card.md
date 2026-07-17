# Issues

Concern slug: `issues`

## What this cares about

Known failures or invariant violations already observed.

## Type

`list<issue_ref>`

## Interrogation

What's broken before, and which invariant did it violate?

## Scan notes

The shipped config (TODO/FIXME markers + git_log) is the **preliminary** scan only —
cheap first contact, not to be believed on its own. The **informed** scan is built in
a Cycle round from what the run has learned: the builder's named failure modes from
elicitation, error signatures found in exemplar transcripts, ticket states from the
workflow's own integrations. Derive a new config from those and rescan; see
slot-protocol.md, "Preliminary vs informed scans". The fix/revert ratio surfaced here
also feeds session-quality's analysis — shared evidence, not a duplicated scan.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns issues`
