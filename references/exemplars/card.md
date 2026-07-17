# Exemplars

Concern slug: `exemplars`

## What this cares about

A concrete instance demonstrating this object working as intended.

## Type

`list<example_ref>`

## Interrogation

Give one real run where this worked. If none exists, say so.

## Scan notes

Looks for test/eval/example artifacts plus recent commit subjects as candidate exemplars — still needs a human or the target's agent to confirm one actually demonstrates correct behavior, the script can't judge that.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns exemplars`
