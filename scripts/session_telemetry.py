#!/usr/bin/env python3
"""Instrument for the session-quality concern (scanner kind: external).

Restores the implementation lost in the v0.x consolidation. Deliberately
never prints a single number: it emits structured inputs — commits bucketed
by month, date range, a crude fix/revert-subject ratio, and (with
--sessions-dir) session-transcript files bucketed by month with sizes — and
stops. Turning these into a trend read (frequent vs sparse, recent vs
stale, converging vs churning) is synthesis, done in conversation with
judgment. "47 sessions" answers a different, less useful question than the
one this concern asks — see references/session-quality/card.md.

    python session_telemetry.py --target <repo> [--sessions-dir <dir>] [--out <file>]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone, date

FIX_RE = re.compile(r"\b(fix|revert|hotfix|patch)\b", re.IGNORECASE)


def skill_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def git_log(root, limit=200):
    cmd = ["git", "-C", root, "log", f"-{limit}", "--format=%H|%ad|%s", "--date=short"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if out.returncode != 0:
            return []
        entries = []
        for line in out.stdout.splitlines():
            if line:
                sha, d, subject = line.split("|", 2)
                entries.append({"sha": sha, "date": d, "subject": subject})
        return entries
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def analyze_git(log):
    if not log:
        return {"commit_count": 0, "note": "no git history found for this target"}
    months = Counter(e["date"][:7] for e in log)
    fix_like = sum(1 for e in log if FIX_RE.search(e["subject"]))
    dates = sorted(e["date"] for e in log)
    return {
        "commit_count": len(log),
        "date_range": [dates[0], dates[-1]],
        "commits_by_month": dict(sorted(months.items())),
        "fix_or_revert_subject_ratio": round(fix_like / len(log), 2),
        "note": "structured inputs only — characterize frequency/recency/convergence "
                "in conversation; never reduce this to a single number",
    }


def analyze_sessions(sessions_dir):
    files = []
    for fn in os.listdir(sessions_dir):
        if fn.endswith(".jsonl"):
            p = os.path.join(sessions_dir, fn)
            st = os.stat(p)
            files.append({"file": fn,
                          "month": date.fromtimestamp(st.st_mtime).strftime("%Y-%m"),
                          "bytes": st.st_size})
    if not files:
        return {"session_file_count": 0, "note": "no .jsonl transcripts found"}
    months = Counter(f["month"] for f in files)
    return {
        "session_file_count": len(files),
        "sessions_by_month": dict(sorted(months.items())),
        "largest_sessions": sorted(files, key=lambda f: -f["bytes"])[:5],
        "note": "structured inputs only; large transcripts are exemplar candidates "
                "for the export bundle",
    }


def main():
    ap = argparse.ArgumentParser(description="session-quality telemetry instrument")
    ap.add_argument("--target", required=True)
    ap.add_argument("--target-name", default=None)
    ap.add_argument("--sessions-dir", default=None,
                    help="Session transcript dir, e.g. ~/.claude/projects/<slug>")
    ap.add_argument("--git-limit", type=int, default=200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    t0 = time.monotonic()

    result = {
        "schema_version": "1.0",
        "concern": "session-quality",
        "target": args.target_name or args.target,
        "git_analysis": analyze_git(git_log(args.target, args.git_limit)),
    }
    if args.sessions_dir:
        sd = os.path.expanduser(args.sessions_dir)
        result["session_analysis"] = (analyze_sessions(sd) if os.path.isdir(sd)
                                      else {"error": f"not a directory: {sd}"})
    result["run"] = {
        "script": "session_telemetry.py",
        "argv": sys.argv[1:],
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_ms": round((time.monotonic() - t0) * 1000),
    }
    result["produced_by"] = {"skill": "system-cartographer", "skill_version": skill_version()}
    text = json.dumps(result, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
