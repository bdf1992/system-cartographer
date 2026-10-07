# Analysis brief — for the agents that analyse a unit

The scan and the parse produce a graph. Analysis is what an agent adds on top: reading a
unit of that graph against its source and saying what is true of it. Every conclusion is a
claim in the audit ledger, so it goes through the same eleven stages as any other claim.
Nothing an agent concludes is written anywhere else.

Three roles, three different agents. One agent never holds two roles on the same claim.

## Analyst

Given: one packet, `<run>/analysis/packets/<unit>.json`, and read access to the target.

1. Read the packet whole: members, `links_inside`, `reaches`, `reached_by`, `lint`,
   `questions`.
2. Open the source. The packet says where to look; it is not the evidence. Read the
   busiest members first (`links` is highest), then anything the questions turn on.
3. Write one to three claims. A claim is one sentence someone could check and find false:
   "`write_record` is the only function that writes a record file" is a claim; "the store
   module handles persistence" is not.
4. Record each claim through the stages, in order, with `scripts/audit.py`:
   - `intake --source agent --unit <unit> --concern <concern> --statement "..."`
   - `findings`: what in the packet led you here (`--ref` the packet or a member id).
   - `evidence`: what the source shows, one entry per fact, `--ref file:line`.
     `--basis EXTRACTED` only for what you read in the source yourself; a link the graph
     marks INFERRED stays `INFERRED` until you have read both ends.
   - `conflicts`: where the graph and the source disagree, or the name and the behaviour,
     or two members. `--none --text <where you looked>` if you looked and found none.
   - `organization`: the unit, and the neighbouring unit if the claim is about a boundary.
   - `refutation`: state what would make your claim false, go and look for it, and record
     what you did and whether the claim survived. A refutation you did not run is not one.
   - `judgement`, `verdict` (confirmed, drift, undocumented, unevidenced, aspiration),
     `qualification` (what it rests on, what you did not read, what would overturn it).
5. Stop at `qualification`. Settling is not yours.

Read only. Change nothing in the target. Do not fix what you find; a defect is a claim
with the verdict `drift` and a conflict that says what is wrong.

## Lead

The session running the audit. It hands out packets, reads `audit.py status`, and settles
each qualified claim: `accepted`, `repair` (a defect to fix), `deferred`, or `dropped`.
It does not edit an analyst's entries; to disagree it records a conflict, which reopens
the claim.

## Validator

Given: a settled claim id, and read access to the target. Not the analyst's entries.

1. `audit.py validate <claim> --actor <you>`: this opens a second record of the same
   statement and prints its id.
2. Do not open `audit.json` or `AUDIT.md`. Work from the statement and the source.
3. Walk your record from `findings` to `verdict` exactly as an analyst would, reaching
   your own verdict. Agreement is not the goal; a different verdict reopens the first
   claim, which is the tool doing its job.

## What the lead reports back

`AUDIT.md`, and a re-run of `graph_export.py --audit <run>/audit.json`, which puts each
unit's claims and verdicts on the map beside the code they are about.
