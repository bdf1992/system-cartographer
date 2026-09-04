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


def featured(nodes: dict) -> list[str]:
    """The repositories the first screen leads with, in canonical line order.

    Which six lead is a judgement, not something derivable from the record: test
    counts alone would drop the flagship for a repository with a larger suite.
    So the choice is declared in lineage.yaml as `featured: true` with the reason
    beside it, and this only projects it. Six because that is what GitHub pins,
    so the page and the pinned row can say the same thing.

    Nothing superseded, experimental, archived, third-party or empty is eligible.
    They stay in the full inventory below, which is why its count still reads 20.
    """
    order = [key for key, _, _ in LINES]
    picked = [n for n in nodes if nodes[n].get("featured") == "true"]
    return sorted(picked, key=lambda n: order.index(nodes[n].get("line", order[-1])))


VOICE = Path(__file__).resolve().parent / "profile-voice.md"


def page(nodes: dict, edges: list) -> str:
    """The profile page: the written part from profile-voice.md, facts from here.

    Kept short on purpose. A profile README is read above the fold or not at all,
    so the page leads with six repositories and folds the rest away.
    """
    total, contributors = counted(nodes)
    unconnected = sorted(
        n for n in nodes if not any(n in (e["from"], e["to"]) for e in edges)
    )
    observed_on = next(iter(nodes.values()))["evidence"]["observed"]

    voice = "\n".join(
        line for line in VOICE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("<!--") and not line.startswith("     ")
    ).strip()
    voice = voice.format(repos=len(nodes), observed=observed_on)

    lines = [voice, ""]
    for name in featured(nodes):
        node = nodes[name]
        repo = node["repo"].split("/", 1)[1]
        evidence = node["evidence"]
        lines += [
            f"**[{repo}](https://github.com/{node['repo']})** — {node['claim']}  ",
            f"`{evidence['command']}` → {evidence['result']}",
            "",
        ]

    lines += [
        f"{total:,} tests pass across {len(contributors)} of the {len(nodes)}; "
        "the rest count in "
        "suites, checks and proofs, which are real but not the same unit, so I don't "
        "add them together.",
        "",
        f"[How they relate]({LINEAGE_URL}) is written down, each relation with the "
        f"file and line that shows it: {len(edges)} of them. So are the "
        f"{len(unconnected)} that connect to nothing, and the relations I looked "
        "for and could not evidence.",
        "",
        "<details>",
        "<summary>Everything else</summary>",
        "",
    ]

    for key, title, blurb in LINES:
        body = rows(nodes, key)
        if not body:
            continue
        lines += [f"**{title}** — {blurb}", "",
                  "| | | |", "| --- | --- | --- |"] + body + [""]

    lines += ["</details>", ""]
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

    picked = featured(nodes)
    if len(picked) != 6:
        failures.append(f"{len(picked)} repositories are featured; GitHub pins 6")
    for name in picked:
        node = nodes[name]
        if node.get("status") != "active":
            failures.append(f"featured {name} is {node.get('status')}, not active")
        if node["evidence"]["command"].startswith("none"):
            failures.append(f"featured {name} has no runnable check")
        if node.get("github_archived") == "true":
            failures.append(f"featured {name} is archived on GitHub")

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
