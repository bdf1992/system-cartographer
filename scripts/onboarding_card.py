#!/usr/bin/env python3
"""Render the onboarding card — the skill's standing final-deliverable template.

This is the shape every cartography run is aimed at producing (SKILL.md's "what
done means"): a dev with no priors reads capability + requirement cards for
every real agent/skill/workflow this target has, sees what it depends on
outside its own root, and can open the actual exported source underneath any
claim — all from one self-contained file. `bundle_synopsis.py`'s README/
handoff/report.html are the *process* surfaces (state, warnings, next
actions); this is the *product* surface: the card itself.

Every string in this module is generic English about concerns and evidence
stages — it carries no knowledge of any particular target's agents, roles, or
vocabulary. All content comes from `extracted` fields structural_validators.py
already pulled out of the target's own files (a frontmatter `name:`/
`description:`, a real hook binding, an import), or from patterns.json's own
generic fields (summary counts, boundary pointers). Point this at any target
system and it renders the same template from that target's own data — nothing
here is graey-specific, or specific to any other one target.

    python onboarding_card.py --scan-dir <run>/scan --bundle <run> --out <run>/onboarding-card.html
"""
import argparse
import html
import json
import os

CAPABILITY_TYPES = {"actor", "instruction"}     # agent-shaped, skill-shaped
SEQUENCE_TYPES = {"sequence"}                    # workflow-shaped
EVIDENCED_STAGES = {"structural", "behavioral", "observed", "confirmed"}
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".woff", ".woff2", ".ttf"}


