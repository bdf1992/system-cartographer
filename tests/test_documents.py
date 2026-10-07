"""Documents joined to the files they name, and written files shown apart from derived ones.

    python -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import graph_export as ge  # noqa: E402
import graph_view as gv  # noqa: E402

MANY = [f"src/m{i:02}.py" for i in range(15)]
CODE = ["src/app.py", "src/util/paths.py", "docs/img/shot.py", "README.md", "docs/README.md", "other/settings.json"] + MANY
TEXT = {
    "docs/guide.md": "Start with `src/app.py`, then src/app.py again and docs/guide.md itself.\n"
                     "See also docs/other.md and missing/file.py.",
    "docs/other.md": "Nothing named here.",
    "docs/listing.md": "First src/app.py. Then " + ", ".join(MANY) + ".",
    "docs/relative.md": "Beside this file: sibling.md and ./img/shot.py. Up one: ../src/app.py. The README.md here.",
    "docs/sibling.md": "The other project's `settings.json`, and ~\\other\\settings.json in a home folder, "
                       "and C:\\work\\root\\src\\util\\paths.py on this machine.",
    "notes/filed-elsewhere.md": "This one names src/app.py too.",
    "data/rows.csv": "src/app.py",
}
GENERATED = [f"out/gen{i}.md" for i in range(5)]
GENERATED_TEXT = "Page for src/app.py. Imported by src/m00.py, src/m01.py."
ARCHIVES = [f"drop/pack{i}.zip" for i in range(5)]
FEW = ["build/one.png", "build/two.png", "build/three.png", "build/four.png"]
TRANSCRIPTS = [f"sessions/s{i}.json" for i in range(5)]


def build():
    root = tempfile.mkdtemp(prefix="carto-docs-")
    bodies = {**TEXT, **{rel: GENERATED_TEXT for rel in GENERATED}, **{rel: "{}" for rel in TRANSCRIPTS}}
    for rel, body in bodies.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
    row = lambda rel, cls="source": {"id": rel, "source_class": cls}  # noqa: E731
    documents = [rel for rel in TEXT if rel.endswith(".md")]
    graphs = {
        "asset-documents": {"root": root, "edges": [{"src": "docs/guide.md", "dst": "docs/other.md", "kind": "doc_link"}],
                            "findings": [], "nodes": [row(rel) for rel in documents] + [row(rel, "generated") for rel in GENERATED]},
        "asset-data": {"root": root, "edges": [], "findings": [], "nodes": [row("data/rows.csv", "unknown")]},
        "asset-files": {"root": root, "edges": [], "findings": [], "nodes": [row(rel, "archive") for rel in ARCHIVES]},
        "asset-media": {"root": root, "edges": [], "findings": [], "nodes": [row(rel, "generated") for rel in FEW]},
        "asset-records": {"root": root, "edges": [], "findings": [], "nodes": [row(rel, "transcript") for rel in TRANSCRIPTS]},
        "code-scripts": {"root": root, "edges": [], "nodes": [row(rel) for rel in CODE] + [row("notes/filed-elsewhere.md")],
                         "findings": [{"file": "notes/filed-elsewhere.md", "evidence_stage": "structural"}]},
    }
    kinds = {"asset-documents": "documents", "asset-data": "data", "asset-files": "files", "asset-media": "media",
             "asset-records": "records"}
    return ge.build_graph(graphs, {}, asset_kinds=kinds, group_by="asset")


class DocumentLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build()
        cls.rows = {(l["source"], l["target"]): l for l in cls.graph["links"] if l["relation"] == "names"}

    def named_by(self, rel):
        return [target for source, target in self.rows if source == rel]

    def test_a_document_is_linked_once_to_each_scanned_file_it_names(self):
        self.assertEqual(self.named_by("docs/guide.md"), ["src/app.py"])    # named twice; itself and a missing file are not
        row = self.rows[("docs/guide.md", "src/app.py")]
        self.assertEqual((row["confidence"], row["confidence_score"], row["concern"]), ("INFERRED", 0.75, "asset-documents"))

    def test_a_file_it_is_already_linked_to_is_not_linked_again(self):
        self.assertEqual(sum(1 for l in self.graph["links"] if (l["source"], l["target"]) == ("docs/guide.md", "docs/other.md")), 1)

    def test_a_written_document_is_linked_to_every_file_it_names(self):
        self.assertEqual(self.named_by("docs/listing.md"), ["src/app.py"] + MANY)

    def test_a_derived_document_is_linked_to_the_first_file_it_names(self):
        for rel in GENERATED:
            self.assertEqual(self.named_by(rel), ["src/app.py"])

    def test_a_path_is_read_against_the_document_s_folder_first(self):
        # README.md is a bare name: the one beside the document, not the root's
        self.assertEqual(self.named_by("docs/relative.md"), ["docs/README.md", "docs/img/shot.py", "docs/sibling.md", "src/app.py"])
        self.assertEqual(ge.document_targets(TEXT["docs/relative.md"], "docs/relative.md", {n["id"]: n for n in self.graph["nodes"]}),
                         ["docs/sibling.md", "docs/img/shot.py", "src/app.py", "docs/README.md"])    # in the order named

    def test_a_bare_name_elsewhere_and_a_home_path_are_not_this_root_s_files(self):
        # `settings.json` is not beside the document; ~\other\settings.json is in a home folder
        self.assertEqual(self.named_by("docs/sibling.md"), ["src/util/paths.py"])    # the absolute path, by its trailing parts

    def test_a_document_filed_under_another_concern_is_still_a_document(self):
        node = next(n for n in self.graph["nodes"] if n["id"] == "notes/filed-elsewhere.md")
        self.assertEqual(node["primary_concern"], "code-scripts")
        self.assertEqual(self.named_by("notes/filed-elsewhere.md"), ["src/app.py"])
        self.assertEqual(self.rows[("notes/filed-elsewhere.md", "src/app.py")]["concern"], "asset-documents")

    def test_a_file_that_is_not_a_document_is_not_read_for_names(self):
        self.assertEqual(self.named_by("data/rows.csv"), [])

    def test_the_counts_reach_the_report(self):
        self.assertEqual(self.graph["graph"]["documents"],
                         {"documents": 11, "naming": 10, "links": 28, "derived": 5, "left_out": 10})
        report = ge.render_report(self.graph, "fixture")
        self.assertIn("11 documents, 5 of them derived", report)
        self.assertIn("10 name at least one scanned file by path. 28 `names` links", report)
        self.assertIn("10 further names in derived documents were left out", report)


class DerivedClusters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = gv.build_view(build(), [], [])
        planes = [p["name"] for p in cls.view["planes"]]
        cls.names = {c["name"]: (planes[c["plane"]], c["count"]) for c in cls.view["clusters"]}

    def test_derived_files_on_an_asset_plane_are_a_cluster_of_their_own(self):
        self.assertEqual(self.names["documents: generated"], ("documents", 5))    # five is enough
        self.assertEqual(self.names["documents"], ("documents", 5))
        self.assertEqual(self.names["files: archive"], ("files", 5))

    def test_four_stay_with_the_rest(self):
        self.assertNotIn("media: generated", self.names)
        self.assertEqual(self.names["media"], ("media", 4))

    def test_a_record_is_grouped_by_its_type_whatever_its_source_class(self):
        self.assertNotIn("records: transcript", self.names)
        self.assertEqual(self.names["records: sessions"], ("records", 5))

    def test_written_files_are_not_split(self):
        self.assertFalse([name for name in self.names if name.endswith((": source", ": unknown"))])

    def test_a_names_link_is_drawn_as_a_use(self):
        index = {row[5]: i for i, row in enumerate(self.view["nodes"])}
        edge = next(e for e in self.view["edges"] if (e[0], e[1]) == (index["docs/guide.md"], index["src/app.py"]))
        self.assertEqual((self.view["kinds"][edge[2]], edge[3]), ("uses", 1))


if __name__ == "__main__":
    unittest.main()
