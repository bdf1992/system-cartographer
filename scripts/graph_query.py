#!/usr/bin/env python3
"""graph_query.py -- ask the map: where is it, what does it reach, what does changing it hit.

A text search finds where a name is written. It does not say what that thing is part of,
what depends on it, or which tests would notice it change. The graph already holds those
answers; this reads them out fast enough to sit beside every search.

    python scripts/graph_query.py index   --graph <run>/graph/graph.json --out <run>/graph-index.json
    python scripts/graph_query.py search  write_record      --index <run>/graph-index.json
    python scripts/graph_query.py impact  write_record      --index ...   # what breaks if this changes
    python scripts/graph_query.py reach   write_record      --index ...   # what this needs
    python scripts/graph_query.py path    guard write_record --index ...  # how one depends on the other
    python scripts/graph_query.py measure                   --index ...   # the graph's own numbers

The words, each one thing:

  depends   a link whose source needs its target: calls, imports, inherits, uses, references,
            runs, names. A link that only says where something sits (contains, method,
            defines) is not a dependency and is never followed as one.
  impact    everything that depends on a thing, directly or through others: what a change
            to it can reach. For a file, the impact of the file and of what it holds.
  reach     the other direction: everything a thing depends on.
  test      a node whose file is a test file (under tests/, or named test_*, *_test.*,
            *.test.*, *.spec.*). "Tests that reach it" is the impact that falls in tests.

`index` runs once per graph and writes integer adjacency lists; every other command loads
that file. Standard library only.
"""
import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter, deque

STRUCTURAL = frozenset({"contains", "method", "defines", "binds", "rationale_for", "points_outside_root",
                        "declares", "may_use"})
_TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|_test\.[^/.]+$|\.(test|spec)\.[^/]+$")
# Code the target holds but did not write: type declarations, vendored and generated files.
_NOT_OWN = re.compile(r"\.d\.ts$|(^|/)(vendor|vendored|third_party|node_modules|dist|generated)/")
DEPTHS = 3
CHECK_SAMPLE = 60
CHECK_FILE_BYTES = 2_000_000
CHECK_EXTENSIONS = frozenset({".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".cmd", ".toml",
                              ".yml", ".yaml", ".md", ".html"})


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def is_test(source_file):
    return bool(source_file) and bool(_TEST_FILE.search(source_file.replace("\\", "/")))


def build_index(graph):
    """The graph as parallel arrays and integer adjacency, plus the lookups a search needs."""
    nodes = graph["nodes"]
    ident = {node["id"]: i for i, node in enumerate(nodes)}
    relations, rel_id = [], {}
    uses = [[] for _ in nodes]        # i -> [[j, relation, inferred]]  i depends on j
    used_by = [[] for _ in nodes]
    holds = [[] for _ in nodes]       # a file or class -> what it contains
    for link in graph["links"]:
        a, b, relation = ident[link["source"]], ident[link["target"]], link["relation"]
        if a == b:
            continue
        if relation in STRUCTURAL:
            if relation in ("contains", "method", "defines"):
                holds[a].append(b)
            continue
        r = rel_id.setdefault(relation, len(relations))
        if r == len(relations):
            relations.append(relation)
        inferred = 1 if link.get("confidence") == "INFERRED" else 0
        uses[a].append([b, r, inferred])
        used_by[b].append([a, r, inferred])
    labels = graph["graph"].get("community_labels") or {}
    claims = graph["graph"].get("claims") or {}
    rows = []
    for node in nodes:
        source = node.get("source_file") or ""
        community = node.get("code_community")
        rows.append({
            "label": str(node.get("label") or node["id"]), "kind": node["kind"], "file": source,
            "line": node.get("source_location") or "", "layer": node.get("layer") or "",
            "group": node.get("asset_kind") or node.get("primary_concern") or "",
            "cluster": f"code-{community}" if community is not None else "",
            "test": is_test(source), "lint": sum((node.get("lint") or {}).values()),
            "own": not (node.get("source_class") in ("vendor", "generated") or _NOT_OWN.search(source.replace("\\", "/"))),
        })
    names = {}
    for i, row in enumerate(rows):
        key = row["label"].lower().rstrip("()").lstrip(".")
        names.setdefault(key, []).append(i)
    files = {}
    for i, row in enumerate(rows):
        if row["file"]:
            files.setdefault(row["file"], []).append(i)
    return {"root": graph["graph"].get("root"), "relations": relations, "nodes": rows, "uses": uses,
            "used_by": used_by, "holds": holds, "names": names, "files": files, "labels": labels,
            "claims": {unit: [f"{c['id']} {c['verdict'] or c['state']}" for c in rows_] for unit, rows_ in claims.items()}}


