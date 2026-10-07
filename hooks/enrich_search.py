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
MAX_CHARS = 1500
MAX_LINE = 220
MAX_NAMED = 4
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


def subjects(payload):
    """What the search was plainly about: the names it looked for, and the files it returned."""
    tool, given, response = payload.get("tool_name"), payload.get("tool_input") or {}, payload.get("tool_response")
    names, paths = [], []
    for part in (given.get("pattern") or "").split("|") if tool == "Grep" else []:
        name = part.strip().strip("()").strip("\\b").replace("\\(", "").replace("def ", "").replace("class ", "").strip()
        if _IDENTIFIER.match(name) and name not in names:
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


def file_node(index, lowered, subject):
    """The map's node for a path, whatever its case or slashes, and wherever a copy of the tree sits:
    a file in a worktree is the same file as far as the map knows. At least two path parts must match."""
    parts = subject.replace("\\", "/").lower().strip("/").split("/")
    for k in range(len(parts) - 1 if len(parts) > 1 else 1):
        real = lowered.get("/".join(parts[k:]))
        if real:
            return next((i for i in index["files"][real] if index["nodes"][i]["kind"] == "file"), None)
    return None


def name_node(index, name, returned):
    """The definition a searched name means. A name defined once is that definition. A name defined
    in several files is only the one in a file the search returned; otherwise it is said to be
    several, since guessing would put another function's facts in front of the agent."""
    nodes = index["nodes"]
    key = name.lower().rstrip("()").lstrip(".")
    found = index["names"].get(key) or index["names"].get(key.split(".")[-1]) or []
    found = [i for i in found if nodes[i]["kind"] != "file"]
    here = [i for i in found if nodes[i]["file"] in returned]
    if here or len(found) == 1:
        return max(here or found, key=lambda i: len(index["used_by"][i])), None
    if not found:
        return None, None
    files = sorted({nodes[i]["file"] for i in found if nodes[i]["file"]})
    return None, (f"- {name}: {len(found)} definitions in the map, none in a file this search returned "
                  f"({', '.join(files[:MAX_NAMED])}{' ...' if len(files) > MAX_NAMED else ''})")


def from_source(root, row):
    """What the code says about itself, read from the file as it is now: the first sentence of the
    docstring, and for a function its signature. A file that will not parse says nothing."""
    import ast
    full = os.path.join(root or "", row["file"])
    if not row["file"].endswith(".py") or not os.path.isfile(full) or os.path.getsize(full) > MAX_SOURCE:
        return None, None
    try:
        with open(full, encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError, ValueError):
        return None, None
    node, signature = tree, None
    if row["kind"] != "file":
        name = row["label"].rstrip("()").lstrip(".").split(".")[-1]
        line = int("".join(ch for ch in str(row["line"] or "").split("-")[0] if ch.isdigit()) or 0)
        same = [n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name]
        if not same:
            return None, None
        node = min(same, key=lambda n: abs(n.lineno - line))    # the map's line may have drifted
        if not isinstance(node, ast.ClassDef):
            signature = f"{name}({ast.unparse(node.args)})"[:MAX_LINE]
    doc = (ast.get_docstring(node) or "").strip().split("\n\n")[0].replace("\n", " ")
    stop = doc.find(". ")
    return (doc[:stop + 1] if stop > 0 else doc)[:MAX_LINE] or None, signature


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


def card(gq, index, i, notes, notes_path):
    """One thing the search turned up, as a few whole lines: what it is, what the code says it
    does, what is on record about its file, and who uses it by name."""
    row = index["nodes"][i]
    where = f"{row['file']}{' ' + str(row['line']) if row['line'] else ''}" if row["file"] else row["layer"]
    lines = [f"- {row['label']} ({row['kind']}, {where})"]
    does, signature = from_source(index.get("root"), row) if row["file"] else (None, None)
    if signature:
        lines.append(f"  signature: {signature}")
    if does:
        lines.append(f"  does: {does}")
    note = notes.get(row["file"].lower())
    if isinstance(note, dict) and note.get("about") and note["about"] != does:
        lines.append(f"  {'about' if row['kind'] == 'file' else 'its file'}: {note['about']}")
    lines += known(dict(note, about=None)) if isinstance(note, dict) else []
    parsed = row["layer"] == "code"
    if notes and not note and not does and parsed and row["kind"] == "file" and not row["test"]:
        # A gap is said with the place to fill it, so it is a job and not a remark.
        lines.append(f"  no description on record or in the file: add a docstring, or an entry in {notes_path}")
    start = gq.start_set(index, i)
    direct = {j for s in start for j, _relation, _inferred in index["used_by"][s] if j not in start}
    code, tests = by_file(index, direct, row["file"])
    if code:
        lines.append(f"  referred to from {named(code)}")
    if tests:
        lines.append(f"  tests that refer to it directly, {named(tests)}")
    if not direct:
        # The parse misses links it cannot resolve, and does not parse every kind of file.
        lines.append("  no links found in the map" if parsed else "  this kind of file is not parsed for links; search for its name")
    elif not tests and not row["test"]:
        lines.append("  no test refers to it directly in the map")
    extra = [f"{row['lint']} lint finding{'' if row['lint'] == 1 else 's'} (ruff)" if row["lint"] else "",
             "claims on its cluster: " + ", ".join(index["claims"].get(row["cluster"], []))
             if index["claims"].get(row["cluster"]) else ""]
    if any(extra):
        lines.append("  " + "; ".join(item for item in extra if item))
    return lines


def enrich(payload):
    import graph_query as gq
    path = find_index(payload.get("cwd"))
    if path is None:
        return None
    index = gq.read_json(path)
    notes = load_notes(path)
    notes_path = os.environ.get("CARTOGRAPHER_NOTES") or os.path.join(os.path.dirname(path), "notes.json")
    names, paths = subjects(payload)
    lowered = {key.lower(): key for key in index["files"]}
    file_ids = [i for i in dict.fromkeys(file_node(index, lowered, item) for item in paths) if i is not None]
    returned = {index["nodes"][i]["file"] for i in file_ids}
    blocks = []
    for name in names:
        i, several = name_node(index, name, returned)
        blocks.append((i, [several] if several else None))
    blocks += [(i, None) for i in file_ids]
    head = "From the system map (graph_query.py impact <name> for everything a change reaches):"
    lines, files, count = [head], set(), 0
    for i, said in blocks:
        if i is None and not said:
            continue
        # One card per file: a function already shown stands for the file it is in.
        if i is not None and index["nodes"][i]["file"] in files:
            continue
        block = said or card(gq, index, i, notes, notes_path)
        if len("\n".join(lines + block)) > MAX_CHARS:
            break                                   # whole cards only; a line is never cut
        if i is not None:
            files.add(index["nodes"][i]["file"])
        lines += block
        count += 1
        if count == MAX_SUBJECTS:
            break
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
