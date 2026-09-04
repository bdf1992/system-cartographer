# Handoff: land what a sandboxed session could not

Read this whole file before acting. The expensive discovery is done. Your job is
the six steps in section 5, not to rebuild any of it.

The owner is **Brandon Freeman** (`bdf1992`, bdf1992.fb@gmail.com). He answers
briefly. Lead with the result, keep the report short, and settle anything you
could settle yourself.

## 1. What this is

Twenty public repositories with no navigable relation between them. The work
records those relations with the evidence for each, and generates everything a
reader sees from that record rather than typing it.

`lineage/lineage.yaml` is the record. Four scripts project it: into each
repository's README, into a GitHub profile page, into the `gh` commands that set
descriptions and topics, and into a validator that fails on a claim without
evidence.

## 2. Ground truth, verified by running it on 2026-09-04

    python lineage/validate.py                PASS, 20 nodes, 7 edges, 12 unconnected
    python lineage/render_profile.py --selfcheck        PASS
    python lineage/render_readme_section.py --selfcheck PASS
    python lineage/render_repo_metadata.py --check      18 reconcilable, 2 archived

In Soveraeign, `python scripts/verify.py` exits 0 across 50 checks and
`python scripts/lint.py` exits 0.

Do not carry a number from this file into anything a reader sees. Run the
command.

## 3. Rules

Evidence. A number you did not observe does not go in. An edge you cannot point
at in a repository is not recorded.

Do not overclaim on his behalf. The failure across this account is prose that
outruns the artifact.

Do not flatten his vocabulary. `custody`, `witness`, `residual`, `grant`,
`Cast`, `Spell`, `vacuum`, `frustration`, `arc`, `datum` carry exact meanings.

Prose style. `Soveraeign/.claude/skills/unslop/SKILL.md` is the default output
modifier and was extended this session with shape and formatting sections and a
rule about what to keep. Persisted prose also needs a `clarity` review and a
receipt. Single copy, add a ref; do not vendor either skill.

Never rewrite git history.

Branch. Everything is on `claude/access-requirements-zbl1s7` in every repository
listed in section 4. Push with `git push -u origin <branch>`, retrying network
failures with backoff. No pull request unless he asks.

Commits. Author as `Brandon Freeman <bdf1992.fb@gmail.com>`. Use the trailers the
harness gives you. No model identifier in a commit, PR, or code comment.

## 4. What is landed

`claude/access-requirements-zbl1s7`, pushed, in eighteen repositories.

Each of the eighteen carries a generated "Where this sits" section in its README,
bounded by markers, holding its claim, the command that checks it and what that
returned, and every relation touching it with the evidence. A repository no edge
touches says so.

`system-cartographer/lineage/` holds the record and the four scripts. Also
`profile-README.md`, the rendered profile page, and `repo-metadata.sh`, generated.

`Soveraeign` additionally has: `LICENSE` classified in
`contracts/publication-surface.json`, which was failing the publication test; the
documentation and surface projections rebuilt; the `unslop` skill extended; and
clarity receipts re-recorded for every README that changed.

Every clarity receipt in all eighteen is current.

## 5. What is open, in order

1. **Create the profile repository.** `bdf1992/bdf1992`, public, README.md at
   root. That is the whole mechanical requirement; GitHub shows a confirmation
   banner when the name matches the account. This session got
   `403 Resource not accessible by integration` on `POST /user/repos`, so it is
   the one step that has to be done by hand or by a session whose GitHub App
   grants repository creation. Then push `lineage/profile-README.md` as its
   `README.md`.

2. **Run `bash lineage/repo-metadata.sh`.** Needs `gh` authenticated as the
   owner. It reads what GitHub currently holds for each repository, skips what
   already matches, and prints the old value beside the new one for the rest.
   Expect around 36 edits the first time and a clean no-op on a second run.
   Fifteen of twenty public repositories have no description and none has a
   single topic, so this is the largest visible change available.

3. **Pin six repositories** to match the six the profile leads with. They are the
   ones marked `featured: true` in `lineage.yaml`, with the reason beside each.
   No API covers pinning; it is done in the profile UI.

4. **Re-point the record link.** `LINEAGE_URL` in
   `lineage/render_readme_section.py` points at the working branch, because that
   is the only place `lineage.yaml` resolves today. After the branch merges,
   change it to the default branch and re-run both renderers, then re-record the
   clarity receipts for every README that changes.

5. **`onton` and `Agentic` are archived on GitHub** and reject writes, so neither
   carries its README section and `onton`'s stale-ticket fix cannot land. Both
   are correctly described in the record. Unarchiving is the owner's call.

6. **A name discrepancy, unresolved.** `DDD-CCC/LICENSE` and its `pyproject.toml`
   both say **Brandon Fritz**, consistently. He gave his name as **Brandon
   Freeman**. Flagged and left untouched, because it could be deliberate. Ask
   before normalizing it.

Also open and his to answer: whether `Worldbuilder` is the right first word on
the profile, whether the paragraph about his work belongs, and whether `nine
years` stays now that it is the only number on the page.

## 6. What a profile repository normally contains

Almost nothing. Public, and `README.md` at the root, is the entire requirement.
Some add a GitHub Actions workflow that regenerates the README on a schedule, and
an `assets/` folder for images.

The variance is all in the README, and the genre convention is emoji-prefixed
bullets, rows of technology badges, and third-party statistics cards. The same
guides that describe those conventions also warn that rows of vanity badges read
as generated filler, and that one working project with real numbers beats any
amount of self-description.

This page deliberately has none of them. It is prose, links, and one claim that
the work is checked with a pointer to the checking. If he later wants the
conventional furniture, it goes in `lineage/profile-voice.md`, not in code.

## 7. Where things live

| Need | Open |
| --- | --- |
| The relations and their evidence | `lineage/lineage.yaml` |
| Whether the record is well-formed | `python lineage/validate.py` |
| The profile page | `python lineage/render_profile.py` |
| Its prose, editable without touching code | `lineage/profile-voice.md` |
| Descriptions and topics | `bash lineage/repo-metadata.sh` |
| A repository's README section | `python lineage/render_readme_section.py --apply <path> --node <name>` |
| Prose style | `Soveraeign/.claude/skills/unslop/SKILL.md` |
| Prose audit and receipts | `Soveraeign/.claude/skills/clarity/SKILL.md` |

Every renderer has `--selfcheck` or `--check`. Run it before and after you touch
anything; each one is proven to refuse a deliberate corruption.

Report outcomes as they are. Landed, presented, or blocked with the blocker
named are the only three. "Opened a pull request" is none of them.
