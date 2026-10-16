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
