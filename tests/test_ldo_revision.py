"""Independent ES1 source-stage gates; no fabricated PCB/thermal acceptance."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import shutil
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sexp import parse,nodes,one,dump
from electrical_checks import check,REVIEWED
from schematic_connectivity import Connectivity
from ldo_budget import budget


class LDORevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=Connectivity(ROOT/'hardware');cls.pins=cls.g.named_pins()
        with (ROOT/'BOM.csv').open() as f:cls.bom={r['Reference']:r for r in csv.DictReader(f)}

    def test_exact_requested_variants_and_ground_exposed_pads(self):
        for ref,mpn,code in [('U12','TPS7A4700RGWR','C114839'),('U13','TPS7A3301RGWR','C90082')]:
            self.assertEqual((self.bom[ref]['MPN'],self.bom[ref]['LCSC']),(mpn,code))
            self.assertEqual(self.pins[(ref,'21')],'GND')
            self.assertEqual(self.pins[(ref,'7')],'GND')
            self.assertEqual({p:n for (r,p),n in self.pins.items() if r==ref},REVIEWED[ref])
        self.assertFalse(any('TPS7A4701' in r['MPN'] for r in self.bom.values()))

    def test_anyout_is_not_a_feedback_resistor_design(self):
        self.assertEqual([p for p in ['4','5','6','8','9','10','11','12'] if self.pins[('U12',p)]=='GND'],['5','6','9','11'])
        self.assertAlmostEqual(1.4+6.4+3.2+.8+.2,12.)
        self.assertEqual(self.pins[('U12','3')],'P12')
        self.assertEqual(self.pins[('U12','13')],'PRAW')

    def test_negative_polarity_feedback_and_shunts(self):
        self.assertEqual(self.pins[('U13','13')],'NRAW')
        self.assertEqual(self.pins[('U13','14')],'N_NR')
        for ref,val in [('R72','90.9k 0.1%'),('R73','1.21k 0.1%'),('R74','10k 0.1%')]:self.assertEqual(self.bom[ref]['Value'],val)
        self.assertAlmostEqual(-1.175*(1+92110/10000),-11.997925)
        self.assertGreater(1.175*.975/(10000*1.003503),5e-6)
        self.assertEqual((self.pins[('D27','1')],self.pins[('D27','2')]),('PRAW','P12'))
        self.assertEqual((self.pins[('D28','1')],self.pins[('D28','2')]),('N12','NRAW'))
        self.assertEqual(self.pins[('C62','1')],'N12');self.assertEqual(self.pins[('C62','2')],'N_LDO_FB')

    def test_raw_internal_only_and_five_volt_stage_exactly_preserved(self):
        old=json.loads((ROOT/'docs/ldo-evidence/baseline-pin-net.json').read_text())
        permitted={('U4','15'),('U4','23'),('C8','1'),('C9','1'),('C10','1'),('C11','1'),('D2','1'),('D3','2'),('R12','1'),('R14','1'),('#FLG06','1'),('#FLG07','1'),('R12','2'),('R15','2'),
                   ('R4','2'),('R8','2'),('R36','2')}
        changes={k for r,ps in old.items() for p,n in ps.items() if self.pins[k:=(r,p)]!=n}
        self.assertEqual(changes,permitted)
        for p in range(1,17):self.assertNotIn(self.pins[('J7',str(p))],('PRAW','NRAW'))
        with (ROOT/'docs/ldo-evidence/baseline-BOM.csv').open() as f:oldbom={r['Reference']:r for r in csv.DictReader(f)}
        for r in ['U5','L4','C18','C19','C20','C36','C38','R17','R18','R27','R32','D10']:
            if r=='D10':
                # User-authorized DNP is the only accepted delta from the baseline row.
                self.assertEqual({k:self.bom[r][k] for k in ('MPN','Footprint','LCSC','Manufacturer','Block')},
                                 {k:oldbom[r][k] for k in ('MPN','Footprint','LCSC','Manufacturer','Block')})
                self.assertEqual(self.bom[r]['Value'],oldbom[r]['Value'].replace(' / MANUAL',' / DNP'))
                self.assertEqual((self.bom[r]['Classification'],self.bom[r]['DNP']),('DNP','yes'))
            elif r=='C18':
                # Approved exact sourcing fill (Samsung CL31B106KAHNNNE/C14860); electrical identity unchanged.
                self.assertEqual({k:self.bom[r][k] for k in ('Value','Footprint','Block')},{k:oldbom[r][k] for k in ('Value','Footprint','Block')})
                self.assertEqual((self.bom[r]['MPN'],self.bom[r]['LCSC'],self.bom[r]['Classification'],self.bom[r]['DNP']),('CL31B106KAHNNNE','C14860','Extended','no'))
            else:
                # The accepted BOM adds an explicit DNP column; these refs stay fitted.
                self.assertEqual({k:v for k,v in self.bom[r].items() if k!='DNP'},oldbom[r],r)
                self.assertEqual(self.bom[r]['DNP'],'no',r)

    def test_precision_raw_setpoint_and_capacitor_requirements_are_explicit(self):
        for r in ['R12','R14']:
            self.assertEqual(self.bom[r]['Value'],('1.5M' if r=='R12' else '1.6M')+' 0.1%')
            self.assertEqual(self.bom[r]['LCSC'],'C4223894' if r=='R12' else 'C2088870')
            self.assertTrue(self.bom[r]['Footprint'].endswith('R_0805_2012Metric'))
        for r in ['R13','R15','R60']:self.assertEqual(self.bom[r]['Value'],'150k 0.1%')
        for i in range(48,60):
            self.assertEqual(self.bom['C'+str(i)]['Value'],'22u 25V X5R')
            self.assertEqual(self.bom['C'+str(i)]['LCSC'],'C12891')
        self.assertEqual(self.bom['C60']['Value'],'1u 50V X7R')
        self.assertEqual(self.bom['C61']['Value'],'100n 50V X7R')
        self.assertEqual(self.bom['C62']['Value'],'10n 50V X7R')
        for ref,v in [('C10','4.5p'),('C11','4.3p')]:self.assertEqual(self.bom[ref]['Value'],v+' 50V C0G')
        self.assertEqual(self.bom['R75']['Value'],'23.2k 0.1%');self.assertEqual(self.bom['R76']['Value'],'2.49k 0.1%')
        b=budget();self.assertFalse(b['cap_effective_C_verified']);self.assertFalse(b['cap_ESR_verified'])

    def test_headroom_and_800mA_1A_dissipation_not_supply_ratings(self):
        b=budget()
        self.assertAlmostEqual(b['raw_nominal_magnitudes_V']['positive'],1.213*(1+1523200/150000))
        self.assertAlmostEqual(b['raw_nominal_magnitudes_V']['negative'],1.213*1750000/152490)
        self.assertGreater(b['negative_worst_headroom_V'],.805)
        self.assertGreater(b['positive_input_trough_V'],13.)
        self.assertGreater(b['positive_worst_headroom_V'],.702)
        self.assertLess(b['negative_raw_DC_magnitude_V'][1]+.1,15)
        self.assertAlmostEqual(b['pass_dissipation_excludes_ground_current']['0.8']['positive_pass_nominal_W'],1.2244885333333344)
        self.assertGreater(b['pass_dissipation_excludes_ground_current']['1.0']['negative_pass_nominal_W'],1.92)
        self.assertLess(b['nominal_efuse_input_power_W_at_9V'],b['simultaneous_12V_800mA_rail_output_power_W'])
        self.assertIsNone(b['current_rating_claim']);self.assertTrue(b['PCB_integration_completed'])

    def test_exact_TI_RGW_land_pattern_not_generic_QFN(self):
        fp=parse((ROOT/'hardware/BigModular.pretty/Texas_RGW0020A_VQFN-20-1EP_5x5mm_P0.65mm_EP3.15x3.15mm.kicad_mod').read_text())
        pads={p[1]:p for p in nodes(fp,'pad') if p[1]}
        self.assertEqual(set(pads),{str(i) for i in range(1,22)})
        self.assertEqual(tuple(map(float,one(pads['21'],'size')[1:])),(3.15,3.15))
        self.assertEqual(tuple(map(float,one(pads['1'],'at')[1:3])),(-2.325,-1.3))
        self.assertEqual(tuple(map(float,one(pads['15'],'at')[1:3])),(2.325,-1.3))
        for i in range(1,21):self.assertEqual(sorted(map(float,one(pads[str(i)],'size')[1:])),[.31,.75])
        paste=[p for p in nodes(fp,'pad') if p[1]==''];self.assertEqual(len(paste),4)
        for p in paste:self.assertEqual(tuple(map(float,one(p,'size')[1:])),(1.37,1.37))
        self.assertFalse(nodes(fp,'model'))

    def test_fixed_interfaces_preserved_and_old_release_not_current(self):
        h=json.loads((ROOT/'docs/ldo-evidence/preserved-hashes.json').read_text())
        for f,d in h.items():self.assertEqual(hashlib.sha256((ROOT/f).read_bytes()).hexdigest(),d,f)
        self.assertIn('STALE',(ROOT/'production/README.md').read_text())
        self.assertIn('PCB integration complete',(ROOT/'README.md').read_text())

    def test_negative_enable_pad_and_anyout_mutations_are_rejected(self):
        # Change the literal audit + native labels together: independent roles
        # must still reject the resulting superficially self-consistent circuit.
        with tempfile.TemporaryDirectory() as td:
            dst=Path(td)/'hardware';shutil.copytree(ROOT/'hardware',dst)
            source=(dst/'05_quiet_rails.kicad_sch').read_text()
            audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
            for old,new in [('NRAW','PRAW'),('P_NR','GND'),('N_LDO_FB','GND')]:
                with self.subTest(old=old):
                    (dst/'05_quiet_rails.kicad_sch').write_text(source.replace('"'+old+'"','"'+new+'"'))
                    altered={r:{p:(new if n==old else n) for p,n in ps.items()} for r,ps in audit.items()}
                    a=Path(td)/'audit.json';a.write_text(json.dumps(altered))
                    with self.assertRaises(AssertionError):check(dst,a,ROOT/'BOM.csv')
            (dst/'05_quiet_rails.kicad_sch').write_text(source)


if __name__=='__main__':unittest.main()


class LDOFinalPrototypeTests(unittest.TestCase):
    def test_exact_parallel_population_and_screen_rejects_old_banks(self):
        from ldo_budget import capacitor_screen
        screen=capacitor_screen();g=Connectivity(ROOT/'hardware').named_pins()
        wanted={'positive_input':('PRAW',[48,49,50,63],12.5918272493),
                'positive_output':('P12',[51,52,53,64,65,66],23.9899640877),
                'negative_input':('NRAW',[54,55,56,67],12.5918272493),
                'negative_output':('N12',[57,58,59],11.9949820438)}
        for key,(net,refs,value) in wanted.items():
            r=screen[key];self.assertEqual(r['refs'],['C'+str(i) for i in refs])
            self.assertAlmostEqual(r['screened_effective_uF'],value,places=8)
            self.assertGreaterEqual(r['screened_effective_uF'],r['required_effective_uF'])
            for ref in r['refs']:
                self.assertEqual(g[ref,'1'],net);self.assertEqual(g[ref,'2'],'GND')
        self.assertLess(screen['positive_output']['screened_effective_uF']/2,20)
        self.assertLess(screen['negative_input']['screened_effective_uF']*3/4,10)
        data=json.loads((ROOT/'docs/ldo-evidence/manufacturer-mlcc-data.json').read_text())
        self.assertEqual([data[k] for k in ['tolerance_factor','temperature_screen_factor','aging_allowance_factor']],[.9,.85,.95])
        self.assertGreater(data['typical_12p5V_temperature_relative_min_factor'],.85)

    def test_all_components_front_and_no_bottom_paste(self):
        import pcbnew as p
        from routed_checks import verify_front_only
        b=p.LoadBoard(str(ROOT/'hardware/big_modular.kicad_pcb'));g=json.loads((ROOT/'docs/assembly-geometry.json').read_text())
        r=verify_front_only(b,g)
        self.assertEqual(set(r['caps']),{'C63','C64','C65','C66','C67'})
        self.assertEqual(r['B_Cu_footprints'],0)
        self.assertEqual(r['B_Paste_component_apertures'],0)
        self.assertTrue(r['all_components_front'])
        # Flipping a cap to the back must fail the single-side gate.
        f=next(f for f in b.GetFootprints() if f.GetReference()=='C63')
        f.Flip(f.GetPosition(),False)
        with self.assertRaises(AssertionError):verify_front_only(b,g)

    def test_ldo_exposed_pads_have_nine_ground_thermal_vias_each(self):
        import pcbnew as p
        b=p.LoadBoard(str(ROOT/'hardware/big_modular.kicad_pcb'))
        for ref in ['U12','U13']:
            f=next(f for f in b.GetFootprints() if f.GetReference()==ref)
            ep=next(q for q in f.Pads() if q.GetNumber()=='21');self.assertEqual(ep.GetNetname(),'/GND')
            x,y=p.ToMM(ep.GetPosition());vs=[v for v in b.GetTracks() if v.GetClass()=='PCB_VIA' and abs(p.ToMM(v.GetPosition().x)-x)<1.575 and abs(p.ToMM(v.GetPosition().y)-y)<1.575]
            self.assertEqual(len(vs),9)
            self.assertTrue(all(v.GetNetname()=='/GND' and not v.GetPrimaryDrillFilledFlag() and not v.GetPrimaryDrillCappedFlag() for v in vs))