_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
WRITTEN_TOP = 30


def written_in(index):
    """Where each defined name is written, read from the files: {name: [how many files, [[file node, times], ...]]}.

    The parse links a use only where it can resolve it. A function reached as module.name(),
    passed by name, or named in a string is still written down somewhere, and this finds it. It
    is a fact about text, not meaning: two things of one name are counted together.
    """
    nodes, root = index["nodes"], index.get("root") or ""
    wanted = {row["label"].rstrip("()").lstrip(".").split(".")[-1]
              for row in nodes if row["kind"] in ("function", "class") and row["own"]}
    wanted = {name for name in wanted if len(name) >= 4}
    found = {}
    for i, row in enumerate(nodes):
        if row["kind"] != "file" or os.path.splitext(row["file"])[1].lower() not in CHECK_EXTENSIONS:
            continue
        full = os.path.join(root, row["file"])
        try:
            if os.path.getsize(full) > CHECK_FILE_BYTES:
                continue
            with open(full, encoding="utf-8", errors="replace") as handle:
                counts = Counter(_WORD.findall(handle.read()))
        except OSError:
            continue
        for name in counts.keys() & wanted:
            found.setdefault(name, []).append([i, counts[name]])
    return {name: [len(rows), sorted(rows, key=lambda r: (-r[1], r[0]))[:WRITTEN_TOP]] for name, rows in found.items()}


# ---- traversal --------------------------------------------------------------------------------

def start_set(index, i):
    """A node, and for a file or class everything it holds: changing a file changes what is in it."""
    seen, queue = {i}, deque([i])
    while queue:
        for j in index["holds"][queue.popleft()]:
            if j not in seen:
                seen.add(j)
                queue.append(j)
    return seen


def spread(index, i, table, limit=None):
    """Breadth-first over `table` from a node's start set. Returns {node: depth}, depth from 1."""
    start = start_set(index, i)
    depth, queue = {}, deque((s, 0) for s in start)
    while queue:
        node, d = queue.popleft()
        if limit is not None and d >= limit:
            continue
        for other, _relation, _inferred in table[node]:
            if other not in start and other not in depth:
                depth[other] = d + 1
                queue.append((other, d + 1))
    return depth


def summary(index, i, table):
    """The numbers of one direction: how many at each depth, in how many files, how many are tests."""
    depth = spread(index, i, table)
    nodes = index["nodes"]
    by_depth = [sum(1 for d in depth.values() if d == k) for k in range(1, DEPTHS + 1)]
    files = {nodes[j]["file"] for j in depth if nodes[j]["file"]}
    tests = sorted({nodes[j]["file"] for j in depth if nodes[j]["test"]})
    direct = [j for j, d in depth.items() if d == 1]
    return {"total": len(depth), "by_depth": by_depth, "beyond": len(depth) - sum(by_depth), "files": len(files),
            "tests": len(tests), "test_files": tests, "direct": direct, "depth": depth}


# ---- search -----------------------------------------------------------------------------------

