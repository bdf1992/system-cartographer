#!/usr/bin/env python3
"""graph_export.py -- a scan as one graph, a report on it, and a Schematically document.

Reads a scan directory written by cartographer_scan.py (the per-concern graphs plus
patterns.json) and writes three files:

  graph.json        graphify's node-link format: nodes with id / label / file_type /
                    source_file / community, links with source / target / relation /
                    confidence (EXTRACTED or INFERRED) / confidence_score / source_file.
                    Anything that reads a graphify graph reads this one.
  GRAPH_REPORT.md   the most connected nodes, the communities, the basis counts, the
                    files held only by a pattern match, and what sits outside the root.
  system.sov        a soveraeign.schematic/document@0.1 document: one card per node,
                    one wire per link labelled with its relation and carrying its basis,
                    one group per community. With --schematically <checkout> it is laid
                    out by that checkout's scripts/layout_sov.mjs; without it the
                    document is written unplaced.

How the scan's own terms map onto the graph's:

  node        every file a concern graph names, every edge target that is not a file
              (an imported package, a named external system, a repository), and every
              boundary pointer.
  community   a file's primary concern: the concern holding its strongest evidence
              stage. A file with no evidence anywhere goes to an asset concern before
              a system-description one, and among equals to the concern with the
              fewest files. The scan already sorted the target by concern, so no
              clustering is run.
  basis       a link is EXTRACTED when a structural or behavioral finding backs it (a
              finding naming the same target, or failing that any such finding for the
              source file in the link's concern). A link resting on a pattern match
              alone is INFERRED at 0.65, graphify's score for a name-only match.
  asset kind  the asset_kind its primary concern declares in the registry; a concern
              that declares none describes the system itself. --group-by asset makes
              the communities asset kinds, with the system description as one of them.
  hyperedge   three or more files tied by one shared target, in graph.hyperedges.
  partitions  each grouping's modularity and its place among shuffled groupings, in
              graph.partitions, so a reader can tell which grouping the links support.

Standard library only. Nothing here calls a model or a network service.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

SCHEMA = "soveraeign.schematic/document@0.1"
CANVAS = "canvas:global"
STAGE_RANK = {"candidate": 0, "structural": 1, "behavioral": 2}
EVIDENCED = ("structural", "behavioral")
INFERRED_SCORE = 0.65
# A target longer than this is a value the scan captured (a description, a sentence),
# not a thing another file could also point at.
MAX_TARGET_CHARS = 80
# Kinds that mark something about the source file rather than a relation to a target.
MARKER_KINDS = frozenset({"todo_marker"})
BOUNDARY_COMMUNITY = "outside the root"
# A concern that declares no asset_kind belongs to the description of the system itself.
SYSTEM_DESCRIPTION = "system description"
GROUPINGS = ("concern", "asset")
NULL_DRAWS = 1000
HYPEREDGE_MIN = 3
REPORT_ROWS = 15
SOURCE_ROWS = 5
# The scan's own import guesses, replaced by parsed imports when a code graph is merged.
SCAN_IMPORT_KINDS = frozenset({"python_import", "js_import", "js_require"})
# Relations that say where a definition sits, not what it does.
STRUCTURAL_RELATIONS = frozenset({"contains", "method", "rationale_for"})
# Above this many nodes the full document is a wall; the overviews are written and it is not.
FULL_DOCUMENT_NODES = 2500
CODE_CARDS = 14
CODE_WIRES = 22
AGENTIC_KINDS = frozenset({"agent", "skill", "hook", "workflow", "tool"})
AGENTIC_READ_BYTES = 262144
MAX_SHUFFLE_WORK = 30_000_000
CODE_EXTENSIONS = frozenset({".py", ".js", ".mjs", ".ts", ".tsx", ".sh", ".ps1", ".go", ".rs", ".cs", ".java", ".rb"})
RECORDS = "records"
# The fields a record uses to say what kind of record it is, in the order they are tried.
RECORD_TYPE_FIELDS = ("record_type", "type", "kind")
# In those fields these are JSON Schema's own words for a value's shape, not a kind of record.
SCHEMA_TYPE_WORDS = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})
RECORD_READ_BYTES = 1048576
# A value shorter than this is a word (a state, a flag), not the id of another record.
RECORD_ID_MIN = 4
LABEL_LENGTH = 28
ELLIPSIS = "…"

_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")
_BACKSLASHES = re.compile(r"\\{2,}")
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_.$\\/-]+\.[A-Za-z0-9]{1,5}")
_DRIVE_ROOT = re.compile(r"^[A-Za-z]:[\\/]*[A-Za-z]?$")
_TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|_test\.[^/.]+$|\.(test|spec)\.[^/]+$")
# Code the target holds but did not write: type declarations, vendored and generated files.
_NOT_OWN = re.compile(r"\.d\.ts$|(^|/)(vendor|vendored|third_party|node_modules|dist|generated)/")
# A test file's name without its extension, and the part of it that names what it tests.
_TEST_NAME = re.compile(r"^(?:test_(.+)|(.+)_test|(.+)\.(?:test|spec))$")
OWN, TEST, NOT_OWN = "own", "test", "not written here"
SCRIPT_EXTENSIONS = frozenset({".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"})
# The file that stands for its folder: a test named for the folder is about the package.
PACKAGE_FILES = frozenset({"__init__", "index"})
# Trailing parts of a path a test's name may run together: `commands_observer` for commands/observer.py.
SUBJECT_PARTS = 3
_ID_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.:-]*[A-Za-z0-9])?")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def load_scan(scan_dir):
    """The concern graphs (those with a nodes list) by concern name, and patterns.json."""
    graphs = {}
    for name in sorted(os.listdir(scan_dir)):
        if not name.endswith(".json") or name in ("scan.json", "patterns.json", "lineage.json"):
            continue
        data = read_json(os.path.join(scan_dir, name))
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            graphs[data.get("concern") or name[: -len(".json")]] = data
    patterns_path = os.path.join(scan_dir, "patterns.json")
    patterns = read_json(patterns_path) if os.path.exists(patterns_path) else {}
    return graphs, patterns


def load_asset_kinds(registry_paths):
    """concern id -> asset_kind, from every registry that declares one."""
    kinds = {}
    for path in registry_paths:
        data = read_json(path)
        for item in (data.get("concerns") if isinstance(data, dict) else data) or []:
            if item.get("asset_kind"):
                kinds[item["id"]] = item["asset_kind"]
    return kinds


def file_label(rel):
    parts = rel.replace("\\", "/").split("/")
    return "/".join(parts[-2:])


def file_type(rel):
    return "code" if os.path.splitext(rel)[1].lower() in CODE_EXTENSIONS else "document"


def module_file(module, nodes):
    """The scanned file a dotted Python module name names, or None when it is not in the root."""
    base = module.replace(".", "/")
    for rel in (f"{base}.py", f"{base}/__init__.py"):
        if rel in nodes:
            return rel
    return None


def clean_pointer(reference):
    """One spelling for an outside-the-root path, or None when it names nothing.

    A path quoted inside JSON arrives with doubled backslashes and one quoted in a
    sentence with a trailing full stop; both are the same place. A bare drive root is
    what is left of a path pattern matching an escape sequence, and points nowhere."""
    path = _BACKSLASHES.sub(r"\\", reference).rstrip(".")
    if len(path) > 3:
        path = path.rstrip("\\/")
    return None if _DRIVE_ROOT.match(path) else path


def best_stages(graphs):
    """(concern, file) -> strongest evidence stage, from each concern's findings."""
    best = {}
    for concern, graph in graphs.items():
        for finding in graph.get("findings") or []:
            key = (concern, finding.get("file"))
            stage = finding.get("evidence_stage") or "candidate"
            if STAGE_RANK.get(stage, 0) >= STAGE_RANK.get(best.get(key, "candidate"), 0):
                best[key] = stage
    return best


def primary_concerns(graphs, stages, asset_kinds=None):
    """file -> the concern that owns it as a community.

    Evidence decides first. A file no concern has evidence for goes to an asset concern
    before a system-description one: a filename pattern alone does not make a file part
    of the system description. Among equals the concern with the fewest files wins."""
    asset_kinds = asset_kinds or {}
    sizes = {concern: len(graph.get("nodes") or []) for concern, graph in graphs.items()}
    holders = {}
    for concern, graph in graphs.items():
        for node in graph.get("nodes") or []:
            holders.setdefault(node["id"], []).append(concern)

    def rank(concern, rel):
        stage = STAGE_RANK[stages.get((concern, rel), "candidate")]
        return -stage, 0 if stage or concern in asset_kinds else 1, sizes[concern], concern

    return {rel: min(concerns, key=lambda c: rank(c, rel)) for rel, concerns in holders.items()}


