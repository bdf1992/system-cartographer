# Releases

## 3.9.0 (2026-10-07)

The view named a code cluster after its most connected member and drew it on whichever plane
most of it was on. Both misled. On the workstation root the cluster called `now_utc()` was
30% `hosting_ops.py`, and 19% of it touched `now_utc()`; and 1,639 of 16,653 code nodes sat on
a plane that was not theirs, kernel modules on the tests plane among them.

- **A cluster is named for the files it holds.** The folder of its largest file, then that
  file when it holds half the members, or its two largest files, then how many more there are:
  `wskernel/ops: hosting_ops.py, hosting_advance.py +11 files`. A file from another folder is
  said with its folder. Where the files named would hold under a quarter of the members the
  name is the count and the largest file: `tests: 126 files, largest test_registry.py`. A
  long folder keeps its last three parts, and a name too long loses the end of its file
  names, never the count.
- **Two clusters of one name on a plane are told apart** by their most connected member:
  `tests: test_booth.py (FakeProcesses)`. On that root 296 of 765 code clusters carry one.
- **A community is drawn once on each plane it has members on**, and each cluster carries its
  `community` so the parts can be tied together. A part with fewer than five members joins a
  cluster on its own plane when it has at least as many links to it as inside itself: the one
  it is linked to most, and among equals one holding a file of its own. A small part tied
  more to itself stands as it is; one with no link at all goes to its plane's `other code`.
  On that root no code node is on a plane that is not its own. There are 798 clusters where
  there were 740; 61 code clusters have fewer than five members.
- **A claim is shown once**, on the cluster its community's most connected member is in,
  wherever that member was placed.
- `tests/test_view.py` (new): 19 cases; each of 26 rules broken in a copy turns one red.

The grouping itself is graphify's and is unchanged. What moved is where each part of a group
is drawn and what it is called. The viewer does not yet use `community` to light the parts of
one group together.

## 3.8.0 (2026-10-07)

Round four of the trials, and a fixed set to score against. A reader who believes every line
was wrong on five of ten new jobs; a reader on a weaker model, shown users on three separate
lines, read the first and stopped. The jobs from every round where a reader was led wrong are
now one set of twenty, each with the fact a reviewer found by hand. The hook as of 3.6.0 holds
that fact on 12 of the 20; this release on 16.

- **One list of users and one of tests.** The links the parse read, the files that write the
  name, and the files that write it qualified by its module are merged: `used or named in ...`
  and `tests that use or name it ...`. Code comes before documents that mention it.
- **The index records qualified names and module paths.** `written_in` also returns
  `qualified` (files that write `module.name` for the module that defines it, which tells two
  things of one common name apart), `loaded` (files that write `folder.module`, as in
  `-m pkg.module` or a patched dotted string) and `stemmed` (files that write a file's bare
  name where no other file shares it, as in a path string).
- **A method called on an object in its own file is said,** apart from uses on `self`.
- **The no-test line says what it cannot see:** a test that runs the code through a command, a
  subprocess or a browser.

Four of the twenty are not answered by reading text. Three ask which tests reach a function
through a command or a browser, which only recorded test coverage can say; one is a command
whose file shares its bare name with another.

## 3.7.0 (2026-10-07)

On a records-heavy root the view drew every record as one disc: 3,718 files under one label,
15% of them linked to anything. The owner asked what on the map needed more classification.

- **A record carries its type.** `graph_export.py` reads every file a records concern holds,
  whichever concern it is filed under, and takes the type from `record_type`, `type` or `kind`.
  One that names none, or cannot be read as a JSON object, is typed by the folder it sits in;
  `record_type_basis` says which. A JSON Schema's `"type": "object"` is not a record type. On
  that root: 3,802 records, 3,693 saying their own type, 109 typed by folder, 33 of those
  because the file was gone since the scan, not JSON, a list or over 1 MB.
- **Records are linked to the records they name.** A string, or an object's key, that is
  exactly the `id` another record declares is a `refers_to` link carrying its field, EXTRACTED.
  A match on a file name alone, or on an id that is a plain lower-case word, is INFERRED: a
  word can do either by chance. A declared id inside a longer string is a `mentions` link,
  INFERRED. Where two records share a name, a reference is followed only when one of them has
  the type that field usually points at, and that link is INFERRED. On that root: 10,290
  `refers_to` links (7,299 EXTRACTED, 2,991 INFERRED), 2,891 `mentions`, and 3,725 of 3,802
  records with at least one.
- **The view draws one cluster per record type on each plane.** A type with fewer than five
  records there is shown with its folder, and a folder's worth still under five as `other`.
  The disc became 20 clusters: 19 named and `other`.
- `GRAPH_REPORT.md` has a Records section: the counts above, the types, and which type names
  which by what field.
