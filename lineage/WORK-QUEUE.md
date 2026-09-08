# Continue the public lineage

## Public entrance pass — 2026-09-08

The profile now leads with six recent original projects and a plain implementation-state summary. The remaining public experiments and forks are available in a collapsed list. `lineage.yaml` remains the source; `featured` and `portfolio` choose the front row without asserting a runtime dependency or promoting project standing.

| Repository | Result | Validation |
| --- | --- | --- |
| ide | README purpose, prototype status, launch instructions and limitations landed on `main` ([commit](https://github.com/bdf1992/ide/commit/56479997f810dde035a0e025620fad1a47a6cc97)) | Chat artifact exporter passed; output equals the canonical shell |
| small-world | M0.6/M0.7 state and owner-revision boundary landed on `main` ([commit](https://github.com/bdf1992/small-world/commit/fc11a8e14b29d6c25c0d74d3120890f76afa63ed)) | All nine package-declared Node test commands passed |
| familiar | Entry links, Work/Current distinctions and missing Pydantic test dependency landed on `main` ([commit](https://github.com/bdf1992/familiar/commit/d52265f02e85b47802226bfd81fc5a3615ab1589)) | 463 unittest tests passed |
| nostalgia | Bootstrap state and validation boundary moved to the top on `main` ([commit](https://github.com/bdf1992/nostalgia/commit/a5d5801b45134c28375055e2641784a87d48adc7)) | Catalog JSON parsed; PowerShell was unavailable, so no helper execution is claimed |
| Canvas | Purpose, 0.1 prototype state and first-example links landed on `main` ([commit](https://github.com/bdf1992/Canvas/commit/9c90a870db37ff334d752d1427a3636dc95d70ba)) | 30 unittest tests passed |
| schematically | README is on [`docs/public-portfolio`](https://github.com/bdf1992/schematically/tree/docs/public-portfolio), based on the merged Point/Path/Plane repair | Six static QA suites passed; the browser gate could not start because Chromium installation failed. Remains unlanded |
| Soveraeign | README, clarity receipt and generated documentation are on [`docs/public-portfolio-current`](https://github.com/bdf1992/Soveraeign/tree/docs/public-portfolio-current) | Verify and lint passed; independent prose/source review passed. Remains unlanded under repository landing rules |

The GitHub Contents API returned the expected reviewed README blob for each landed update. No repositories were deleted, archived, renamed, or made private. Existing implementation PRs and historical evidence were preserved. No new PRs were opened, following the prior handoff's restriction.

Remaining publication work: create public `bdf1992/bdf1992`, install the generated `profile-README.md` as its root `README.md`, apply the reviewed About-field plan with an owner-authenticated `gh`, and set profile pins. Repository creation, About-field administration, and pinning were not exposed by this connection. The profile source and this queue are retained on `system-cartographer`'s `docs/public-portfolio` branch.

Soveraeign's candidate was reconstructed through the GitHub Git Data API because local Git had no push credentials. Its remote tree exactly matches the reviewed local tree; the remote commit is a distinct candidate and must retain its own verification and witness identity before landing. The earlier local frozen candidate remains preserved.

One separate consistency finding remains for Soveraeign's owning documents: the earlier README review found a `NONE_ACTIVE` narrative in `CANON.md` against the live Phase 1.5 records. Check current `main` before changing that canonical document; this editorial pass did not settle product meaning.

## Earlier lineage work

The working source is `system-cartographer/lineage/lineage.yaml`. Keep this as one record while the profile repository is unavailable. The public source inventory covers 29 repositories as of 2026-09-05. Source verification is complete for this snapshot; repository runtime suites were not rerun in this pass.

| Work | Owning repository | Acceptance evidence | State |
| --- | --- | --- | --- |
| Publish the profile | system-cartographer → bdf1992/bdf1992 | Create the account-named repository; choose the canonical source location once; clone plus `python lineage/render.py --check` passes in the chosen home; its CI is green | Repository creation is unavailable through this connection; prior session recorded a 403 and this pass found no profile repository |
| Refresh distributed README sections | Each editable repository | Apply this generator against the current branch; review against repository instructions; record a fresh clarity receipt; generated relation states match the central source | Pending; existing sections can still carry the older claims |
| Reconcile About fields | Each public editable repository | Review the generated plan, apply with an owner-authenticated `gh`, run again with no changes | Prepared; no description/topic writes made in this pass |
| Settle repository lineage | system-cartographer | A source identifies repository identities and the actual relation, or the claim remains explicitly qualified | Five qualified claims retained; the unsupported unit-name supersession is excluded from diagrams |
| Continue runtime hygiene | familiar, DDD-CCC, ontum, onton | Check the already-pushed work against each current default branch and its own test command before making another fix | Prior session work exists; avoid duplicating it; onton remains GitHub-archived |

The earlier `HANDOFF.md` records owner decisions and work in eighteen repositories. It is preserved as history. Its unqualified evidence claims and validator instructions are superseded by the gate in this change. Its restrictions on creating PRs, moving the canonical skills, and changing archival state remain as recorded; this pass does not decide those transitions.

## Next experiment: one model across human and agent surfaces

The generated `lineage.sov` exercises the current Schematically document contract using generic Components and Paths. Components preserve repository addresses, and relation labels preserve evidence state. The editor's own data core accepts the document. It is a projection: editing geometry or drawing a wire does not admit a relationship into `lineage.yaml`.

The next useful experiment belongs at the existing adapter boundaries:

1. Select a repository or relation in Schematically and resolve its exact source from the lineage record.
2. Produce an IDE state packet containing that selection and its source revision, using the IDE's existing packet contract.
3. Propose one change and reject it if the source revision changed or its evidence does not support the proposed relation state.
4. Return an inspectable receipt through the existing Soveraeign operation and record boundary when that binding exists.

Acceptance requires the same selected identity and source revision to survive the path, an invalid change to be refused, and a valid proposal to remain a proposal until its owning boundary admits it. No new domain registry or authority service is needed. This is a proposed integration experiment, not a claim that these bindings already run.