def link_basis(concern, edge, graph, stages):
    """('EXTRACTED', 1.0) or ('INFERRED', 0.65) for one scan edge."""
    src, dst = edge.get("src"), edge.get("dst")
    targeted = [f for f in graph.get("findings") or [] if f.get("file") == src and f.get("import_target")]
    if targeted:
        hit = any(f["import_target"] == dst and f.get("evidence_stage") in EVIDENCED for f in targeted)
        return ("EXTRACTED", 1.0) if hit else ("INFERRED", INFERRED_SCORE)
    if stages.get((concern, src)) in EVIDENCED:
        return "EXTRACTED", 1.0
    return "INFERRED", INFERRED_SCORE


def code_kind(node):
    """'module', 'class', 'function' or 'symbol' for a parsed code node; None for one that
    is not a definition inside the root (a rationale note, an imported name)."""
    source_file = str(node.get("source_file") or "").replace("\\", "/")
    if node.get("file_type") != "code" or not source_file:
        return None
    if node.get("_callable_class") is True:
        return "class"
    if node.get("_callable") is True:
        return "function"
    label = str(node.get("label") or "")
    return "module" if label and source_file.endswith(label) else "symbol"


def merge_code(nodes, links, skipped, code_dir):
    """Lay the parsed code over the scanned files: every definition becomes a node under
    the file that holds it, every call, import, inheritance and use becomes a link, and a
    module is the file node itself. Returns the links, with the scan's own file-to-file
    import guesses dropped in favour of the parsed ones."""
    code = read_json(os.path.join(code_dir, "code-graph.json"))
    lint_path = os.path.join(code_dir, "lint.json")
    lint = read_json(lint_path) if os.path.exists(lint_path) else {}
    mapped = {}
    for node in code["nodes"]:
        kind = code_kind(node)
        rel = str(node.get("source_file") or "").replace("\\", "/")
        if kind is None or rel not in nodes:
            continue
        holder = nodes[rel]
        if kind == "module":
            mapped[node["id"]] = rel
            holder["code_community"] = node.get("community")
            continue
        node_id = f"code:{node['id']}"
        mapped[node["id"]] = node_id
        nodes[node_id] = {
            "id": node_id, "label": str(node.get("label") or node["id"]), "file_type": "code", "source_file": rel,
            "source_location": node.get("source_location"), "kind": kind, "source_class": holder.get("source_class"),
            "concerns": list(holder["concerns"]), "evidence_stage": "structural",
            "primary_concern": holder["primary_concern"], "code_community": node.get("community"),
        }
        if node.get("lint"):
            nodes[node_id]["lint"] = node["lint"]
    for rel, codes in (lint.get("by_file") or {}).items():
        if rel in nodes:
            nodes[rel]["lint"] = codes
    kept = [l for l in links if not (l["relation"] in SCAN_IMPORT_KINDS and nodes[l["target"]]["kind"] == "file")]
    skipped["scan_imports_replaced"] = len(links) - len(kept)
    seen = set()
    for link in code["links"]:
        a, b = mapped.get(link.get("source")), mapped.get(link.get("target"))
        relation = str(link.get("relation") or "relates_to")
        if a is None or b is None:
            skipped["code_links_leaving_root"] += 1
            continue
        if a == b or (a, b, relation) in seen:
            continue
        seen.add((a, b, relation))
        basis = link.get("confidence") if link.get("confidence") in ("EXTRACTED", "INFERRED") else "INFERRED"
        kept.append({
            "source": a, "target": b, "relation": relation, "confidence": basis,
            "confidence_score": link.get("confidence_score") or (1.0 if basis == "EXTRACTED" else INFERRED_SCORE),
            "source_file": nodes[a]["source_file"], "concern": nodes[a]["primary_concern"],
        })
    declare_dependencies(nodes, kept, code_dir)
    return kept


def package_key(name):
    return re.sub(r"[-_]+", "-", str(name)).lower()


def declare_dependencies(nodes, links, code_dir):
    """Join what the manifests declare to what the code imports: a declared package is an
    external node marked declared, linked from the manifest that names it."""
    path = os.path.join(code_dir, "dependencies.json")
    if not os.path.exists(path):
        return
    externals = {package_key(n["label"]): n for n in nodes.values() if n["kind"] == "external"}
    for manifest, names in sorted(read_json(path).items()):
        if manifest not in nodes:
            continue
        for name in names:
            node = externals.get(package_key(name))
            if node is None:
                node = externals[package_key(name)] = nodes[f"external:{name}"] = {
                    "id": f"external:{name}", "label": name, "file_type": "external", "source_file": "",
                    "kind": "external", "source_class": None, "concerns": ["required-tools-repos"],
                    "evidence_stage": None, "primary_concern": nodes[manifest]["primary_concern"],
                }
            node["declared"] = True
            links.append({
                "source": manifest, "target": node["id"], "relation": "declares", "confidence": "EXTRACTED",
                "confidence_score": 1.0, "source_file": manifest, "concern": nodes[manifest]["primary_concern"],
            })


def path_targets(text, nodes):
    """The scanned files a piece of text names by path, in the order they appear."""
    found = []
    for token in _PATH_TOKEN.findall(text or ""):
        parts = token.replace("\\", "/").split("/")
        for start in range(len(parts)):
            rel = "/".join(parts[start:])
            if rel in nodes and nodes[rel]["kind"] == "file":
                if rel not in found:
                    found.append(rel)
                break
    return found


def read_target_text(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="ignore") as handle:
            return handle.read(AGENTIC_READ_BYTES)
    except OSError:
        return ""


def agentic_layer(nodes, links, graphs):
    """The actors and triggers, wired down to what they run.

    From the scan's structural findings: an agent definition becomes an agent node with a
    link to each tool it is granted; a skill becomes a skill node; each hook binding and
    each workflow becomes a node of its own. Then each is joined to the scanned files its
    command or its text names by path, which is where the layer meets the parsed code. A
    hook's command is the thing that runs, so that link is EXTRACTED; a path named in an
    instruction or a workflow file is INFERRED."""
    root = next((g.get("root") or g.get("target") for g in graphs.values() if g.get("root") or g.get("target")), "")

    def add(node_id, label, kind, concern, source_file):
        nodes[node_id] = {
            "id": node_id, "label": label, "file_type": "agentic", "source_file": source_file, "kind": kind,
            "source_class": None, "concerns": [concern], "evidence_stage": "structural", "primary_concern": concern,
        }
        return node_id

    def link(a, b, relation, basis, concern, score=None):
        links.append({"source": a, "target": b, "relation": relation, "confidence": basis,
                      "confidence_score": score or (1.0 if basis == "EXTRACTED" else INFERRED_SCORE),
                      "source_file": nodes[a]["source_file"], "concern": concern})

    def names(owner, rel, concern, relation="names", basis="INFERRED", score=0.75, text=None):
        for target in path_targets(text if text is not None else read_target_text(root, rel), nodes):
            if target != rel:
                link(owner, target, relation, basis, concern, score)

    for concern in ("agent", "skill", "workflow"):
        for finding in (graphs.get(concern) or {}).get("findings") or []:
            data, rel = finding.get("extracted") or {}, finding.get("file")
            if finding.get("evidence_stage") not in EVIDENCED or rel not in nodes or not data:
                continue
            if concern in ("agent", "skill") and data.get("name"):
                owner = add(f"{concern}:{data['name']}", str(data["name"]), concern, concern, rel)
                link(rel, owner, "defines", "EXTRACTED", concern)
                for tool in [t.strip() for t in str(data.get("tools") or "").split(",") if t.strip()]:
                    tool_id = f"tool:{tool}"
                    if tool_id not in nodes:
                        add(tool_id, tool, "tool", "agent", "")
                    link(owner, tool_id, "may_use", "EXTRACTED", concern)
                names(owner, rel, concern)
            for index, row in enumerate(data.get("hook_rows") or []):
                label = str(row.get("event")) + (f" [{row['matcher']}]" if row.get("matcher") else "")
                owner = add(f"hook:{rel}:{row.get('event')}:{index}", label, "hook", "workflow", rel)
                nodes[owner]["command"] = row.get("command")
                link(rel, owner, "binds", "EXTRACTED", "workflow")
                names(owner, rel, "workflow", relation="runs", basis="EXTRACTED", score=1.0,
                      text=str(row.get("command") or ""))
            if data.get("trigger") and not data.get("hook_rows"):
                owner = add(f"workflow:{rel}", str(data.get("name") or file_label(rel)), "workflow", "workflow", rel)
                nodes[owner]["trigger"] = data.get("trigger")
                link(rel, owner, "defines", "EXTRACTED", "workflow")
                names(owner, rel, "workflow", relation="runs", score=0.85)


