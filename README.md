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

A scan also exports as a graph in graphify's format, a report on it, and a Schematically
document (`scripts/graph_export.py`), with every link marked as backed by evidence or by a
pattern match only, and each way of grouping the nodes tested against shuffled groupings. With
the asset overlay (`references/assets.registry.json`) the same run maps a company's documents,
data, records, services, owners, access, media and log data, with the system description as one asset
kind among them.

The target does not have to be a repository. Pointed at a shared drive or any folder, the
overlay's `files` kind holds every file no other concern accounts for, so the map covers the
whole file system and shows what nobody has explained. Log files are linked to the severities
and the exception names they contain, so logs that record the same failure sit together.

```bash
python scripts/environment_probe.py --root <folder> --out run/environment.json
python scripts/cartographer_scan.py --target <folder> --environment run/environment.json \
  --registry references/concerns.registry.json --registry references/assets.registry.json \
  --no-boundary-scan --out-dir run/scan --cache run/scan-cache.json --compact
python scripts/graph_export.py --scan-dir run/scan --out-dir run/graph --group-by asset
```

That writes `run/graph/graph.json`, `GRAPH_REPORT.md`, `system.sov` and
`system-overview.sov`, one card per group, which is the one to open first. Add
`--schematically <checkout>` to the last command to have the document laid out.

## Code, actors and agent analysis

`scripts/code_graph.py` parses the target's code with graphify's tree-sitter extractor, so the
map holds every function, class and module with the calls, imports, inheritance and uses between
them, `ruff` findings on the definitions they fall in, and declared dependencies set against
imported ones. The export adds the agents, skills, hooks and workflows as nodes wired to the files
they run. `scripts/analysis_packets.py` then cuts the map into units, and agents analyse each one
and record what they conclude as claims in the audit.

```bash
python scripts/code_graph.py --scan-dir run/scan --out-dir run/code
python scripts/graph_export.py --scan-dir run/scan --code-dir run/code --out-dir run/graph --group-by asset
python scripts/analysis_packets.py --graph run/graph/graph.json --run run
```

The code pass needs `graphify` importable (`pip install graphifyy`); `ruff` is optional.

## The audit

Every claim the run makes about the target, whether the builder said it or the scan supports
it, walks eleven recorded stages: intake, findings, evidence, conflicts, organization,
refutation, judgement, verdict, qualification, settle, validation. `scripts/audit.py` keeps the
record and holds the order: no judgement before an attempt to refute the claim, no `confirmed`
verdict without evidence a check backs, no settlement before the verdict is qualified.
Validation is a second record of the same claim, walked through the same stages by a different
actor; a different verdict reopens the first claim instead of overruling it.

```bash
python scripts/audit.py init --run run --actor <you>
python scripts/audit.py seed --run run --actor <you> --scan-dir run/scan
python scripts/audit.py status --run run
```

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
- `scripts/audit.py` — the claim ledger: eleven stages, refusals, validation by a second actor.
- `scripts/graph_export.py` — a scan as a graphify-format graph, a report and a Schematically document.
- `references/assets.registry.json`, `references/assets/` — the asset overlay and its scan configs.
- `references/` — the concern registry, per-concern scan configs and card templates, and the
  protocol docs (environment negotiation, boundary pointers, slot-fill rules, save states).
- `agents/openai.yaml` — a non-Claude host binding.

## License

Not yet declared.
