"""The viewer's data logic, run under node from the marked block in references/viewer/index.html.

    python tests/test_viewer.py

Needs node on PATH; a missing node fails the test.
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import graph_view as gv  # noqa: E402
from test_view import graph  # noqa: E402

VIEWER = os.path.join(ROOT, "references", "viewer", "index.html")
START = "// ---- pure: no DOM, read by tests/test_viewer.py ----"
END = "// ---- end pure ----"


def pure_block():
    """The text of the viewer between the two marker lines."""
    with open(VIEWER, encoding="utf-8") as f:
        lines = f.read().splitlines()
    stripped = [line.strip() for line in lines]
    if START not in stripped:
        raise AssertionError("the viewer has no line " + START)
    if END not in stripped:
        raise AssertionError("the viewer has no line " + END)
    a, b = stripped.index(START), stripped.index(END)
    if b < a:
        raise AssertionError("the end marker comes before the start marker")
    return "\n".join(lines[a + 1:b])


def run(expression, data):
    """Evaluate a JavaScript expression over the block, with the JSON `data` as D; return the parsed result."""
    script = (pure_block() + "\nconst D = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
              "console.log(JSON.stringify(" + expression + "));")
    try:
        done = subprocess.run(["node", "-e", script], input=json.dumps(data), capture_output=True,
                              text=True, encoding="utf-8", timeout=60)
    except FileNotFoundError:
        raise AssertionError("node is not on PATH")
    if done.returncode != 0:
        raise AssertionError("node failed: " + done.stderr)
    return json.loads(done.stdout)


class Siblings(unittest.TestCase):
    def setUp(self):
        self.view = gv.build_view(graph(), [], [])
        cl = self.view["clusters"]
        parts = [i for i, c in enumerate(cl) if c["community"] == "code-1"]
        self.assertEqual(len(parts), 2)
        named = {self.view["planes"][cl[k]["plane"]]["name"]: k for k in parts}
        self.assertEqual(set(named), {"kernel", "tests"})
        self.i, self.j = named["kernel"], named["tests"]

    def test_the_parts_of_one_community_are_siblings(self):
        d = self.view
        self.assertEqual(run(f"siblingsOf(D.clusters, {self.i})", d), [self.j])
        self.assertEqual(run(f"siblingsOf(D.clusters, {self.j})", d), [self.i])

    def test_a_community_drawn_once_has_none(self):
        cl = self.view["clusters"]
        k = [n for n, c in enumerate(cl) if c["community"] == "code-2"]
        self.assertTrue(k)
        for n in k:
            self.assertEqual(run(f"siblingsOf(D.clusters, {n})", self.view), [])

    def test_a_cluster_with_no_community_has_none(self):
        cl = self.view["clusters"]
        k = [n for n, c in enumerate(cl) if c["name"] == "app: other code"]
        self.assertEqual(len(k), 1)
        self.assertIsNone(cl[k[0]]["community"])
        self.assertEqual(run(f"siblingsOf(D.clusters, {k[0]})", self.view), [])

    def test_rows_name_the_plane_each_part_is_on(self):
        self.assertEqual(run(f"siblingRows(D.clusters, D.planes, {self.i})", self.view), [[self.j, "tests"]])


class Routes(unittest.TestCase):
    """The curves: control points through the centres of the groups a link leaves and enters."""
    POINTS = [[0, 0], [5, 9], [7, -3], [10, 10]]

    def setUp(self):
        self.view = gv.build_view(graph(), [], [])
        cl, nodes = self.view["clusters"], self.view["nodes"]
        self.node = {row[3]: i for i, row in enumerate(nodes)}
        node_cluster, node_file = [0] * len(nodes), [-1] * len(nodes)
        for k, c in enumerate(cl):
            for i in range(c["start"], c["start"] + c["count"]):
                node_cluster[i] = k
        for k, row in enumerate(self.view["files"]):
            for i in range(row[4], row[4] + row[5]):
                node_file[i] = k
        self.cluster_of, self.file_of = node_cluster, node_file
        self.data = dict(self.view, nodeCluster=node_cluster, nodeFile=node_file, points=self.POINTS)

    def hops(self, a, b):
        return run(f"hops({self.node[a]}, {self.node[b]}, D.nodes, D.nodeFile, D.nodeCluster, D.files, D.clusters)", self.data)

    def centre_of_file(self, label):
        row = self.view["files"][self.file_of[self.node[label]]]
        return [row[1], row[2]]

    def centre_of_cluster(self, label):
        c = self.view["clusters"][self.cluster_of[self.node[label]]]
        return [c["x"], c["y"]]

    def at(self, label):
        return self.view["nodes"][self.node[label]][:2]

    def test_route_returns_a_flat_run_that_starts_and_ends_on_the_ends(self):
        for steps in (1, 7, 16):
            out = run(f"route(D.points, 0.85, {steps})", self.data)
            self.assertEqual(len(out), 2 * (steps + 1))
            self.assertEqual((out[:2], out[-2:]), (self.POINTS[0], self.POINTS[-1]))

    def test_with_beta_0_every_point_lies_on_the_straight_line(self):
        out = run("route(D.points, 0, 8)", self.data)
        for step in range(9):
            self.assertAlmostEqual(out[2 * step], 10 * step / 8, places=9)
            self.assertAlmostEqual(out[2 * step + 1], 10 * step / 8, places=9)

    def test_with_two_control_points_it_is_that_line(self):
        out = run("route([[2, 4], [10, -4]], 0.85, 4)", self.data)
        for got, want in zip(out, [2, 4, 4, 2, 6, 0, 8, -2, 10, -4]):
            self.assertAlmostEqual(got, want, places=9)

    def test_with_beta_1_the_middle_of_three_is_a_quarter_a_half_and_a_quarter(self):
        out = run("route([[0, 0], [5, 9], [10, 2]], 1, 16)", self.data)
        self.assertAlmostEqual(out[16], 0.25 * 0 + 0.5 * 5 + 0.25 * 10, places=9)
        self.assertAlmostEqual(out[17], 0.25 * 0 + 0.5 * 9 + 0.25 * 2, places=9)

    def test_beta_pulls_the_curve_towards_the_line(self):
        full = run("route([[0, 0], [5, 9], [10, 2]], 1, 16)", self.data)
        part = run("route([[0, 0], [5, 9], [10, 2]], 0.85, 16)", self.data)
        self.assertAlmostEqual(part[17], 0.25 * 0 + 0.5 * (0.85 * 9 + 0.15 * 1) + 0.25 * 2, places=9)
        self.assertLess(part[17], full[17])

    def test_hops_between_files_of_two_clusters_are_six_points(self):
        self.assertNotEqual(self.cluster_of[self.node["store0"]], self.cluster_of[self.node["a0"]])
        self.assertEqual(self.hops("store0", "a0"),
                         [self.at("store0"), self.centre_of_file("store0"), self.centre_of_cluster("store0"),
                          self.centre_of_cluster("a0"), self.centre_of_file("a0"), self.at("a0")])

    def test_hops_between_two_files_of_one_cluster_are_four_points(self):
        self.assertEqual(self.cluster_of[self.node["a1"]], self.cluster_of[self.node["b0"]])
        self.assertEqual(self.hops("a1", "b0"),
                         [self.at("a1"), self.centre_of_file("a1"), self.centre_of_file("b0"), self.at("b0")])

    def test_hops_from_a_cluster_with_no_file_level_skip_the_file(self):
        self.assertEqual(self.file_of[self.node["test0"]], -1)
        self.assertEqual(self.hops("test0", "store0"),
                         [self.at("test0"), self.centre_of_cluster("test0"), self.centre_of_cluster("store0"),
                          self.centre_of_file("store0"), self.at("store0")])
        self.assertEqual(self.hops("test0", "test1"), [self.at("test0"), self.at("test1")])

    def test_band_hops_are_four_points_across_planes_and_two_on_one(self):
        cl, planes = self.view["clusters"], self.view["planes"]
        store, tests, ops = (self.cluster_of[self.node[label]] for label in ("store0", "test0", "a0"))
        self.assertNotEqual(cl[store]["plane"], cl[tests]["plane"])
        self.assertEqual(cl[store]["plane"], cl[ops]["plane"])

        def middle(k):
            box = planes[cl[k]["plane"]]
            return [box["x"] + box["w"] / 2, box["y"] + box["h"] / 2]

        start = self.at("store0")
        self.data["start"] = self.view["nodes"][self.node["store0"]]    # a node row: only its x and y are taken
        across = run(f"bandHops(D.start, {store}, {tests}, D.clusters, D.planes)", self.data)
        self.assertEqual(across, [start, middle(store), middle(tests), [cl[tests]["x"], cl[tests]["y"]]])
        along = run(f"bandHops(D.start, {store}, {ops}, D.clusters, D.planes)", self.data)
        self.assertEqual(along, [start, [cl[ops]["x"], cl[ops]["y"]]])


if __name__ == "__main__":
    unittest.main()
