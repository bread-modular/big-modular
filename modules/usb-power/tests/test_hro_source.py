"""Independent HRO land, fit, source and no-ignore regression checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sexp import parse,nodes,one,Atom
from routed_checks import verify_hro,routing_contract
from hro_fit import verify as verify_fit
from stack_geometry import geometry
from schematic_connectivity import Connectivity


class HROSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree=parse((ROOT/'hardware/usb-power.kicad_pcb').read_text())
        cls.usb=next(f for f in nodes(cls.tree,'footprint') if any(v[1:3]==['Reference','J1'] for v in nodes(f,'property')))
        cls.lib=ROOT/'hardware/BigModular.pretty/HRO-TYPE-C-31-M-12.kicad_mod'

    def test_local_land_and_honest_missing_model(self):
        result=verify_hro(self.usb,self.lib)
        self.assertAlmostEqual(result['nominal_boss_to_nearest_land_clearance_mm'],.3965651391)
        self.assertFalse(result['drawing_land_length_claim'])
        self.assertFalse((ROOT/'tools/usb_relief.py').exists())
        self.assertFalse(any((ROOT/'hardware/BigModular.pretty').glob('*GCT*')))

    def test_boss_shrink_and_pad_relief_and_missing_mask_are_rejected(self):
        for which in ('boss','relief','mask'):
            fp=copy.deepcopy(self.usb)
            if which=='boss':one(next(p for p in nodes(fp,'pad') if p[1]==''),'drill')[1]='0.60'
            elif which=='relief':next(p for p in nodes(fp,'pad') if p[1]=='A1')[3]='custom'
            else:one(next(p for p in nodes(fp,'pad') if p[1]=='S1'),'layers')[1:]=['*.Cu']
            with self.subTest(which=which),self.assertRaises(AssertionError):verify_hro(fp,self.lib)

    def test_independent_contact_mapping_and_all_NCs(self):
        expected={'A1':'GND','A12':'GND','A4':'USB_VBUS','A9':'USB_VBUS','A5':'CC1','B5':'CC2','S1':'GND',
                  'A6':None,'A7':None,'B6':None,'B7':None,'A8':None,'B8':None}
        graph=Connectivity(ROOT/'hardware')
        self.assertEqual({p:n for (r,p),n in graph.named_pins().items() if r=='J1'},expected)
        audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
        expected_non_j1=sum(len(v) for r,v in audit.items() if r!='J1' and not r.startswith('#'))
        self.assertEqual(len([k for k in graph.named_pins() if k[0]!='J1' and not k[0].startswith('#')]),expected_non_j1)
        props={p[1]:p[2] for p in nodes(graph.refs['J1'][1],'property')}
        self.assertEqual(props['LCSC'],'C165948');self.assertEqual(props['MPN'],'TYPE-C-31-M-12')

    def test_independent_fit_and_wrong_GCT_axis_rejection(self):
        self.assertGreater(verify_fit(geometry())['minimum_rounded_aperture_corner_margin_mm'],.22)
        for key,value in [('mouth_axis_XYZ_mm',[6.43,33.5,.8]),('aperture_XYWHR_mm',[4.23,28.6,3.8,9.8,.6])]:
            g=geometry();g[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):verify_fit(g)

    def test_routing_deletion_and_via_process_changes_are_detected(self):
        expected=json.loads((ROOT/'docs/routed-baseline.json').read_text())['routing_contract']
        self.assertEqual(routing_contract(self.tree),expected)
        t=copy.deepcopy(self.tree);t.remove(nodes(t,'segment')[0]);self.assertNotEqual(routing_contract(t),expected)
        t=copy.deepcopy(self.tree);v=nodes(t,'via')[0];v.remove(one(v,'filling'));self.assertNotEqual(routing_contract(t),expected)

    def test_no_ignored_DRC_rules_or_exclusions_and_limits_unchanged(self):
        for name in ['usb-power','usb-power-panel']:
            d=json.loads((ROOT/'hardware'/f'{name}.kicad_pro').read_text())['board']['design_settings']
            self.assertNotIn('ignore',d['rule_severities'].values());self.assertEqual(d['drc_exclusions'],[])
            for k,v in {'min_copper_edge_clearance':.5,'min_hole_clearance':.25,'min_hole_to_hole':.25,
                        'min_track_width':.2,'min_via_diameter':.5,'min_through_hole_diameter':.3,'min_text_height':.8}.items():self.assertEqual(d['rules'][k],v)

    def test_panel_builder_preserves_project_rules_and_carrier(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'usb-power-panel.kicad_pcb';pro=out.with_suffix('.kicad_pro')
            source=(ROOT/'hardware/usb-power-panel.kicad_pro').read_bytes();pro.write_bytes(source)
            cmd="from pathlib import Path; import sys;sys.path.insert(0,'tools');from build_stack import build_panel;build_panel(Path(sys.argv[1]))"
            r=subprocess.run(['/usr/bin/python3','-B','-c',cmd,str(out)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(pro.read_bytes(),source)
            self.assertEqual(out.read_bytes(),(ROOT/'hardware/usb-power-panel.kicad_pcb').read_bytes())

    def test_native_hidden_property_keyword_and_ERC_severities(self):
        graph=Connectivity(ROOT/'hardware')
        prop=next(p for p in nodes(graph.refs['J1'][1],'property') if p[1]=='Manufacturer')
        self.assertTrue(any(isinstance(v,Atom) and v=='hide' for v in one(prop,'effects')))
        project=json.loads((ROOT/'hardware/usb-power.kicad_pro').read_text())
        self.assertNotIn('ignore',project['erc']['rule_severities'].values())

    def test_generated_SCAD_is_an_envelope_not_borrowed_model(self):
        s=(ROOT/'hardware/mechanics/assembly-envelope.scad').read_text()
        self.assertIn('NOT a connector model',s);self.assertNotIn('.step',s.lower());self.assertIn('[3.26,8.94,7.35]',s)


if __name__=='__main__':unittest.main()
