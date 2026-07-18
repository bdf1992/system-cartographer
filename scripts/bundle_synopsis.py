#!/usr/bin/env python3
"""Generate the bundle's three review surfaces: README.md, handoff.json, report.html.

A bundle full of graph JSON is complete but not usable: the receiving agent
has to spelunk, and the reviewing human has nothing to read. This script
reads what the bundle already contains (state.json, manifest.json,
export-plan.json, any exported scan/patterns/lineage/telemetry) and writes:

  README.md     — the human surface: what this is, where it stands, what was
                  found, what needs review, what happens next.
  handoff.json  — the agent surface: current/pending states, typed actionable
                  items (owner: human|agent, with commands where mechanical),
                  unresolved warnings, artifact index.
  report.html   — a self-contained static dashboard (no external assets, no
                  network calls) of the same data, for a human who would
                  rather look at bars than read JSON. It travels inside the
                  bundle and opens directly in a browser offline — it is not
                  a hosted page, because the bundle has to work on a machine
                  with no path back to this one.

Run it whenever the bundle's contents change — state.py refuses to advance a
bundle to `shared` unless README.md and handoff.json exist, so generating
them is part of the export path, not an optional nicety.

    python bundle_synopsis.py --bundle <dir> [--target-name <name>]
"""
import argparse
import html
import json
import os
import re
from datetime import datetime, timezone

STATE_ORDER = ["initialized", "negotiated", "elicited", "exported", "shared",
               "reconciled", "carded", "delivered"]

# Same heuristic as session_telemetry.py's FIX_RE — kept identical so a
# fix/revert ratio computed from either source means the same thing.
FIX_RE = re.compile(r"\b(fix|revert|hotfix|patch)\b", re.IGNORECASE)

EVIDENCED_STAGES = ("structural", "behavioral", "observed", "confirmed")
REAL_SOURCE_CLASSES = {"source", "configuration"}

NEXT_ACTIONS = {
    "negotiated": [("agent", "Elicit the builder's blind beliefs across the twelve concerns "
                             "(structured questions; record skips as skips)", None)],
    "elicited":   [("agent", "Run the scan and build exports",
                    "python scripts/cartographer_scan.py --target <root> --out-dir <run>/scan")],
    "exported":   [("agent", "Plan what evidence actually ships",
                    "python scripts/build_export_manifest.py --scan-dir <run>/scan --profile "
                    "handoff|replication --out <run>/export-plan.json"),
                   ("human", "Review every secret warning listed below before this bundle "
                             "leaves the machine", None),
                   ("agent", "Share the bundle through a channel from the shareability slot",
                    "python scripts/state.py --bundle <bundle> advance shared --actor <who> --note <dest>")],
    "shared":     [("agent", "Reconcile: diff blind beliefs against exported evidence per slot; "
                             "tag deltas (confirmed/drift/undocumented/unevidenced/aspiration)", None),
                   ("human", "Answer the compact question list the reconciling agent sends back", None)],
    "reconciled": [("agent", "Fill cards to terminal status; apply the replication test to every "
                             "value; write the Tending section", None)],
    "carded":     [("human", "Review the finished cards before delivery", None),
                   ("agent", "Deliver the deck to its audience and record the destination", None)],
    "delivered":  [],
}


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _git_analysis(telemetry):
    """Normalize the two real shapes this can arrive in — session_telemetry.py's
    own {"git_analysis": {...}} output, or the scan's built-in session-quality
    concern, which nests the same commit data under
    {"analysis": {"commit_count", "recent_commits"}} with no git_analysis key
    at all. Reading only the first shape silently reported real git history as
    absent whenever a bundle exported the scan's own session-quality evidence
    instead of running session_telemetry.py separately."""
    if not telemetry:
        return {}
    g = telemetry.get("git_analysis")
    if g:
        return g
    analysis = telemetry.get("analysis") or {}
    commits = analysis.get("recent_commits") or []
    if not commits:
        return {}
    dates = sorted(c["date"] for c in commits if c.get("date"))
    fix_like = sum(1 for c in commits if FIX_RE.search(c.get("subject") or ""))
    return {
        "commit_count": analysis.get("commit_count", len(commits)),
        "date_range": [dates[0], dates[-1]] if dates else ["?", "?"],
        "fix_or_revert_subject_ratio": round(fix_like / len(commits), 2) if commits else None,
    }


