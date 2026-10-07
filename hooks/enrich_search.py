#!/usr/bin/env python3
"""enrich_search.py -- a Claude Code PostToolUse hook that adds what the graph knows to a search.

An agent's own search (Grep, Glob, Read) answers "where is this written". This runs after
it and adds, for the few things the search most plainly turned up, what each is part of,
how many things depend on it, how many files a change would reach, and which tests would
notice. The search result itself is not touched; the added lines arrive as context.

Wire it in a project's .claude/settings.json:

    {"hooks": {"PostToolUse": [{"matcher": "Grep|Glob|Read", "hooks": [{"type": "command",
      "command": "python <skill>/hooks/enrich_search.py"}]}]}}

It finds the index at $CARTOGRAPHER_INDEX, else at .cartographer/graph-index.json in the
working directory or any folder above it. Build one with:

    python scripts/graph_query.py index --graph <run>/graph/graph.json --out .cartographer/graph-index.json

It never blocks and never fails a tool: with no index, an index it cannot read, a payload it
does not understand, or nothing worth adding, it prints nothing and exits 0. Set
CARTOGRAPHER_ENRICH=off to switch it off. Standard library only.

Where a notes file exists ($CARTOGRAPHER_NOTES, else notes.json beside the index), each file's
written description, its metadata and a pointer to where more is kept follow its line.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

MAX_SUBJECTS = 3
MAX_CHARS = 2000
MAX_LINE = 220
MAX_NAMED = 4
_PAPER = frozenset({".md", ".txt", ".rst", ".json", ".yml", ".yaml", ".toml", ".html", ".csv"})
MAX_COMMON = 40            # a name written in more files than this cannot be told apart by name
MIN_SENTENCE = 40
MAX_SEVERAL = 6          # more definitions than this is a common word, and is not listed
MAX_PATHS = 60             # returned files looked up; a search returning more is not about any of them
MAX_SOURCE = 400_000      # bytes; a larger file is not parsed at hook time
_PATH_IN_OUTPUT = re.compile(r"^([A-Za-z]:)?[^\s:*?\"<>|]+\.[A-Za-z0-9]{1,6}", re.MULTILINE)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{2,60}$")


def find_index(cwd):
    explicit = os.environ.get("CARTOGRAPHER_INDEX")
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    folder = os.path.abspath(cwd or os.getcwd())
    while True:
        candidate = os.path.join(folder, ".cartographer", "graph-index.json")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def load_notes(index_path):
    """What has been written down about each file, keyed by its path in the map.

    {"notes": {"<path>": {"about": "one sentence", "meta": {"layer": "..."}, "see": ["where more is"]}}}
    Found at $CARTOGRAPHER_NOTES, else notes.json beside the index. Absent or unreadable is no notes.
    """
    path = os.environ.get("CARTOGRAPHER_NOTES") or os.path.join(os.path.dirname(index_path), "notes.json")
    try:
        with open(path, encoding="utf-8") as handle:
            notes = json.load(handle).get("notes")
    except (OSError, ValueError, AttributeError):
        return {}
    return {key.replace("\\", "/").lower(): value for key, value in notes.items()} if isinstance(notes, dict) else {}


def note_for(notes, file):
    """The note for a file: its own entry, else the first entry whose key is a pattern it matches
    (wskernel/commands/*), so a folder can be described once."""
    import fnmatch
    key = file.lower()
    if key in notes:
        return notes[key]
    return next((value for pattern, value in notes.items() if "*" in pattern and fnmatch.fnmatch(key, pattern)), None)


def own_uses(full, row):
    """How many more times a name is written in its own file, counted in the file as it is now.
    The map's links leave these out or miss them; a function called only by its neighbours is in use."""
    name = row["label"].rstrip("()").lstrip(".").split(".")[-1]
    if row["kind"] == "file" or not name or not os.path.isfile(full) or os.path.getsize(full) > MAX_SOURCE:
        return 0
    try:
        with open(full, encoding="utf-8", errors="replace") as handle:
            return max(0, len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", handle.read())) - 1)
    except OSError:
        return 0


def known(note):
    """A note as lines: what the file is for, then its metadata, then where to read more."""
    if not isinstance(note, dict):
        return []
    lines = [f"  about: {note['about']}"] if note.get("about") else []
    if isinstance(note.get("meta"), dict) and note["meta"]:
        lines.append("  " + ", ".join(f"{key} {value}" for key, value in note["meta"].items()))
    if note.get("see"):
        lines.append("  see: " + "; ".join(str(item) for item in note["see"][:3]))
    return lines


def searched_name(part):
    r"""The name a grep pattern is plainly after, or None: `^def guard`, `guard\s*\(` and
    `write_record\(.*overwrite` are all after one name; `class \w+Refusal` is after none."""
    clean = part.strip().strip("()").lstrip("^").strip()
    for lead in ("\\b", "async def ", "def ", "class "):
        clean = clean.removeprefix(lead)
    match = re.match(r"[A-Za-z_][A-Za-z0-9_.]{2,60}", clean)
    if not match:
        return None
    rest = clean[match.end():]
    return match.group(0).rstrip(".") if not rest or rest.startswith(("\\(", "(", "\\s", "\\b", ":", "\\.")) else None


def subjects(payload):
    """What the search was plainly about: the names it looked for, and the files it returned."""
    tool, given, response = payload.get("tool_name"), payload.get("tool_input") or {}, payload.get("tool_response")
    names, paths = [], []
    for part in (given.get("pattern") or "").split("|") if tool == "Grep" else []:
        name = searched_name(part)
        if name and name not in names:
            names.append(name)
    if tool == "Read" and given.get("file_path"):
        paths.append(given["file_path"])
    text = response if isinstance(response, str) else json.dumps(response) if response is not None else ""
    if isinstance(response, dict):
        for key in ("filenames", "files"):
            if isinstance(response.get(key), list):
                paths += [str(item) for item in response[key]]
        text = str(response.get("content") or response.get("stdout") or text)
    paths += [match.group(0) for match in _PATH_IN_OUTPUT.finditer(text.replace("\\\\", "\\"))]
    return names, paths


def same_start(a, b):
    """Two files that begin alike: a copy of the mapped file in another checkout, not another project's."""
    try:
        with open(a, "rb") as one, open(b, "rb") as two:
            return one.read(160) == two.read(160)
    except OSError:
        return False


def file_node(index, lowered, subject, cwd):
    """The map's node for a path, whatever its case or slashes. A path outside the mapped tree, or
    under a folder the map does not hold, is only the mapped file when it is a copy of it (a
    worktree): the path must end the same over two parts and the two files must begin alike."""
    nodes, root = index["nodes"], (index.get("root") or "").replace("\\", "/").rstrip("/")
    given = subject.replace("\\", "/")
    parts = given.lower().strip("/").split("/")
    inside = root and given.lower().startswith(root.lower() + "/")
    exact = lowered.get(given.lower()[len(root) + 1:] if inside else "/".join(parts))
    if exact:
        return next((i for i in index["files"][exact] if nodes[i]["kind"] == "file"), None), None
    full = given if os.path.isabs(subject) else os.path.join(cwd or root, subject)
    for k in range(1, len(parts) - 1):
        real = lowered.get("/".join(parts[k:]))
        if real and same_start(full, os.path.join(root, real)):
            return next((i for i in index["files"][real] if nodes[i]["kind"] == "file"), None), full
    return None, None


def name_nodes(index, name, returned):
    """The definitions a searched name means. A name defined once is that definition. A name
    defined in several places is only those in files the search returned, each shown; otherwise
    nothing is guessed, since another function's facts would be put in front of the agent."""
    nodes = index["nodes"]
    key = name.lower().rstrip("()").lstrip(".")
    found = index["names"].get(key) or []
    dotted = not found and "." in key
    if dotted:                                    # Refusal.render: the last part, but only in a returned file
        found = index["names"].get(key.split(".")[-1]) or []
    found = [i for i in found if nodes[i]["kind"] != "file"]
    here = sorted((i for i in found if nodes[i]["file"] in returned), key=lambda i: (-len(index["used_by"][i]), i))
    if here or (len(found) == 1 and not dotted):
        return (here or found)[:MAX_SUBJECTS], None
    if not found or dotted or len(found) > MAX_SEVERAL:
        return [], None                           # a common word: saying "110 definitions" tells nobody anything
    files = sorted({nodes[i]["file"] for i in found if nodes[i]["file"]})
    return [], (f"- {name}: {len(found)} definitions in the map, none in a file this search returned "
                f"({', '.join(files[:MAX_NAMED])}{' ...' if len(files) > MAX_NAMED else ''})")


def clip(text):
    return text if len(text) <= MAX_LINE else text[:MAX_LINE - 3].rstrip() + "..."


def from_source(full, row):
    """What the code says about itself, read from the file as it is now: the first sentence of the
    docstring, a function's signature, a method's class, the line it is on today, and how many
    more times it is used in its own file. A file that will not parse says nothing."""
    import ast
    if not row["file"].endswith(".py") or not os.path.isfile(full) or os.path.getsize(full) > MAX_SOURCE:
        return {}
    try:
        with open(full, encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError, ValueError, RecursionError):
        return {}
    node, said = tree, {}
    if row["kind"] != "file":
        name = row["label"].rstrip("()").lstrip(".").split(".")[-1]
        line = int("".join(ch for ch in str(row["line"] or "").split("-")[0] if ch.isdigit()) or 0)
        kinds = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        same = [(n, parent) for parent in ast.walk(tree) for n in ast.iter_child_nodes(parent)
                if isinstance(n, kinds) and n.name == name]
        if not same:
            return {"gone": True}
        node, parent = min(same, key=lambda pair: abs(pair[0].lineno - line))    # the map's line may have drifted
        owner = parent.name if isinstance(parent, ast.ClassDef) else None
        said.update(owner=owner, line=node.lineno)
        if not isinstance(node, ast.ClassDef):
            said["signature"] = clip(f"{name}({ast.unparse(node.args)})")
        # Uses, not mentions: a bare name for a function or class, self.name or Class.name for a method.
        holders = {"self", "cls", owner}
        said["inside"] = sum(
            1 for n in ast.walk(tree)
            if (isinstance(n, ast.Name) and n.id == name and not owner)
            or (isinstance(n, ast.Attribute) and n.attr == name and owner
                and isinstance(n.value, ast.Name) and n.value.id in holders))
        # A method called on an object (watch.over()) is some object's .over: said apart, not as a sure use.
        said["loose"] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == name) - said["inside"] \
            if owner else 0
    doc = (ast.get_docstring(node) or "").strip().split("\n\n")[0].replace("\n", " ")
    stop = re.search(r"(?<!e\.g)(?<!i\.e)(?<!etc)(?<!vs)\.\s", doc)
    # A first sentence too short to say anything ("(allowed, reason).") is followed by the rest.
    said["does"] = clip(doc[:stop.start() + 1] if stop and stop.start() >= MIN_SENTENCE else doc) or None
    return said


def by_file(index, ids, own):
    """Which files a set of nodes sits in, busiest first, as ('path', how many), tests apart."""
    code, tests = {}, {}
    for j in ids:
        row = index["nodes"][j]
        if row["file"] and row["file"] != own:
            table = tests if row["test"] else code
            table[row["file"]] = table.get(row["file"], 0) + 1
    rank = lambda table: sorted(table.items(), key=lambda item: (-item[1], item[0]))  # noqa: E731
    return rank(code), rank(tests)


def named(files):
    text = ", ".join(f"{path} ({n})" for path, n in files[:MAX_NAMED])
    return f"{len(files)} file{'' if len(files) == 1 else 's'}: {text}" + (" ..." if len(files) > MAX_NAMED else "")


def users(index, start):
    """Who uses a set of nodes, as two sets: links the parse read, and links it guessed from a
    name alone. A guess is never named as a user: `.json()` is not called by all who import json."""
    read, guessed = set(), set()
    for s in start:
        for j, _relation, inferred in index["used_by"][s]:
            if j not in start:
                (guessed if inferred else read).add(j)
    return read, guessed - read


def card(gq, index, i, notes, copy=None):
    """One thing the search turned up, as a few whole lines: what it is, what the code says it
    does, what is on record about its file, and who uses it by name."""
    row = index["nodes"][i]
    full = copy or os.path.join(index.get("root") or "", row["file"])
    source = from_source(full, row) if row["file"] else {}
    does, signature, owner = source.get("does"), source.get("signature"), source.get("owner")
    line = f"L{source['line']}" if source.get("line") else row["line"]
    where = f"{row['file']}{' ' + str(line) if line else ''}" if row["file"] else row["layer"]
    method = row["label"].startswith(".") or bool(owner)
    label = f"{owner}{row['label'] if row['label'].startswith('.') else '.' + row['label']}" if owner else row["label"]
    lines = [f"- {label} ({'method' if method else row['kind']}, {where})"]
    if copy:
        lines.append("  you are in a copy of this file: the lines read from it are this copy's, the users are the mapped checkout's")
    if source.get("gone"):
        lines.append("  the map has it here, and it is not in the file now: moved, renamed or removed since the map was built")
    if signature:
        lines.append(f"  signature: {signature}")
    if does:
        lines.append(f"  does: {does}")
    note = note_for(notes, row["file"])
    if isinstance(note, dict) and note.get("about") and note["about"] != does:
        lines.append(f"  {'about' if row['kind'] == 'file' else 'its file is for'}: {note['about']}")
    lines += known(dict(note, about=None)) if isinstance(note, dict) else []
    parsed = row["layer"] == "code"
    if notes and not note and not does and row["file"].endswith(".py") and row["kind"] == "file" and not row["test"]:
        lines.append("  it has no docstring and nothing is on record about it; if you learn what it is for, add a docstring")
    # Who uses it, from every route there is, as one list: the links the parse read, the files that
    # write its name (module.name(), passed by name, in a string), and the files that write it
    # qualified by its module. A reader given three lists adds them up wrongly.
    read, guessed = users(index, gq.start_set(index, i))
    code, tests = by_file(index, read, row["file"])
    name = row["label"].rstrip("()").lstrip(".").split(".")[-1]
    stem = os.path.splitext(os.path.basename(row["file"]))[0]
    is_file = row["kind"] == "file"
    searched = "written" in index and not is_file and len(name) >= 4
    total, rows = index["written"].get(name, (0, [])) if searched else (0, [])
    wide = total > MAX_COMMON                     # written in too many files for the name alone to mean this thing
    exact = (index.get("loaded") or {}).get(row["file"], []) + (index.get("stemmed") or {}).get(row["file"], []) \
        if is_file else (index.get("qualified") or {}).get(f"{row['file']}::{name}", [])
    merged, papers = {False: dict(code), True: dict(tests)}, set()
    for j, times in exact + ([] if wide else rows):
        other = index["nodes"][j]
        if other["file"] and other["file"] != row["file"]:
            table = merged[bool(other["test"])]
            table[other["file"]] = max(table.get(other["file"], 0), times)
            if os.path.splitext(other["file"])[1].lower() in _PAPER:
                papers.add(other["file"])        # a document or a record that names it: after the code that uses it
    rank = lambda table: sorted(table.items(), key=lambda item: (item[0] in papers, -item[1], item[0]))  # noqa: E731
    code, tests = rank(merged[False]), rank(merged[True])
    if code:
        lines.append(f"  used or named in {named(code)}")
    inside, loose = source.get("inside"), source.get("loose", 0)
    if inside is None:
        inside = own_uses(full, row)             # not Python: the text is all there is to count
    if inside:
        lines.append(f"  used {inside} time{'' if inside == 1 else 's'} in its own file")
    elif loose:
        lines.append(f"  .{name} is written {loose} time{'' if loose == 1 else 's'} in its own file, on some object")
    if wide and searched:
        lines.append(f"  the name {name} is written in {total} files, too many to list; the files above are those the "
                     f"parse linked{'' if method else ' or that write ' + stem + '.' + name}")
    if tests:
        lines.append(f"  tests that use or name it, {named(tests)}")
    elif not row["test"]:
        whole = next((j for j in index["files"].get(row["file"], []) if index["nodes"][j]["kind"] == "file"), None)
        around = users(index, gq.start_set(index, whole))[0] if whole is not None else set()
        # Of the tests that import the file, the one named for it comes first.
        near = sorted(by_file(index, around, row["file"])[1], key=lambda item: (stem.lower() not in item[0].lower(), -item[1], item[0]))
        lines.append("  no test names it" + (f"; tests that import its file, {named(near)}" if near else ", and none imports its file")
                     + ". A test that runs it through a command, a subprocess or a browser is not seen here")
    if not parsed and not read and not exact:
        lines.append("  this kind of file is not parsed for links; search for its name to find what reads it")
    elif not code and not inside and not loose:
        if is_file:
            lines.append("  no other file imports it or writes its module path; a file named only in a table "
                         "(a list of command names, config) is still not seen, so search for its name")
        elif searched and not wide:
            lines.append("  no other file uses it or writes its name")
        else:
            lines.append("  no user found; x.name() on an object is not seen, so search for its name")
    if guessed and "written" not in index:
        files = {index["nodes"][j]["file"] for j in guessed} - {row["file"], ""}
        if files:
            lines.append(f"  {len(files)} more file{'' if len(files) == 1 else 's'} guessed from the name alone, not verified, not listed")
    if row["lint"]:
        lines.append(f"  {row['lint']} lint finding{'' if row['lint'] == 1 else 's'} (ruff)")
    return lines


def enrich(payload):
    import graph_query as gq
    path = find_index(payload.get("cwd"))
    if path is None:
        return None
    index = gq.read_json(path)
    notes = load_notes(path)
    names, paths = subjects(payload)
    nodes, lowered = index["nodes"], {key.lower(): key for key in index["files"]}
    found = dict(pair for pair in (file_node(index, lowered, item, payload.get("cwd")) for item in paths[:MAX_PATHS])
                 if pair[0] is not None)
    file_ids = list(found)
    copies = {nodes[i]["file"]: full for i, full in found.items() if full}
    returned = {nodes[i]["file"] for i in file_ids}
    blocks = []
    for name in names:
        ids, several = name_nodes(index, name, returned)
        blocks += [(i, None) for i in ids] + ([(None, [several])] if several else [])
    shown = {nodes[i]["file"] for i, _said in blocks if i is not None}
    # A function shown stands for its file. Of many files, the most used come first, tests last.
    rest = [i for i in file_ids if nodes[i]["file"] not in shown]
    blocks += [(i, None) for i in sorted(rest, key=lambda i: (nodes[i]["test"], -len(index["used_by"][i])))]
    head = (f"From the system map{' of ' + index['built'] if index.get('built') else ''} "
            "(graph_query.py impact <name> for everything a change reaches):")
    lines, count = [head], 0
    for i, said in blocks:
        block = said or card(gq, index, i, notes, copies.get(nodes[i]["file"]))
        if len("\n".join(lines + block)) > MAX_CHARS:
            break                                   # whole cards only; a line is never cut
        lines += block
        count += 1
        if count == MAX_SUBJECTS:
            break
    if count and len(blocks) > count:
        lines.append(f"({len(blocks) - count} more of what this search returned are in the map and not shown; "
                     "the most used come first)")
    return "\n".join(lines) if count else None


def main():
    if os.environ.get("CARTOGRAPHER_ENRICH", "").lower() == "off":
        return
    try:
        payload = json.load(sys.stdin)
        text = enrich(payload)
    except Exception:  # noqa: BLE001 - a hook that raises would cost the session its tool result
        return
    if text:
        json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}, sys.stdout)


if __name__ == "__main__":
    main()
