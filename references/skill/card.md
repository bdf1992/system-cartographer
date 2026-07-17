# Skill

Concern slug: `skill`

## What this cares about

A packaged, invocable set of instructions — not autonomous, triggered.

## Type

`identity/trigger record`

## Interrogation

Is this a Skill — invoked instructions rather than a standing actor? What triggers it?

## Scan notes

Looks specifically for SKILL.md-shaped files. If none are found but the object clearly does something invocable, that's a needs_lifting signal, not a not_applicable one.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns skill`
