#!/usr/bin/env python3
"""Assemble the portable export bundle — the thing that actually ships.

The card's replication test says values must stand alone, and priors must
survive leaving the builder's machine. A path into ~/.claude/projects/ or
the local repo dies the moment the bundle is handed to a dev team, so this
script copies (or excerpts) the actual evidence into exports/<slot>/ and
records a manifest mapping each export back to its original source. Priors
in the card then point at bundle-relative paths — content that travels —
with the original location preserved in the manifest for anyone who also
has access to the source system.

Manifest format (JSON list):
    [
      {"source": "/abs/or/rel/path", "slot": "exemplars",
       "as": "good-run-2026-06.jsonl",          # optional rename
       "lines": [120, 240],                       # optional 1-based inclusive range
       "grep": "regex"},                          # optional line filter (applied after lines)
      ...
    ]

Usage:
    python export_bundle.py --manifest manifest.json --out ./bundle [--card card.md ...]

Produces:
    bundle/
      card(s)...                # any --card files, copied to bundle root
      exports/<slot>/<name>     # the evidence content itself
      manifest.json             # source→export map, line ranges, sha256, warnings

Secret scan: every exported text file is checked against a few naive
patterns (key/token/bearer/password assignments, long hex/base64 runs).
Hits are WARNINGS in the manifest and on stderr — review them yourself;
this is a tripwire, not a scrubber. Nothing is redacted automatically,
because silent redaction would corrupt exemplars in ways a receiving team
can't detect.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer)\b\s*[:=]"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),  # long opaque strings; noisy on purpose
]


def excerpt(path, lines=None, grep=None):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()
    if lines:
        start, end = lines
        all_lines = all_lines[start - 1:end]
    if grep:
        rx = re.compile(grep)
        all_lines = [ln for ln in all_lines if rx.search(ln)]
    return "".join(all_lines)


def secret_warnings(text, name):
    warnings = []
    for i, line in enumerate(text.splitlines(), 1):
        for rx in SECRET_PATTERNS:
            if rx.search(line):
                warnings.append(f"{name}:{i} matches {rx.pattern[:40]!r}")
                break
    return warnings


def sha256(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()



def _produced_by():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"), encoding="utf-8") as f:
            v = f.read().strip()
    except OSError:
        v = "unknown"
    return {"skill": "system-cartographer", "skill_version": v}


def main():
    ap = argparse.ArgumentParser(description="Build the portable export bundle")
    ap.add_argument("--manifest", required=True, help="JSON list of export entries")
    ap.add_argument("--out", required=True, help="Bundle output directory")
    ap.add_argument("--card", action="append", default=[],
                    help="Card file(s) to copy into the bundle root (repeatable)")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as f:
        entries = json.load(f)

    os.makedirs(args.out, exist_ok=True)
    record, all_warnings = [], []

    for card in args.card:
        shutil.copy2(card, os.path.join(args.out, os.path.basename(card)))

    for e in entries:
        src, slot = e["source"], e["slot"]
        name = e.get("as") or os.path.basename(src)
        slot_dir = os.path.join(args.out, "exports", slot)
        os.makedirs(slot_dir, exist_ok=True)
        dst = os.path.join(slot_dir, name)
        rel = "/".join(("exports", slot, name))  # bundle-relative identifier, not a filesystem
        # path for this OS — must stay portable (forward slash) so the manifest travels off-machine

        if not os.path.exists(src):
            record.append({"source": src, "export": None, "error": "source not found"})
            print(f"MISSING {src}", file=sys.stderr)
            continue

        if e.get("lines") or e.get("grep"):
            text = excerpt(src, e.get("lines"), e.get("grep"))
            with open(dst, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            shutil.copy2(src, dst)
            with open(dst, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        warnings = secret_warnings(text, rel)
        all_warnings.extend(warnings)
        record.append({
            "source": src, "export": rel, "slot": slot,
            "lines": e.get("lines"), "grep": e.get("grep"),
            "sha256": sha256(text), "secret_warnings": warnings,
        })

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": record, "produced_by": _produced_by()}, f, indent=2)

    exported = sum(1 for r in record if r.get("export"))
    print(f"bundle: {args.out} — {exported}/{len(record)} exports, "
          f"{len(all_warnings)} secret warning(s)")
    for w in all_warnings:
        print(f"  WARN {w}", file=sys.stderr)
    if all_warnings:
        print("Review flagged lines before this bundle leaves the machine.", file=sys.stderr)


if __name__ == "__main__":
    main()
