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
        self.assertEqual(sum(not r.startswith('#') for r in self.graph.refs), 127)
        self.assertEqual(len(self.graph.hierarchy_links), 59)
        self.assertNotIn('D1', self.graph.refs)

    def test_page_structure_and_component_distribution(self):
        counts = {}
        for ref, (filename, symbol) in self.graph.refs.items():
            if not ref.startswith('#'):counts[filename] = counts.get(filename, 0)+1
            path = one(one(one(symbol, 'instances'), 'project'), 'path')[1]
            self.assertEqual(path.count('/'), 2)
        self.assertEqual(counts, {'01_input_protection.kicad_sch':10,'02_hardgate.kicad_sch':17,'03_bucks.kicad_sch':18,'04_bipolar.kicad_sch':23,'05_diagnostics.kicad_sch':14,'06_sensing.kicad_sch':40,'07_output_rails.kicad_sch':5})
        root = self.graph.sheets['big_modular.kicad_sch']
        self.assertEqual(one(root, 'paper')[1], 'User')
        self.assertEqual([one(s, 'paper')[1] for n, s in self.graph.sheets.items() if n!='big_modular.kicad_sch'], ['User']*7)
        pages = {one(one(one(s, 'instances'), 'project'), 'path')[2][1] for s in nodes(root, 'sheet')}
        self.assertEqual(pages, {str(i) for i in range(2,9)})

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
            expected=('passive' if name=='GND' or (filename.startswith('07_') and name in ('ANA_MID','MID','VBUS_RAW','VBUS_FUSED'))
                      else 'bidirectional' if name in ('PD_SDA','PD_SCL')
                      else 'output' if (filename.startswith('01_') or
                           (filename.startswith('02_') and name in ('VPROT','EF_ENABLE','EF_FLT_N')) or
                           (filename.startswith('03_') and name in ('MID','P5')) or
                           (filename.startswith('04_') and name in ('P12','N12','ANA_MID')) or
                           (filename.startswith('06_') and name.startswith('ADC_')))
                      else 'input')
            self.assertEqual(g.port_types[(filename,name)],expected,(filename,name))
            self.assertTrue(any(p[0]==filename and g.find(p)==g.find(point) for p in g.pins.values()),(filename,name,'floating port bank'))

    def test_root_power_and_six_sense_paths_are_real_wires(self):
        g=self.graph
        pairs=[(0,1,n) for n in ('VBUS_FUSED','PD_PG_N','AUX3V3')]
        pairs += [(1,2,n) for n in ('VPROT','EF_ENABLE')]
        pairs += [(2,3,'MID'),(2,6,'P5'),(3,6,'P12'),(3,6,'N12')]
        pairs += [(5,4,n) for n in ('ADC_P12','ADC_N12','ADC_P5','ADC_MID','ADC_VBUS','ADC_VPROT')]
        from render_schematic import SHEET_NAMES
        for a,b,n in pairs:
            self.assertEqual(g.find(g.sheet_pins[(SHEET_NAMES[a]+'.kicad_sch',n)]),
                             g.find(g.sheet_pins[(SHEET_NAMES[b]+'.kicad_sch',n)]),(a,b,n))

    def test_easy_local_connections_and_harness_are_wired(self):
        g=self.graph
        pairs=[(('J8',str(pin)),(ref,'2')) for pin,ref in [(2,'R61'),(11,'R62'),(12,'R63'),(13,'R64'),(14,'R65'),(15,'R66')]]
        pairs += [(('R70','2'),('R64','1')),(('R71','2'),('R65','1')),
                  (('R66','1'),('SW1','1')),(('R66','1'),('C40','1')),(('R66','1'),('R41','2')),
                  (('R32','2'),('D10','2')),(('U11','8'),('C41','1')),
                  (('U2','1'),('R4','1')),(('U2','1'),('R6','1')),(('U2','1'),('C2','1')),
                  (('U3','3'),('U5','3')),(('U3','5'),('U5','5')),(('R38','1'),('U4','5'))]
        pairs += [(('J7',str(pin)),('J2',str(pin))) for pin in range(1,13)]
        pairs += [(('J7',str(pin)),(ref,'1')) for pin,ref in [(9,'R25'),(1,'R26'),(11,'R27')]]
        for a,b in pairs:
            self.assertTrue(g.wire_connected(a,b),(a,b))
        self.assertEqual(one(g.refs['J2'][1],'on_board')[1],'no')
        self.assertEqual(one(g.refs['J7'][1],'on_board')[1],'yes')
        self.assertFalse(g.wire_connected(('SW1','MP'),('SW1','2')))

    def test_opposite_child_port_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)
            for name in self.graph.sheets:shutil.copyfile(ROOT/'hardware'/name,target/name)
            child=target/'07_output_rails.kicad_sch'
            child.write_text(child.read_text().replace('(hierarchical_label "P5" (shape input)',
                                                       '(hierarchical_label "P5" (shape output)',1))
            with self.assertRaisesRegex(AssertionError,'direction mismatch'):Connectivity(target)

    def test_component_document_covers_the_entire_real_bom(self):
        text = (ROOT/'docs/component-guide.md').read_text()
        with (ROOT/'BOM.csv').open() as f:
            for row in csv.DictReader(f):
                ref=row['Reference']
                self.assertRegex(text, r'\b'+re.escape(ref)+r'\b', ref)
        for filename in self.graph.sheets:
            self.assertIn(filename, (ROOT/'docs/schematic-guide.md').read_text())

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
