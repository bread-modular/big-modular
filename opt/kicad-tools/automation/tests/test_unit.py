"""Stdlib-only schema, identity, path and transaction-precondition tests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import api
import schema
from fixtures import uid, operations, text_op, hashes


class SchemaTests(unittest.TestCase):
    def test_valid_operations_and_copy_isolation(self):
        doc=operations(text_op()); result=schema.validate(doc); result['operations'][0]['text']='changed'
        self.assertEqual(doc['operations'][0]['text'],'SYNTHETIC')

    def test_numeric_and_schema_types(self):
        for value in (True,float('nan'),float('inf'),'1',1001,0.0000001):
            with self.subTest(value=value):
                doc=operations(text_op()); doc['operations'][0]['at'][0]=value
                with self.assertRaises((api.Error,ValueError)): schema.validate(doc)
        for version in (True,1.0,2,'1'):
            doc=operations(text_op()); doc['schema_version']=version
            with self.assertRaises(api.Error): schema.validate(doc)

    def test_unknown_fields_everywhere(self):
        for op in ({**text_op(),'surprise':0},{'op':'move_footprint','target':{'ref':'R1','hidden':1},'at':[0,0]},
                   {'op':'add_polyline','uuid':uid('p'),'net':'N','layer':'F.Cu','width_mm':0.2,'start':{'pad':{'ref':'R1','number':'1','hidden':1}},'end':{'uuid':uid('e')}}):
            with self.assertRaises(api.Error): schema.validate(operations(op))
        doc=operations(text_op()); doc['more']=[]
        with self.assertRaises(api.Error): schema.validate(doc)

    def test_duplicate_json_keys_and_nonfinite(self):
        for text in ('{"schema_version":1,"schema_version":1,"operations":[]}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(api.Error): schema.loads(text)

    def test_uuid_refs_and_duplicates(self):
        for ident in ('bad','00000000-0000-0000-0000-000000000000',uid('upper').upper()):
            op=text_op(); op['uuid']=ident
            with self.assertRaises(api.Error): schema.validate(operations(op))
        with self.assertRaises(api.Error): schema.validate(operations(text_op(),text_op()))
        for ref in ('R?','R 1','../R1',''):
            with self.assertRaises(api.Error): schema.validate(operations({'op':'move_footprint','target':{'ref':ref},'at':[0,0]}))

    def test_geometry_and_bounds(self):
        for poly in ([[0,0],[1,1],[0,1],[1,0]], [[0,0],[1,0],[2,0]], [[0,0],[1,0],[1,1],[0,0]]):
            with self.assertRaises(api.Error): schema.validate(operations({'op':'add_outline','uuid':uid('edge'),'polygon':poly,'width_mm':0.05}))
        with self.assertRaises(api.Error): schema.validate(operations({'op':'add_via','uuid':uid('via'),'at':[0,0],'net':'N','diameter_mm':0.3,'drill_mm':0.3}))
        with self.assertRaises(api.Error): schema.validate({'schema_version':1,'operations':[text_op(str(i)) for i in range(257)]})
        schema.validate(operations({'op':'add_outline','uuid':uid('edge'),'polygon':[[0,0],[2,0],[2,2],[0,2]],'width_mm':0.05}))

    def test_no_deferred_operations(self):
        for op in ('add_arc','lock','unlock','eval','set','move_symbol','auto_place'):
            with self.assertRaises(api.Error): schema.validate(operations({'op':op}))

    def test_relative_footprint_and_strict_mechanical(self):
        op={'op':'add_footprint','uuid':uid('fp'),'file':'part.kicad_mod','mechanical_only':True,'at':[0,0],'rotation_deg':0,'side':'back'}
        with self.assertRaises(api.Error): schema.validate(operations(op))
        self.assertTrue(Path(schema.validate(operations(op),'/tmp')['operations'][0]['file']).is_absolute())
        op['file']='child/../part.kicad_mod'
        self.assertEqual(schema.validate(operations(op),'/tmp')['operations'][0]['file'],'/tmp/part.kicad_mod')
        for key,value in [('pad_nets',{}),('reference','M1')]:
            with self.assertRaises(api.Error): schema.validate(operations({**op,key:value}),'/tmp')

    def test_deterministic_uuid_generation(self):
        self.assertEqual(schema.child_uuid(uid('fp'),1),schema.child_uuid(uid('fp'),1))
        self.assertNotEqual(schema.child_uuid(uid('fp'),1),schema.child_uuid(uid('fp'),2))


class RootMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='root metadata '); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.source=self.root/'source'; self.source.mkdir()
        self.sch=self.source/'demo.kicad_sch'; self.pro=self.sch.with_suffix('.kicad_pro')
        (self.source/'demo.kicad_pcb').write_text('(kicad_pcb)')
        self.sch.write_text('(kicad_sch (uuid "'+uid('schematic')+'"))')
        self.entry={'filename':self.sch.name,'name':self.sch.stem,'uuid':uid('schematic')}
        self.settings={'schematic':{'top_level_sheets':[self.entry]}}
        self.write(self.settings)

    def write(self,settings):
        self.pro.write_text(json.dumps(settings,indent=2)+'\n')

    def closure(self):
        return api._closure(api.select(project_dir=self.source))

    def test_exact_root_is_hash_covered_and_metadata_survives_stage_and_relocation(self):
        before=hashes(self.source); original=self.pro.read_bytes(); closure=self.closure()
        self.assertEqual(closure.snapshot()[str(self.sch)]['sha256'],before[self.sch.name])
        self.assertEqual(closure.snapshot()[str(self.pro)]['sha256'],before[self.pro.name])
        output=self.root/'candidate'; output.mkdir()
        board,_,_=closure.stage(output); api._rebind(closure,output)
        self.assertEqual(board.with_suffix('.kicad_pro').read_bytes(),original)
        moved=output.rename(self.root/'relocated')
        copied=moved/board.relative_to(output)
        self.assertEqual(copied.with_suffix('.kicad_pro').read_bytes(),original)
        api._closure(api.select(project_dir=copied.parent))
        self.assertEqual(hashes(self.source),before); closure.verify_sources(closure.snapshot())
        self.pro.write_text(original.decode()+'\n')
        with self.assertRaisesRegex(api.Error,'SOURCE CHANGED'): closure.verify_sources(closure.snapshot())

    def test_malformed_multiroot_path_name_and_uuid_metadata_fail_closed(self):
        entries=[None,{},[],[self.entry,self.entry],[{}],['demo.kicad_sch']]
        for field,values in {
            'filename':['other.kicad_sch','./demo.kicad_sch','sub/../demo.kicad_sch',
                        '../source/demo.kicad_sch',str(self.sch),'${KIPRJMOD}/demo.kicad_sch',
                        'file://'+str(self.sch),'demo.sch','demo.KICAD_SCH',None],
            'name':['other','',None],
            'uuid':[uid('leaf'),uid('schematic').upper(),'bad','00000000-0000-0000-0000-000000000000',None],
        }.items():
            entries.extend([{**self.entry,field:value}] for value in values)
        entries.extend([[{**self.entry,'unknown':True}],[{k:v for k,v in self.entry.items() if k!='uuid'}]])
        for value in entries:
            with self.subTest(value=value):
                self.write({'schematic':{'top_level_sheets':value}})
                with self.assertRaises(api.Error): self.closure()

    def test_unknown_contexts_resources_and_ignored_rules_are_still_blocked(self):
        bad=[{'top_level_sheets':[self.entry]}, {'other':self.settings},
             {'schematic':{'other':{'top_level_sheets':[self.entry]}}}]
        for suffix in ('.kicad_sch','.kicad_wks','.kicad_pcb','.kicad_sym','.kicad_mod','.step','.stp','.wrl'):
            bad.append({**self.settings,'unknown_resource':'demo'+suffix})
        bad.extend([{**self.settings,'schematic':{**self.settings['schematic'],'drawing_sheet':'layout'}},
                    {**self.settings,'board':{'rule_severities':{'clearance':'ignore'}}}])
        for settings in bad:
            with self.subTest(settings=settings):
                self.write(settings)
                with self.assertRaises(api.Error): self.closure()

    def test_covered_child_and_other_project_metadata_are_not_selected_root(self):
        child=self.source/'child.kicad_sch'
        child.write_text('(kicad_sch (uuid "'+uid('leaf')+'"))')
        self.sch.write_text('(kicad_sch (uuid "'+uid('schematic')+'") (sheet (property "Sheetfile" "child.kicad_sch")))')
        self.write({'schematic':{'top_level_sheets':[{'filename':child.name,'name':child.stem,'uuid':uid('leaf')}]}})
        with self.assertRaises(api.Error): self.closure()
        self.write(self.settings)
        child.with_suffix('.kicad_pro').write_text(json.dumps(self.settings))
        with self.assertRaises(api.Error): self.closure()

    def test_external_resolved_root_and_missing_or_duplicate_root_uuid_fail_closed(self):
        for nodes in ('','(uuid "'+uid('leaf')+'")',2*('(uuid "'+uid('schematic')+'")')):
            with self.subTest(nodes=nodes):
                self.sch.write_text('(kicad_sch '+nodes+')')
                with self.assertRaises(api.Error): self.closure()
        external=self.root/'external.kicad_sch'
        external.write_text('(kicad_sch (uuid "'+uid('schematic')+'"))')
        self.sch.unlink(); self.sch.symlink_to(external)
        with self.assertRaises(api.Error): self.closure()


class IdentityTests(unittest.TestCase):
    def test_compare_identities_not_totals(self):
        report=lambda ident:{'violations':[{'type':'shorting_items','severity':'error','description':'short','items':[{'uuid':ident}]}],'unconnected_items':[],'schematic_parity':[]}
        left=api._identities(report(uid('a')),'drc'); right=api._identities(report(uid('b')),'drc')
        delta=api.compare_findings(left,right)
        self.assertEqual(len(delta['added']),1); self.assertEqual(len(delta['removed']),1); self.assertEqual(delta['retained'],[])

    def test_unknown_report_never_passes(self):
        for report in ({},{'violations':[]}, {'violations':[{}],'unconnected_items':[],'schematic_parity':[]}):
            with self.assertRaises(api.Error): api._identities(report,'drc')

    def test_apply_tamper_fails_before_any_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'candidate'
            doc={'schema_version':1,'kind':'pcb_edit_plan','operations':operations(text_op()),'preconditions':{},'changes':{},'source_writes':False,'status':'planned_not_checked','caveats':[],'native_diagnostics':{},'plan_sha256':'bad'}
            with self.assertRaises(api.Error): api.apply(doc,output)
            self.assertFalse(output.exists())

    def test_relocatable_model_paths_cannot_escape_or_remain_unbound(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); board=root/'demo.kicad_pcb'; model=root/'m.step'; model.write_text('resource')
            for value in ('${UNDECLARED}/m.step',str(model),'../outside.step','${KIPRJMOD}/../outside.step'):
                board.write_text('(kicad_pcb (footprint "F" (model '+json.dumps(value)+')))')
                with self.subTest(value=value), self.assertRaises(api.Error): api._relocatable(root,root)
            board.write_text('(kicad_pcb (footprint "F" (model "${KIPRJMOD}/m.step")))')
            api._relocatable(root,root)
            model.unlink()
            with self.assertRaises(api.Error): api._relocatable(root,root)

    def test_duplicate_identity_and_ignored_rule_admission_are_not_waived(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); board=root/'demo.kicad_pcb'; sch=root/'demo.kicad_sch'
            ident=uid('duplicate'); sch.write_text('(kicad_sch)')
            board.write_text('(kicad_pcb (property "A" "a" (uuid "'+ident+'")) (property "B" "b" (uuid "'+ident+'")))')
            with self.assertRaisesRegex(api.Error,'Duplicate serialized board UUIDs'): api._closure(api.select(project_dir=root))
            board.write_text('(kicad_pcb)')
            (root/'demo.kicad_pro').write_text('{"board":{"design_settings":{"rule_severities":{"clearance":"ignore"}}}}')
            with self.assertRaisesRegex(api.Error,'Ignored project rule'): api._closure(api.select(project_dir=root))

    def test_new_output_rejects_collision_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); (path/'used').mkdir(); (path/'alias').symlink_to(path/'used',target_is_directory=True)
            for target in (path/'used',path/'alias'/'child'):
                with self.assertRaises(api.Error): api.project.new_output(target)

    def test_promote_restores_model_bindings_by_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); project=root/'hardware'; project.mkdir()
            models=project/'_kicad_models'/'committed'; models.mkdir(parents=True)
            (models/'part.step').write_text('MODEL BYTES')
            board=project/'demo.kicad_pcb'; board.write_text('(kicad_pcb (model "${KIPRJMOD}/_kicad_models/committed/part.step"))')
            candidate=root/'candidate'; staged=candidate/'inputs'/'hardware'
            (staged/'_kicad_models'/'staged').mkdir(parents=True)
            (staged/'_kicad_models'/'staged'/'part.step').write_text('MODEL BYTES')
            copy=staged/'demo.kicad_pcb'
            copy.write_text('(kicad_pcb (model "${KIPRJMOD}/_kicad_models/staged/part.step"))')
            (candidate/'result.json').write_text(json.dumps({'status':'accepted','accepted':True,'board':'inputs/hardware/demo.kicad_pcb'}))
            before=board.read_text()
            dry=api.promote(candidate,board,dry_run=True)
            self.assertEqual(dry['status'],'dry_run')
            self.assertFalse(dry['source_writes'])
            self.assertEqual(dry['remapped'],[{'from':'_kicad_models/staged/part.step','to':'_kicad_models/committed/part.step'}])
            self.assertEqual(board.read_text(),before)
            result=api.promote(candidate,board)
            self.assertEqual(result['status'],'promoted')
            self.assertIn('_kicad_models/committed/part.step',board.read_text())
            self.assertNotIn('staged/part.step',board.read_text())

    def test_promote_refuses_unresolved_models_and_unaccepted_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); project=root/'hardware'; project.mkdir()
            board=project/'demo.kicad_pcb'; board.write_text('(kicad_pcb)')
            candidate=root/'candidate'; staged=candidate/'inputs'/'hardware'; staged.mkdir(parents=True)
            copy=staged/'demo.kicad_pcb'
            copy.write_text('(kicad_pcb (model "${KIPRJMOD}/_kicad_models/missing/part.step"))')
            (candidate/'result.json').write_text(json.dumps({'status':'accepted','accepted':True,'board':'inputs/hardware/demo.kicad_pcb'}))
            with self.assertRaisesRegex(api.Error,'Unresolved model bindings'): api.promote(candidate,board)
            self.assertEqual(board.read_text(),'(kicad_pcb)')
            (candidate/'result.json').write_text(json.dumps({'status':'rejected','accepted':False,'board':'inputs/hardware/demo.kicad_pcb'}))
            with self.assertRaisesRegex(api.Error,'Only an accepted candidate'): api.promote(candidate,board)


if __name__=='__main__': unittest.main()
