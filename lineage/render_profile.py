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

TOKEN_RE = re.compile(r"\{([a-z0-9-]+)(?:\.([a-z]+))?\}")


def resolve(nodes: dict, edges: list) -> dict[str, str]:
    """Every token the voice may use, and what it expands to.

    A repository token becomes a link built from the record, so renaming a
    repository in lineage.yaml moves every reference to it and a reference to a
    repository that does not exist fails loudly instead of shipping a dead link.
    """
    total, contributors = counted(nodes)
    values = {
        "total": f"{total:,}",
        "contributors": str(len(contributors)),
        "repos": str(len(nodes)),
        "edges": str(len(edges)),
        "unconnected": str(sum(
            1 for n in nodes if not any(n in (e["from"], e["to"]) for e in edges))),
        "observed": next(iter(nodes.values()))["evidence"]["observed"],
        "lineage": f"[The full record]({LINEAGE_URL})",
    }
    for name, node in nodes.items():
        shown = node["repo"].split("/", 1)[1]
        values[name] = f"[{shown}](https://github.com/{node['repo']})"
        evidence = node["evidence"]
        values[f"{name}.check"] = (
            evidence["result"] if evidence["command"].startswith("none")
            else f"`{evidence['command']}` → {evidence['result']}"
        )
    return values


def page(nodes: dict, edges: list) -> str:
    """The profile page: prose from profile-voice.md, every reference resolved here.

    The page is a description with references, not an inventory. Archived and
    closed work is named where the prose has a reason to name it, rather than
    listed as though a reader should go and look at it.
    """
    values = resolve(nodes, edges)
    text = "\n".join(
        line for line in VOICE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("<!--") and not line.startswith("     ")
    ).strip()

    unknown: list[str] = []

    def expand(match: re.Match) -> str:
        key = match.group(1) + (f".{match.group(2)}" if match.group(2) else "")
        if key not in values:
            unknown.append(key)
            return match.group(0)
        return values[key]

    text = TOKEN_RE.sub(expand, text)
    if unknown:
        raise KeyError(f"profile-voice.md references unknown: {sorted(set(unknown))}")
    return text + "\n"


def selfcheck(nodes: dict, edges: list) -> int:
    """Prove the page states nothing it did not get from the record."""
    failures: list[str] = []
    text = page(nodes, edges)
    total, contributors = counted(nodes)

    left = TOKEN_RE.findall(text)
    if left:
        failures.append(f"unresolved references remain: {left}")

    declared = sum(int(COUNT_RE.search(nodes[n]["evidence"]["result"]).group(1))
                   for n in contributors)
    if declared != total:
        failures.append(f"stated total {total} is not the sum of its parts {declared}")

    plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)

    picked = featured(nodes)
    if len(picked) != 6:
        failures.append(f"{len(picked)} repositories are featured; GitHub pins 6")
    for name in picked:
        node = nodes[name]
        if f"](https://github.com/{node['repo']})" not in text:
            failures.append(f"featured {name} is never mentioned on the page")
        if node.get("status") != "active":
            failures.append(f"featured {name} is {node.get('status')}, not active")
        if node["evidence"]["command"].startswith("none"):
            failures.append(f"featured {name} has no runnable check")
        if node.get("github_archived") == "true":
            failures.append(f"featured {name} is archived on GitHub")

    # Archived work may be named where the prose has a reason to name it, but a
    # reader must never be pointed at it without being told what it is.
    for name, node in nodes.items():
        linked = f"](https://github.com/{node['repo']})" in text
        closed = (node.get("github_archived") == "true"
                  or node.get("status") in ("archived", "empty", "reference"))
        if linked and closed:
            shown = node["repo"].split("/", 1)[1]
            near = re.search(rf"{re.escape(shown)}[^.]*?\.", plain, re.S)
            if not near or not re.search(r"archived|empty|third-party|copy",
                                         near.group(0)):
                failures.append(f"{name} is linked without being called what it is")

    # A number the record did not supply cannot be verified by running anything,
    # so the sentence carrying it has to say so. Otherwise an unverifiable figure
    # sits beside checkable ones and borrows their standing.
    source = "\n".join(
        line for line in VOICE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("<!--") and not line.startswith("     ")
    )
    bare = re.sub(r"\{[^}]*\}", "", source)
    for sentence in re.split(r"(?<=\.)\s", bare):
        if re.search(r"\d", sentence) and not re.search(
                r"can'?t check|cannot check|behind a company", sentence, re.I):
            around = " ".join(bare.split("\n"))
            index = around.find(sentence.strip().split("\n")[0][:40])
            window = around[max(0, index - 200):index + 400]
            if not re.search(r"can'?t check|cannot check|behind a company",
                             window, re.I):
                failures.append(
                    f"a hand-typed number is stated without saying it cannot be "
                    f"checked: {sentence.strip()[:70]!r}")

    for line in failures:
        print(f"FAIL  {line}")
    if failures:
        return 1
    linked = sum(1 for n in nodes
                 if f"](https://github.com/{nodes[n]['repo']})" in text)
    print(f"PASS — {linked} of {len(nodes)} repositories referenced, every reference "
          f"resolved, {total:,} tests summed from {len(contributors)} observed "
          f"results only.")
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
