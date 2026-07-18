#!/usr/bin/env python3
"""Duplicate suppression and source classification.

Before concern counting, a copy of a real file (a vendored tree, a nested
export, a snapshot) must not inflate the same count a canonical source
already contributes to. This hashes candidate content (bounded, same size
ceiling the scanner already applies), groups exact byte-identical copies,
nominates one canonical member per group (deterministic: shortest path,
then lexicographic — no judgment call, just a stable tie-break), and
classifies every candidate's `source_class` so a receiving agent can tell
source from generated output from observation residue at a glance.
"""
import hashlib
import os
import re

SOURCE_EXT_RE = re.compile(r"\.(?:md|py|js|ts|jsx|tsx|sh|rb|go|rs|java|c|cpp|h|hpp)$", re.IGNORECASE)
CONFIG_EXT_RE = re.compile(r"\.(?:json|ya?ml|toml|cfg|ini)$", re.IGNORECASE)


def hash_file(path, max_bytes):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            h.update(f.read(max_bytes))
    except OSError:
        return None
    return h.hexdigest()


def classify_source_class(rel, is_duplicate_copy):
    if is_duplicate_copy:
        return "copy"
    lower = rel.lower()
    if re.search(r"\.(?:zip|tar|gz|tgz|7z|rar)$", lower):
        return "archive"
    if re.search(r"(?:^|/)(?:dist|build|out|generated|\.generated)(?:/|$)", lower) or ".generated." in lower:
        return "generated"
    if re.search(r"(?:^|/)(?:snapshot|backup|bak)s?(?:/|$)", lower) or lower.endswith(".bak"):
        return "snapshot"
    if re.search(r"(?:^|/)(?:\.cache|__pycache__|cache)(?:/|$)", lower):
        return "cache"
    if re.search(r"(?:^|/)(?:vendor|third[_-]party|node_modules)(?:/|$)", lower):
        return "vendor"
    if re.search(r"(?:session|transcript|conversation)[^/]*\.(?:jsonl|json|log|md)$", lower) or \
       re.search(r"(?:^|/)(?:transcripts|sessions)(?:/|$)", lower):
        return "transcript"
    if re.search(r"(?:^|/)(?:state|runs)\.jsonl?$", lower) or re.search(r"\brun[-_]?state\b", lower):
        return "runtime-state"
    if CONFIG_EXT_RE.search(lower):
        return "configuration"
    if SOURCE_EXT_RE.search(lower):
        return "source"
    return "unknown"


def build_lineage(records, root, max_bytes):
    """Mutates each record in place with `content_hash` and `source_class`;
    returns the lineage report: duplicate groups, canonical nominations,
    and copy->canonical edges."""
    by_hash = {}
    for record in records:
        if not record["concerns"]:
            record["content_hash"] = None
            continue
        h = hash_file(record["path"], max_bytes)
        record["content_hash"] = h
        if h:
            by_hash.setdefault(h, []).append(record)

    groups, edges = [], []
    canonical_of = {}
    for h, members in by_hash.items():
        if len(members) < 2:
            canonical_of[members[0]["rel"]] = members[0]["rel"]
            continue
        ordered = sorted(members, key=lambda r: (len(r["rel"]), r["rel"]))
        canonical = ordered[0]
        for m in ordered:
            canonical_of[m["rel"]] = canonical["rel"]
        groups.append({
            "hash": h, "canonical": canonical["rel"],
            "copies": [m["rel"] for m in ordered[1:]],
        })
        edges.extend({"copy": m["rel"], "canonical": canonical["rel"], "hash": h} for m in ordered[1:])

    for record in records:
        if not record["concerns"]:
            continue
        is_copy = canonical_of.get(record["rel"]) not in (None, record["rel"])
        record["source_class"] = classify_source_class(record["rel"], is_copy)
        record["canonical_rel"] = canonical_of.get(record["rel"], record["rel"])

    return {
        "duplicate_groups": groups,
        "lineage_edges": edges,
        "summary": {
            "candidates_hashed": sum(1 for r in records if r.get("content_hash")),
            "duplicate_groups": len(groups),
            "copies_suppressed": sum(len(g["copies"]) for g in groups),
        },
    }
