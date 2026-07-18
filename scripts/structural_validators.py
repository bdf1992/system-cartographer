#!/usr/bin/env python3
"""Concern-specific structural validators.

A glob/extension match makes a file a *candidate* — nothing more. This module
is what a candidate has to survive to become *structural* (parses against the
concern's real shape) or *behavioral* (the file demonstrates an actual
operation, not just a declaration). `evidence_stage` never moves past
"candidate" from a bare filename match alone; every function here has to look
at real content and say why.

Two concerns (memories, and the cross-cutting "referenced by real code")
need context beyond their own file text — `ctx` carries whatever the caller
(cartographer_scan.py) has already computed once for the whole scan
(`internal_names`, `path_references`) rather than re-deriving it per file.

Every validator returns a list of dicts:
    {"evidence_stage": "structural"|"behavioral", "signal": "...", "locator_lines": [a,b]|None}
An empty list means: still just a candidate, and that's an honest answer, not
a failure — most files matched by a broad glob are not going to be real.
"""
import ast
import os
import re
import sys

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)


def _f(stage, signal, lines=None):
    return {"evidence_stage": stage, "signal": signal, "locator_lines": lines}


def frontmatter(text):
    """Returns (fields_dict_or_None, (start_line, end_line), body_text)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, None, text
    fields = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if mm:
            fields[mm.group(1).lower()] = mm.group(2).strip()
    end_line = m.group(0).count("\n") + 1
    return fields, (1, end_line), text[m.end():]


def validate_agent(rel, text, ctx):
    fm, lines, _ = frontmatter(text)
    if not fm:
        return []
    identity = fm.get("name") or fm.get("description")
    tools = fm.get("tools") or fm.get("tool")
    if identity and tools:
        return [_f("structural",
                    f"frontmatter declares identity ({'name' if fm.get('name') else 'description'}) "
                    f"and tool authority ({tools[:60]!r})", lines)]
    return []


def validate_skill(rel, text, ctx):
    fm, lines, body = frontmatter(text)
    if not fm or "name" not in fm or "description" not in fm:
        return []
    if len(body.strip()) < 40:
        return []
    return [_f("structural",
                "frontmatter declares name + invocation description, with a real instruction body "
                f"({len(body.strip())} chars past frontmatter)", lines)]


WORKFLOW_META_RE = re.compile(r"export\s+const\s+meta\s*=")
WORKFLOW_CALL_RE = re.compile(r"\b(?:phase|pipeline|parallel)\s*\(")
GH_ACTIONS_ON_RE = re.compile(r"^\s*on:\s*$", re.MULTILINE)
GH_ACTIONS_JOBS_RE = re.compile(r"^\s*jobs:\s*$", re.MULTILINE)


def validate_workflow(rel, text, ctx):
    if WORKFLOW_META_RE.search(text) and WORKFLOW_CALL_RE.search(text):
        return [_f("structural",
                    "declares meta.phases and calls phase()/pipeline()/parallel() — an ordered, "
                    "branchable sequence, not just a name containing 'workflow'", None)]
    if GH_ACTIONS_ON_RE.search(text) and GH_ACTIONS_JOBS_RE.search(text):
        return [_f("structural", "GitHub Actions trigger (on:) with an ordered jobs: list", None)]
    if re.search(r"cron_expression", text) and re.search(r"\b(steps|phases|tasks)\s*:", text):
        return [_f("structural", "cron trigger with a declared step/phase list", None)]
    return []


def validate_memories(rel, text, ctx):
    refs = ctx.get("path_references", set())
    base = os.path.basename(rel)
    if rel in refs or base in refs:
        return [_f("behavioral",
                    "path or basename appears as a reference target elsewhere in the scan — a proxy "
                    "for a demonstrated reader/writer, not a proven one (see reference before trusting)",
                    None)]
    return []


BEHAVIORAL_INTEGRATION_PATTERNS = [
    re.compile(r"\bmcp__\w+__\w+\s*\("),
    re.compile(r"\bOctokit\s*\("),
    re.compile(r"\.rest\.\w+\.\w+\("),
    re.compile(r"\bgh\s+(?:api|issue|pr|repo)\b"),
    re.compile(r"\brequests\.(?:get|post|put|delete)\(\s*f?['\"][^'\"]*(?:github|gitlab|slack|jira|confluence)"),
    re.compile(r"\bfetch\(\s*[`'\"]https?://api\.\w+"),
    # a starter set of common real client-SDK shapes, not an exhaustive library
    # list — extend as a real run surfaces a client this misses.
    re.compile(r"\bGithub\(\s*[\w\"'.]"),                       # PyGithub
    re.compile(r"\.(?:get_repo|get_issue|create_issue|create_pull|get_pull)\("),
    re.compile(r"\bWebClient\(\s*(?:token|[\w\"'.])"),          # Slack SDK
    re.compile(r"\bJIRA\(\s*(?:server|[\w\"'.])"),              # jira-python
    re.compile(r"\bslack_sdk\b|\bslack_bolt\b"),
]


def validate_integrations(rel, text, ctx):
    for rx in BEHAVIORAL_INTEGRATION_PATTERNS:
        m = rx.search(text)
        if m:
            return [_f("behavioral", f"operational call pattern matched: {m.group(0)[:60]!r} — a real "
                        "invocation, not a prose mention", None)]
    return []


MANIFEST_NAME_RE = re.compile(
    r"(?:^|/)(?:requirements[^/]*\.txt|package\.json|pyproject\.toml|Pipfile|go\.mod|Gemfile)$",
    re.IGNORECASE,
)
INSTALL_INVOCATION_RE = re.compile(r"\b(?:git clone|pip install|npm install|npm ci|go get|gem install|yarn add)\b")


def validate_required_tools_repos(rel, text, ctx):
    if MANIFEST_NAME_RE.search(rel):
        return [_f("structural", "declarative dependency manifest file (not a mention of one)", None)]
    m = INSTALL_INVOCATION_RE.search(text)
    if m:
        return [_f("behavioral", f"explicit install/clone invocation: {m.group(0)!r}", None)]
    return []


EXEMPLAR_INVOCATION_RE = re.compile(r"\b(?:def test_\w+|it\(|test\(|describe\()")
EXEMPLAR_ASSERTION_RE = re.compile(r"\b(?:assert\b|expect\(|self\.assertEqual|toBe\(|toEqual\()")


def validate_exemplars(rel, text, ctx):
    if EXEMPLAR_INVOCATION_RE.search(text) and EXEMPLAR_ASSERTION_RE.search(text):
        return [_f("structural", "test-shaped: an invocation form and an assertion form both present "
                    "(input/output + a checked success condition)", None)]
    return []


FAILURE_MARKER_RE = re.compile(
    r"\b(?:Traceback \(most recent call last\)|AssertionError|FAILED|panic:|Exception:|Error:\s*\S)"
)


def validate_issues(rel, text, ctx):
    m = FAILURE_MARKER_RE.search(text)
    if m:
        return [_f("structural", f"real failure evidence present ({m.group(0)[:40]!r}), not just a TODO/FIXME", None)]
    return []


SHARE_CHANNEL_PATTERNS = [
    re.compile(r"(?:github|gitlab|bitbucket)\.[a-z]+[:/][\w\-]+/[\w\-.]+"),
    re.compile(r"https?://[\w.\-]*(?:confluence|wiki|notion)[\w.\-]*"),
    re.compile(r"https?://[\w.\-]+/(?:docs|documentation|wiki)"),
]


def validate_shareability(rel, text, ctx):
    for rx in SHARE_CHANNEL_PATTERNS:
        m = rx.search(text)
        if m:
            return [_f("structural", f"names a real reachable channel ({m.group(0)[:60]!r}), not just "
                        "markdown existing", None)]
    return []


VALIDATORS = {
    "agent": validate_agent,
    "skill": validate_skill,
    "workflow": validate_workflow,
    "memories": validate_memories,
    "integrations": validate_integrations,
    "required-tools-repos": validate_required_tools_repos,
    "exemplars": validate_exemplars,
    "issues": validate_issues,
    "shareability": validate_shareability,
}


def validate(concern_id, rel, text, ctx=None):
    fn = VALIDATORS.get(concern_id)
    if not fn:
        return []
    return fn(rel, text, ctx or {})


# --- code-scripts: language-aware import classification -------------------
#
# The registered concern's edge_patterns are plain regexes over raw text —
# they cannot tell an `import` statement from the word "import" inside a
# comment or a docstring ("# derived from the theory" -> a bogus "from the"
# python_import edge). Python gets a real fix: ast.parse cannot mis-tokenize
# prose as an Import node. JS/TS have no stdlib parser available, so the fix
# there is a heuristic upgrade (strip comments, require a real module-specifier
# shape) — real, but named honestly as heuristic, not a full parse.

try:
    STDLIB_MODULES = set(sys.stdlib_module_names)  # 3.10+
except AttributeError:  # pragma: no cover - older Python
    STDLIB_MODULES = {
        "os", "sys", "re", "json", "itertools", "functools", "collections", "subprocess",
        "hashlib", "time", "datetime", "argparse", "typing", "pathlib", "shutil", "math",
        "random", "logging", "unittest", "io", "abc", "enum", "dataclasses", "threading",
        "asyncio", "socket", "struct", "copy", "glob", "tempfile", "traceback", "inspect",
        "importlib", "string", "textwrap", "csv", "sqlite3", "xml", "html", "http", "urllib",
        "email", "base64", "uuid", "platform", "warnings", "contextlib", "concurrent",
        "multiprocessing", "pickle", "gzip", "zipfile", "tarfile", "configparser", "ast",
        "dis", "keyword", "token", "tokenize",
    }

_MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _classify_module(name, internal_names):
    if not name or not _MODULE_NAME_RE.match(name):
        return "unresolved"
    if name in STDLIB_MODULES:
        return "stdlib"
    if name in internal_names:
        return "internal"
    return "external"


def classify_python_imports(rel, text, internal_names):
    """Returns (findings, rejected). A rejected entry means the file did not
    even parse — every candidate import in it is unknowable, named as such
    rather than silently dropped."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [], [{"reason": f"does not parse as Python: {exc.msg} (line {exc.lineno})"}]
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                findings.append(_f("structural",
                                    f"real Python import: {alias.name} ({_classify_module(top, internal_names)})",
                                    [node.lineno, node.lineno]) | {"import_target": alias.name,
                                                                    "import_class": _classify_module(top, internal_names)})
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                findings.append(_f("structural",
                                    f"real Python import: from {node.module} ({_classify_module(top, internal_names)})",
                                    [node.lineno, node.lineno]) | {"import_target": node.module,
                                                                    "import_class": _classify_module(top, internal_names)})
    return findings, []


