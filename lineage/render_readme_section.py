#!/usr/bin/env python3
"""Project lineage.yaml into a generated README section, one per repository.

The relations are recorded in lineage.yaml, but a reader arriving at a
repository never sees that file. This renders each node's claim, its observed
check, and its evidenced relations into a marker-bounded block that is written
into that repository's README. The block is generated: change lineage.yaml and
re-run this, never hand-edit the block.

    python lineage/render_readme_section.py --node owl        # print one block
    python lineage/render_readme_section.py --check           # what would change
    python lineage/render_readme_section.py --apply /path/to/Owl --node owl
    python lineage/render_readme_section.py --selfcheck       # prove the splice

Absence is rendered, not hidden. A repository that no edge touches says so.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate import LINEAGE, parse  # noqa: E402

BEGIN = "<!-- lineage:begin — generated from system-cartographer lineage/lineage.yaml. Do not hand-edit. -->"
END = "<!-- lineage:end -->"

# lineage.yaml currently lives on this branch, not on system-cartographer's
# default branch. Linking at the default branch would dangle until the branch
# merges, and a link that does not resolve is the defect this whole artifact
# exists to avoid. Re-point this once the branch lands.
REF = "claude/access-requirements-zbl1s7"
LINEAGE_URL = (
    f"https://github.com/bdf1992/system-cartographer/blob/{REF}/lineage/lineage.yaml"
)

RELATION_PHRASE = {
    "implements-format-of": "implements the document format of",
    "supersedes": "supersedes",
    "may-provide-substrate": "may provide substrate to",
    "adapts": "adapts",
    "uses": "uses",
    "references": "references",
    "sibling-phase": "is parallel work with",
}


def with_folded(text: str):
    """Compatibility name: the shared YAML parser now handles folded scalars."""
    return parse(text)


def relations(name: str, nodes: dict, edges: list) -> list[str]:
    """One bullet per edge touching this node, in either direction."""
    out: list[str] = []
    for edge in edges:
        if name not in (edge["from"], edge["to"]):
            continue
        if edge['state'] == 'unsupported':
            continue
        phrase = RELATION_PHRASE.get(edge["type"], edge["type"].replace("-", " "))
        other = edge["to"] if edge["from"] == name else edge["from"]
        subject = "This repository" if edge["from"] == name else f"`{other}`"
        object_ = f"`{other}`" if edge["from"] == name else "this repository"
        out.append(f"- [{edge['state']}] {subject} **{phrase}** {object_}. {edge['evidence']} {edge['limit']}")
    return out


def block(name: str, nodes: dict, edges: list) -> str:
    """The generated section for one node."""
    node = nodes[name]
    evidence = node["evidence"]
    unconnected = sum(
        1 for other in nodes
        if not relations(other, nodes, edges)
    )

    lines = [BEGIN, "", "## Where this sits", "", (
        f"This is one of {len(nodes)} repositories on this account whose relations "
        f"are recorded, with the evidence for each, in "
        f"[`lineage.yaml`]({LINEAGE_URL}). What that record says about this one:"
    ), ""]

    lines += [f"**Claim.** {node['claim']}", ""]

    if evidence["command"].startswith("none"):
        lines += [f"**Source inspection.** {evidence['command']} ({evidence['result']}), "
                  f"observed {evidence['observed']}.", ""]
    else:
        lines += [f"**Source inspection.** `{evidence['command']}` — {evidence['result']}, "
                  f"observed {evidence['observed']}.", ""]

    lines += ["Run this source check from the system-cartographer checkout. It checks a pinned source file; it does not certify the runtime or repeat a test suite.", ""]

    found = relations(name, nodes, edges)
    if found:
        lines += ["**Relations.**", ""] + found + [""]
    else:
        lines += [(
            "**Relations.** None recorded, in either direction. "
            f"{unconnected} of the {len(nodes)} repositories are unconnected; "
            "that absence is recorded rather than papered over with a plausible edge."
        ), ""]

    if node.get("note"):
        lines += [f"**Note.** {node['note']}", ""]

    lines += [END]
    return "\n".join(lines) + "\n"


def splice(readme: str, generated: str) -> str:
    """README with the generated block appended, or the existing one replaced.

    Idempotent by construction: a second application over an already-spliced
    README replaces the block between the markers rather than appending a
    second copy.
    """
    start = readme.find(BEGIN)
    if start != -1:
        end = readme.find(END, start)
        if end == -1:
            raise ValueError("opening marker with no closing marker")
        return readme[:start] + generated + readme[end + len(END):].lstrip("\n")
    return readme.rstrip("\n") + "\n\n" + generated


def selfcheck(nodes: dict, edges: list) -> int:
    """Prove the properties the splice is relied on for."""
    failures: list[str] = []
    sample = block("owl", nodes, edges)

    once = splice("# Owl\n\nSome prose.\n", sample)
    twice = splice(once, sample)
    if once != twice:
        failures.append("splice is not idempotent: re-applying changed the file")
    if once.count(BEGIN) != 1 or twice.count(BEGIN) != 1:
        failures.append("splice duplicated the block instead of replacing it")
    if not once.startswith("# Owl\n\nSome prose.\n"):
        failures.append("splice did not preserve the prose above the block")

    changed = splice(once, block("howdo", nodes, edges))
    if "familiar" in changed.split(BEGIN)[1]:
        failures.append("replacement left content from the previous block")

    try:
        splice("# X\n\n" + BEGIN + "\nno closing marker\n", sample)
    except ValueError:
        pass
    else:
        failures.append("an unterminated block was accepted")

    for name in sorted(nodes):
        text = block(name, nodes, edges)
        if "None recorded" not in text and "**Relations.**" not in text:
            failures.append(f"node {name}: block states neither relations nor absence")

    for line in failures:
        print(f"FAIL  {line}")
    if failures:
        return 1
    print(f"PASS — splice is idempotent, replacing, prose-preserving; "
          f"{len(nodes)} blocks render.")
    return 0


def main() -> int:
    text = LINEAGE.read_text(encoding="utf-8")
    nodes, edges = with_folded(text)

    if "--selfcheck" in sys.argv:
        return selfcheck(nodes, edges)

    name = None
    if "--node" in sys.argv:
        name = sys.argv[sys.argv.index("--node") + 1]
        if name not in nodes:
            print(f"no such node: {name}", file=sys.stderr)
            return 1

    if "--check" in sys.argv:
        touched = sum(1 for n in nodes if relations(n, nodes, edges))
        print(f"{len(nodes)} blocks renderable; {touched} carry a relation, "
              f"{len(nodes) - touched} state its absence.")
        return 0

    if "--apply" in sys.argv:
        root = Path(sys.argv[sys.argv.index("--apply") + 1])
        if name is None:
            print("--apply needs --node", file=sys.stderr)
            return 1
        readme = root / "README.md"
        if not readme.exists():
            print(f"no README at {readme}", file=sys.stderr)
            return 1
        before = readme.read_text(encoding="utf-8")
        after = splice(before, block(name, nodes, edges))
        if after == before:
            print(f"unchanged  {name}")
            return 0
        readme.write_text(after, encoding="utf-8", newline="\n")
        print(f"written    {name} -> {readme}")
        return 0

    print(block(name, nodes, edges) if name else "\n".join(
        block(n, nodes, edges) for n in sorted(nodes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
