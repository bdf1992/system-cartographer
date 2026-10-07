#!/usr/bin/env python3
"""graph_view.py -- the map as something to move through: every node, drawn fast.

The Schematically documents show a system at the height of its units. This writes the
node-level view: a folder holding `index.html` and `data.js` that opens from disk in a
browser, with no server and nothing fetched from the network.

    python scripts/graph_view.py --graph <run>/graph/graph.json --out-dir <run>/view [--structure <file>]

What is computed here, once, so that opening the view does no layout work:

  plane     a domain. Code goes on the layer its target declares for it when --structure
            names a declaration (a JSON file with `layers: [{name}]` and `registrations:
            [{selector, layer}]`, selectors being path globs); otherwise on its top folder.
            Actors, each asset kind, names from outside and the boundary get a plane each.
  cluster   the unit that opens and closes: a code community, or one plane's worth of
            anything that has none. A cluster sits on the plane most of its members are on.
  position  planes are packed into rows; inside a plane, clusters start where a spring layout
            of the links between them puts them (when networkx is importable) and are then
            placed largest first, each at the nearest free spot, so none overlap; members sit
            on a disc around their cluster, most connected at the centre.

How the view draws it (references/viewer/index.html):

  one rule for detail   a cluster shows its members when there is room to read them on
                        screen and it is of interest: under the pointer, or selected.
                        Everything else is one disc with a count. The number of things drawn
                        therefore follows the screen, not the size of the graph.
  links                 inside an open cluster, each link, coloured by relation and faint when
                        inferred. Between clusters, one line per pair; for what is selected,
                        its twelve strongest connections as bands, wider for more links.
  colour                the plane a thing is on.
  selection             opens only itself, keeps what it ties to bright and named, quiets the
                        rest, and lists what uses it and what it uses.

Standard library, plus networkx when present.
"""
import argparse
import fnmatch
import json
import math
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_export as ge  # noqa: E402

SPACING = 26.0            # world units between two member nodes
CLUSTER_GAP = 28.0
PLANE_GAP = 260.0
KINDS = ["calls", "imports", "uses", "holds", "other"]
KIND = {"calls": 0, "indirect_call": 0, "imports": 1, "imports_from": 1, "inherits": 1, "re_exports": 1,
        "dynamic_import": 1, "python_import": 1, "js_import": 1, "js_require": 1, "references": 2, "uses": 2,
        "contains": 3, "method": 3, "defines": 3, "binds": 3}
FIRST_PLANES = ["actors"]
LAST_PLANES = ["packages and names", ge.BOUNDARY_COMMUNITY]


def load_structure(path):
    """(layer names in declared order, registrations) from a structure declaration, or two empty lists."""
    if not path:
        return [], []
    data = ge.read_json(path)
    layers = [layer["name"] for layer in data.get("layers") or [] if layer.get("name")]
    return layers, [r for r in data.get("registrations") or [] if r.get("selector") and r.get("layer") in layers]


def declared_layer(rel, registrations):
    for r in registrations:
        if fnmatch.fnmatch(rel, r["selector"]) or fnmatch.fnmatch(rel, r["selector"].rstrip("/") + "/*"):
            return r["layer"]
    return None


def plane_of(node, registrations):
    if node["layer"] == "code":
        return declared_layer(node["source_file"], registrations) or node["source_file"].split("/")[0]
    if node["layer"] == "actors":
        return "actors"
    if node["layer"] == "outside":
        return ge.BOUNDARY_COMMUNITY
    return node["asset_kind"] if node["kind"] == "file" else "packages and names"


def spring_positions(cluster_ids, between, side):
    """Where the links between clusters want each one, or the origin for all when networkx is absent."""
    try:
        import networkx as nx
    except ImportError:
        return {c: [0.0, 0.0] for c in cluster_ids}
    if len(cluster_ids) < 2:
        return {c: [0.0, 0.0] for c in cluster_ids}
    meta = nx.Graph()
    meta.add_nodes_from(cluster_ids)
    for (a, b), count in between.items():
        if a in meta and b in meta:
            meta.add_edge(a, b, weight=math.log1p(count))
    pos = nx.spring_layout(meta, seed=7, k=1.6 / math.sqrt(len(cluster_ids)), iterations=120)
    return {c: [pos[c][0] * side / 2, pos[c][1] * side / 2] for c in cluster_ids}


def place_without_overlap(points, radius):
    """Largest first, each cluster takes the free spot nearest where it wanted to be, found by
    walking a spiral outward. Returns nothing; `points` is changed in place."""
    placed = []
    for c in sorted(points, key=lambda c: (-radius[c], c)):
        ox, oy = points[c]
        step, angle, dist, x, y = radius[c] * 0.35 + 6, 0.0, 0.0, ox, oy
        while any(math.hypot(x - px, y - py) < radius[c] + pr + CLUSTER_GAP for px, py, pr in placed):
            angle += 0.6
            dist += step * 0.6 / (2 * math.pi)
            x, y = ox + dist * math.cos(angle), oy + dist * math.sin(angle)
        points[c] = [x, y]
        placed.append((x, y, radius[c]))


