# Required Tools & Repos (Knowledge/Capability)

Concern slug: `required-tools-repos`

## What this cares about

What tools, repositories, or other knowledge/capability this object needs access to or familiarity with in order to function.

## Type

`list<ref>`

## Interrogation

What tools does this need? What repos does it touch or need to know about? What else must it know to work?

## Scan notes

Scans manifests (package.json, requirements.txt, .mcp.json-style config) and READMEs for repo URLs and tool/connector references.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns required-tools-repos`