def load(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_in_bundle(bundle_dir, name):
    """scan.json/patterns.json travel inside exports/process/ once a bundle is
    built (build_export_manifest.py) — fall back to searching for them so this
    can render straight from a bundle dir without also needing --scan-dir."""
    if not bundle_dir:
        return None
    exports = os.path.join(bundle_dir, "exports")
    if not os.path.isdir(exports):
        return None
    for root, _, files in os.walk(exports):
        if name in files:
            return os.path.join(root, name)
    return None


def esc(x):
    return html.escape("" if x is None else str(x))


def evidenced_findings(graph):
    return [f for f in (graph.get("findings") or []) if f.get("evidence_stage") in EVIDENCED_STAGES]


def evidenced_files(graph):
    """One representative finding per file — enough for a card; a file with
    many findings (code imports) still gets one row here."""
    by_file = {}
    for f in evidenced_findings(graph):
        by_file.setdefault(f["file"], f)
    return by_file


def render_capability_cards(concern_id, title, graph):
    files = evidenced_files(graph)
    if not files:
        return ""
    cards = []
    for rel, finding in sorted(files.items()):
        extracted = finding.get("extracted") or {}
        name = extracted.get("name") or rel
        description = extracted.get("description") or finding.get("signal", "")
        tools = extracted.get("tools")
        meta = f'<div class="meta"><b>Tools:</b> {esc(tools)}</div>' if tools else ""
        cards.append(f'''
    <div class="card">
      <div class="role-row"><h3>{esc(name)}</h3><span class="path-tag">{esc(rel)}</span></div>
      <p class="cap">{esc(description)}</p>
      {meta}
    </div>''')
    return f'''
  <h2>{esc(title)} ({len(files)})</h2>
  <div class="cards">{"".join(cards)}</div>
'''


def render_workflow_section(graph):
    files = evidenced_files(graph)
    if not files:
        return ""
    hook_rows, other_cards = [], []
    for rel, finding in sorted(files.items()):
        extracted = finding.get("extracted") or {}
        if extracted.get("trigger") == "host-hook-config":
            for row in extracted.get("hook_rows", []):
                hook_rows.append({"file": rel, **row})
        else:
            name = extracted.get("name") or rel
            desc = extracted.get("description") or finding.get("signal", "")
            trig = extracted.get("trigger", "declared sequence")
            other_cards.append(f'''
    <div class="card">
      <div class="role-row"><h3>{esc(name)}</h3><span class="path-tag">{esc(rel)}</span></div>
      <p class="cap">{esc(desc)}</p>
      <div class="meta"><b>Trigger:</b> {esc(trig)}</div>
    </div>''')
    parts = [f"<h2>Workflow / trigger bindings ({len(files)} file(s))</h2>"]
    if hook_rows:
        parts.append('<table class="hook-table"><tr><th>File</th><th>Event</th><th>Matcher</th><th>Command</th></tr>')
        for r in hook_rows:
            parts.append(f'<tr><td>{esc(r["file"])}</td><td>{esc(r["event"])}</td>'
                          f'<td>{esc(r.get("matcher") or "—")}</td><td><code>{esc(r["command"])}</code></td></tr>')
        parts.append("</table>")
    if other_cards:
        parts.append(f'<div class="cards">{"".join(other_cards)}</div>')
    return "\n".join(parts)


def render_table_section(concern_id, title, graph):
    files = evidenced_files(graph)
    if not files:
        return ""
    rows = []
    for rel, finding in sorted(files.items()):
        rows.append(f'<tr><td>{esc(rel)}</td><td>{esc(finding.get("evidence_stage"))}</td>'
                     f'<td>{esc(finding.get("signal"))}</td></tr>')
    return f'''
  <h2>{esc(title)} ({len(files)})</h2>
  <table class="hook-table"><tr><th>File</th><th>Evidence</th><th>Signal</th></tr>{"".join(rows)}</table>
'''


def render_boundary_section(patterns):
    pointers = [p for p in (patterns or {}).get("boundary_pointers", [])
                if p.get("exists") and p.get("relation") != "unresolved"]
    if not pointers:
        return ""
    rows = []
    for p in sorted(pointers, key=lambda p: -len(p["referenced_from"]))[:40]:
        variants = p.get("reference_variants") or [p["reference"]]
        ref = esc(p["reference"]) + (f" <span class=\"path-tag\">+{len(variants)-1} spelling(s)</span>" if len(variants) > 1 else "")
        rows.append(f'<tr><td>{ref}</td><td>{esc(p["relation"])}</td>'
                     f'<td>{len(p["referenced_from"])}</td><td>{esc(p.get("disposition") or "undispositioned")}</td></tr>')
    return f'''
  <h2>What this depends on outside its own root ({len(pointers)})</h2>
  <p>Every real, resolved reference this target's own files make to something outside the scanned
  root — named rather than silently dropped, because a card that omits what its subject depends on
  fails its own replication test.</p>
  <table class="hook-table"><tr><th>Reference</th><th>Relation</th><th>Cited from N files</th><th>Disposition</th></tr>{"".join(rows)}</table>
'''


def render_source_appendix(manifest):
    if not manifest:
        return "<h2>Source</h2><p>No bundle manifest supplied — run export_bundle.py and pass " \
               "--bundle to embed the real exported source here.</p>"
    blocks = []
    for e in manifest.get("entries", []):
        export = e.get("export")
        if not export or e.get("slot") == "process":
            continue
        ext = os.path.splitext(export)[1].lower()
        if e.get("binary") or ext in BINARY_EXTENSIONS:
            blocks.append(f'<details><summary>{esc(export)} <span class="path-tag">binary, {e.get("byte_size", "?")} bytes</span></summary></details>')
            continue
        full = os.path.join(manifest.get("_bundle_dir", ""), *export.split("/"))
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            content = "(source not found on disk)"
        blocks.append(f'<details><summary>{esc(export)} <span class="path-tag">from {esc(e.get("source"))}</span></summary>'
                       f'<pre>{esc(content)}</pre></details>')
    if not blocks:
        return "<h2>Source</h2><p>The bundle carries no non-process exports yet.</p>"
    return f"<h2>Source — every evidenced file exported ({len(blocks)})</h2>{''.join(blocks)}"


CSS = """
  :root {
    --bg: #f7f5ee; --ink: #21261f; --ink-soft: #4b5147; --panel: #ffffff; --rule: #d9d3c2;
    --accent: #a8641f; --accent-soft: #dfe6d8; --code-bg: #f0ede1; --tag-bg: #eef1e6;
  }
  :root[data-theme="dark"] {
    --bg: #14170f; --ink: #e9e6da; --ink-soft: #a8ad9c; --panel: #1b1f16; --rule: #333a2a;
    --accent: #d99a4e; --accent-soft: #232c1c; --code-bg: #10130d; --tag-bg: #1f2517;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #14170f; --ink: #e9e6da; --ink-soft: #a8ad9c; --panel: #1b1f16; --rule: #333a2a;
      --accent: #d99a4e; --accent-soft: #232c1c; --code-bg: #10130d; --tag-bg: #1f2517;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.6 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
  main { max-width: 920px; margin: 0 auto; padding: 3rem 1.5rem 5rem; }
  h1, h2, h3 { font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif; text-wrap: balance; }
  h1 { font-size: 2rem; margin: 0 0 .3rem; letter-spacing: -.01em; }
  h2 { font-size: 1.3rem; margin: 3rem 0 .6rem; padding-bottom: .4rem; border-bottom: 2px solid var(--rule); color: var(--accent); }
  h3 { font-size: 1.05rem; margin: 0 0 .2rem; }
  p { max-width: 68ch; color: var(--ink-soft); }
  p.lede { max-width: 74ch; font-size: 1.05rem; color: var(--ink); }
  code, pre, .mono { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }
  code { background: var(--code-bg); padding: .1em .35em; border-radius: 4px; font-size: .9em; }
  .kicker { display: inline-block; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); margin-bottom: .6rem; }
  .stat-row { display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 1.5rem 0 2rem; }
  .stat { min-width: 110px; }
  .stat .n { font-size: 1.6rem; font-family: Georgia, serif; font-variant-numeric: tabular-nums; }
  .stat .l { font-size: .8rem; color: var(--ink-soft); }
  .hook-table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .88rem; }
  .hook-table th, .hook-table td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid var(--rule); vertical-align: top; }
  .hook-table th { color: var(--ink-soft); font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }
  .cards { display: grid; grid-template-columns: 1fr; gap: .9rem; }
  .card { background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; padding: 1.1rem 1.3rem; }
  .card .role-row { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
  .path-tag { font-size: .72rem; color: var(--ink-soft); background: var(--tag-bg); padding: .1rem .5rem; border-radius: 999px; white-space: nowrap; }
  .card .cap { margin: .5rem 0 .4rem; color: var(--ink); }
  .card .meta { font-size: .85rem; color: var(--ink-soft); margin-top: .3rem; }
  .card .meta b { color: var(--ink); font-weight: 600; }
  details { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; margin-bottom: .5rem; padding: .1rem 1rem; }
  details summary { cursor: pointer; padding: .7rem 0; font-weight: 600; }
  details pre { background: var(--code-bg); padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: .82rem; white-space: pre-wrap; word-break: break-word; margin: 0 0 1rem; }
  footer { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--rule); font-size: .82rem; color: var(--ink-soft); }
"""


def build(scan_dir, bundle_dir, target_name=None):
    scan_path = os.path.join(scan_dir, "scan.json") if scan_dir else find_in_bundle(bundle_dir, "scan.json")
    patterns_path = os.path.join(scan_dir, "patterns.json") if scan_dir else find_in_bundle(bundle_dir, "patterns.json")
    scan = load(scan_path) or {}
    patterns = load(patterns_path) or {}
    manifest = load(os.path.join(bundle_dir, "manifest.json")) if bundle_dir else None
    if manifest is not None:
        manifest["_bundle_dir"] = bundle_dir

    graphs = scan.get("graphs", {})
    target = target_name or scan.get("target") or "unknown target"
    s = patterns.get("summary", {})

    sections = []
    for cid, graph in sorted(graphs.items()):
        gtype = graph.get("type")
        if gtype in CAPABILITY_TYPES:
            sections.append(render_capability_cards(cid, f"{cid} — capabilities", graph))
        elif gtype in SEQUENCE_TYPES:
            sections.append(render_workflow_section(graph))
        elif gtype not in ("relation",):
            sections.append(render_table_section(cid, f"{cid} — evidence", graph))
    sections.append(render_boundary_section(patterns))
    sections.append(render_source_appendix(manifest))

    stat_row = f'''
  <div class="stat-row">
    <div class="stat"><div class="n">{s.get("files_seen", "?")}</div><div class="l">files scanned</div></div>
    <div class="stat"><div class="n">{s.get("files_with_evidence", "?")}</div><div class="l">structurally evidenced</div></div>
    <div class="stat"><div class="n">{s.get("edges", "?")}</div><div class="l">real edges</div></div>
    <div class="stat"><div class="n">{s.get("findings", "?")}</div><div class="l">findings</div></div>
    <div class="stat"><div class="n">{s.get("boundary_pointers", "?")}</div><div class="l">out-of-root references</div></div>
  </div>'''

    produced_by = scan.get("produced_by", {})
    return f'''<title>{esc(target)} — onboarding card</title>
<meta charset="utf-8">
<style>{CSS}</style>
<main>
  <span class="kicker">Onboarding card · replication-grade export</span>
  <h1>{esc(target)}</h1>
  <p class="lede">Capabilities and requirements for every real, structurally-evidenced agent,
  skill, and workflow this target actually has — not a description standing in for the system,
  but a card built from what a scan proved plus the exported source underneath every claim.</p>
  {stat_row}
  {"".join(sections)}
  <footer>Generated by {esc(produced_by.get("skill", "system-cartographer"))}
  {esc(produced_by.get("skill_version", ""))} from a real scan of {esc(target)}. Every card above
  comes from a structural finding (real frontmatter, a real hook binding, a real import) — never
  from a filename match alone.</footer>
</main>
'''


def main():
    ap = argparse.ArgumentParser(description="Render the onboarding card from a real scan + bundle")
    ap.add_argument("--scan-dir", help="Directory with scan.json/patterns.json directly; omit to "
                    "derive them from --bundle's exports/process/")
    ap.add_argument("--bundle", help="Bundle directory (for manifest.json — embeds real exported "
                    "source; also used to locate scan.json/patterns.json if --scan-dir is omitted)")
    ap.add_argument("--target-name")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not args.scan_dir and not args.bundle:
        ap.error("one of --scan-dir or --bundle is required")
    doc = build(args.scan_dir, args.bundle, args.target_name)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(doc)
    print(f"onboarding card: {args.out}")


if __name__ == "__main__":
    main()
