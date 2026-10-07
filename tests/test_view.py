"""Where graph_view.py draws code and what it calls a cluster, on a made-up graph.

    python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import graph_view as gv  # noqa: E402


def code(node_id, source_file, community, kind="function"):
    return {"id": node_id, "label": node_id, "kind": kind, "source_file": source_file, "layer": "code",
            "code_community": community, "asset_kind": "system description"}


def link(source, target, relation="calls"):
    return {"source": source, "target": target, "relation": relation, "confidence": "EXTRACTED"}


def graph():
    """Community 1: six definitions in kernel/store.py, six tests of it, and one helper in
    kernel/ids.py that everything calls. Community 2: seven definitions over three kernel
    files, none holding half. Community 3: two definitions in app/, linked to nothing."""
    nodes = [code(f"store{i}", "kernel/store.py", 1) for i in range(6)]
    nodes += [code(f"test{i}", "tests/test_store.py", 1) for i in range(6)]
    nodes += [code("now", "kernel/ids.py", 1)]
    nodes += [code(f"a{i}", "kernel/ops/alpha.py", 2) for i in range(3)]
    nodes += [code(f"b{i}", "kernel/ops/beta.py", 2) for i in range(3)] + [code("g0", "kernel/ops/gamma.py", 2)]
    nodes += [code("lone0", "app/lone.py", 3), code("lone1", "app/lone.py", 3)]
    links = [link(f"test{i}", f"store{i}") for i in range(6)] + [link(f"test{i}", "now") for i in range(6)]
    links += [link(f"store{i}", "now") for i in range(6)] + [link("a0", "now"), link("a1", "b0")]
    return {"graph": {"claims": {"code-1": [{"id": "c1", "verdict": "confirmed", "state": "judged"}]}},
            "nodes": nodes, "links": links}


class Clusters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = gv.build_view(graph(), [], [])
        cls.planes = [p["name"] for p in cls.view["planes"]]
        cls.where = {}
        for c in cls.view["clusters"]:
            for i in range(c["start"], c["start"] + c["count"]):
                cls.where[cls.view["nodes"][i][3]] = c

    def plane(self, label):
        return self.planes[self.where[label]["plane"]]

    def test_a_community_on_two_planes_is_two_clusters(self):
        self.assertEqual((self.plane("store0"), self.plane("test0")), ("kernel", "tests"))
        self.assertIsNot(self.where["store0"], self.where["test0"])

    def test_nothing_is_drawn_on_a_plane_that_is_not_its_own(self):
        for label, c in self.where.items():
            file = next(n[5] for n in self.view["nodes"] if n[3] == label)
            self.assertEqual(self.planes[c["plane"]], file.split("/")[0], label)

    def test_a_cluster_in_one_file_is_named_for_it(self):
        self.assertEqual(self.where["test0"]["name"], "tests: test_store.py")

    def test_a_cluster_is_named_for_the_file_holding_half_not_its_busiest_member(self):
        # `now` is the most connected member and sits in ids.py; six of the seven are in store.py
        self.assertIs(self.where["now"], self.where["store0"])
        self.assertEqual(self.where["store0"]["name"], "kernel: store.py +1 file")

    def test_a_cluster_with_no_such_file_is_named_for_its_two_largest(self):
        self.assertEqual(self.where["a0"]["name"], "kernel/ops: alpha.py, beta.py +1 file")

    def test_a_small_part_joins_the_cluster_on_its_plane_it_is_linked_to_most(self):
        before, gv.SMALL_PART = gv.SMALL_PART, 8
        try:
            view = gv.build_view(graph(), [], [])
        finally:
            gv.SMALL_PART = before
        names = sorted(c["name"] for c in view["clusters"])
        # seven in community 1 on kernel and seven in community 2 are both under eight: neither can take the other in
        self.assertEqual(names, ["app: other code", "kernel: other code", "tests: other code"])

    def test_a_small_part_linked_to_a_cluster_on_its_plane_joins_it(self):
        g = graph()
        g["nodes"].append(code("stray", "kernel/stray.py", 9))
        g["links"].append(link("stray", "a0"))
        view = gv.build_view(g, [], [])
        holder = next(c for c in view["clusters"] if any(view["nodes"][i][3] == "stray" for i in range(c["start"], c["start"] + c["count"])))
        self.assertEqual(holder["name"], "kernel/ops: alpha.py, beta.py +2 files")

    def test_a_small_part_linked_to_nothing_goes_to_its_plane_s_leftovers(self):
        self.assertEqual(self.where["lone0"]["name"], "app: other code")

    def test_a_small_part_never_joins_a_cluster_on_another_plane(self):
        g = graph()
        g["links"] += [link("lone0", "store0"), link("lone1", "store1")]
        view = gv.build_view(g, [], [])
        self.assertIn("app: other code", [c["name"] for c in view["clusters"]])
        self.assertEqual(next(c["count"] for c in view["clusters"] if c["name"] == "kernel: store.py +1 file"), 7)

    def test_a_claim_is_shown_once_on_the_part_holding_the_busiest_member(self):
        holders = [c["name"] for c in self.view["clusters"] if c["claims"]]
        self.assertEqual(holders, ["kernel: store.py +1 file"])
        self.assertEqual(self.where["now"]["claims"], ["c1 confirmed"])
        # with more tests than kernel code the tests part is the larger one; the claim stays with `now`
        g = graph()
        g["nodes"] += [code(f"more{i}", "tests/test_store.py", 1) for i in range(4)]
        view = gv.build_view(g, [], [])
        self.assertEqual([c["name"] for c in view["clusters"] if c["claims"]], ["kernel: store.py +1 file"])

    def test_a_long_folder_is_cut_to_its_last_parts(self):
        rows = [code(f"d{i}", "ext/mods/seats/plugin/types/code/index.d.ts", 4) for i in range(5)]
        self.assertEqual(gv.cluster_name("code-4@ext", rows), "plugin/types/code: index.d.ts")


if __name__ == "__main__":
    unittest.main()
