# System Cartographer

A [Claude Code](https://claude.ai/code) skill that reverse-engineers a tacit Agent, Skill,
Workflow, or AI-native system — across GPT, Claude, Grok, Ollama, custom harnesses, IDE agents,
and repository environments — into a portable, replication-grade description of it.

It negotiates the host's model, runtime, tools, authority, evidence roots, and constraints;
elicits the builder's own mental model *before* scanning (so the gap between belief and evidence
is measurable, not contaminated); runs a bounded, registry-driven scan that promotes a candidate
file to real evidence only when it survives a structural check (real frontmatter, a real import,
a real hook binding — never a bare filename match); and produces a bundle whose product surface
is an **onboarding card** — capability-and-requirement cards for every real agent, skill, and
workflow the target has, built from that target's own data, plus the actual exported source
underneath every claim.

Full documentation: [SKILL.md](SKILL.md). Version history (every entry earned by actually
running the tool against a real target, not by reading the code): [RELEASES.md](RELEASES.md).

## Install

Drop this directory into your Claude Code skills folder as `system-cartographer`:

```bash
git clone https://github.com/bdf1992/system-cartographer ~/.claude/skills/system-cartographer
```

Claude Code picks it up automatically; invoke it by describing what you want documented, audited,
ported, or handed off (see `SKILL.md`'s frontmatter `description` for trigger phrasing), or by name.

## Layout

- `SKILL.md` — the skill definition Claude Code loads.
- `scripts/` — the deterministic scanner, structural validators, export planner, bundler, save-state
  manager, and the onboarding-card renderer.
- `references/` — the concern registry, per-concern scan configs and card templates, and the
  protocol docs (environment negotiation, boundary pointers, slot-fill rules, save states).
- `agents/openai.yaml` — a non-Claude host binding.

## Public repository lineage

`lineage/` records public repository identities and qualified relations. It generates a profile README, an evidence map, and a Schematically document. Run `python -m pip install -r lineage/requirements.txt`, then `python lineage/validate.py` and `python lineage/render.py --check`. Source integrity, declared relationships, and runtime verification remain distinct.

See [the map](lineage/LINEAGE.md) and [continuation queue](lineage/WORK-QUEUE.md).

## License

See [LICENSE](LICENSE).

<!-- lineage:begin — generated from system-cartographer lineage/lineage.yaml. Do not hand-edit. -->

## Where this sits

This is one of 29 repositories on this account whose relations are recorded, with the evidence for each, in [`lineage.yaml`](https://github.com/bdf1992/system-cartographer/blob/claude/access-requirements-zbl1s7/lineage/lineage.yaml). What that record says about this one:

**Claim.** A Claude Code skill that reverse-engineers an undocumented agent or AI-native system into a description complete enough to rebuild it.

**Source inspection.** `python lineage/verify_sources.py --remote --node system-cartographer` — Pinned source blob a1fc3af3ef3c833d16b6c954d02b2abedcca8dae; SHA256 and cited text verified, observed 2026-09-05.

Run this source check from the system-cartographer checkout. It checks a pinned source file; it does not certify the runtime or repeat a test suite.

**Relations.** None recorded, in either direction. 22 of the 29 repositories are unconnected; that absence is recorded rather than papered over with a plausible edge.

<!-- lineage:end -->
