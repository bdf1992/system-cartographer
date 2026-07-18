#!/usr/bin/env python3
"""Single-pass, registry-driven cartography scan.

Walk the target once, read each relevant text file at most once, classify it across
all selected concerns, and emit both per-concern evidence graphs and a cross-concern
pattern map. Optional stat/config caching makes repeated cycle scans incremental.
"""
import argparse
import concurrent.futures
import fnmatch
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from concern_registry import load as load_registries  # noqa: E402
import structural_validators  # noqa: E402
import lineage  # noqa: E402

# Bumped whenever structural_validators.py's checks change meaning — folded into
# config_signature() so an old scan-cache built under a looser validator can't be
# silently reused to claim a file is still just "candidate" (or vice versa).
VALIDATORS_VERSION = "1"

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
DEFAULT_REGISTRY = os.path.join(SKILL_ROOT, "references", "concerns.registry.json")
DEFAULT_EXCLUDES = [
    "**/.git/**", "**/node_modules/**", "**/vendor/**", "**/.venv/**", "**/venv/**",
    "**/__pycache__/**", "**/dist/**", "**/build/**", "**/coverage/**", "*.pyc",
]


def _norm(path):
    return os.path.normpath(path).replace(os.sep, "/")


def _matches(rel_path, globs):
    rel_path = _norm(rel_path)
    for pattern in globs:
        pattern = _norm(pattern)
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        while pattern.startswith("**/"):
            pattern = pattern[3:]
            if fnmatch.fnmatch(rel_path, pattern):
                return True
    return False


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def atomic_json(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
    os.replace(temp, path)


def resolve(item, relative):
    return os.path.normpath(os.path.join(item["_registry_dir"], relative))


def load_environment(path):
    if not path:
        return None, {}
    env = read_json(path)
    caps = {item["id"]: item["status"] for item in env.get("capabilities", [])}
    return env, caps


def config_signature(items, configs, boundary_config=None):
    stable = [{"validators_version": VALIDATORS_VERSION}]
    for item in items:
        stable.append({k: v for k, v in item.items() if not k.startswith("_")})
        if item["id"] in configs:
            stable.append(configs[item["id"]])
    if boundary_config:
        stable.append(boundary_config)
    raw = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def compile_patterns(config):
    return [
        (p["kind"], re.compile(p["regex"], re.MULTILINE), p.get("include"), p.get("exclude", []))
        for p in config.get("edge_patterns", [])
    ]


def is_excluded(rel, patterns):
    return _matches(rel, patterns) or _matches(rel + "/**", patterns)


DEFAULT_BOUNDARY_CONFIG = os.path.join(SKILL_ROOT, "references", "boundary.scan.json")


def load_boundary_config(path):
    if path in (None, "", "none"):
        path = DEFAULT_BOUNDARY_CONFIG
    if not os.path.isfile(path):
        return {}, []
    config = read_json(path)
    return config, compile_patterns(config)


def resolve_boundary_target(dst, root, src_rel):
    """Try to land dst on a real path, relative to the referencing file, the
    target root, or the scan's own launch directory — in that order, because
    a reference in a doc is most often relative to where the doc sits."""
    if "://" in dst or dst.startswith(("mailto:", "#", "tel:")):
        return None
    bases, seen = [], set()
    for base in (os.path.dirname(os.path.join(root, src_rel)), root, os.getcwd()):
        b = os.path.abspath(base)
        if b not in seen:
            seen.add(b)
            bases.append(b)
    for base in bases:
        candidate = os.path.normpath(os.path.join(base, dst))
        if os.path.exists(candidate):
            return candidate
    return None


def classify_relation(resolved, root):
    # normcase makes the comparison match the filesystem's own identity rules —
    # a no-op on POSIX, but on Windows it folds drive-letter/segment case so a
    # reference written as "c:\..." isn't wrongly called a stranger to "C:\...".
    root_n = os.path.normpath(os.path.abspath(root))
    resolved_n = os.path.normpath(resolved)
    root_cf = os.path.normcase(root_n)
    resolved_cf = os.path.normcase(resolved_n)
    if resolved_cf == root_cf:
        return "self"
    if resolved_cf.startswith(root_cf + os.path.normcase(os.sep)):
        return "descendant"
    if root_cf.startswith(resolved_cf + os.path.normcase(os.sep)):
        return "ancestor"
    if os.path.normcase(os.path.dirname(resolved_n)) == os.path.normcase(os.path.dirname(root_n)):
        return "sibling"
    return "cousin"


def peek_boundary_target(path, max_entries=25, max_chars=160):
    """A cheap, bounded look at what a pointer names — enough for the map to
    say what's behind the door without a second scan. Metadata and a single
    line only; never a content dump."""
    try:
        if os.path.isdir(path):
            names = sorted(os.listdir(path))
            return {"kind": "directory", "entry_count": len(names), "entries": names[:max_entries]}
        size = os.path.getsize(path)
        first_line = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not re.fullmatch(r"[-=`~#*+]{1,}", line):
                        first_line = line[:max_chars]
                        break
        except OSError:
            pass
        return {"kind": "file", "bytes": size, "first_line": first_line}
    except OSError as exc:
        return {"kind": "unknown", "error": str(exc)}


def _canonical_key(resolved):
    """Canonicalizes Windows case, separators, and drive-letter spelling so
    two differently-written references to the SAME real file group as one
    pointer, not two — os.path.normcase folds drive-letter/segment case on
    Windows (a no-op on POSIX); normpath folds separators and '..' segments."""
    return os.path.normcase(os.path.normpath(resolved))


def build_boundary_pointers(boundary_edges, root):
    """Every path-shaped reference the scan noticed that resolves outside
    (or fails to resolve inside) the declared target root — named, classified
    by relation to root, and given a cheap peek. This is what lets the map
    say 'there is a door here' instead of silently stopping at its own walls.

    Grouping key is the resolved target's canonical form, not the literal
    reference string — 'C:\\Foo\\Bar', 'c:/foo/bar', and './Bar' from a
    sibling file all name the same door and must land in the same group
    (references/boundary-protocol.md's grouping law)."""
    grouped = {}
    for edge in boundary_edges:
        dst = edge["dst"]
        if "://" in dst or dst.startswith(("mailto:", "#", "tel:")):
            continue
        resolved = resolve_boundary_target(dst, root, edge["src"])
        relation = classify_relation(resolved, root) if resolved else "unresolved"
        if relation in ("self", "descendant"):
            continue
        key = _canonical_key(resolved) if resolved else ("unresolved", dst)
        if key not in grouped:
            pid = hashlib.sha256(f"{key}".encode()).hexdigest()[:12]
            grouped[key] = {
                "id": pid,
                "reference": dst,
                "reference_variants": [],
                "relation": relation,
                "resolved_path": resolved,
                "exists": resolved is not None,
                "referenced_from": [],
                "explore": peek_boundary_target(resolved) if resolved else None,
                "source_class": (lineage.classify_source_class(_norm(os.path.relpath(resolved, root)), False)
                                 if resolved and os.path.isfile(resolved) else None),
                "disposition": None,
            }
        entry = grouped[key]
        if dst not in entry["reference_variants"]:
            entry["reference_variants"].append(dst)
        if edge["src"] not in entry["referenced_from"]:
            entry["referenced_from"].append(edge["src"])
    return sorted(
        grouped.values(),
        key=lambda p: (0 if p["exists"] else 1, -len(p["referenced_from"]), p["reference"]),
    )


def _slug(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")[:60] or "target"


def collect_files(root, configs, extra_excludes, max_files, follow_symlinks):
    global_excludes = DEFAULT_EXCLUDES + list(extra_excludes)
    found = []
    truncated = False
    errors = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        rel_dir = _norm(os.path.relpath(dirpath, root))
        if rel_dir == ".":
            rel_dir = ""
        dirnames[:] = sorted(
            d for d in dirnames
            if not is_excluded(_norm(os.path.join(rel_dir, d)), global_excludes)
        )
        for name in sorted(filenames):
            rel = _norm(os.path.join(rel_dir, name))
            if is_excluded(rel, global_excludes):
                continue
            concerns = []
            for cid, config in configs.items():
                includes = config.get("include", ["**/*"])
                excludes = config.get("exclude", [])
                if _matches(rel, includes) and not is_excluded(rel, excludes):
                    concerns.append(cid)
            path = os.path.join(root, rel)
            try:
                stat = os.stat(path, follow_symlinks=follow_symlinks)
            except OSError as exc:
                errors.append({"path": rel, "error": str(exc)})
                continue
            found.append({
                "rel": rel, "path": path, "concerns": sorted(concerns),
                "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            })
            if max_files and len(found) >= max_files:
                truncated = True
                return found, truncated, errors
    return found, truncated, errors


def scan_one(record, compiled, max_file_bytes, cached, boundary_compiled=(), internal_names=None):
    rel = record["rel"]
    cache_key = f"{record['size']}:{record['mtime_ns']}"
    if cached and cached.get("stat") == cache_key and cached.get("concerns") == record["concerns"]:
        return rel, cached.get("edges", []), cached.get("boundary_edges", []), True, None, cached.get("findings", []), cached.get("rejected", [])
    if not record["concerns"] or record["size"] > max_file_bytes:
        return rel, [], [], False, "oversize" if record["concerns"] else None, [], []
    if not any(compiled.get(cid) for cid in record["concerns"]) and not boundary_compiled:
        return rel, [], [], False, None, [], []
    try:
        with open(record["path"], "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(max_file_bytes + 1)
    except OSError as exc:
        return rel, [], [], False, str(exc), [], []
    edges = []
    for cid in record["concerns"]:
        for kind, rx, includes, excludes in compiled.get(cid, []):
            if includes and not _matches(rel, includes):
                continue
            if excludes and _matches(rel, excludes):
                continue
            for match in rx.finditer(text):
                dst = match.group(1) if match.groups() else match.group(0)
                edges.append({"concern": cid, "src": rel, "dst": dst.strip(), "kind": kind, "meta": {}})
    boundary_edges = []
    for kind, rx, includes, excludes in boundary_compiled:
        if includes and not _matches(rel, includes):
            continue
        if excludes and _matches(rel, excludes):
            continue
        for match in rx.finditer(text):
            dst = match.group(1) if match.groups() else match.group(0)
            boundary_edges.append({"src": rel, "dst": dst.strip(), "kind": kind})

    findings, rejected = [], []
    for cid in record["concerns"]:
        if cid == "code-scripts":
            imp_findings, imp_rejected = structural_validators.classify_imports(rel, text, internal_names or set())
            findings.extend({"concern": cid, "file": rel, **f} for f in imp_findings)
            rejected.extend({"concern": cid, "file": rel, **r} for r in imp_rejected)
            continue
        for f in structural_validators.validate(cid, rel, text, {}):
            findings.append({"concern": cid, "file": rel, **f})
    return rel, edges, boundary_edges, False, None, findings, rejected


def git_log(root, limit=200):
    cmd = ["git", "-C", root, "log", f"-{limit}", "--format=%H|%ad|%s", "--date=short"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode:
        return []
    rows = []
    for line in out.stdout.splitlines():
        try:
            sha, date, subject = line.split("|", 2)
        except ValueError:
            continue
        rows.append({"sha": sha, "date": date, "subject": subject})
    return rows


def build_patterns(records, all_edges, selected_ids, environment_gaps, node_evidence, boundary_pointers=(),
                    boundary_pointers_unresolved_dropped=0, all_findings=(), all_rejected=(),
                    lineage_report=None, evidenced_files_by_concern=None):
    candidate_pairs = Counter()
    evidence_pairs = Counter()
    hotspots = []
    extension_counts = Counter()
    classified = 0
    edge_counts_by_file = Counter(e["src"] for e in all_edges)
    edge_concerns_by_file = defaultdict(set)
    for edge in all_edges:
        edge_concerns_by_file[edge["src"]].add(edge["concern"])

    evidenced_files_by_concern = evidenced_files_by_concern or {}
    structural_concerns_by_file = defaultdict(set)
    for cid, files in evidenced_files_by_concern.items():
        for file_ in files:
            structural_concerns_by_file[file_].add(cid)

    candidate_coverage = Counter()
    evidence_coverage = Counter()
    for record in records:
        ext = os.path.splitext(record["rel"])[1].lower() or "[none]"
        extension_counts[ext] += 1
        concerns = record["concerns"]
        if concerns:
            classified += 1
        candidate_coverage.update(concerns)
        # A file counts as evidenced for a concern only on a real edge (a regex
        # actually matched a relationship) or a real structural+/behavioral+
        # finding — never merely because the concern's evidence_mode is "node"
        # and the glob happened to match (references/evidence-model.md).
        evidenced = sorted(edge_concerns_by_file[record["rel"]] | structural_concerns_by_file.get(record["rel"], set()))
        evidence_coverage.update(evidenced)
        for left, right in itertools.combinations(concerns, 2):
            candidate_pairs[(left, right)] += 1
        for left, right in itertools.combinations(evidenced, 2):
            evidence_pairs[(left, right)] += 1
        if len(evidenced) > 1 or edge_counts_by_file[record["rel"]] > 2:
            hotspots.append({
                "path": record["rel"], "evidenced_concerns": evidenced,
                "candidate_concerns": concerns, "concern_count": len(evidenced),
                "edge_count": edge_counts_by_file[record["rel"]],
            })
    target_concerns = defaultdict(set)
    for edge in all_edges:
        target_concerns[edge["dst"]].add(edge["concern"])
    shared_targets = [
        {"target": target, "concerns": sorted(concerns), "concern_count": len(concerns)}
        for target, concerns in target_concerns.items() if len(concerns) > 1
    ]

    stage_counts = Counter(f["evidence_stage"] for f in all_findings)
    stage_by_concern = defaultdict(Counter)
    for f in all_findings:
        stage_by_concern[f["concern"]][f["evidence_stage"]] += 1
    source_class_counts = Counter(r.get("source_class") for r in records if r.get("source_class"))

    lineage_report = lineage_report or {}
    return {
        "summary": {
            "files_seen": len(records),
            "files_candidate_classified": classified,
            "files_with_evidence": sum(1 for r in records if edge_concerns_by_file[r["rel"]] or structural_concerns_by_file.get(r["rel"])),
            "files_outside_scan_surfaces": len(records) - classified,
            "concerns_selected": len(selected_ids),
            "edges": len(all_edges),
            "findings": len(all_findings),
            "findings_by_stage": dict(sorted(stage_counts.items())),
            "rejected_candidates": len(all_rejected),
            "duplicate_groups": lineage_report.get("summary", {}).get("duplicate_groups", 0),
            "copies_suppressed": lineage_report.get("summary", {}).get("copies_suppressed", 0),
            "boundary_pointers": len(boundary_pointers),
            "boundary_pointers_undispositioned": sum(
                1 for p in boundary_pointers
                if p["exists"] and p["relation"] != "unresolved" and not p.get("disposition")
            ),
            "boundary_pointers_unresolved_dropped": boundary_pointers_unresolved_dropped,
        },
        "candidate_concern_coverage": dict(sorted(candidate_coverage.items())),
        "evidenced_concern_coverage": dict(sorted(evidence_coverage.items())),
        "findings_by_concern_and_stage": {cid: dict(sorted(c.items())) for cid, c in sorted(stage_by_concern.items())},
        "rejected_candidates": list(all_rejected)[:200],
        "source_class_counts": dict(sorted(source_class_counts.items())),
        "evidenced_concern_pairs": [
            {"concerns": list(pair), "shared_file_count": count}
            for pair, count in evidence_pairs.most_common()
        ],
        "candidate_surface_pairs": [
            {"concerns": list(pair), "shared_file_count": count}
            for pair, count in candidate_pairs.most_common()
        ],
        "hotspot_files": sorted(hotspots, key=lambda x: (-x["concern_count"], -x["edge_count"], x["path"]))[:50],
        "shared_edge_targets": sorted(shared_targets, key=lambda x: (-x["concern_count"], x["target"]))[:50],
        "edge_kinds": dict(sorted(Counter(f"{e['concern']}:{e['kind']}" for e in all_edges).items())),
        "file_extensions": dict(extension_counts.most_common()),
        "environment_gaps": environment_gaps,
        "boundary_pointers": list(boundary_pointers),
        "reading_notes": [
            "Candidate surface overlap measures the instrument; evidenced overlap measures the target.",
            "evidenced_concern_coverage now requires a real edge or a structural+/behavioral+ finding — "
            "a node-evidence concern's bare glob match is never enough on its own (references/evidence-model.md).",
            "High evidenced concern-pair counts indicate shared substrate, not automatically bad coupling.",
            "A hotspot is a question target: ask whether its multiple roles are intentional.",
            "Unclassified files expose registry/config blind spots; they are not evidence of irrelevance.",
            "Pattern counts describe the observation instrument as well as the target.",
            "rejected_candidates names candidates that failed real structural validation with a reason "
            "(e.g. a .py file that doesn't parse) — never silently dropped.",
            "source_class_counts / duplicate_groups / copies_suppressed come from lineage.py's dedup pass — "
            "a copy never independently inflates a concern count past its canonical source.",
            "boundary_pointers names every path-shaped reference this scan found that actually resolved "
            "outside its own root (ancestor, sibling, or cousin) — see references/boundary-protocol.md. "
            "A card is not done while a load-bearing pointer here carries no disposition. Candidates that "
            "never resolved to anything real (prose false positives) are dropped by default — see "
            "boundary_pointers_unresolved_dropped in summary, or rerun with "
            "--include-unresolved-boundary-pointers to inspect them (useful when tuning --boundary-config).",
        ],
    }


def follow_boundary_pointers(boundary_pointers, args):
    """Take exactly one hop past the declared root, for pointers worth the trip.

    Bounded on purpose, two ways. First, only pointers that already resolve to a
    real *directory* are eligible — a reference to a single file (by far the
    common case: CLAUDE.md, a specific script) never gets expanded to "scan its
    containing folder," because for a root-level file that folder can be the
    entire repo (caught live: a reference to CLAUDE.md at a repo root turned into
    an 8,300-file, 20-second scan of the whole tree — exactly the silent-crawl
    risk this guard exists to prevent). A file-type pointer is still named and
    peeked; going deeper on it is a deliberate targeted read, not an automatic
    directory expansion. Second, eligible directory hops are capped at
    max_boundary_follow, and the sub-scan itself never follows its own boundaries
    (follow_boundaries=False) — one hop, not a crawl. This is the
    'propagate to peers/children' capability, opt-in via --follow-boundaries so
    a plain run stays fast and never reads outside its declared root by surprise."""
    cap = getattr(args, "max_boundary_follow", 8) or 8
    dispositions = {}
    disp_path = getattr(args, "boundary_dispositions", None)
    if disp_path and os.path.isfile(disp_path):
        with open(disp_path, encoding="utf-8") as f:
            dispositions = json.load(f)
    followed = 0
    for pointer in boundary_pointers:
        disp = dispositions.get(pointer["id"], {}).get("status")
        if disp in ("excluded", "deferred"):
            pointer["followed"] = {"status": "not_followed",
                                    "reason": f"disposed {disp} — never sub-scanned (boundary-protocol.md)"}
            continue
        if not pointer["exists"] or pointer["relation"] not in ("ancestor", "sibling", "cousin"):
            continue
        if (pointer.get("explore") or {}).get("kind") != "directory":
            pointer["followed"] = {"status": "not_followed", "reason": "pointer resolves to a file, not a "
                                    "directory — widen the root manually or read it directly; see boundary-protocol.md"}
            continue
        if followed >= cap:
            pointer["followed"] = {"status": "not_followed", "reason": f"max_boundary_follow={cap} reached"}
            continue
        target = pointer["resolved_path"]
        if not target or not os.path.isdir(target):
            pointer["followed"] = {"status": "skipped", "reason": "resolved target is not a directory"}
            continue
        sub_out_dir = (
            os.path.join(args.out_dir, "boundary", f"{pointer['id']}-{_slug(pointer['reference'])}")
            if getattr(args, "out_dir", None) else None
        )
        sub_args = argparse.Namespace(**vars(args))
        sub_args.target = target
        sub_args.target_name = f"{args.target_name or args.target} -> {pointer['reference']}"
        sub_args.out_dir = sub_out_dir
        sub_args.follow_boundaries = False
        sub_args.cache = None
        try:
            sub_result = scan(sub_args)
        except Exception as exc:  # a peer scan must never sink the primary run
            pointer["followed"] = {"status": "error", "error": str(exc)}
            continue
        pointer["followed"] = {
            "status": "scanned",
            "out_dir": os.path.abspath(sub_out_dir) if sub_out_dir else None,
            "summary": sub_result["patterns"]["summary"],
        }
        followed += 1


def scan(args):
    started = time.monotonic()
    registry_paths = args.registry or [DEFAULT_REGISTRY]
    items, registry_errors = load_registries(registry_paths)
    if registry_errors:
        raise ValueError("\n".join(registry_errors))
    requested = set(filter(None, (args.concerns or "").split(",")))
    if requested:
        unknown = requested - {item["id"] for item in items}
        if unknown:
            raise ValueError(f"unknown concerns: {sorted(unknown)}")
        items = [item for item in items if item["id"] in requested or item["id"] == "cross-cutting"]
    items = [item for item in items if item["status"] != "disabled"]
    environment, capabilities = load_environment(args.environment)
    environment_gaps = []
    active = []
    for item in items:
        missing = [cap for cap in item.get("requires", []) if capabilities.get(cap) == "unavailable"]
        restricted = [cap for cap in item.get("requires", []) if capabilities.get(cap) in {"restricted", "unknown"}]
        if missing:
            environment_gaps.append({"concern": item["id"], "status": "blocked", "capabilities": missing})
            continue
        if restricted:
            environment_gaps.append({"concern": item["id"], "status": "question", "capabilities": restricted})
        active.append(item)
    configs = {}
    for item in active:
        scanner = item["scanner"]
        if scanner["kind"] == "regex-graph":
            configs[item["id"]] = read_json(resolve(item, scanner["config"]))
    boundary_config, boundary_compiled = ({}, []) if getattr(args, "no_boundary_scan", False) \
        else load_boundary_config(getattr(args, "boundary_config", None))
    signature = config_signature(active, configs, boundary_config)
    cache = {}
    if args.cache and os.path.isfile(args.cache):
        try:
            candidate = read_json(args.cache)
            if candidate.get("signature") == signature:
                cache = candidate.get("files", {})
        except (OSError, ValueError, json.JSONDecodeError):
            cache = {}
    root = os.path.abspath(args.target)
    records, truncated, walk_errors = collect_files(
        root, configs, args.exclude, args.max_files, args.follow_symlinks
    )
    lineage_report = lineage.build_lineage(records, root, args.max_file_bytes)
    internal_names = set()
    for r in records:
        stem = os.path.splitext(os.path.basename(r["rel"]))[0]
        if stem:
            internal_names.add(stem)
        top = r["rel"].split("/")[0]
        if top and top != r["rel"]:
            internal_names.add(top)

    compiled = {cid: compile_patterns(config) for cid, config in configs.items()}
    all_edges = []
    all_boundary_edges = []
    all_findings = []
    all_rejected = []
    cache_hits = 0
    read_errors = []
    new_cache = {}
    effective_workers = args.workers or (1 if len(records) < 10000 else min(8, (os.cpu_count() or 2) + 2))
    if effective_workers == 1:
        scanned = (
            (record, scan_one(record, compiled, args.max_file_bytes, cache.get(record["rel"]), boundary_compiled, internal_names))
            for record in records
        )
    else:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers)
        futures = [pool.submit(scan_one, record, compiled, args.max_file_bytes, cache.get(record["rel"]), boundary_compiled, internal_names) for record in records]
        scanned = zip(records, (future.result() for future in futures))
    try:
        for record, outcome in scanned:
            rel, edges, boundary_edges, hit, error, findings, rejected = outcome
            all_edges.extend(edges)
            all_boundary_edges.extend(boundary_edges)
            all_findings.extend(findings)
            all_rejected.extend(rejected)
            cache_hits += int(hit)
            if error:
                read_errors.append({"path": rel, "error": error})
            if record["concerns"]:
                new_cache[rel] = {
                    "stat": f"{record['size']}:{record['mtime_ns']}",
                    "concerns": record["concerns"], "edges": edges, "boundary_edges": boundary_edges,
                    "findings": findings, "rejected": rejected,
                }
    finally:
        if effective_workers != 1:
            pool.shutdown()

    # memories' evidence needs the whole edge set (a demonstrated reader/writer
    # is a cross-file fact) — a cheap post-pass, no re-reading of file text.
    path_references = set()
    for edge in all_edges:
        dst = edge["dst"]
        if "://" not in dst and ("/" in dst or "." in dst) and len(dst) < 200:
            path_references.add(dst)
            path_references.add(os.path.basename(dst))
    for record in records:
        if "memories" in record["concerns"]:
            for f in structural_validators.validate("memories", record["rel"], "", {"path_references": path_references}):
                all_findings.append({"concern": "memories", "file": record["rel"], **f})
    EVIDENCED_STAGES = {"structural", "behavioral", "observed", "confirmed"}
    findings_by_concern_file = defaultdict(list)
    for f in all_findings:
        findings_by_concern_file[(f["concern"], f["file"])].append(f)
    evidenced_files_by_concern = defaultdict(set)
    for (cid, file_), fs in findings_by_concern_file.items():
        if any(f["evidence_stage"] in EVIDENCED_STAGES for f in fs):
            evidenced_files_by_concern[cid].add(file_)

    git_history = git_log(root) if any(i["id"] == "session-quality" for i in active) else []
    graphs = {}
    for item in active:
        cid = item["id"]
        scanner_kind = item["scanner"]["kind"]
        if scanner_kind == "regex-graph":
            nodes = [
                {"id": r["rel"], "kind": "file", "path": r["path"], "meta": {"bytes": r["size"]},
                 "source_class": r.get("source_class"), "canonical_rel": r.get("canonical_rel")}
                for r in records if cid in r["concerns"]
            ]
            edges = [{k: v for k, v in edge.items() if k != "concern"} for edge in all_edges if edge["concern"] == cid]
            findings = [f for f in all_findings if f["concern"] == cid]
            graphs[cid] = {"target": args.target_name or root, "root": root, "concern": cid, "type": item["type"],
                           "nodes": nodes, "edges": edges, "findings": findings,
                           "meta": {"node_count": len(nodes), "edge_count": len(edges),
                                    "evidenced_count": len(evidenced_files_by_concern.get(cid, ()))}}
        elif cid == "session-quality":
            graphs[cid] = {"target": args.target_name or root, "root": root, "concern": cid, "type": item["type"], "analysis": {"commit_count": len(git_history), "recent_commits": git_history}, "meta": {"scanner": "shared-git-read"}}
    node_evidence = {
        item["id"] for item in active
        if item.get("scanner", {}).get("evidence_mode") in {"node", "node-or-edge"}
        or (item["id"] in configs and not configs[item["id"]].get("edge_patterns"))
    }
    boundary_pointers_all = build_boundary_pointers(all_boundary_edges, root)
    if getattr(args, "follow_boundaries", False) and boundary_pointers_all:
        follow_boundary_pointers(boundary_pointers_all, args)
    if getattr(args, "include_unresolved_boundary_pointers", False):
        boundary_pointers, boundary_pointers_dropped = boundary_pointers_all, 0
    else:
        boundary_pointers = [p for p in boundary_pointers_all if p["exists"]]
        boundary_pointers_dropped = len(boundary_pointers_all) - len(boundary_pointers)
    patterns = build_patterns(records, all_edges, sorted(graphs), environment_gaps, node_evidence,
                               boundary_pointers, boundary_pointers_dropped,
                               all_findings, all_rejected, lineage_report, evidenced_files_by_concern)
    # Cross-cutting couplings: a node only joins if it's real evidence for that
    # concern (a structural+ finding), never a bare candidate glob match — a
    # weak candidate shared across two concerns' globs is not a coupling.
    shared = defaultdict(set)
    for cid, graph in graphs.items():
        for file_ in evidenced_files_by_concern.get(cid, ()):
            shared[file_].add(cid)
        for edge in graph.get("edges", []):
            shared[edge["dst"]].add(cid)
    if any(item["id"] == "cross-cutting" for item in active):
        couplings = {key: sorted(value) for key, value in shared.items() if len(value) > 1}
        graphs["cross-cutting"] = {"target": args.target_name or root, "root": root, "concern": "cross-cutting", "type": "relation", "candidate_coupling_points": couplings, "meta": {"concern_count": len(graphs), "coupling_point_count": len(couplings)}}
    run = {
        "script": "cartographer_scan.py", "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_ms": round((time.monotonic() - started) * 1000), "registry": registry_paths,
        "registry_signature": signature, "workers": effective_workers, "max_file_bytes": args.max_file_bytes,
        "max_files": args.max_files, "truncated": truncated, "cache_hits": cache_hits,
        "walk_errors": walk_errors, "read_notes": read_errors, "environment": args.environment,
    }
    for graph in graphs.values():
        graph["run"] = run
    result = {"schema_version": "1.1", "target": args.target_name or root, "environment": environment, "graphs": graphs, "patterns": patterns, "lineage": lineage_report, "run": run, "produced_by": _produced_by(signature)}
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for cid, graph in graphs.items():
            atomic_json(os.path.join(args.out_dir, cid + ".json"), graph)
        atomic_json(os.path.join(args.out_dir, "patterns.json"), patterns)
        atomic_json(os.path.join(args.out_dir, "lineage.json"), lineage_report)
        atomic_json(os.path.join(args.out_dir, "scan.json"), result)
    if args.cache:
        atomic_json(args.cache, {"version": 1, "signature": signature, "files": new_cache})
    return result



def _produced_by(registry_signature=None):
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"), encoding="utf-8") as f:
            v = f.read().strip()
    except OSError:
        v = "unknown"
    pb = {"skill": "system-cartographer", "skill_version": v}
    if registry_signature:
        pb["registry_signature"] = registry_signature
    return pb


def main():
    ap = argparse.ArgumentParser(description="Scan every registered concern in one target walk")
    ap.add_argument("--target", required=True)
    ap.add_argument("--target-name")
    ap.add_argument("--registry", action="append", help="Base registry followed by overlay registries")
    ap.add_argument("--environment", help="Environment descriptor from environment_probe.py")
    ap.add_argument("--concerns", help="Comma-separated subset; cross-cutting is included")
    ap.add_argument("--out-dir")
    ap.add_argument("--cache", help="Optional incremental cache JSON path")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--max-files", type=int, default=50000)
    ap.add_argument("--max-file-bytes", type=int, default=2 * 1024 * 1024)
    ap.add_argument("--workers", type=int, default=0, help="0=adaptive; local trees default to sequential reads")
    ap.add_argument("--follow-symlinks", action="store_true")
    ap.add_argument("--compact", action="store_true", help="Print only run and pattern summary")
    ap.add_argument("--boundary-config", help="Path-reference pattern config; default references/boundary.scan.json")
    ap.add_argument("--no-boundary-scan", action="store_true", help="Disable out-of-root pointer detection entirely")
    ap.add_argument("--follow-boundaries", action="store_true",
                    help="Take one real sub-scan hop into resolved ancestor/sibling/cousin pointers (bounded, opt-in)")
    ap.add_argument("--max-boundary-follow", type=int, default=8,
                    help="Cap on how many boundary pointers --follow-boundaries actually scans")
    ap.add_argument("--boundary-dispositions",
                    help="boundary-dispositions.json from state.py — excluded/deferred pointers are never "
                         "sub-scanned by --follow-boundaries, even if they'd otherwise be eligible")
    ap.add_argument("--include-unresolved-boundary-pointers", action="store_true",
                    help="Also emit boundary-pointer candidates that never resolved to anything real "
                         "(prose false positives) — dropped by default; useful when tuning --boundary-config")
    args = ap.parse_args()
    try:
        result = scan(args)
    except ValueError as exc:
        ap.error(str(exc))
    if args.compact:
        print(json.dumps({"target": result["target"], "summary": result["patterns"]["summary"], "run": result["run"]}, indent=2))
    elif not args.out_dir:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"out_dir": os.path.abspath(args.out_dir), "summary": result["patterns"]["summary"], "run": result["run"]}, indent=2))


if __name__ == "__main__":
    main()
