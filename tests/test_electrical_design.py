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
        self.assertEqual(result['local_visible_wire_checks'],31)
    def test_mid_dc_corner_is_not_a_transient_guarantee(self):
        upper=.611*(1+100e3*1.001/(12.9e3*.999))
        self.assertGreater(upper,5.35);self.assertLess(upper,5.5)
        self.assertGreater(upper*1.08,5.5)
        self.assertGreater(2*1.5/(290e3*(5.5-upper)),44e-6)
        self.assertLess(9*(12000/6040),2*12*.8) # even before conversion losses
    def test_tl3340_manufacturer_contacts_and_case(self):
        # E-Switch P021301 Rev B: 1+3 are internally common, 2 is NO.
        from schematic_connectivity import Connectivity
        graph=Connectivity(ROOT/'hardware');pins=graph.named_pins()
        self.assertEqual({p:n for (r,p),n in pins.items() if r=='SW1'},
                         {'1':'EF_SHDN','3':'EF_SHDN','2':'RTN','MP':None})
        self.assertTrue(graph.wire_connected(('SW1','1'),('SW1','3')))
        fp=parse((ROOT/'hardware/BigModular.pretty/SW_TL3340AF160QG_HandSolder.kicad_mod').read_text())
        padnums=[p[1] for p in nodes(fp,'pad') if p[1]]
        self.assertEqual(set(padnums),{'1','2','3','MP'})
        self.assertEqual(padnums.count('MP'),2)
    def test_no_onboard_controller_or_programming_build(self):
        self.assertFalse((ROOT/'firmware').exists())
        from schematic_connectivity import Connectivity
        graph=Connectivity(ROOT/'hardware')
        self.assertNotIn('U10',graph.refs);self.assertNotIn('C39',graph.refs)
        self.assertFalse(any(n and ('UPDI' in n or 'MCU' in n) for n in graph.named_pins().values()))
    def test_single_led_and_hardware_only_operation(self):
        from schematic_connectivity import Connectivity
        pins=Connectivity(ROOT/'hardware').named_pins()
        self.assertEqual({p:n for (r,p),n in pins.items() if r=='D10'},{'1':'GND','2':'LED_P_A'})
        self.assertEqual(pins[('R32','1')],'P5')
        self.assertEqual(pins[('U2','7')],'EF_SHDN')
        self.assertEqual(pins[('SW1','2')],'RTN')
        self.assertIsNone(pins[('U3','5')]);self.assertIsNone(pins[('U5','5')])
        self.assertEqual(pins[('R38','1')],'MID');self.assertEqual(pins[('R38','2')],'BI_EN')
        for ref in ['Q2','Q3','D11','D12','R33','R34','R39']:
            self.assertFalse(any(r==ref for r,p in pins))
        self.assertFalse(any(n and ('EXT_' in n or n.endswith('_K')) for n in pins.values()))
    def test_exact_magnetic_land_patterns(self):
        for name,c,w,h in [('L_KOHER_MDA1040',4.475,3.55,3.5),('L_CENKER_CKCS6045',2.1,2.4,5.7)]:
            fp=parse((ROOT/'hardware/BigModular.pretty'/(name+'.kicad_mod')).read_text())
            pads={p[1]:p for p in nodes(fp,'pad')}
            self.assertEqual(set(pads),{'1','2'})
            for pin,x in [('1',-c),('2',c)]:
                self.assertEqual(tuple(map(float,one(pads[pin],'at')[1:3])),(x,0))
                self.assertEqual(tuple(map(float,one(pads[pin],'size')[1:3])),(w,h))
        fp=parse((ROOT/'hardware/BigModular.pretty'/('Texas_RGE0024B_VQFN-24-1EP_4x4mm_P0.5mm_EP2.45x2.45mm.kicad_mod')).read_text())
        pads={p[1]:p for p in nodes(fp,'pad') if p[1]}
        self.assertEqual(set(pads),{str(i) for i in range(1,26)})
        self.assertEqual(tuple(map(float,one(pads['25'],'size')[1:3])),(2.45,2.45))
        for n,pad in pads.items():
            if n=='25':continue
            self.assertEqual(sorted(map(float,one(pad,'size')[1:3])),[.25,.6])
            self.assertAlmostEqual(max(map(abs,map(float,one(pad,'at')[1:3]))),1.9)
    def test_removed_sensing_cannot_backfeed_or_reappear(self):
        from schematic_connectivity import Connectivity
        g=Connectivity(ROOT/'hardware');p=g.named_pins()
        for ref in ['J2','J8','JP1','U9','U11','Q1','R35','R41','C40']:
            self.assertNotIn(ref,g.refs)
        self.assertFalse((ROOT/'hardware/06_sensing.kicad_sch').exists())
        self.assertFalse(any(n and any(t in n for t in ['ADC_','AUX','DBG_']) for n in p.values()))
        self.assertAlmostEqual(5.216/2,2.608)
        self.assertLess(5.5**2/990,.031)
    def test_mutated_hardware_gate_and_power_contract_are_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'copy';shutil.copytree(ROOT/'hardware',dest)
            audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
            for old,new in [('EF_SHDN','BROKEN_GATE'),('VIN9','USB_VBUS'),('BI_EN','GND')]:
                with self.subTest(mutation=old):
                    sources={p.name:p.read_text() for p in (ROOT/'hardware').glob('*.kicad_sch')}
                    # Changing both source and generated audit cannot fool the independent checks.
                    for name,source in sources.items():(dest/name).write_text(source.replace('"'+old+'"','"'+new+'"'))
                    altered={r:{p:(new if n==old else n) for p,n in pins.items()} for r,pins in audit.items()}
                    (Path(tmp)/'audit.json').write_text(json.dumps(altered))
                    with self.assertRaises(AssertionError):check(dest,Path(tmp)/'audit.json',ROOT/'BOM.csv')
                    for name,source in sources.items():(dest/name).write_text(source)
if __name__=='__main__':unittest.main()
