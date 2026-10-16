"""A4.2 plain L and restored SMT reset regressions; no physical/strength qualification."""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from stack_geometry import geometry,carrier_outline
from m3_fit import verify_access


class M3AccessTests(unittest.TestCase):
    def test_two_plain_Ls_with_loose_nut_tool_access(self):
        r=verify_access(geometry(),carrier_outline())
        self.assertEqual(len(r['brackets']),2)
        self.assertTrue(r['identical_parts'] and r['plain_L'])
        self.assertEqual(r['all_fasteners'],'M3');self.assertEqual(r['wall_mm'],3)
        self.assertIn('soldered main PCB retained',r['service_condition'])
        self.assertEqual([p['side_bolt_exposure_min_mm'] for p in r['brackets']],[1,1])
        self.assertEqual([p['front_bolt_exposure_mm'] for p in r['brackets']],[1,1])
        self.assertEqual([p['front_nut_upright_clearance_mm'] for p in r['brackets']],[.125,.125])

    def test_corner_pattern_and_new_bracket_holes(self):
        g=geometry();self.assertEqual(g['rail_holes_mm'],[[2.42,3,3.2],[2.42,125.5,3.2]])
        self.assertEqual(g['panel_bracket_holes_mm'],[[6.4,22,3.2],[6.4,106.5,3.2]])
        self.assertEqual(g['carrier_holes_YZ_mm'],[[22,15],[106.5,15]])

    def test_unrelieved_board_blocks_front_leg(self):
        with self.assertRaisesRegex(AssertionError,'collides'):
            verify_access(geometry(),[(14,2),(114.5,2),(114.5,32),(14,32)])

    def test_proud_side_head_rejected(self):
        g=geometry();g['brackets']['side_head_recess_mm']=[-.2,0]
        with self.assertRaisesRegex(AssertionError,'side head must be flush'):
            verify_access(g,carrier_outline())

    def test_short_side_screw_rejected(self):
        g=geometry();g['brackets']['side_length_mm']=6
        with self.assertRaisesRegex(AssertionError,'nut not fully engaged'):
            verify_access(g,carrier_outline())

    def test_old_panel_hole_position_would_hit_upright(self):
        g=geometry();g['brackets']['front_hole_X_mm']=4.9
        with self.assertRaisesRegex(AssertionError,'front nut collides'):
            verify_access(g,carrier_outline())

    def test_oversized_countersink_rejected(self):
        g=geometry();g['brackets']['side_countersink_diameter_mm']=7
        with self.assertRaisesRegex(AssertionError,'insufficient material'):
            verify_access(g,carrier_outline())

    def test_front_tool_cannot_cross_the_upright(self):
        g=geometry();g['brackets']['front_tool_X_mm']=[2.5,30]
        with self.assertRaisesRegex(AssertionError,'path blocked'):
            verify_access(g,carrier_outline())

    def test_scad_is_plain_L_and_matches_contract(self):
        s=(ROOT/'hardware/mechanics/corner_braces.scad').read_text()
        vals={k:float(v) for k,v in re.findall(r'^([a-z_]+)\s*=\s*([\d.]+);',s,re.M)}
        self.assertEqual(vals,{'width_x':9.2,'width_y':10,'depth_z':18.4,'wall':3,
                             'front_x':6.3,'side_z':13.4,'clearance':3.2,
                             'countersink_diameter':6,'countersink_depth':1.4})
        self.assertEqual(s.count('cube('),2)
        self.assertEqual(s.count('rotate([90,0,0]) bracket();'),2)
        self.assertNotIn('$fn=6)',s)
        self.assertEqual(geometry()['brackets']['wall_mm'],vals['wall'])

    def test_drawing_regeneration_matches_contract(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'new'
            r=subprocess.run([sys.executable,'-B',str(ROOT/'tools/build_mechanics.py'),'--output',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads((out/'assembly-geometry.json').read_text()),geometry())
            # HRO assembly; bracket bytes independently matched HEAD generator.
            # Previous bracket golden predated the retained mounting-note update.
            import hashlib
            golden={'assembly.svg': 'db7a6acda583bf369a63bd9f520fe4f446aeb051d0a15fe2b948443a6de8c5ca', 'm3-brackets.svg': 'e39fe07da9e097195ca8fcf75102805a3de159e231f2b63a0378ecf6e8ac7dfd'}
            for name,digest in golden.items():
                self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)

    def test_selected_reset_is_restored_SMT_with_exposed_lands(self):
        s=geometry()['switch']
        self.assertEqual(s['mpn'],'TL3340AF160QG');self.assertEqual(s['LCSC'],'C2886925')
        self.assertIn('SMT',s['type'])
        self.assertEqual(s['body_height_mm'],3.3)
        self.assertEqual(s['peg_row_YZ_mm'],[49.5,4.1])
        self.assertEqual([s['peg_pitch_mm'],s['peg_drill_mm']],[4.25,.9])
        self.assertEqual(geometry()['reset_XY_diameter_mm'],[6.4,49.5,3.2])
        self.assertEqual(s['pins']['1'],s['pins']['3'])
        self.assertNotEqual(s['pins']['1'],s['pins']['2'])
        self.assertNotIn('signal_row_YZ_mm',s)

    def test_power_landing_still_output_and_not_a_box_header_footprint(self):
        p=geometry()['power_output'];self.assertEqual(len(p['pinout']),16)
        self.assertEqual(p['pinout']['1'],'N12');self.assertEqual(p['pinout']['12'],'P5')
        self.assertEqual([p['pinout'][str(i)] for i in range(13,17)],['']*4)
        self.assertIn('NEVER parallel',p['warning']);self.assertIn('CABLE MOUNT',p['type'])


if __name__=='__main__':unittest.main()
