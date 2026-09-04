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
    """The profile page: written part from profile-voice.md, facts from the record.

    It carries the featured repositories and nothing else. The full inventory —
    archived work, the third-party copy, the empty name, everything unconnected —
    stays in lineage.yaml, which the page links rather than reprints. A profile is
    read above the fold, and an archived repository is not what a reader should
    meet first.
    """
    total, contributors = counted(nodes)
    unconnected = sum(
        1 for n in nodes if not any(n in (e["from"], e["to"]) for e in edges)
    )
    observed_on = next(iter(nodes.values()))["evidence"]["observed"]

    voice = "\n".join(
        line for line in VOICE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("<!--") and not line.startswith("     ")
    ).strip()

    lines = [voice.format(repos=len(nodes), observed=observed_on), ""]
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
        f"That is {len(featured(nodes))} of {len(nodes)}. Across all of them "
        f"{total:,} tests pass in {len(contributors)}; the rest count in suites, "
        "checks and proofs, which are real but not the same unit, so I don't add "
        "them together.",
        "",
        f"[The full record]({LINEAGE_URL}) has the other {len(nodes) - len(featured(nodes))} "
        f"— including what is archived and the {unconnected} that connect to nothing "
        f"— plus the {len(edges)} relations between them, each with the file and line "
        "that shows it, and the ones I looked for and could not evidence.",
        "",
    ]
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

    picked = featured(nodes)
    for name, node in nodes.items():
        shown = f"](https://github.com/{node['repo']})" in text
        if name in picked and not shown:
            failures.append(f"featured {name} is missing from the page")
        if name not in picked and shown:
            failures.append(f"{name} is on the page but not featured")
        if shown and node.get("github_archived") == "true":
            failures.append(f"{name} is archived on GitHub and reached the page")
        if shown and node.get("status") in ("archived", "empty", "reference",
                                            "superseded", "experiment"):
            failures.append(f"{name} has status {node['status']} and reached the page")

    if str(len(edges)) not in text:
        failures.append("the edge count is not stated")

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
    print(f"PASS — {len(picked)} featured of {len(nodes)} on the page, nothing "
          f"archived or closed reaching it, {total:,} tests summed from "
          f"{len(contributors)} observed results only.")
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
