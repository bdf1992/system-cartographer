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
    printf '!  %-24s could not read current description\n' "$repo"; return 1; }
  if [ "$have" = "$want" ]; then
    printf '=  %-24s description already current\n' "$repo"; skipped=$((skipped+1)); return 0
  fi
  printf '~  %-24s description\n' "$repo"
  printf '       was: %s\n' "${have:-<empty>}"
  printf '       now: %s\n' "$want"
  gh repo edit "$repo" --description "$want" >/dev/null && changed=$((changed+1))
}

reconcile_topics() {
  local repo="$1"; shift
  local have missing=() t
  have="$(gh repo view "$repo" --json repositoryTopics \
          -q '.repositoryTopics[].name' 2>/dev/null)" || {
    printf '!  %-24s could not read current topics\n' "$repo"; return 1; }
  for t in "$@"; do
    grep -qxF "$t" <<<"$have" || missing+=("$t")
  done
  if [ ${#missing[@]} -eq 0 ]; then
    printf '=  %-24s topics already current\n' "$repo"; skipped=$((skipped+1)); return 0
  fi
  printf '~  %-24s topics + %s\n' "$repo" "${missing[*]}"
  gh repo edit "$repo" $(printf -- '--add-topic %s ' "${missing[@]}") >/dev/null \
    && changed=$((changed+1))
}

reconcile_description bdf1992/baseless 'An empty repository. The name is reserved and nothing has been committed to it.'
reconcile_topics bdf1992/baseless placeholder

reconcile_description bdf1992/Canvas 'Arranges addressable things in space, relates them visibly, and wires a subset into executable circuits.'
reconcile_topics bdf1992/Canvas spatial-composition canvas wiring addressable-objects python

reconcile_description bdf1992/context 'A single-file harness that installs into any directory and gives an agent a bounded world to work in.'
reconcile_topics bdf1992/context llm-agents context-management single-file harness bootstrap

reconcile_description bdf1992/DDD-CCC 'Measures how much of a repository'"'"'s meaning is actually covered by its tests, and names the gaps.'
reconcile_topics bdf1992/DDD-CCC test-coverage semantic-coverage mutation-testing static-analysis python

reconcile_description bdf1992/evident 'A session-based instrument for bootstrapping how an organization works, in about thirty minutes.'
reconcile_topics bdf1992/evident organizational-design bootstrap ai-native session-based

reconcile_description bdf1992/familiar 'A local-first workbench for agent guidance that a practitioner has to accept before it binds.'
reconcile_topics bdf1992/familiar agent-guidance local-first workbench portable-agents python

reconcile_description bdf1992/holon 'An archived notebook on whether one generative distinction could account for structure and form.'
reconcile_topics bdf1992/holon research archive notes formal-systems

reconcile_description bdf1992/HowDo 'A discipline for understanding a problem before acting on it.'
reconcile_topics bdf1992/HowDo methodology discipline understanding-before-acting python

reconcile_description bdf1992/ide 'A small in-chat editor that opens in a side panel and reuses proven browser components.'
reconcile_topics bdf1992/ide editor chatgpt browser side-panel javascript

reconcile_description bdf1992/LangWorld 'An unmodified copy of LangChain'"'"'s react-agent template. None of the code is the owner'"'"'s.'
reconcile_topics bdf1992/LangWorld template langgraph third-party-copy reference

reconcile_description bdf1992/nostalgia 'An agent-assisted helper for getting classic games running and playable with others.'
reconcile_topics bdf1992/nostalgia retro-gaming emulation multiplayer compatibility agent-assisted

reconcile_description bdf1992/ontum 'A governed gateway for autonomous AI work, where the append-only log is the truth and every other view is folded from it.'
reconcile_topics bdf1992/ontum ai-native append-only-log agent-governance autonomous-agents provenance python

reconcile_description bdf1992/Owl 'Turns a rough request or exploratory mark into a complete, inspectable result, then redraws that same target from feedback without drifting into another project.'
reconcile_topics bdf1992/Owl methodology prototyping claude-code skill iteration

reconcile_description bdf1992/S4 'Tests whether the two-axis split between programs and protocols survives being handed to a fresh agent.'
reconcile_topics bdf1992/S4 protocol experiment agent-harness claude-code subprotocol

reconcile_description bdf1992/schematically 'A schematic editor whose document is a semantic model of components, parts and wires rather than a drawing.'
reconcile_topics bdf1992/schematically schematic-editor semantic-model svg mcp ai-native browser javascript

reconcile_description bdf1992/small-world 'A bounded lab for generative-world architecture, built for Catalyst Core.'
reconcile_topics bdf1992/small-world generative-worlds architecture catalyst-core javascript simulation

reconcile_description bdf1992/Soveraeign 'People and AI models work through the same records, permissions and history.'
reconcile_topics bdf1992/Soveraeign local-first ai-native provenance audit-log permissions records python

reconcile_description bdf1992/system-cartographer 'A Claude Code skill that reverse-engineers an undocumented agent or AI-native system into a description complete enough to rebuild it.'
reconcile_topics bdf1992/system-cartographer claude-code skill reverse-engineering documentation ai-native lineage

# Archived on GitHub. `gh repo edit` is rejected until the repository
# is unarchived, so these are commented out rather than left to fail.
# reconcile_description bdf1992/Agentic 'Spawned and scheduled real Claude Code sessions from a dashboard, each configured for a role.'
# reconcile_topics bdf1992/Agentic multi-agent claude-code dashboard orchestration archive
#
# reconcile_description bdf1992/onton 'Types how a generated artifact was formed, so trust carries across human, machine and composed work.'
# reconcile_topics bdf1992/onton provenance type-system ai-native artifact-provenance receipts python
#

printf '\n%s edit(s) applied, %s already current.\n' "$changed" "$skipped"