def find_export(bundle, *names):
    for root, _, files in os.walk(os.path.join(bundle, "exports")):
        for fn in files:
            if fn in names:
                return os.path.join(root, fn)
    return None


def skill_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def collect(bundle, target_name):
    state = load_json(os.path.join(bundle, "state.json")) or {}
    manifest = load_json(os.path.join(bundle, "manifest.json")) or {}
    plan = load_json(os.path.join(bundle, "export-plan.json"))
    patterns = load_json(find_export(bundle, "patterns.json") or "")
    lineage = load_json(find_export(bundle, "lineage.json") or "")
    telemetry = load_json(find_export(bundle, "telemetry.json", "session-quality.json") or "")
    scan = load_json(find_export(bundle, "scan.json") or "")
    dispositions = load_json(os.path.join(bundle, "boundary-dispositions.json")) or {}
    secret_dispositions = load_json(os.path.join(bundle, "secret-dispositions.json")) or {}
    justifications = load_json(os.path.join(bundle, "justifications.json")) or {}

    current = state.get("current", "initialized")
    pending = STATE_ORDER[STATE_ORDER.index(current) + 1:] if current in STATE_ORDER else []
    all_warnings = [w for e in manifest.get("entries", []) for w in (e.get("secret_warnings") or [])]
    unresolved_warnings = [w for w in all_warnings if w.split(" matches ")[0] not in secret_dispositions]
    elicit_entry = next((h for h in state.get("history", [])
                         if "skip" in (h.get("note") or "").lower()
                         and "elicit" in (h.get("note") or "").lower()), None)
    if not target_name:
        target_name = (scan or {}).get("target") or "unknown target"

    artifacts, real_source_exports, size_by_class = [], 0, {}
    for e in manifest.get("entries", []):
        if not e.get("export"):
            continue
        artifacts.append({"path": e["export"], "slot": e.get("slot"), "source": e.get("source"),
                          "sha256": e.get("export_sha256"), "source_class": e.get("source_class"),
                          "byte_size": e.get("byte_size", 0)})
        cls = e.get("source_class") or "unknown"
        size_by_class[cls] = size_by_class.get(cls, 0) + (e.get("byte_size") or 0)
        if cls in REAL_SOURCE_CLASSES:
            real_source_exports += 1

    boundary_pointers = (patterns or {}).get("boundary_pointers", [])
    load_bearing = [p for p in boundary_pointers if p.get("exists") and p.get("relation") != "unresolved"]
    undispositioned = [p for p in load_bearing if p["id"] not in dispositions and not p.get("disposition")]

    stage_summary = (patterns or {}).get("summary", {})
    findings_by_stage = stage_summary.get("findings_by_stage", {})
    rejected = (patterns or {}).get("rejected_candidates", [])
    if isinstance(rejected, int):
        rejected = []  # older/compact patterns shapes; count-only, no detail to list
    plan_needing_justification = [e for e in (plan or {}).get("entries", []) if e.get("needs_justification")]
    unjustified = [e for e in plan_needing_justification if e.get("rel") not in justifications]

    return {
        "target": target_name, "state": state, "current": current, "pending": pending,
        "warnings": all_warnings, "unresolved_warnings": unresolved_warnings, "patterns": patterns,
        "telemetry": telemetry, "artifacts": artifacts, "elicit_skipped": elicit_entry,
        "boundary_pointers": boundary_pointers, "boundary_dispositions": dispositions,
        "boundary_undispositioned": undispositioned, "plan": plan, "lineage": lineage,
        "findings_by_stage": findings_by_stage, "rejected_candidates": rejected,
        "real_source_exports": real_source_exports, "size_by_class": size_by_class,
        "plan_unjustified": unjustified, "candidate_coverage": (patterns or {}).get("candidate_concern_coverage", {}),
        "evidenced_coverage": (patterns or {}).get("evidenced_concern_coverage", {}),
        "duplicate_groups": (lineage or {}).get("summary", {}).get("duplicate_groups", 0),
        "copies_suppressed": (lineage or {}).get("summary", {}).get("copies_suppressed", 0),
    }


