#!/usr/bin/env python3
"""Emit a conservative, vendor-neutral description of the current host.

The probe is read-only. It inspects the declared target root, process environment
names (never values), and executable availability. It does not probe the network,
search a home directory, or open transcript/session stores.
"""
import argparse
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone


def capability(cid, status, source, detail=""):
    item = {"id": cid, "status": status, "source": source}
    if detail:
        item["detail"] = detail
    return item


def detect_host(root, declared=None):
    if declared:
        return {"id": declared, "confidence": "declared", "evidence": []}
    env_names = set(os.environ)
    markers = []
    candidates = []
    if "CLAUDE_CODE" in env_names or "CLAUDE_CODE_ENTRYPOINT" in env_names:
        candidates.append("claude-code")
        markers.append("Claude Code process marker")
    if "CODEX_PRIMARY_RUNTIME_ROOT" in env_names or os.path.isdir(os.path.join(root, ".codex")):
        candidates.append("codex")
        markers.append("Codex runtime or workspace marker")
    if "OLLAMA_HOST" in env_names:
        candidates.append("ollama-harness")
        markers.append("Ollama endpoint marker")
    if len(set(candidates)) == 1:
        return {"id": candidates[0], "confidence": "detected", "evidence": markers}
    if candidates:
        return {"id": "hybrid-or-custom", "confidence": "detected", "evidence": markers}
    return {"id": "unknown", "confidence": "unknown", "evidence": []}


def detect_model(provider=None, name=None):
    if provider or name:
        return {"provider": provider, "name": name, "source": "declared"}
    env_names = set(os.environ)
    detected = []
    for marker, candidate in (
        ("OPENAI_API_KEY", "openai"),
        ("XAI_API_KEY", "xai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OLLAMA_HOST", "ollama"),
    ):
        if marker in env_names:
            detected.append(candidate)
    if len(detected) == 1:
        return {"provider": detected[0], "name": None, "source": "detected"}
    return {"provider": None, "name": None, "source": "unknown"}


def parse_declarations(values):
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"capability declaration must be ID=STATUS: {value}")
        cid, status = value.split("=", 1)
        if status not in {"available", "unavailable", "unknown", "restricted"}:
            raise ValueError(f"invalid capability status: {status}")
        result[cid] = capability(cid, status, "declared")
    return result


def probe(root, host=None, provider=None, model=None, declarations=()):
    root = os.path.abspath(root)
    declared = parse_declarations(declarations)
    caps = {
        "filesystem.read": capability(
            "filesystem.read", "available" if os.path.isdir(root) and os.access(root, os.R_OK) else "unavailable",
            "detected", f"declared target root: {root}"
        ),
        "filesystem.write": capability(
            "filesystem.write", "available" if os.path.isdir(root) and os.access(root, os.W_OK) else "restricted",
            "inferred", "os.access only; host policy may be narrower"
        ),
        "process.exec": capability("process.exec", "available", "detected", "environment probe is executing"),
        "git.read": capability("git.read", "available" if shutil.which("git") else "unavailable", "detected"),
        "search.rg": capability("search.rg", "available" if shutil.which("rg") else "unavailable", "detected"),
        "network.fetch": capability("network.fetch", "unknown", "inferred", "not actively probed"),
        "conversation.ask": capability("conversation.ask", "unknown", "inferred", "must be declared by host/operator"),
        "subagents.spawn": capability("subagents.spawn", "unknown", "inferred", "must be declared by host/operator"),
        "memory.read": capability("memory.read", "unknown", "inferred", "no private stores are probed"),
    }
    caps.update(declared)
    questions = []
    detected_host = detect_host(root, host)
    detected_model = detect_model(provider, model)
    if detected_host["confidence"] == "unknown":
        questions.append({"id": "host", "question": "Which host or harness is orchestrating this run?", "blocks": ["host-specific evidence discovery"]})
    if detected_model["source"] == "unknown":
        questions.append({"id": "model", "question": "Which model/provider is running, if that distinction matters to replication?", "blocks": []})
    for cid in ("conversation.ask", "memory.read"):
        if caps[cid]["status"] == "unknown":
            questions.append({"id": cid, "question": f"Is {cid} available, unavailable, or restricted in this host?", "blocks": [cid]})
    return {
        "schema_version": "1.0",
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": detected_host,
        "model": detected_model,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "working_directory": os.getcwd(),
        },
        "capabilities": sorted(caps.values(), key=lambda x: x["id"]),
        "roots": [{"path": root, "role": "target", "authority": "read"}],
        "constraints": [
            "No network capability was actively tested.",
            "No private session, memory, credential, or home-directory store was opened.",
            "Detected availability does not override host policy or user authority.",
        ],
        "questions": questions,
    }


def main():
    ap = argparse.ArgumentParser(description="Describe a cartography host without vendor assumptions")
    ap.add_argument("--root", default=".", help="Explicit target root; defaults to cwd")
    ap.add_argument("--host", help="Declared host/harness id")
    ap.add_argument("--provider", help="Declared model provider")
    ap.add_argument("--model", help="Declared model name")
    ap.add_argument("--capability", action="append", default=[], metavar="ID=STATUS")
    ap.add_argument("--out")
    args = ap.parse_args()
    try:
        result = probe(args.root, args.host, args.provider, args.model, args.capability)
    except ValueError as exc:
        ap.error(str(exc))
    text = json.dumps(result, indent=2)
    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
