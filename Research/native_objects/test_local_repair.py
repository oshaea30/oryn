from copy import deepcopy
import json
from pathlib import Path
import unittest
from Research.native_objects import local_repair as local
from Research.native_objects import assembly_followup as run

class LocalRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=run.prepare_replay();cls.raw=cls.data['plan'];cls.contract=cls.data['contract']
        cls.report=json.loads((run.SOURCE/'results/assembly-011/diagnostic-replay/cooling-fan-row-plan-0/relations.json').read_text())
    def patch(self):
        scope=local.scope(self.raw,self.report);port=deepcopy(next(v for v in self.raw['ports'] if v['id'] in scope['allowed_ports'] and v['kind']=='bore_axis'))
        port['span']=[.3,.7]
        return scope,{'base_sha256':scope['base_sha256'],'status':'patch','reason':'','shapes':[],'ports':[port]}
    def test_scope_keeps_panel_protected_and_includes_shared_users(self):
        scope=local.scope(self.raw,self.report)
        self.assertNotIn('panel',scope['allowed_parts']);self.assertEqual(len(scope['allowed_parts']),6)
        self.assertTrue(all(p['part']!='panel' for p in self.raw['ports'] if p['id'] in scope['allowed_ports']))
    def test_patch_preserves_unrelated_data_and_input(self):
        scope,patch=self.patch();original=deepcopy(self.raw)
        revised,audit=local.apply(self.raw,patch,scope,self.contract)
        self.assertEqual(original,self.raw);self.assertTrue(audit['protected_geometry_unchanged']);self.assertEqual(audit['protected_parts'],['panel'])
        for key in ('parts','mates','bindings','containments','clearances','symmetries','root_position','root_rotation','shapes'):self.assertEqual(revised[key],self.raw[key])
    def test_patch_cannot_modify_panel_constraint_or_port_role(self):
        scope,patch=self.patch();patch['ports']=[deepcopy(next(v for v in self.raw['ports'] if v['part']=='panel'))]
        with self.assertRaises(ValueError):local.apply(self.raw,patch,scope,self.contract)
        scope,patch=self.patch();patch['mates']=[]
        with self.assertRaises(ValueError):local.apply(self.raw,patch,scope,self.contract)
        scope,patch=self.patch();patch['ports'][0]['kind']='face'
        with self.assertRaises(ValueError):local.apply(self.raw,patch,scope,self.contract)
    def test_stale_scope_duplicate_or_unchanged_edit_rejected(self):
        scope,patch=self.patch();scope['allowed_parts'].append('panel')
        with self.assertRaises(ValueError):local.apply(self.raw,patch,scope,self.contract)
        scope,patch=self.patch();patch['ports']*=2
        with self.assertRaises(ValueError):local.apply(self.raw,patch,scope,self.contract)
        scope,patch=self.patch();patch['ports']=[deepcopy(next(p for p in self.raw['ports'] if p['id']==patch['ports'][0]['id']))]
        with self.assertRaises(ValueError):local.apply(self.raw,patch,scope,self.contract)
    def test_shared_shape_edit_is_limited_to_its_consumers(self):
        scope=local.scope(self.raw,self.report);shape=deepcopy(next(s for s in self.raw['shapes'] if s['id'] in scope['allowed_shapes']))
        shape['forms'][0]['size'][0]*=.99
        patch={'base_sha256':scope['base_sha256'],'status':'patch','reason':'','shapes':[shape],'ports':[]}
        revised,audit=local.apply(self.raw,patch,scope,self.contract)
        self.assertTrue(audit['protected_geometry_unchanged']);self.assertEqual(revised['parts'],self.raw['parts'])
    def test_explicit_unsupported_is_not_a_success_or_edit(self):
        scope=local.scope(self.raw,self.report);patch={'base_sha256':scope['base_sha256'],'status':'unsupported','reason':'Requires unavailable scope','shapes':[],'ports':[]}
        revised,audit=local.apply(self.raw,patch,scope,self.contract)
        self.assertIsNone(revised);self.assertEqual(audit['status'],'unsupported')

if __name__=='__main__':unittest.main()
