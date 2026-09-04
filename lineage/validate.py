#!/usr/bin/env python3
"""Check lineage.yaml against the rules it is kept under.

Fails when a node or edge is missing the evidence that makes it worth
recording, or when an edge points at a node that does not exist. Nodes that
no edge touches are reported but do not fail: most repositories here are
genuinely unconnected, and hiding that would be the opposite of the point.

Reads a small fixed subset of YAML rather than taking a dependency.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINEAGE = Path(__file__).resolve().parent / "lineage.yaml"

NODE_RE = re.compile(r"^  ([a-z0-9][a-z0-9-]*):$")


def scalar(raw: str) -> str:
    """The value's text, with surrounding quotes removed.

    Without this, `result: ""` reads as the two quote characters, which is
    truthy, and an empty evidence field passes the emptiness checks below.
    """
    value = raw.strip()
    if value and value[0] in "\"'":
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
        return value[1:]
    # An unquoted scalar may carry a trailing comment; the value stops there.
    if "#" in value:
        value = value.split("#", 1)[0]
    return value.strip()
FIELD_RE = re.compile(r"^    ([a-z_]+):\s*(.*)$")
EVIDENCE_FIELD_RE = re.compile(r"^      ([a-z_]+):\s*(.*)$")
EDGE_START_RE = re.compile(r"^  - from:\s*(\S+)$")
EDGE_FIELD_RE = re.compile(r"^    ([a-z_]+):\s*(.*)$")

REQUIRED_NODE_FIELDS = ("repo", "status", "line", "claim", "topics")
REQUIRED_EVIDENCE_FIELDS = ("command", "result", "observed")
REQUIRED_EDGE_FIELDS = ("to", "type", "evidence")


def parse(text: str):
    """Return (nodes, edges) from the file's fixed shape."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    section = None
    node = None
    edge = None
    in_evidence = False

    for line in text.splitlines():
        if line.startswith("nodes:"):
            section, node, edge = "nodes", None, None
            continue
        if line.startswith("edges:"):
            section, node, edge = "edges", None, None
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if section == "nodes":
            m = NODE_RE.match(line)
            if m:
                node = {"id": m.group(1), "evidence": {}}
                nodes[m.group(1)] = node
                in_evidence = False
                continue
            if node is None:
                continue
            m = FIELD_RE.match(line)
            if m:
                key, value = m.group(1), scalar(m.group(2))
                in_evidence = key == "evidence"
                if not in_evidence:
                    node[key] = value
                continue
            m = EVIDENCE_FIELD_RE.match(line)
            if m and in_evidence:
                node["evidence"][m.group(1)] = scalar(m.group(2))

        elif section == "edges":
            m = EDGE_START_RE.match(line)
            if m:
                edge = {"from": m.group(1)}
                edges.append(edge)
                continue
            if edge is None:
                continue
            m = EDGE_FIELD_RE.match(line)
            if m:
                key, value = m.group(1), scalar(m.group(2))
                edge.setdefault(key, value)

    return nodes, edges


def main() -> int:
    text = LINEAGE.read_text(encoding="utf-8")
    nodes, edges = parse(text)
    failures: list[str] = []

    if not nodes:
        failures.append("no nodes parsed")
    if not edges:
        failures.append("no edges parsed")

    for name, node in sorted(nodes.items()):
        for field in REQUIRED_NODE_FIELDS:
            if not node.get(field):
                failures.append(f"node {name}: missing {field}")
        for field in REQUIRED_EVIDENCE_FIELDS:
            if not node.get("evidence", {}).get(field):
                failures.append(f"node {name}: evidence missing {field}")
        repo = node.get("repo", "")
        if repo and not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            failures.append(f"node {name}: repo {repo!r} is not owner/name")

        # GitHub's own limits on the fields this file projects into.
        claim = node.get("claim", "")
        if len(claim) > 350:
            failures.append(f"node {name}: claim is {len(claim)} chars, over GitHub's 350")
        for topic in node.get("topics", "").split():
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", topic):
                failures.append(f"node {name}: topic {topic!r} is not a legal GitHub topic")
        if len(node.get("topics", "").split()) > 20:
            failures.append(f"node {name}: more than 20 topics")

    touched = set()
    for index, edge in enumerate(edges):
        label = f"edge {index} ({edge.get('from')} -> {edge.get('to')})"
        for field in REQUIRED_EDGE_FIELDS:
            if not edge.get(field):
                failures.append(f"{label}: missing {field}")
        for end in ("from", "to"):
            target = edge.get(end)
            if target and target not in nodes:
                failures.append(f"{label}: {end} names no node ({target})")
            elif target:
                touched.add(target)

    orphans = sorted(set(nodes) - touched)

    print(f"nodes: {len(nodes)}    edges: {len(edges)}")
    if orphans:
        print(f"unconnected nodes ({len(orphans)}): {', '.join(orphans)}")
    if failures:
        print(f"\nFAIL — {len(failures)} problem(s):")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("\nPASS — every node carries a claim and observed evidence; "
          "every edge carries evidence and resolves to a node.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
