# Integrations

Concern slug: `integrations`

## What this cares about

External systems this object reads from or writes to.

## Type

`list<system_ref>`

## Interrogation

What external systems does this touch — read, write, or both?

## Scan notes

High false-positive-rate scan by design — it over-collects candidates and leaves confirmation (read/write/both, in-scope or not) to interrogation.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns integrations`
