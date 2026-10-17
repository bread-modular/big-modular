"""SR2 focused native/pin/NC/part/voltage/cap/current/budget/protection gates."""
import csv,hashlib,json,subprocess,sys,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from schematic_connectivity import Connectivity
from electrical_checks import check
from sr2_budget import budget
from sexp import nodes,one,parse
BASE='1e5b31f3a441b030da1b9d1c25427a97b03cbe00'
SR1='0f5b49d4384b7b1a1c3ab3c193042db181d819d1'
def old(name,rev=SR1):return subprocess.check_output(['git','show',rev+':modules/usb-power/'+name],cwd=REPO)
class SR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=Connectivity(ROOT/'hardware');cls.p=cls.g.named_pins();cls.b=budget()
        cls.rows={r['Reference']:r for r in csv.DictReader((ROOT/'BOM.csv').read_text().splitlines())}
        cls.tmp=tempfile.TemporaryDirectory(prefix='sr2-native-');cls.out=Path(cls.tmp.name)
        for args in [['erc','--severity-all','--exit-code-violations','--format','json','--output',str(cls.out/'erc.json')],['export','netlist','--format','kicadxml','--output',str(cls.out/'netlist.xml')]]:
            subprocess.run(['kicad-cli','sch',*args,str(ROOT/'hardware/usb-power.kicad_sch')],capture_output=True,text=True,check=True)
        cls.xml=ET.parse(cls.out/'netlist.xml').getroot()
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_independent_roles_BOM_pads_NC(self):
        r=check(ROOT/'hardware',ROOT/'docs/pin-net-audit.json',ROOT/'BOM.csv')
        self.assertEqual((r['parts'],r['pins_including_NC'],r['hierarchical_ports']),(116,350,23))
        self.assertEqual(r['footprint_pin_maps'],116)
    def test_all_severities_native_ERC_zero_no_ignores(self):
        e=json.loads((self.out/'erc.json').read_text());self.assertEqual(e['ignored_checks'],[])
        self.assertEqual(set(e['included_severities']),{'error','warning','exclusion'})
        self.assertEqual([v for s in e['sheets'] for v in s['violations']],[])
    def test_native_netlist_all_component_pins_and_NCs(self):
        actual={};nc=0
        for net in self.xml.findall('./nets/net'):
            ns=net.findall('node');name=net.get('name').split('/')[-1]
            for n in ns:
                r,p=n.get('ref'),n.get('pin')
                if name.startswith('unconnected-'):
                    self.assertEqual(len(ns),1);value=None;nc+=1
                else:value=name
                self.assertNotIn((r,p),actual);actual[(r,p)]=value
        expected={k:v for k,v in self.p.items() if not k[0].startswith('#')}
        self.assertEqual(actual,expected);self.assertEqual(nc,39);self.assertEqual(len(actual),344)
        for comp in self.xml.findall('./components/comp'):
            row=self.rows[comp.get('ref')];self.assertEqual(comp.findtext('value'),row['Value']);self.assertEqual(comp.findtext('footprint'),row['Footprint'])
            fields={f.get('name'):f.text or '' for f in comp.findall('./fields/field')}
            for f in ['MPN','LCSC']:self.assertEqual(fields.get(f,''),row[f])
    def test_exact_delta_from_staged_SR1(self):
        prior=json.loads(old('docs/pin-net-audit.json'));current=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
        from sr2_design import REMOVED_REFS
        self.assertEqual(set(prior)-set(current),REMOVED_REFS)
        self.assertEqual(set(current)-set(prior),{'C89','C90','C91','C92','R91','R92','R93','D30','C93'})
        changed={r for r in set(prior)&set(current) if prior[r]!=current[r]}
        self.assertEqual(changed,{'U3','L1','C7','C35','C6','C37','C70','C71','R9','R10','R15','R84'})
    def test_preserved_SR1_positive_and_protection_interfaces(self):
        for name in ['01_input_protection','02_hardgate','06_positive_boost','07_output_rails']:
            self.assertEqual((ROOT/'hardware'/(name+'.kicad_sch')).read_bytes(),old('hardware/'+name+'.kicad_sch'),name)
        self.assertEqual(self.p[('U14','2')],'VPROT');self.assertEqual(self.rows['U13']['MPN'],'TPS7A3301RGWR')
        self.assertEqual(self.p[('SW1','1')],'EF_SHDN');self.assertEqual(self.p[('SW1','2')],'RTN')
        self.assertNotIn('BI_EN',self.p.values());self.assertEqual(self.p[('U3','1')],'NRAW')
    def test_protected_PCB_project_rules_and_existing_libraries(self):
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','modules/usb-power/hardware','modules/usb-power/jlcpcb'],cwd=REPO,text=True).splitlines()
        for p in paths:
            rel=p.removeprefix('modules/usb-power/')
            if p.endswith(('.kicad_sch','.kicad_sym')):continue
            self.assertEqual((REPO/p).read_bytes(),old(rel,BASE),p)
    def test_selected_network_and_native_corners(self):
        c=self.b['corners'];self.assertAlmostEqual(c['raw_nominal_magnitude_V'],14.07752)
        self.assertAlmostEqual(c['upper_initial_tolerance_pct'],.1246684350132626)
        self.assertGreater(c['LDO_headroom_V'],1);self.assertFalse(c['FB_current_guaranteed_max'])
        self.assertAlmostEqual(self.b['voltage']['OV_max_including100nA_V'],11.583678444135291,places=4)
        self.assertLess(self.b['voltage']['allocated_span_V'],28);self.assertFalse(self.b['voltage']['OV_is_clamp'])
        self.assertFalse(self.b['voltage']['open_FB_survival_proven'])
    def test_enable_current_caps_and_shared_budget(self):
        b=self.b;self.assertLess(b['enable']['start_max_V_ignoring_helpful_pullup'],7.34)
        self.assertLess(b['enable']['max_at28V_with5uA_V'],5.5);self.assertFalse(b['enable']['bias_guaranteed_max'])
        self.assertGreater(b['capacitors']['IBB_span_bypass']['effective_screen_uF'],2.2)
        self.assertEqual(b['capacitors']['IBB_span_bypass']['nominal_uF'],8.8)
        self.assertLess(b['switch']['peak_A'],4);self.assertLess(b['switch']['valley_A'],3.1)
        self.assertEqual(b['switch']['L1_guaranteed_hot_min_A'],None)
        self.assertTrue(b['power']['rows'][1]['adverse']['allocation_1p85A_pass']);self.assertFalse(b['power']['guaranteed_rating'])
        self.assertEqual(b['power']['eFuse_ILIM_ohm'],6040);self.assertIsNone(b['rated_output_current'])
        self.assertEqual(b,json.loads((ROOT/'docs/sr2-schematic-budget.json').read_text()))
    def test_uncertainties_are_not_certification(self):
        b=self.b;self.assertFalse(b['qualification_complete']);self.assertFalse(b['PCB_parity_claim'])
        self.assertIsNone(b['negative_loop']['measured_phase_margin_deg']);self.assertFalse(b['negative_loop']['parameters_guaranteed'])
        self.assertFalse(b['startup']['full_load_startup_proven']);self.assertGreater(b['startup']['off_EN_at_zero_VPROT_max_sensitivity_V'],1.28)
        self.assertGreater(b['startup']['positive_NRAW_charge_sharing_no_switch_upper_sensitivity_V'],.3)
        self.assertFalse(b['mechanical']['actual_fit_approved']);self.assertEqual(b['mechanical']['height_max_mm'],5.)
    def test_all_component_classifications_reuse_and_DNP(self):
        catalog=json.loads((ROOT/'docs/electrical-catalog.json').read_text())
        for p in [json.loads((ROOT/'docs/split-rail-catalog.json').read_text()),{p['code']:p for p in json.loads((ROOT/'docs/tps54302-selected-parts.json').read_text())['selected_parts']}]:
            catalog.update(p)
        precision={'R9','R10','R15','R72','R74','R86','R87'}
        for ref,row in self.rows.items():
            if row['DNP']=='yes':continue
            if ref=='J7':self.assertEqual(row['Classification'],'Manual');continue
            p=catalog[row['LCSC']];self.assertEqual(row['MPN'],p['mpn']);self.assertEqual(row['Classification'],p['classification']);self.assertTrue(p['economy_eligible'],ref)
            if ref[0] in 'RC':self.assertEqual(p['classification'],'Extended' if ref in precision|{'R6'} else 'Basic',ref)
        self.assertEqual({self.rows[r]['LCSC'] for r in ['R9','R15','R10']},{'C122538','C705720','C95204'})
    def test_deterministic_native_BOM_pin_audit_and_library(self):
        dest=self.out/'rebuild'
        subprocess.run([sys.executable,'-B',str(ROOT/'tools/build_project.py'),'--schematic-only','--output',str(dest)],capture_output=True,text=True,check=True)
        for p in (ROOT/'hardware').glob('*.kicad_sch'):self.assertEqual((dest/p.name).read_bytes(),p.read_bytes(),p.name)
        self.assertEqual((dest/'BigModular.kicad_sym').read_bytes(),(ROOT/'hardware/BigModular.kicad_sym').read_bytes())
        self.assertEqual((dest/'BOM.csv').read_bytes(),(ROOT/'BOM.csv').read_bytes())
        self.assertEqual((dest/'pin-net-audit.json').read_bytes(),(ROOT/'docs/pin-net-audit.json').read_bytes())
        self.assertFalse(list(dest.glob('*.kicad_pcb')))

    def test_D30_orientation_identity_and_local_bank_wires(self):
        self.assertEqual({p:n for (r,p),n in self.p.items() if r=='D30'}, {'1':'GND','2':'NRAW'})
        for ref in ['D27','D28','D29']:
            for f in ['MPN','LCSC','Manufacturer','Footprint','Classification']:
                self.assertEqual(self.rows['D30'][f],self.rows[ref][f])
        self.assertEqual(self.rows['D30']['LCSC'],'C8678')
        self.assertEqual(self.rows['D30']['DNP'],'no')
        self.assertTrue(self.g.wire_connected(('D30','1'),('C6','2')))
        self.assertTrue(self.g.wire_connected(('D30','2'),('C6','1')))
        from sexp import walk
        lib=one(self.g.sheets['04_bipolar.kicad_sch'],'lib_symbols')
        diode=next(n for n in nodes(lib,'symbol') if n[1]=='BigModular:Device_D_Schottky')
        self.assertEqual({one(p,'number')[1]:one(p,'name')[1] for p in walk(diode,'pin')},{'1':'K','2':'A'})
        self.assertIsNone(self.b['startup']['mitigation']['guaranteed_positive_clamp_V'])
        self.assertFalse(self.b['startup']['mitigation']['startup_waveforms_qualified'])

    def test_C93_DNP_across_entire_upper_divider_not_purchased(self):
        self.assertEqual({p:n for (r,p),n in self.p.items() if r=='C93'}, {'1':'GND','2':'NINV_FB'})
        self.assertTrue(self.g.wire_connected(('C93','1'),('R9','1')))
        self.assertTrue(self.g.wire_connected(('C93','2'),('R84','2')))
        self.assertNotEqual(self.p['C93','1'],self.p['R84','1'])
        row=self.rows['C93'];symbol=self.g.refs['C93'][1]
        props={p[1]:p[2] for p in nodes(symbol,'property')}
        self.assertEqual(one(symbol,'dnp')[1],'yes')
        self.assertEqual(one(symbol,'on_board')[1],'yes')
        self.assertEqual(props['JLCPCB Exclude'],'yes')
        self.assertIn('placeholder',props['JLCPCB Audit Requirements'])
        self.assertEqual((row['Classification'],row['DNP'],row['LCSC']),('DNP','yes','C57112'))
        self.assertEqual(row['Footprint'],'BigModular:C_0603_1608Metric')
        self.assertEqual(row['Value'],'DNP CFF / TBD')
        self.assertIn('excluded purchasing',row['Sourcing'])
        self.assertEqual({r for r,v in self.rows.items() if v['DNP']=='yes'},{'D10','C62','C93'})

    def test_exact_reviewed_6219_electrical_delta_only_two_additions(self):
        candidate='6219eddcb0564f3d4e32e45aaaecf92a3316cbd7'
        prior=json.loads(old('docs/pin-net-audit.json',candidate))
        now=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
        self.assertEqual(set(now)-set(prior),{'D30','C93'})
        self.assertEqual({r:now[r] for r in prior},prior)
        before={r['Reference']:r for r in csv.DictReader(old('BOM.csv',candidate).decode().splitlines())}
        self.assertEqual({r:self.rows[r] for r in before},before)
        self.assertEqual({v['LCSC'] for v in self.rows.values()},{v['LCSC'] for v in before.values()})

    def test_no_mixed_corner_RHP_or_rating_pass(self):
        loop=self.b['negative_loop']
        self.assertEqual(loop['crossover_RHP5_screen'],'NOT_QUALIFIED')
        self.assertIsNone(loop['paired_efficiency_adverse_crossover_Hz'])
        self.assertIsNone(loop['measured_phase_margin_deg'])
        self.assertIsNone(self.b['rated_output_current'])
        self.assertFalse(self.b['qualification_complete'])
        self.assertFalse(self.b['power']['guaranteed_rating'])
        self.assertFalse(self.b['power']['nominal_eFuse_is_tolerance_bound'])
        self.assertIn('excludes loop',self.b['normal_static_screen_scope'])

    def test_leakage_recomputed_allocation_failures_are_visible(self):
        power=self.b['power'];leak=power['D30_reverse_leakage']
        self.assertIsNone(leak['documented_hot_max_A'])
        self.assertFalse(leak['guaranteed_operating_max'])
        self.assertEqual(leak['operating_assumptions_A'],{'nominal':.0005,'adverse':.005})
        self.assertEqual(leak['temperature_sensitivity_assumed_C'],[25,125])
        from split_rail_budget import corners
        prior=corners()
        import math
        for row in power['rows']:
            for key,vs,ep,en in [('nominal',9,.9,.9),('adverse',8.55,.85,.8)]:
                c=row[key];adverse=key=='adverse'
                vp=prior['positive_peak_V'] if adverse else prior['positive_nominal_V']
                vn=self.b['corners']['raw_peak_V'] if adverse else self.b['corners']['raw_nominal_magnitude_V']
                v5=prior['MID_peak_V'] if adverse else prior['MID_P5_nominal_V']
                expected_bus=vp*(row['P12_mA']/1000+.007)/ep+vn*(row['N12_mA']/1000+.007+leak['operating_assumptions_A'][key])/en+v5*.25/ep+.15
                self.assertAlmostEqual(c['bus_W'],expected_bus)
                self.assertAlmostEqual(c['input_A'],((vs-.15)-math.sqrt((vs-.15)**2-expected_bus))/.5)
                self.assertEqual(c['allocation_1p85A_pass'],c['input_A']<1.85)
                self.assertEqual(c['below_nominal_eFuse_limit'],c['input_A']<12000/6040)
        rows={(r['P12_mA'],r['N12_mA']):r['adverse'] for r in power['rows']}
        self.assertTrue(rows[400,300]['allocation_1p85A_pass'])
        self.assertFalse(rows[400,400]['allocation_1p85A_pass'])
        self.assertFalse(rows[400,400]['below_nominal_eFuse_limit'])
        self.assertFalse(rows[600,200]['allocation_1p85A_pass'])
        self.assertTrue(rows[600,200]['below_nominal_eFuse_limit'])

    def test_span_nominal_effective_and_example_are_distinct(self):
        span=self.b['capacitors']['IBB_span_bypass']
        self.assertEqual(span['nominal_uF'],4*2.2)
        self.assertAlmostEqual(span['effective_screen_uF'],4*.99*.8*.95)
        self.assertEqual(span['TI_typical_example_uF'],10)
        self.assertFalse(span['TI_example_is_specified_minimum'])
        self.assertFalse(span['guaranteed_minimum'])
        self.assertFalse(span['startup_current_ripple_qualified'])

    def test_all_108_protected_hashes_and_old_receipts_unchanged(self):
        candidate='6219eddcb0564f3d4e32e45aaaecf92a3316cbd7'
        frozen=old('docs/sr2-schematic-receipt.json',candidate)
        self.assertEqual((ROOT/'docs/sr2-schematic-receipt.json').read_bytes(),frozen)
        receipt=json.loads(frozen)
        self.assertEqual(len(receipt['protected_before_after_sha256']),108)
        for p,h in {**receipt['protected_before_after_sha256'],**receipt['frozen_SR1_sha256']}.items():
            self.assertEqual(hashlib.sha256((REPO/p).read_bytes()).hexdigest(),h,p)
        audit=json.loads((ROOT/'docs/sr2-component-audit.json').read_text())
        self.assertEqual(sum(x['physical_parts'] for x in audit['counts'].values()),116)
        self.assertEqual(audit['parts']['C8678']['count'],4)
        self.assertEqual(set(audit['parts']['C57112']['refs']),{'C62','C93'})
