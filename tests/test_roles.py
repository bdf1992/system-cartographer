"""Whose code a node is, and which file a test file is about, on a made-up root.

    python -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import graph_export as ge  # noqa: E402
import graph_query as gq  # noqa: E402
import graph_view as gv  # noqa: E402

FILES = ["kernel/store.py", "kernel/ops/store.py", "kernel/ids.py", "kernel/dup.py", "other/dup.py", "tests/dup.py",
         "tests/test_store.py", "tests/test_ids.py", "tests/test_dup.py", "tests/test_nothing.py", "tests/helpers.py",
         "web/src/panel.tsx", "web/src/panel.test.tsx", "web/src/client.spec.ts", "kernel/client.py",
         "web/types/lib.d.ts", "web/out/bundle.js", "vendor/pkg/test_thing.py", "tools/build_test.py", "tools/build.py",
         "web/src/widget.ts", "web/src/widget.test.tsx", "web/src/shared.ts", "web/lib/shared.ts", "web/src/shared.test.ts",
         "kernel/twin.py", "other/twin.py", "tests/test_twin.py"]
CALLS = [("tests/test_store.py", "kernel/ops/store.py"), ("tests/test_ids.py", "kernel/store.py"),
         ("web/src/panel.test.tsx", "web/src/panel.tsx"), ("web/src/widget.test.tsx", "web/src/widget.ts"),
         ("tests/test_twin.py", "kernel/twin.py"), ("tests/test_twin.py", "other/twin.py")]


def build():
    """A scan of FILES and a code graph giving each one function; CALLS are calls between those functions."""
    root, code_dir = tempfile.mkdtemp(prefix="carto-roles-"), tempfile.mkdtemp(prefix="carto-roles-code-")
    generated = {"web/out/bundle.js"}
    scan = {"code-scripts": {"root": root, "edges": [], "findings": [], "nodes": [
        {"id": rel, "source_class": "generated" if rel in generated else "source"} for rel in FILES]}}
    nodes, links = [], []
    for i, rel in enumerate(FILES):
        nodes.append({"id": f"m{i}", "label": os.path.basename(rel), "file_type": "code", "source_file": rel, "community": i})
        nodes.append({"id": f"f{i}", "label": f"fn{i}()", "file_type": "code", "source_file": rel, "community": i,
                      "_callable": True})
        links.append({"source": f"m{i}", "target": f"f{i}", "relation": "contains", "confidence": "EXTRACTED"})
    for a, b in CALLS:
        links.append({"source": f"f{FILES.index(a)}", "target": f"f{FILES.index(b)}", "relation": "calls", "confidence": "EXTRACTED"})
    with open(os.path.join(code_dir, "code-graph.json"), "w", encoding="utf-8") as handle:
        json.dump({"nodes": nodes, "links": links}, handle)
    return ge.build_graph(scan, {}, code_dir=code_dir)


class Roles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build()
        cls.node = {n["id"]: n for n in cls.graph["nodes"]}
        cls.tests = {l["source"]: l for l in cls.graph["links"] if l["relation"] == "tests"}

    def role(self, rel):
        return self.node[rel]["role"]

    def test_a_file_and_its_definitions_have_one_role(self):
        self.assertEqual(self.role("kernel/store.py"), "own")
        self.assertEqual({n["role"] for n in self.graph["nodes"] if n["source_file"] == "tests/test_store.py"}, {"test"})

    def test_tests_are_known_by_folder_and_by_name(self):
        for rel in ("tests/test_store.py", "tests/helpers.py", "web/src/panel.test.tsx", "web/src/client.spec.ts", "tools/build_test.py"):
            self.assertEqual(self.role(rel), "test", rel)

    def test_declarations_generated_and_vendored_files_are_not_written_here(self):
        for rel in ("web/types/lib.d.ts", "web/out/bundle.js", "vendor/pkg/test_thing.py"):    # the last is a vendored test
            self.assertEqual(self.role(rel), "not written here", rel)

    def test_what_is_not_code_has_no_role(self):
        scan = {"asset-records": {"root": tempfile.mkdtemp(), "edges": [], "findings": [],
                                  "nodes": [{"id": "tasks/t.json", "source_class": "configuration"}]}}
        graph = ge.build_graph(scan, {}, asset_kinds={"asset-records": "records"})
        self.assertNotIn("role", graph["nodes"][0])

    def test_the_query_index_reads_the_same_rule(self):
        index = gq.build_index(self.graph)
        flags = {row["file"]: (row["test"], row["own"]) for row in index["nodes"]}
        self.assertEqual(flags["tests/test_store.py"], (True, True))
        self.assertEqual(flags["vendor/pkg/test_thing.py"], (True, False))
        self.assertEqual(flags["web/out/bundle.js"], (False, False))
        self.assertEqual(flags["kernel/store.py"], (False, True))

    def subject(self, rel):
        row = self.tests.get(rel)
        return row and (row["target"], row["confidence"])

    def test_a_test_is_about_the_file_of_that_name_it_links_to(self):
        # two files are named store.py; the test calls into kernel/ops/store.py
        self.assertEqual(self.subject("tests/test_store.py"), ("kernel/ops/store.py", "EXTRACTED"))
        self.assertEqual(self.node["tests/test_store.py"]["tests"], "kernel/ops/store.py")

    def test_a_name_match_the_test_does_not_link_to_is_inferred(self):
        self.assertEqual(self.subject("tests/test_ids.py"), ("kernel/ids.py", "INFERRED"))    # it calls store.py, not ids.py
        self.assertEqual(self.subject("tools/build_test.py"), ("tools/build.py", "INFERRED"))

    def test_the_suffix_forms_are_read(self):
        self.assertEqual(self.subject("web/src/panel.test.tsx"), ("web/src/panel.tsx", "EXTRACTED"))

    def test_a_name_two_files_have_and_nothing_settles_is_about_none(self):
        self.assertIsNone(self.subject("tests/test_dup.py"))    # kernel/dup.py and other/dup.py; tests/dup.py is a test
        self.assertNotIn("tests", self.node["tests/test_dup.py"])

    def test_the_subject_is_in_the_test_s_language(self):
        self.assertIsNone(self.subject("web/src/client.spec.ts"))    # kernel/client.py is Python
        self.assertEqual(self.subject("web/src/widget.test.tsx"), ("web/src/widget.ts", "EXTRACTED"))    # .tsx tests .ts

    def test_among_files_of_one_name_the_one_in_the_test_s_folder_is_taken(self):
        self.assertEqual(self.subject("web/src/shared.test.ts"), ("web/src/shared.ts", "INFERRED"))

    def test_a_test_linking_to_two_files_of_the_name_is_about_none(self):
        self.assertIsNone(self.subject("tests/test_twin.py"))

    def test_a_test_naming_no_file_and_a_helper_are_about_none(self):
        self.assertIsNone(self.subject("tests/test_nothing.py"))
        self.assertIsNone(self.subject("tests/helpers.py"))

    def test_a_vendored_test_is_not_joined(self):
        self.assertIsNone(self.subject("vendor/pkg/test_thing.py"))

    def test_the_counts_reach_the_report(self):
        self.assertEqual(self.graph["graph"]["tests"], {"test_files": 12, "with_subject": 6, "linked_too": 3})
        report = ge.render_report(self.graph, "fixture")
        self.assertIn("6 of 12 test files are joined by name", report)
        self.assertIn("6 are in files it holds but did not write", report)


class RolePlanes(unittest.TestCase):
    def test_tests_and_code_not_written_here_have_planes_after_the_rest_of_the_code(self):
        view = gv.build_view(build(), [], [])
        planes = [p["name"] for p in view["planes"]]
        self.assertEqual(planes, ["kernel", "other", "tools", "web", "tests", "code not written here"])
        where = {view["nodes"][i][5]: planes[c["plane"]] for c in view["clusters"] for i in range(c["start"], c["start"] + c["count"])}
        self.assertEqual(where["web/src/panel.test.tsx"], "tests")
        self.assertEqual(where["tools/build_test.py"], "tests")
        self.assertEqual(where["web/types/lib.d.ts"], "code not written here")
        self.assertEqual(where["vendor/pkg/test_thing.py"], "code not written here")
        self.assertEqual(where["web/src/panel.tsx"], "web")

    def test_a_declared_layer_does_not_take_a_test(self):
        registrations = [{"selector": "web/*", "layer": "front"}, {"selector": "tools/*", "layer": "front"}]
        view = gv.build_view(build(), ["front"], registrations)
        planes = [p["name"] for p in view["planes"]]
        where = {view["nodes"][i][5]: planes[c["plane"]] for c in view["clusters"] for i in range(c["start"], c["start"] + c["count"])}
        self.assertEqual((where["web/src/panel.tsx"], where["web/src/panel.test.tsx"], where["tools/build_test.py"]),
                         ("front", "tests", "tests"))


if __name__ == "__main__":
    unittest.main()