_JS_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_JS_IMPORT_RE = re.compile(
    r"""(?:^\s*import\s+(?:[\w*${},\s]+\s+from\s+)?|require\(\s*)['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_JS_SPEC_SHAPE_RE = re.compile(r"^(?:\.{1,2}/)?[@\w][\w@./-]*$")


def classify_js_imports(rel, text, internal_names):
    """Heuristic, not a real parser (no JS AST available in stdlib): strips
    comments first (so 'from the mother lode' inside a // comment can't
    match), then requires the quoted specifier to have a real module-path
    shape — no spaces, no sentence-like content. A destructured one-letter
    import ('f') is real JS and correctly stays accepted; a prose sentence
    is correctly rejected because it can never match `_JS_SPEC_SHAPE_RE`."""
    stripped = _JS_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), text)
    findings = []
    for m in _JS_IMPORT_RE.finditer(stripped):
        spec = m.group(1)
        line = stripped.count("\n", 0, m.start()) + 1
        if not _JS_SPEC_SHAPE_RE.match(spec):
            continue  # rejected candidate: not a real module-specifier shape
        cls = "internal" if spec.startswith(".") else _classify_module(
            re.split(r"[/@]", spec.lstrip("@"))[0] if spec.startswith("@") else spec.split("/")[0],
            internal_names,
        )
        if spec.startswith("."):
            cls = "internal"
        findings.append(_f("structural", f"real JS/TS import specifier: {spec} ({cls})", [line, line])
                         | {"import_target": spec, "import_class": cls})
    return findings, []


def classify_imports(rel, text, internal_names):
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".py":
        findings, rejected = classify_python_imports(rel, text, internal_names)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        findings, rejected = classify_js_imports(rel, text, internal_names)
    else:
        findings, rejected = [], []
    # A file with real function/class structure IS behavior, even with zero
    # imports — code-scripts asks "what implements the actual behavior", not
    # "what imports something". Import-only evidence would wrongly leave a
    # dependency-free real script stuck at candidate forever.
    if not any(f["evidence_stage"] == "structural" for f in findings):
        defn = has_code_definitions(rel, text)
        if defn:
            findings.append(_f("structural", defn, None))
    return findings, rejected


_PY_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_JS_DEF_RE = re.compile(r"\bfunction\s+\w+\s*\(|\bclass\s+\w+|=>\s*{|module\.exports\s*=")


def has_code_definitions(rel, text):
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return None
        if any(isinstance(n, _PY_DEF_NODES) for n in ast.walk(tree)):
            return "contains real function/class definitions (AST-detected), independent of imports"
        return None
    if ext in (".js", ".ts", ".jsx", ".tsx", ".sh", ".rb", ".go"):
        if _JS_DEF_RE.search(text) or re.search(r"^\s*def\s+\w+\(|^\s*func\s+\w+\(", text, re.MULTILINE):
            return "contains a real function/class definition shape, independent of imports"
        return None
    return None
