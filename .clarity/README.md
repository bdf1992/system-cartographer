# Clarity receipts

`coverage.json` records completed `clarity` reviews of this repository's
root-level human-facing prose, keyed by content digest.

The `unslop` and `clarity` skills are not vendored here. The canonical copies
are in the Soveraeign repository:

- `Soveraeign/.claude/skills/unslop/SKILL.md`
- `Soveraeign/.claude/skills/clarity/SKILL.md`

The receipt format is Soveraeign's `soveraeign-clarity-coverage/v1`: for each
reviewed path, the digest of the artifact reviewed, the digests of the sources
that govern its claims, and whether the review changed the text. A review stops
being valid when either the artifact or one of its sources changes.
