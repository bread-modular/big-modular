"""Bounded resources: synthetic files only, no model-tree scans/native runtime."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native import Error, kicad, replace_paths, sha256
from project import Plan, Project, new_output

STEP = "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
WRL = '#VRML V2.0 utf8\nShape { geometry Box { size 1 2 3 } }\n'
TRANSFORM = '(offset (xyz 1.25 -2.5 3.75)) (scale (xyz 0.5 1.25 2)) (rotate (xyz 12 34 56))'


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bounded models with spaces ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'source'; self.source.mkdir()
        self.models = self.root/'models with spaces'; self.models.mkdir()
        for name in ('first model.STEP', 'second.stp', 'unused.step'):
            (self.models/name).write_text(STEP)
        (self.models/'third.wrl').write_text(WRL)
        self.board = self.source/'demo.kicad_pcb'
        self.board.write_text('(kicad_pcb)')
        self.sch = self.source/'demo.kicad_sch'; self.sch.write_text('(kicad_sch)')
        self.selection = Project(self.source, self.board, self.sch,
                                 variables={'MODELS': str(self.models)})

    def declare(self, *values, tail=''):
        self.board.write_text('(kicad_pcb (footprint "Synthetic" '+''.join(
            f'(model {json.dumps(value)} {TRANSFORM})' for value in values)+')'+tail+')')

    def test_all_models_hashed_staged_and_relocated_with_existing_mappings(self):
        self.declare('${MODELS}/first model.STEP', '${MODELS}/second.stp', '${MODELS}/third.wrl', '${MODELS}/second.stp')
        pretty = self.source/'Parts.pretty'; pretty.mkdir()
        mod = pretty/'P.kicad_mod'
        mod.write_text('(footprint "P" (model "${MODELS}/first model.STEP" '+TRANSFORM+') (model "${MODELS}/third.wrl" '+TRANSFORM+'))')
        (self.source/'fp-lib-table').write_text('(fp_lib_table (lib (name "Parts") (type "KiCad") (uri "${KIPRJMOD}/Parts.pretty")))')
        child = self.source/'child with spaces.kicad_sch'; child.write_text('(kicad_sch)')
        self.sch.write_text('(kicad_sch (sheet (property "Sheetfile" "${KIPRJMOD}/child with spaces.kicad_sch")))')
        before = {p:sha256(p) for p in self.source.rglob('*') if p.is_file()}
        plan = Plan(self.selection)
        self.assertEqual(len(plan.model_rewrites[self.board]), 3)
        self.assertEqual(len(plan.model_rewrites[mod]), 2)
        self.assertNotIn(self.models/'unused.step', plan.files)
        for name in ('first model.STEP', 'second.stp', 'third.wrl'):
            self.assertEqual(plan.snapshot()[str(self.models/name)]['sha256'], sha256(self.models/name))
        out = self.root/'candidate'; out.mkdir()
        board, sch, records = plan.stage(out)
        self.assertEqual({r['kind'] for r in records}, {'model', 'uri', 'property'})
        # The resource and legacy rewrite namespaces compose, even on one file.
        expected = replace_paths(self.board.read_text(), 'model', next(r['path_bindings'] for r in records if r['source']==str(self.board)))
        self.assertEqual(board.read_text(), expected)
        self.assertEqual(board.read_text().count(TRANSFORM), 4)
        self.assertEqual(before, {p:sha256(p) for p in before})
        self.assertFalse(any(p.is_symlink() for p in out.rglob('*')))
        self.assertIn('child with spaces', sch.read_text())
        plan.verify_sources(plan.snapshot())
        with self.assertRaises(Error): new_output(self.models/'candidate', plan)
        snapshot = plan.snapshot()
        (self.models/'second.stp').write_text(STEP+'\n')
        with self.assertRaisesRegex(Error, 'SOURCE CHANGED'): plan.verify_sources(snapshot)

    def test_same_basename_models_do_not_alias_or_overwrite(self):
        other=self.models/'other'; other.mkdir()
        (other/'first model.STEP').write_text(STEP+'\n')
        self.declare('${MODELS}/first model.STEP','${MODELS}/other/first model.STEP')
        plan=Plan(self.selection); out=self.root/'collision-free'; out.mkdir()
        _,_,records=plan.stage(out)
        mapping=next(r['path_bindings'] for r in records if r['kind']=='model')
        self.assertEqual(len(set(mapping.values())),2)
        self.assertNotEqual(Path(mapping['${MODELS}/first model.STEP']).read_bytes(),
                            Path(mapping['${MODELS}/other/first model.STEP']).read_bytes())

    def test_kiprjmod_relative_config_and_local_file_paths(self):
        (self.source/'local.wrl').write_text(WRL)
        self.declare('${KIPRJMOD}/local.wrl', 'local.wrl')
        self.assertIn(self.source/'local.wrl', Plan(self.selection).files)
        self.selection.config = self.root/'profile.json'
        self.selection.variables = {'MODELS': 'models with spaces'}
        self.declare('${MODELS}/second.stp')
        self.assertIn(self.models/'second.stp', Plan(self.selection).files)

    def test_unresolved_missing_uri_escaping_unsupported_and_ambient_variables(self):
        values = ('${MISSING}/x.step', '${MODELS}/missing.step', '${MODELS}/../outside.step',
                  '../models with spaces/second.stp', 'https://example.invalid/x.step', 'file:///x.step',
                  'C:\\x.step', ':alias:x.step', str(self.models/'second.stp'), '${MODELS}/third.obj',
                  '${MODELS}/', '${MODELS}/x.step.gz', '${MODELS}/x\n.step', '${MODELS}/nested/${OTHER}.step')
        with patch.dict('os.environ', MISSING=str(self.models)):
            for value in values:
                with self.subTest(value=value):
                    self.declare(value)
                    with self.assertRaises(Error): Plan(self.selection)
        with self.assertRaises(Error): Plan(Project(self.source, self.board, self.sch, dependencies=[self.models]))

    def test_broken_symlinks_file_and_directory_aliases_fail_closed(self):
        for name, target in (('broken.step', 'missing.step'), ('inbound.step', 'second.stp'), ('escape.step', '../outside.step')):
            link = self.models/name; link.symlink_to(target)
            self.declare('${MODELS}/'+name)
            with self.subTest(name=name), self.assertRaises(Error): Plan(self.selection)
        alias = self.root/'alias'; alias.symlink_to(self.models, target_is_directory=True)
        self.selection.variables = {'MODELS': str(alias)}
        self.declare('${MODELS}/second.stp')
        with self.assertRaises(Error): Plan(self.selection)

    def test_aggregate_file_and_byte_bounds_include_resources(self):
        self.declare('${MODELS}/first model.STEP', '${MODELS}/second.stp')
        for setting, value in (('MAX_FILES', 2), ('MAX_BYTES', self.board.stat().st_size+1)):
            with self.subTest(setting=setting), patch('project.'+setting, value), self.assertRaisesRegex(Error, 'bound exceeded'):
                Plan(self.selection)

    def test_nonempty_embedded_images_fonts_malformed_and_secondary_resources(self):
        for declaration in ('(embedded_files (file))', '(embedded_files (file (name "")))', '(image)',
                            '(image (data ""))', '(embedded_fonts yes)', '(embedded_fonts)', '(model)'):
            self.declare(tail=declaration)
            with self.subTest(declaration=declaration), self.assertRaises(Error): Plan(self.selection)
        self.declare(tail='(embedded_files) (embedded_fonts no)')
        Plan(self.selection)
        for suffix, text in (('.wrl', WRL+'Inline { url ["other.wrl"] }'),
                             ('.wrl', WRL+'EXTERNPROTO X [] ["other.wrl"]'),
                             ('.wrl', WRL+'Shape { appearance Appearance { texture ImageTexture { url "a.png" } } }'),
                             ('.step', STEP.replace('DATA;', 'DATA;\n#1=EXTERNAL_SOURCE(\'other.step\');')),
                             ('.stp', STEP.replace('DATA;', 'REFERENCE;\nENDSEC;\nDATA;')),
                             ('.step', 'not STEP'), ('.wrl', 'not VRML')):
            name = 'external'+suffix; (self.models/name).write_text(text)
            self.declare('${MODELS}/'+name)
            with self.subTest(text=text), self.assertRaises(Error): Plan(self.selection)


if __name__ == '__main__': unittest.main()