- `tests/test_records.py` (new, the repository's first tests): 22 cases on a made-up root; each of 17 rules broken in a copy turns one red. Run
  with `python -m unittest discover -s tests`.

What this does not do. Records are read from the root as it is when the export runs, not from
the scan, so the counts move if the root has changed. Of the 2,991 INFERRED links on that root,
2,875 are a repository's name matching `control/policy/<name>.json`, which is a record about
the repository and not the repository; 48 are one shared name settled by its field; the other
68 are words that are also file names or ids, such as `task`, `done` or `kernel`. An id written as part of a path is not followed.

## 3.6.0 (2026-10-07)

Round three of the trials. An agent that believes every line and never checks was wrong on
three of eight jobs, down from six of seven, and all three had one cause: the parse does not
link a function reached as `module.name()` or passed by name, so its real users were missing.
Cautious wording does not repair that, and the same agent reported that the caution, printed on
nearly every card, teaches a reader to skip it.

- **`graph_query.py index` records where each defined name is written.** `written_in` reads
  the scanned files once and keeps, for every function and class name of four letters or more,
  the files that write it. It is a fact about text beside the parsed links. The index also
  records the date of the graph it was built from.
- **The hook reports those files.** `its name is also written in ...` names the files the parse
  did not link, and `tests that write its name` the test files. A name with several
  definitions written in more than 40 files is said to be too common to search by.
- **An absence is now a checked fact where it can be.** `no other file uses it or writes its
  name` and `no test names it` are printed only when the text was searched; elsewhere the hook
  still says what the map cannot see.
- **Wording from a reader given no explanation:** `its file is for:` in place of `its file:`;
  the map's date in the heading; the undefined `claims on its cluster` line is gone; guessed
  links are not mentioned when the text search covers them.

A third agent, set to make the hook crash or lie, found no input that raised or hung, and four
defects.

- **A copy of a file reads its own source.** In a worktree the signature, docstring and line
  number came from the mapped checkout, so a function at line 3261 was shown at 2167. They are
  now read from the copy, and the card says the users are the mapped checkout's.
- **Uses in the thing's own file are counted from the syntax tree,** for Python: a bare name
  for a function, `self.name` or `Class.name` for a method. Counting the word gave "named 46
  more times" to a function its file never calls. Other languages say "written".
- **A thing the map holds that is no longer in the file says so.**
- **Cards left out for room are counted,** and Python advice stays on Python files.

## 3.5.1 (2026-10-07)

An agent was asked to believe every line of the search hook and never check, on six small jobs
(safe to delete, which tests to run, safe to rename, dead code), and a reviewer then checked
each conclusion. Six of seven conclusions drawn from a line that said nothing, or said no, were
wrong. The hook was right about what it found and misleading about what it did not.

- **Uses inside the thing's own file are counted,** from the file as it is now. A function
  called only by its neighbours showed no users and read as safe to delete.
- **A function no test names falls back to the tests of its file.** "No test refers to it
  directly" read as "run no tests".
- **An absence is only ever "not seen".** Where the map links no other file, the hook says so
  and names what the map cannot see (loads by name: command tables, importlib, test discovery,
  config), and that it is not evidence of non-use.
- **A note may be keyed by a pattern** (`wskernel/commands/*`), so a folder's component and
  purpose reach every file in it.
- **The gap line no longer points at a file outside the tree.**

A second agent, set to break name matching and wording, reported ten more defects.

- **A user the map only guessed from a name is never named.** A method called `json` was shown
  as used by four files that import the `json` module. Guessed links are now a count, marked
  unchecked.
- **Every definition of a searched name in the returned files is shown,** with its class for a
  method; two methods of one name in one file were one card.
- **A path only matches a mapped file it is a copy of.** A file in another project that ended
  with the same two path parts got the mapped file's facts; the two files must now begin alike.
- **Patterns give up their name:** `^def guard`, `guard\s*\(`, `write_record\(.*overwrite`.
  A dotted name is only answered in a returned file, and a word with many definitions is not
  listed.
- **A docstring is not cut at "e.g.",** a first sentence too short to say anything is followed
  by the rest, and a clipped line ends in an ellipsis.
- **Of many returned files, the most used are shown,** tests last.

## 3.5.0 (2026-10-07)

Four agents used the search hook on real work (tracing a path, planning a change, orienting as
a newcomer, trying to break it) and reported what its lines did for them. All four ignored the
transitive totals, and one found that a searched name could be answered with another file's
function. `hooks/enrich_search.py` now says what they asked for.

- **A name means the definition in a file the search returned.** A name defined once is that
  definition. A name defined in several files, none of them returned, is reported as several
  with the files named; it is never guessed. Before, `main` or `run` returned whichever
  definition the map found first.
- **The code speaks for itself.** For Python, the first sentence of the docstring and a
  function's signature are read from the file as it is now, so they cannot be stale.
- **Users are named, not counted.** The files that refer to a thing, busiest first, and the
  test files that refer to it directly, each with the number of files. The transitive totals
  are left to `graph_query.py impact`.
- **One card per file, whole cards only.** A function shown stands for its file; a card that
  will not fit is left out and no line is cut.
- **Paths match whatever their case or slashes,** and a copy of the tree elsewhere (a worktree)
  matches the file it is a copy of. `a|b` patterns are read as two names.
- **A file the map does not parse says so,** in place of "no dependents". A file with neither a
  docstring nor a note is told where to add one.

## 3.4.0 (2026-10-06)

The search hook led with raw counts. The owner asked that it lead with what is known about a
file, with the counts as metadata under that.

- **`hooks/enrich_search.py` reads a notes file.** `$CARTOGRAPHER_NOTES`, else `notes.json`
  beside the index: `{"notes": {"<path>": {"about": "...", "meta": {...}, "see": [...]}}}`.
  A file's description comes first, then its metadata, then where to read more, then the counts.
- **A gap is said.** Where a notes file exists and holds nothing for a file, the hook says
  nothing is written down about it yet. With no notes file the output is as it was.

## 3.3.1 (2026-10-06)

`measure` printed numbers that read as a verdict and were wrong in the alarming direction. The
owner saw 35% of definitions reached by a test and 2,007 referred to by nothing, and took them
as a judgement on the codebase. Checked against the source by another route, neither held.

- **Declaration, vendored and generated files are left out.** 806 of the 7,281 definitions
  counted before were not the target's own code, most of them one vendored type file.
- **Test reach is a range.** Lower: a test reaches the definition through calls. Upper: a test
  can reach its file. Each is printed with the direction it errs in, per top folder. On the run
  that printed 35%: 39.6% to 85.8% overall, 40.8% to 92.2% in the kernel.
- **"No link found" replaces "referred to by nothing", and is printed with its own check.** A
  sample of those definitions is looked up by name in the source. On that run 42 of 60 were
  named in another file: the parse had missed the link.
- Search and hook lines say `no dependents found in the map` and `no test file found among
  them`. Neither says a thing is unused or untested.
- The hook's time was also overstated in 3.3.0 as "about 110 ms". Measured on two more runs of
  the same six payloads it ranged from 107 to 563 ms a call on a machine doing other work, and
  once reached 1,620 ms. 110 ms is the best case, not the usual one.
- The rule this release adds to `SKILL.md`: a measure is not shown as a verdict on a codebase,
  and is not shown at all before it has been checked by a second route.

## 3.3.0 (2026-10-06)

The graph answers questions, and can sit beside an agent's own search.

- **`scripts/graph_query.py`** (new): `index` once, then `search`, `impact`, `reach`, `path` and
  `measure`. A dependency is a link whose source needs its target; containment is never followed
  as one. Impact is given at one, two and three steps, with the files it spans and the test
  files among them.
- **`hooks/enrich_search.py`** (new): a Claude Code `PostToolUse` hook for `Grep`, `Glob` and
  `Read` that adds up to three lines of context about the name searched for and the first files
  returned. It adds a line only for an exact name or a scanned file, and exits 0 with no output
  when it has no index, cannot read its input, or has nothing sure to say.
- On a 21,328-node graph: index built in under a second, 6.9 MB. Each query took 110 to 160 ms
  as a fresh process (`path` 550 ms). `search write_record` put `write_record()` in
  `wskernel/store.py` first: 354 direct users, 1,667 in all across 405 files, 209 test files.
- The hook on six replayed payloads: about 110 ms each once the index is in the file cache, 517
  ms on the first call after a rebuild; 249 to 514 characters added; nothing added and exit 0
  for an unknown name, a broken payload and a missing index.
- `measure` on that graph: 7,281 definitions outside tests; 4,803 have a name nothing else
  shares; 2,565 are reached by a test through calls; 2,007 are referred to by nothing; median
  direct users 1, 90th centile 5; 18.9% of dependencies are inferred.
- Not done: the hook has only been run on payloads written by hand to the documented shape, not
  inside a live session, and is installed nowhere. Whether the added lines make an agent's work
  better is not measured: that needs the same questions asked with and without it. Impact is an
  upper bound, since it follows file-level imports.

## 3.2.0 (2026-10-06)

Our own node-level view.

- **`scripts/graph_view.py`** and **`references/viewer/index.html`** (new): a self-contained view
  written beside a run. Positions are computed once by plane and cluster; a WebGL renderer draws
  nodes and links; a cluster opens into its members when there is room on screen and it is under
  the pointer or selected; a selection shows its twelve strongest connections as bands; the card
  lists what uses a node and what it uses. Nothing is fetched from the network.
- `--structure` puts code on the layers a target declares for it; without it, on its top folder.
- Measured on a 21,328-node, 56,221-link graph at 2560x1271 with software rendering: first full
  draw 0.2 to 0.5 s; 1.9 ms a frame mean and 2.9 ms worst over 40 moving frames; 29 ms for the
  frame that shows all 718 clusters. On a real GPU the same whole-view frame took 23.7 ms.
- Built in four looked-at passes. Rejected on the way: node-level links from a selected cluster
  to everything it touches (a flood), every connection of a hub drawn at once (a starburst),
  neighbouring discs at full strength when zoomed in (slabs), and twelve cycling colours that
  meant nothing (colour is now the plane).
- Not done: labels crowd the centre of an open cluster, where its busiest members sit. Zoomed in
  with the pointer elsewhere, the screen is quiet discs until one is pointed at. No typed
  symbols, no editing, and planes are flat: each carries a depth index that nothing uses yet.
  The moving-frame figures come from software rendering in a test browser, not the owner's GPU.

## 3.1.1 (2026-10-06)

graphify's viewer is taken back out. 3.1.0 wrote its `graph.html` beside our documents; the owner
wants the capacity in Schematically, not graphify's viewer, which also re-runs its layout on
every open and offers little past looking. `code_graph.py` no longer writes it. The measurement
in 3.1.0 stands and is the list of what Schematically's own node-level view has to do.

## 3.1.0 (2026-10-06)

Measured against graphify's visual, and its viewer shipped beside ours.

- **The measurement.** One slice of parsed code, `wskernel/guard` of the 711-file root: 52
  definitions, 158 links, 8 Leiden communities, drawn both ways from the same data.

  | Capability | graphify `graph.html` | Schematically document |
  |---|---|---|
  | Whole slice in one 1600x1000 window | yes | no: 3994x3795, 9.5 times the window's area |
  | Communities told apart by colour | 8 of 8 | 3 of 8 |
  | A node's importance visible | size by links | every card one size |
  | One link followed by eye | mostly | no: 158 wires merge into white bundles |
  | Labels | hubs labelled, the rest on hover | every card labelled, long names cut |
  | Link meaning | dashed when inferred, coloured by community | four line styles by relation, one colour |
  | Details and neighbours on click | yes | not measured |
  | Search | yes | not measured |
  | Filter by community | checkbox each | no |
  | Opens as one file | yes, needs a connection for `vis-network` | needs a served editor and an address |
  | Typed symbols, regions, editing, claims on a unit | no | yes |

  Three of eight colours was the exporter's error, not Schematically's: slots 1 to 5 are greys
  and the categorical colours are slots 6 to 11, which also means six colours at most.
- **`code_graph.py` writes `graph.html`**, graphify's viewer over the parsed code, aggregated to
  one node per community above 5,000 nodes, with communities named from their folder and most
  connected definition. On the 711-file root: 707 community nodes and 3,711 links between them.
- `SKILL.md` says which visual to open for which question.
- Not done: the Schematically documents are unchanged. Closing the gap there means a node-link
  view in Schematically itself (fit to window, size by links, colour per community, straight
  wires), which is that product's work and is not started; and the exporter using slots 6 to 11,
  dropping containment wires that a group already shows, and reading a target's declared
  structure, which is this repository's next change.

## 3.0.0 (2026-10-06)

The map is made from parsed code, and agents analyse it. Until this release the graph was
graphify's format over file-level pattern matches; the owner asked for graphify's depth.

- **`scripts/code_graph.py`** (new): graphify's tree-sitter extraction, graph build and Leiden
  clustering over the scanned code files, with nothing written into the target. On a 4,959-file
  root, 711 code files became 21,315 nodes and 64,474 links in 28 seconds: 21,632 calls, 11,825
  imports, 1,289 inheritances. `ruff` findings land on the definition they fall in (721 findings
  there). Manifests are read for declared dependencies.
- **`graph_export.py --code-dir`**: merges the definitions under the files that hold them and
  replaces the scan's file-to-file import guesses (2,702 there). The merged graph had 21,328
  nodes and 56,221 links. The Leiden grouping scored modularity 0.61 against 178 shuffles; the
  concern grouping 0.40; the asset-kind grouping 0.04.
- **Actors and triggers**: agents, skills, hook bindings and workflows are nodes, joined to the
  scanned files their commands and instructions name. Every node carries a layer.
- **Three overviews**: `system-overview.sov`, `system-code.sov` (the largest code communities and
  the strongest links between them), `system-actors.sov`. Above 2,500 nodes `system.sov` is not
  written. A first `system-code.sov` of 40 cards and 90 wires was rendered, read and rejected as
  a tangle; it is 14 cards and 22 wires.
- **`scripts/analysis_packets.py`** and **`references/analysis-brief.md`** (new): the map cut
  into units with one packet each, and the instruction for analyst, lead and validator agents.
  `audit.py` takes `--source agent --unit`, holds a lock so agents can record together, and
  `graph_export.py --audit` puts verdicts on the map.
- Run for real on that root: two analyst agents took one code unit and one hook unit and recorded
  four claims through qualification; the lead settled them; a third agent, given only the
  statement, validated one. Two of the four were defects in the target that nobody had filed,
  one of them confirmed by the validator link by link.
- What the analysts said the packets lack, not yet fixed: a code unit named for its busiest
  definition misleads when the community is really "everything that imports it"; a member's
  importers are not listed by name; a hook packet omits the hook's timeout, its tests and the
  configuration its script reads; a member without a line number is hard to cite.
- Not done: only Python is linted. A package whose import name differs from its distribution
  name appears as both undeclared and unused. The run ledger seeds no task for these passes and
  no gate depends on them. This repository still has no test suite.

## 2.5.0 (2026-10-06)

A map a person can read, from the same 4,952-file run.

- **`system-overview.sov`** (new, written beside `system.sov`): one card per community with
  its node count, one wire per pair of communities labelled with its link count and how many
  are inferred. On that root: 9 cards and 7 wires, where `system.sov` has 5,341 components.
  Rendered with Schematically's `export_svg.py` and read as a picture before release; the
  counts moved from the subtitle into the label because a small card hides its subtitle.
- **Large logs are read from the end.** A concern whose scan config says `"oversize": "tail"`
  has the last `--max-file-bytes` of an oversize file read with its own patterns; `asset-logs`
  sets it. On that root the log data group went from 87 nodes to 97.
- **Outside-the-root pointers are cleaned in the export.** A bare drive root is dropped and
  JSON-escaped or full-stopped spellings of one path are merged: 50 pointers became 47.
- Not done: the overview does not link each card to a document of its own members, so going
  from a group to its files still means opening `system.sov` or `graph.json`.

## 2.4.1 (2026-10-06)

Four defects from the first real run, on a 4,952-file root that is mostly JSON records.

- **Filing.** 3,448 record files had been filed under `integrations`, because that concern
  matches any `.json` file and the smallest matching concern won. Now a file with no evidence
  goes to an asset concern before a system-description one, and a file other files provably
  import is filed with that link. New `asset-records` kind for structured records kept one per
  file. On that root: 3,714 nodes under `records`, the system description down from about
  5,000 nodes to 1,045, and the asset-kind grouping from z 0.69 to z 5.54 against shuffles.
- **Log data.** `asset-logs` now matches event logs kept as `.jsonl` or `.ndjson` under an
  `events/` folder, with `events` in the name, or named by date. The root's 29 dated event
  logs moved from `data` to `log data`.
- **Report.** A boundary pointer lists five referencing files and a count of the rest; one
  pointer had listed about 60.
- **Audit seed.** No claim is opened for a concern with nothing past a pattern match; those
  concerns are named in one line instead. On that root: 8 claims where there had been 15.
- Rerun after the fixes: this repository (81 nodes) and a 958-file Python repository
  (1,350 nodes) still export and validate; the 38-command audit walk still passes.
- Not done: a log over `--max-file-bytes` is filed but not read, so the large event logs
  contributed no severity links. Junk boundary pointers such as `C:\\` and JSON-escaped
  duplicates of one path come from the scanner's path patterns and are unchanged.

## 2.4.0 (2026-10-06)

A run is an audit: every claim walks eleven recorded stages.

- **`scripts/audit.py`** (new): one record per claim in `audit.json`, moved through intake,
  findings, evidence, conflicts, organization, refutation, judgement, verdict, qualification,
  settle and validation; `AUDIT.md` is regenerated from it. A stage is refused while the one
  before it is empty; a judgement needs a refutation attempt; `confirmed` needs `EXTRACTED`
  evidence and no defeating refutation. Recording into an earlier stage moves later entries to
  the claim's history and raises its round.
- **Validation is the process run again.** `validate` opens a second record of the same claim
  for a different actor. Matching verdicts validate the first; a different verdict is recorded
  on it as a conflict and reopens it.
- `seed` opens one claim per concern from a scan directory, with its findings and evidence
  attached. The verdict words are the existing delta words; nothing new is named.
- Walked by script: 38 commands on one claim and its validation, 12 expected refusals all
  fired, the disagreeing validation reopened the claim at round 3; `seed` on a 949-file scan
  opened 15 claims.
- Not done: the run ledger seeds no audit task and `state.py` gates nothing on the audit, so a
  bundle can still be shared with claims unsettled. No claim has been walked on a real target
  with its owner yet.

## 2.3.0 (2026-10-06)

The asset map covers a whole file system and its log data.

- **`asset-files`** (new, provisional): matches every file. A file belongs to the most specific
  concern that holds it, so the `files` kind is what no other concern accounts for.
- **`asset-logs`** (new, provisional): log files, linked to the severities and the exception
  names they contain, one link per file and name.
- `SKILL.md` and `README.md` describe a file system as the target, the bounds to pass on a
  large root, and what the log links do and do not say. The skill's trigger description names
  asset mapping and the graph export.
- Run on a folder that is not a repository, holding three small logs: 40 nodes, 27 links, the
  logs grouped as `log data` with `ERROR`, `WARNING` and `PermissionError` each shared by all
  three; document accepted by Schematically's `validate_sov.mjs`. There the asset-kind grouping
  scored modularity 0.444 (z 8.0 against shuffles), against 0.002 on the code-heavy repository
  in 2.2.0.
- Not done: no run yet on a drive of more than a few dozen files, so the bounds in `SKILL.md`
  are the scan's existing flags, not measured settings.

## 2.2.0 (2026-10-06)

A scan ends in a graph and a schematic, and reaches past the agent system to company assets.

- **`scripts/graph_export.py`** (new): a scan directory becomes `graph.json` in graphify's
  node-link format, `GRAPH_REPORT.md`, and `system.sov`, a Schematically document laid out by a
  Schematically checkout's `scripts/layout_sov.mjs` when one is passed. A link is `EXTRACTED`
  when a structural or behavioral finding backs it and `INFERRED` at 0.65 otherwise.
- **Grouping is measured.** `graph.partitions` holds each grouping's modularity and its place
  among 1000 seeded shuffles (concern, asset kind, and Louvain when `networkx` is importable).
  `graph.hyperedges` holds every set of three or more files tied by one shared target.
- **`references/assets.registry.json`** (new, provisional): six asset concerns (documents, data,
  services, ownership, access, brand and media) with scan configs under `references/assets/`.
  The concern schema gains an optional `asset_kind`; a concern without one belongs to the
  system description.
- Run on this repository with the overlay: 75 nodes, 31 links, document accepted by
  Schematically's `validate_sov.mjs`. Run on a 949-file Python repository: 1341 nodes, 1860
  links, accepted. There the concern grouping scored modularity 0.094 (z 11.0 against shuffles)
  and the asset-kind grouping 0.002 (z 0.65), because the system description held 1132 of the
  nodes: on a code-heavy root, asset kind does not explain which files are linked.
- Not done: the asset concerns have no structural validators, the export is not part of the
  bundle or its gates, and the run ledger does not seed a task for it.

## 2.1.1 (2026-07-18)

Public-release cleanup pass, no behavior contract changes, patch bump. Audited the whole skill
for anything specific to the private repo it was developed and dogfooded against: one
inconsistent example actor name in `state.py`'s usage docstring, one ironic self-reference in
`onboarding_card.py`'s own "this is generic" docstring, one motivating-bug reference in
`build_export_manifest.py`, and two examples in `boundary-protocol.md` (a path example, a
dogfooding number tied to a named repo root). All genericized without losing the substance of
what each was documenting. `RELEASES.md`'s dogfooding history (five prior entries, each a real
bug found by actually running the tool at scale) is kept — the numbers and fixes are real
evidence this tool works, not something to launder away — but every mention of the specific
private repo it was tested against is now a generic description ("a large multi-agent repo," "a
real subproject inside it") instead of a name.

## 2.1.0 (2026-07-18)

The standing product template. 2.0.0 fixed *which* evidence is real; this release fixes what a
run actually hands back — a card, not a stats dashboard. Built after using the skill for real on
a live target (this repo's own `.claude/` — 14 subagents, 7 commands, the hook wiring) and
finding that a hand-authored HTML report, however accurate, isn't the deliverable: SKILL.md's own
"what done means" always promised *capability + requirement cards a dev with no priors could
rebuild from*, and nothing before this release actually produced that shape without an agent
hand-writing prose per target.

- **`structural_validators.py`**: every validator that already promotes a candidate to
  structural/behavioral now also returns `extracted` — the real structured data the check pulled
  out (an agent's `name`/`description`/`tools` from its own frontmatter; a skill's `name`/
  `description`; a workflow's real trigger shape). `validate_workflow` gained a genuinely new
  check: any JSON file shaped like a Claude Code `settings.json` (`{"hooks": {<event>: [...]}}`,
  the convention `host-environments.md` already documents) gets its real event/matcher/command
  rows extracted structurally — not just "the word PreToolUse appeared somewhere." Nothing in
  this module changed to know about any specific target; `extracted` is real data pulled from the
  file, never prose this module authored about the file.
- **`cartographer_scan.py`**: no code change needed — `extracted` flows through the existing
  `**f` spread into every finding automatically, additive.
- **`scripts/onboarding_card.py`** (new): renders the actual card SKILL.md has always promised —
  one capability card per real evidenced agent/skill file (name, description, tools, straight
  from `extracted`), a merged hook/trigger table for workflow-type concerns, plain evidence
  tables for every other concern, the real boundary-pointer dependency list, and the real
  exported source for every evidenced file, embedded verbatim. Every string in the module is
  generic English about concerns and evidence stages — verified by pointing it at a completely
  different real target (this repo's own `.claude/`) and getting back 14 correct capability
  cards and a 9-row hook table with zero target-specific code in the generator.
- **`bundle_synopsis.py`**: now always calls `onboarding_card.py` and writes
  `onboarding-card.html` alongside README/handoff/report.html — the product surface, generated
  every run, never an extra step an agent has to remember. `state.py`'s `shared` gate now
  requires it present, the same way it already required README.md/handoff.json.
- **`cartographer_run.py`**: the `validate-replication-bundle` task's completion condition
  updated to name all three required surfaces.

Verified live end to end against `.claude/` (14 agents, 7 commands, settings.json): the full
`init` → `negotiated` → `elicited(skipped)` → scan → plan → export → `exported` → `shared` →
`carded` → `delivered` pipeline ran clean with the new gate requirement in place, and
`onboarding-card.html` rendered 14 real agent cards (each with its actual frontmatter
description) plus the full 9-row hook table extracted structurally from `settings.json` — with
no hand-authored content anywhere in the generator.

Minor bump, matching the precedent set by 1.1.0 (which also added a new hard-required file to
the `shared` gate): additive fields only (`extracted` on findings), one new generated artifact,
no existing fill or contract invalidated.

## 2.0.0 (2026-07-18)

The replication-grade rewrite. The full-repo run against a large multi-agent
repo (1.2.4) proved the scanner could walk 7,666 files and name real evidence — but its bundle still
shipped scan JSON, not the source files that evidence cited, because nothing
in the pipeline distinguished a glob candidate from a validated finding, or
planned what evidence a bundle actually needed before copying started. This
release is that missing layer, built as five new/changed pieces working
together rather than one big patch:

- **`scripts/structural_validators.py`** (new). One real check per concern
  that a candidate has to survive to become `structural` (parses against the
  concern's actual shape) or `behavioral` (demonstrates a real operation) —
  frontmatter + tool grant for agent, name+description+real body for skill,
  `meta.phases` + `phase()`/`pipeline()` calls or GH Actions `on:`+`jobs:`
  for workflow, a real client-call pattern (PyGithub/Slack SDK/jira-python/
  mcp tool call, not a bare word) for integrations, a manifest filename or
  install invocation for required-tools-repos, invocation+assertion for
  exemplars, a real failure marker (not just TODO) for issues, a real
  reachable channel URL for shareability, a path-reference proxy for
  memories. `code-scripts` gets a real fix, not a heuristic: Python imports
  are read via `ast.parse`, so a docstring line that merely *starts with*
  "from the..." can never become a bogus import the way the old regex read
  it — proven with the exact fixture this epic's acceptance test describes
  (a "derived from the original design" docstring; the old regex extracts
  `'the'` as an import, `ast.parse` correctly extracts none). JS/TS gets a
  tightened, comment-stripped, module-shape-anchored regex (no JS parser in
  stdlib) that rejects the same class of comment-borne false hit while still
  accepting a legitimate one-letter destructured import.
- **`scripts/lineage.py`** (new). Hashes every candidate file's raw bytes,
  groups exact byte-identical copies, nominates one canonical member per
  group (shortest path, then lexicographic), and classifies every
  candidate's `source_class` (source / configuration / generated / copy /
  archive / snapshot / cache / vendor / transcript / runtime-state /
  unknown) from path and content shape.
- **`cartographer_scan.py`**: wired additively. Every regex-graph concern's
  `scan_one` now also runs its structural validator and (for code-scripts)
  the import classifier, emitting a typed `findings[]` per concern
  (concern/file/evidence_stage/signal/locator, plus import_target/class for
  code). `evidenced_concern_coverage` is **redefined** — a file counts only
  on a real edge or a structural+ finding, never merely because a
  node-evidence concern's glob matched (the exact bug the epic opens with).
  Cross-cutting couplings are filtered the same way: a bare candidate shared
  across two concerns' globs is no longer a "coupling". Boundary-pointer
  grouping now keys on the canonicalized resolved target, not the literal
  reference string, so differently-cased/spelled references to the same
  real file land in one group (`reference_variants`), not several —
  verified live: the skill's own self-scan went from 5 boundary-pointer
  groups to 3 once two case-variant spellings of the same path folded
  together. `--follow-boundaries` now accepts `--boundary-dispositions` and
  never sub-scans a pointer already disposed excluded/deferred.
  `schema_version` bumped to 1.1 (additive: `findings`, `lineage`, node
  `source_class`/`canonical_rel`); `VALIDATORS_VERSION` folds into the cache
  signature so an old cache can't hide a validator change.
- **`scripts/build_export_manifest.py`** (new). Turns real findings into an
  `export-plan.json` — only structural+ findings ever earn a plan entry,
  copies are folded into their canonical source (stored once, referenced by
  every concern it supports), and the scan's own process trace
  (scan.json/patterns.json/lineage.json/environment.json) is always planned
  under a `process` slot, separate from evidence. `--profile handoff` caps
  per-concern, ranked by finding strength; `--profile replication` plans
  every evidenced source. Included boundary dispositions add their own
  entries.
- **`export_bundle.py`**: hardened. Accepts `--plan` (preferred) alongside
  the legacy `--manifest`. Hashes raw bytes, not decoded-with-errors-ignore
  text. Binary files (by extension or failed UTF-8 decode) are copied
  byte-for-byte, never secret-scanned. A collision on the export name gets a
  numbered suffix instead of a silent overwrite; a name attempting to escape
  the bundle (`../`, an absolute path) is refused per-entry with a reason,
  never written. Identical content across entries is written once and
  referenced by hash. Every write is re-hashed against what's actually on
  disk — and a real bug lived here: opening the destination in Windows
  text-mode without `newline=""` silently turns `\n` into `\r\n`, so every
  single text export failed its own post-write verification on this host,
  100% false-positive, until fixed. Caught by the verification feature
  itself, on its first real run.
- **`state.py`**: new hard gates, not just presence checks.
  `exported` now requires a profile-carrying manifest, an export-plan.json
  in the bundle, re-hashed export integrity, and no shipped
  `scan-cache.json`. `shared` (existing boundary-disposition gate kept)
  gains: an `included` boundary disposition must link to real exported or
  followed evidence, not just the label; and every secret warning needs a
  `secret-disposition` (new subcommand: resolved/accepted/non-secret).
  `carded` (new gate) requires the export plan and a `justify` record (new
  subcommand) for every planned source whose `source_class` needs one.
  `delivered` (new gate) re-verifies export integrity and requires `--note`
  naming a real destination. **A second real bug, more serious, found
  proving these**: `cmd_advance`'s existing skip-ahead mechanism (jump
  straight from `exported` to `carded`) silently bypassed every check
  `shared` would have enforced, because the new gates were keyed to the
  literal `target` argument, not to states skipped over on the way there —
  the same class of hole `elicited`'s existing skip-guard was built to
  close, just not yet extended to the newer gates. Fixed: every named gate
  now fires if its state is skipped over OR is the literal target.
  Reproduced the exact bypass (advance straight to `carded` with zero
  dispositions recorded) before the fix — it succeeded silently; after the
  fix, the same call correctly refuses on `shared`'s unresolved secrets.
- **`bundle_synopsis.py`**: rewritten to report candidate vs. structural vs.
  behavioral vs. observed vs. confirmed counts, never the unqualified
  "with evidence" for a bare glob match, plus lineage/dedup savings and a
  headline number: how many exported files are real source/configuration
  content (not scan output, not a copy) backing how many real findings —
  the actual answer to "how much of this bundle can a receiving team inspect
  without the original repo." New **`report.html`**: a single
  self-contained static dashboard (inline CSS, no external assets, no
  network calls) generated alongside README.md/handoff.json — bar charts for
  evidence-stage breakdown, per-concern coverage, and exported bytes by
  source class, a boundary-pointer table, and the secret-warning list with
  resolved ones struck through. It travels inside the bundle and opens
  directly in a browser on a machine with no path back to this one.

Verified live end to end, self-scan target (this skill's own ~49-file repo,
run three times over the course of building this — numbers below are the
final clean run): `state.py init` → `negotiated` → `elicited` (skipped,
documented, no builder present) → `cartographer_scan.py` (49 files, 47
candidates, **18 structurally-or-better evidenced**, 78 findings — 77
structural + 1 behavioral, 0 rejected, 0 duplicate groups on this target) →
`build_export_manifest.py --profile replication` (12 real sources planned,
plus the process-trace entries) → `export_bundle.py --plan` (12/12 exported,
0 failed post-write verification after the CRLF fix, real source `.py`/`.md`
files landing in `exports/`, not scan output) → `advance exported` (passed:
plan present, integrity verified, no cache shipped) → refused `advance
shared` twice for real reasons (missing README/handoff, then 50 undisposed
secret warnings — the process-trace files' own hashes trip the intentionally
noisy long-string tripwire) → all secret + the 3 boundary-pointer
dispositions recorded for real reasons → `advance shared` succeeded →
`advance carded` → `advance delivered` with a real destination note. Also
verified live: the two regressions above, reproduced broken before their
fix and correct after, on this same pipeline.

Not done in this pass, named rather than implied: the full 7,666-file/467MB
fitness run against that large multi-agent repo this epic's acceptance
section asks for was not re-run — this release is proven on a real but much smaller target, not yet
re-proven at that scale. Several of the epic's sixteen acceptance tests
(directory-move portability, deleted-original-repo validation, an `included`
boundary with no evidence blocking `shared` specifically) have the
mechanism built and gate-checked in code but no dedicated fixture run
against them yet. Both are the natural next dogfooding step, in the same
spirit every prior release here was earned by actually running the tool,
not by reading the code.

Major bump: `evidenced_concern_coverage`'s meaning changed (stricter, by
design), boundary-pointer `id`s changed (canonical-key grouping, not
literal-string grouping — an in-flight bundle's `boundary-dispositions.json`
from before this release won't match), and `state.py` now hard-refuses
transitions earlier releases allowed silently. `cartographer_run.py`'s
`export-source-evidence` task command updated to the plan-based two-step
flow.

## 1.3.0 (2026-07-18)

New `scripts/cartographer_run.py` — a first-touch run ledger, so an agent has a visible
work contract before the first environment probe instead of reconstructing the workflow
from this file's prose. `init` creates `<run>/work.json` (typed tasks: phase, owner,
`blocked_by`, a `completion_evidence` artifact + condition) and regenerates `TODO.md`
from it after every mutation — never hand-edited, the way any generated file isn't. The
seed task graph mirrors this skill's own phase list (negotiate → elicit → scan →
reconcile → cycle → assemble → share); every seed task's completion evidence points at
an artifact a different script in this skill already produces (`environment.json`,
`scan/scan.json`, `manifest.json`, `README.md`), so the ledger wraps existing mechanism
rather than inventing a parallel one. Two gates are real, not descriptive: `start`
refuses a task whose `blocked_by` isn't satisfied, and `complete` refuses to close a
task whose artifact doesn't exist — an agent's say-so is not evidence. A task marked
`skippable` (elicit, informed-rescan) can close via `--skip <reason>` instead, matching
the precedent 1.2.4 itself set (elicit explicitly skipped, no builder present). Discovered
work lands with `add-task --discovered-by <what surfaced it>` instead of being buried in
`patterns.json`.

Verified live end to end against this skill's own repo as target (`init` only stats the
target directory — no content read): status blocked `scan-target` on the real message
"blocked by unfinished task(s): elicit-blind-beliefs" before elicitation closed; `complete
confirm-roots` refused with "required artifact missing — environment.json" before the
probe had actually run, then succeeded once it had; skipping `elicit-blind-beliefs`
correctly unblocked `scan-target`, which then ran the real scanner and closed on its real
`scan/scan.json`; an `add-task --discovered-by boundary-pointer` landed mid-run and
appeared `ready` the moment its one blocker was already done; the regenerated `TODO.md`
correctly reported "Current phase:: Reconcile" with four tasks in `## Done` (one shown
skipped, with its reason) after that sequence. `state.py`'s own save-state ladder is
untouched by this addition — `init` calls its existing `cmd_init` once and nothing more;
the two ladders (fine-grained tasks, coarse save-states) stay independent, and finishing
a phase's tasks is the cue to call `state.py advance`, not a trigger that does it for you.
Minor bump: additive only, no existing script's contract changed.