def build_view(graph, layers, registrations):
    nodes, links = graph["nodes"], graph["links"]
    degree = ge.degrees(graph)
    claims = graph["graph"].get("claims") or {}
    plane = {n["id"]: plane_of(n, registrations) for n in nodes}
    cluster = {n["id"]: f"code-{n['code_community']}" if n.get("code_community") is not None else plane[n["id"]]
               for n in nodes}
    members = {}
    for n in nodes:
        members.setdefault(cluster[n["id"]], []).append(n)
    cluster_plane = {}
    for cid, rows in members.items():
        count = {}
        for n in rows:
            count[plane[n["id"]]] = count.get(plane[n["id"]], 0) + 1
        cluster_plane[cid] = max(sorted(count), key=lambda p: count[p])
    between = {}
    for link in links:
        a, b = cluster[link["source"]], cluster[link["target"]]
        if a != b:
            key = (a, b) if a < b else (b, a)
            between[key] = between.get(key, 0) + 1

    # Planes in reading order: actors, then declared layers from the top of the stack down,
    # then other code, then assets, then what is outside.
    present = set(cluster_plane.values())
    code_planes = sorted({plane[n["id"]] for n in nodes if n["layer"] == "code"} - set(layers))
    asset_planes = sorted(present - set(FIRST_PLANES) - set(LAST_PLANES) - set(layers) - set(code_planes))
    order = [p for p in FIRST_PLANES + list(reversed(layers)) + code_planes + asset_planes + LAST_PLANES if p in present]

    radius = {cid: SPACING * math.sqrt(len(rows)) * 0.62 + 12 for cid, rows in members.items()}
    centers, boxes = {}, {}
    for z, name in enumerate(order):
        cids = sorted(c for c, p in cluster_plane.items() if p == name)
        side = max(math.sqrt(sum(math.pi * (radius[c] + 14) ** 2 for c in cids) * 1.9), 400.0)
        points = spring_positions(cids, between, side)
        place_without_overlap(points, radius)
        min_x = min(points[c][0] - radius[c] for c in cids)
        max_x = max(points[c][0] + radius[c] for c in cids)
        min_y = min(points[c][1] - radius[c] for c in cids)
        max_y = max(points[c][1] + radius[c] for c in cids)
        for c in cids:
            centers[c] = [points[c][0] - min_x + 120, points[c][1] - min_y + 200]
        boxes[name] = {"name": name, "z": z, "x": 0.0, "y": 0.0, "w": (max_x - min_x) + 240, "h": (max_y - min_y) + 320}
    row_width = math.sqrt(sum(b["w"] * b["h"] for b in boxes.values()) * 1.6) * 1.15
    x = y = row_h = 0.0
    for name in order:
        box = boxes[name]
        if x > 0 and x + box["w"] > row_width:
            x, y, row_h = 0.0, y + row_h + PLANE_GAP, 0.0
        box["x"], box["y"] = x, y
        x += box["w"] + PLANE_GAP
        row_h = max(row_h, box["h"])
    for c, p in cluster_plane.items():
        centers[c] = (centers[c][0] + boxes[p]["x"], centers[c][1] + boxes[p]["y"])

    cluster_ids = sorted(members, key=lambda c: (order.index(cluster_plane[c]), -len(members[c]), c))
    cindex = {c: i for i, c in enumerate(cluster_ids)}
    out_nodes, node_index, clusters = [], {}, []
    for cid in cluster_ids:
        rows = sorted(members[cid], key=lambda n: (-degree[n["id"]], n["id"]))
        cx, cy = centers[cid]
        start = len(out_nodes)
        for i, n in enumerate(rows):                    # a sunflower disc: the busiest member at the centre
            r, t = SPACING * 0.6 * math.sqrt(i), i * 2.399963
            node_index[n["id"]] = len(out_nodes)
            out_nodes.append([round(cx + r * math.cos(t), 1), round(cy + r * math.sin(t), 1), degree[n["id"]],
                              str(n["label"])[:48], n["kind"], n.get("source_file") or "",
                              sum((n.get("lint") or {}).values())])
        name = cid
        if cid.startswith("code-"):
            folders = {}
            for n in rows:
                folder = os.path.dirname(n.get("source_file") or "") or "."
                folders[folder] = folders.get(folder, 0) + 1
            name = f"{max(sorted(folders), key=lambda f: folders[f])}: {rows[0]['label']}"
        clusters.append({"id": cid, "name": name[:60], "plane": order.index(cluster_plane[cid]), "x": round(cx, 1),
                         "y": round(cy, 1), "r": round(radius[cid], 1), "start": start, "count": len(rows),
                         "claims": [f"{c['id']} {c['verdict'] or c['state']}" for c in claims.get(cid, [])]})
    return {
        "planes": [boxes[p] for p in order], "clusters": clusters, "nodes": out_nodes, "kinds": KINDS,
        "edges": [[node_index[l["source"]], node_index[l["target"]], KIND.get(l["relation"], 4),
                   1 if l["confidence"] == "INFERRED" else 0] for l in links],
        "clusterEdges": [[cindex[a], cindex[b], count] for (a, b), count in between.items()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--graph", required=True, help="graph.json from graph_export.py")
    parser.add_argument("--out-dir", required=True, help="the folder the view is written into")
    parser.add_argument("--structure", default=None,
                        help="a JSON declaration of the target's layers and which paths belong to each")
    args = parser.parse_args()

    layers, registrations = load_structure(args.structure)
    view = build_view(ge.read_json(args.graph), layers, registrations)
    os.makedirs(args.out_dir, exist_ok=True)
    data_path = os.path.join(args.out_dir, "data.js")
    ge.write_text(data_path, "window.GRAPH = " + json.dumps(view, separators=(",", ":"), ensure_ascii=False) + ";\n")
    viewer = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "viewer", "index.html")
    shutil.copyfile(viewer, os.path.join(args.out_dir, "index.html"))
    json.dump({"view": os.path.join(args.out_dir, "index.html"), "planes": [p["name"] for p in view["planes"]],
               "clusters": len(view["clusters"]), "nodes": len(view["nodes"]), "links": len(view["edges"]),
               "data_bytes": os.path.getsize(data_path)}, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