def write_handoff(bundle, c):
    actions = []
    for owner, desc, cmd in NEXT_ACTIONS.get(c["current"], []):
        actions.append({"owner": owner, "action": desc, **({"command": cmd} if cmd else {})})
    if c["boundary_undispositioned"]:
        names = ", ".join(p["reference"] for p in c["boundary_undispositioned"][:5])
        actions.insert(0, {
            "owner": "human",
            "action": f"Disposition {len(c['boundary_undispositioned'])} boundary pointer(s) this "
                      f"target's own evidence names outside its scanned root ({names}"
                      f"{', ...' if len(c['boundary_undispositioned']) > 5 else ''}) — pull each in, "
                      "mark it out of scope, or defer it, with a reason. Hard gate before `shared`.",
            "command": "python scripts/state.py --bundle <bundle> disposition <id> "
                       "--status included|excluded|deferred --actor <who> --note <why>",
        })
    if c["unresolved_warnings"]:
        actions.insert(0, {"owner": "human",
                           "action": f"Review {len(c['unresolved_warnings'])} unresolved secret warning(s) "
                                     f"in manifest.json — hard gate before any further share",
                           "command": "python scripts/state.py --bundle <bundle> secret-disposition "
                                      "<export:line> --status resolved|accepted|non-secret --actor <who> "
                                      "--note <why>"})
    if c["plan_unjustified"]:
        actions.append({"owner": "human",
                        "action": f"Justify {len(c['plan_unjustified'])} planned source(s) whose "
                                  "source_class needs a stated reason before carding",
                        "command": "python scripts/state.py --bundle <bundle> justify <rel> --actor "
                                   "<who> --note <why>"})
    if c["elicit_skipped"]:
        actions.append({"owner": "human",
                        "action": "Elicitation was skipped (see state history). Downstream deltas "
                                  "measure evidence against nothing; decide whether a belated "
                                  "elicitation is still meaningful or the card must say so."})
    handoff = {
        "schema_version": "1.1",
        "produced_by": {"skill": "system-cartographer", "skill_version": skill_version()},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": c["target"],
        "current_state": c["current"],
        "pending_states": c["pending"],
        "actions": actions,
        "secret_warnings": c["warnings"],
        "secret_warnings_unresolved": c["unresolved_warnings"],
        "boundary_pointers": c["boundary_pointers"],
        "boundary_pointers_undispositioned": [p["id"] for p in c["boundary_undispositioned"]],
        "findings_by_stage": c["findings_by_stage"],
        "real_source_exports": c["real_source_exports"],
        "artifacts": c["artifacts"],
    }
    with open(os.path.join(bundle, "handoff.json"), "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2)
    return handoff


def write_readme(bundle, c, handoff):
    lines = []
    a = lines.append
    a(f"# Cartography bundle: {c['target']}")
    a("")
    a(f"State: **{c['current']}**"
      + (f" → next: {' → '.join(c['pending'])}" if c["pending"] else " (complete)"))
    a("")
    a("This bundle is a save state of a system-cartographer run — evidence, provenance, "
      "and process trace travel together so a different person or agent can continue it. "
      "`handoff.json` holds the machine-readable version of everything below; `report.html` "
      "is the same data as a visual dashboard, openable offline.")
    a("")
    a("## How many claims can actually be inspected without the original repo?")
    a("")
    total_findings = sum(c["findings_by_stage"].values()) if c["findings_by_stage"] else 0
    a(f"**{c['real_source_exports']}** exported file(s) are real source or configuration content "
      f"(not scan output, not a copy, not process residue) backing **{total_findings}** real "
      "finding(s) at structural stage or past it. That is the number this bundle actually earns — "
      "everything else in it is either candidate-stage (unconfirmed) or process trace.")
    a("")
    a("## Where it stands")
    a("")
    for h in c["state"].get("history", []):
        flag = " *(reopened)*" if h.get("reopened") else ""
        note = f" — {h['note']}" if h.get("note") else ""
        a(f"- `{h['state']}`{flag} by **{h['actor']}** at {h['at']}{note}")
    a("")
    if c["patterns"]:
        s = c["patterns"].get("summary", {})
        a("## Findings at a glance — candidate vs. actually evidenced")
        a("")
        a(f"{s.get('files_seen', '?')} files walked, **{s.get('files_candidate_classified', '?')} "
          f"candidates** (glob-matched a concern), **{s.get('files_with_evidence', '?')} "
          "structurally-or-better evidenced** — never the same number, and the gap between them "
          "is the honest measure of how much of this scan is confirmed versus merely plausible.")
        a("")
        if c["findings_by_stage"]:
            a("Findings by stage: " + ", ".join(
                f"{stage} ({n})" for stage, n in sorted(c["findings_by_stage"].items(),
                                                         key=lambda kv: -kv[1])) + ".")
            a("")
        a(f"Rejected candidates: **{len(c['rejected_candidates']) or s.get('rejected_candidates', 0)}** "
          "(named with a reason, e.g. a file that doesn't parse — never silently dropped).")
        a("")
        a(f"Duplicate suppression: **{c['duplicate_groups']}** duplicate group(s), "
          f"**{c['copies_suppressed']}** copy/copies folded into their canonical source instead of "
          "inflating counts independently.")
        cov = c["evidenced_coverage"]
        if cov:
            a("")
            a("Evidenced-concern coverage (real findings, not glob candidates): " + ", ".join(
                f"{k} ({v})" for k, v in sorted(cov.items(), key=lambda kv: -kv[1])) + ".")
        if c["size_by_class"]:
            a("")
            a("Exported bytes by source class: " + ", ".join(
                f"{k} ({v:,}B)" for k, v in sorted(c["size_by_class"].items(), key=lambda kv: -kv[1])) + ".")
        a("")
    if c["telemetry"]:
        g = _git_analysis(c["telemetry"])
        if g.get("commit_count"):
            a(f"History: {g['commit_count']} commit(s) spanning "
              f"{'–'.join(g.get('date_range', ['?', '?']))}, fix/revert subject ratio "
              f"{g.get('fix_or_revert_subject_ratio', '?')}. Read the trend in conversation — "
              "these are inputs, not a verdict.")
        else:
            a("History: no git history found for this target.")
        a("")
    if c["boundary_pointers"]:
        load_bearing = [p for p in c["boundary_pointers"] if p.get("exists") and p.get("relation") != "unresolved"]
        a("## Points beyond this map")
        a("")
        a(f"This target's own files reference {len(load_bearing)} real path(s) outside the scanned "
          "root — code, docs, or config the target depends on that this run never walked. Each is "
          "named here instead of silently dropped, because a card that omits a load-bearing pointer "
          "fails its own replication test.")
        a("")
        for p in sorted(load_bearing, key=lambda p: -len(p["referenced_from"]))[:20]:
            disp = c["boundary_dispositions"].get(p["id"])
            status = f"**{disp['status']}** — {disp['note']}" if disp else "*(undispositioned)*"
            peek = p.get("explore") or {}
            what = (f"{peek.get('entry_count', '?')} entries" if peek.get("kind") == "directory"
                    else peek.get("first_line") or f"{peek.get('bytes', '?')} bytes")
            what = what.rstrip(".")
            variants = p.get("reference_variants") or [p["reference"]]
            names = f"`{p['reference']}`" if len(variants) < 2 else \
                f"`{p['reference']}` (+{len(variants) - 1} equivalent spelling(s) folded in)"
            a(f"- {names} ({p['relation']}, referenced from "
              f"{', '.join(p['referenced_from'][:3])}{', ...' if len(p['referenced_from']) > 3 else ''}) "
              f"— {what}. {status}")
        if len(load_bearing) > 20:
            a(f"- *(+{len(load_bearing) - 20} more — see `boundary_pointers` in the exported patterns.json)*")
        a("")
    a("## Needs human review")
    a("")
    if c["unresolved_warnings"]:
        a(f"**{len(c['unresolved_warnings'])} secret warning(s)** from the export tripwire have no "
          "recorded disposition — review each before this bundle is shared further (locations in "
          "`manifest.json`). The tripwire is deliberately noisy; many hits are benign hashes, but a "
          "human decides that, not the script.")
    elif c["warnings"]:
        a(f"All {len(c['warnings'])} secret warning(s) have a recorded disposition "
          "(`secret-dispositions.json`).")
    else:
        a("No secret warnings.")
    if c["boundary_undispositioned"]:
        a("")
        a(f"**{len(c['boundary_undispositioned'])} boundary pointer(s) undispositioned** (see "
          "'Points beyond this map' above) — `state.py advance shared` refuses until each is "
          "included, excluded, or deferred with a reason.")
    if c["plan_unjustified"]:
        a("")
        a(f"**{len(c['plan_unjustified'])} planned source(s) need justification** — a "
          "source_class like generated/vendor/transcript/snapshot needs a stated reason it's "
          "acceptable replication evidence before `carded`.")
    if c["elicit_skipped"]:
        a("")
        a("**Elicitation was skipped** (reason in state history). Deltas downstream measure "
          "evidence against nothing; any card built from this bundle must say so.")
    a("")
    a("## Next actions")
    a("")
    for act in handoff["actions"]:
        cmd = f" — `{act['command']}`" if act.get("command") else ""
        a(f"- **{act['owner']}**: {act['action']}{cmd}")
    if not handoff["actions"]:
        a("- None — run complete.")
    a("")
    a("## What's inside")
    a("")
    for art in c["artifacts"]:
        cls = f" [{art['source_class']}]" if art.get("source_class") else ""
        a(f"- `{art['path']}` ({art['slot']}){cls} — from `{art['source']}`")
    a("")
    a(f"*Generated by system-cartographer {handoff['produced_by']['skill_version']} "
      f"at {handoff['generated_at']}. Regenerate with "
      "`python scripts/bundle_synopsis.py --bundle <dir>` after any change. See also `report.html`.*")
    with open(os.path.join(bundle, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _bar(label, value, total, color):
    pct = round(100 * value / total) if total else 0
    return (f'<div class="bar-row"><span class="bar-label">{html.escape(str(label))}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<span class="bar-value">{value}</span></div>')


STAGE_COLORS = {"candidate": "#6b7280", "structural": "#2563eb", "behavioral": "#7c3aed",
                "observed": "#059669", "confirmed": "#d97706"}
CLASS_COLORS = {"source": "#059669", "configuration": "#2563eb", "copy": "#9ca3af",
                "generated": "#d97706", "vendor": "#9ca3af", "cache": "#9ca3af",
                "unknown": "#6b7280"}


def write_report_html(bundle, c, handoff):
    total_findings = sum(c["findings_by_stage"].values()) if c["findings_by_stage"] else 0
    stage_bars = "".join(
        _bar(stage, c["findings_by_stage"].get(stage, 0), total_findings, STAGE_COLORS.get(stage, "#6b7280"))
        for stage in EVIDENCED_STAGES if c["findings_by_stage"].get(stage)
    )
    cov_total = max(c["candidate_coverage"].values(), default=0)
    coverage_rows = "".join(
        _bar(cid, c["evidenced_coverage"].get(cid, 0), cov_total, "#2563eb")
        for cid in sorted(c["candidate_coverage"], key=lambda k: -c["candidate_coverage"][k])
    )
    size_total = sum(c["size_by_class"].values()) or 1
    size_rows = "".join(
        _bar(cls, n, size_total, CLASS_COLORS.get(cls, "#6b7280"))
        for cls, n in sorted(c["size_by_class"].items(), key=lambda kv: -kv[1])
    )

    def esc(x):
        return html.escape(str(x))

    warn_rows = "".join(
        f'<li class="{"resolved" if w.split(" matches ")[0] not in [uw.split(" matches ")[0] for uw in c["unresolved_warnings"]] else "unresolved"}">{esc(w)}</li>'
        for w in c["warnings"][:100]
    ) or '<li class="none">none</li>'

    boundary_rows = "".join(
        f'<tr><td>{esc(p["reference"])}</td><td>{esc(p["relation"])}</td>'
        f'<td>{esc((c["boundary_dispositions"].get(p["id"]) or {}).get("status", "undispositioned"))}</td></tr>'
        for p in c["boundary_pointers"] if p.get("exists") and p.get("relation") != "unresolved"
    ) or '<tr><td colspan="3">none</td></tr>'

    html_doc = f"""<title>Cartography bundle: {esc(c['target'])}</title>
<meta charset="utf-8">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 -apple-system, Segoe UI, sans-serif; max-width: 900px; margin: 2rem auto;
          padding: 0 1.5rem; color: #1f2328; background: #fff; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #e6edf3; background: #0d1117; }}
    .card {{ background: #161b22 !important; border-color: #30363d !important; }}
    .bar-track {{ background: #21262d !important; }} table {{ border-color: #30363d !important; }}
    td, th {{ border-color: #30363d !important; }} }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; border-bottom: 1px solid #d0d7de;
       padding-bottom: .3rem; }}
  .headline {{ font-size: 1.1rem; padding: 1rem; border: 1px solid #d0d7de; border-radius: 8px;
               background: #f6f8fa; margin: 1rem 0; }}
  .card {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 1rem; margin: .75rem 0; background: #f6f8fa; }}
  .bar-row {{ display: flex; align-items: center; gap: .6rem; margin: .35rem 0; font-size: .9rem; }}
  .bar-label {{ width: 160px; flex-shrink: 0; text-align: right; opacity: .85; }}
  .bar-track {{ flex: 1; background: #eaeef2; border-radius: 4px; height: 14px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; }}
  .bar-value {{ width: 3rem; text-align: right; font-variant-numeric: tabular-nums; opacity: .85; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .85rem; }}
  td, th {{ border: 1px solid #d0d7de; padding: .3rem .5rem; text-align: left; }}
  ul.warnings {{ font-family: ui-monospace, monospace; font-size: .8rem; max-height: 240px; overflow: auto;
                 background: #f6f8fa; border-radius: 6px; padding: .75rem 1.5rem; }}
  li.unresolved {{ color: #b91c1c; }} li.resolved {{ color: #6b7280; text-decoration: line-through; }}
  li.none {{ opacity: .6; }}
  footer {{ margin-top: 3rem; font-size: .8rem; opacity: .6; }}
</style>
<h1>Cartography bundle: {esc(c['target'])}</h1>
<p>State: <strong>{esc(c['current'])}</strong>{' — next: ' + esc(' → '.join(c['pending'])) if c['pending'] else ' (complete)'}</p>

<div class="headline">
  <strong>{c['real_source_exports']}</strong> exported file(s) are real source or configuration
  content backing <strong>{total_findings}</strong> real finding(s) at structural stage or past it —
  the number of claims a receiving team can actually inspect without the original repository.
</div>

<h2>Findings by evidence stage</h2>
{stage_bars or '<p>No findings recorded.</p>'}

<h2>Evidenced-concern coverage (of candidate ceiling per concern)</h2>
{coverage_rows or '<p>No concerns scanned.</p>'}

<h2>Exported bytes by source class</h2>
{size_rows or '<p>No exports yet.</p>'}
<p style="font-size:.85rem;opacity:.75">source/configuration = real evidence; copy/generated/vendor/cache
= named, not counted as independent evidence (lineage.py).</p>

<h2>Boundary pointers</h2>
<table><tr><th>Reference</th><th>Relation</th><th>Disposition</th></tr>{boundary_rows}</table>

<h2>Secret warnings ({len(c['warnings'])} total, {len(c['unresolved_warnings'])} unresolved)</h2>
<ul class="warnings">{warn_rows}</ul>

<h2>Next actions</h2>
<ul>{"".join(f'<li><strong>{esc(a["owner"])}</strong>: {esc(a["action"])}'
             + (f' &mdash; <code>{esc(a["command"])}</code>' if a.get("command") else '') + '</li>'
             for a in handoff["actions"]) or '<li>None — run complete.</li>'}</ul>

<footer>Generated by system-cartographer {esc(handoff['produced_by']['skill_version'])} at
{esc(handoff['generated_at'])}. Static, self-contained, no network calls — open this file directly
from inside the bundle on any machine. See also README.md / handoff.json.</footer>
"""
    with open(os.path.join(bundle, "report.html"), "w", encoding="utf-8", newline="") as f:
        f.write(html_doc)


def main():
    ap = argparse.ArgumentParser(description="Generate bundle README.md + handoff.json + report.html")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--target-name", default=None)
    args = ap.parse_args()
    c = collect(args.bundle, args.target_name)
    handoff = write_handoff(args.bundle, c)
    write_readme(args.bundle, c, handoff)
    write_report_html(args.bundle, c, handoff)
    print(f"synopsis: README.md + handoff.json + report.html written — state {c['current']}, "
          f"{len(handoff['actions'])} action(s), {len(c['unresolved_warnings'])}/{len(c['warnings'])} "
          f"unresolved warning(s)")


if __name__ == "__main__":
    main()
