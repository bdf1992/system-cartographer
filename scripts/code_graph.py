#!/usr/bin/env python3
"""code_graph.py -- the target's code, parsed: functions, classes, modules, calls, imports.

The scan sorts files by concern from patterns. This pass reads the code itself. It hands
the scanned code files to graphify's tree-sitter extractor (the same parse `graphify
update` runs, no model involved), so a function, a class and a module are each a node and
a call, an import, an inheritance and a containment are each an edge, tagged EXTRACTED
when read off the source and INFERRED when resolved across files. Leiden then groups the
nodes into communities from the edges alone.

Two more passes ride on the same file list:

  lint          `ruff check` over the Python files, under the target's own configuration.
                Each finding lands on the function or class it falls inside, else on its
                file. Nothing is fixed and no cache is written.
  dependencies  what the target's manifests declare (pyproject.toml, requirements*.txt,
                package.json), so the export can set declared against imported.

Writes <out-dir>/code-graph.json (graphify's node-link format, each node carrying its
community and lint), lint.json and dependencies.json. Nothing is written into the target:
graphify's extraction cache goes under <out-dir>.

    python scripts/code_graph.py --scan-dir <run>/scan --out-dir <run>/code
    python scripts/graph_export.py --scan-dir <run>/scan --code-dir <run>/code --out-dir <run>/graph

Needs `graphify` importable (pip install graphifyy, or a checkout of the schematify fork
on PYTHONPATH). `ruff` on PATH is optional; without it the lint pass is skipped and the
output says so.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".go", ".rs", ".cs", ".java", ".rb", ".php", ".c", ".h",
    ".cpp", ".hpp", ".kt", ".swift", ".scala", ".lua", ".sh", ".ps1", ".sql",
})
# Files per ruff call, to stay under the command-line length a shell allows.
LINT_BATCH = 200
_REQUIREMENT_NAME =re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_LINE = re.compile(r"L(\d+)")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def scanned_files(scan_dir):
    """The target root and every file the scan saw, as paths relative to it."""
    root, files = None, set()
    for name in sorted(os.listdir(scan_dir)):
        if not name.endswith(".json") or name in ("scan.json", "patterns.json", "lineage.json"):
            continue
        graph = read_json(os.path.join(scan_dir, name))
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
            continue
        root = root or graph.get("root") or graph.get("target")
        files.update(node["id"] for node in graph["nodes"] if node.get("kind") == "file")
    if root is None:
        raise SystemExit(f"code_graph: no concern graphs in {scan_dir}; run cartographer_scan.py first")
    return root, sorted(files)


def parse_code(root, files, out_dir):
    """graphify's extraction, graph build and Leiden clustering over the scanned code files."""
    try:
        from graphify.build import build_from_json
        from graphify.cluster import cluster
        from graphify.extract import extract
    except ImportError as exc:
        raise SystemExit(f"code_graph: graphify is not importable ({exc}). Install it (pip install graphifyy) "
                         "or put a checkout of the schematify fork on PYTHONPATH.")
    from pathlib import Path
    paths = [Path(root) / rel for rel in files if os.path.splitext(rel)[1].lower() in CODE_EXTENSIONS]
    extraction = extract(paths, cache_root=Path(out_dir), root=Path(root))
    graph = build_from_json(extraction, directed=True, root=Path(root))
    communities = cluster(graph)
    community_of = {node: cid for cid, members in communities.items() for node in members}
    nodes = []
    for node_id, data in graph.nodes(data=True):
        nodes.append({"id": node_id, **data, "community": community_of.get(node_id)})
    links = []
    for edge in graph.edges(data=True):
        source, target, data = edge[0], edge[1], dict(edge[2])
        # build_from_json keeps the true direction of an edge it had to store reversed.
        links.append({**data, "source": data.pop("_src", source), "target": data.pop("_tgt", target)})
    return {"directed": True, "multigraph": False, "graph": {"files_parsed": len(paths)},
            "nodes": nodes, "links": links}


def start_line(node):
    match = _LINE.search(str(node.get("source_location") or ""))
    return int(match.group(1)) if match else None


