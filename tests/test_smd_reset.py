"""A4.2 restored TL3340 placement: exact contacts/pegs, not production approval."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SMDRestorationTests(unittest.TestCase):
    def native(self, mutation='', rejects=False):
        code = '''
from pathlib import Path
import sys
sys.path.insert(0,'tools')
import pcbnew as pcb
from verify_stack import verify_reset_smt
from stack_geometry import geometry
b=pcb.LoadBoard('hardware/big_modular.kicad_pcb')
f=next(f for f in b.GetFootprints() if f.GetReference()=='SW1')
g=geometry()
'''+mutation+'\n'
        if rejects:
            code += '''
try:
    verify_reset_smt(f,g)
except AssertionError:
    pass
else:
    raise AssertionError('bad switch configuration was accepted')
'''
        else:
            code += "r=verify_reset_smt(f,g)\nassert r['smd_pads']==5 and r['locator_NPTHs']==2\n"
        r=subprocess.run(['/usr/bin/python3','-B','-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_installed_part_and_lands_match_manufacturer_mapping(self):
        self.native()

    def test_pin3_cannot_be_assigned_to_the_opposite_contact(self):
        self.native("next(p for p in f.Pads() if p.GetNumber()=='3').SetNet(b.FindNet('RESET_B_PENDING'))",True)

    def test_alignment_holes_must_stay_non_plated(self):
        self.native("next(p for p in f.Pads() if p.GetNumber()=='').SetAttribute(pcb.PAD_ATTRIB_PTH)",True)

    def test_original_THT_panel_axis_is_rejected(self):
        self.native("g['reset_XY_diameter_mm']=[7.2,91,3.2]",True)

    def test_undersized_iron_access_land_is_rejected(self):
        self.native("next(p for p in f.Pads() if p.GetNumber()=='2').SetSize(pcb.VECTOR2I(pcb.FromMM(.6),pcb.FromMM(1.8)))",True)

    def test_floating_case_tabs_cannot_be_tied_to_reset(self):
        self.native("next(p for p in f.Pads() if p.GetNumber()=='MP').SetNet(b.FindNet('RESET_A_PENDING'))",True)


if __name__=='__main__':
    unittest.main()
