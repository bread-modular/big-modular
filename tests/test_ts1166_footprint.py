"""Requested seller drawing is a hole-pattern candidate, not a 2HP fit approval."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = 'SW_TS1166VW_RightAngle_THT_P4.50_P7.00_Row2.50mm'
FP = ROOT/'hardware/BigModular.pretty'/(NAME+'.kicad_mod')


def native(*args):
    return subprocess.run(['/usr/bin/python3', '-B', str(ROOT/'tools/verify_ts1166.py'),
                           *map(str, args)], cwd=ROOT, capture_output=True, text=True)


class TS1166FootprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = native()
        if r.returncode:
            raise AssertionError(r.stdout+r.stderr)
        cls.report = json.loads(r.stdout)

    def test_uploaded_hole_pattern_and_hand_solder_rings(self):
        p = self.report['pads']
        self.assertEqual(p['1']['XY_mm'], [-2.25, 0])
        self.assertEqual(p['2']['XY_mm'], [2.25, 0])
        self.assertEqual(p['MP1']['XY_mm'], [-3.5, -2.5])
        self.assertEqual(p['MP2']['XY_mm'], [3.5, -2.5])
        self.assertEqual([p[k]['drill_mm'] for k in p], [1, 1, 1.5, 1.5])
        self.assertEqual([p[k]['annular_ring_mm'] for k in p], [.5, .5, .55, .55])
        self.assertGreater(self.report['minimum_land_clearance_mm'], .49)

    def test_width_conflict_is_not_hidden_or_promoted(self):
        r = self.report
        self.assertFalse(r['fabrication_ready'])
        self.assertFalse(r['installed_on_active_board'])
        self.assertEqual(r['active_SW1_retained'], 'SW_TL3340AF160QG_HandSolder')
        self.assertFalse(r['fit']['fits_current_stack'])
        self.assertEqual(r['fit']['nominal_overhang_mm'], 2)
        self.assertEqual(r['fit']['H_choice_mm'], 4.3)
        self.assertIn('provisional', r['courtyard_status'].lower())

    def reject_mutation(self, old, new, expected_error):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/(NAME+'.kicad_mod')
            content = FP.read_text()
            self.assertIn(old, content)
            path.write_text(content.replace(old, new))
            r = native('--footprint', path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(expected_error, r.stdout+r.stderr)

    def test_same_name_supplier_row215_not_silently_substituted(self):
        self.reject_mutation(' -2.5)', ' -2.15)', 'hole pattern mismatch')

    def test_old_apem_signal_pitch_not_reused(self):
        self.reject_mutation('(at -2.25 0)', '(at -2.5 0)', 'hole pattern mismatch')

    def test_old_apem_mount_drill_not_reused(self):
        self.reject_mutation('(drill 1.5)', '(drill 1.3)', 'hole pattern mismatch')

    def test_mounting_tabs_not_collapsed_into_a_signal_pad(self):
        self.reject_mutation('(pad "MP1"', '(pad "1"', 'AssertionError')

    def test_stem_height_does_not_cure_lateral_interference(self):
        code = '''import sys,json
sys.path.insert(0,'tools')
from verify_ts1166 import fit_report
from stack_geometry import geometry
print(json.dumps([fit_report(geometry(),h) for h in [4.3,5,6,7,20]]))
'''
        r = subprocess.run(['/usr/bin/python3','-B','-c',code], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        reports = json.loads(r.stdout)
        self.assertTrue(all(x['nominal_overhang_mm']==2 and not x['fits_current_stack'] for x in reports))

    def test_report_output_cannot_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'existing.json'
            path.write_text('keep this evidence\n')
            r = native('--output', path)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(path.read_text(), 'keep this evidence\n')


if __name__ == '__main__':
    unittest.main()
