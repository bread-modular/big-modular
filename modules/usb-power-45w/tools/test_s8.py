"""S8 single-board regressions: table derivation, final schematic (rail LEDs removed), S8.1 guard (reference,
clamp, pin map), S8.3 +5V series disconnect, native verifier (negative controls), P1.3 board and mechanics
contract, calcs.

  python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_s8.py' -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import circuit45  # noqa: E402
import circuit_s8  # noqa: E402
import verify_s8  # noqa: E402

MODULE = HERE.parent
DESIGN = Path(os.environ.get('S8_DESIGN_ROOT', str(MODULE)))
ROOT = DESIGN / 'hardware/single/usb-power-45w-single.kicad_sch'

def verify_native(path):
    return verify_s8.verify(path, hardware=DESIGN / 'hardware', root=ROOT)
BOARD = ROOT.with_suffix('.kicad_pcb')


def export_netlist(dest):
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(dest), str(ROOT)],
                   check=True, stdout=subprocess.DEVNULL)


def move_node(src, dst, ref, pin, to_net):
    """Copy of a native netlist with one pin moved to another named net (negative control)."""
    tree = ET.parse(src)
    nets = tree.getroot().find('nets')
    node = next(n for net in nets for n in net.findall('node') if n.get('ref') == ref and n.get('pin') == pin)
    for net in nets:
        if node in list(net):
            net.remove(node)
    next(net for net in nets if net.get('name').split('/')[-1] == to_net).append(node)
    tree.write(dst)


class TableDerivation(unittest.TestCase):
    def test_s7_table_untouched(self):
        before = json.dumps(circuit45.circuit(), sort_keys=True, default=str)
        circuit_s8.circuit()
        self.assertEqual(before, json.dumps(circuit45.circuit(), sort_keys=True, default=str))

    def test_removed_and_added(self):
        s7 = {p['ref'] for p in circuit45.circuit()}
        s8 = {p['ref'] for p in circuit_s8.circuit()}
        self.assertFalse(set(circuit_s8.S8_REMOVED) & s8)
        self.assertEqual(s7 - s8, set(circuit_s8.S8_REMOVED))
        self.assertTrue({'U6', 'U7', 'U8', 'Q4', 'U16', 'U17'} <= set(circuit_s8.S8_REMOVED))
        self.assertEqual(s8 - s7, {'J3', 'C59', 'C60', 'C61', 'C62', 'R92', 'U20', 'R93', 'R94', 'R95', 'R96',
                                   'R97', 'R98', 'R99', 'C63', 'C64', 'C65', 'C66', 'D21',
                                   'U21', 'R100', 'C67', 'D22', 'TP17', *circuit_s8.DISCONNECT})

    def test_only_5v_retains_raw_net_no_cans(self):
        parts = circuit_s8.circuit()
        nets = {n for p in parts for n in p['pins'].values() if n}
        self.assertFalse({'P12_RAW', 'N12_RAW', 'N12_STATUS', 'NOT_RUN'} & nets)
        self.assertFalse([p['ref'] for p in parts if p['fp'] == 'CP63' or p['sym'] == 'C_Polarized'])
        by = {p['ref']: p for p in parts}
        self.assertEqual(by['U12']['pins']['10'], 'OV_N')
        self.assertEqual(by['J2']['pins'], by['J3']['pins'])


class NativeS8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.xml = Path(cls.tmp.name) / 's8.xml'
        export_netlist(cls.xml)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_verifier_passes(self):
        r = verify_native(self.xml)
        self.assertEqual(r['components'], 188)
        self.assertEqual(r['digital_combinations_checked'], 512)
        g = r['overvoltage_guard_V']
        self.assertTrue(all(v > 0 for v in g['margin_min_to_peak_V'].values()), g)
        self.assertTrue(all(v >= 0 for v in g['margin_max_to_limit_V'].values()), g)
        ef = r['disconnect']
        self.assertGreater(ef['margin_min_to_stacked_peak_V'], 0.05)
        self.assertFalse(ef['OVLO_latched_internally'])
        self.assertFalse(ef['OVLO_response_max_specified'])
        self.assertGreater(r['comparator_supply']['full_temp_headroom_V'], 10)

    def test_negative_ov_preset_not_wired(self):
        bad = Path(self.tmp.name) / 'pre.xml'
        move_node(self.xml, bad, 'U12', '10', 'V3V3')
        with self.assertRaises(AssertionError):
            verify_native(bad)

    def test_negative_guard_input_swap(self):
        bad = Path(self.tmp.name) / 'cmp.xml'
        move_node(self.xml, bad, 'U20', '4', 'REF_OV')
        with self.assertRaises(AssertionError):
            verify_native(bad)

    def test_negative_clamp_not_at_gnd(self):
        bad = Path(self.tmp.name) / 'clamp.xml'
        move_node(self.xml, bad, 'D22', '1', 'MON_OVN')
        with self.assertRaises(AssertionError):
            verify_native(bad)

    def test_negative_minus12_guard_on_v3v3(self):
        bad = Path(self.tmp.name) / 'v3.xml'
        move_node(self.xml, bad, 'R98', '1', 'V3V3')
        with self.assertRaises(AssertionError):
            verify_native(bad)

    def test_disconnect_negative_controls(self):
        for ref,pin,net in [('U23','5','+5V'), ('U23','6','P5_RAW'), ('U23','1','V3V3'),
                            ('U23','3','OV_N'), ('U23','4','GND'), ('R95','1','+5V'),
                            ('R11','2','+5V'), ('C69','1','+5V'), ('C73','1','P5_RAW'),
                            ('D21','1','+5V'), ('D23','1','P5_RAW'), ('C68','1','P5_OVLO'),
                            ('U20','3','V3V3'), ('U18','3','V3V3')]:
            with self.subTest(ref=ref,pin=pin,net=net):
                bad=Path(self.tmp.name)/f'{ref}-{pin}.xml'
                move_node(self.xml,bad,ref,pin,net)
                with self.assertRaises(AssertionError): verify_native(bad)

    def test_wrong_pin_role_rejected(self):
        tree=ET.parse(self.xml)
        pin=tree.find('./libparts/libpart[@part="TPS259470_RPW"]/pins/pin[@num="5"]')
        pin.set('name','OUT')
        bad=Path(self.tmp.name)/'pinrole.xml';tree.write(bad)
        with self.assertRaises(AssertionError): verify_native(bad)


class FinalSchematic(unittest.TestCase):
    def test_rail_leds_removed_main_kept(self):
        parts = {p['ref']: p for p in circuit_s8.circuit()}
        self.assertFalse(set(circuit_s8.LED_REMOVED) & set(parts))
        self.assertTrue(set(circuit_s8.LED_REMOVED) <= set(circuit_s8.S8_REMOVED))
        leds = sorted(r for r, p in parts.items() if p['fp'] in ('LED3EDGE', 'LED0603'))
        self.assertEqual(leds, ['D8'])
        self.assertEqual(parts['Q6']['pins'], {'1': 'MAIN_LED_OK', '2': 'LED_RETURN', '3': '_PANEL_MAIN_K'})

    def test_guard_reference_and_clamp(self):
        """S8.1: U20 runs from REF_OV (U21), the -12V channel compares with GND, D22 clamps MON_OVN."""
        parts = {p['ref']: p for p in circuit_s8.circuit()}
        u20 = parts['U20']['pins']
        self.assertEqual({u20[k] for k in ('5', '7', '10')}, {'REF_OV'})
        self.assertEqual((u20['8'], u20['9']), ('GND', 'MON_OVN'))
        self.assertNotIn('REF_GOOD', u20.values())
        self.assertEqual(parts['D22']['pins'], {'1': 'GND', '2': 'MON_OVN', '3': 'MON_OVN'})
        self.assertEqual(parts['R98']['pins'], {'1': 'REF_OV', '2': 'MON_OVN'})
        for r in ('R93', 'R94', 'R95', 'R96', 'R98', 'R99'):
            self.assertEqual(parts[r]['fields']['Tolerance'], '0.1%', r)
        self.assertEqual({parts[u]['fields']['MPN'] for u in ('U18', 'U20')}, {'LM2901BIDR'})

    def test_disconnect_topology(self):
        parts={p['ref']:p for p in circuit_s8.circuit()}
        self.assertFalse(set(circuit_s8.CROWBAR_REMOVED)&set(parts))
        self.assertFalse(any(n and n.startswith('CROW_') for p in parts.values() for n in p['pins'].values()))
        self.assertEqual(parts['U23']['pins'], {'1':'RUN','2':'P5_OVLO','3':'P5_OK','4':'P5_OK',
                         '5':'P5_RAW','6':'+5V','7':'P5_DVDT','8':'GND','9':'P5_ILM','10':None})
        self.assertEqual(parts['R11']['pins']['2'],'P5_RAW')
        for r in ('U18','U20'): self.assertEqual(parts[r]['pins']['3'],'VPD')
        for r in ('C57','C65'):
            self.assertEqual(parts[r]['pins']['1'],'VPD')
            self.assertEqual(parts[r]['fields']['Voltage'],'50V')

    def test_tps259470_symbol_and_land_pattern(self):
        import s83_parts
        from sexp import one,walk,nodes,parse
        sym=s83_parts.symbol()
        pins={one(p,'number')[1]:one(p,'name')[1] for p in walk(sym,'pin')}
        self.assertEqual(pins,verify_s8.TPS259470_TI)
        fp=parse(s83_parts.footprint())
        pads=[p for p in nodes(fp,'pad') if p[1]]
        self.assertEqual({p[1] for p in pads},set(map(str,range(1,11))))
        self.assertEqual(len(pads),14)  # four L-shaped pads represented by two pieces
        for n,x in [('5',-.25),('6',.25)]:
            p=next(p for p in pads if p[1]==n)
            self.assertEqual(list(map(float,one(p,'at')[1:])),[x,0])
            self.assertEqual(list(map(float,one(p,'size')[1:])),[.3,2.4])
        paste=[p for p in nodes(fp,'pad') if not p[1]]
        self.assertEqual(len(paste),16)
        self.assertTrue(all(one(p,'layers')[1:]==['F.Paste'] for p in paste))
        self.assertFalse(any('via'==v[0] for v in fp if isinstance(v,list)))
        self.assertEqual((MODULE/'hardware/USBPOWER45.pretty'/
                         (s83_parts.FP_S83['RPW10']+'.kicad_mod')).read_text(), s83_parts.footprint())

    def test_tlv431_symbol_pin_numbers(self):
        """U21 symbol = stock TL431DBZ drawing renumbered to TI TLV431 DBZ (SLVS139Z Table 4-1)."""
        import build_schematic as bs
        import build_s8
        from sexp import one, walk
        sym = build_s8.tlv431_dbz()
        pins = {one(p, 'name')[1]: one(p, 'number')[1] for p in walk(sym, 'pin')}
        self.assertEqual(pins, {'REF': '1', 'K': '2', 'A': '3'})
        stock, _, _ = bs.stock_symbol('Reference_Voltage', 'TL431DBZ')
        self.assertEqual({one(p, 'name')[1]: one(p, 'number')[1] for p in walk(stock, 'pin')},
                         {'K': '1', 'REF': '2', 'A': '3'}, 'stock TL431DBZ changed: re-check the renumbering')


class PlacedBoard(unittest.TestCase):
    """P1 trial placement (tools/place_s8.py) on the Z50 single carrier: every part on F, rules checked."""

    def test_placement_rules(self):
        out = subprocess.run([sys.executable, '-B', str(HERE / 'check_s8_board.py'), '--board', str(BOARD)],
                             capture_output=True, text=True, check=True).stdout
        r = json.loads(out[out.index('{'):])
        self.assertTrue(r['pass'], {k: r[k] for k in ('parked_parts', 'courtyard_overlaps', 'edge_rule_findings_not_approved')})
        self.assertEqual(r['parts_on_board'], 188)
        self.assertEqual((r['parked_parts'], r['parts_on_B'], r['tracks'], r['zones']), ([], [], 0, 0))
        self.assertEqual(set(r['headers_vs_contract']), {'J2', 'J3'})
        self.assertTrue(all(h['matches'] for h in r['headers_vs_contract'].values()))
        self.assertEqual(r['board_rear_edge_Z_from_panel_front'], 50.0)
        for ref in ('J1', 'D8', 'J2', 'J3'):
            self.assertEqual(r['hand_solder_2mm'][ref]['violations_lt_2mm'], [], ref)

    def test_table_covers_every_part_once(self):
        import build_s8_board
        import place_s8
        t = place_s8.table()
        refs = {p['ref'] for p in circuit_s8.circuit() if not p['ref'].startswith('#')}
        self.assertEqual(set(t) | set(build_s8_board.FIXED), refs)
        self.assertFalse(set(t) & set(build_s8_board.FIXED))
        self.assertTrue(all(a % 90 == 0 for _, _, a in t.values()))

    def test_mechanical_contract(self):
        import mechanics_s8
        g = mechanics_s8.geometry()
        self.assertEqual(g['carrier_Z_mm'], [2.0, 50.0])
        self.assertEqual([l['reference'] for l in g['LEDs']], ['D8'])
        self.assertEqual([h['pin1_YZ_mm'] for h in g['headers']], [[76.0, 44.0], [107.0, 44.0]])
        rep, problems = mechanics_s8.verify(g)
        self.assertEqual(problems, [])


class Calcs(unittest.TestCase):
    def test_closed_form_screens(self):
        import s8_calcs as c
        parts, val = c.table()
        banks, eff = c.banks(parts)
        self.assertGreater(banks['+12V']['eff_uF'][0], 10)      # TI minimum effective COUT
        self.assertGreater(banks['+5V']['eff_uF'][0], 10)
        ss = c.soft_start(val, eff)
        self.assertGreater(ss['+12V']['track_ramp_max_C_mF']['full_load'], 1.0)
        self.assertGreater(c.startup_window(val)['ratio_min_window_to_budget'], 2)
        rel = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['rail_release']
        ov = c.ov_guard(val, rel)
        for rail in ('+12V', '+5V', '-12V'):
            self.assertGreater(ov[rail]['release_margin_to_guard_min_V'], 0, rail)
            self.assertGreater(ov[rail]['stacked_margin_to_guard_min_V'], 0, rail)
            self.assertGreaterEqual(ov[rail]['margin_guard_max_to_limit_V'], 0, rail)
        self.assertGreater(c.reference(val)['IK_min_mA'], 0.5)
        self.assertGreater(ss['-12V']['rack_allowance_full_load_mF'], 0.3)

    def test_disconnect_screen_and_delay_sensitivity(self):
        import s8_calcs as c
        parts,val=c.table(); _,eff=c.banks(parts)
        rel=json.loads((DESIGN/'docs/s8-single/calcs.json').read_text())['rail_release']
        ef=c.disconnect(val,eff,c.ov_guard(val,rel))
        self.assertGreater(ef['normal_margin_to_OVLO_min_V'],.05)
        self.assertGreater(ef['current_min_nom_max_A'][0],2.5)
        self.assertLess(ef['current_min_nom_max_A'][2],3.5)
        self.assertIsNone(ef['OVLO_response_max_us'])
        self.assertFalse(ef['FLT_reports_OVLO']);self.assertTrue(ef['AUXOFF_reports_OVLO'])
        self.assertFalse(ef['fault_delay_sensitivity']['guaranteed_bound'])
        cases=ef['fault_delay_sensitivity']['cases']
        for case in cases.values():
            self.assertIsNotNone(case['t_disconnect_us'])
            self.assertIsNotNone(case['t_U5_off_us'])
            self.assertLess(case['header_peak_V'],case['raw_peak_V'])
        self.assertGreater(cases['L1uH_delay5us']['header_peak_V'], cases['L1uH_delay1.2us']['header_peak_V'])
        # Do not encode "always <6V": the sensitivity sweep intentionally exposes the unqualified cases.
        self.assertTrue(any(v['header_peak_V']>6 for v in cases.values()))

    def test_fault_screen_timestep_convergence(self):
        import s8_calcs as c
        _,eff=c.banks(c.table()[0]);cin=eff['VIN'][1]+eff['damper'][1]
        kw=dict(c_in=cin,c_raw=eff['P5_RAW'][0],c_out=eff['+5V'][0],trip=5.848,delay=1.2e-6)
        a,b=c._disconnect_run(**kw),c._disconnect_run(**kw,dt=2.5e-9)
        self.assertLess(abs(a['header_peak_V']-b['header_peak_V']),.005)

    def test_comparator_headroom_and_legacy_failure(self):
        import s8_calcs as c
        self.assertLess(3.3*.98-2.0-1.259,0)
        self.assertGreater(c.comparator_supply(c.table()[1])['input_headroom_V'],10)


if __name__ == '__main__':
    unittest.main()
