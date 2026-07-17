# Agent

Concern slug: `agent`

## What this cares about

Identity and authority of an acting entity — what it's empowered to do and its scope.

## Type

`identity/scope record`

## Interrogation

Is this an Agent — something acting autonomously with tool access? What's its scope?

## Scan notes

Light scan — agent identity is usually declared in a small number of files, not scattered across the codebase. Absence here is meaningful: it may mean this object is actually a Skill or Workflow, not an Agent.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns agent`
