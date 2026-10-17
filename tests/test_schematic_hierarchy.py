"""Presentation and connectivity guards; no PCB regeneration, routing or network."""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from schematic_connectivity import Connectivity
from sexp import nodes, one


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SchematicHierarchyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = Connectivity(ROOT/'hardware')

    def test_every_current_pin_and_no_connect_is_preserved(self):
        audit = json.loads((ROOT/'docs/pin-net-audit.json').read_text())
        expected = {(ref, pin): net for ref, pins in audit.items() for pin, net in pins.items()}
        self.assertEqual(self.graph.named_pins(), expected)
        # Derive the active-ref count from the actual BOM; 043 will add local caps.
        with (ROOT/'BOM.csv').open() as f:
            bom_refs={r['Reference'] for r in csv.DictReader(f)}
        self.assertEqual({r for r in self.graph.refs if not r.startswith('#')},bom_refs)
        self.assertEqual(len(self.graph.hierarchy_links), 22)
        self.assertNotIn('D1', self.graph.refs)

    def test_page_structure_and_component_distribution(self):
        counts = {}
        for ref, (filename, symbol) in self.graph.refs.items():
            if not ref.startswith('#'):counts[filename] = counts.get(filename, 0)+1
            path = one(one(one(symbol, 'instances'), 'project'), 'path')[1]
            self.assertEqual(path.count('/'), 2)
        with (ROOT/'BOM.csv').open() as f:
            expected_counts={}
            for row in csv.DictReader(f):
                key=row['Block']+'.kicad_sch'
                expected_counts[key]=expected_counts.get(key,0)+1
        self.assertEqual(counts, expected_counts)
        root = self.graph.sheets['big_modular.kicad_sch']
        self.assertEqual(one(root, 'paper')[1], 'User')
        self.assertEqual([one(s, 'paper')[1] for n, s in self.graph.sheets.items() if n!='big_modular.kicad_sch'], ['User']*6)
        pages = {one(one(one(s, 'instances'), 'project'), 'path')[2][1] for s in nodes(root, 'sheet')}
        self.assertEqual(pages, {str(i) for i in range(2,8)})

    def test_sensitive_local_networks_are_wires_not_label_only(self):
        from electrical_checks import LOCAL
        pairs = LOCAL
        for a,b in pairs:
            with self.subTest(pins=(a,b)):self.assertTrue(self.graph.wire_connected(a,b))
        self.assertFalse(self.graph.wire_connected(('U2','8'),('U2','9')))
        self.assertFalse(self.graph.wire_connected(('U4','17'),('U4','19')))

    def test_directional_ports_match_and_touch_component_wires(self):
        g=self.graph
        for (filename,name),point in g.ports.items():
            expected=('passive' if name=='GND' else 'output' if
                filename.startswith('01_') or (filename.startswith('02_') and name=='VPROT') or
                (filename.startswith('03_') and name in ('MID','P5')) or
                (filename.startswith('04_') and name in ('PRAW','NRAW')) or
                (filename.startswith('05_') and name in ('P12','N12')) else 'input')
            self.assertEqual(g.port_types[(filename,name)],expected,(filename,name))
            self.assertTrue(any(p[0]==filename and g.find(p)==g.find(point) for p in g.pins.values()),(filename,name,'floating port bank'))

    def test_root_power_flow_is_real_wires(self):
        g=self.graph
        pairs=[(0,1,'VIN9'),(1,2,'VPROT'),(2,3,'MID'),(2,5,'P5'),(3,4,'PRAW'),(3,4,'NRAW'),(4,5,'P12'),(4,5,'N12')]
        from render_schematic import SHEET_NAMES
        for a,b,n in pairs:
            self.assertEqual(g.find(g.sheet_pins[(SHEET_NAMES[a]+'.kicad_sch',n)]),g.find(g.sheet_pins[(SHEET_NAMES[b]+'.kicad_sch',n)]))

    def test_easy_local_connections_and_harness_are_wired(self):
        g=self.graph
        pairs=[(('R32','2'),('D10','2')),(('U2','1'),('R4','1')),(('U2','1'),('R6','1')),(('U2','1'),('C2','1')),(('U3','3'),('U5','3')),(('R38','1'),('U4','5'))]
        pairs += [(('J7',str(pin)),(ref,'1')) for pin,ref in [(9,'R25'),(1,'R26'),(11,'R27')]]
        for a,b in pairs:self.assertTrue(g.wire_connected(a,b),(a,b))
        self.assertEqual(one(g.refs['J7'][1],'on_board')[1],'yes')
        self.assertFalse(g.wire_connected(('SW1','MP'),('SW1','2')))

    def test_opposite_child_port_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)
            for name in self.graph.sheets:shutil.copyfile(ROOT/'hardware'/name,target/name)
            child=target/'07_output_rails.kicad_sch'
            changed,count=re.subn(r'(\(hierarchical_label\s+"P5"\s+\(shape\s+)input',
                                  r'\1output',child.read_text(),count=1)
            self.assertEqual(count,1,'negative-control mutation must actually change the saved presentation')
            child.write_text(changed)
            with self.assertRaisesRegex(AssertionError,'direction mismatch'):Connectivity(target)

    def test_build_instructions_cover_current_sources(self):
        for filename in self.graph.sheets:self.assertIn(filename,(ROOT/'docs/build.md').read_text())

    def test_deterministic_candidate_mode_preserves_all_sources(self):
        inputs = [p for p in (ROOT/'hardware').rglob('*') if p.is_file()]
        inputs += [ROOT/'BOM.csv', ROOT/'docs/pin-net-audit.json']
        before = {str(p): digest(p) for p in inputs}
        with tempfile.TemporaryDirectory(prefix='big-modular-schematic-') as temp:
            output = Path(temp)/'new candidate'
            command = [sys.executable, '-B', str(ROOT/'tools/build_project.py'), '--schematic-only', '--output', str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(list(output.glob('*.kicad_pcb')))
            self.assertEqual((output/'BOM.csv').read_bytes(),(ROOT/'BOM.csv').read_bytes())
            self.assertEqual((output/'pin-net-audit.json').read_bytes(),(ROOT/'docs/pin-net-audit.json').read_bytes())
            for name in self.graph.sheets:
                self.assertEqual((output/name).read_bytes(), (ROOT/'hardware'/name).read_bytes(), name)
            self.assertEqual(Connectivity(output).named_pins(), self.graph.named_pins())
            for local in [ROOT/'hardware/BigModular.kicad_sym',*(ROOT/'hardware/BigModular.pretty').glob('*.kicad_mod')]:
                self.assertEqual((output/local.relative_to(ROOT/'hardware')).read_bytes(),local.read_bytes(),local.name)
            # Existing destinations, including source hardware/, cannot be overwritten.
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(again.returncode, 0)
        self.assertEqual(before, {str(p): digest(p) for p in inputs})

    def test_missing_child_and_broken_port_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)
            for name in self.graph.sheets:shutil.copyfile(ROOT/'hardware'/name, target/name)
            child=target/'07_output_rails.kicad_sch'
            content=child.read_text()
            child.write_text(content.replace('(hierarchical_label "P5"', '(hierarchical_label "WRONG_PORT"', 1))
            with self.assertRaisesRegex(AssertionError, 'port mismatch'):Connectivity(target)
            child.unlink()
            with self.assertRaisesRegex(AssertionError, 'Missing or orphan'):Connectivity(target)


if __name__ == '__main__':
    unittest.main()
