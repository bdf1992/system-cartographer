#!/usr/bin/env python3
"""The first-touch run ledger: a work contract before the first scan.

Every other script in this skill answers "what did the run observe" or "what
state is the bundle in." Nothing answered "what does the agent owe right
now, and what would prove it done" until first touch — an agent had to read
SKILL.md prose to reconstruct that. This script makes it a standing,
machine-checked ledger instead:

    <run>/
      work.json    typed source of truth (tasks, statuses, blocked_by, evidence)
      TODO.md      human-readable view, ALWAYS regenerated from work.json — never
                   hand-edit it, the way a generated file is never hand-edited
      state.json   the existing save-state ladder (scripts/state.py), untouched

`init` creates the seed task graph mirroring SKILL.md's own phases
(negotiate -> elicit -> scan -> join -> reconcile -> cycle -> assemble ->
share) and does not read the target's contents — only a directory-existence
stat, the same read-only root check environment_probe.py already performs.
Each task's completion_evidence names a real artifact this skill's other
scripts already produce; `complete` mechanically checks that artifact exists
before a task can close — an agent's say-so is not evidence.

    python cartographer_run.py init --target /path/to/target --run ./run --actor me
    python cartographer_run.py status --run ./run
    python cartographer_run.py start scan-target --run ./run --actor me
    python cartographer_run.py complete confirm-roots --run ./run --actor me
    python cartographer_run.py add-task --run ./run --id my-task --title "..." --phase cycle
    python cartographer_run.py sync --run ./run
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import state as state_mod

PHASES = ["negotiate", "elicit", "scan", "join", "reconcile", "cycle", "assemble", "share"]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _skill_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"),
                   encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def _work_path(run):
    return os.path.join(run, "work.json")


def _todo_path(run):
    return os.path.join(run, "TODO.md")


def _load_work(run):
    path = _work_path(run)
    if not os.path.exists(path):
        sys.exit(f"no work.json at {path} — run `cartographer_run.py init` first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_work(run, work):
    with open(_work_path(run), "w", encoding="utf-8") as f:
        json.dump(work, f, indent=2)


def _task(work, task_id):
    for t in work["tasks"]:
        if t["id"] == task_id:
            return t
    sys.exit(f"no such task: {task_id}")


def _done_ids(work):
    return {t["id"] for t in work["tasks"] if t["status"] == "done"}


def _recompute_statuses(work):
    """A task's status is recomputed from its blocked_by graph, never trusted
    as hand-set — this is what lets a fresh session reconstruct exactly what's
    ready by reading work.json alone, with no hidden state."""
    done = _done_ids(work)
    for t in work["tasks"]:
        if t["status"] in ("done", "in_progress"):
            continue
        unmet = [b for b in t["blocked_by"] if b not in done]
        t["status"] = "blocked" if unmet else "ready"


def _current_phase(work):
    done = _done_ids(work)
    by_phase = {}
    for t in work["tasks"]:
        by_phase.setdefault(t["phase"], []).append(t)
    for phase in PHASES:
        tasks = by_phase.get(phase, [])
        if any(t["id"] not in done for t in tasks):
            return phase
    return "complete"


def _seed_tasks(run):
    """Ten tasks mirroring SKILL.md's own phase list. Each completion_evidence
    names an artifact this skill's *existing* scripts already produce —
    the ledger wraps real mechanism, it does not invent a parallel one."""
    def t(id_, title, phase, blocked_by, reason, command, artifact, condition, skippable=False):
        return {
            "id": id_, "title": title, "phase": phase, "owner": "agent",
            "status": "blocked" if blocked_by else "ready",
            "blocked_by": blocked_by, "reason": reason, "command": command,
            "completion_evidence": {"artifact": artifact, "condition": condition} if artifact else None,
            "skippable": skippable, "skipped": False, "skip_reason": None,
            "discovered_by": "seed", "created_at": _now(), "completed_at": None,
        }

    return [
        t("confirm-roots", "Confirm target and evidence roots", "negotiate", [],
          "The observation contract has to name its root before anything else can be scoped honestly.",
          "python scripts/environment_probe.py --root <target> --out " + run + "/environment.json",
          "environment.json", "environment.json exists and names the target under roots[]"),
        t("resolve-capability-questions", "Resolve environment capability questions", "negotiate",
          ["confirm-roots"],
          "An unresolved capability is a question, not an absence (workflow-template.md Sec.1).",
          None, "environment.json",
          "environment.json's questions[] is empty, or every question has a declared --capability answer"),
        t("elicit-blind-beliefs", "Capture blind builder beliefs", "elicit",
          ["resolve-capability-questions"],
          "Belief must be captured before scan evidence can contaminate it — unrecoverable once seen (save-states.md).",
          None, "elicitation.jsonl",
          "every active concern has an answer or an explicit, documented skip", skippable=True),
        t("scan-target", "Run preliminary scan", "scan", ["elicit-blind-beliefs"],
          "Scanning before elicitation is terminal contaminates the one measurement this skill exists to make.",
          "python scripts/cartographer_scan.py --target <target> --environment " + run +
          "/environment.json --out-dir " + run + "/scan --cache " + run + "/scan-cache.json --compact",
          "scan/scan.json", "scan.json exists and carries a produced_by stamp"),
        t("reconcile-against-beliefs", "Reconcile candidates against builder beliefs", "reconcile",
          ["scan-target"],
          "Deltas, not confirmations, are the product (SKILL.md).",
          None, "reconciliation.json",
          "every concern's deltas are tagged confirmed/drift/undocumented/unevidenced/aspiration"),
        t("generate-informed-scan-configs", "Generate informed scan configurations", "cycle",
          ["reconcile-against-beliefs"],
          "A reconcile round can surface vocabulary no registered concern owns yet.",
          None, "project.concerns.json",
          "an overlay registry exists, or this task is skipped with a reason (no new vocabulary found)",
          skippable=True),
        t("export-source-evidence", "Export relevant source evidence", "assemble",
          ["generate-informed-scan-configs"],
          "Priors must point at content that travels, not paths that die off-machine (export_bundle.py) — "
          "and only real evidence gets planned, never every candidate (build_export_manifest.py).",
          "python scripts/build_export_manifest.py --scan-dir " + run + "/scan --profile replication "
          "--out " + run + "/export-plan.json && python scripts/export_bundle.py --plan " +
          run + "/export-plan.json --out " + run,
          "manifest.json", "every card prior resolves to an exports/<slot>/ path, not a machine-local path"),
        t("resolve-boundary-dispositions", "Resolve boundary dispositions", "share",
          ["export-source-evidence"],
          "A bundle that silently omits what its target points at outside its root fails its own replication test.",
          None, "boundary-dispositions.json",
          "every resolved boundary pointer carries a disposition (included/excluded/deferred)"),
        t("review-secret-findings", "Review secret findings", "share",
          ["export-source-evidence"],
          "export_bundle.py's secret scan is a tripwire, not a scrubber — a human has to actually look.",
          None, "manifest.json",
          "every secret_warnings entry has been read and accepted, or the export was fixed"),
        t("validate-replication-bundle", "Validate replication bundle", "share",
          ["resolve-boundary-dispositions", "review-secret-findings"],
          "state.py refuses `shared` without both review surfaces present — this is that gate, named as a task.",
          "python scripts/bundle_synopsis.py --bundle " + run,
          "README.md", "README.md and handoff.json both exist"),
    ]


def cmd_init(target, run, actor, note):
    if not os.path.isdir(target):
        sys.exit(f"--target {target} is not a directory (stat-only check; target contents are not read at init)")
    if os.path.exists(_work_path(run)):
        sys.exit(f"work.json already exists at {run} — use status/start/complete/sync, not init")
    os.makedirs(run, exist_ok=True)

    work = {
        "run": {
            "target": os.path.abspath(target),
            "run_dir": os.path.abspath(run),
            "actor": actor,
            "created_at": _now(),
            "note": note or "",
            "produced_by": {"skill": "system-cartographer", "skill_version": _skill_version()},
        },
        "tasks": _seed_tasks(run),
    }
    _recompute_statuses(work)
    _save_work(run, work)

    if not os.path.exists(os.path.join(run, "state.json")):
        state_mod.cmd_init(run, actor, note)
    else:
        print("note: state.json already existed — left untouched", file=sys.stderr)

    _write_todo(run, work)
    print(f"initialized run at {run} — {len(work['tasks'])} tasks, phase: {_current_phase(work)}")


def _fmt_task_line(t):
    marker = {"ready": "[ ]", "in_progress": "[~]", "blocked": "[ ]", "done": "[x]"}[t["status"]]
    line = f"- {marker} {t['title']}"
    if t["status"] == "in_progress":
        line += f" (in progress — {t.get('started_by', '?')})"
    if t["status"] == "done" and t.get("skipped"):
        line += f" (skipped: {t['skip_reason']})"
    return line


def _write_todo(run, work):
    by_id = {t["id"]: t for t in work["tasks"]}
    ready = [t for t in work["tasks"] if t["status"] == "ready"]
    in_progress = [t for t in work["tasks"] if t["status"] == "in_progress"]
    blocked = [t for t in work["tasks"] if t["status"] == "blocked"]
    done = [t for t in work["tasks"] if t["status"] == "done"]

    env_path = os.path.join(run, "environment.json")
    authority = "not yet negotiated — see confirm-roots"
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                env = json.load(f)
            roots = env.get("roots") or []
            if roots:
                authority = ", ".join(f"{r['path']} ({r['authority']})" for r in roots)
        except (OSError, json.JSONDecodeError, KeyError):
            authority = "environment.json present but unreadable"

    lines = [
        "# System Cartographer Run", "",
        f"Target: {work['run']['target']}",
        f"Actor: {work['run']['actor']}",
        f"Current phase:: {_current_phase(work).capitalize()}",
        f"Authority: {authority}", "",
    ]

    lines.append("## Now")
    if not ready and not in_progress:
        lines.append("(nothing ready — see Blocked)")
    for t in ready + in_progress:
        lines.append(_fmt_task_line(t))
    lines.append("")

    lines.append("## Blocked")
    if not blocked:
        lines.append("(nothing blocked)")
    for t in blocked:
        lines.append(_fmt_task_line(t))
        names = ", ".join(by_id[b]["title"] if b in by_id else b for b in t["blocked_by"])
        lines.append(f"  - Blocked by: {names}")
    lines.append("")

    lines.append("## Done")
    if not done:
        lines.append("(nothing done yet)")
    for t in done:
        lines.append(_fmt_task_line(t))
    lines.append("")

    lines.append(
        "_Generated from work.json by cartographer_run.py — never hand-edit this file; "
        "use start / complete / add-task / sync._"
    )
    with open(_todo_path(run), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def cmd_status(run):
    work = _load_work(run)
    _recompute_statuses(work)
    _save_work(run, work)
    _write_todo(run, work)
    print(f"phase: {_current_phase(work)}")
    for label, statuses in (("ready", ("ready",)), ("in progress", ("in_progress",)),
                             ("blocked", ("blocked",)), ("done", ("done",))):
        items = [t for t in work["tasks"] if t["status"] in statuses]
        print(f"\n{label} ({len(items)}):")
        for t in items:
            extra = f"  <- {', '.join(t['blocked_by'])}" if statuses == ("blocked",) else ""
            print(f"  {t['id']}: {t['title']}{extra}")


def cmd_start(run, task_id, actor):
    work = _load_work(run)
    _recompute_statuses(work)
    t = _task(work, task_id)
    if t["status"] == "done":
        sys.exit(f"'{task_id}' is already done")
    if t["status"] == "in_progress":
        print(f"'{task_id}' is already in progress")
        return
    if t["status"] == "blocked":
        sys.exit(f"cannot start '{task_id}': blocked by unfinished task(s): "
                  f"{', '.join(t['blocked_by'])}. Complete or --skip those first.")
    t["status"] = "in_progress"
    t["started_by"] = actor
    t["started_at"] = _now()
    _save_work(run, work)
    _write_todo(run, work)
    print(f"-> in_progress: {task_id}")
    if t.get("command"):
        print(f"command: {t['command']}")


def cmd_complete(run, task_id, actor, note, skip_reason):
    work = _load_work(run)
    _recompute_statuses(work)
    t = _task(work, task_id)
    if t["status"] == "done":
        sys.exit(f"'{task_id}' is already done")
    ready_before = {x["id"] for x in work["tasks"] if x["status"] == "ready"}

    if skip_reason:
        if not t["skippable"]:
            sys.exit(f"'{task_id}' is not skippable — it requires its completion_evidence artifact")
        t["skipped"] = True
        t["skip_reason"] = skip_reason
    else:
        ce = t["completion_evidence"]
        if ce:
            artifact_path = os.path.join(run, ce["artifact"])
            if not os.path.exists(artifact_path):
                sys.exit(
                    f"cannot complete '{task_id}': required artifact missing — {ce['artifact']}\n"
                    f"What 'done' means here: {ce['condition']}\n"
                    "(this checks the artifact exists; the condition text is a reminder, not "
                    "mechanically verified — read it before you call this done)"
                )
            print(f"artifact present: {ce['artifact']} — done means: {ce['condition']}")

    t["status"] = "done"
    t["completed_by"] = actor
    t["completed_at"] = _now()
    if note:
        t["note"] = note
    _recompute_statuses(work)
    _save_work(run, work)
    _write_todo(run, work)

    newly_ready = [x["id"] for x in work["tasks"]
                   if x["status"] == "ready" and x["id"] not in ready_before and x["id"] != task_id]
    print(f"-> done: {task_id}")
    if newly_ready:
        print(f"newly ready: {', '.join(newly_ready)}")


def cmd_add_task(run, task_id, title, phase, owner, blocked_by, reason, command,
                  artifact, condition, discovered_by, skippable):
    work = _load_work(run)
    if any(t["id"] == task_id for t in work["tasks"]):
        sys.exit(f"task id already exists: {task_id}")
    if phase not in PHASES:
        sys.exit(f"--phase must be one of: {', '.join(PHASES)}")
    for b in blocked_by:
        if not any(t["id"] == b for t in work["tasks"]):
            sys.exit(f"--blocked-by names an unknown task: {b}")
    if bool(artifact) != bool(condition):
        sys.exit("--artifact and --condition must be given together, or not at all")

    task = {
        "id": task_id, "title": title, "phase": phase, "owner": owner or "agent",
        "status": "blocked" if blocked_by else "ready",
        "blocked_by": blocked_by, "reason": reason or "",
        "command": command,
        "completion_evidence": {"artifact": artifact, "condition": condition} if artifact else None,
        "skippable": skippable, "skipped": False, "skip_reason": None,
        "discovered_by": discovered_by or "manual",
        "created_at": _now(), "completed_at": None,
    }
    work["tasks"].append(task)
    _recompute_statuses(work)
    _save_work(run, work)
    _write_todo(run, work)
    print(f"added: {task_id} (status: {task['status']}, discovered_by: {task['discovered_by']})")


def cmd_sync(run):
    work = _load_work(run)
    _recompute_statuses(work)
    _save_work(run, work)
    _write_todo(run, work)
    print(f"synced — phase: {_current_phase(work)}")


def main():
    ap = argparse.ArgumentParser(description="System Cartographer first-touch run ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--target", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--note", default=None)

    p = sub.add_parser("status")
    p.add_argument("--run", required=True)

    p = sub.add_parser("start")
    p.add_argument("task_id")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("complete")
    p.add_argument("task_id")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--note", default=None)
    p.add_argument("--skip", dest="skip_reason", default=None,
                    help="Close a skippable task without its artifact, recording why")

    p = sub.add_parser("add-task")
    p.add_argument("--run", required=True)
    p.add_argument("--id", dest="task_id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--owner", default="agent")
    p.add_argument("--blocked-by", default="", help="comma-separated task ids")
    p.add_argument("--reason", default=None)
    p.add_argument("--command", default=None)
    p.add_argument("--artifact", default=None)
    p.add_argument("--condition", default=None)
    p.add_argument("--discovered-by", default="manual",
                    help="what surfaced this task, e.g. 'boundary-pointer', 'secret-finding'")
    p.add_argument("--skippable", action="store_true")

    sub.add_parser("sync").add_argument("--run", required=True)

    args = ap.parse_args()

    if args.cmd == "init":
        cmd_init(args.target, args.run, args.actor, args.note)
    elif args.cmd == "status":
        cmd_status(args.run)
    elif args.cmd == "start":
        cmd_start(args.run, args.task_id, args.actor)
    elif args.cmd == "complete":
        cmd_complete(args.run, args.task_id, args.actor, args.note, args.skip_reason)
    elif args.cmd == "add-task":
        blocked_by = [b.strip() for b in args.blocked_by.split(",") if b.strip()]
        cmd_add_task(args.run, args.task_id, args.title, args.phase, args.owner, blocked_by,
                      args.reason, args.command, args.artifact, args.condition,
                      args.discovered_by, args.skippable)
    elif args.cmd == "sync":
        cmd_sync(args.run)


if __name__ == "__main__":
    main()