def find(index, text, limit=8):
    """Nodes matching a name or a path, best first: an exact name, then a prefix, then a part of
    it, then a file path; among equals, what more things depend on."""
    query = text.strip().lower().rstrip("()").lstrip(".")
    nodes, scored = index["nodes"], {}
    if not query:
        return []
    for i in index["names"].get(query, []):
        scored[i] = 100
    path = text.strip().replace("\\", "/")
    root = (index.get("root") or "").replace("\\", "/").rstrip("/")
    if root and path.lower().startswith(root.lower() + "/"):
        path = path[len(root) + 1:]
    for i in index["files"].get(path, []):
        scored[i] = max(scored.get(i, 0), 95 if nodes[i]["kind"] == "file" else 30)
    if len(scored) < limit:
        for key, ids in index["names"].items():
            score = 60 if key.startswith(query) else 40 if query in key else 0
            if score:
                for i in ids:
                    scored.setdefault(i, score)
        for rel, ids in index["files"].items():
            if query in rel.lower():
                for i in ids:
                    if nodes[i]["kind"] == "file":
                        scored.setdefault(i, 20)
    rank = lambda i: (-scored[i], nodes[i]["test"], -len(index["used_by"][i]), nodes[i]["file"], i)  # noqa: E731
    return sorted(scored, key=rank)[:limit]


def resolve(index, text):
    hits = find(index, text, limit=1)
    if not hits:
        raise SystemExit(f"graph_query: nothing in the graph is named {text!r}")
    return hits[0]


def describe(index, i, impact=None):
    """One hit as a record: what it is, where it sits, and what depends on it."""
    row = index["nodes"][i]
    impact = impact or summary(index, i, index["used_by"])
    return {"label": row["label"], "kind": row["kind"], "file": row["file"], "line": row["line"],
            "layer": row["layer"], "group": row["group"], "cluster": row["cluster"], "test": row["test"],
            "lint": row["lint"], "claims": index["claims"].get(row["cluster"], []),
            "used_by": impact["by_depth"][0], "impact": impact["total"], "impact_files": impact["files"],
            "tests": impact["tests"], "uses": len({j for j, _r, _i in index["uses"][i]})}


def one_line(record):
    where = f"{record['file']}{' ' + record['line'] if record['line'] else ''}" if record["file"] else record["layer"]
    plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")  # noqa: E731
    text = f"{record['label']} ({record['kind']}, {where}): "
    if not record["impact"]:
        # The parse misses links it cannot resolve, so absence here is "not found", never "unused".
        text += "a test" if record["test"] else "no dependents found in the map"
    else:
        text += (f"used by {record['used_by']} directly, {record['impact']} in all across "
                 f"{plural(record['impact_files'], 'file')}")
        if not record["test"]:
            text += f"; {plural(record['tests'], 'test file')} can reach it" if record["tests"] else "; no test file found among them"
    if record["lint"]:
        text += f"; {record['lint']} lint"
    if record["claims"]:
        text += f"; claims on its cluster: {', '.join(record['claims'])}"
    return text


def shortest_path(index, a, b):
    """The shortest chain of dependencies from a to b, as node indices, or None."""
    before, queue, goal = {a: None}, deque([a]), start_set(index, b)
    for s in start_set(index, a):
        if s not in before:
            before[s] = a
            queue.append(s)
    while queue:
        node = queue.popleft()
        if node in goal:
            chain = []
            while node is not None:
                chain.append(node)
                node = before[node]
            return chain[::-1]
        for other, _r, _i in index["uses"][node]:
            if other not in before:
                before[other] = node
                queue.append(other)
    return None