def read_record(root, rel):
    """(parsed JSON object, its strings) for a record file, or (None, []) when it cannot be read as
    one: not JSON, a list, missing, over RECORD_READ_BYTES, or nested past what Python will walk."""
    path = os.path.join(root, rel)
    try:
        if not rel.lower().endswith(".json") or os.path.getsize(path) > RECORD_READ_BYTES:
            return None, []
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return (data, list(record_strings(data))) if isinstance(data, dict) else (None, [])
    except (OSError, ValueError, RecursionError):
        return None, []


def record_strings(value, field=""):
    """(field path, string) for every string inside a parsed record: values, and the keys of
    an object as `field{}`. List positions are left out of the path."""
    if isinstance(value, str):
        yield field, value
    elif isinstance(value, dict):
        for key, inner in value.items():
            yield f"{field}{{}}", str(key)
            yield from record_strings(inner, f"{field}.{key}" if field else str(key))
    elif isinstance(value, list):
        for inner in value:
            yield from record_strings(inner, f"{field}[]")


def plain_word(name):
    """True for a name an ordinary word could equal by chance: lower-case letters and nothing else."""
    return name.isalpha() and name.islower()


def record_layer(nodes, links, graphs, asset_kinds):
    """The records, told apart and joined to each other.

    A record is any file a records concern holds, whichever concern it is filed under. It
    says what it is in one of RECORD_TYPE_FIELDS; one that does not is typed by the folder
    it sits in, and `record_type_basis` says which of the two it was.

    A record is known by the `id` it declares and by its file name. A string in one record
    that is exactly the name of another is a `refers_to` link carrying the field it was
    found in: EXTRACTED when it is the id the target declares, INFERRED when it only matches
    the target's file name or is a plain word, either of which can happen by chance. An
    object's key counts only as a declared id. A declared id found inside a longer string
    is a `mentions` link, INFERRED. Where two
    records share a name, a reference is followed only when one of them has the type that
    field usually points at, and is then INFERRED. Returns the counts for the report."""
    root = next((g.get("root") or g.get("target") for g in graphs.values() if g.get("root") or g.get("target")), "")
    records = sorted(rel for rel, node in nodes.items() if node["kind"] == "file"
                     and any(asset_kinds.get(concern) == RECORDS for concern in node["concerns"]))
    strings, named = {}, {}
    stats = {"records": len(records), "declared_type": 0, "typed_by_folder": 0, "unread": 0, "links": 0,
             "by_file_name": 0, "mentions": 0, "linked_records": 0, "ambiguous_ids": 0}
    for rel in records:
        data, found = read_record(root, rel) if root else (None, [])
        declared = next((data[f].strip() for f in RECORD_TYPE_FIELDS
                         if data and isinstance(data.get(f), str) and 0 < len(data[f].strip()) <= LABEL_LENGTH
                         and data[f].strip() not in SCHEMA_TYPE_WORDS), None)
        nodes[rel]["record_type"] = declared or os.path.basename(os.path.dirname(rel)) or "."
        nodes[rel]["record_type_basis"] = "declared" if declared else "folder"
        stats["declared_type" if declared else "typed_by_folder"] += 1
        if data is None:
            stats["unread"] += 1
            continue
        strings[rel] = found
        for name, basis in ((os.path.splitext(os.path.basename(rel))[0], "INFERRED"), (data.get("id"), "EXTRACTED")):
            if isinstance(name, str) and len(name) >= RECORD_ID_MIN:
                named.setdefault(name, {})[rel] = "INFERRED" if plain_word(name) else basis
    # A name some record declares as its id belongs to those records, not to a file that happens to share it.
    owners = {name: {rel: b for rel, b in held.items() if b == "EXTRACTED"} or held for name, held in named.items()}
    stats["ambiguous_ids"] = sum(1 for held in owners.values() if len(held) > 1)

    points_at = {}    # field -> how often it names each record type, counted where the name has one owner
    for rel, found in strings.items():
        for field, value in found:
            held = owners.get(value)
            if held and len(held) == 1 and rel not in held:
                row = points_at.setdefault(field, {})
                kind = nodes[next(iter(held))]["record_type"]
                row[kind] = row.get(kind, 0) + 1
    usual = {field: max(sorted(row), key=lambda kind: row[kind]) for field, row in points_at.items()}

    def owner_of(value, field):
        held = owners.get(value) or {}
        if len(held) > 1:    # settled by what the field usually points at: a judgement, so never EXTRACTED
            held = {rel: "INFERRED" for rel in held if nodes[rel]["record_type"] == usual.get(field)}
        return next(iter(held.items())) if len(held) == 1 else (None, None)

    touched = set()
    for rel, found in sorted(strings.items()):
        seen = set()

        def link(target, relation, field, basis):
            if target is None or target == rel or target in seen:
                return
            if field.endswith("{}") and basis != "EXTRACTED":    # a key is a field's name far more often than a record's
                return
            seen.add(target)
            touched.update((rel, target))
            stats["mentions" if relation == "mentions" else "links"] += 1
            stats["by_file_name"] += relation == "refers_to" and basis == "INFERRED"
            links.append({"source": rel, "target": target, "relation": relation, "field": field,
                          "confidence": basis, "confidence_score": 1.0 if basis == "EXTRACTED" else INFERRED_SCORE,
                          "source_file": rel, "concern": concern})

        concern = next(c for c in nodes[rel]["concerns"] if asset_kinds.get(c) == RECORDS)
        for field, value in found:
            target, basis = owner_of(value, field)
            link(target, "refers_to", field, basis)
        for field, value in found:
            if value in owners:
                continue
            for token in set(_ID_TOKEN.findall(value)):
                target, basis = owner_of(token, field)
                if basis == "EXTRACTED":
                    link(target, "mentions", field, "INFERRED")
    stats["linked_records"] = len(touched)
    return stats


def records_report(graph):
    stats = graph["graph"].get("records") or {}
    if not stats.get("records"):
        return []
    types, pairs = {}, {}
    by_id = {node["id"]: node for node in graph["nodes"]}
    for node in graph["nodes"]:
        if node.get("record_type"):
            row = types.setdefault(node["record_type"], {"count": 0, "basis": node["record_type_basis"]})
            row["count"] += 1
    for link in graph["links"]:
        if link["relation"] == "refers_to" and link["confidence"] == "EXTRACTED":
            pair = (by_id[link["source"]]["record_type"], link["field"], by_id[link["target"]]["record_type"])
            pairs[pair] = pairs.get(pair, 0) + 1
    exact = stats["links"] - stats["by_file_name"]
    out = ["## Records", "",
           f"{stats['records']} record files: {stats['declared_type']} say their own type, "
           f"{stats['typed_by_folder']} are typed by the folder they sit in, {stats['unread']} of those because the "
           "file could not be read as a JSON object (missing since the scan, not JSON, a list, or too large). "
           f"{stats['links']} links from one record to another it names: {exact} by the id the other declares "
           f"(EXTRACTED), {stats['by_file_name']} by a file name or a plain word, which can match by chance "
           f"(INFERRED). {stats['mentions']} more where a declared id sits inside a longer string (`mentions`, "
           f"INFERRED). {stats['linked_records']} records have at least one. {stats['ambiguous_ids']} names are "
           "shared by two records; a reference to one is followed only where its field settles which. Records are "
           "read from the root as it is now, so these counts move if the root changed since the scan.", "",
           "| Type | Records | Type comes from |", "|---|---|---|"]
    for name in sorted(types, key=lambda k: (-types[k]["count"], k))[:REPORT_ROWS]:
        out.append(f"| {name} | {types[name]['count']} | {'the record' if types[name]['basis'] == 'declared' else 'its folder'} |")
    if len(types) > REPORT_ROWS:
        out.append(f"| {len(types) - REPORT_ROWS} more types | {sum(types[k]['count'] for k in sorted(types, key=lambda k: (-types[k]['count'], k))[REPORT_ROWS:])} | |")
    if pairs:
        out += ["", "Which records name which by declared id, and the field that holds it: " + "; ".join(
            f"{a} `{field}` to {b} ({count})" for (a, field, b), count in
            sorted(pairs.items(), key=lambda i: (-i[1], i[0]))[:REPORT_ROWS]) + "."]
    return out + [""]


