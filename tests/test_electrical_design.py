"""Authorized architecture guards, separate from generator-derived expectations."""
import json,sys,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from electrical_checks import check
from sexp import parse,nodes,one
class ElectricalPrototypeTests(unittest.TestCase):
    def test_independent_roles_bom_and_visible_feedback(self):
        result=check(ROOT/'hardware',ROOT/'docs/pin-net-audit.json',ROOT/'BOM.csv')
        self.assertEqual(result['independent_pin_checks'],123)
        self.assertEqual(result['local_visible_wire_checks'],42)
    def test_mid_dc_corner_is_not_a_transient_guarantee(self):
        upper=.611*(1+100e3*1.001/(12.9e3*.999))
        self.assertGreater(upper,5.35);self.assertLess(upper,5.5)
        self.assertGreater(upper*1.08,5.5)
        self.assertGreater(2*1.5/(290e3*(5.5-upper)),44e-6)
        self.assertLess(9*(12000/6040),2*12*.8) # even before conversion losses
    def test_custom_ldo_tab_matches_manufacturer_pin4(self):
        fp=parse((ROOT/'hardware/BigModular.pretty/MCP1799_SOT223_Tab4.kicad_mod').read_text())
        self.assertEqual({p[1] for p in nodes(fp,'pad')},{'1','2','3','4'})
        tab=next(p for p in nodes(fp,'pad') if p[1]=='4')
        # Independent manufacturer dimensions, not a generic area threshold:
        # DS20006248A p21 / C04-2032A: C6.10, E2.30, X1max0.95,
        # X2max3.25, Ymax1.90 mm, with the footprint rotated 90 degrees.
        pads={p[1]:p for p in nodes(fp,'pad')}
        expected={'1':(-3.05,-2.30,1.90,.95),'2':(-3.05,0,1.90,.95),
                  '3':(-3.05,2.30,1.90,.95),'4':(3.05,0,1.90,3.25)}
        for num,dimensions in expected.items():
            actual=tuple(map(float,one(pads[num],'at')[1:3]+one(pads[num],'size')[1:3]))
            for actual_dimension,expected_dimension in zip(actual,dimensions):
                self.assertAlmostEqual(actual_dimension,expected_dimension,places=6)
        self.assertAlmostEqual(float(one(tab,'size')[1])*float(one(tab,'size')[2]),6.175)
    def test_tl3340_manufacturer_contacts_and_case(self):
        # E-Switch P021301 Rev B: 1+3 are internally common, 2 is NO.
        from schematic_connectivity import Connectivity
        graph=Connectivity(ROOT/'hardware');pins=graph.named_pins()
        self.assertEqual({p:n for (r,p),n in pins.items() if r=='SW1'},
                         {'1':'RESET_N','3':'RESET_N','2':'GND','MP':None})
        self.assertTrue(graph.wire_connected(('SW1','1'),('SW1','3')))
        fp=parse((ROOT/'hardware/BigModular.pretty/SW_TL3340AF160QG_HandSolder.kicad_mod').read_text())
        padnums=[p[1] for p in nodes(fp,'pad') if p[1]]
        self.assertEqual(set(padnums),{'1','2','3','MP'})
        self.assertEqual(padnums.count('MP'),2)
    def test_actual_host_controller_c_code(self):
        with tempfile.TemporaryDirectory(prefix='controller-test-') as tmp:
            p=subprocess.run(['make','-C',str(ROOT/'firmware'),'host-test','OUT='+tmp],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn('first-fault retention',p.stdout)
if __name__=='__main__':unittest.main()
