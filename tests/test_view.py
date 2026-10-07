"""Where graph_view.py draws code and what it calls a cluster, on made-up graphs.

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


def graph(extra_nodes=(), extra_links=(), claims=None):
    """Community 1: six definitions in kernel/store.py, six tests of it, and one helper in
    kernel/ids.py that everything calls. Community 2: seven definitions over three files in
    kernel/ops, none holding half. Community 3: two definitions in app/, linked to nothing."""
    nodes = [code(f"store{i}", "kernel/store.py", 1) for i in range(6)]
    nodes += [code(f"test{i}", "tests/test_store.py", 1) for i in range(6)]
    nodes += [code("now", "kernel/ids.py", 1)]
    nodes += [code(f"a{i}", "kernel/ops/alpha.py", 2) for i in range(3)]
    nodes += [code(f"b{i}", "kernel/ops/beta.py", 2) for i in range(3)] + [code("g0", "kernel/ops/gamma.py", 2)]
    nodes += [code("lone0", "app/lone.py", 3), code("lone1", "app/lone.py", 3)]
    links = [link(f"test{i}", f"store{i}") for i in range(6)] + [link(f"test{i}", "now") for i in range(6)]
    links += [link(f"store{i}", "now") for i in range(6)] + [link("a0", "now"), link("a1", "b0")]
    claims = claims or {"code-1": [{"id": "c1", "verdict": "confirmed", "state": "judged"}]}
    return {"graph": {"claims": claims}, "nodes": nodes + list(extra_nodes), "links": links + list(extra_links)}


STORE, OPS = "kernel: store.py +1 file", "kernel/ops: alpha.py, beta.py +1 file"


class View(unittest.TestCase):
    def see(self, *args, **kwargs):
        view = gv.build_view(graph(*args, **kwargs), [], [])
        self.planes = [p["name"] for p in view["planes"]]
        self.where = {view["nodes"][i][3]: c for c in view["clusters"] for i in range(c["start"], c["start"] + c["count"])}
        return view

    def home(self, label):
        return self.where[label]["name"]


class Planes(View):
    def test_a_community_on_two_planes_is_two_clusters(self):
        self.see()
        self.assertEqual((self.planes[self.where["store0"]["plane"]], self.planes[self.where["test0"]["plane"]]),
                         ("kernel", "tests"))
        self.assertEqual((self.where["store0"]["community"], self.where["test0"]["community"]), ("code-1", "code-1"))

    def test_nothing_is_drawn_on_a_plane_that_is_not_its_own(self):
        view = self.see()
        for row in view["nodes"]:
            self.assertEqual(self.planes[self.where[row[3]]["plane"]], row[5].split("/")[0], row[3])


class DeclaredLayers(unittest.TestCase):
    CORE = [{"selector": "kernel/store.py", "layer": "core"}]

    def see(self, registrations, extra=()):
        view = gv.build_view(graph(extra), ["core"], registrations)
        self.planes = [p["name"] for p in view["planes"]]
        self.where = {row[5]: self.planes[c["plane"]] for c in view["clusters"]
                      for row in view["nodes"][c["start"]: c["start"] + c["count"]]}
        return view

    def test_code_a_declaration_covers_but_does_not_place_says_so(self):
        view = self.see(self.CORE)
        self.assertEqual(self.where["kernel/store.py"], "core")
        for rel in ("kernel/ids.py", "kernel/ops/alpha.py"):
            self.assertEqual(self.where[rel], "kernel (no declared layer)", rel)
        self.assertEqual(view["unplaced"], {})    # the made-up graph has definitions and no file nodes

    def test_a_folder_the_declaration_does_not_speak_for_keeps_its_name(self):
        self.see(self.CORE)
        self.assertEqual((self.where["app/lone.py"], self.where["tests/test_store.py"]), ("app", "tests"))

    def test_what_was_left_out_comes_straight_after_the_layers(self):
        self.see(self.CORE)
        self.assertEqual(self.planes, ["core", "kernel (no declared layer)", "app", "tests"])

    def test_the_files_left_out_are_counted(self):
        files = [code("kernel/ids.py", "kernel/ids.py", 1, kind="file"), code("kernel/ops/alpha.py", "kernel/ops/alpha.py", 2, kind="file"),
                 code("kernel/store.py", "kernel/store.py", 1, kind="file"), code("app/lone.py", "app/lone.py", 3, kind="file")]
        self.assertEqual(self.see(self.CORE, files)["unplaced"], {"kernel (no declared layer)": 2})

    def test_with_no_declaration_nothing_is_marked(self):
        view = self.see([])
        self.assertEqual(self.planes, ["app", "kernel", "tests"])
        self.assertEqual(view["unplaced"], {})

    def test_a_declaration_that_places_everything_marks_nothing(self):
        self.see([{"selector": "kernel/*", "layer": "core"}])
        self.assertEqual(self.planes, ["core", "app", "tests"])


class SmallParts(View):
    def test_a_part_of_five_stands_and_a_part_of_four_does_not(self):
        five = [code(f"f{i}", "kernel/five.py", 7) for i in range(5)]
        four = [code(f"q{i}", "kernel/four.py", 8) for i in range(4)]
        self.see(five + four, [link("f0", "a0"), link("q0", "a0")])
        self.assertEqual(self.home("f0"), "kernel: five.py")
        self.assertIs(self.where["q0"], self.where["a0"])
        self.assertEqual(self.home("q0"), "kernel: four.py, ops/alpha.py +2 files")

    def test_it_joins_the_cluster_it_is_linked_to_most(self):
        self.see([code("stray", "kernel/stray.py", 9)], [link("stray", "a0"), link("stray", "store0"), link("store1", "stray")])
        self.assertEqual(self.home("stray"), "kernel: store.py +2 files")

    def test_among_equals_it_joins_the_one_holding_a_file_of_its_own(self):
        self.see([code("stray", "kernel/ops/gamma.py", 9)], [link("stray", "store0"), link("stray", "a0")])
        self.assertEqual(self.where["stray"], self.where["a0"])
        self.see([code("stray", "kernel/ids.py", 9)], [link("stray", "store0"), link("stray", "a0")])
        self.assertEqual(self.where["stray"], self.where["store0"])

    def test_it_never_joins_a_cluster_on_another_plane(self):
        self.see((), [link("lone0", "store0"), link("lone1", "store1")])
        self.assertEqual(self.home("lone0"), "app: other code")
        self.assertEqual(self.where["store0"]["count"], 7)

    def test_one_tied_to_itself_as_much_as_to_a_neighbour_joins_and_one_tied_more_stands(self):
        pair = [code("p0", "kernel/pair.py", 9), code("p1", "kernel/pair.py", 9)]
        self.see(pair, [link("p0", "p1"), link("p0", "a0")])
        self.assertEqual(self.where["p0"], self.where["a0"])
        self.see(pair, [link("p0", "p1"), link("p1", "p0", "uses"), link("p0", "a0")])
        self.assertEqual(self.home("p0"), "kernel: pair.py")
        self.assertEqual(self.where["p0"]["count"], 2)

    def test_one_linked_only_inside_itself_stands(self):
        self.see([code("p0", "kernel/pair.py", 9), code("p1", "kernel/pair.py", 9)], [link("p0", "p1")])
        self.assertEqual(self.home("p0"), "kernel: pair.py")

    def test_one_linked_to_nothing_goes_to_its_plane_s_leftovers(self):
        self.see()
        self.assertEqual(self.home("lone0"), "app: other code")
        self.assertIsNone(self.where["lone0"]["community"])


class Names(View):
    def name(self, *counts):
        rows = [code(f"{file}{i}", file, 4) for file, count in counts for i in range(count)]
        return gv.cluster_name("code-4@kernel", rows)

    def test_one_file_names_the_cluster_when_it_holds_half(self):
        self.assertEqual(self.name(("kernel/a.py", 4), ("kernel/b.py", 3), ("kernel/c.py", 1)), "kernel: a.py +2 files")
        self.assertEqual(self.name(("kernel/a.py", 3), ("kernel/b.py", 3), ("kernel/c.py", 1)), "kernel: a.py, b.py +1 file")
        self.assertEqual(self.name(("kernel/a.py", 5)), "kernel: a.py")

    def test_it_is_named_for_its_files_not_its_busiest_member(self):
        self.see()
        self.assertIs(self.where["now"], self.where["store0"])    # `now` is the most connected and sits in ids.py
        self.assertEqual(self.home("now"), STORE)
        self.assertEqual(self.home("a0"), OPS)

    def test_a_file_from_another_folder_is_said_with_its_folder(self):
        self.assertEqual(self.name(("kernel/ops/a.py", 3), ("scripts/run.py", 3), ("kernel/ops/c.py", 1)),
                         "kernel/ops: a.py, scripts/run.py +1 file")

    def test_a_long_folder_keeps_its_last_three_parts(self):
        self.assertEqual(self.name(("ext/mods/seats/plugin/types/code/index.d.ts", 5)), "plugin/types/code: index.d.ts")

    def test_files_holding_under_a_quarter_are_not_the_name(self):
        many = [(f"kernel/bag/f{i}.py", 1) for i in range(9)]
        self.assertEqual(self.name(*many), "kernel/bag: 9 files, largest f0.py")
        self.assertEqual(self.name(*many[:8]), "kernel/bag: f0.py, f1.py +6 files")    # two of eight is a quarter

    def test_a_name_too_long_keeps_its_count(self):
        name = self.name(("kernel/" + "a" * 60 + ".py", 3), ("kernel/" + "b" * 60 + ".py", 3), ("kernel/c.py", 1))
        self.assertEqual(len(name), 72)
        self.assertEqual(self.name(("kernel/" + "a" * 60 + ".py", 5)), "kernel: " + "a" * 60 + ".py")    # 71: whole
        self.assertTrue(name.startswith("kernel: aaaa") and name.endswith("… +1 file"), name)

    def test_two_clusters_of_one_name_on_a_plane_are_told_apart(self):
        twin = [code(f"t{i}", "kernel/store.py", 5) for i in range(5)] + [code("tx", "kernel/ids.py", 5)]
        view = self.see(twin, [link(f"t{i}", "t0") for i in range(1, 5)])
        self.assertEqual(self.home("store0"), STORE + " (now)")
        self.assertEqual(self.home("t1"), STORE + " (t0)")
        # a file node that is the busiest member would only repeat the name: the busiest definition is used
        module = code("kernel/store.py", "kernel/store.py", 5, kind="file")
        self.see(twin + [module], [link(f"t{i}", "t0") for i in range(1, 5)] + [link("kernel/store.py", f"t{i}", "contains") for i in range(5)])
        self.assertEqual(self.home("t1"), "kernel: store.py +1 file (t0)")
        self.assertEqual(len({(c["plane"], c["name"]) for c in view["clusters"]}), len(view["clusters"]))

    def test_the_same_busiest_member_too_gets_a_number(self):
        names = gv.distinct_names({"x": "n", "y": "n", "z": "n"}, {"x": "p", "y": "p", "z": "q"}, {"x": "m", "y": "m", "z": "m"})
        self.assertEqual(names, {"x": "n (m) #1", "y": "n (m) #2", "z": "n"})


class Claims(View):
    def test_a_claim_is_shown_once_on_the_cluster_its_busiest_member_is_in(self):
        more_tests = [code(f"more{i}", "tests/test_store.py", 1) for i in range(4)]    # the tests part is the larger
        view = self.see(more_tests)
        self.assertEqual([c["name"] for c in view["clusters"] if c["claims"]], [STORE])
        self.assertEqual(self.where["now"]["claims"], ["c1 confirmed"])

    def test_a_claim_follows_a_community_that_was_taken_into_another_cluster(self):
        claim = {"code-9": [{"id": "c9", "verdict": None, "state": "open"}]}
        view = self.see([code("stray", "kernel/stray.py", 9)], [link("stray", "a0")], claims=claim)
        self.assertEqual([(c["community"], c["claims"]) for c in view["clusters"] if c["claims"]],
                         [("code-2", ["c9 open (code-9)"])])    # on another community's cluster it says which unit
        view = self.see([code("stray", "kernel/stray.py", 9)], claims=claim)    # linked to nothing: the leftovers
        self.assertEqual([(c["name"], c["claims"]) for c in view["clusters"] if c["claims"]],
                         [("kernel: other code", ["c9 open (code-9)"])])


if __name__ == "__main__":
    unittest.main()