## 1.2.4 (2026-07-18)

Full-scale run: a subagent actually played the System Cartographer role (Negotiate →
Scan → Join → Assemble → Share, per `SKILL.md`'s own phases, Elicit explicitly skipped
with a documented reason — no builder present for a real commissioning) against the
whole target repo — 7666 files, not the 24-file `.claude/` slice 1.2.3 was proven on.
Reached `shared` for real, including one genuine reopen-and-refix cycle mid-run. Four
more bugs, all found by actually running the tool at this scale and all proven with a
live before/after re-run:

- **`DEFAULT_EXCLUDES` only matched at the scan root**, never nested — `"node_modules/**"`
  needs a target's *own* node_modules directly under the declared root; a repo this
  size has a `node_modules` nested inside one subproject, 168 stray `__pycache__` dirs, and a
  synthetic PC-crawl tree of fake vendor dirs several levels down, all silently walked
  anyway. Prefixed every default with `**/`. Edges dropped 17380 → 7683, and
  `hotspot_files` went from 100% vendored noise to real target files.
- **The boundary scanner only recognized forward-slash paths** — every Windows
  absolute path (`C:\Users\...`) was invisible to it, including one this repo's own
  deeply-nested doc file that explicitly names it as load-bearing ("the
  mother lode"). Added a `win_abs_path` pattern to `boundary.scan.json`; pointers went
  0 → 589 real on a repo where they should obviously have been nonzero.
- **That fix exposed a case-sensitivity bug in `classify_relation`**: a lowercase-drive
  path (`c:\Users\...`, written that way in one real `.workflow.js` file) compared
  unequal to the uppercase-drive scan root, misclassifying an internal file as an
  external "cousin". Fixed with `os.path.normcase`; count dropped 589 → 572, exactly
  the false positives, verified by pointer id.
- **`bundle_synopsis.py` read the wrong JSON shape for git history.** The scan's own
  `session-quality` concern nests commit data under `["analysis"]`; the synopsis script
  only ever checked `["git_analysis"]` (the shape `session_telemetry.py` produces
  separately) — so a bundle built from the scan's own evidence *always* reported "no
  git history found," even with 200 real commits sitting right there. Added a
  shape-normalizing helper; the README now correctly reads "200 commit(s) spanning
  2026-07-13–2026-07-17."

Read the resulting bundle's `README.md` critically, the way a human recipient would:
"Points beyond this map" correctly identifies the user's global `.claude` home as a genuine
load-bearing dependency (the global Claude Code home this very tool runs from) and
correctly bulk-excludes PC-wide filesystem-inventory noise (vendored HuggingFace/Ollama
model blobs, `pagefile.sys`) with specific, defensible reasoning per class, rather than
either drowning in it or silently dropping it. Of 572 real pointers, 10 got individual
reasoning after reading their actual source files, 544 were bulk-dispositioned across
two genuinely coherent classes (a PC-wide crawl domain, a local-projects discovery
audit) with the methodology stated plainly, and 18 stayed honestly `deferred` rather
than guessed — the replication test this tool holds everything else to, applied to its
own output.

## 1.2.3 (2026-07-17)

Premise check: does the tool actually map a real agentic system, not just run without
crashing? Pointed it at a real target's `.claude/` — 15 real Claude Code subagent definitions, a
`settings.json` with real hooks, real commands — the exact evidence set
`host-environments.md`'s own Claude Code row names. First result: **zero edges across
all eleven concerns.** Two compounding bugs, both load-bearing:

- **`agent`'s `tool_grant` pattern never matched real Claude Code frontmatter.** It
  required bracket syntax (`tools: [Read, Write]`); every real subagent file in this
  repo (and, per `host-environments.md`, this tool's own native host) writes a bare
  comma list (`tools: Read, Write, Edit, Bash, Grep, Glob`) instead. The concern found
  all 15 files as candidates and extracted zero tool grants from any of them — "Agent",
  one of the three first-class object types `SKILL.md` opens with, silently couldn't
  do its one job against the most common real-world case. Regex now accepts both forms
  (`\[?([^\]\n]+)\]?`), verified to still handle the bracketed form unchanged.
- **`workflow` and `memories` found zero candidate files at all**, because their
  configs anchor on `**/.claude/...` — written assuming `.claude/` is a *nested*
  ancestor of the scan root (a repo-root scan). Point `--target` at `.claude/` itself
  — a natural, common choice, the row directly above in the same doc — and the anchor
  segment is consumed by being the root, so it can never appear in a relative path
  again. `workflow` gained root-relative fallbacks (`commands/*`, `settings.json`)
  alongside the nested forms; `memories` gained a scoped, justified addition
  (`settings.local.json`, matching its own interrogation question — session-local
  config, different authority than the shared file) rather than a blanket `**`, which
  would fix this one target shape by breaking every other target's specificity.
  `host-environments.md` now names the remaining gap honestly instead of implying it's
  fully solved.

Verified live, against ground truth already visible earlier in this exact session: the
scan's extracted tool grants for `agents/analytical-admin.md`
(`Read, Bash, Grep, Glob, Agent`) match the real agent roster shown at session start,
and the extracted hook names (`SessionStart, UserPromptSubmit, PreToolUse,
PostToolUse`) match hooks that actually fired earlier in this conversation. Built the
full bundle end to end: `agent`/`workflow`/`memories` went from 0/0/0 to 15/8/1
evidenced files and 0 to 18 real edges; `cross-cutting` now correctly flags
`settings.json` as coupling three concerns at once; the README's "Points beyond this
map" section correctly surfaces that the 15 agent-role prompts all point outward to the
real enforcement machinery in `tools/session/`, `tools/sign/`, and
`workspace/descent/` — which is the actual premise this tool exists for.

## 1.2.2 (2026-07-17)

Cut the boundary-pointer false-positive noise two ways — a small regex improvement,
then the actual fix underneath it.

The real fix: `cartographer_scan.py` was emitting every regex candidate into
`patterns.json["boundary_pointers"]`, including ones that never resolved to anything on
disk — the tool already computes ground truth (`resolve_boundary_target` checks the real
filesystem) but wasn't using it to decide what to report, only what to gate on. It now
does: unresolved candidates (prose false positives — never real paths, never load-
bearing, never gated on) are dropped from the emitted list by default, with the dropped
count reported plainly (`summary.boundary_pointers_unresolved_dropped`) rather than
hidden — nothing silently vanishes, it's just no longer mixed in with actual findings.
`--include-unresolved-boundary-pointers` opts back into the full noisy list, for anyone
tuning `--boundary-config` who needs to see what the patterns are over/under-matching.
Verified live on `workspace/reception`: default output went from 84 boundary pointers
(38 real + 46 noise) to exactly 38 — 100% signal — with the flag reproducing the
original 84. The 38 real, gate-relevant pointers are byte-for-byte unchanged; every
downstream consumer (`state.py`'s `shared` gate, `bundle_synopsis.py`'s README) already
filtered on resolution status internally, so nothing downstream had to change.

Smaller, first-pass improvement, kept because it still helps the (now opt-in) full
list: tightened `path_dir_token` in `references/boundary.scan.json`, the noisiest of
the three detection patterns, which previously matched any `word/word` shape regardless
of case or context. Every segment must now start lowercase (real directory names in
this ecosystem are lowercase; kills Title-Case/ALL-CAPS prose lists like
`Agents/Skills/Workflows` or `TODO/FIXME` outright), and a match immediately followed by
a copula (`mode/value/status **are** filled by...`) is rejected. What's left
(`blocker/fork`, `claim/file` — lowercase English word-pairs used as shorthand for "or")
is genuinely undecidable from a real path by regex alone, since real kebab-case
directory names have the identical shape — `boundary-protocol.md` says so explicitly
now instead of citing a since-fixed example. This mattered more before the real fix
above (it shrank the noise that used to ship by default); now it just shrinks what
`--include-unresolved-boundary-pointers` shows.

No contract change to the `shared` gate either way: unresolved pointers never blocked
it before this release and still don't.

## 1.2.1 (2026-07-17)

Release-readiness pass — no behavior contract changes, patch bump. Found by driving the
whole phase lifecycle for real (self-scan plus a second live run against
one real subproject inside a large multi-agent repo, through probe, scan, telemetry, every state
transition, disposition, `--follow-boundaries`, and the registry validate/propose
commands) rather than reading the code. Five fixes, all bugs the dogfooding actually
hit, none design changes:

- **Bundle paths were not portable.** `export_bundle.py` wrote `manifest.json`'s
  `export` field with `os.path.join`, which emits backslashes on Windows — baked
  straight into `README.md` and `handoff.json` too. A bundle whose entire purpose is
  "content that travels" (`SKILL.md`) shipped Windows-only relative paths by default.
  Now always forward-slash, OS-independent.
- **The skill's own quickstart crashed on first use.** `environment_probe.py --out
  <run>/environment.json` — the literal first command in `SKILL.md` — raised a raw
  `FileNotFoundError` traceback whenever `<run>` hadn't been created yet, instead of
  creating it like `cartographer_scan.py`'s writer already does. `session_telemetry.py
  --out` had the same gap. Both now create the parent directory first.
- **Inconsistent text encoding.** `state.py`, `session_telemetry.py`,
  `bundle_synopsis.py`, and `export_bundle.py` had file reads/writes with no explicit
  `encoding="utf-8"`, unlike the rest of the codebase. Latent: this host's Python
  defaults to UTF-8 mode so it didn't reproduce here, but the generated docs contain
  non-ASCII punctuation (em dashes, arrows) and the tool's whole premise is running
  across arbitrary hosts — a legacy-codepage Windows box would mojibake or crash on
  its own README. Normalized to the `encoding="utf-8"` convention already used
  elsewhere.
- **`state.py disposition <id>` didn't strip its argument.** A trailing CR/whitespace
  on the id (easy to pick up from Windows text tooling) silently recorded the
  disposition under the wrong key, so `advance shared` kept reporting the pointer as
  undispositioned with no clue why the disposition that was just recorded didn't
  count. Now stripped before use.

Verified live: fresh runs of the full pipeline (uncreated run dir → probe → scan →
telemetry → init → negotiate → elicit(skip) → export → synopsis → exported →
`shared` blocked on 38 real undispositioned pointers → disposition each → `shared`
succeeds → synopsis regenerated with dispositions shown) against two targets, plus
`--follow-boundaries` (capped hop confirmed, file-type pointers correctly left
unexpanded) and `concern_registry.py validate`/`propose`. Confirmed as design, not
touched: the noisy `path_dir_token` boundary-pointer false-positive rate on prose
(`boundary-protocol.md` already documents and contains it — never blocks the gate,
never shown in `README.md`) and the "scan's own launch directory" resolution base
(works exactly as documented when the scan is launched from the target's repo root,
reproduced both the miss and the hit).

## 1.2.0 (2026-07-17)

Boundary pointers. A live run against one real subproject inside a large multi-agent repo (a real
QA-agent commissioning) surfaced a structural gap by luck: the target's own docs named
the code that actually implements it (`tools/session/{claim,route}.py` and the
SessionStart hook chain), but that code lives outside the declared root and the scan
never said so — a card built from that run would have silently omitted what its target
depends on, failing the replication test it's supposed to pass. `cartographer_scan.py`
now detects this by default, every run, at no extra walk: every file already read for
any concern is also checked against `references/boundary.scan.json`'s path-reference
patterns, each match resolved and classified relative to the target root (ancestor /
sibling / cousin / unresolved), deduplicated, and given a cheap automatic peek —
emitted as `patterns.json["boundary_pointers"]`. Naming is unconditional; actually
scanning what a pointer names is a separate, explicit opt-in (`--follow-boundaries`,
capped by `--max-boundary-follow`, exactly one hop, no crawl) — this is the resolution
of the tension between "the map must say what it doesn't cover" and "never read outside
the declared root by surprise" (`environment-protocol.md`'s authority boundary).
`state.py` gained a `disposition` subcommand and now refuses to advance a bundle to
`shared` while any resolved boundary pointer carries none (included / excluded /
deferred, with a reason) — the same enforcement shape it already used for
README.md/handoff.json and secret warnings, not a new mechanism. `bundle_synopsis.py`
surfaces the same list as a "Points beyond this map" section and a hard-gated
`handoff.json` action. New: `references/boundary-protocol.md`. Minor bump: additive
fields only (`boundary_pointers` in patterns.json, new CLI flags default to current
behavior when omitted except the new hard gate at `shared`, which only fires when a
bundle actually carries boundary evidence) — no existing fills or concern contracts
invalidated.

## 1.1.0 (2026-07-17)

Bundle review surfaces. New `scripts/bundle_synopsis.py` generates `README.md` (human
synopsis: state history, findings at a glance, review items, next actions) and
`handoff.json` (agent surface: typed actions with owner human|agent and commands where
mechanical, pending states, unresolved secret warnings, artifact index) from the
bundle's own contents. `state.py` now refuses to advance a bundle to `shared` unless
both surfaces exist. Minor bump: no existing fills or contracts invalidated.

## 1.0.0 — "First Light" (2026-07-17)

First versioned release, cut after the inaugural commissioning run (the cartographer
pointed at its own tree — first light verifies the optics on a known object; it is not
a survey). Lineage: v0.x iterations in-conversation (Cowork/Claude), architectural fork
(registry-driven concerns, environment negotiation, single-pass scanner), then this
polish: session-quality instrument restored (`scripts/session_telemetry.py`),
`produced_by` stamping on every emitted artifact, versioning semantics written down,
founding concern statuses made honest (provisional until evidenced by a real run, per
the registry's own promotion rule).

## Versioning semantics

- **Skill version** lives in `VERSION` (semver). Every artifact the skill emits — scan
  results, telemetry, bundle manifests, state transitions — carries a `produced_by`
  block with the skill version (and, where computed, the registry signature). A
  resuming or receiving agent compares those stamps against its own copies before
  trusting fills; a mismatch is drift to reconcile, not to ignore.
- **Concern versions** (X.Y in the registry): bump **minor** for changes that do not
  invalidate existing fills (glob/config widening, prose clarification, added edge
  patterns). Bump **major** (X) when the interrogation question's meaning, the type, or
  cares_about changes — existing fills recorded under the old version become
  `discovered`-at-best and must be re-elicited. Per-fill provenance records
  `concern@version` so this is checkable mechanically.
- **Status ladder** (`provisional` → `stable`): a concern is promoted only after it has
  survived a real run — produced evidence, or a defensible structured absence, against
  a real target. The founding twelve entered 1.0.0 as provisional; those evidenced by
  the First Light commissioning run were promoted in this release, the rest remain
  provisional until the first field run (the QA-agent cartography) exercises them.
- **Registry schema_version** changes only with breaking contract changes and requires
  a migration note here.
