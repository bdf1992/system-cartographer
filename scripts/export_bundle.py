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

Two input formats, both accepted:

    --plan export-plan.json      preferred — build_export_manifest.py's typed
                                  output (claim-to-evidence supports[], source_class,
                                  expected_sha256, copies folded into their canonical)
    --manifest manifest.json     legacy flat JSON list:
        [{"source": "...", "slot": "exemplars", "as": "renamed.jsonl",
          "lines": [120, 240], "grep": "regex"}, ...]

Usage:
    python export_bundle.py --plan export-plan.json --out ./bundle [--card card.md ...]

Produces:
    bundle/
      card(s)...                # any --card files, copied to bundle root
      exports/<slot>/<name>     # the evidence content itself
      manifest.json             # source->export map, hashes, supports, warnings

Binary files are copied byte-for-byte and never decoded, excerpted, or
secret-scanned. Text files are hashed twice — the source bytes as found, and
the bytes actually written to disk — and a bundle that finds those two hashes
disagree for any entry refuses to call itself done (exit code, not just a
warning), because a bundle that silently mis-wrote its own evidence is worse
than one that never shipped it. Identical content across multiple entries is
written once and referenced by hash, never duplicated on disk. Secret scan:
a few naive patterns (key/token/bearer/password assignments, long hex/base64
runs) on text content only. Hits are WARNINGS in the manifest and on stderr —
review them yourself; this is a tripwire, not a scrubber.
"""
import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer)\b\s*[:=]"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),  # long opaque strings; noisy on purpose
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".pdf", ".zip", ".tar", ".gz",
    ".tgz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib", ".bin", ".woff", ".woff2",
    ".ttf", ".otf", ".sqlite", ".sqlite3", ".db", ".pyc", ".class", ".jar",
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def is_binary(name, data):
    if os.path.splitext(name)[1].lower() in BINARY_EXTENSIONS:
        return True
    try:
        data.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def excerpt_text(text, lines=None, grep=None):
    all_lines = text.splitlines(keepends=True)
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


def _produced_by():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"), encoding="utf-8") as f:
            v = f.read().strip()
    except OSError:
        v = "unknown"
    return {"skill": "system-cartographer", "skill_version": v}


def safe_export_name(requested, used_names):
    """Refuses a name that could escape the bundle (absolute, or any ".."
    segment), and guarantees two different sources never silently overwrite
    the same export path — a repeat name gets a numbered suffix instead."""
    name = requested.replace("\\", "/")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":") or ".." in name.split("/"):
        raise ValueError(f"unsafe export name (escapes the bundle): {requested!r}")
    candidate, n = name, 1
    while candidate in used_names:
        stem, ext = os.path.splitext(name)
        candidate = f"{stem}-{n}{ext}"
        n += 1
    used_names.add(candidate)
    return candidate


def load_entries(args):
    if args.plan:
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
        entries = [{
            "source": e["source"], "slot": e["slot"], "as": None, "lines": None, "grep": None,
            "supports": e.get("supports", []), "source_class": e.get("source_class"),
            "expected_sha256": e.get("expected_sha256"), "copies_folded_in": e.get("copies_folded_in", []),
        } for e in plan["entries"]]
        return entries, plan.get("profile")
    with open(args.manifest, encoding="utf-8") as f:
        raw = json.load(f)
    entries = [{**e, "supports": [], "source_class": None, "expected_sha256": None,
                "copies_folded_in": []} for e in raw]
    return entries, None


def main():
    ap = argparse.ArgumentParser(description="Build the portable export bundle")
    ap.add_argument("--manifest", help="Legacy flat JSON list of export entries")
    ap.add_argument("--plan", help="export-plan.json from build_export_manifest.py (preferred)")
    ap.add_argument("--out", required=True, help="Bundle output directory")
    ap.add_argument("--card", action="append", default=[],
                    help="Card file(s) to copy into the bundle root (repeatable)")
    args = ap.parse_args()
    if not args.manifest and not args.plan:
        ap.error("one of --manifest or --plan is required")

    entries, profile = load_entries(args)
    os.makedirs(args.out, exist_ok=True)
    record, all_warnings = [], []
    hash_to_export = {}
    used_names_by_slot = {}

    for card in args.card:
        shutil.copy2(card, os.path.join(args.out, os.path.basename(card)))

    for e in entries:
        src, slot = e["source"], e["slot"]
        used_names = used_names_by_slot.setdefault(slot, set())
        requested_name = e.get("as") or os.path.basename(src)
        excerpted = bool(e.get("lines") or e.get("grep"))

        if not os.path.exists(src):
            record.append({"source": src, "export": None, "slot": slot, "error": "source not found"})
            print(f"MISSING {src}", file=sys.stderr)
            continue
        try:
            with open(src, "rb") as f:
                data = f.read()
        except OSError as exc:
            record.append({"source": src, "export": None, "slot": slot, "error": str(exc)})
            continue

        source_hash = sha256_bytes(data)
        if e.get("expected_sha256") and e["expected_sha256"] != source_hash:
            print(f"WARN {src}: content changed since planning "
                  f"({e['expected_sha256'][:8]} -> {source_hash[:8]})", file=sys.stderr)

        if source_hash in hash_to_export and not excerpted:
            existing = hash_to_export[source_hash]
            record.append({
                "source": src, "export": existing["export"], "slot": slot, "duplicate_of": existing["export"],
                "source_sha256": source_hash, "export_sha256": source_hash, "export_verified": True,
                "binary": existing["binary"], "byte_size": len(data), "secret_warnings": [],
                "source_class": e.get("source_class"), "supports": e.get("supports", []),
                "copies_folded_in": e.get("copies_folded_in", []),
            })
            continue

        try:
            safe_name = safe_export_name(requested_name, used_names)
        except ValueError as exc:
            record.append({"source": src, "export": None, "slot": slot, "error": str(exc)})
            print(f"REFUSED {src}: {exc}", file=sys.stderr)
            continue

        slot_dir = os.path.join(args.out, "exports", slot)
        dst = os.path.join(slot_dir, safe_name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        rel = "/".join(("exports", slot, safe_name))
        binary = is_binary(safe_name, data) and not excerpted
        warnings = []

        if binary:
            with open(dst, "wb") as f:
                f.write(data)
            export_hash = source_hash
        else:
            text = data.decode("utf-8", errors="ignore")
            if excerpted:
                text = excerpt_text(text, e.get("lines"), e.get("grep"))
            # newline="" disables Windows' text-mode \n -> \r\n translation —
            # without it the bytes actually written never match export_hash
            # below, and post-write verification would refuse every single
            # text export on this OS regardless of content correctness.
            with open(dst, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            warnings = secret_warnings(text, rel)
            export_hash = sha256_bytes(text.encode("utf-8"))

        with open(dst, "rb") as f:
            written = f.read()
        verified = sha256_bytes(written) == export_hash

        all_warnings.extend(warnings)
        record.append({
            "source": src, "export": rel, "slot": slot,
            "lines": e.get("lines"), "grep": e.get("grep"),
            "mime_type": mimetypes.guess_type(safe_name)[0], "binary": binary, "byte_size": len(data),
            "source_sha256": source_hash, "export_sha256": export_hash, "export_verified": verified,
            "secret_warnings": warnings, "source_class": e.get("source_class"),
            "supports": e.get("supports", []), "copies_folded_in": e.get("copies_folded_in", []),
        })
        if not excerpted:
            hash_to_export[source_hash] = {"export": rel, "binary": binary}

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": record, "profile": profile, "produced_by": _produced_by()}, f, indent=2)

    exported = sum(1 for r in record if r.get("export"))
    unverified = [r["export"] for r in record if r.get("export") and not r.get("export_verified", True)]
    print(f"bundle: {args.out} — {exported}/{len(record)} exports, {len(all_warnings)} secret warning(s), "
          f"{len(unverified)} failed post-write verification")
    for w in all_warnings:
        print(f"  WARN {w}", file=sys.stderr)
    if all_warnings:
        print("Review flagged lines before this bundle leaves the machine.", file=sys.stderr)
    if unverified:
        sys.exit(f"{len(unverified)} export(s) failed post-write hash verification: "
                  f"{', '.join(unverified)} — bundle is not trustworthy")


if __name__ == "__main__":
    main()