def is_test(source_file):
    return bool(source_file) and bool(_TEST_FILE.search(source_file.replace("\\", "/")))


def not_written_here(source_file, source_class=None):
    """True for code the target holds but did not write: declarations, vendored and generated files."""
    return source_class in ("vendor", "generated") or bool(_NOT_OWN.search((source_file or "").replace("\\", "/")))


def code_role(node):
    """NOT_OWN, TEST or OWN for a code node, from the file it is in."""
    if not_written_here(node.get("source_file"), node.get("source_class")):
        return NOT_OWN
    return TEST if is_test(node.get("source_file")) else OWN


def language(rel):
    """A file's extension, with the JavaScript and TypeScript ones counted as one language."""
    extension = os.path.splitext(rel)[1].lower()
    return ".js" if extension in SCRIPT_EXTENSIONS else extension


def test_subjects(nodes, links):
    """Each test file joined to the file it is about.

    The name gives the candidates: `test_x`, `x_test`, `x.test` and `x.spec` may be about
    the target's own `x` in the same language, where `x` is a file's name, a package's
    folder, or the last folders and name of a file run together (`test_commands_observer`
    for `commands/observer.py`). The test's code decides among them: the candidate it has
    the most links into is its subject, EXTRACTED, and a package counts every link into its
    folder. With no link into any candidate the name is all there is. It is then taken,
    INFERRED, only for a candidate beside the test, or for a lone candidate when the test
    links into none of the target's own code at all, as a test that drives a command does.
    Anything else is about no one file. Returns the counts for the report."""
    named, reached = {}, {}
    for rel, node in nodes.items():
        if node["kind"] == "file" and node.get("role") == OWN:
            parts = os.path.splitext(rel)[0].split("/")
            for path in [parts] + ([parts[:-1]] if parts[-1] in PACKAGE_FILES else []):    # a package file, and its folder
                for count in range(1, min(len(path), SUBJECT_PARTS) + 1):
                    named.setdefault("_".join(path[-count:]), set()).add(rel)
    for link in links:
        a, b = nodes[link["source"]], nodes[link["target"]]
        if a.get("role") == TEST and b.get("role") == OWN:
            row = reached.setdefault(a["source_file"], {})
            row[b["source_file"]] = row.get(b["source_file"], 0) + 1

    def weight(test, candidate):
        into = reached.get(test, {})
        if os.path.splitext(os.path.basename(candidate))[0] not in PACKAGE_FILES:
            return into.get(candidate, 0)
        folder = os.path.dirname(candidate) + "/"
        return sum(count for file, count in into.items() if file.startswith(folder))

    stats = {"test_files": 0, "with_subject": 0, "linked_too": 0}
    for rel in sorted(nodes):
        node = nodes[rel]
        if node["kind"] != "file" or node.get("role") != TEST:
            continue
        stats["test_files"] += 1
        about = _TEST_NAME.match(os.path.splitext(os.path.basename(rel))[0])
        found = sorted(f for f in named.get(next(part for part in about.groups() if part), ())
                       if language(f) == language(rel)) if about else []
        weights = {f: weight(rel, f) for f in found}
        most = max(weights.values(), default=0)
        if most:
            best, linked = [f for f in found if weights[f] == most], True
        else:
            beside, linked = [f for f in found if os.path.dirname(f) == os.path.dirname(rel)], False
            best = beside if len(beside) == 1 else found if not reached.get(rel) else []
        if len(best) != 1:
            continue
        node["tests"] = best[0]
        stats["with_subject"] += 1
        stats["linked_too"] += linked
        links.append({"source": rel, "target": best[0], "relation": "tests",
                      "confidence": "EXTRACTED" if linked else "INFERRED",
                      "confidence_score": 1.0 if linked else INFERRED_SCORE, "source_file": rel,
                      "concern": node["primary_concern"]})
    return stats


def tests_report(graph):
    stats = graph["graph"].get("tests") or {}
    roles = {}
    for node in graph["nodes"]:
        if node.get("role"):
            roles[node["role"]] = roles.get(node["role"], 0) + 1
    if not roles:
        return []
    return ["## Whose code", "",
            f"Of {sum(roles.values())} code nodes, {roles.get(OWN, 0)} are the target's own, {roles.get(TEST, 0)} are in "
            f"test files and {roles.get(NOT_OWN, 0)} are in files it holds but did not write (declarations, vendored "
            f"or generated). {stats.get('with_subject', 0)} of {stats.get('test_files', 0)} test files are joined by name "
            f"to the file they are about; in {stats.get('linked_too', 0)} of those the test's code links into that file "
            "as well, and the others stand on the name alone. A test file with no such join is not a test of nothing: "
            "its name and its links settled on no one file.", ""]


def node_layer(node):
    if node["kind"] in AGENTIC_KINDS:
        return "actors"
    if node["kind"] in ("function", "class", "symbol") or node.get("code_community") is not None:
        return "code"
    return "outside" if node["kind"] == "boundary" else "asset"


def build_graph(graphs, patterns, include_stdlib=False, asset_kinds=None, group_by="concern", code_dir=None):
    """The node-link graph for a loaded scan. Pure: no I/O."""
    asset_kinds = asset_kinds or {}
    stages = best_stages(graphs)
    primary = primary_concerns(graphs, stages, asset_kinds)
    nodes, links = {}, []
    skipped = {"stdlib_imports": 0, "markers": 0, "long_targets": 0, "junk_pointers": 0, "merged_pointers": 0,
               "scan_imports_replaced": 0, "code_links_leaving_root": 0}

    for concern, graph in graphs.items():
        for node in graph.get("nodes") or []:
            rel = node["id"]
            entry = nodes.setdefault(rel, {
                "id": rel, "label": file_label(rel), "file_type": file_type(rel), "source_file": rel,
                "kind": "file", "source_class": node.get("source_class"), "concerns": [],
                "evidence_stage": "candidate", "primary_concern": primary[rel],
            })
            entry["concerns"].append(concern)
            stage = stages.get((concern, rel), "candidate")
            if STAGE_RANK[stage] > STAGE_RANK[entry["evidence_stage"]]:
                entry["evidence_stage"] = stage

    for concern, graph in graphs.items():
        stdlib = {(f.get("file"), f.get("import_target")) for f in graph.get("findings") or []
                  if f.get("import_class") == "stdlib"}
        seen = set()
        for edge in graph.get("edges") or []:
            src, dst, kind = edge.get("src"), str(edge.get("dst")), edge.get("kind") or "relates_to"
            if src not in nodes:
                continue
            if kind in MARKER_KINDS:
                skipped["markers"] += 1
                continue
            if len(dst) > MAX_TARGET_CHARS or "\n" in dst:
                skipped["long_targets"] += 1
                continue
            if (src, dst) in stdlib and not include_stdlib:
                skipped["stdlib_imports"] += 1
                continue
            if (src, dst, kind) in seen:
                continue
            seen.add((src, dst, kind))
            target = dst if dst in nodes else module_file(dst, nodes) if kind == "python_import" else None
            target = target or f"external:{dst}"
            if target not in nodes:
                nodes[target] = {
                    "id": target, "label": dst, "file_type": "external", "source_file": "",
                    "kind": "external", "source_class": None, "concerns": [concern],
                    "evidence_stage": None, "primary_concern": concern,
                }
            elif nodes[target]["kind"] == "external" and concern not in nodes[target]["concerns"]:
                nodes[target]["concerns"].append(concern)
            basis, score = link_basis(concern, edge, graph, stages)
            links.append({
                "source": src, "target": target, "relation": kind, "confidence": basis,
                "confidence_score": score, "source_file": src, "concern": concern,
            })

    if code_dir:
        links = merge_code(nodes, links, skipped, code_dir)
    agentic_layer(nodes, links, graphs)
    records = record_layer(nodes, links, graphs, asset_kinds)
    for node in nodes.values():
        if node_layer(node) == "code":
            node["role"] = code_role(node)
    tests = test_subjects(nodes, links)

    pointer_ids, pointed = {}, set()
    for pointer in patterns.get("boundary_pointers") or []:
        path = clean_pointer(str(pointer.get("reference")))
        if path is None:
            skipped["junk_pointers"] += 1
            continue
        pid = pointer_ids.get(path.lower())
        if pid is None:
            pid = pointer_ids[path.lower()] = f"boundary:{pointer.get('id')}"
            nodes[pid] = {
                "id": pid, "label": path, "file_type": "boundary", "source_file": "",
                "kind": "boundary", "source_class": pointer.get("source_class"), "concerns": [],
                "evidence_stage": None, "primary_concern": BOUNDARY_COMMUNITY,
                "relation": pointer.get("relation"), "exists": pointer.get("exists"),
                "disposition": pointer.get("disposition"),
            }
        else:
            skipped["merged_pointers"] += 1
        for src in pointer.get("referenced_from") or []:
            if src in nodes and (src, pid) not in pointed:
                pointed.add((src, pid))
                links.append({
                    "source": src, "target": pid, "relation": "points_outside_root",
                    "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": src,
                    "concern": BOUNDARY_COMMUNITY,
                })

    # A file other files demonstrably depend on is part of the system even when the scan
    # found nothing inside it (an empty __init__.py): file it with the link that proves it.
    for link in links:
        target = nodes[link["target"]]
        if (link["confidence"] == "EXTRACTED" and link["concern"] != BOUNDARY_COMMUNITY
                and target["kind"] == "file" and target["evidence_stage"] == "candidate"
                and target["primary_concern"] in asset_kinds):
            target["primary_concern"] = link["concern"]

    for node in nodes.values():
        node["concerns"] = sorted(node["concerns"])
        concern = node["primary_concern"]
        node["asset_kind"] = concern if concern == BOUNDARY_COMMUNITY else asset_kinds.get(concern, SYSTEM_DESCRIPTION)
        node["layer"] = node_layer(node)
    key = "asset_kind" if group_by == "asset" else "primary_concern"
    names = sorted({n[key] for n in nodes.values()})
    index = {name: i for i, name in enumerate(names)}
    for node in nodes.values():
        node["community"] = index[node[key]]
    links.sort(key=lambda l: (l["source"], l["target"], l["relation"], l["concern"]))
    graph = {
        "directed": True, "multigraph": True,
        "graph": {"community_labels": {str(i): name for name, i in index.items()}, "grouped_by": group_by,
                  "skipped": skipped, "records": records, "tests": tests},
        "nodes": [nodes[key] for key in sorted(nodes)],
        "links": links,
    }
    graph["graph"]["root"] = next((g.get("root") or g.get("target") for g in graphs.values()
                                   if g.get("root") or g.get("target")), None)
    graph["graph"]["hyperedges"] = hyperedges(graph)
    graph["graph"]["partitions"] = partition_stats(graph)
    return graph


