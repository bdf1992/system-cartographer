#!/usr/bin/env python3
"""Emit a script that reconciles each repository's About box with lineage.yaml.

Descriptions and topics are projections of lineage.yaml, not a second list to
keep in step with it. Change the claim or the topics there and re-run this.

No tool in this environment reaches PATCH /repos/{owner}/{repo}, which is what
`gh repo edit` calls, so the reconciliation is emitted for someone with `gh` to
run. What is emitted is not a list of blind edits: each block reads the value
GitHub currently holds, skips the repository when it already matches, and prints
the old value beside the new one when it does not. Running it twice changes
nothing the second time, and running it after the lineage moves changes only
what moved.

    python lineage/render_repo_metadata.py            # the script
    python lineage/render_repo_metadata.py --check    # how many would be touched
    python lineage/render_repo_metadata.py --observed # the state read on 2026-09-04
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate import LINEAGE, parse  # noqa: E402

# Read from the GitHub API on 2026-09-04, across all 20 public repositories.
# Recorded because it is the baseline the reconciliation was designed against
# and because it is the finding: the account's front door is almost entirely
# blank. The emitted script re-reads live state rather than trusting this.
OBSERVED = """\
descriptions set:      5 of 20  (DDD-CCC, Owl, schematically, Soveraeign, system-cartographer)
descriptions absent:  15 of 20
topics set:            0 of 20  — no repository carries a single topic
defects in the five:   Owl leads with a space; DDD-CCC trails with one
"""

PREAMBLE = """\
#!/usr/bin/env bash
# Generated from lineage.yaml by lineage/render_repo_metadata.py.
# Do not hand-edit; re-run the renderer.
#
# Requires `gh` authenticated as the repository owner. Reconciles each About box
# with the lineage: reads what GitHub holds now, reports it, and edits only when
# it differs. Safe to re-run; a second run reports every repository unchanged.
set -uo pipefail

changed=0
skipped=0

reconcile_description() {
  local repo="$1" want="$2" have
  have="$(gh repo view "$repo" --json description -q '.description // ""' 2>/dev/null)" || {
    printf '!  %-24s could not read current description\\n' "$repo"; return 1; }
  if [ "$have" = "$want" ]; then
    printf '=  %-24s description already current\\n' "$repo"; skipped=$((skipped+1)); return 0
  fi
  printf '~  %-24s description\\n' "$repo"
  printf '       was: %s\\n' "${have:-<empty>}"
  printf '       now: %s\\n' "$want"
  gh repo edit "$repo" --description "$want" >/dev/null && changed=$((changed+1))
}

reconcile_topics() {
  local repo="$1"; shift
  local have missing=() t
  have="$(gh repo view "$repo" --json repositoryTopics \\
          -q '.repositoryTopics[].name' 2>/dev/null)" || {
    printf '!  %-24s could not read current topics\\n' "$repo"; return 1; }
  for t in "$@"; do
    grep -qxF "$t" <<<"$have" || missing+=("$t")
  done
  if [ ${#missing[@]} -eq 0 ]; then
    printf '=  %-24s topics already current\\n' "$repo"; skipped=$((skipped+1)); return 0
  fi
  printf '~  %-24s topics + %s\\n' "$repo" "${missing[*]}"
  gh repo edit "$repo" $(printf -- '--add-topic %s ' "${missing[@]}") >/dev/null \\
    && changed=$((changed+1))
}
"""

EPILOGUE = """
printf '\\n%s edit(s) applied, %s already current.\\n' "$changed" "$skipped"
"""


def blocks() -> tuple[list[str], list[str]]:
    """Return (runnable, archived) reconciliation blocks.

    Keys off github_archived, the repository being read-only on GitHub, not off
    status, which describes whether the work itself is finished. holon is a
    closed phase but an editable repository; the two are not the same fact.
    """
    nodes, _ = parse(LINEAGE.read_text(encoding="utf-8"))
    runnable: list[str] = []
    archived: list[str] = []
    for name in sorted(nodes):
        node = nodes[name]
        repo = shlex.quote(node["repo"])
        lines = [f"reconcile_description {repo} {shlex.quote(node['claim'])}"]
        topics = node.get("topics", "").split()
        if topics:
            lines.append(
                f"reconcile_topics {repo} " + " ".join(shlex.quote(t) for t in topics)
            )
        (archived if node.get("github_archived") == "true" else runnable).append(
            "\n".join(lines)
        )
    return runnable, archived


def main() -> int:
    if "--observed" in sys.argv:
        print(OBSERVED, end="")
        return 0

    runnable, archived = blocks()

    if "--check" in sys.argv:
        print(f"{len(runnable)} repositories would be reconciled, "
              f"{len(archived)} skipped as archived. The emitted script edits only "
              f"what differs from GitHub's current value.")
        return 0

    print(PREAMBLE)
    for block in runnable:
        print(block)
        print()
    if archived:
        print("# Archived on GitHub. `gh repo edit` is rejected until the repository")
        print("# is unarchived, so these are commented out rather than left to fail.")
        for block in archived:
            for line in block.splitlines():
                print(f"# {line}")
            print("#")
    print(EPILOGUE, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
