#!/usr/bin/env python3
"""analysis_packets.py -- cut the map into units an agent can analyse, one packet each.

The parse and the scan say what is there and what points at what. They do not say what a
cluster of code is for, whether it does what its name says, or what is wrong with it. That
is analysis, and it is done by agents, one unit at a time, with every conclusion recorded
as a claim in the audit ledger (scripts/audit.py) so it is argued, judged and validated
like any other claim.

A unit is one of:

  code-<n>     a code community: definitions the parse found tightly linked
  actor-<name> one agent, skill, hook or workflow, with what it runs
  asset-<kind> one asset group: records, documents, log data and the rest

A packet is everything an analyst needs to start without reading the whole graph: the
unit's members with their files and lines, what links run inside it, what it calls and
what calls it (by neighbouring unit), its lint findings, how much of it is EXTRACTED and
how much INFERRED, the questions to answer, and the exact commands that record a claim.
The analyst reads the packet, then the source it points at, and writes claims; a second
agent refutes and a third validates. references/analysis-brief.md is their instruction.

    python scripts/analysis_packets.py --graph <run>/graph/graph.json --run <run> [--code-units 12]

Writes <run>/analysis/packets/<unit>.json and <run>/analysis/INDEX.md.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_export  # noqa: E402

MEMBER_ROWS = 120
NEIGHBOUR_ROWS = 12
EXAMPLE_ROWS = 4
QUESTIONS = {
    "code": [
        "What is this group of definitions for, in one sentence a newcomer could act on?",
        "What does it depend on, and what depends on it? Is either direction surprising?",
        "Which INFERRED links here are wrong when you read the source?",
        "What in it is dead, duplicated, or doing a second job its name does not say?",
        "Do the lint findings point at a real defect or at noise?",
    ],
    "actor": [
        "What does this actor do when it runs, and what triggers it?",
        "Does the code it runs do what its definition says it does?",
        "What authority does it hold (tools, commands), and is any of it unused or missing?",
    ],
    "asset": [
        "What is kept here and what is each kind of it for?",
        "Which code or actor reads or writes it? If none is linked, who does?",
        "What here is stale, duplicated or unexplained?",
    ],
}
_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text):
    return _SLUG.sub("-", str(text).lower()).strip("-")[:48]


def unit_of(node, code_units):
    """The unit a node belongs to, or None for a node outside every chosen unit."""
    if node["kind"] in ("agent", "skill", "hook", "workflow"):
        return f"actor-{slug(node['kind'] + '-' + node['label'])}"
    community = node.get("code_community")
    if community is not None:
        return f"code-{community}" if community in code_units else None
    if node["kind"] == "file" and node["asset_kind"] != graph_export.SYSTEM_DESCRIPTION:
        return f"asset-{slug(node['asset_kind'])}"
    return None


def code_unit_title(rows, degree):
    folders = {}
    for node in rows:
        folder = os.path.dirname(node["source_file"]) or "."
        folders[folder] = folders.get(folder, 0) + 1
    folder = max(sorted(folders), key=lambda f: folders[f])
    top = max(sorted(rows, key=lambda n: n["id"]), key=lambda n: degree[n["id"]])
    return f"{folder}: {top['label']} ({len(rows)} definitions)"


def build_packets(graph, code_unit_count):
    nodes, links = graph["nodes"], graph["links"]
    by_id = {node["id"]: node for node in nodes}
    degree = graph_export.degrees(graph)
    sizes = {}
    for node in nodes:
        if node.get("code_community") is not None:
            sizes[node["code_community"]] = sizes.get(node["code_community"], 0) + 1
    code_units = set(sorted(sizes, key=lambda c: (-sizes[c], c))[:code_unit_count])
    members = {}
    for node in nodes:
        unit = unit_of(node, code_units)
        if unit:
            members.setdefault(unit, []).append(node)
    titles = {}
    for unit, rows in members.items():
        if unit.startswith("code-"):
            titles[unit] = code_unit_title(rows, degree)
        elif unit.startswith("actor-"):
            titles[unit] = f"{rows[0]['kind']} {rows[0]['label']}"
        else:
            titles[unit] = f"{rows[0]['asset_kind']} ({len(rows)} files)"
    inside, outgoing, incoming = {}, {}, {}
    for link in links:
        a = unit_of(by_id[link["source"]], code_units)
        b = unit_of(by_id[link["target"]], code_units)
        if a and a == b:
            row = inside.setdefault(a, {})
            key = f"{link['relation']} ({link['confidence']})"
            row[key] = row.get(key, 0) + 1
            continue
        example = {"from": by_id[link["source"]]["label"], "to": by_id[link["target"]]["label"],
                   "relation": link["relation"], "basis": link["confidence"],
                   "to_file": by_id[link["target"]].get("source_file") or None}
        other = lambda unit, node: unit or (node.get("source_file") or node["label"])  # noqa: E731
        if a:
            row = outgoing.setdefault(a, {}).setdefault(other(b, by_id[link["target"]]), {"count": 0, "examples": []})
            row["count"] += 1
            if len(row["examples"]) < EXAMPLE_ROWS:
                row["examples"].append(example)
        if b:
            row = incoming.setdefault(b, {}).setdefault(other(a, by_id[link["source"]]), {"count": 0, "examples": []})
            row["count"] += 1
            if len(row["examples"]) < EXAMPLE_ROWS:
                row["examples"].append(example)

    def neighbours(table):
        rows = sorted(table.items(), key=lambda item: (-item[1]["count"], item[0]))[:NEIGHBOUR_ROWS]
        return [{"unit_or_file": key, "title": titles.get(key), **value} for key, value in rows]

    packets = []
    for unit in sorted(members, key=lambda u: (u.split("-")[0], -len(members[u]), u)):
        rows = sorted(members[unit], key=lambda n: (-degree[n["id"]], n["id"]))
        kind = unit.split("-")[0]
        lint = {}
        for node in rows:
            for code, count in (node.get("lint") or {}).items() if node["kind"] != "file" or kind != "code" else []:
                lint[code] = lint.get(code, 0) + count
        packets.append({
            "unit": unit, "kind": kind, "title": titles[unit], "root": graph["graph"].get("root"),
            "members_total": len(rows), "members_shown": min(len(rows), MEMBER_ROWS),
            "members": [{"id": n["id"], "label": n["label"], "kind": n["kind"], "file": n.get("source_file"),
                         "line": n.get("source_location"), "links": degree[n["id"]],
                         **({"lint": n["lint"]} if n.get("lint") else {}),
                         **({"command": n["command"]} if n.get("command") else {})}
                        for n in rows[:MEMBER_ROWS]],
            "files": sorted({n["source_file"] for n in rows if n.get("source_file")})[:200],
            "links_inside": dict(sorted((inside.get(unit) or {}).items(), key=lambda item: -item[1])),
            "reaches": neighbours(outgoing.get(unit) or {}),
            "reached_by": neighbours(incoming.get(unit) or {}),
            "lint": dict(sorted(lint.items(), key=lambda item: -item[1])),
            "questions": QUESTIONS[kind],
        })
    return packets


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--graph", required=True, help="graph.json from graph_export.py")
    parser.add_argument("--run", required=True, help="the run directory; packets land in <run>/analysis")
    parser.add_argument("--code-units", type=int, default=12, help="how many of the largest code communities get a packet")
    args = parser.parse_args()

    graph = graph_export.read_json(args.graph)
    packets = build_packets(graph, args.code_units)
    out = os.path.join(args.run, "analysis", "packets")
    os.makedirs(out, exist_ok=True)
    lines = ["# Units for analysis", "",
             "One packet per unit. An analyst takes a packet, reads the source it points at, and records claims "
             "with `scripts/audit.py`; see `references/analysis-brief.md`.", "",
             "| Unit | Kind | What it is | Members | Reaches | Reached by |", "|---|---|---|---|---|---|"]
    for packet in packets:
        packet["record_with"] = {
            "intake": f"python scripts/audit.py intake --run {args.run} --actor <you> --source agent "
                      f"--unit {packet['unit']} --concern <concern> --statement \"<one checkable sentence>\"",
            "then": "python scripts/audit.py record <claim> <stage> --run <run> --actor <you> ...  "
                    "(findings, evidence, conflicts, organization, refutation, judgement, verdict, qualification)",
        }
        graph_export.write_text(os.path.join(out, packet["unit"] + ".json"),
                                json.dumps(packet, indent=2, ensure_ascii=False) + "\n")
        lines.append(f"| `{packet['unit']}` | {packet['kind']} | {packet['title']} | {packet['members_total']} | "
                     f"{len(packet['reaches'])} | {len(packet['reached_by'])} |")
    graph_export.write_text(os.path.join(args.run, "analysis", "INDEX.md"), "\n".join(lines) + "\n")
    json.dump({"packets": len(packets), "dir": out,
               "by_kind": {kind: sum(1 for p in packets if p["kind"] == kind) for kind in ("code", "actor", "asset")}},
              sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