def named_elsewhere(index, ids):
    """For each definition, is its name written in any scanned file other than its own? Read
    from the target's files, so it is a check on the graph by a route the graph did not take."""
    root = index.get("root")
    if not root or not os.path.isdir(root):
        return None
    nodes = index["nodes"]
    wanted = {}                            # name -> the files that define it, which do not count
    for i in ids:
        wanted.setdefault(nodes[i]["label"].lstrip(".").rstrip("()"), set()).add(nodes[i]["file"])
    pattern = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, wanted), key=len, reverse=True))
                         + r")(?![A-Za-z0-9_])")
    seen = set()
    for rel in index["files"]:             # one pass over the files that can refer to code
        if os.path.splitext(rel)[1].lower() not in CHECK_EXTENSIONS:
            continue
        full = os.path.join(root, rel)
        try:
            if os.path.getsize(full) > CHECK_FILE_BYTES:
                continue
            with open(full, encoding="utf-8", errors="ignore") as handle:
                text = handle.read()
        except OSError:
            continue
        seen.update(name for name in set(pattern.findall(text)) if rel not in wanted[name])
    return sum(1 for i in ids if nodes[i]["label"].lstrip(".").rstrip("()") in seen)


def measure(index, check=CHECK_SAMPLE):
    """The graph's own numbers, each stated as what it can and cannot show.

    Only the target's own code outside tests is counted: declaration, vendored and generated
    files are left out. Test reach is a range, because the two ways of counting it err in
    opposite directions. A definition with no link found is not called unused: a sample of
    them is looked up in the source by name, and the share found there is reported beside
    the count, since that share is the parse missing a link, not the code missing a user."""
    nodes = index["nodes"]
    definitions = [i for i, n in enumerate(nodes)
                   if n["kind"] in ("function", "class") and not n["test"] and n.get("own", True)]
    left_out = sum(1 for n in nodes if n["kind"] in ("function", "class") and not n["test"] and not n.get("own", True))
    reached = set()
    for i, n in enumerate(nodes):          # everything any test depends on, at any depth
        if n["test"]:
            reached.update(spread(index, i, index["uses"]))
    reached_files = {nodes[j]["file"] for j in reached if nodes[j]["file"]}
    by_folder = {}
    for i in definitions:
        row = by_folder.setdefault(nodes[i]["file"].split("/")[0], {"definitions": 0, "by_call": 0, "by_file": 0})
        row["definitions"] += 1
        row["by_call"] += i in reached
        row["by_file"] += nodes[i]["file"] in reached_files
    share = lambda part, whole: round(part / whole, 3) if whole else None  # noqa: E731
    total = len(definitions)
    by_call, by_file = sum(r["by_call"] for r in by_folder.values()), sum(r["by_file"] for r in by_folder.values())
    shared = sum(1 for ids in index["names"].values() if len(ids) > 1 for i in ids if i in set(definitions)) \
        if total < 50000 else None
    direct = sorted(len({j for j, _r, _i in index["used_by"][i]}) for i in definitions)
    no_link = [i for i in definitions if not index["used_by"][i]]
    sample = sorted(no_link, key=lambda i: (hash_of(nodes[i]["label"] + nodes[i]["file"]), i))[:check]
    elsewhere = named_elsewhere(index, sample) if sample else None
    widest = sorted(definitions, key=lambda i: -len(index["used_by"][i]))[:10]
    return {
        "counted": {"definitions": total, "what": "functions and classes in the target's own code, outside tests",
                    "left_out_as_not_own_code": left_out},
        "found_by_name_alone": {"definitions": total - (shared or 0), "share": share(total - (shared or 0), total),
                                "means": "no other definition has the same name"},
        "test_reach": {
            "lower": {"share": share(by_call, total), "counts": "a test reaches the definition through calls and uses",
                      "errs": "low: misses what a test exercises through an import or a framework"},
            "upper": {"share": share(by_file, total), "counts": "a test can reach the file the definition is in",
                      "errs": "high: one tested function counts its whole file"},
            "by_folder": {folder: {"definitions": row["definitions"], "lower": share(row["by_call"], row["definitions"]),
                                   "upper": share(row["by_file"], row["definitions"])}
                          for folder, row in sorted(by_folder.items(), key=lambda kv: -kv[1]["definitions"])},
        },
        "no_link_found": {
            "definitions": len(no_link), "share": share(len(no_link), total),
            "means": "the parse found nothing that refers to it; this is not a count of unused code",
            "checked": None if elsewhere is None else {
                "sampled": len(sample), "named_in_another_file": elsewhere,
                "reading": f"{elsewhere} of {len(sample)} sampled are named in another source file, so the parse "
                           "missed a link there; only the rest are candidates for unused, and each needs reading"},
        },
        "direct_users": {"median": direct[len(direct) // 2] if direct else 0,
                         "p90": direct[int(len(direct) * 0.9)] if direct else 0},
        "most_used": [[nodes[i]["label"], nodes[i]["file"], len({j for j, _r, _i in index["used_by"][i]})] for i in widest],
        "inferred_share_of_dependencies": round(
            sum(inf for row in index["uses"] for _j, _r, inf in row) / max(1, sum(len(row) for row in index["uses"])), 3),
    }


def hash_of(text):
    """A stable order for sampling, the same on every run and machine."""
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("index")
    p.add_argument("--graph", required=True)
    p.add_argument("--out", required=True)
    for name in ("search", "impact", "reach"):
        p = sub.add_parser(name)
        p.add_argument("text")
        p.add_argument("--index", required=True)
        p.add_argument("--json", action="store_true")
        p.add_argument("--limit", type=int, default=8)
    p = sub.add_parser("path")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--index", required=True)
    p = sub.add_parser("measure")
    p.add_argument("--index", required=True)
    args = parser.parse_args()

    if args.cmd == "index":
        started = time.time()
        index = build_index(read_json(args.graph))
        index["written"] = written_in(index)
        index["built"] = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(args.graph)))
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(index, handle, separators=(",", ":"), ensure_ascii=False)
        print(json.dumps({"index": args.out, "nodes": len(index["nodes"]), "relations": index["relations"],
                          "bytes": os.path.getsize(args.out), "seconds": round(time.time() - started, 2)}, indent=2))
        return
    index = read_json(args.index)
    nodes = index["nodes"]
    if args.cmd == "search":
        records = [describe(index, i) for i in find(index, args.text, args.limit)]
        print(json.dumps(records, indent=2) if args.json else "\n".join(one_line(r) for r in records) or "no match")
    elif args.cmd in ("impact", "reach"):
        i = resolve(index, args.text)
        table = index["used_by"] if args.cmd == "impact" else index["uses"]
        result = summary(index, i, table)
        nearest = sorted(result["direct"], key=lambda j: (-len(index["used_by"][j]), nodes[j]["file"]))[:args.limit]
        out = {"of": describe(index, i), "direction": "depends on it" if args.cmd == "impact" else "it depends on",
               "total": result["total"], "by_depth": result["by_depth"], "beyond_depth_3": result["beyond"],
               "files": result["files"], "test_files": result["test_files"][:args.limit], "tests": result["tests"],
               "nearest": [f"{nodes[j]['label']}  {nodes[j]['file']}" for j in nearest]}
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            verb = "What depends on" if args.cmd == "impact" else "What is needed by"
            print(f"{verb} {nodes[i]['label']} ({nodes[i]['kind']}, {nodes[i]['file']}):")
            print(f"  {result['total']} in all across {result['files']} files: "
                  f"{result['by_depth'][0]} directly, {result['by_depth'][1]} one step further, "
                  f"{result['by_depth'][2]} two steps, {result['beyond']} beyond")
            print(f"  {result['tests']} test files among them" + (": " + ", ".join(result["test_files"][:args.limit]) if result["tests"] else ""))
            for line in out["nearest"]:
                print("  - " + line)
    elif args.cmd == "path":
        chain = shortest_path(index, resolve(index, args.a), resolve(index, args.b))
        print("no dependency path" if chain is None else "\n".join(
            f"{'  ' * k}{nodes[j]['label']}  {nodes[j]['file']}" for k, j in enumerate(chain)))
    elif args.cmd == "measure":
        print(json.dumps(measure(index), indent=2))


if __name__ == "__main__":
    main()
