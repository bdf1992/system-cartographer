"""Defeating cases for the evidence gate and generated projections."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate import LINEAGE,Invalid,load
import render
from render_profile import diagram,page
from verify_sources import check_source,verify_inventory

class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.good=load(LINEAGE.read_text())
    def reject(self,mutate,pattern):
        data=copy.deepcopy(self.good);mutate(data)
        with self.assertRaisesRegex(Invalid,pattern):load(yaml.safe_dump(data))
    def test_valid_source(self): self.assertEqual(verify_inventory(self.good),len(self.good['nodes']))
    def test_wrong_schema(self): self.reject(lambda d:d.update(schema='anything/v9'),'schema')
    def test_unknown_node_status(self):self.reject(lambda d:d['nodes']['owl'].update(status='complete'),'invalid status')
    def test_unknown_relation(self):self.reject(lambda d:d['edges'][0].update(type='trust-me'),'relation type')
    def test_dangling_edge(self):self.reject(lambda d:d['edges'][0].update(to='missing'),'dangling')
    def test_empty_folded_evidence(self):
        text=yaml.safe_dump(self.good);data=copy.deepcopy(self.good);data['edges'][0]['evidence']=''
        text=yaml.safe_dump(data).replace("evidence: ''",'evidence: >-')
        with self.assertRaisesRegex(Invalid,'empty evidence'):load(text)
    def test_duplicate_yaml_key(self):
        with self.assertRaisesRegex(Invalid,'duplicate'):load('schema: lineage/v1\nschema: lineage/v2\n')
    def test_duplicate_node_address(self):self.reject(lambda d:d['nodes']['owl'].update(repo=d['nodes']['ontum']['repo']),'duplicate repo')
    def test_private_node_refused(self):self.reject(lambda d:d['nodes']['owl'].update(visibility='private'),'private repositories')
    def test_missing_revision(self):self.reject(lambda d:d['nodes']['owl']['evidence'].pop('revision'),'invalid revision')
    def test_path_traversal(self):self.reject(lambda d:d['nodes']['owl']['evidence'].update(path='../secret'),'unsafe evidence path')
    def test_hypothesis_cannot_be_promoted_by_changing_state(self):
        self.reject(lambda d:d['edges'][3].update(state='documented'),'basis does not support')
    def test_vocabulary_cannot_prove_supersession(self):
        self.reject(lambda d:d['edges'][4].update(state='documented'),'basis does not support')
    def test_isolation_must_be_explained(self):self.reject(lambda d:d['nodes']['ide'].pop('unconnected_reason'),'needs a reason')
    def test_source_integrity_detects_mutation(self):
        source=dict(self.good['nodes']['owl']['evidence'])
        with patch('verify_sources.read_source',return_value=b'changed source'):
            with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):check_source('bdf1992/Owl',source,Path('.'),False)
    def test_quote_must_exist_even_if_digest_matches(self):
        raw=b'actual source';source={'revision':'a'*40,'path':'README.md','sha256':hashlib.sha256(raw).hexdigest(),'quote':'invented quote'}
        with patch('verify_sources.read_source',return_value=raw):
            with self.assertRaisesRegex(ValueError,'quote absent'):check_source('bdf1992/Owl',source,Path('.'),False)
    def test_inventory_omission_detected(self):
        data=copy.deepcopy(self.good);data['nodes'].pop('field')
        with self.assertRaisesRegex(ValueError,'inventory mismatch'):verify_inventory(data)
    def test_rejected_relation_not_projected(self):
        edges=[e for e in self.good['edges'] if e['state']=='unsupported']
        self.assertEqual(diagram(self.good['nodes'],edges),'')
        doc=json.loads(render.schematic(self.good));self.assertEqual(len(doc['wires']),sum(e['state']!='unsupported' for e in self.good['edges']))
        self.assertFalse(any(w['a']=='repo:ontum' and w['b']=='repo:onton' for w in doc['wires']))
    def test_projections_retain_ids_and_states(self):
        doc=json.loads(render.schematic(self.good));self.assertEqual({c['id'] for c in doc['components']},{'repo:'+n for n in self.good['nodes']})
        self.assertTrue(any('[inferred]' in w['config']['label'] for w in doc['wires']))
    def test_actual_drift_gate_refuses_hand_edit(self):
        path=LINEAGE.parent/'profile-README.md';before=path.read_bytes()
        try:
            path.write_bytes(before+b'\nmanual drift\n')
            p=subprocess.run([sys.executable,str(LINEAGE.parent/'render.py'),'--check'],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0);self.assertIn('generated drift',p.stdout)
        finally:path.write_bytes(before)
    def test_render_is_deterministic(self):self.assertEqual(render.outputs(self.good),render.outputs(self.good))
    def test_profile_keeps_all_public_repositories(self):
        text=page(self.good['nodes'],self.good['edges'])
        for node in self.good['nodes'].values():self.assertIn('https://github.com/'+node['repo'],text)
        self.assertNotIn('All of it is checked',text)
if __name__=='__main__':unittest.main()
