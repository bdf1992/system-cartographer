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

OWN = ["kernel/store.py", "kernel/ops/store.py", "kernel/ids.py", "kernel/dup.py", "other/dup.py", "kernel/client.py",
       "kernel/twin.py", "other/twin.py", "kernel/most.py", "other/most.py", "kernel/pack/__init__.py",
       "kernel/pack/inner.py", "kernel/cmd/pack.py", "kernel/cmd/observer.py", "tools/build.py", "tools/cli.py",
       "tools/lonely.py", "web/src/panel.tsx", "web/src/widget.ts", "web/src/shared.ts", "web/lib/shared.ts",
       "web/src/menu.ts", "web/src/loader.mjs"]
TESTS = ["tests/dup.py", "tests/test_store.py", "tests/test_ids.py", "tests/test_dup.py", "tests/test_nothing.py",
         "tests/helpers.py", "tests/test_twin.py", "tests/test_most.py", "tests/test_pack.py", "tests/test_cmd_observer.py",
         "tests/test_cli.py", "tests/test_lonely.py", "tools/build_test.py", "web/src/panel.test.tsx",
         "web/src/widget.test.tsx", "web/src/shared.test.ts", "web/src/client.spec.ts", "web/src/menu.spec.ts",
         "web/src/loader.test.cjs", "web/__tests__/thing.js", "lib/spec/helper.rb"]
NOT_HERE = ["web/types/lib.d.ts", "web/out/bundle.js", "vendor/pkg/test_thing.py", "web/node_modules/p/i.js",
            "web/dist/app.js", "third_party/z/z.py", "gen/generated/q.py"]
FILES = OWN + TESTS + NOT_HERE
# (test file, file it links into, how many links)
LINKS = [("tests/test_store.py", "kernel/ops/store.py", 1), ("tests/test_ids.py", "kernel/store.py", 1),
         ("web/src/panel.test.tsx", "web/src/panel.tsx", 1), ("web/src/widget.test.tsx", "web/src/widget.ts", 1),
         ("tests/test_twin.py", "kernel/twin.py", 1), ("tests/test_twin.py", "other/twin.py", 1),
         ("tests/test_most.py", "kernel/most.py", 1), ("tests/test_most.py", "other/most.py", 2),
         ("tests/test_pack.py", "kernel/pack/inner.py", 2), ("tests/test_pack.py", "kernel/cmd/pack.py", 1),
         ("tests/test_cmd_observer.py", "kernel/cmd/observer.py", 1), ("tests/test_lonely.py", "kernel/ids.py", 1)]
RELATIONS = ["calls", "uses", "references"]


def build():
    """A scan of FILES and a code graph giving each one function; LINKS are links between those functions."""
    root, code_dir = tempfile.mkdtemp(prefix="carto-roles-"), tempfile.mkdtemp(prefix="carto-roles-code-")
    scan = {"code-scripts": {"root": root, "edges": [], "findings": [], "nodes": [
        {"id": rel, "source_class": "generated" if rel == "web/out/bundle.js" else "source"} for rel in FILES]}}
    nodes, links = [], []
    for i, rel in enumerate(FILES):
        nodes.append({"id": f"m{i}", "label": os.path.basename(rel), "file_type": "code", "source_file": rel, "community": i})
        nodes.append({"id": f"f{i}", "label": f"fn{i}()", "file_type": "code", "source_file": rel, "community": i,
                      "_callable": True})
        links.append({"source": f"m{i}", "target": f"f{i}", "relation": "contains", "confidence": "EXTRACTED"})
    for a, b, count in LINKS:
        for relation in RELATIONS[:count]:
            links.append({"source": f"f{FILES.index(a)}", "target": f"f{FILES.index(b)}", "relation": relation,
                          "confidence": "EXTRACTED"})
    with open(os.path.join(code_dir, "code-graph.json"), "w", encoding="utf-8") as handle:
        json.dump({"nodes": nodes, "links": links}, handle)
    return ge.build_graph(scan, {}, code_dir=code_dir)


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build()
        cls.node = {n["id"]: n for n in cls.graph["nodes"]}
        cls.tests = {l["source"]: l for l in cls.graph["links"] if l["relation"] == "tests"}

    def subject(self, rel):
        row = self.tests.get(rel)
        return row and (row["target"], row["confidence"])


class Roles(Built):
    def test_a_file_and_its_definitions_have_one_role(self):
        self.assertEqual({n["role"] for n in self.graph["nodes"] if n["source_file"] == "kernel/store.py"}, {"own"})
        self.assertEqual({n["role"] for n in self.graph["nodes"] if n["source_file"] == "tests/test_store.py"}, {"test"})

    def test_tests_are_known_by_folder_and_by_name(self):
        for rel in TESTS:
            self.assertEqual(self.node[rel]["role"], "test", rel)

    def test_declarations_generated_and_vendored_files_are_not_written_here(self):
        for rel in NOT_HERE:    # vendor/pkg/test_thing.py is a vendored test: still not written here
            self.assertEqual(self.node[rel]["role"], "not written here", rel)

    def test_the_rest_is_the_target_s_own(self):
        for rel in OWN:
            self.assertEqual(self.node[rel]["role"], "own", rel)

    def test_what_is_not_code_has_no_role(self):
        scan = {"asset-records": {"root": tempfile.mkdtemp(), "edges": [], "findings": [],
                                  "nodes": [{"id": "tasks/t.json", "source_class": "configuration"}]}}
        graph = ge.build_graph(scan, {}, asset_kinds={"asset-records": "records"})
        self.assertNotIn("role", graph["nodes"][0])

    def test_the_query_index_reads_the_same_rule_and_does_not_follow_a_join(self):
        index = gq.build_index(self.graph)
        flags = {row["file"]: (row["test"], row["own"]) for row in index["nodes"]}
        self.assertEqual(flags["tests/test_store.py"], (True, True))
        self.assertEqual(flags["vendor/pkg/test_thing.py"], (True, False))
        self.assertEqual(flags["web/out/bundle.js"], (False, False))
        self.assertEqual(flags["kernel/store.py"], (False, True))
        self.assertNotIn("tests", index["relations"])    # a join by name is not something the test depends on


