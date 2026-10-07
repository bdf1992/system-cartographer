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
MAX_CHARS = 900
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
    """What the search was plainly about: the name it looked for, then the files it returned."""
    tool, given, response = payload.get("tool_name"), payload.get("tool_input") or {}, payload.get("tool_response")
    found = []
    pattern = given.get("pattern") if tool == "Grep" else None
    if pattern:
        name = pattern.strip().strip("\\b").replace("\\(", "").replace("def ", "").replace("class ", "").strip()
        if _IDENTIFIER.match(name):
            found.append(name)
    if tool == "Read" and given.get("file_path"):
        found.append(given["file_path"])
    text = response if isinstance(response, str) else json.dumps(response) if response is not None else ""
    if isinstance(response, dict):
        for key in ("filenames", "files"):
            if isinstance(response.get(key), list):
                found += [str(item) for item in response[key]]
        text = str(response.get("content") or response.get("stdout") or text)
    for match in _PATH_IN_OUTPUT.finditer(text.replace("\\\\", "\\")):
        found.append(match.group(0))
    seen, ordered = set(), []
    for item in found:
        key = item.replace("\\", "/").lower()
        if key not in seen:
            seen.add(key)
            ordered.append(item)
    return ordered


def enrich(payload):
    import graph_query as gq
    path = find_index(payload.get("cwd"))
    if path is None:
        return None
    index = gq.read_json(path)
    notes = load_notes(path)
    lines, used, noted, count = [], set(), set(), 0
    for subject in subjects(payload):
        hits = gq.find(index, subject, limit=1)
        # A file path must name a scanned file; a name must be an exact name. A near miss says nothing.
        if not hits or hits[0] in used:
            continue
        row = index["nodes"][hits[0]]
        exact = row["label"].lower().rstrip("()").lstrip(".") == subject.lower().rstrip("()").lstrip(".") \
            or subject.replace("\\", "/").lower().endswith(row["file"].lower()) and row["file"]
        if not exact:
            continue
        used.add(hits[0])
        head, _, counts = gq.one_line(gq.describe(index, hits[0])).partition("): ")
        note = notes.get(row["file"].lower()) if row["file"] not in noted else None
        if note and note.get("about"):
            # What the file is for leads; the counts are metadata under it.
            noted.add(row["file"])
            about = note["about"] if row["kind"] == "file" else f"in the file whose job is: {note['about']}"
            lines += [f"- {head}): {about}"] + known(dict(note, about=None)) + ["  " + counts]
        else:
            lines.append(f"- {head}): {counts}")
            if notes and not row["test"] and row["file"] not in noted:
                # A gap is said out loud, so whoever is in the file is asked to fill it.
                lines.append("  nothing is written down about this file yet")
        count += 1
        if count == MAX_SUBJECTS:
            break
    if not lines:
        return None
    text = "From the system map (graph_query.py impact <name> for the full list):\n" + "\n".join(lines)
    return text[:MAX_CHARS]


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
