# Code/Scripts

Concern slug: `code-scripts`

## What this cares about

What code or scripts implement or evidence this object's actual behavior — the artifacts you can point to and say this is what actually runs.

## Type

`list<file_ref>`

## Interrogation

What code/scripts carry out this behavior? Point to them, or state none exist and why.

## Scan notes

Baseline evidence source — most other concerns cross-reference this one's node list rather than re-walking the filesystem themselves.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns code-scripts`
