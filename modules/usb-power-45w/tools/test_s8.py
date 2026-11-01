"""S8 single-board regressions: table derivation, final schematic (rail LEDs removed), S8.1 guard (reference,
clamp, pin map), S8.2 +5V crowbar, native verifier (with negative controls), P1.2 placed board and mechanics
contract, calcs.

  python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_s8.py' -v
"""
import json
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
ROOT = MODULE / 'hardware/single/usb-power-45w-single.kicad_sch'
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
                                   'U21', 'R100', 'C67', 'D22', 'TP17', *circuit_s8.CROWBAR})

    def test_no_raw_nets_or_cans(self):
        parts = circuit_s8.circuit()
        nets = {n for p in parts for n in p['pins'].values() if n}
        self.assertFalse({'P12_RAW', 'P5_RAW', 'N12_RAW', 'N12_STATUS', 'NOT_RUN'} & nets)
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
        r = verify_s8.verify(self.xml)
        self.assertEqual(r['components'], 182)
        self.assertEqual(r['digital_combinations_checked'], 512)
        g = r['overvoltage_guard_V']
        self.assertTrue(all(v > 0 for v in g['margin_min_to_peak_V'].values()), g)
        self.assertTrue(all(v >= 0 for v in g['margin_max_to_limit_V'].values()), g)
        cb = r['crowbar']
        self.assertGreater(cb['margin_min_to_stacked_peak_V'], 0)
        self.assertGreaterEqual(cb['margin_max_to_6V_V'], 0)
        self.assertTrue(all(v >= 2.5 for v in cb['gate_overdrive_x_IGT_max'].values()), cb)

    def test_negative_ov_preset_not_wired(self):
        bad = Path(self.tmp.name) / 'pre.xml'
        move_node(self.xml, bad, 'U12', '10', 'V3V3')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)

    def test_negative_guard_input_swap(self):
        bad = Path(self.tmp.name) / 'cmp.xml'
        move_node(self.xml, bad, 'U20', '4', 'REF_OV')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)

    def test_negative_clamp_not_at_gnd(self):
        bad = Path(self.tmp.name) / 'clamp.xml'
        move_node(self.xml, bad, 'D22', '1', 'MON_OVN')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)

    def test_negative_minus12_guard_on_v3v3(self):
        bad = Path(self.tmp.name) / 'v3.xml'
        move_node(self.xml, bad, 'R98', '1', 'V3V3')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)

    def test_negative_crowbar_trigger_on_v3v3(self):
        """S8.2: the crowbar trigger must run from +5V alone (a V3V3-fed trigger can misfire at power-down)."""
        bad = Path(self.tmp.name) / 'cbv3.xml'
        move_node(self.xml, bad, 'R103', '1', 'V3V3')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)

    def test_negative_crowbar_latch_link_open(self):
        bad = Path(self.tmp.name) / 'cblink.xml'
        move_node(self.xml, bad, 'Q13', '3', 'GND')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)

    def test_negative_scr_anode_not_on_5v(self):
        bad = Path(self.tmp.name) / 'cbanode.xml'
        move_node(self.xml, bad, 'Q11', '2', '+12V')
        with self.assertRaises(AssertionError):
            verify_s8.verify(bad)


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

    def test_crowbar_topology(self):
        """S8.2: SCR across +5V, TLVH432B trigger on its own 37k/10k 0.1 % divider powered by +5V, Q13 on OV_N."""
        parts = {p['ref']: p for p in circuit_s8.circuit()}
        self.assertEqual(parts['Q11']['pins'], {'1': 'GND', '2': '+5V', '3': 'CROW_GATE'})
        self.assertEqual(parts['Q11']['fp'], 'DPAK')
        self.assertEqual(parts['U22']['pins'], {'1': 'CROW_TRIP_N', '2': 'CROW_SENSE', '3': 'GND'})
        self.assertEqual((parts['R101']['value'], parts['R102']['value']), (parts['R95']['value'], parts['R96']['value']))
        self.assertEqual(parts['Q13']['pins']['3'], 'OV_N')
        nets = {n for r in circuit_s8.CROWBAR for n in parts[r]['pins'].values()}
        self.assertFalse(nets & {'V3V3', 'REF_OV', 'REF_GOOD', 'MON_OV5'})
        self.assertIsNone(parts['U20']['pins']['13'], 'U20 comparator 4 stays spare')

    def test_tlvh432_symbol_pin_numbers(self):
        """U22 symbol = stock TL431DBZ unchanged: its numbers already are the TI TLVH432 DBZ pinout (SLVS555N)."""
        import build_s8
        from sexp import one, walk
        pins = {one(p, 'name')[1]: one(p, 'number')[1] for p in walk(build_s8.tlvh432_dbz(), 'pin')}
        self.assertEqual(pins, {'K': '1', 'REF': '2', 'A': '3'})
        self.assertEqual(verify_s8.PINS_MFR['TLVH432_DBZ'], {'1': 'K', '2': 'REF', '3': 'A'})

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
        self.assertEqual(r['parts_on_board'], 182)
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
        self.assertGreater(c.startup_window(val)['ratio_min_window_to_budget'], 3)
        rel = json.loads((MODULE / 'docs/s8-single/calcs.json').read_text())['rail_release']
        ov = c.ov_guard(val, rel)
        for rail in ('+12V', '+5V', '-12V'):
            self.assertGreater(ov[rail]['release_margin_to_guard_min_V'], 0, rail)
            self.assertGreater(ov[rail]['stacked_margin_to_guard_min_V'], 0, rail)
            self.assertGreaterEqual(ov[rail]['margin_guard_max_to_limit_V'], 0, rail)
        self.assertGreater(c.reference(val)['IK_min_mA'], 0.5)
        self.assertGreater(ss['-12V']['rack_allowance_full_load_mF'], 0.3)

    def test_crowbar_screen(self):
        """S8.2: the crowbar fires in every shorted-high-side case, ends the >6 V excursion sooner than D21 alone, holds
        +5V under 6 V after firing, D3 keeps the ring above -0.5 V, and Q12 VGS stays inside +-12 V at a 10 V rail."""
        import s8_calcs as c
        parts, val = c.table()
        _, eff = c.banks(parts)
        rel = json.loads((MODULE / 'docs/s8-single/calcs.json').read_text())['rail_release']
        cb = c.crowbar(val, eff, c.ov_guard(val, rel))
        self.assertGreater(cb['margin_min_to_stacked_peak_V'], 0)
        self.assertGreaterEqual(cb['margin_max_to_6V_V'], 0)
        self.assertGreater(cb['trigger']['Q12_VGS_at_10V_rail_V'], cb['trigger']['Q12_VGS_limit_V'])
        for name, case in cb['hs_short_time_domain']['cases'].items():
            on, off = case['crowbar'], case['S8.1_no_crowbar']
            self.assertIsNotNone(on['t_scr_fire_us'], name)
            self.assertLess(on['t_above_6V_us'], off['t_above_6V_us'] / 3, name)
            self.assertLess(on['v5_max_after_fire_2us'], 6.0, name)
            self.assertGreater(on['v5_min_V'], -0.5, name)
            self.assertGreater(on['vin_min_V'], -0.8, name)
            self.assertLess(on['i2t_A2s'], 0.01 * 60, name)


if __name__ == '__main__':
    unittest.main()
