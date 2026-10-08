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


if __name__ == "__main__":
    unittest.main()
