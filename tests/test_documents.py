"""Documents joined to the files they name, and written files shown apart from derived ones.

    python -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import graph_export as ge  # noqa: E402
import graph_view as gv  # noqa: E402

MANY = [f"src/m{i:02}.py" for i in range(15)]
TEXT = {
    "docs/guide.md": "Start with `src/app.py`, then src/app.py again and docs/guide.md itself.\nSee also docs/other.md and missing/file.py.",
    "docs/other.md": "Nothing named here.",
    "docs/listing.md": "First src/app.py. Then " + ", ".join(MANY) + ".",
    "notes/filed-elsewhere.md": "This one names src/app.py too.",
    "data/rows.csv": "src/app.py",
}
GENERATED = [f"out/gen{i}.md" for i in range(5)]
FEW = ["build/one.md", "build/two.md"]


def build():
    root = tempfile.mkdtemp(prefix="carto-docs-")
    for rel, body in {**TEXT, **{rel: "generated from src/app.py" for rel in GENERATED + FEW}}.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
    row = lambda rel, cls="source": {"id": rel, "source_class": cls}  # noqa: E731
    documents = [rel for rel in TEXT if rel.endswith(".md")]
    graphs = {
        "asset-documents": {"root": root, "edges": [{"src": "docs/guide.md", "dst": "docs/other.md", "kind": "doc_link"}],
                            "findings": [], "nodes": [row(rel) for rel in documents]
                            + [row(rel, "generated") for rel in GENERATED + FEW]},
        "asset-data": {"root": root, "edges": [], "findings": [], "nodes": [row("data/rows.csv", "unknown")]},
        "code-scripts": {"root": root, "edges": [], "nodes": [row(rel) for rel in ["src/app.py"] + MANY] + [row("notes/filed-elsewhere.md")],
                         "findings": [{"file": "notes/filed-elsewhere.md", "evidence_stage": "structural"}]},
    }
    kinds = {"asset-documents": "documents", "asset-data": "data"}
    return ge.build_graph(graphs, {}, asset_kinds=kinds, group_by="asset")


class DocumentLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build()
        cls.names = [(l["source"], l["target"]) for l in cls.graph["links"] if l["relation"] == "names"]
        cls.rows = {(l["source"], l["target"]): l for l in cls.graph["links"] if l["relation"] == "names"}

    def named_by(self, rel):
        return [target for source, target in self.names if source == rel]

    def test_a_document_is_linked_once_to_each_scanned_file_it_names(self):
        self.assertEqual(self.named_by("docs/guide.md"), ["src/app.py"])    # named twice; itself and a missing file are not
        row = self.rows[("docs/guide.md", "src/app.py")]
        self.assertEqual((row["confidence"], row["confidence_score"], row["concern"]), ("INFERRED", 0.75, "asset-documents"))

    def test_a_file_it_is_already_linked_to_is_not_linked_again(self):
        self.assertNotIn("docs/other.md", self.named_by("docs/guide.md"))
        self.assertEqual(sum(1 for l in self.graph["links"] if (l["source"], l["target"]) == ("docs/guide.md", "docs/other.md")), 1)

    def test_only_the_first_twelve_named_are_kept_in_the_order_named(self):
        self.assertEqual(self.named_by("docs/listing.md"), ["src/app.py"] + MANY[:11])

    def test_a_document_filed_under_another_concern_is_still_a_document(self):
        node = next(n for n in self.graph["nodes"] if n["id"] == "notes/filed-elsewhere.md")
        self.assertEqual(node["primary_concern"], "code-scripts")
        self.assertEqual(self.named_by("notes/filed-elsewhere.md"), ["src/app.py"])
        self.assertEqual(self.rows[("notes/filed-elsewhere.md", "src/app.py")]["concern"], "asset-documents")

    def test_a_file_that_is_not_a_document_is_not_read_for_names(self):
        self.assertEqual(self.named_by("data/rows.csv"), [])

    def test_the_counts_reach_the_report(self):
        self.assertEqual(self.graph["graph"]["documents"], {"documents": 11, "naming": 10, "links": 21, "left_out": 4})
        report = ge.render_report(self.graph, "fixture")
        self.assertIn("11 documents; 10 name at least one scanned file by path. 21 `names` links", report)
        self.assertIn("4 further names were left out", report)
        self.assertIn("7 generated, 3 source", report)


class DerivedClusters(unittest.TestCase):
    def names(self, small=5):
        before, gv.SMALL_TYPE = gv.SMALL_TYPE, small
        try:
            view = gv.build_view(build(), [], [])
        finally:
            gv.SMALL_TYPE = before
        planes = [p["name"] for p in view["planes"]]
        return {c["name"]: (planes[c["plane"]], c["count"]) for c in view["clusters"]}

    def test_derived_files_on_an_asset_plane_are_a_cluster_of_their_own(self):
        names = self.names()
        self.assertEqual(names["documents: generated"], ("documents", 7))
        self.assertEqual(names["documents"], ("documents", 3))

    def test_too_few_stay_with_the_rest(self):
        names = self.names(small=8)
        self.assertNotIn("documents: generated", names)
        self.assertEqual(names["documents"], ("documents", 10))

    def test_code_and_written_files_are_not_split(self):
        self.assertNotIn("data: unknown", self.names())
        self.assertFalse([name for name in self.names() if name.endswith(": source")])


if __name__ == "__main__":
    unittest.main()
