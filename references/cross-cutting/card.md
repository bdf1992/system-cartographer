# Cross-cutting concerns

Concern slug: `cross-cutting`

## What this cares about

What this object requires to be true about the other objects around it.

## Type

`list<relation_ref>`

## Interrogation

What must hold about the other Agents/Skills/Workflows nearby for this to work correctly?

## Scan notes

Not a separate filesystem scan. `cartographer_scan.py` derives this concern by joining
the other concerns from the same observation pass. Interpret it after those graphs;
never run a second walk merely to discover relations.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: included automatically by `scripts/cartographer_scan.py`; `--concerns` cycles
still include the cross-cutting join for the selected subset.