def hyperedges(graph):
    """Groups of three or more files tied by one shared target, in graphify's hyperedge shape."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    sources = {}
    for link in graph["links"]:
        sources.setdefault((link["target"], link["relation"]), []).append(link)
    rows = []
    for (target, relation), members in sorted(sources.items()):
        files = sorted({link["source"] for link in members})
        if len(files) < HYPEREDGE_MIN:
            continue
        extracted = all(link["confidence"] == "EXTRACTED" for link in members)
        rows.append({
            "id": f"shared:{relation}:{target}", "label": f"{relation.replace('_', ' ')} {by_id[target]['label']}",
            "relation": relation, "nodes": files + [target],
            "confidence": "EXTRACTED" if extracted else "INFERRED",
            "confidence_score": 1.0 if extracted else INFERRED_SCORE,
        })
    return rows


def modularity(weights, degree, total, group_of):
    """Newman's Q for one partition of an undirected weighted graph."""
    inside, group_degree = {}, {}
    for (a, b), weight in weights.items():
        if group_of[a] == group_of[b]:
            inside[group_of[a]] = inside.get(group_of[a], 0) + weight
    for node, value in degree.items():
        group_degree[group_of[node]] = group_degree.get(group_of[node], 0) + value
    return sum(inside.get(g, 0) / total - (d / (2 * total)) ** 2 for g, d in group_degree.items())


def detected_partition(graph):
    """Louvain communities when networkx is importable; None otherwise. Nothing is installed for it."""
    try:
        import networkx
    except ImportError:
        return None
    net = networkx.Graph()
    net.add_nodes_from(node["id"] for node in graph["nodes"])
    for link in graph["links"]:
        previous = net.get_edge_data(link["source"], link["target"], {"weight": 0})["weight"]
        net.add_edge(link["source"], link["target"], weight=previous + 1)
    return {node: i for i, group in enumerate(networkx.community.louvain_communities(net, seed=0)) for node in group}


