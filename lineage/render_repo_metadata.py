#!/usr/bin/env python3
"""Emit the `gh repo edit` commands that set each repository's About box.

Descriptions and topics are projections of lineage.yaml, not a second list to
keep in step with it. Change the claim or the topics there and re-run this.

This session has no tool that reaches PATCH /repos/{owner}/{repo}, which is
what `gh repo edit` calls, so the commands are printed for someone with `gh`
to run rather than applied here.

    python lineage/render_repo_metadata.py            # the commands
    python lineage/render_repo_metadata.py --check    # what would change
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate import LINEAGE, parse  # noqa: E402


def commands() -> tuple[list[str], list[str]]:
    """Return (runnable, archived).\n\n    Keys off github_archived, the repository being read-only on GitHub, not off\n    status, which describes whether the work itself is finished. holon is a\n    closed phase but an editable repository; the two are not the same fact.\n    """
    nodes, _ = parse(LINEAGE.read_text(encoding="utf-8"))
    runnable: list[str] = []
    archived: list[str] = []
    for name in sorted(nodes):
        node = nodes[name]
        parts = ["gh", "repo", "edit", node["repo"], "--description", node["claim"]]
        for topic in node.get("topics", "").split():
            parts += ["--add-topic", topic]
        line = " ".join(shlex.quote(p) for p in parts)
        (archived if node.get("github_archived") == "true" else runnable).append(line)
    return runnable, archived


def main() -> int:
    runnable, archived = commands()
    if "--check" in sys.argv:
        print(f"{len(runnable)} repositories would be updated, "
              f"{len(archived)} skipped as archived.")
        return 0
    print("# Generated from lineage.yaml. Do not hand-edit; re-run the renderer.")
    print("# Requires `gh` authenticated as the repository owner.")
    print()
    for line in runnable:
        print(line)
    if archived:
        print()
        print("# Archived on GitHub. These are rejected until the repository is")
        print("# unarchived, so they are commented out rather than left to fail.")
        for line in archived:
            print(f"# {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
