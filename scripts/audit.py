#!/usr/bin/env python3
"""audit.py -- every claim about the target walks the same eleven stages.

    intake         the claim as it arrived, and who made it
    findings       what the scan or a person noticed that bears on it
    evidence       the findings that hold up, each EXTRACTED or INFERRED
    conflicts      where belief and evidence, or two pieces of evidence, disagree
    organization   where the claim is filed: its concern, asset kind or community
    refutation     an attempt to make the claim false, and how it came out
    judgement      the reasons, weighed, by a named actor
    verdict        one delta word: confirmed, drift, undocumented, unevidenced, aspiration
    qualification  what the verdict rests on, its limits, what would overturn it
    settle         the owner's disposition
    validation     a second claim record, by a different actor, walked through the same
                   stages; agreement validates the first, disagreement reopens it

A claim may come from the builder, from the scan, or from an agent analysing one unit of
the map (--source agent --unit <unit>; see analysis_packets.py).

    <run>/
      audit.json   the claims and every entry (source of truth)
      AUDIT.md     the view, regenerated on every write -- never hand-edit it

A stage is refused while the stage before it is empty. Absence is stated, never assumed:
findings, evidence and conflicts take --none with a reason. Recording into a stage that
later stages were already built on moves those later entries into the claim's history
and the claim walks them again.

    python audit.py init --run ./run --actor me
    python audit.py intake --run ./run --actor me --source builder --concern integrations \\
        --statement "It writes to JIRA and nothing else"
    python audit.py seed --run ./run --actor me --scan-dir ./run/scan
    python audit.py record c1 evidence --run ./run --actor me --ref scripts/sync.py --basis EXTRACTED
    python audit.py record c1 refutation --run ./run --actor me --text "A second write target exists" \\
        --check "searched every client call in the export" --outcome survived
    python audit.py validate c1 --run ./run --actor someone-else
    python audit.py status --run ./run
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

LOCK_WAIT_SECONDS = 30

STAGES = ["intake", "findings", "evidence", "conflicts", "organization", "refutation",
          "judgement", "verdict", "qualification", "settle", "validation"]
RECORDABLE = STAGES[1:-1]
VERDICTS = ["confirmed", "drift", "undocumented", "unevidenced", "aspiration"]
BASES = ["EXTRACTED", "INFERRED"]
OUTCOMES = ["survived", "defeated"]
DISPOSITIONS = ["accepted", "repair", "deferred", "dropped"]
SOURCES = ["builder", "scan", "agent", "validation"]
# The fields an entry must carry, by stage.
REQUIRED = {
    "findings": ["ref"], "evidence": ["ref", "basis"], "conflicts": ["text"], "organization": ["group"],
    "refutation": ["text", "check", "outcome"], "judgement": ["text"], "verdict": ["verdict"],
    "qualification": ["rests_on", "limits", "overturned_by"], "settle": ["disposition"],
}
MAY_BE_NONE = ("findings", "evidence", "conflicts")
ONE_PER_ROUND = ("verdict", "settle")
EVIDENCED = ("structural", "behavioral")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(run):
    return os.path.join(run, "audit.json")


def _load(run):
    if not os.path.exists(_path(run)):
        sys.exit(f"no audit.json at {_path(run)} -- run `audit.py init` first")
    with open(_path(run), encoding="utf-8") as f:
        return json.load(f)


def _save(run, audit):
    with open(_path(run), "w", encoding="utf-8", newline="\n") as f:
        json.dump(audit, f, indent=2)
        f.write("\n")
    _write_view(run, audit)


def _claim(audit, claim_id):
    for claim in audit["claims"]:
        if claim["id"] == claim_id:
            return claim
    sys.exit(f"no such claim: {claim_id}")


def _new_claim(audit, statement, concern, source, actor, validates=None, unit=None):
    claim = {
        "id": f"c{len(audit['claims']) + 1}", "statement": statement, "concern": concern, "source": source,
        "validates": validates, "unit": unit, "round": 1, "history": [],
        "stages": {stage: [] for stage in STAGES},
    }
    claim["stages"]["intake"].append({"actor": actor, "at": _now(), "text": statement})
    audit["claims"].append(claim)
    return claim


def claim_state(claim):
    """The first empty stage, or how the validation came out."""
    for stage in STAGES[:-1]:
        if not claim["stages"][stage]:
            return stage
    checks = claim["stages"]["validation"]
    if not checks:
        return "validation"
    return "validated" if checks[-1]["agrees"] else "contested"


def _reopen_after(claim, stage):
    """Move every entry in the stages after `stage` into history; the claim walks them again."""
    later = STAGES[STAGES.index(stage) + 1:]
    moved = {s: claim["stages"][s] for s in later if claim["stages"][s]}
    if not moved:
        return []
    claim["history"].append({"round": claim["round"], "reopened_by": stage, "at": _now(), "stages": moved})
    claim["round"] += 1
    for s in moved:
        claim["stages"][s] = []
    return sorted(moved, key=STAGES.index)


def _check_verdict(claim, verdict):
    if verdict != "confirmed":
        return
    if not any(e.get("basis") == "EXTRACTED" for e in claim["stages"]["evidence"]):
        sys.exit(f"cannot confirm {claim['id']}: no EXTRACTED evidence is recorded. "
                 "A claim resting on pattern matches alone is unevidenced, or needs evidence first.")
    defeated = [e for e in claim["stages"]["refutation"] if e["outcome"] == "defeated"]
    if defeated:
        sys.exit(f"cannot confirm {claim['id']}: a refutation defeated it ({defeated[-1]['text']}). "
                 "Record the verdict the evidence supports.")


def _record(audit, claim, stage, actor, fields, none=False):
    """Append one entry to a stage, holding every gate. Returns the stages it reopened."""
    previous = STAGES[STAGES.index(stage) - 1]
    if not claim["stages"][previous]:
        sys.exit(f"cannot record {stage} on {claim['id']}: {previous} is empty. "
                 f"Record {previous} first" + (", or state its absence with --none --text <why>."
                                               if previous in MAY_BE_NONE else "."))
    if none:
        if stage not in MAY_BE_NONE:
            sys.exit(f"--none is only for {', '.join(MAY_BE_NONE)}; {stage} must be recorded")
        if not fields.get("text"):
            sys.exit("--none needs --text saying where you looked and found nothing")
        entry = {"none": True, "text": fields["text"]}
    else:
        missing = [name for name in REQUIRED[stage] if not fields.get(name)]
        if missing:
            sys.exit(f"{stage} needs: {', '.join('--' + m.replace('_', '-') for m in missing)}")
        entry = {name: value for name, value in fields.items() if value}
    if stage in ONE_PER_ROUND and claim["stages"][stage]:
        sys.exit(f"{claim['id']} already has a {stage} this round. "
                 "Record the earlier stage that changed and the claim will walk forward again.")
    if stage == "verdict":
        _check_verdict(claim, entry["verdict"])
    reopened = _reopen_after(claim, stage)
    claim["stages"][stage].append({"actor": actor, "at": _now(), **entry})
    if stage == "verdict" and claim["validates"]:
        _report_validation(audit, claim, actor)
    return reopened


def _report_validation(audit, check, actor):
    """A validating claim reached its verdict: tell the claim it validates."""
    original = _claim(audit, check["validates"])
    theirs, ours = original["stages"]["verdict"][-1]["verdict"], check["stages"]["verdict"][-1]["verdict"]
    agrees = theirs == ours
    if not agrees:
        _reopen_after(original, "conflicts")
        original["stages"]["conflicts"].append({
            "actor": actor, "at": _now(),
            "text": f"validation {check['id']} returned {ours} against {theirs}",
        })
    original["stages"]["validation"].append({
        "actor": actor, "at": _now(), "by_claim": check["id"], "verdict": ours, "agrees": agrees,
    })


def _write_view(run, audit):
    lines = ["# Audit", "", "| Claim | Source | Concern | Round | Stands at | Verdict | Statement |",
             "|---|---|---|---|---|---|---|"]
    for claim in audit["claims"]:
        verdict = claim["stages"]["verdict"][-1]["verdict"] if claim["stages"]["verdict"] else ""
        name = claim["id"] + (f" (validates {claim['validates']})" if claim["validates"] else "") \
            + (f" on `{claim['unit']}`" if claim.get("unit") else "")
        lines.append(f"| {name} | {claim['source']} | {claim['concern']} | {claim['round']} | "
                     f"{claim_state(claim)} | {verdict} | {claim['statement']} |")
    open_conflicts = [(c["id"], e["text"]) for c in audit["claims"] for e in c["stages"]["conflicts"]
                      if not e.get("none") and not c["stages"]["settle"]]
    lines += ["", "## Conflicts not yet settled", ""]
    lines += [f"- {cid}: {text}" for cid, text in open_conflicts] or ["(none)"]
    lines += ["", "_Generated from audit.json by audit.py -- never hand-edit this file._", ""]
    with open(os.path.join(run, "AUDIT.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def cmd_init(run, actor):
    if os.path.exists(_path(run)):
        sys.exit(f"audit.json already exists at {run}")
    os.makedirs(run, exist_ok=True)
    _save(run, {"audit": {"run_dir": os.path.abspath(run), "actor": actor, "created_at": _now()}, "claims": []})
    print(f"initialized audit at {run}")


def cmd_intake(run, actor, statement, concern, source, unit=None):
    audit = _load(run)
    claim = _new_claim(audit, statement, concern, source, actor, unit=unit)
    _save(run, audit)
    print(f"{claim['id']}: intake recorded -- next: findings")


def cmd_seed(run, actor, scan_dir):
    """One claim per concern the scan found files for, with its findings and evidence attached."""
    audit = _load(run)
    made, unevidenced = [], []
    for name in sorted(os.listdir(scan_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(scan_dir, name), encoding="utf-8") as f:
            graph = json.load(f)
        if not isinstance(graph, dict) or not graph.get("nodes") or not graph.get("concern"):
            continue
        concern, findings = graph["concern"], graph.get("findings") or []
        strong = [f for f in findings if f.get("evidence_stage") in EVIDENCED]
        if not strong:
            # Nothing past a pattern match: there is no statement here a scan could support.
            unevidenced.append(f"{concern} ({len(graph['nodes'])} files)")
            continue
        files = sorted({f["file"] for f in strong})
        claim = _new_claim(audit, f"{len(files)} of {len(graph['nodes'])} files matched for {concern} "
                                  "carry structural or behavioral evidence", concern, "scan", actor)
        _record(audit, claim, "findings", actor, {"ref": f"scan/{name}", "text": f"{len(graph['nodes'])} files matched"})
        for rel in files:
            signal = next(f["signal"] for f in strong if f["file"] == rel)
            _record(audit, claim, "evidence", actor, {"ref": rel, "basis": "EXTRACTED", "text": signal})
        made.append(claim["id"])
    _save(run, audit)
    print(f"seeded {len(made)} claims from {scan_dir}: {', '.join(made)} -- next for each: conflicts")
    if unevidenced:
        print(f"no claim opened, pattern matches only: {', '.join(unevidenced)}")


def cmd_record(run, claim_id, stage, actor, fields, none):
    audit = _load(run)
    claim = _claim(audit, claim_id)
    reopened = _record(audit, claim, stage, actor, fields, none)
    _save(run, audit)
    print(f"{claim_id}: {stage} recorded -- stands at: {claim_state(claim)}")
    if reopened:
        print(f"reopened (round {claim['round']}): {', '.join(reopened)} moved to history")
    if stage == "verdict" and claim["validates"]:
        original = _claim(audit, claim["validates"])
        print(f"{original['id']}: {claim_state(original)}")


def cmd_validate(run, claim_id, actor):
    audit = _load(run)
    original = _claim(audit, claim_id)
    if not original["stages"]["settle"]:
        sys.exit(f"cannot validate {claim_id}: it is not settled (stands at {claim_state(original)})")
    judges = {e["actor"] for stage in ("judgement", "verdict") for e in original["stages"][stage]}
    if actor in judges:
        sys.exit(f"cannot validate {claim_id} as {actor}: {actor} judged it. Validation needs a different actor.")
    check = _new_claim(audit, original["statement"], original["concern"], "validation", actor,
                       validates=claim_id, unit=original.get("unit"))
    _save(run, audit)
    print(f"{check['id']}: opened to validate {claim_id} -- walk it from findings to verdict without "
          f"reading {claim_id}'s entries; its verdict is compared with {claim_id}'s")


def cmd_status(run):
    audit = _load(run)
    _write_view(run, audit)
    counts = {}
    for claim in audit["claims"]:
        state = claim_state(claim)
        counts[state] = counts.get(state, 0) + 1
        target = f" (validates {claim['validates']})" if claim["validates"] else ""
        print(f"{claim['id']}{target}  round {claim['round']}  stands at {state}  -- {claim['statement']}")
    print("\n" + ", ".join(f"{counts[s]} at {s}" for s in STAGES + ["validated", "contested"] if s in counts))


def main():
    ap = argparse.ArgumentParser(description="System Cartographer audit: each claim walks eleven stages")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("intake")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--statement", required=True)
    p.add_argument("--concern", required=True)
    p.add_argument("--source", choices=SOURCES[:3], default="builder",
                   help="who the claim came from: the builder's belief, the scan, or an analysing agent")
    p.add_argument("--unit", default=None,
                   help="the unit of the map the claim is about, from analysis_packets.py (code-12, actor-..., asset-...)")

    p = sub.add_parser("seed")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--scan-dir", required=True)

    p = sub.add_parser("record")
    p.add_argument("claim_id")
    p.add_argument("stage", choices=RECORDABLE)
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--text", default=None, help="the entry in words; for refutation, what would make the claim false")
    p.add_argument("--ref", default=None, help="findings, evidence: the file, finding or export it points at")
    p.add_argument("--basis", choices=BASES, default=None, help="evidence: backed by a check, or a pattern match")
    p.add_argument("--group", default=None, help="organization: the concern, asset kind or community it is filed under")
    p.add_argument("--check", default=None, help="refutation: what was done to test it")
    p.add_argument("--outcome", choices=OUTCOMES, default=None, help="refutation: did the claim survive")
    p.add_argument("--verdict", choices=VERDICTS, default=None)
    p.add_argument("--rests-on", default=None, help="qualification: the evidence the verdict stands on")
    p.add_argument("--limits", default=None, help="qualification: what was not looked at")
    p.add_argument("--overturned-by", default=None, help="qualification: what would change the verdict")
    p.add_argument("--disposition", choices=DISPOSITIONS, default=None, help="settle: the owner's call")
    p.add_argument("--none", action="store_true", help="findings, evidence, conflicts: looked, found nothing")

    p = sub.add_parser("validate")
    p.add_argument("claim_id")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)

    sub.add_parser("status").add_argument("--run", required=True)

    args = ap.parse_args()
    # Several agents record into one ledger; each command reads, changes and writes the
    # whole file, so one command holds the ledger at a time.
    os.makedirs(args.run, exist_ok=True)
    lock = os.path.join(args.run, "audit.lock")
    deadline = time.time() + LOCK_WAIT_SECONDS
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            if time.time() > deadline:
                sys.exit(f"the ledger is held by another command ({lock}); if none is running, delete that file")
            time.sleep(0.1)
    try:
        dispatch(args)
    finally:
        os.unlink(lock)


def dispatch(args):
    if args.cmd == "init":
        cmd_init(args.run, args.actor)
    elif args.cmd == "intake":
        cmd_intake(args.run, args.actor, args.statement, args.concern, args.source, args.unit)
    elif args.cmd == "seed":
        cmd_seed(args.run, args.actor, args.scan_dir)
    elif args.cmd == "record":
        fields = {name: getattr(args, name) for name in
                  ("text", "ref", "basis", "group", "check", "outcome", "verdict", "rests_on", "limits",
                   "overturned_by", "disposition")}
        cmd_record(args.run, args.claim_id, args.stage, args.actor, fields, args.none)
    elif args.cmd == "validate":
        cmd_validate(args.run, args.claim_id, args.actor)
    elif args.cmd == "status":
        cmd_status(args.run)


if __name__ == "__main__":
    main()
