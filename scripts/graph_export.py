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
CODE_EXTENSIONS = frozenset({".py", ".js", ".mjs", ".ts", ".tsx", ".sh", ".ps1", ".go", ".rs", ".cs", ".java", ".rb"})
LABEL_LENGTH = 28
ELLIPSIS = "…"

_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


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


def build_graph(graphs, patterns, include_stdlib=False, asset_kinds=None, group_by="concern"):
    """The node-link graph for a loaded scan. Pure: no I/O."""
    asset_kinds = asset_kinds or {}
    stages = best_stages(graphs)
    primary = primary_concerns(graphs, stages, asset_kinds)
    nodes, links = {}, []
    skipped = {"stdlib_imports": 0, "markers": 0, "long_targets": 0}

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

    for pointer in patterns.get("boundary_pointers") or []:
        pid = f"boundary:{pointer.get('id')}"
        nodes[pid] = {
            "id": pid, "label": str(pointer.get("reference")), "file_type": "boundary", "source_file": "",
            "kind": "boundary", "source_class": pointer.get("source_class"), "concerns": [],
            "evidence_stage": None, "primary_concern": BOUNDARY_COMMUNITY,
            "relation": pointer.get("relation"), "exists": pointer.get("exists"),
            "disposition": pointer.get("disposition"),
        }
        for src in pointer.get("referenced_from") or []:
            if src in nodes:
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
    key = "asset_kind" if group_by == "asset" else "primary_concern"
    names = sorted({n[key] for n in nodes.values()})
    index = {name: i for i, name in enumerate(names)}
    for node in nodes.values():
        node["community"] = index[node[key]]
    links.sort(key=lambda l: (l["source"], l["target"], l["relation"], l["concern"]))
    graph = {
        "directed": True, "multigraph": True,
        "graph": {"community_labels": {str(i): name for name, i in index.items()}, "grouped_by": group_by,
                  "skipped": skipped},
        "nodes": [nodes[key] for key in sorted(nodes)],
        "links": links,
    }
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
    detected = detected_partition(graph)
    if detected is not None:
        partitions["detected (Louvain)"] = detected
    stats = {}
    for name, group_of in partitions.items():
        row = {"groups": len(set(group_of.values())), "links": total, "modularity": None,
               "null_mean": None, "null_sd": None, "z": None, "p": None}
        if total and row["groups"] > 1:
            observed = modularity(weights, degree, total, group_of)
            rng, ids, labels = random.Random(0), sorted(group_of), [group_of[k] for k in sorted(group_of)]
            draws = []
            for _ in range(NULL_DRAWS):
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
            f"{skipped['long_targets']} captured values too long to be a target", ""]
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
            f"Modularity of each grouping over the {len(links)} links, against {NULL_DRAWS} shuffles of the same "
            "group sizes. The detected grouping is fitted to these links, so its score is a ceiling, not a test.", "",
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
                        asset_kinds=load_asset_kinds(registries), group_by=args.group_by)
    graph_path = os.path.join(args.out_dir, "graph.json")
    report_path = os.path.join(args.out_dir, "GRAPH_REPORT.md")
    sov_path = os.path.join(args.out_dir, "system.sov")
    write_text(graph_path, json.dumps(graph, indent=2, ensure_ascii=False) + "\n")
    write_text(report_path, render_report(graph, title))
    document = graph_to_sov(graph, title)
    laid_out = write_sov(document, sov_path, args.schematically)
    basis = {"EXTRACTED": 0, "INFERRED": 0}
    for link in graph["links"]:
        basis[link["confidence"]] += 1
    json.dump({
        "graph": graph_path, "report": report_path, "sov": sov_path, "laid_out": laid_out,
        "nodes": len(graph["nodes"]), "links": len(graph["links"]), "basis": basis,
        "communities": len(graph["graph"]["community_labels"]), "grouped_by": args.group_by,
        "hyperedges": len(graph["graph"]["hyperedges"]), "partitions": graph["graph"]["partitions"],
        "skipped": graph["graph"]["skipped"],
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
