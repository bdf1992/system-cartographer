"""Calls written through an imported module name, on a made-up root.

    python -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import code_graph as cg  # noqa: E402

SOURCES = {
    "pkg/__init__.py": "",
    "pkg/mod.py": "def f():\n    return 1\n",
    "pkg/sub/__init__.py": "",
    "pkg/sub/deep.py": "def g():\n    return 2\n",
    "app/method.py": "from pkg import mod\n\n\nclass K:\n    def run(self):\n        return mod.f()\n",
    "app/top.py": "from pkg import mod\n\n\ndef run():\n    return mod.f()\n",
    "app/deep.py": "import pkg.sub.deep\n\n\ndef run():\n    return pkg.sub.deep.g()\n",
    "app/alias.py": "import pkg.mod as m\n\n\ndef run():\n    return m.f()\n",
    "app/plain.py": "from pkg import mod\n\n\nclass K:\n    def f(self):\n        return 1\n\n    def run(self, obj):\n"
                    "        self.f()\n        obj.f()\n        return other.f()\n",
}
# (file, label, start line)
DEFS = [("pkg/mod.py", "f()", 1), ("pkg/sub/deep.py", "g()", 1), ("app/method.py", ".run()", 5),
        ("app/top.py", "run()", 4), ("app/deep.py", "run()", 4), ("app/alias.py", "run()", 4),
        ("app/plain.py", ".f()", 5), ("app/plain.py", ".run()", 8)]


def build():
    """A root holding SOURCES and a code dict with a module node and the definitions in DEFS."""
    root = tempfile.mkdtemp(prefix="carto-calls-")
    for rel, text in SOURCES.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    nodes, ids = [], {}
    for rel in SOURCES:
        if rel.endswith("__init__.py"):
            continue
        nodes.append({"id": "m:" + rel, "label": os.path.basename(rel), "file_type": "code", "source_file": rel})
    for rel, label, line in DEFS:
        ids[(rel, label)] = f"{rel}:{label}"
        nodes.append({"id": ids[(rel, label)], "label": label, "file_type": "code", "source_file": rel,
                      "source_location": f"L{line}", "_callable": True})
    return root, {"nodes": nodes, "links": []}, ids


def calls(code, source, target):
    return [x for x in code["links"] if x["source"] == source and x["target"] == target and x["relation"] == "calls"]


class ModuleCallsTest(unittest.TestCase):
    def setUp(self):
        self.root, self.code, self.ids = build()
        self.files = sorted(SOURCES)

    def run_pass(self):
        return cg.resolve_module_calls(self.root, self.files, self.code)

    def test_call_inside_a_method(self):
        self.run_pass()
        found = calls(self.code, self.ids[("app/method.py", ".run()")], self.ids[("pkg/mod.py", "f()")])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["source_location"], "L6")
        self.assertEqual(found[0]["confidence"], "EXTRACTED")
        self.assertEqual(found[0]["_origin"], "cartographer")

    def test_call_in_a_top_level_function(self):
        self.run_pass()
        self.assertEqual(len(calls(self.code, self.ids[("app/top.py", "run()")], self.ids[("pkg/mod.py", "f()")])), 1)

    def test_dotted_package_import(self):
        self.run_pass()
        self.assertEqual(len(calls(self.code, self.ids[("app/deep.py", "run()")], self.ids[("pkg/sub/deep.py", "g()")])), 1)

    def test_aliased_import(self):
        self.run_pass()
        self.assertEqual(len(calls(self.code, self.ids[("app/alias.py", "run()")], self.ids[("pkg/mod.py", "f()")])), 1)

    def test_indirect_call_does_not_stop_a_calls_link(self):
        source, target = self.ids[("app/top.py", "run()")], self.ids[("pkg/mod.py", "f()")]
        self.code["links"].append({"source": source, "target": target, "relation": "indirect_call"})
        self.run_pass()
        self.assertEqual(len(calls(self.code, source, target)), 1)

    def test_existing_calls_link_is_not_doubled(self):
        source, target = self.ids[("app/top.py", "run()")], self.ids[("pkg/mod.py", "f()")]
        self.code["links"].append({"source": source, "target": target, "relation": "calls"})
        self.run_pass()
        self.assertEqual(len(calls(self.code, source, target)), 1)

    def test_self_and_unimported_names_add_nothing(self):
        self.run_pass()
        plain = {self.ids[("app/plain.py", ".f()")], self.ids[("app/plain.py", ".run()")]}
        self.assertEqual([x for x in self.code["links"] if x["source"] in plain], [])

    def test_second_run_adds_nothing(self):
        first = self.run_pass()
        self.assertEqual(first, 4)
        count = len(self.code["links"])
        self.assertEqual(self.run_pass(), 0)
        self.assertEqual(len(self.code["links"]), count)


if __name__ == "__main__":
    unittest.main()
