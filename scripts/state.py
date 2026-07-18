#!/usr/bin/env python3
"""Save-state manager for a cartographer bundle.

The bundle + state.json is the whole save state: share it at any boundary
and a different person/agent continues from exactly here. Transitions are
recorded with actor, timestamp, and note — the state history is part of
the process trace (who carried which phase, and how many cycles it took,
are findings about the system, not logistics).

    python state.py --bundle ./bundle init --actor "qa-manager"
    python state.py --bundle ./bundle advance negotiated --actor "qa-manager" --note "host and evidence roots confirmed"
    python state.py --bundle ./bundle advance elicited --actor "qa-manager" --note "12 concerns asked, 2 skipped"
    python state.py --bundle ./bundle advance exported --actor "qa-manager"
    python state.py --bundle ./bundle advance shared --actor "qa-manager" --note "gh:org/qa-agent-cartography (private)"
    python state.py --bundle ./bundle reopen exported --actor "qa-manager" --note "unevidenced claim names second repo; rescan"
    python state.py --bundle ./bundle show

See references/save-states.md for what each state means, who produces it,
and why someone would deliberately stop there.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ORDER = ["initialized", "negotiated", "elicited", "exported", "shared", "reconciled", "carded", "delivered"]


def _path(bundle):
    return os.path.join(bundle, "state.json")


def _dispositions_path(bundle):
    return os.path.join(bundle, "boundary-dispositions.json")


def _secret_dispositions_path(bundle):
    return os.path.join(bundle, "secret-dispositions.json")


def _justifications_path(bundle):
    return os.path.join(bundle, "justifications.json")


def _load_json_or(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_dispositions(bundle):
    return _load_json_or(_dispositions_path(bundle), {})


def _find_patterns(bundle):
    """patterns.json travels inside exports/<slot>/ — same layout export_bundle.py
    uses for every other artifact. Returns None if this bundle never exported a
    scan (nothing to gate on), not an error."""
    exports = os.path.join(bundle, "exports")
    if not os.path.isdir(exports):
        return None
    for root, _, files in os.walk(exports):
        if "patterns.json" in files:
            with open(os.path.join(root, "patterns.json"), encoding="utf-8") as f:
                return json.load(f)
    return None


def _find_manifest(bundle):
    path = os.path.join(bundle, "manifest.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_scan_caches(bundle):
    """A bundle that ships scanner exhaust (scan-cache.json, or a followed
    sub-scan of a boundary that was never actually disposed included) is
    shipping process residue as if it were evidence."""
    hits = []
    for root, dirs, files in os.walk(bundle):
        for name in files:
            if name == "scan-cache.json":
                hits.append(os.path.relpath(os.path.join(root, name), bundle))
    return hits


def cmd_secret_disposition(bundle, key, status, actor, note):
    key = key.strip()
    if status not in ("resolved", "accepted", "non-secret"):
        sys.exit("--status must be one of: resolved, accepted, non-secret")
    if not note:
        sys.exit("secret-disposition requires --note: say what was checked and why it's safe to ship")
    dispositions = _load_json_or(_secret_dispositions_path(bundle), {})
    dispositions[key] = {"status": status, "actor": actor, "note": note,
                         "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with open(_secret_dispositions_path(bundle), "w", encoding="utf-8") as f:
        json.dump(dispositions, f, indent=2)
    print(f"{key} -> {status}")


def _undispositioned_secret_warnings(bundle):
    manifest = _find_manifest(bundle)
    if not manifest:
        return []
    dispositions = _load_json_or(_secret_dispositions_path(bundle), {})
    missing = []
    for entry in manifest.get("entries", []):
        for warning in entry.get("secret_warnings", []):
            key = warning.split(" matches ")[0]  # "export:line" prefix — stable per-hit key
            if key not in dispositions:
                missing.append(warning)
    return missing


def cmd_justify(bundle, rel, actor, note):
    if not note:
        sys.exit("justify requires --note: why this source_class is acceptable evidence")
    justifications = _load_json_or(_justifications_path(bundle), {})
    justifications[rel] = {"actor": actor, "note": note,
                           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with open(_justifications_path(bundle), "w", encoding="utf-8") as f:
        json.dump(justifications, f, indent=2)
    print(f"{rel} -> justified")


def _find_export_plan(bundle):
    path = os.path.join(bundle, "export-plan.json")
    return _load_json_or(path, None)


def _unjustified_plan_entries(bundle):
    plan = _find_export_plan(bundle)
    if not plan:
        return None  # no plan at all is a separate, harder failure — checked directly
    justifications = _load_json_or(_justifications_path(bundle), {})
    return [e["rel"] for e in plan.get("entries", [])
            if e.get("needs_justification") and e.get("rel") not in justifications]


def _verify_export_integrity(bundle):
    """Re-hashes every export actually on disk right now and compares against
    the hash export_bundle.py recorded at write time — the mechanical form of
    'exported hashes match', not a claim taken on faith."""
    manifest = _find_manifest(bundle)
    if not manifest:
        return ["no manifest.json to verify"]
    problems = []
    for entry in manifest.get("entries", []):
        export = entry.get("export")
        if not export:
            continue
        full = os.path.join(bundle, *export.split("/"))
        if not os.path.isfile(full):
            problems.append(f"{export}: missing on disk")
            continue
        with open(full, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        expected = entry.get("export_sha256")
        if expected and actual != expected:
            problems.append(f"{export}: hash mismatch (recorded {expected[:8]}, actual {actual[:8]})")
    return problems


def _undispositioned_boundary_pointers(bundle):
    """Load-bearing pointers only: resolved, real, out-of-root (never a bare
    unresolved guess) with no recorded disposition. This is the check that
    keeps a bundle from shipping while it silently omits code/docs its own
    target root points at — see references/boundary-protocol.md."""
    patterns = _find_patterns(bundle)
    if not patterns:
        return []
    dispositions = _load_dispositions(bundle)
    missing = []
    for p in patterns.get("boundary_pointers", []):
        if not p.get("exists") or p.get("relation") == "unresolved":
            continue
        if p["id"] not in dispositions and not p.get("disposition"):
            missing.append(p)
    return missing


def cmd_disposition(bundle, pointer_id, status, actor, note):
    pointer_id = pointer_id.strip()
    if status not in ("included", "excluded", "deferred"):
        sys.exit("--status must be one of: included, excluded, deferred")
    if not note:
        sys.exit("disposition requires --note: say why (pulled into scope / genuinely "
                  "out of scope / deferred to a later cycle) — see boundary-protocol.md")
    dispositions = _load_dispositions(bundle)
    dispositions[pointer_id] = {
        "status": status, "actor": actor, "note": note,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(_dispositions_path(bundle), "w", encoding="utf-8") as f:
        json.dump(dispositions, f, indent=2)
    print(f"{pointer_id} -> {status}")


def _load(bundle):
    with open(_path(bundle), encoding="utf-8") as f:
        return json.load(f)


def _save(bundle, state):
    with open(_path(bundle), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _skill_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def _entry(name, actor, note):
    return {
        "state": name,
        "actor": actor,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note or "",
        "skill_version": _skill_version(),
    }


def cmd_init(bundle, actor, note):
    os.makedirs(bundle, exist_ok=True)
    if os.path.exists(_path(bundle)):
        sys.exit("state.json already exists — use show/advance/reopen")
    state = {"current": "initialized", "history": [_entry("initialized", actor, note)]}
    _save(bundle, state)
    print("initialized")


def cmd_advance(bundle, target, actor, note):
    state = _load(bundle)
    cur_i, tgt_i = ORDER.index(state["current"]), ORDER.index(target)
    if tgt_i <= cur_i:
        sys.exit(f"cannot advance {state['current']} -> {target}; use reopen to go back "
                 f"(reason required)")
    skipped = ORDER[cur_i + 1:tgt_i]
    if skipped:
        if "elicited" in skipped and not (note and "skip" in note.lower()):
            sys.exit("refusing to silently skip 'elicited' — blind belief capture is "
                     "unrecoverable (save-states.md). Pass --note 'skipped(<reason>)' "
                     "to record the skip explicitly.")
        print(f"note: skipping {skipped} — recorded in history", file=sys.stderr)
    # A gate belongs to its named state whether that state is the literal
    # target or one jumped over — otherwise 'exported -> carded' in one call
    # silently bypasses every check 'shared' would have enforced, which is
    # worse than not having the gate at all (save-states.md's skip law,
    # extended past just 'elicited' now that later states carry hard gates).
    checkpoints = set(skipped) | {target}
    if "exported" in checkpoints:
        manifest = _find_manifest(bundle)
        if not manifest:
            sys.exit("cannot advance to exported: no manifest.json — run export_bundle.py first")
        if not manifest.get("profile"):
            sys.exit("cannot advance to exported: manifest.json carries no profile — build an "
                     "export-plan.json with build_export_manifest.py and export from --plan, "
                     "not a hand-authored --manifest, so the bundle knows handoff vs replication.")
        if not _find_export_plan(bundle):
            sys.exit("cannot advance to exported: no export-plan.json in the bundle — the evidence "
                     "plan travels with the bundle, it isn't a build-time-only artifact.")
        integrity_problems = _verify_export_integrity(bundle)
        if integrity_problems:
            sys.exit("cannot advance to exported: " + "; ".join(integrity_problems[:5]))
        caches = _find_scan_caches(bundle)
        if caches:
            sys.exit(f"cannot advance to exported: scan-cache.json shipped in the bundle "
                     f"({', '.join(caches[:3])}) — scanner exhaust, not evidence; delete before export.")
    if "shared" in checkpoints:
        missing = [f for f in ("README.md", "handoff.json", "onboarding-card.html")
                   if not os.path.exists(os.path.join(bundle, f))]
        if missing:
            sys.exit(f"cannot advance to shared: {', '.join(missing)} missing. A bundle "
                     "must carry its review surfaces AND its product surface (the onboarding "
                     "card) before it travels — run "
                     "`python scripts/bundle_synopsis.py --bundle " + bundle + "` first.")
        undispositioned = _undispositioned_boundary_pointers(bundle)
        if undispositioned:
            names = ", ".join(p["reference"] for p in undispositioned[:5])
            more = f" (+{len(undispositioned) - 5} more)" if len(undispositioned) > 5 else ""
            sys.exit(
                f"cannot advance to shared: {len(undispositioned)} boundary pointer(s) have no "
                f"disposition — {names}{more}. This target's own evidence points outside the "
                "scanned root; an export that ships without saying what happened to those pointers "
                "doesn't meet the replication test (slot-protocol.md). For each: "
                "`python scripts/state.py --bundle " + bundle + " disposition <id> "
                "--status included|excluded|deferred --actor <who> --note <why>`."
            )
        disp_map = _load_dispositions(bundle)
        patterns = _find_patterns(bundle) or {}
        pointers_by_id = {p["id"]: p for p in patterns.get("boundary_pointers", [])}
        for pid, disp in disp_map.items():
            if disp.get("status") == "included":
                pointer = pointers_by_id.get(pid)
                followed_ok = bool(pointer and (pointer.get("followed") or {}).get("status") == "scanned")
                exported_ok = pointer is not None and any(
                    e.get("source") == pointer.get("resolved_path")
                    for e in (_find_manifest(bundle) or {}).get("entries", [])
                )
                if not followed_ok and not exported_ok:
                    sys.exit(f"cannot advance to shared: boundary pointer {pid} is disposed 'included' "
                             "but has no exported evidence and was never followed — an 'included' label "
                             "alone doesn't ground it (boundary-protocol.md).")
        unresolved_secrets = _undispositioned_secret_warnings(bundle)
        if unresolved_secrets:
            sys.exit(f"cannot advance to shared: {len(unresolved_secrets)} secret warning(s) have no "
                     f"disposition, e.g. {unresolved_secrets[0]!r} — `python scripts/state.py --bundle " +
                     bundle + " secret-disposition <export:line> --status resolved|accepted|non-secret "
                     "--actor <who> --note <why>`.")
    if "carded" in checkpoints:
        plan = _find_export_plan(bundle)
        if not plan:
            sys.exit("cannot advance to carded: no export-plan.json — every card prior needs a named "
                     "evidence plan behind it, not just a card author's say-so.")
        unjustified = _unjustified_plan_entries(bundle)
        if unjustified:
            sys.exit(f"cannot advance to carded: {len(unjustified)} planned source(s) carry a "
                     f"source_class needing justification with none recorded, e.g. {unjustified[0]!r} — "
                     "`python scripts/state.py --bundle " + bundle + " justify <rel> --actor <who> "
                     "--note <why this is acceptable evidence>`.")
    if "delivered" in checkpoints:
        integrity_problems = _verify_export_integrity(bundle)
        if integrity_problems:
            sys.exit("cannot advance to delivered: " + "; ".join(integrity_problems[:5]))
        if not note:
            sys.exit("delivered requires --note naming the destination and authority "
                     "(e.g. 'gh:org/repo (private), pushed by X') — a delivery with no recorded "
                     "destination isn't a delivery, it's a guess about where it went.")
    state["current"] = target
    state["history"].append(_entry(target, actor, note))
    _save(bundle, state)
    print(f"-> {target}")


def cmd_reopen(bundle, target, actor, note):
    state = _load(bundle)
    if not note:
        sys.exit("reopen requires --note: cycles must record why (save-states.md)")
    if ORDER.index(target) >= ORDER.index(state["current"]):
        sys.exit(f"reopen goes backward; current is {state['current']}")
    state["current"] = target
    state["history"].append({**_entry(target, actor, note), "reopened": True})
    _save(bundle, state)
    print(f"reopened -> {target}")


def cmd_show(bundle):
    state = _load(bundle)
    print(json.dumps(state, indent=2))
    cur = ORDER.index(state["current"])
    pending = ORDER[cur + 1:]
    print(f"\ncurrent: {state['current']}  |  pending: {' -> '.join(pending) or 'none'}",
          file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Bundle save-state manager")
    ap.add_argument("--bundle", required=True, help="Bundle directory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "advance", "reopen"):
        p = sub.add_parser(name)
        if name != "init":
            p.add_argument("target", choices=ORDER[1:])
        p.add_argument("--actor", required=(name != "show"), help="Who is doing this")
        p.add_argument("--note", default=None)
    sub.add_parser("show")
    p = sub.add_parser("disposition", help="Record what happened to a boundary pointer")
    p.add_argument("pointer_id")
    p.add_argument("--status", required=True, choices=["included", "excluded", "deferred"])
    p.add_argument("--actor", required=True)
    p.add_argument("--note", required=True)
    p = sub.add_parser("secret-disposition", help="Record what happened to a flagged secret warning")
    p.add_argument("key", help="The 'export:line' prefix from manifest.json's secret_warnings")
    p.add_argument("--status", required=True, choices=["resolved", "accepted", "non-secret"])
    p.add_argument("--actor", required=True)
    p.add_argument("--note", required=True)
    p = sub.add_parser("justify", help="Record why a needs_justification source_class is acceptable evidence")
    p.add_argument("rel")
    p.add_argument("--actor", required=True)
    p.add_argument("--note", required=True)
    args = ap.parse_args()

    if args.cmd == "init":
        cmd_init(args.bundle, args.actor, args.note)
    elif args.cmd == "advance":
        cmd_advance(args.bundle, args.target, args.actor, args.note)
    elif args.cmd == "reopen":
        cmd_reopen(args.bundle, args.target, args.actor, args.note)
    elif args.cmd == "disposition":
        cmd_disposition(args.bundle, args.pointer_id, args.status, args.actor, args.note)
    elif args.cmd == "secret-disposition":
        cmd_secret_disposition(args.bundle, args.key, args.status, args.actor, args.note)
    elif args.cmd == "justify":
        cmd_justify(args.bundle, args.rel, args.actor, args.note)
    else:
        cmd_show(args.bundle)


if __name__ == "__main__":
    main()
