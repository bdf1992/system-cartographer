#!/usr/bin/env python3
"""Plan what earns a place in the bundle, before anything gets copied.

cartographer_scan.py's findings answer "is this evidence real" (candidate /
structural / behavioral / observed / confirmed). This script is the next
question: given real evidence, *what actually ships*, and why. Historically
that decision was a hand-authored manifest.json — this is what made the
Graey run's bundle ship the scan's own JSON instead of the source files the
scan cited: nobody wrote the step that says "the finding at
agent/foo.md:12 needs foo.md itself in the bundle."

Only structural+ findings ever earn a plan entry — a bare candidate is never
auto-exported, by design (references/evidence-model.md). A source file that
supports N concerns is planned once and referenced by all N, never
duplicated. A copy (per lineage.json) is never planned directly — its
canonical is, and the copy is recorded as a lineage note on that one entry.

    python build_export_manifest.py --scan-dir ./run/scan \
        --profile handoff --out ./run/export-plan.json
    python build_export_manifest.py --scan-dir ./run/scan \
        --boundary-dispositions ./run/boundary-dispositions.json \
        --profile replication --out ./run/export-plan.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lineage import hash_file  # noqa: E402

EVIDENCED_STAGES = {"structural", "behavioral", "observed", "confirmed"}
NEEDS_JUSTIFICATION = {"generated", "vendor", "transcript", "runtime-state", "snapshot", "archive", "cache", "unknown"}
HANDOFF_PER_CONCERN_CAP = 10


def _produced_by():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"),
                   encoding="utf-8") as f:
            v = f.read().strip()
    except OSError:
        v = "unknown"
    return {"skill": "system-cartographer", "skill_version": v}


def load_scan(scan_dir):
    with open(os.path.join(scan_dir, "scan.json"), encoding="utf-8") as f:
        scan = json.load(f)
    lineage_path = os.path.join(scan_dir, "lineage.json")
    lineage_report = {}
    if os.path.isfile(lineage_path):
        with open(lineage_path, encoding="utf-8") as f:
            lineage_report = json.load(f)
    return scan, lineage_report


def canonical_map(lineage_report):
    """copy rel -> canonical rel, for every copy lineage.py found."""
    m = {}
    for edge in lineage_report.get("lineage_edges", []):
        m[edge["copy"]] = edge["canonical"]
    return m


def node_meta(scan, rel):
    """source_class for a given rel, read back from whichever concern graph saw it."""
    for cid, graph in scan.get("graphs", {}).items():
        for node in graph.get("nodes", []) or []:
            if node["id"] == rel:
                return node.get("source_class"), node.get("path")
    return None, None


def collect_sources(scan, lineage_report, profile):
    root = scan.get("target")
    copy_of = canonical_map(lineage_report)
    sources = {}  # rel -> {supports: [...], source_class, path}
    per_concern_count = {}

    for cid, graph in scan.get("graphs", {}).items():
        findings = graph.get("findings") or []
        by_file = {}
        for f in findings:
            if f["evidence_stage"] not in EVIDENCED_STAGES:
                continue
            by_file.setdefault(f["file"], []).append(f)
        # rank files with more/stronger findings first so a handoff's cap
        # keeps the most-evidenced files, not an arbitrary alphabetical slice
        stage_rank = {"confirmed": 4, "observed": 3, "behavioral": 2, "structural": 1}
        ranked = sorted(by_file.items(), key=lambda kv: -max(stage_rank.get(f["evidence_stage"], 0) for f in kv[1]))
        for rel, file_findings in ranked:
            canonical_rel = copy_of.get(rel, rel)
            if profile == "handoff" and per_concern_count.get(cid, 0) >= HANDOFF_PER_CONCERN_CAP and canonical_rel not in sources:
                continue
            source_class, path = node_meta(scan, canonical_rel)
            entry = sources.setdefault(canonical_rel, {
                "source": os.path.join(root, canonical_rel) if path is None else path,
                "source_class": source_class, "supports": [], "copies": [],
            })
            entry["supports"].append({
                "concern": cid,
                "evidence_stage": max((f["evidence_stage"] for f in file_findings), key=lambda s: stage_rank.get(s, 0)),
                "finding_count": len(file_findings),
                "signal": file_findings[0].get("signal", ""),
            })
            if canonical_rel == rel:
                per_concern_count[cid] = per_concern_count.get(cid, 0) + 1

    for copy_rel, canon_rel in copy_of.items():
        if canon_rel in sources:
            sources[canon_rel]["copies"].append(copy_rel)

    return sources


PROCESS_TRACE_FILES = ["scan.json", "patterns.json", "lineage.json"]


def process_trace_entries(scan_dir):
    """scan.json/patterns.json/lineage.json are the run's own instrument
    output, not source evidence a card cites — they belong under
    exports/process/ (SKILL.md's documented process trace), never mixed
    into a concern's evidence slot, and always carried regardless of
    profile: state.py's boundary/secret gates read patterns.json back out
    of exports/, and a bundle missing it can't be gated at all."""
    entries = []
    for name in PROCESS_TRACE_FILES:
        path = os.path.join(scan_dir, name)
        if not os.path.isfile(path):
            continue
        entries.append({
            "source": path, "rel": name, "slot": "process",
            "supports": [{"concern": "process", "evidence_stage": "observed",
                          "finding_count": 1, "signal": "the scan's own instrument output"}],
            "whole_file_or_excerpt": "whole",
            "reason": "process trace — required for state.py's own gates to read back "
                      "boundary pointers / findings summaries",
            "source_class": "generated", "needs_justification": False,
            "copies_folded_in": [], "expected_sha256": hash_file(path, 32 * 1024 * 1024),
            "profile": ["handoff", "replication"], "export_policy": "required",
        })
    run_dir = os.path.dirname(os.path.abspath(scan_dir))
    env_path = os.path.join(run_dir, "environment.json")
    if os.path.isfile(env_path):
        entries.append({
            "source": env_path, "rel": "environment.json", "slot": "process",
            "supports": [{"concern": "process", "evidence_stage": "observed",
                          "finding_count": 1, "signal": "the negotiated environment descriptor"}],
            "whole_file_or_excerpt": "whole", "reason": "process trace — the observation contract",
            "source_class": "generated", "needs_justification": False,
            "copies_folded_in": [], "expected_sha256": hash_file(env_path, 32 * 1024 * 1024),
            "profile": ["handoff", "replication"], "export_policy": "required",
        })
    return entries


def build_plan(scan_dir, profile, boundary_dispositions_path):
    scan, lineage_report = load_scan(scan_dir)
    sources = collect_sources(scan, lineage_report, profile)

    entries = list(process_trace_entries(scan_dir))
    for rel, info in sorted(sources.items()):
        h = hash_file(info["source"], 8 * 1024 * 1024) if os.path.isfile(info["source"]) else None
        concerns = sorted({s["concern"] for s in info["supports"]})
        entries.append({
            "source": info["source"], "rel": rel, "slot": concerns[0] if len(concerns) == 1 else "cross-cutting",
            "supports": info["supports"],
            "whole_file_or_excerpt": "whole",
            "reason": "cited as evidence by " + ", ".join(concerns),
            "source_class": info["source_class"] or "unknown",
            "needs_justification": (info["source_class"] or "unknown") in NEEDS_JUSTIFICATION,
            "copies_folded_in": info["copies"],
            "expected_sha256": h,
            "profile": ["handoff", "replication"] if profile == "handoff" else ["replication"],
            "export_policy": "required",
        })

    boundary_entries = []
    if boundary_dispositions_path and os.path.isfile(boundary_dispositions_path):
        with open(boundary_dispositions_path, encoding="utf-8") as f:
            dispositions = json.load(f)
        patterns_path = os.path.join(scan_dir, "patterns.json")
        pointers = []
        if os.path.isfile(patterns_path):
            with open(patterns_path, encoding="utf-8") as f:
                pointers = json.load(f).get("boundary_pointers", [])
        by_id = {p["id"]: p for p in pointers}
        for pid, disp in dispositions.items():
            if disp.get("status") != "included":
                continue
            pointer = by_id.get(pid)
            if not pointer or not pointer.get("resolved_path") or not os.path.isfile(pointer["resolved_path"]):
                continue
            h = hash_file(pointer["resolved_path"], 8 * 1024 * 1024)
            boundary_entries.append({
                "source": pointer["resolved_path"], "rel": None, "slot": "boundary",
                "supports": [{"concern": "boundary", "evidence_stage": "confirmed",
                              "finding_count": 1, "signal": f"disposed included: {disp.get('note', '')}"}],
                "whole_file_or_excerpt": "whole",
                "reason": f"boundary pointer {pid} disposed included — {disp.get('note', '')}",
                "source_class": "unknown", "needs_justification": False,
                "copies_folded_in": [], "expected_sha256": h,
                "profile": ["replication"], "export_policy": "required",
            })

    all_entries = entries + boundary_entries
    return {
        "schema_version": "1.0",
        "profile": profile,
        "scan_dir": os.path.abspath(scan_dir),
        "entries": all_entries,
        "summary": {
            "process_trace_planned": sum(1 for e in entries if e["slot"] == "process"),
            "sources_planned": sum(1 for e in entries if e["slot"] != "process"),
            "boundary_sources_planned": len(boundary_entries),
            "needing_justification": sum(1 for e in entries if e["needs_justification"]),
            "copies_folded_in": sum(len(e["copies_folded_in"]) for e in entries),
        },
        "produced_by": _produced_by(),
    }


def main():
    ap = argparse.ArgumentParser(description="Plan the evidence a bundle actually needs to ship")
    ap.add_argument("--scan-dir", required=True, help="Directory containing scan.json (+ optional lineage.json)")
    ap.add_argument("--profile", required=True, choices=["handoff", "replication"])
    ap.add_argument("--boundary-dispositions", help="boundary-dispositions.json from state.py, for included pointers")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    plan = build_plan(args.scan_dir, args.profile, args.boundary_dispositions)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    print(f"plan: {args.out} — {plan['summary']['sources_planned']} source(s), "
          f"{plan['summary']['boundary_sources_planned']} boundary source(s), "
          f"{plan['summary']['needing_justification']} needing justification")


if __name__ == "__main__":
    main()
