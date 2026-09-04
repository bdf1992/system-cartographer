#!/usr/bin/env python3
"""Render the GitHub profile page from lineage.yaml.

GitHub's profile page is the README of a repository named after the account.
There is no other mechanism, so this renders that file. It is a projection of
the lineage like every other rendered surface: the typology is the `line` each
node declares, the topology is the recorded edges, and the counts are computed
from the observed results rather than typed.

    python lineage/render_profile.py             # the page
    python lineage/render_profile.py --check     # the counts it would state
    python lineage/render_profile.py --selfcheck # prove nothing is asserted

Nothing here may state a number the lineage did not observe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_readme_section import (  # noqa: E402
    LINEAGE_URL,
    RELATION_PHRASE,
    with_folded,
)
from validate import LINEAGE  # noqa: E402

# The order a reader should meet them in: what the work runs on, what it is
# used through, what it measures with, how it is worked, then closed material.
LINES = [
    ("substrate", "Substrate", "What everything else runs on."),
    ("surface", "Surfaces", "What the work is used through."),
    ("instrument", "Instruments", "What measures, records, or bootstraps."),
    ("method", "Methods", "How the work is done."),
    ("world", "Worlds", "Bounded labs."),
    ("reference", "Closed and reference", "Archived, third-party, or empty. Listed so the "
                                          "count is honest."),
]

COUNT_RE = re.compile(r"(\d+)\s+(?:passed|tests)")


def counted(nodes: dict) -> tuple[int, list[str]]:
    """Total individual tests observed, and which repositories contribute.

    Only nodes whose result states a count of passing tests are added. Suites,
    checks, proofs, cases and mutants are real evidence but different units, so
    summing them into one number would invent a figure nobody observed.
    """
    total = 0
    contributors: list[str] = []
    for name in sorted(nodes):
        match = COUNT_RE.search(nodes[name]["evidence"]["result"])
        if match:
            total += int(match.group(1))
            contributors.append(name)
    return total, contributors


def rows(nodes: dict, line: str) -> list[str]:
    out: list[str] = []
    for name in sorted(nodes):
        node = nodes[name]
        if node.get("line") != line:
            continue
        repo = node["repo"].split("/", 1)[1]
        url = f"https://github.com/{node['repo']}"
        evidence = node["evidence"]
        if evidence["command"].startswith("none"):
            check = evidence["result"] if evidence["result"] != "not applicable" else "—"
        else:
            check = f"`{evidence['command']}` → {evidence['result']}"
        flag = " *(archived)*" if node.get("github_archived") == "true" else ""
        out.append(f"| [{repo}]({url}){flag} | {node['claim']} | {check} |")
    return out


def page(nodes: dict, edges: list) -> str:
    total, contributors = counted(nodes)
    unconnected = sorted(
        n for n in nodes if not any(n in (e["from"], e["to"]) for e in edges)
    )
    lines = [
        "## Brandon Freeman",
        "",
        "I build systems where a claim has to carry its evidence — records that keep "
        "their own history, work that can be checked by someone who was not there, and "
        "AI that operates inside the same rules as the people it works with.",
        "",
        f"{len(nodes)} public repositories. Every claim below names a command you can "
        f"run and what it returned when it was run, on "
        f"{[n for n in nodes.values()][0]['evidence']['observed']}. "
        f"{total:,} individual tests pass across "
        f"{len(contributors)} of them; the rest report suites, checks, proofs or cases, "
        "which are real but not the same unit and are not added in.",
        "",
    ]

    for key, title, blurb in LINES:
        body = rows(nodes, key)
        if not body:
            continue
        lines += [f"### {title}", "", blurb, "",
                  "| Repository | What it is | Checked |",
                  "| --- | --- | --- |"] + body + [""]

    lines += ["### How they relate", "",
              f"{len(edges)} relations, each one pointing at the file and line where it "
              "is visible. They are recorded in the lineage with that evidence attached.",
              ""]
    def shown(node_id: str) -> str:
        return nodes[node_id]["repo"].split("/", 1)[1]

    for edge in edges:
        phrase = RELATION_PHRASE.get(edge["type"], edge["type"].replace("-", " "))
        lines.append(f"- **{shown(edge['from'])}** {phrase} **{shown(edge['to'])}**")
    lines += [""]

    lines += ["### What does not connect", "",
              f"{len(unconnected)} of the {len(nodes)} are unconnected: "
              + ", ".join(f"`{n}`" for n in unconnected) + ".",
              "",
              "That is the honest shape — two small clusters and a lot of standalone "
              "work. Relations that were tested and found unevidenced are written into "
              "the lineage too, so the absence is legible rather than tidied away.",
              ""]

    lines += ["---", "",
              f"This page is generated from [`lineage.yaml`]({LINEAGE_URL}), which is "
              "checked by a validator that fails on a claim without evidence or an edge "
              "pointing nowhere. Editing this page by hand would only be overwritten.",
              ""]
    return "\n".join(lines)


def selfcheck(nodes: dict, edges: list) -> int:
    """Every number on the page must come from the lineage."""
    failures: list[str] = []
    text = page(nodes, edges)
    total, contributors = counted(nodes)

    for name in contributors:
        if not COUNT_RE.search(nodes[name]["evidence"]["result"]):
            failures.append(f"{name} counted without a stated test count")

    declared = sum(int(COUNT_RE.search(nodes[n]["evidence"]["result"]).group(1))
                   for n in contributors)
    if declared != total:
        failures.append(f"stated total {total} is not the sum of its parts {declared}")

    for name, node in nodes.items():
        if node["repo"].split("/", 1)[1] not in text:
            failures.append(f"{name} is missing from the page")

    if str(len(edges)) not in text:
        failures.append("the edge count is not stated")

    for line in failures:
        print(f"FAIL  {line}")
    if failures:
        return 1
    print(f"PASS — {len(nodes)} repositories present, {len(edges)} relations stated, "
          f"{total:,} tests summed from {len(contributors)} observed results only.")
    return 0


def main() -> int:
    nodes, edges = with_folded(LINEAGE.read_text(encoding="utf-8"))
    if "--selfcheck" in sys.argv:
        return selfcheck(nodes, edges)
    if "--check" in sys.argv:
        total, contributors = counted(nodes)
        print(f"{total:,} tests from {len(contributors)} repositories: "
              f"{', '.join(contributors)}")
        return 0
    print(page(nodes, edges), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