def partition_stats(graph):
    """For each way of grouping the nodes: its modularity, and where that sits among
    NULL_DRAWS shuffles of the same group sizes over the same links (a permutation test,
    seeded). A z near 0 means the grouping says nothing about which nodes are linked."""
    weights, degree = {}, {node["id"]: 0 for node in graph["nodes"]}
    for link in graph["links"]:
        pair = tuple(sorted((link["source"], link["target"])))
        weights[pair] = weights.get(pair, 0) + 1
        degree[link["source"]] += 1
        degree[link["target"]] += 1
    total = sum(weights.values())
    partitions = {
        "concern": {node["id"]: node["primary_concern"] for node in graph["nodes"]},
        "asset kind": {node["id"]: node["asset_kind"] for node in graph["nodes"]},
    }
    if any(node.get("code_community") is not None for node in graph["nodes"]):
        partitions["code community (Leiden, graphify)"] = {
            node["id"]: node["code_community"] if node.get("code_community") is not None else "not code"
            for node in graph["nodes"]}
    else:
        detected = detected_partition(graph)
        if detected is not None:
            partitions["detected (Louvain)"] = detected
    draws_wanted = max(50, min(NULL_DRAWS, MAX_SHUFFLE_WORK // max(1, len(weights) * len(partitions))))
    stats = {}
    for name, group_of in partitions.items():
        row = {"groups": len(set(group_of.values())), "links": total, "shuffles": draws_wanted, "modularity": None,
               "null_mean": None, "null_sd": None, "z": None, "p": None}
        if total and row["groups"] > 1:
            observed = modularity(weights, degree, total, group_of)
            rng, ids, labels = random.Random(0), sorted(group_of), [group_of[k] for k in sorted(group_of)]
            draws = []
            for _ in range(draws_wanted):
                rng.shuffle(labels)
                draws.append(modularity(weights, degree, total, dict(zip(ids, labels))))
            mean = sum(draws) / len(draws)
            sd = (sum((d - mean) ** 2 for d in draws) / len(draws)) ** 0.5
            row.update({
                "modularity": round(observed, 4), "null_mean": round(mean, 4), "null_sd": round(sd, 4),
                "z": round((observed - mean) / sd, 2) if sd else None,
                "p": round((sum(1 for d in draws if d >= observed) + 1) / (len(draws) + 1), 4),
            })
        stats[name] = row
    return stats


def load_claims(audit_path):
    """unit -> its claims, each with where it stands and its verdict, from an audit ledger."""
    import audit as audit_mod
    by_unit = {}
    for claim in read_json(audit_path)["claims"]:
        if not claim.get("unit") or claim.get("validates"):
            continue
        verdict = claim["stages"]["verdict"][-1]["verdict"] if claim["stages"]["verdict"] else None
        by_unit.setdefault(claim["unit"], []).append({
            "id": claim["id"], "statement": claim["statement"], "state": audit_mod.claim_state(claim),
            "verdict": verdict, "source": claim["source"]})
    return by_unit


def claims_report(graph):
    claims = graph["graph"].get("claims") or {}
    if not claims:
        return []
    out = ["## What the analysis claims", "", "| Unit | Claim | Verdict | Stands at | Statement |", "|---|---|---|---|---|"]
    for unit in sorted(claims):
        for claim in claims[unit]:
            out.append(f"| `{unit}` | {claim['id']} | {claim['verdict'] or ''} | {claim['state']} | {claim['statement']} |")
    return out + [""]


def layer_report(graph):
    """The three layers and what the code and agentic passes found, as report lines."""
    nodes, links = graph["nodes"], graph["links"]
    by_id = {node["id"]: node for node in nodes}
    out = ["## Layers", "", "| Layer | Nodes | Of which |", "|---|---|---|"]
    for layer in ("actors", "code", "asset", "outside"):
        members = [n for n in nodes if n["layer"] == layer]
        kinds = {}
        for node in members:
            kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
        detail = ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items(), key=lambda i: (-i[1], i[0])))
        out.append(f"| {layer} | {len(members)} | {detail} |")
    crossing = {}
    for link in links:
        pair = (by_id[link["source"]]["layer"], by_id[link["target"]]["layer"])
        if pair[0] != pair[1]:
            crossing[pair] = crossing.get(pair, 0) + 1
    if crossing:
        out += ["", "Links from one layer to another: " + "; ".join(
            f"{a} to {b} {count}" for (a, b), count in sorted(crossing.items(), key=lambda i: -i[1])) + "."]
    out.append("")
    agentic = [n for n in nodes if n["kind"] in ("agent", "skill", "hook", "workflow")]
    if agentic:
        reach = {}
        for link in links:
            if by_id[link["source"]]["kind"] in ("agent", "skill", "hook", "workflow") \
                    and by_id[link["target"]]["kind"] == "file":
                reach.setdefault(link["source"], []).append((link["relation"], link["confidence"], link["target"]))
        out += ["## Actors and triggers", "", "| Kind | Name | Defined in | Reaches |", "|---|---|---|---|"]
        for node in sorted(agentic, key=lambda n: (n["kind"], n["label"])):
            rows = reach.get(node["id"], [])
            shown = ", ".join(f"{relation} `{target}` ({basis})" for relation, basis, target in rows[:3])
            if len(rows) > 3:
                shown += f" and {len(rows) - 3} more"
            out.append(f"| {node['kind']} | {node['label']} | `{node['source_file']}` | {shown or 'no scanned file'} |")
        out.append("")
    definitions = [n for n in nodes if n["kind"] in ("function", "class", "symbol")]
    if definitions:
        relations = {}
        for link in links:
            if by_id[link["source"]]["layer"] == "code" and by_id[link["target"]]["layer"] == "code":
                row = relations.setdefault(link["relation"], {"EXTRACTED": 0, "INFERRED": 0})
                row[link["confidence"]] += 1
        counts = {}
        for node in definitions:
            counts[node["kind"]] = counts.get(node["kind"], 0) + 1
        modules = sum(1 for n in nodes if n["kind"] == "file" and n.get("code_community") is not None)
        out += ["## Code, parsed", "",
                f"{modules} modules, " + ", ".join(f"{count} {kind}s" if kind != "class" else f"{count} classes"
                                                    for kind, count in sorted(counts.items(), key=lambda i: -i[1]))
                + f", in {len({n.get('code_community') for n in nodes if n.get('code_community') is not None})} "
                "communities found from the links alone.", "",
                "| Relation | EXTRACTED | INFERRED |", "|---|---|---|"]
        for relation in sorted(relations, key=lambda k: -sum(relations[k].values())):
            out.append(f"| {relation} | {relations[relation]['EXTRACTED']} | {relations[relation]['INFERRED']} |")
        called = {}
        for link in links:
            if link["relation"] in ("calls", "indirect_call") and by_id[link["target"]]["kind"] in ("function", "class"):
                called[link["target"]] = called.get(link["target"], 0) + 1
        out += ["", "Most called: " + "; ".join(
            f"`{by_id[k]['label']}` in `{by_id[k]['source_file']}` ({called[k]})"
            for k in sorted(called, key=lambda k: (-called[k], k))[:8]) + ".", ""]
        linted = [n for n in nodes if n.get("lint")]
        if linted:
            codes, files = {}, {}
            for node in linted:
                if node["kind"] == "file":
                    files[node["id"]] = sum(node["lint"].values())
                    for code, count in node["lint"].items():
                        codes[code] = codes.get(code, 0) + count
            held = sorted((n for n in linted if n["kind"] != "file"), key=lambda n: -sum(n["lint"].values()))
            out += ["## Lint", "",
                    f"{sum(files.values())} findings in {len(files)} files. By rule: " + ", ".join(
                        f"{code} {count}" for code, count in sorted(codes.items(), key=lambda i: -i[1])[:8]) + ".", "",
                    "Files with the most: " + "; ".join(
                        f"`{rel}` ({count})" for rel, count in sorted(files.items(), key=lambda i: -i[1])[:6]) + ".", "",
                    "Definitions with the most: " + "; ".join(
                        f"`{n['label']}` in `{n['source_file']}` ({sum(n['lint'].values())})" for n in held[:6]) + ".", ""]
    declared = [n for n in nodes if n.get("declared")]
    if declared:
        # An import names a package by its first segment (two for a scoped npm name); a
        # relative import names a file of the target's own, not a package.
        imported = set()
        for link in links:
            name = by_id[link["target"]]["label"]
            if link["relation"] in SCAN_IMPORT_KINDS and by_id[link["target"]]["kind"] == "external" \
                    and name and not name.startswith((".", "/", "node:")):
                parts = name.split("/")
                imported.add(package_key("/".join(parts[:2]) if name.startswith("@") else parts[0].split(".")[0]))
        declared_keys = {package_key(n["label"]) for n in declared}
        unused = sorted(n["label"] for n in declared if package_key(n["label"]) not in imported)
        undeclared = sorted(imported - declared_keys)
        out += ["## Dependencies", "",
                f"{len(declared)} packages declared in manifests; {len(imported)} external names imported.", "",
                f"Declared and not seen imported ({len(unused)}): {', '.join(unused[:25]) or 'none'}.", "",
                f"Imported and not declared ({len(undeclared)}): {', '.join(undeclared[:25]) or 'none'}.", "",
                "A package whose import name differs from its distribution name shows in both lists.", ""]
    return out


def degrees(graph):
    count = {node["id"]: 0 for node in graph["nodes"]}
    for link in graph["links"]:
        count[link["source"]] += 1
        count[link["target"]] += 1
    return count


def render_report(graph, target):
    nodes, links = graph["nodes"], graph["links"]
    labels = graph["graph"]["community_labels"]
    skipped = graph["graph"]["skipped"]
    by_id = {node["id"]: node for node in nodes}
    degree = degrees(graph)
    basis = {"EXTRACTED": 0, "INFERRED": 0}
    for link in links:
        basis[link["confidence"]] += 1
    files = [n for n in nodes if n["kind"] == "file"]
    out = [f"# Graph report: {target}", ""]
    out += [f"- {len(nodes)} nodes: {len(files)} files, "
            f"{sum(1 for n in nodes if n['kind'] == 'external')} external targets, "
            f"{sum(1 for n in nodes if n['kind'] == 'boundary')} boundary pointers",
            f"- {len(links)} links: {basis['EXTRACTED']} EXTRACTED (a structural or behavioral finding backs it), "
            f"{basis['INFERRED']} INFERRED (a pattern match only)",
            f"- left out: {skipped['stdlib_imports']} standard-library imports, {skipped['markers']} markers, "
            f"{skipped['long_targets']} captured values too long to be a target, "
            f"{skipped['junk_pointers']} outside-the-root pointers that name nothing "
            f"({skipped['merged_pointers']} more merged as second spellings of one path)", ""]
    out += claims_report(graph)
    out += layer_report(graph)
    out += tests_report(graph)
    out += records_report(graph)
    out += ["## Most connected", ""]
    for node_id in sorted(degree, key=lambda k: (-degree[k], k))[:10]:
        if degree[node_id]:
            out.append(f"- `{by_id[node_id]['label']}` ({by_id[node_id]['kind']}): {degree[node_id]} links")
    out += ["", "## Communities", "", "| Community | Nodes | Evidenced files | Pattern-match-only files |", "|---|---|---|---|"]
    for key in sorted(labels, key=int):
        members = [n for n in nodes if n["community"] == int(key)]
        member_files = [n for n in members if n["kind"] == "file"]
        evidenced = sum(1 for n in member_files if n["evidence_stage"] in EVIDENCED)
        out.append(f"| {labels[key]} | {len(members)} | {evidenced} | {len(member_files) - evidenced} |")
    cross = {}
    for link in links:
        a, b = by_id[link["source"]]["community"], by_id[link["target"]]["community"]
        if a != b:
            pair = tuple(sorted((labels[str(a)], labels[str(b)])))
            cross[pair] = cross.get(pair, 0) + 1
    if cross:
        out += ["", "## Links between communities", ""]
        for pair in sorted(cross, key=lambda p: (-cross[p], p)):
            out.append(f"- {pair[0]} and {pair[1]}: {cross[pair]}")
    out += ["", "## Which grouping the links support", "",
            f"Modularity of each grouping over the {len(links)} links, against "
            f"{next(iter(graph['graph']['partitions'].values()))['shuffles']} shuffles of the same group sizes. "
            "A grouping detected from these links is fitted to them, so its score is a ceiling, not a test.", "",
            "| Grouping | Groups | Modularity | Shuffled mean | Shuffled sd | z | p |", "|---|---|---|---|---|---|---|"]
    for name, row in graph["graph"]["partitions"].items():
        out.append(f"| {name} | {row['groups']} | {row['modularity']} | {row['null_mean']} | {row['null_sd']} | "
                   f"{row['z']} | {row['p']} |")
    kinds = {}
    for link in links:
        kinds.setdefault(link["relation"], {"EXTRACTED": 0, "INFERRED": 0})[link["confidence"]] += 1
    out += ["", "## Links by relation", "", "| Relation | EXTRACTED | INFERRED |", "|---|---|---|"]
    for relation in sorted(kinds, key=lambda k: (-sum(kinds[k].values()), k)):
        out.append(f"| {relation} | {kinds[relation]['EXTRACTED']} | {kinds[relation]['INFERRED']} |")
    if graph["graph"]["hyperedges"]:
        groups = sorted(graph["graph"]["hyperedges"], key=lambda e: (-len(e["nodes"]), e["id"]))
        out += ["", "## Groups of three or more", "",
                f"{len(groups)} groups of files share one target; the largest {min(len(groups), REPORT_ROWS)}:", ""]
        for edge in groups[:REPORT_ROWS]:
            out.append(f"- {edge['label']} ({edge['confidence']}): {len(edge['nodes']) - 1} files")
    boundary = [n for n in nodes if n["kind"] == "boundary"]
    if boundary:
        out += ["", "## Outside the root", ""]
        for node in boundary:
            sources = sorted(l["source"] for l in links if l["target"] == node["id"])
            named = ", ".join(sources[:SOURCE_ROWS]) or "no scanned file"
            if len(sources) > SOURCE_ROWS:
                named += f" and {len(sources) - SOURCE_ROWS} more"
            out.append(f"- `{node['label']}` ({node.get('relation')}, disposition {node.get('disposition')}): "
                       f"named by {named}")
    out.append("")
    return "\n".join(out)


