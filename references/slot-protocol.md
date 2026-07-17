# Slot protocol — shared by every concern card

Each concern is a typed slot. The card holds the static half (name, type, cares_about,
interrogation). Everything below is the dynamic half, filled per object, never preassigned.

## Ask twice

Every interrogation question runs twice:

1. **Elicit (blind)** — before the user sees any scan output. Capture what they *believe*
   the answer is. Their belief is evidence too — it's just a different kind, and it must
   be collected before the scan can anchor it.
2. **Reconcile (with evidence)** — after scanning, show the delta between what they said
   and what the evidence shows, and resolve it together.

## Dynamic fields

- **mode** — `invariant` (must hold for this object) or `covariate` (conditionally
  relevant, tied to another slot). Judged per object at fill time.
- **value** — the answer, written to pass the replication test below: a self-contained
  statement of capability and requirement — what this object affects and effects, and
  what it needs in order to do so. Mechanism (how it internally triggers its causes)
  is not the value; a replicating team chooses their own mechanism.
- **priors** — optional pointers that accelerate a team who *does* have context.
  Additive only; a pointer is a citation, never a substitute for the value. Priors
  must be **portable**: point into the bundle's `exports/` directory (real content,
  excerpted by `scripts/export_bundle.py`) or at durable references (remote commit
  SHAs, ticket URLs). A machine-local path — the builder's repo checkout, a
  `~/.claude/projects/` transcript — is not a prior; export the content it names
  into the bundle and point there instead. The bundle's `manifest.json` preserves
  each export's original location for anyone who also has the source system.
- **status** — exactly one of: `defined` (formally specified somewhere) · `discovered`
  (inferred from evidence, unconfirmed) · `described` (narrated, not formalized) ·
  `absent:needs_lifting` (exists in practice, never captured) ·
  `absent:not_applicable(<reason>)`. Never blank.

## The replication test (what "filled" means)

Before marking any slot terminal, read its value alone — no priors, no scan output, no
access to the original repo. Could a competent dev team rebuild an equivalent
capability from that text? If not, the slot isn't filled — it's pointed. Rewrite it as
effect + requirement until it stands on its own. "See scripts/jira_sync.py" fails;
"transitions JIRA tickets through the QA workflow states, requiring project-scoped
write auth and the workflow's state map" passes — and the file path goes in priors.

This is the telos of the whole card: a tactile definition of capabilities and
requirements, portable without its source system, with pointers attached as priors for
anyone lucky enough to also have the source.

## Delta classification (Reconcile output)

For each slot, compare the blind answer against the scan evidence and tag:

- **confirmed** — belief and evidence agree. Highest-confidence fill; move on fast.
- **drift** — evidence shows the system changed and the user's model didn't follow.
- **undocumented** — evidence shows something the user never mentioned. Ask if it's
  intentional, forgotten, or unknown to them.
- **unevidenced** — user claims it, scan finds nothing. Either the scan missed it
  (extend the config, rescan) or it lives only in habit → `absent:needs_lifting`.
- **aspiration** — the user said "it should / I meant it to." Not a defect. Route to
  the Tending section of the final card, not to a status fix.

The deltas — not the confirmations — are the product. A card that's all `confirmed`
means the user already knew their system; that's a fine outcome, but a rare one.

## Preliminary vs informed scans

The shipped `scan.config.json` files are deliberately naive first-contact instruments —
TODO/FIXME greps, generic import patterns, guessed globs. They exist to make blind
first contact cheap, not to be believed. After elicitation and first reconcile, the
run knows things no shipped config could: the builder's own vocabulary, their named
failure modes, the actual integration names, the error signatures visible in exemplar
transcripts. **Regenerate the affected concerns' configs from that knowledge and
rescan in a Cycle round** — save the derived config beside the original (e.g.
`scan.config.informed.json`) so each finding's `run` block shows which instrument
produced it. Findings from an informed scan supersede preliminary ones; a preliminary
finding that an informed scan can't reproduce gets demoted, not silently kept. Issues
is the loudest example: markers in code are a hint, but the informed issue scan is
built from what the builder said breaks and what the workflow's own artifacts (tickets,
transcripts, reverts) actually record breaking.

## Process trace: the process is informative of the product

The run is instrumented end to end, and the trace ships in the bundle
(`exports/process/`) alongside the card:

- **Scans** — every script stamps a `run` block into its output (script, argv, config
  path, start time, duration_ms). Slow scans over "simple" systems and instant scans
  over "rich" ones are both findings.
- **Elicitation** — ask through structured question tools (AskUserQuestion or the
  host's equivalent) rather than free prose wherever the question has a bounded shape,
  so each answer lands as a data point: concern, question, chosen answer, free-text
  addendum, round number, and whether it was skipped. Free conversation still has its
  place — follow-the-energy moments — but log those exchanges as entries too.
- **Per-fill provenance** — each slot fill records how it was obtained: which tool or
  script produced it, in which round, at which phase (elicit-blind vs reconcile).

Why: the shape of the process measures the object. A concern that took three cycles to
converge, a question the builder skipped twice, an elicitation answer that flipped at
reconcile — these are findings about the system, not logistics. Discarding them would
throw away a measurement the run already paid for.

## Pacing: depth follows signal

Do not give the twelve concerns equal airtime. Where the user's telling is rich and the
evidence is dense, dig. Where both are thin, ask once and move on — record the thinness
itself (a concern the builder never thinks about is data). What the user skips,
hesitates on, or over-explains is the count/quality signal that steers the whole run;
the skill provides the frame, the user's own system decides what matters.
