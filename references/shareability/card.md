# Shareability

Concern slug: `shareability`

## What this cares about

Who this object's knowledge is for beyond its builder, and through what channel it
reaches them (or fails to): where documentation and exports live today, who can access
them, and how updates propagate when the object changes. An object nobody else can
receive is bus-factor-one by construction, whatever its other slots say.

## Type

`distribution record (audience, channel, access, propagation)`

## Interrogation

Who else needs to understand or receive this object — a team, a successor, an auditor?
Through what channel do they get it today: repo, wiki, tickets, word of mouth, nothing?
And where should this very run's export bundle live so those people can actually reach
it?

## Scan notes

Looks for evidence of existing distribution: READMEs and docs directories, publishing
workflows (.github/workflows), doc-site configs, wiki/Confluence/remote URLs in the
tree. Doubly self-referential: this slot's answer decides where the current run's own
bundle gets delivered (workflow-template.md, Share phase), and the channel options are
seeded by what the Integrations concern discovered — GitHub access found there becomes
a delivery candidate here.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/cartographer_scan.py --target <path> --target-name <name> --concerns shareability`