def run_lint(root, files, code_graph):
    """ruff's findings, each placed on the definition it falls inside."""
    python_files = [rel for rel in files if rel.endswith(".py")]
    ruff = shutil.which("ruff")
    if not python_files:
        return {"ran": False, "reason": "no Python files in the scan", "findings": 0, "by_file": {}, "by_code": {}}
    if ruff is None:
        return {"ran": False, "reason": "ruff is not on PATH", "findings": 0, "by_file": {}, "by_code": {}}
    found = []
    for start in range(0, len(python_files), LINT_BATCH):
        proc = subprocess.run(
            [ruff, "check", "--output-format", "json", "--no-fix", "--no-cache", "--exit-zero",
             *python_files[start:start + LINT_BATCH]],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=root)
        try:
            found += json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            return {"ran": False, "reason": f"ruff output was not JSON: {proc.stderr[-300:]}", "findings": 0,
                    "by_file": {}, "by_code": {}}
    wanted = set(python_files)
    definitions = {}
    for node in code_graph["nodes"]:
        line = start_line(node)
        source = str(node.get("source_file") or "").replace("\\", "/")
        if line is not None and source:
            definitions.setdefault(source, []).append((line, node["id"]))
    for rows in definitions.values():
        rows.sort()
    by_file, by_code, by_node = {}, {}, {}
    for finding in found:
        rel = os.path.relpath(finding["filename"], root).replace("\\", "/")
        if rel not in wanted:
            continue
        code = finding.get("code") or "syntax"
        row = (finding.get("location") or {}).get("row") or 0
        by_file.setdefault(rel, {})
        by_file[rel][code] = by_file[rel].get(code, 0) + 1
        by_code[code] = by_code.get(code, 0) + 1
        holder = None
        for line, node_id in definitions.get(rel, []):
            if line > row:
                break
            holder = node_id
        if holder is not None:
            by_node.setdefault(holder, {})
            by_node[holder][code] = by_node[holder].get(code, 0) + 1
    for node in code_graph["nodes"]:
        if node["id"] in by_node:
            node["lint"] = by_node[node["id"]]
    return {"ran": True, "reason": None, "findings": sum(by_code.values()), "files_checked": len(python_files),
            "by_code": dict(sorted(by_code.items(), key=lambda item: (-item[1], item[0]))), "by_file": by_file}


def declared_dependencies(root, files):
    """manifest file -> the package names it declares."""
    declared = {}
    for rel in files:
        name = os.path.basename(rel).lower()
        path = os.path.join(root, rel)
        names = []
        try:
            if name == "pyproject.toml":
                import tomllib
                with open(path, "rb") as handle:
                    data = tomllib.load(handle)
                project = data.get("project") or {}
                rows = list(project.get("dependencies") or [])
                for extra in (project.get("optional-dependencies") or {}).values():
                    rows += list(extra)
                names = [m.group(1) for m in map(_REQUIREMENT_NAME.match, rows) if m]
            elif name.startswith("requirements") and name.endswith(".txt"):
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    rows = [line for line in handle if line.strip() and not line.lstrip().startswith(("#", "-"))]
                names = [m.group(1) for m in map(_REQUIREMENT_NAME.match, rows) if m]
            elif name == "package.json":
                data = read_json(path)
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    names += list((data.get(key) or {}).keys())
        except (OSError, ValueError):
            continue
        if names:
            declared[rel] = sorted(set(names))
    return declared


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scan-dir", required=True, help="the --out-dir of a cartographer_scan.py run")
    parser.add_argument("--out-dir", required=True, help="where code-graph.json, lint.json and dependencies.json land")
    parser.add_argument("--no-lint", action="store_true", help="skip the ruff pass")
    args = parser.parse_args()

    root, files = scanned_files(args.scan_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    started = time.time()
    code = parse_code(root, files, args.out_dir)
    parse_seconds = round(time.time() - started, 1)
    lint = ({"ran": False, "reason": "--no-lint", "findings": 0, "by_file": {}, "by_code": {}}
            if args.no_lint else run_lint(root, files, code))
    out = os.path.join(args.out_dir, "code-graph.json")
    code["graph"]["root"] = root
    write_json(out, code)
    write_json(os.path.join(args.out_dir, "lint.json"), lint)
    dependencies = declared_dependencies(root, files)
    write_json(os.path.join(args.out_dir, "dependencies.json"), dependencies)
    relations, basis = {}, {}
    for link in code["links"]:
        relations[link.get("relation")] = relations.get(link.get("relation"), 0) + 1
        basis[link.get("confidence")] = basis.get(link.get("confidence"), 0) + 1
    json.dump({
        "code_graph": out, "files_parsed": code["graph"]["files_parsed"], "parse_seconds": parse_seconds,
        "nodes": len(code["nodes"]), "links": len(code["links"]),
        "communities": len({n["community"] for n in code["nodes"] if n["community"] is not None}),
        "relations": dict(sorted(relations.items(), key=lambda item: -item[1])), "basis": basis,
        "lint": {k: lint[k] for k in ("ran", "reason", "findings")},
        "manifests": {rel: len(names) for rel, names in dependencies.items()},
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
