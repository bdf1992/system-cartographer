# Memories

Concern slug: `memories`

## What this cares about

Persistent context this object relies on or produces across runs.

## Type

`list<memory_ref>`

## Interrogation

Does this depend on anything remembered from prior runs? What, and where does it live?

## Scan notes

Structural scan only (no edge patterns) — memory stores are usually a place, not a reference pattern. If nothing turns up under common memory paths, ask directly rather than widening the glob indefinitely.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns memories`
