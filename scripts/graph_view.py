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
  cluster   the unit that opens and closes: the part of a code community that is on one
            plane, the records of one type, or one plane's worth of anything that has
            neither. A code cluster is named for the files it holds, not for its busiest
            member. A part of a community too small to stand alone joins the cluster on its
            plane it is linked to most.
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
SMALL_TYPE = 5            # records of a type before the type is a cluster of its own
SMALL_PART = 5            # members of a community on one plane before that part is a cluster of its own
NAME_LENGTH = 72          # of a cluster's name, before anything added to tell two apart
LABEL_LENGTH = 24
FOLDER_PARTS = 3          # trailing folders kept in a cluster's name
KINDS = ["calls", "imports", "uses", "holds", "other"]
KIND = {"calls": 0, "indirect_call": 0, "imports": 1, "imports_from": 1, "inherits": 1, "re_exports": 1,
        "dynamic_import": 1, "python_import": 1, "js_import": 1, "js_require": 1, "references": 2, "uses": 2, "refers_to": 2, "mentions": 2, "names": 2,
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


def tally(names):
    count = {}
    for name in names.values():
        count[name] = count.get(name, 0) + 1
    return count


def code_clusters(nodes, links, plane):
    """node id -> cluster id, for parsed code. A community is drawn once on each plane it has
    members on, so nothing sits on a plane that is not its own. A part with fewer than
    SMALL_PART members joins a cluster on its own plane when it has at least as many links
    to that cluster as it has inside itself: the cluster it is linked to most, and among
    equals one holding a file of its own. A small part tied more to itself stands as it is,
    and one with no link at all goes to its plane's leftovers."""
    part = {n["id"]: f"code-{n['code_community']}@{plane[n['id']]}" for n in nodes if n.get("code_community") is not None}
    size, files, inside, pull = tally(part), {}, {}, {}
    for n in nodes:
        if n["id"] in part:
            files.setdefault(part[n["id"]], set()).add(n.get("source_file"))
    for link in links:
        a, b = link["source"], link["target"]
        if a not in part or b not in part:
            continue
        if part[a] == part[b]:
            inside[part[a]] = inside.get(part[a], 0) + 1
        elif plane[a] == plane[b]:
            for small, big in ((part[a], part[b]), (part[b], part[a])):
                if size[small] < SMALL_PART <= size[big]:
                    row = pull.setdefault(small, {})
                    row[big] = row.get(big, 0) + 1
    home = {}
    for small, row in pull.items():
        best = min(row, key=lambda c: (-row[c], not files[c] & files[small], c))
        if row[best] >= inside.get(small, 0):
            home[small] = best

    def placed(node_id, p):
        if size[p] >= SMALL_PART or (p not in home and inside.get(p)):
            return p
        return home.get(p, f"code-other@{plane[node_id]}")

    return {i: placed(i, p) for i, p in part.items()}


def cluster_name(cid, rows):
    """What a code cluster holds. The folder of its largest file, then that file when it
    holds half the members, or the two largest files; a file from another folder is said
    with its folder. Then how many more files there are. Where the files named would hold
    under a quarter of the members, the name is the count of files and the largest one.
    A name too long loses the end of its file names, never the count."""
    if cid.startswith("code-other@"):
        return f"{cid.split('@', 1)[1]}: other code"
    files = tally({n["id"]: n.get("source_file") or "" for n in rows})
    ranked = sorted(files, key=lambda f: (-files[f], f))
    shown = ranked[:1] if files[ranked[0]] * 2 >= len(rows) else ranked[:2]
    folder = os.path.dirname(ranked[0])

    def said(file):
        there = os.path.dirname(file)
        return os.path.basename(file) if there == folder else f"{os.path.basename(there) or '.'}/{os.path.basename(file)}"

    if sum(files[f] for f in shown) * 4 < len(rows):
        folders = tally({n["id"]: os.path.dirname(n.get("source_file") or "") for n in rows})
        folder = max(sorted(folders), key=lambda f: folders[f])
        body, tail = f"{len(ranked)} files", f", largest {said(ranked[0])}"
    else:
        more = len(ranked) - len(shown)
        body, tail = ", ".join(said(f) for f in shown), f" +{more} file{'s' if more > 1 else ''}" if more else ""
    prefix = "/".join((folder or ".").split("/")[-FOLDER_PARTS:]) + ": "
    room = NAME_LENGTH - len(prefix) - len(tail)
    return prefix + (body if len(body) <= room else body[:max(room - 1, 1)] + ge.ELLIPSIS) + tail


def distinct_names(names, plane_of_cluster, busiest):
    """Two clusters on one plane with one name are told apart by their most connected member,
    and by a number where that is the same too."""
    out, taken = dict(names), tally({cid: (plane_of_cluster[cid], name) for cid, name in names.items()})
    for cid in sorted(names):
        if taken[(plane_of_cluster[cid], names[cid])] > 1:
            out[cid] = f"{names[cid]} ({busiest[cid][:LABEL_LENGTH]})"
    again, seen = tally({cid: (plane_of_cluster[cid], name) for cid, name in out.items()}), {}
    for cid in sorted(out):
        key = (plane_of_cluster[cid], out[cid])
        if again[key] > 1:
            seen[key] = seen.get(key, 0) + 1
            out[cid] = f"{out[cid]} #{seen[key]}"
    return out


def build_view(graph, layers, registrations):
    nodes, links = graph["nodes"], graph["links"]
    degree = ge.degrees(graph)
    claims = graph["graph"].get("claims") or {}
    plane = {n["id"]: plane_of(n, registrations) for n in nodes}
    # On its plane, a record type too small to be a cluster of its own is shown with the folder
    # its records sit in, and a folder's worth that is still too small with the other leftovers.
    group = {n["id"]: f"{plane[n['id']]}: {n['record_type']}" for n in nodes if n.get("record_type")}
    for fallback in ({n["id"]: os.path.basename(os.path.dirname(n["source_file"])) for n in nodes}, {}):
        held = tally(group)
        group = {i: name if held[name] >= SMALL_TYPE else f"{plane[i]}: {fallback.get(i, 'other')}"
                 for i, name in group.items()}
    # An asset file that is a product of something else (generated, a copy, an archive, a transcript)
    # is shown apart from the files that were written, where a plane has enough of them.
    aside = {n["id"]: f"{plane[n['id']]}: {n['source_class']}" for n in nodes
             if n["kind"] == "file" and not n.get("record_type")    # a record is grouped by its type, code by its community
             and n.get("source_class") in ge.DERIVED_CLASSES}
    held = tally(aside)
    group.update({i: name for i, name in aside.items() if held[name] >= SMALL_TYPE})
    code = code_clusters(nodes, links, plane)
    cluster = {n["id"]: code.get(n["id"]) or group.get(n["id"], plane[n["id"]]) for n in nodes}
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
    # A claim is about a whole community; it is shown once, on the cluster its busiest member is in.
    holder, shown_claims = {}, {}
    for n in sorted(nodes, key=lambda n: (-degree[n["id"]], n["id"])):
        if n.get("code_community") is not None:
            holder.setdefault(f"code-{n['code_community']}", cluster[n["id"]])
    for unit, rows in claims.items():
        here = holder.get(unit, unit)    # on another community's cluster a claim says which unit it is about
        shown_claims.setdefault(here, []).extend(
            f"{c['id']} {c['verdict'] or c['state']}" + ("" if here.split("@")[0] == unit else f" ({unit})") for c in rows)
    ranked = {cid: sorted(rows, key=lambda n: (-degree[n["id"]], n["id"])) for cid, rows in members.items()}
    names = distinct_names({cid: cluster_name(cid, rows) if cid.startswith("code-") else cid for cid, rows in members.items()},
                           cluster_plane, {cid: str(next((n for n in rows if n["kind"] != "file"), rows[0])["label"])
                                           for cid, rows in ranked.items()})
    out_nodes, node_index, clusters = [], {}, []
    for cid in cluster_ids:
        rows = ranked[cid]
        cx, cy = centers[cid]
        start = len(out_nodes)
        for i, n in enumerate(rows):                    # a sunflower disc: the busiest member at the centre
            r, t = SPACING * 0.6 * math.sqrt(i), i * 2.399963
            node_index[n["id"]] = len(out_nodes)
            out_nodes.append([round(cx + r * math.cos(t), 1), round(cy + r * math.sin(t), 1), degree[n["id"]],
                              str(n["label"])[:48], n["kind"], n.get("source_file") or "",
                              sum((n.get("lint") or {}).values())])
        community = cid.split("@")[0] if cid.startswith("code-") and not cid.startswith("code-other@") else None
        clusters.append({"id": cid, "name": names[cid], "community": community, "plane": order.index(cluster_plane[cid]),
                         "x": round(cx, 1), "y": round(cy, 1), "r": round(radius[cid], 1), "start": start, "count": len(rows),
                         "claims": shown_claims.get(cid, [])})
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
