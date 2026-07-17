# Related session count/quality

Concern slug: `session-quality`

## What this cares about

How much usage/session history backs this object, and what that history actually looks like: frequency, recency, and whether it's converging (fewer fixes/reverts over time) or still volatile. A read on maturity, not a headcount. A single integer answers a different, less useful question than the one this concern is asking.

## Type

`analysis (trend + quality signal — not a bare count)`

## Interrogation

Look at the commit/session history touching this object. Is activity frequent or sparse, recent or stale, converging or still churning? Characterize the pattern — don't just count events.

## Scan notes

The scan script computes structured inputs for an analysis (commits-per-month buckets, days-since-last-touch, fix/revert-subject ratio) and stops there — it does NOT reduce them to one number. Turning those inputs into the actual trend read stays an interrogation step, done with judgment, not printed by the script.

## Fill protocol

Ask this concern's interrogation question twice — once blind (Elicit, before any scan
output is shown), once with evidence in hand (Reconcile). Fill rules, status ladder,
delta taxonomy, and pacing: see `../slot-protocol.md`. mode/value/status are filled by
the target's builder or agent, never preassigned here.

Scan: `scripts/session_telemetry.py --target <path> [--sessions-dir <dir>]`
