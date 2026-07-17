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
    python state.py --bundle ./bundle reopen exported --actor "bdo-agent" --note "unevidenced claim names second repo; rescan"
    python state.py --bundle ./bundle show

See references/save-states.md for what each state means, who produces it,
and why someone would deliberately stop there.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ORDER = ["initialized", "negotiated", "elicited", "exported", "shared", "reconciled", "carded", "delivered"]


def _path(bundle):
    return os.path.join(bundle, "state.json")


def _dispositions_path(bundle):
    return os.path.join(bundle, "boundary-dispositions.json")


def _load_dispositions(bundle):
    path = _dispositions_path(bundle)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
    if tgt_i > cur_i + 1:
        skipped = ORDER[cur_i + 1:tgt_i]
        if "elicited" in skipped and not (note and "skip" in note.lower()):
            sys.exit("refusing to silently skip 'elicited' — blind belief capture is "
                     "unrecoverable (save-states.md). Pass --note 'skipped(<reason>)' "
                     "to record the skip explicitly.")
        print(f"note: skipping {skipped} — recorded in history", file=sys.stderr)
    if target == "shared":
        missing = [f for f in ("README.md", "handoff.json")
                   if not os.path.exists(os.path.join(bundle, f))]
        if missing:
            sys.exit(f"cannot advance to shared: {', '.join(missing)} missing. A bundle "
                     "must carry its review surfaces before it travels — run "
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
    args = ap.parse_args()

    if args.cmd == "init":
        cmd_init(args.bundle, args.actor, args.note)
    elif args.cmd == "advance":
        cmd_advance(args.bundle, args.target, args.actor, args.note)
    elif args.cmd == "reopen":
        cmd_reopen(args.bundle, args.target, args.actor, args.note)
    elif args.cmd == "disposition":
        cmd_disposition(args.bundle, args.pointer_id, args.status, args.actor, args.note)
    else:
        cmd_show(args.bundle)


if __name__ == "__main__":
    main()