class Subjects(Built):
    def test_among_files_of_a_name_it_is_about_the_one_it_links_into(self):
        self.assertEqual(self.subject("tests/test_store.py"), ("kernel/ops/store.py", "EXTRACTED"))
        self.assertEqual(self.node["tests/test_store.py"]["tests"], "kernel/ops/store.py")

    def test_it_is_about_the_one_it_links_into_most(self):
        self.assertEqual(self.subject("tests/test_most.py"), ("other/most.py", "EXTRACTED"))

    def test_linking_equally_into_two_it_is_about_none(self):
        self.assertIsNone(self.subject("tests/test_twin.py"))

    def test_a_package_counts_every_link_into_its_folder(self):
        # two links into kernel/pack/inner.py against one into kernel/cmd/pack.py
        self.assertEqual(self.subject("tests/test_pack.py"), ("kernel/pack/__init__.py", "EXTRACTED"))

    def test_a_name_may_run_a_folder_and_a_file_together(self):
        self.assertEqual(self.subject("tests/test_cmd_observer.py"), ("kernel/cmd/observer.py", "EXTRACTED"))

    def test_a_name_it_does_not_link_into_is_not_its_subject_when_it_links_elsewhere(self):
        self.assertIsNone(self.subject("tests/test_ids.py"))       # it links into store.py, not ids.py
        self.assertIsNone(self.subject("tests/test_lonely.py"))    # tools/lonely.py is the only candidate; it links into ids.py
        self.assertNotIn("tests", self.node["tests/test_ids.py"])

    def test_a_test_linking_into_none_of_the_target_s_code_takes_a_lone_name(self):
        self.assertEqual(self.subject("tests/test_cli.py"), ("tools/cli.py", "INFERRED"))
        self.assertEqual(self.tests["tests/test_cli.py"]["confidence_score"], 0.65)
        self.assertIsNone(self.subject("tests/test_dup.py"))    # two candidates and nothing to choose by

    def test_a_file_beside_the_test_is_taken_by_name(self):
        self.assertEqual(self.subject("tools/build_test.py"), ("tools/build.py", "INFERRED"))
        self.assertEqual(self.subject("web/src/shared.test.ts"), ("web/src/shared.ts", "INFERRED"))    # not web/lib/shared.ts
        self.assertEqual(self.subject("web/src/menu.spec.ts"), ("web/src/menu.ts", "INFERRED"))

    def test_the_subject_is_in_the_test_s_language(self):
        self.assertIsNone(self.subject("web/src/client.spec.ts"))    # kernel/client.py is Python
        self.assertEqual(self.subject("web/src/widget.test.tsx"), ("web/src/widget.ts", "EXTRACTED"))
        self.assertEqual(self.subject("web/src/loader.test.cjs"), ("web/src/loader.mjs", "INFERRED"))

    def test_a_test_naming_no_file_a_helper_and_a_vendored_test_are_about_none(self):
        for rel in ("tests/test_nothing.py", "tests/helpers.py", "tests/dup.py", "vendor/pkg/test_thing.py"):
            self.assertIsNone(self.subject(rel), rel)

    def test_the_counts_reach_the_report(self):
        self.assertEqual(self.graph["graph"]["tests"], {"test_files": 21, "with_subject": 11, "linked_too": 6})
        report = ge.render_report(self.graph, "fixture")
        self.assertIn("11 of 21 test files are joined by name", report)
        self.assertIn("14 are in files it holds but did not write", report)


class RolePlanes(unittest.TestCase):
    def see(self, layers=(), registrations=()):
        view = gv.build_view(build(), list(layers), list(registrations))
        self.planes = [p["name"] for p in view["planes"]]
        self.where = {view["nodes"][i][5]: self.planes[c["plane"]] for c in view["clusters"]
                      for i in range(c["start"], c["start"] + c["count"])}
        return view

    def test_tests_and_code_not_written_here_have_planes_after_the_rest_of_the_code(self):
        self.see()
        self.assertEqual(self.planes, ["kernel", "other", "tools", "web", "tests", "code not written here"])
        for rel in ("web/src/panel.test.tsx", "tools/build_test.py", "lib/spec/helper.rb"):
            self.assertEqual(self.where[rel], "tests", rel)
        for rel in ("web/types/lib.d.ts", "vendor/pkg/test_thing.py"):
            self.assertEqual(self.where[rel], "code not written here", rel)
        self.assertEqual(self.where["web/src/panel.tsx"], "web")

    def test_a_declared_layer_does_not_take_a_test(self):
        self.see(["front"], [{"selector": "web/*", "layer": "front"}, {"selector": "tools/*", "layer": "front"}])
        self.assertEqual((self.where["web/src/panel.tsx"], self.where["web/src/panel.test.tsx"], self.where["tools/build_test.py"]),
                         ("front", "tests", "tests"))

    def test_a_join_is_drawn_as_a_use(self):
        view = self.see()
        index = {(row[5], row[4]): i for i, row in enumerate(view["nodes"])}
        a, b = index[("tests/test_cli.py", "file")], index[("tools/cli.py", "file")]
        edge = next(e for e in view["edges"] if (e[0], e[1]) == (a, b))
        self.assertEqual((view["kinds"][edge[2]], edge[3]), ("uses", 1))


if __name__ == "__main__":
    unittest.main()
