#!/usr/bin/env python3
"""Validate, combine, and propose typed concern registry entries."""
import argparse
import json
import os
import re
import sys

TYPES = {"actor", "instruction", "sequence", "artifact", "dependency", "integration", "memory", "telemetry", "exemplar", "failure", "distribution", "relation", "environment", "custom"}
KINDS = {"regex-graph", "join", "external", "conversation"}
STATUSES = {"stable", "provisional", "disabled"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def read_registry(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        data = {"schema_version": "1.0", "concerns": data}
    return data


def validate_concern(item, source="registry"):
    errors = []
    required = {"id", "version", "type", "title", "question", "scanner", "requires", "produces", "status"}
    missing = sorted(required - set(item))
    if missing:
        errors.append(f"{source}: missing {', '.join(missing)}")
        return errors
    if not ID_RE.match(item["id"]):
        errors.append(f"{source}: invalid id {item['id']!r}")
    if item["type"] not in TYPES:
        errors.append(f"{source}:{item['id']}: invalid type {item['type']!r}")
    if item["status"] not in STATUSES:
        errors.append(f"{source}:{item['id']}: invalid status {item['status']!r}")
    if not isinstance(item["scanner"], dict) or item["scanner"].get("kind") not in KINDS:
        errors.append(f"{source}:{item['id']}: invalid scanner kind")
    if item.get("scanner", {}).get("kind") == "regex-graph" and not item["scanner"].get("config"):
        errors.append(f"{source}:{item['id']}: regex-graph requires scanner.config")
    for key in ("requires", "produces"):
        if not isinstance(item[key], list) or not all(isinstance(v, str) for v in item[key]):
            errors.append(f"{source}:{item['id']}: {key} must be a string list")
    return errors


def load(paths):
    merged = {}
    order = []
    errors = []
    for path in paths:
        data = read_registry(path)
        if data.get("schema_version") != "1.0":
            errors.append(f"{path}: unsupported schema_version")
        for item in data.get("concerns", []):
            errors.extend(validate_concern(item, path))
            cid = item.get("id")
            if not cid:
                continue
            copy = dict(item)
            copy["_registry_dir"] = os.path.dirname(os.path.abspath(path))
            if cid not in merged:
                order.append(cid)
            merged[cid] = copy
    known = set(merged)
    for cid, item in merged.items():
        unknown = sorted(set(item.get("depends_on", [])) - known)
        if unknown:
            errors.append(f"{cid}: unknown dependencies {unknown}")
    return [merged[cid] for cid in order], errors


def clean(items):
    return [{k: v for k, v in item.items() if not k.startswith("_")} for item in items]


def cmd_validate(paths):
    items, errors = load(paths)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"valid: {len(items)} concerns ({sum(i['status'] == 'provisional' for i in items)} provisional)")
    return 0


def cmd_merge(paths, out):
    items, errors = load(paths)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    text = json.dumps({"schema_version": "1.0", "concerns": clean(items)}, indent=2) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text, end="")
    return 0


def cmd_propose(args):
    item = {
        "id": args.id,
        "version": "0.1",
        "type": args.type,
        "title": args.title,
        "question": args.question,
        "scanner": {"kind": "conversation"},
        "requires": args.requires,
        "produces": args.produces or ["evidence.observation"],
        "depends_on": [],
        "status": "provisional",
        "signal": args.signal,
        "registration_questions": [
            "Does this produce evidence no existing concern owns?",
            "Does resolving it change replication, authority, or handoff?",
            "Has at least one real run confirmed the boundary?"
        ]
    }
    errors = validate_concern(item, "proposal")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    payload = {"schema_version": "1.0", "concerns": [item]}
    text = json.dumps(payload, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text, end="")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Manage typed cartography concern overlays")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate")
    p.add_argument("--registry", action="append", required=True)
    p = sub.add_parser("merge")
    p.add_argument("--registry", action="append", required=True)
    p.add_argument("--out")
    p = sub.add_parser("propose")
    p.add_argument("--id", required=True)
    p.add_argument("--type", choices=sorted(TYPES), default="custom")
    p.add_argument("--title", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--signal", required=True)
    p.add_argument("--requires", action="append", default=[])
    p.add_argument("--produces", action="append", default=[])
    p.add_argument("--out")
    args = ap.parse_args()
    if args.command == "validate":
        raise SystemExit(cmd_validate(args.registry))
    if args.command == "merge":
        raise SystemExit(cmd_merge(args.registry, args.out))
    raise SystemExit(cmd_propose(args))


if __name__ == "__main__":
    main()