def card_id(node_id, used):
    base = _ID_UNSAFE.sub("-", str(node_id))
    cid, n = base, 1
    while cid in used:
        n += 1
        cid = f"{base}-{n}"
    used.add(cid)
    return cid


def wire_label(relation):
    label = str(relation).replace("_", " ")
    return label if len(label) <= LABEL_LENGTH else label[: LABEL_LENGTH - 1] + ELLIPSIS


def graph_to_sov(graph, title):
    """The Schematically document for a graph built by build_graph. Pure: no I/O."""
    labels = graph["graph"]["community_labels"]
    used = {f"community-{key}" for key in labels}
    card_of, cards, members = {}, [], {}
    for node in graph["nodes"]:
        cid = card_of[node["id"]] = card_id(node["id"], used)
        if node["kind"] == "file":
            symbol = "act" if node["evidence_stage"] in EVIDENCED else "hold"
            subtitle = f"{node['primary_concern']}, {node['evidence_stage']}, {node['source_file']}"
        else:
            symbol = "ground"
            subtitle = node["kind"] if node["kind"] == "external" else f"outside the root, {node.get('relation')}"
        cards.append({"id": cid, "symbolId": symbol, "config": {"label": node["label"], "subtitle": subtitle}})
        members.setdefault(node["community"], []).append(cid)
    groups = [{
        "id": f"community-{key}", "symbolId": "group", "canvasId": CANVAS,
        "config": {"label": labels[key], "members": sorted(members.get(int(key), []))},
    } for key in sorted(labels, key=int) if members.get(int(key))]
    wires, wire_ids = [], set()
    for link in graph["links"]:
        a, b = card_of[link["source"]], card_of[link["target"]]
        wires.append({
            "id": card_id(f"w-{a}-{b}-{link['relation']}", wire_ids), "a": a, "aSide": "out", "b": b, "bSide": "in",
            "canvasId": CANVAS, "config": {"label": wire_label(link["relation"]), "basis": link["confidence"]},
        })
    return {
        "schema": SCHEMA, "id": "system-cartographer", "revision": 0, "meta": {"title": title},
        "references": [], "components": sorted(cards, key=lambda c: c["id"]) + groups, "wires": wires,
    }


def graph_to_overview(graph, title):
    """The same graph at the height a person can read: one card per community, one wire
    per pair of communities, labelled with how many links run between them. Pure."""
    labels = graph["graph"]["community_labels"]
    by_id = {node["id"]: node for node in graph["nodes"]}
    sizes, files, evidenced, inside, between = {}, {}, {}, {}, {}
    for node in graph["nodes"]:
        c = node["community"]
        sizes[c] = sizes.get(c, 0) + 1
        if node["kind"] == "file":
            files[c] = files.get(c, 0) + 1
            evidenced[c] = evidenced.get(c, 0) + (node["evidence_stage"] in EVIDENCED)
    for link in graph["links"]:
        a, b = by_id[link["source"]]["community"], by_id[link["target"]]["community"]
        if a == b:
            inside[a] = inside.get(a, 0) + 1
            continue
        row = between.setdefault((a, b), {"EXTRACTED": 0, "INFERRED": 0})
        row[link["confidence"]] += 1
    cards = []
    for key in sorted(labels, key=int):
        c = int(key)
        if not sizes.get(c):
            continue
        subtitle = f"{inside.get(c, 0)} links inside"
        if files.get(c):
            subtitle += f", {evidenced[c]} of {files[c]} files evidenced"
        # The count sits in the label: a subtitle is hidden when the card is drawn small.
        cards.append({"id": f"community-{key}", "symbolId": "act" if evidenced.get(c) else "hold",
                      "config": {"label": f"{labels[key]} ({sizes[c]})", "subtitle": subtitle}})
    wires = []
    for (a, b), row in sorted(between.items()):
        total = row["EXTRACTED"] + row["INFERRED"]
        label = f"{total} links" if total != 1 else "1 link"
        if row["INFERRED"]:
            label += f", {row['INFERRED']} inferred"
        wires.append({
            "id": f"w-community-{a}-community-{b}", "a": f"community-{a}", "aSide": "out",
            "b": f"community-{b}", "bSide": "in", "canvasId": CANVAS,
            "config": {"label": label, "basis": "EXTRACTED" if row["EXTRACTED"] >= row["INFERRED"] else "INFERRED"},
        })
    return {
        "schema": SCHEMA, "id": "system-cartographer-overview", "revision": 0,
        "meta": {"title": f"{title}: overview"}, "references": [], "components": cards, "wires": wires,
    }


