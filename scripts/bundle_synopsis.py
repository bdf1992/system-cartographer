#!/usr/bin/env python3
"""Generate the bundle's two review surfaces: README.md and handoff.json.

A bundle full of graph JSON is complete but not usable: the receiving agent
has to spelunk, and the reviewing human has nothing to read. This script
reads what the bundle already contains (state.json, manifest.json, any
exported scan/patterns/telemetry) and writes:

  README.md     — the human surface: what this is, where it stands, what was
                  found, what needs review, what happens next.
  handoff.json  — the agent surface: current/pending states, typed actionable
                  items (owner: human|agent, with commands where mechanical),
                  unresolved warnings, artifact index.

Run it whenever the bundle's contents change — state.py refuses to advance a
bundle to `shared` unless both surfaces exist, so generating them is part of
the export path, not an optional nicety.

    python bundle_synopsis.py --bundle <dir> [--target-name <name>]
"""
import argparse
import json
import os
from datetime import datetime, timezone

STATE_ORDER = ["initialized", "negotiated", "elicited", "exported", "shared",
               "reconciled", "carded", "delivered"]

NEXT_ACTIONS = {
    "negotiated": [("agent", "Elicit the builder's blind beliefs across the twelve concerns "
                             "(structured questions; record skips as skips)", None)],
    "elicited":   [("agent", "Run the scan and build exports",
                    "python scripts/cartographer_scan.py --target <root> --out-dir <run>/scan")],
    "exported":   [("human", "Review every secret warning listed below before this bundle "
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
    patterns = load_json(find_export(bundle, "patterns.json") or "")
    telemetry = load_json(find_export(bundle, "telemetry.json", "session-quality.json") or "")
    scan = load_json(find_export(bundle, "scan.json") or "")
    dispositions = load_json(os.path.join(bundle, "boundary-dispositions.json")) or {}

    current = state.get("current", "initialized")
    pending = STATE_ORDER[STATE_ORDER.index(current) + 1:] if current in STATE_ORDER else []
    warnings = [w for e in manifest.get("entries", [])
                for w in (e.get("secret_warnings") or [])]
    elicit_entry = next((h for h in state.get("history", [])
                         if "skip" in (h.get("note") or "").lower()
                         and "elicit" in (h.get("note") or "").lower()), None)
    if not target_name:
        target_name = (scan or {}).get("target") or "unknown target"

    artifacts = []
    for e in manifest.get("entries", []):
        if e.get("export"):
            artifacts.append({"path": e["export"], "slot": e.get("slot"),
                              "source": e.get("source"), "sha256": e.get("sha256")})

    boundary_pointers = (patterns or {}).get("boundary_pointers", [])
    load_bearing = [p for p in boundary_pointers if p.get("exists") and p.get("relation") != "unresolved"]
    undispositioned = [p for p in load_bearing if p["id"] not in dispositions and not p.get("disposition")]

    return {
        "target": target_name, "state": state, "current": current, "pending": pending,
        "warnings": warnings, "patterns": patterns, "telemetry": telemetry,
        "artifacts": artifacts, "elicit_skipped": elicit_entry,
        "boundary_pointers": boundary_pointers, "boundary_dispositions": dispositions,
        "boundary_undispositioned": undispositioned,
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
    if c["warnings"]:
        actions.insert(0, {"owner": "human",
                           "action": f"Review {len(c['warnings'])} unresolved secret warning(s) "
                                     f"in manifest.json — hard gate before any further share"})
    if c["elicit_skipped"]:
        actions.append({"owner": "human",
                        "action": "Elicitation was skipped (see state history). Downstream deltas "
                                  "measure evidence against nothing; decide whether a belated "
                                  "elicitation is still meaningful or the card must say so."})
    handoff = {
        "schema_version": "1.0",
        "produced_by": {"skill": "system-cartographer", "skill_version": skill_version()},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": c["target"],
        "current_state": c["current"],
        "pending_states": c["pending"],
        "actions": actions,
        "secret_warnings": c["warnings"],
        "boundary_pointers": c["boundary_pointers"],
        "boundary_pointers_undispositioned": [p["id"] for p in c["boundary_undispositioned"]],
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
      "`handoff.json` holds the machine-readable version of everything below.")
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
        a("## Findings at a glance")
        a("")
        a(f"{s.get('files_seen', '?')} files walked, {s.get('files_with_evidence', '?')} "
          f"with evidence, {s.get('edges', '?')} edges across "
          f"{s.get('concerns_selected', '?')} concerns.")
        cov = c["patterns"].get("evidenced_concern_coverage", {})
        if cov:
            a("")
            a("Evidenced concerns: " + ", ".join(
                f"{k} ({v})" for k, v in sorted(cov.items(), key=lambda kv: -kv[1])) + ".")
        a("")
    if c["telemetry"]:
        g = c["telemetry"].get("git_analysis", {})
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
            a(f"- `{p['reference']}` ({p['relation']}, referenced from "
              f"{', '.join(p['referenced_from'][:3])}{', ...' if len(p['referenced_from']) > 3 else ''}) "
              f"— {what}. {status}")
        if len(load_bearing) > 20:
            a(f"- *(+{len(load_bearing) - 20} more — see `boundary_pointers` in the exported patterns.json)*")
        a("")
    a("## Needs human review")
    a("")
    if c["warnings"]:
        a(f"**{len(c['warnings'])} secret warning(s)** from the export tripwire — review each "
          "before this bundle is shared further (locations in `manifest.json`). The tripwire "
          "is deliberately noisy; many hits are benign hashes, but a human decides that, "
          "not the script.")
    else:
        a("No unresolved secret warnings.")
    if c["boundary_undispositioned"]:
        a("")
        a(f"**{len(c['boundary_undispositioned'])} boundary pointer(s) undispositioned** (see "
          "'Points beyond this map' above) — `state.py advance shared` refuses until each is "
          "included, excluded, or deferred with a reason.")
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
        a(f"- `{art['path']}` ({art['slot']}) — from `{art['source']}`")
    a("")
    a(f"*Generated by system-cartographer {handoff['produced_by']['skill_version']} "
      f"at {handoff['generated_at']}. Regenerate with "
      "`python scripts/bundle_synopsis.py --bundle <dir>` after any change.*")
    with open(os.path.join(bundle, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Generate bundle README.md + handoff.json")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--target-name", default=None)
    args = ap.parse_args()
    c = collect(args.bundle, args.target_name)
    handoff = write_handoff(args.bundle, c)
    write_readme(args.bundle, c, handoff)
    print(f"synopsis: README.md + handoff.json written — state {c['current']}, "
          f"{len(handoff['actions'])} action(s), {len(c['warnings'])} warning(s)")


if __name__ == "__main__":
    main()
