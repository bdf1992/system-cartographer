"""The record rules of graph_export.py and graph_view.py, on a made-up root.

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

FILES = {
    "tasks/t-alpha.json": {"record_type": "Task", "id": "t-alpha", "mission": "m-one", "state": "new", "word": "open",
                           "deps": ["t-beta"], "why": "follows t-beta, see D-0007.", "owner": "kernel",
                           "lane": "shared-name", "by_rule": {"D-0007": "the reason", "notes": "a key that is a file name"}},
    "tasks/t-beta.json": {"record_type": "Task", "id": "t-beta", "mission": "m-one", "note": "t-beta"},
    "tasks/t-gamma.json": {"record_type": "Task", "id": "t-gamma", "mission": "shared-name"},
    "tasks/shared-name.json": {"record_type": "Task", "id": "shared-name", "mission": "m-one"},
    "tasks/t-filed-elsewhere.json": {"record_type": "Task", "id": "t-filed-elsewhere", "mission": "m-one"},
    "missions/m-one.json": {"record_type": "Mission", "id": "m-one"},
    "missions/shared-name.json": {"record_type": "Mission", "id": "shared-name"},
    "decisions/D-0007.json": {"record_type": "Decision", "id": "D-0007"},
    "categories/kernel.json": {"record_type": "Category", "id": "kernel"},
    "schemas/task.json": {"type": "object", "properties": {}},
    "missions/t-beta.json": {"record_type": "Mission", "id": "m-two"},    # a file named like another record's id
    "loose/thing.json": {"name": "no type here", "ref": "dupe", "pair": "solo-pair"},
    "loose/second.json": {"pair": "dupe"},
    "a/dupe.json": {"kind": "Pair"},
    "b/dupe.json": {"kind": "Pair"},
    "c/solo-pair.json": {"kind": "Pair"},
    "loose/list.json": ["t-alpha"],
    "loose/open.json": {"type": "Note", "about": "open"},
    "loose/new.json": {"type": "Note"},
    "loose/notes.json": {"type": "Note"},
    "loose/plain.yaml": None,
    "loose/gone.json": "missing",
}
ELSEWHERE = "tasks/t-filed-elsewhere.json"


def build(files=FILES):
    root = tempfile.mkdtemp(prefix="carto-records-")
    for rel, body in files.items():
        if body == "missing":
            continue
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("id: t-alpha\n" if body is None else json.dumps(body))
    row = lambda rel: {"id": rel, "source_class": "configuration"}  # noqa: E731
    graphs = {
        "asset-records": {"root": root, "nodes": [row(rel) for rel in files], "edges": [], "findings": []},
        "integrations": {"root": root, "nodes": [row(ELSEWHERE)], "edges": [],
                         "findings": [{"file": ELSEWHERE, "evidence_stage": "structural"}]},
    }
    return ge.build_graph(graphs, {}, asset_kinds={"asset-records": "records"}, group_by="asset")


class RecordTypes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build()
        cls.node = {n["id"]: n for n in cls.graph["nodes"]}

    def kind(self, rel):
        return self.node[rel]["record_type"], self.node[rel]["record_type_basis"]

    def test_a_record_s_own_type_field_is_used(self):
        self.assertEqual(self.kind("tasks/t-alpha.json"), ("Task", "declared"))
        self.assertEqual(self.kind("a/dupe.json"), ("Pair", "declared"))

    def test_a_json_schema_is_typed_by_its_folder(self):
        self.assertEqual(self.kind("schemas/task.json"), ("schemas", "folder"))

    def test_a_record_naming_no_type_is_typed_by_its_folder(self):
        self.assertEqual(self.kind("loose/thing.json"), ("loose", "folder"))

    def test_what_cannot_be_read_is_typed_by_its_folder_and_counted(self):
        for rel in ("loose/plain.yaml", "loose/list.json", "loose/gone.json"):
            self.assertEqual(self.kind(rel), ("loose", "folder"))
        self.assertEqual(self.graph["graph"]["records"]["unread"], 3)

    def test_a_record_filed_under_another_concern_is_still_a_record(self):
        self.assertEqual(self.node[ELSEWHERE]["primary_concern"], "integrations")
        self.assertEqual(self.kind(ELSEWHERE), ("Task", "declared"))


class RecordLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build()
        cls.links = {(l["source"], l["target"]): l for l in cls.graph["links"] if l["relation"] in ("refers_to", "mentions")}

    def link(self, source, target):
        row = self.links.get((source, target))
        return row and (row["relation"], row["field"], row["confidence"])

    def test_a_field_holding_a_declared_id_is_an_extracted_link(self):
        self.assertEqual(self.link("tasks/t-alpha.json", "missions/m-one.json"), ("refers_to", "mission", "EXTRACTED"))

    def test_an_id_inside_a_list_is_a_link(self):
        self.assertEqual(self.link("tasks/t-alpha.json", "tasks/t-beta.json"), ("refers_to", "deps[]", "EXTRACTED"))

    def test_an_object_key_that_is_a_declared_id_is_a_link(self):
        self.assertEqual(self.link("tasks/t-alpha.json", "decisions/D-0007.json"), ("refers_to", "by_rule{}", "EXTRACTED"))

    def test_an_object_key_that_is_only_a_file_name_is_not_a_link(self):
        self.assertIsNone(self.link("tasks/t-alpha.json", "loose/notes.json"))

    def test_a_match_on_a_file_name_alone_is_inferred(self):
        self.assertEqual(self.link("tasks/t-alpha.json", "loose/open.json"), ("refers_to", "word", "INFERRED"))

    def test_a_declared_id_that_is_a_plain_word_is_inferred(self):
        self.assertEqual(self.link("tasks/t-alpha.json", "categories/kernel.json"), ("refers_to", "owner", "INFERRED"))

    def test_a_word_shorter_than_an_id_is_not_a_link(self):
        self.assertIsNone(self.link("tasks/t-alpha.json", "loose/new.json"))

    def test_a_record_naming_itself_is_not_a_link(self):
        self.assertFalse(any(source == target for source, target in self.links))

    def test_a_declared_id_inside_a_longer_string_is_a_mention(self):
        # t-beta is already a refers_to from deps[]; one link a pair, and the exact one stands.
        self.assertEqual(self.link("tasks/t-alpha.json", "tasks/t-beta.json")[0], "refers_to")
        # `kernel` is a declared id that is a plain word and `notes` only a file name: prose holding them mentions neither
        graph = build({**FILES, "tasks/t-delta.json": {"record_type": "Task", "id": "t-delta",
                                                       "why": "after t-beta. See the kernel notes."}})
        rows = [l for l in graph["links"] if l["source"] == "tasks/t-delta.json"]
        self.assertEqual([(l["target"], l["relation"], l["field"], l["confidence"]) for l in rows],
                         [("tasks/t-beta.json", "mentions", "why", "INFERRED")])

    def test_a_shared_name_is_followed_only_where_the_field_settles_which(self):
        self.assertEqual(self.graph["graph"]["records"]["ambiguous_ids"], 2)    # dupe, shared-name
        self.assertEqual(self.link("tasks/t-gamma.json", "missions/shared-name.json"), ("refers_to", "mission", "INFERRED"))
        self.assertIsNone(self.link("tasks/t-alpha.json", "missions/shared-name.json"))    # `lane` points at nothing known
        self.assertIsNone(self.link("tasks/t-alpha.json", "tasks/shared-name.json"))
        # `pair` usually points at a Pair, and both records named dupe are Pairs: still unsettled
        self.assertEqual(self.link("loose/thing.json", "c/solo-pair.json"), ("refers_to", "pair", "INFERRED"))
        self.assertFalse(any("dupe.json" in target for _, target in self.links))

    def test_a_declared_id_beats_a_file_of_the_same_name(self):
        self.assertEqual(self.link("tasks/t-alpha.json", "tasks/t-beta.json"), ("refers_to", "deps[]", "EXTRACTED"))
        self.assertIsNone(self.link("tasks/t-alpha.json", "missions/t-beta.json"))

    def test_a_link_from_a_record_filed_elsewhere_does_not_refile_its_target(self):
        self.assertEqual(self.link(ELSEWHERE, "missions/m-one.json"), ("refers_to", "mission", "EXTRACTED"))
        node = {n["id"]: n for n in self.graph["nodes"]}
        self.assertEqual(node["missions/m-one.json"]["asset_kind"], "records")

    def test_the_report_counts_them(self):
        report = ge.render_report(self.graph, "fixture")
        self.assertIn("## Records", report)
        self.assertIn("3 of those because the file could not be read", report)

    def test_two_builds_of_one_root_are_the_same(self):
        strip = lambda g: json.dumps({**g, "graph": {**g["graph"], "root": None}}, sort_keys=True)  # noqa: E731
        again = build()
        self.assertEqual(len(again["links"]), len(self.graph["links"]))
        self.assertEqual([(l["source"], l["target"], l["relation"]) for l in again["links"]],
                         [(l["source"], l["target"], l["relation"]) for l in self.graph["links"]])
        self.assertEqual(len(strip(again)), len(strip(self.graph)))


class RecordClusters(unittest.TestCase):
    def names(self, small):
        before, gv.SMALL_TYPE = gv.SMALL_TYPE, small
        try:
            return sorted(c["name"] for c in gv.build_view(build(), [], [])["clusters"])
        finally:
            gv.SMALL_TYPE = before

    def test_a_type_is_a_cluster_once_it_has_enough_records(self):
        self.assertIn("records: Task", self.names(4))
        self.assertNotIn("records: Task", self.names(5))

    def test_a_small_type_goes_to_its_folder_and_a_small_folder_to_other(self):
        names = self.names(5)
        self.assertIn("records: loose", names)     # three Notes join the untyped files of their folder
        self.assertIn("records: other", names)
        self.assertNotIn("records: Note", names)

    def test_the_fold_is_counted_on_each_plane(self):
        # the Task filed under integrations sits on another plane and is not counted with the four on records
        self.assertIn("system description: other", self.names(4))


if __name__ == "__main__":
    unittest.main()
