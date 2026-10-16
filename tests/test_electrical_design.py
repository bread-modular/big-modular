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
        self.assertEqual(result['independent_pin_checks'],138)
        self.assertEqual(result['local_visible_wire_checks'],39)
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
                         {'1':'BUTTON_N','3':'BUTTON_N','2':'GND','MP':None})
        self.assertTrue(graph.wire_connected(('SW1','1'),('SW1','3')))
        fp=parse((ROOT/'hardware/BigModular.pretty/SW_TL3340AF160QG_HandSolder.kicad_mod').read_text())
        padnums=[p[1] for p in nodes(fp,'pad') if p[1]]
        self.assertEqual(set(padnums),{'1','2','3','MP'})
        self.assertEqual(padnums.count('MP'),2)
    def test_no_onboard_controller_or_programming_build(self):
        self.assertEqual({p.name for p in (ROOT/'firmware').iterdir()},{'README.md'})
        from schematic_connectivity import Connectivity
        graph=Connectivity(ROOT/'hardware')
        self.assertNotIn('U10',graph.refs);self.assertNotIn('C39',graph.refs)
        self.assertFalse(any(n and ('UPDI' in n or 'MCU' in n) for n in graph.named_pins().values()))
    def test_single_led_and_hardware_only_operation(self):
        from schematic_connectivity import Connectivity
        pins=Connectivity(ROOT/'hardware').named_pins()
        self.assertEqual({p:n for (r,p),n in pins.items() if r=='D10'},{'1':'GND','2':'LED_P_A'})
        self.assertEqual(pins[('R32','1')],'P5')
        self.assertEqual(pins[('JP1','1')],'PG_PERMIT')
        self.assertEqual(pins[('R38','1')],'MID');self.assertEqual(pins[('R38','2')],'BI_EN')
        for ref in ['Q2','Q3','D11','D12','R33','R34','R39']:
            self.assertFalse(any(r==ref for r,p in pins))
        self.assertFalse(any(n and ('EXT_' in n or n.endswith('_K')) for n in pins.values()))
    def test_keyed_debug_pin1_and_numeric_pad_map(self):
        fp=parse((ROOT/'hardware/BigModular.pretty/IDC-Header_2x10_P2.54mm_Vertical.kicad_mod').read_text())
        pads={p[1]:p for p in nodes(fp,'pad')}
        self.assertEqual(set(pads),{str(i) for i in range(1,21)})
        self.assertEqual(pads['1'][3],'roundrect')
        for i in range(1,21):
            self.assertEqual(tuple(map(float,one(pads[str(i)],'at')[1:3])),((i+1)%2*2.54,((i-1)//2)*2.54))
        self.assertIn('2x10',fp[1])
    def test_negative_sense_loading_error_budget_not_blanket_qualification(self):
        self.assertAlmostEqual(12*16.5e3/100e3,1.98)
        self.assertLess(1.98/16.5e3,121e-6) # feedback output load, ADC is Hi-Z
        self.assertAlmostEqual(2e-3*(1+16.5e3/100e3),.00233) # TI offset limit stated at5V, not3.3V guarantee
        self.assertAlmostEqual(5e-12*16.5e3,82.5e-9) # typical bias only
        self.assertGreater(500e-6*16.5e3,3.3) # rejected diode's @40V bound is not an actual3.3V prediction
        self.assertAlmostEqual(5.216/2,2.608) # automatic MID-derived bipolar enable
        self.assertLess(5.5**2/990,.031) # LED1k worst-case power even with zero Vf
        self.assertAlmostEqual(3.3/10e3,.00033) # AUX monitor short upper estimate
    def test_mutated_hardware_gate_and_sense_contract_are_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'copy';shutil.copytree(ROOT/'hardware',dest)
            audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
            for old,new in [('PG_PERMIT','BROKEN_GATE'),('ADC_N12','BROKEN_ADC'),('BI_EN','GND')]:
                with self.subTest(mutation=old):
                    sources={p.name:p.read_text() for p in (ROOT/'hardware').glob('*.kicad_sch')}
                    # Changing both source and generated audit cannot fool the independent checks.
                    for name,source in sources.items():(dest/name).write_text(source.replace('"'+old+'"','"'+new+'"'))
                    altered={r:{p:(new if n==old else n) for p,n in pins.items()} for r,pins in audit.items()}
                    (Path(tmp)/'audit.json').write_text(json.dumps(altered))
                    with self.assertRaises(AssertionError):check(dest,Path(tmp)/'audit.json',ROOT/'BOM.csv')
                    for name,source in sources.items():(dest/name).write_text(source)
if __name__=='__main__':unittest.main()