def code_overview(graph, title):
    """The parsed code at the height of its communities: the largest as cards named for
    their busiest definition and the folder most of them sit in, wired by the calls,
    imports and uses that cross between them."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    members, degree = {}, degrees(graph)
    for node in graph["nodes"]:
        if node.get("code_community") is not None:
            members.setdefault(node["code_community"], []).append(node)
    if not members:
        return None
    chosen = sorted(members, key=lambda c: (-len(members[c]), c))[:CODE_CARDS]
    cards = []
    for community in chosen:
        rows = members[community]
        folders = {}
        for node in rows:
            folder = os.path.dirname(node["source_file"]) or "."
            folders[folder] = folders.get(folder, 0) + 1
        folder = max(sorted(folders), key=lambda f: folders[f])
        top = max(sorted(rows, key=lambda n: n["id"]), key=lambda n: degree[n["id"]])
        lint = sum(sum(n["lint"].values()) for n in rows if n.get("lint") and n["kind"] != "file")
        claims = (graph["graph"].get("claims") or {}).get(f"code-{community}") or []
        verdicts = ", ".join(f"{c['id']} {c['verdict'] or c['state']}" for c in claims)
        cards.append({"id": f"code-{community}", "symbolId": "act", "config": {
            "label": f"{folder}: {top['label']} ({len(rows)})" + (f" [{len(claims)} claims]" if claims else ""),
            "subtitle": (verdicts + ", " if verdicts else "") + f"{len(folders)} folders"
                        + (f", {lint} lint findings" if lint else "")}})
    between = {}
    for link in graph["links"]:
        if link["relation"] in STRUCTURAL_RELATIONS:
            continue
        a, b = by_id[link["source"]].get("code_community"), by_id[link["target"]].get("code_community")
        if a is None or b is None or a == b or a not in chosen or b not in chosen:
            continue
        row = between.setdefault((a, b), {})
        row[link["relation"]] = row.get(link["relation"], 0) + 1
    wires = []
    for (a, b), row in sorted(between.items(), key=lambda i: (-sum(i[1].values()), i[0]))[:CODE_WIRES]:
        top = max(sorted(row), key=lambda r: row[r])
        wires.append({"id": f"w-code-{a}-code-{b}", "a": f"code-{a}", "aSide": "out", "b": f"code-{b}", "bSide": "in",
                      "canvasId": CANVAS, "config": {"label": wire_label(f"{sum(row.values())} {top}"),
                                                     "basis": "EXTRACTED"}})
    return {"schema": SCHEMA, "id": "system-cartographer-code", "revision": 0,
            "meta": {"title": f"{title}: code, {len(chosen)} largest of {len(members)} communities"},
            "references": [], "components": cards, "wires": wires}


def agentic_overview(graph, title):
    """Who acts and what it runs: every agent, skill, hook and workflow as a card, the
    tools agents are granted, and the files their commands and instructions name."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    actors = [n for n in graph["nodes"] if n["kind"] in AGENTIC_KINDS]
    if not actors:
        return None
    symbols = {"agent": "act", "skill": "buffer", "hook": "gate", "workflow": "clock", "tool": "hold"}
    used, card_of, cards, wires, wire_ids = set(), {}, [], [], set()

    def card(node, symbol, subtitle):
        if node["id"] not in card_of:
            card_of[node["id"]] = card_id(node["id"], used)
            cards.append({"id": card_of[node["id"]], "symbolId": symbol,
                          "config": {"label": node["label"], "subtitle": subtitle}})
        return card_of[node["id"]]

    # A tool is granted to most agents, so drawn as a card it is all wires: it goes in the subtitle.
    tools = {}
    for link in graph["links"]:
        if link["relation"] == "may_use":
            tools.setdefault(link["source"], []).append(by_id[link["target"]]["label"])
    for node in actors:
        if node["kind"] == "tool":
            continue
        granted = f", may use {', '.join(sorted(tools[node['id']]))}" if node["id"] in tools else ""
        card(node, symbols[node["kind"]], f"{node['kind']}, {node['source_file']}{granted}")
    for link in graph["links"]:
        source, target = by_id[link["source"]], by_id[link["target"]]
        if source["kind"] not in AGENTIC_KINDS or "tool" in (source["kind"], target["kind"]):
            continue
        if target["kind"] not in AGENTIC_KINDS:
            if target["kind"] != "file":
                continue
            card(target, "ground", f"{target['primary_concern']}, {target['source_file']}")
        a, b = card_of[source["id"]], card_of[target["id"]]
        wires.append({"id": card_id(f"w-{a}-{b}-{link['relation']}", wire_ids), "a": a, "aSide": "out", "b": b,
                      "bSide": "in", "canvasId": CANVAS,
                      "config": {"label": wire_label(link["relation"]), "basis": link["confidence"]}})
    return {"schema": SCHEMA, "id": "system-cartographer-actors", "revision": 0,
            "meta": {"title": f"{title}: agents, skills, hooks and workflows"},
            "references": [], "components": cards, "wires": wires}


def write_sov(document, path, schematically_dir=None, node="node"):
    """Write the document; lay it out first when a Schematically checkout is given."""
    text = json.dumps(document, indent=1, ensure_ascii=False) + "\n"
    if not schematically_dir:
        write_text(path, text)
        return False
    script = os.path.join(schematically_dir, "scripts", "layout_sov.mjs")
    node_exe = shutil.which(node)
    if not os.path.isfile(script):
        raise SystemExit(f"graph_export: layout script not found: {script}")
    if node_exe is None:
        raise SystemExit(f"graph_export: {node!r} is not on PATH; drop --schematically to write the document unplaced")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".cartographer-", suffix=".sov")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        proc = subprocess.run([node_exe, script, tmp, "--out", path], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise SystemExit(f"graph_export: layout_sov.mjs exited {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scan-dir", required=True, help="the --out-dir of a cartographer_scan.py run")
    parser.add_argument("--out-dir", required=True, help="where graph.json, GRAPH_REPORT.md and system.sov land")
    parser.add_argument("--schematically", default=os.environ.get("SCHEMATICALLY_DIR"),
                        help="a Schematically checkout; lays the document out with its scripts/layout_sov.mjs "
                             "(default: the SCHEMATICALLY_DIR environment variable)")
    parser.add_argument("--registry", action="append", default=[],
                        help="a concern registry to read asset kinds from, repeatable "
                             "(default: every *.registry.json beside this skill's references)")
    parser.add_argument("--group-by", choices=GROUPINGS, default="concern",
                        help="what a community is: a concern, or an asset kind (the system description is one)")
    parser.add_argument("--code-dir", default=None,
                        help="the --out-dir of a code_graph.py run: merges parsed functions, classes, calls and "
                             "imports, lint findings and declared dependencies into the map")
    parser.add_argument("--audit", default=None,
                        help="an audit.json: puts each unit's claims and verdicts on the map and in the report")
    parser.add_argument("--full-document", action="store_true",
                        help=f"write system.sov even above {FULL_DOCUMENT_NODES} nodes")
    parser.add_argument("--include-stdlib", action="store_true", help="keep standard-library imports as links")
    parser.add_argument("--title", default=None, help="the document title (default: the scanned target's folder name)")
    args = parser.parse_args()

    graphs, patterns = load_scan(args.scan_dir)
    if not graphs:
        raise SystemExit(f"graph_export: no concern graphs in {args.scan_dir}; run cartographer_scan.py first")
    target = next(iter(graphs.values())).get("target") or args.scan_dir
    title = args.title or os.path.basename(os.path.normpath(target))
    references = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
    registries = args.registry or sorted(
        os.path.join(references, name) for name in os.listdir(references) if name.endswith(".registry.json"))
    graph = build_graph(graphs, patterns, include_stdlib=args.include_stdlib,
                        asset_kinds=load_asset_kinds(registries), group_by=args.group_by,
                        code_dir=args.code_dir)
    if args.audit:
        graph["graph"]["claims"] = load_claims(args.audit)
    graph_path = os.path.join(args.out_dir, "graph.json")
    report_path = os.path.join(args.out_dir, "GRAPH_REPORT.md")
    sov_path = os.path.join(args.out_dir, "system.sov")
    write_text(graph_path, json.dumps(graph, indent=2, ensure_ascii=False) + "\n")
    write_text(report_path, render_report(graph, title))
    laid_out, documents = False, {}
    if len(graph["nodes"]) <= FULL_DOCUMENT_NODES or args.full_document:
        laid_out = write_sov(graph_to_sov(graph, title), sov_path, args.schematically)
    else:
        # Too many nodes to read as one drawing; an older system.sov here would describe another graph.
        if os.path.exists(sov_path):
            os.unlink(sov_path)
        sov_path = None
    overview_path = os.path.join(args.out_dir, "system-overview.sov")
    laid_out = write_sov(graph_to_overview(graph, title), overview_path, args.schematically) or laid_out
    for name, document in (("system-actors.sov", agentic_overview(graph, title)),
                           ("system-code.sov", code_overview(graph, title))):
        if document is not None:
            documents[name] = os.path.join(args.out_dir, name)
            write_sov(document, documents[name], args.schematically)
    basis = {"EXTRACTED": 0, "INFERRED": 0}
    for link in graph["links"]:
        basis[link["confidence"]] += 1
    json.dump({
        "graph": graph_path, "report": report_path, "sov": sov_path, "overview": overview_path, **documents,
        "layers": {layer: sum(1 for n in graph["nodes"] if n["layer"] == layer)
                   for layer in ("actors", "code", "asset", "outside")},
        "laid_out": laid_out,
        "nodes": len(graph["nodes"]), "links": len(graph["links"]), "basis": basis,
        "communities": len(graph["graph"]["community_labels"]), "grouped_by": args.group_by,
        "hyperedges": len(graph["graph"]["hyperedges"]), "partitions": graph["graph"]["partitions"],
        "skipped": graph["graph"]["skipped"],
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
