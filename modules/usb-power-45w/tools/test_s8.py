"""S8 single-board regressions: table derivation, final schematic (rail LEDs removed), S8.1 guard (reference,
clamp, pin map), S8.3 +5V series disconnect, native verifier (negative controls), P1.4 board and mechanics
contract, calcs. S8.4 review fixes: C1 (U23 FLT never reaches P5_OK / the latch), M1 (TIMER_GO follows MAIN_OK,
not V20_OK), M2 (load release vs OVLO, falling threshold), M3 (V3V3 loss), M4 (local loops), M5 (rating),
M6 (-12V start-up into a typical rack), M7 (U23 mask webs), M8 (Basic-only counterfactual), M9 (mechanical risks),
C2 (<6 V not guaranteed, stays exposed). S8.5: B (one-shot arming: STARTED latch, TIMER_GO = RUN AND STARTED,
V20_OK status floor; the S8.4 wiring and the S8.4 V20_OK divider must fail - regressions), C (MAIN_LED_OK / ANY_BAD
semantics, replug/POR race stays an explicit OPEN item, review record hashes only tracked files). S9.0 step 1: the +5V
subsystem is gone - no +5V/P5_*/EF_* net or +5V ref survives anywhere (table, native netlist, schematic, BOM, placement,
PCB), J2/J3 pins 11/12 open, ANY_BAD without P5_OK, spare comparators defined. S9.0 step 2: 15 V input (R1/R3/R83), the
TPS552892-Q1 buck-boost (duty proof: the S8 buck cannot regulate at 15 V, the buck-boost does everywhere; pinned symbol and
land pattern; cell wiring; ratings and the 3 A total), NO reverse blocking (owner decision: exact rail memberships, no
ideal-diode/FET part, a series element is rejected), the arming chain end to end without P5_OK, the two accepted residuals
recorded with bench-test conditions, the 20 V retarget delta, and a review record that hashes only tracked files. S9.2
(routing-ready): D24 SMBJ20A coordinated with the 15 V U5 OVP (R24 9.1k), C82.2 on PGND with R113 the only AGND_U2 bridge,
R109 on a 4-terminal Kelvin land with its own sense nets, the R115 N_EN_RETURN default, the U4 enable truth table and the
3 A source plant DERIVED from the native netlist (negative controls break single nets and must fail), the thermal rating
conditional on the routing contract, the routing-contract screen of the 1.5 mm acceptance pads, and routing-notes.md
read back against the netlist, the contract and the review record (mutated copies must fail).

  python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_s8.py' -v
"""
import json
import math
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
COMPONENTS = 175                       # S9.0: 191 - 45 (+5V) + 10 (TPS552892-Q1); S9.1 +8; S9.2 + R115 + 10 test pads
ROOT = DESIGN / 'hardware/single/usb-power-45w-single.kicad_sch'

def verify_native(path):
    return verify_s8.verify(path, hardware=DESIGN / 'hardware', root=ROOT)
BOARD = ROOT.with_suffix('.kicad_pcb')


def export_netlist(dest):
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(dest), str(ROOT)],
                   check=True, stdout=subprocess.DEVNULL)


def rewire(src, dst, moves):
    """Copy of a native netlist with pins moved to other nets; a net name that does not exist yet is created."""
    tree = ET.parse(src)
    nets = tree.getroot().find('nets')
    code = max(int(n.get('code')) for n in nets)
    for ref, pin, to_net in moves:
        node = next(n for net in nets for n in net.findall('node') if n.get('ref') == ref and n.get('pin') == pin)
        for net in nets:
            if node in list(net):
                net.remove(node)
        target = next((net for net in nets if net.get('name').split('/')[-1] == to_net), None)
        if target is None:
            code += 1
            target = ET.SubElement(nets, 'net', {'code': str(code), 'name': to_net, 'class': 'Default'})
        target.append(node)
    tree.write(dst)


# The S8.4 arming wiring rebuilt on the S8.5 netlist: TIMER_GO = RUN AND MAIN_OK, U11 RESET -> START_READY -> U12 A CLK,
# U12 A Q = ARMED (PRE_N high), U14 gate 2 unused (inputs GND, output open).
S84_ARMING = [('U13', '10', 'MAIN_OK'), ('U11', '1', 'START_READY'), ('R71', '2', 'START_READY'),
              ('U12', '3', 'START_READY'), ('U12', '5', 'ARMED'), ('U12', '4', 'V3V3'),
              ('U14', '8', 'unconnected-(U14-Pad8)'), ('U14', '9', 'GND'), ('U14', '10', 'GND'), ('U14', '12', 'GND'),
              ('U14', '13', 'GND')]


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


def set_component(src, dst, ref, value=None, **fields):
    """Copy of a native netlist with one component's value and/or fields changed (negative control)."""
    tree = ET.parse(src)
    comp = next(c for c in tree.getroot().find('components') if c.get('ref') == ref)
    if value is not None:
        comp.find('value').text = value
    for name, text in fields.items():
        comp.find(f'fields/field[@name="{name}"]').text = text
    tree.write(dst)


class TableDerivation(unittest.TestCase):
    def test_s7_table_untouched(self):
        before = json.dumps(circuit45.circuit(), sort_keys=True, default=str)
        circuit_s8.circuit()
        self.assertEqual(before, json.dumps(circuit45.circuit(), sort_keys=True, default=str))

    def test_removed_and_added(self):
        s7 = {p['ref'] for p in circuit45.circuit()}
        s8 = {p['ref'] for p in circuit_s8.circuit()}
        removed = set(circuit_s8.S8_REMOVED) | set(circuit_s8.S9_REMOVED)
        self.assertFalse(removed & s8)
        self.assertEqual(s7 - s8, removed)
        self.assertTrue({'U6', 'U7', 'U8', 'Q4', 'U16', 'U17'} <= set(circuit_s8.S8_REMOVED))
        self.assertTrue({'U3', 'L2', 'R11', 'R12', 'D3', 'C35', 'R44', 'TP13'} <= set(circuit_s8.S9_REMOVED))
        self.assertEqual(s8 - s7, {'J3', 'C59', 'C61', 'C62', 'R92', 'U20', 'R93', 'R94', 'R97', 'R98', 'R99',
                                   'C63', 'C65', 'C66', 'U21', 'R100', 'C67', 'D22', 'TP17',
                                   *circuit_s8.ARMING_ADDED, *circuit_s8.BUCKBOOST_ADDED, *circuit_s8.S91_ADDED,
                                   *circuit_s8.S92_ADDED, '#FLG10'})
        self.assertFalse(set(circuit_s8.S8_PLUS5_DROPPED) & s8)

    def test_no_raw_or_plus5_nets_no_cans(self):
        parts = circuit_s8.circuit()
        nets = {n for p in parts for n in p['pins'].values() if n}
        self.assertFalse({'P12_RAW', 'N12_RAW', 'N12_STATUS', 'NOT_RUN', 'START_READY'} & nets)
        self.assertFalse(set(circuit_s8.PLUS5_NETS) & nets)
        self.assertFalse({n for n in nets if n.startswith(('P5_', 'EF_')) or n in ('+5V', 'FIVE_V')})
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
        self.assertEqual(r['components'], COMPONENTS)
        self.assertEqual(r['digital_combinations_checked'], 512)
        g = r['overvoltage_guard_V']
        self.assertEqual(set(g['margin_min_to_peak_V']), {'+12V', '-12V'})
        self.assertTrue(all(v > 0 for v in g['margin_min_to_peak_V'].values()), g)
        self.assertTrue(all(v >= 0 for v in g['margin_max_to_limit_V'].values()), g)
        self.assertEqual(g['OV_N_members'], ['R97.2', 'TP6.1', 'U12.10', 'U20.14', 'U20.2'])
        self.assertGreater(r['comparator_supply']['full_temp_headroom_V'], 5)
        self.assertEqual(r['plus5_removed']['ANY_BAD'], 'NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3)')
        # S8.5 B: one-shot arming record, every timeline against R1-R4 without a violation
        a = r['startup_arming']
        self.assertEqual((a['TIMER_GO'], a['START_N']), ('RUN AND STARTED', 'NAND(MAIN_LED_OK, RUN)'))
        self.assertFalse(a['MAIN_OK_in_timer_path'] or a['V20_OK_in_timer_path'])
        self.assertEqual(a['STARTED_members'], ['TP19.1', 'U12.5', 'U13.10'])
        self.assertEqual(a['ARMED_members'], ['R71.2', 'TP10.1', 'U11.1', 'U13.4'])
        self.assertEqual(a['violations'], [])
        self.assertTrue({'cold_start_worst_loaded_15V', 'brownout_after_ARMED', 'hot_plug_live_bus',
                         'load_release_after_ARMED'} <= set(a['timelines']))
        b = r['plus12_buckboost']
        self.assertEqual(b['pin_roles'], 'native symbol = TI SLVSGT7 Table 5-1')
        self.assertEqual(b['fSW_kHz'], 966)
        self.assertTrue(b['reverse_blocking'].startswith('none'))
        self.assertGreater(a['V20_OK_margin_below_U5_off_min_V'], 2.0)
        self.assertGreater(a['V20_OK_margin_above_vSafe5V_max_V'], 2.0)

    def test_m1_timer_from_v20_ok_rejected(self):
        """Regression (S8.3 review M1): the startup timer gated by V20_OK must fail the verifier."""
        bad = Path(self.tmp.name) / 'm1.xml'
        move_node(self.xml, bad, 'U13', '10', 'V20_OK')
        with self.assertRaisesRegex(AssertionError, 'B:|TIMER_GO|STARTED|U13'):
            verify_native(bad)
        for ref, pin, net in [('U13', '9', 'V20_OK'), ('R69', '1', 'RUN'), ('U13', '10', 'V3V3'),
                              ('U13', '10', 'MAIN_OK')]:
            with self.subTest(ref=ref, pin=pin, net=net):
                bad = Path(self.tmp.name) / f'm1-{ref}-{pin}-{net}.xml'
                move_node(self.xml, bad, ref, pin, net)
                with self.assertRaises(AssertionError):
                    verify_native(bad)

    def test_b_s84_arming_wiring_fails(self):
        """Regression (all three S8.4 reviews, S8.5 item B): the exact S8.4 arming wiring (TIMER_GO = RUN AND MAIN_OK,
        U11 -> U12 A clock -> ARMED) rebuilt on this netlist must fail the arming timelines - armed in the PD 5 V phase
        and latched off before 20 V, window restarted by a brown-out inside it, U5 overload chatter never armed and never
        latched - and the verifier. This is the test that would have caught the S8.4 bug."""
        bad = Path(self.tmp.name) / 'b-s84.xml'
        rewire(self.xml, bad, S84_ARMING)
        for band in ((7.67, 8.44, 9.27), (14.62, 16.12, 17.73)):      # S9.0 and S8.4 V20_OK bands
            with self.subTest(v20=band):
                _, violations = verify_s8.arming_check(bad, band)
                for scenario, rule in (('slow_PD_contract_2s5', 'R3'), ('input_overload_chatter', 'R1/R2'),
                                       ('brownout_inside_window', 'R1/R2'), ('input_overload_chatter', 'never latched')):
                    self.assertTrue(any(v.startswith(scenario) and rule in v for v in violations), (scenario, rule))
        with self.assertRaises(AssertionError):
            verify_native(bad)
        # and the S8.5 wiring itself passes the same timelines
        self.assertEqual(verify_s8.arming_check(self.xml)[1], [])

    def test_b_arming_negative_controls(self):
        """S8.5 B: each way of breaking the one-shot latch must fail the verifier."""
        for ref, pin, net in [('U12', '3', 'ARMED'),       # STARTED clocked: a fault edge could re-load it
                              ('U12', '3', 'MAIN_OK'),
                              ('U12', '1', 'V3V3'),        # STARTED never cleared by RESET
                              ('U14', '9', 'MAIN_OK'),     # start from MAIN_OK without the V20_OK validity floor
                              ('U14', '10', 'V3V3'),       # PRE_N can fight CLR_N during RESET
                              ('U11', '1', 'STARTED'),     # ARMED not from the timer
                              ('U13', '4', 'STARTED'),
                              ('TP19', '1', 'ARMED'),
                              ('U12', '4', 'MAIN_LED_OK')]:
            with self.subTest(ref=ref, pin=pin, net=net):
                bad = Path(self.tmp.name) / f'b-{ref}-{pin}-{net}.xml'
                move_node(self.xml, bad, ref, pin, net)
                with self.assertRaises(AssertionError):
                    verify_native(bad)

    def test_native_b_nets(self):
        """B and the S9.0 fault chain straight from the exported native netlist (independent of the verifier)."""
        root = ET.parse(self.xml).getroot()
        nets = {n.get('name').split('/')[-1]: {(d.get('ref'), d.get('pin')) for d in n.findall('node')}
                for n in root.find('nets')}
        self.assertNotIn('P5_OK', nets)
        self.assertNotIn('P5_FLT_N', nets)
        self.assertIn(('U14', '4'), nets['V3V3'])
        self.assertEqual(nets['OV_N'], {('U20', '2'), ('U20', '14'), ('U12', '10'), ('R97', '2'), ('TP6', '1')})
        self.assertEqual(nets['TIMER_GO'], {('U13', '8'), ('R69', '1')})
        self.assertEqual(nets['STARTED'], {('U12', '5'), ('U13', '10'), ('TP19', '1')})
        self.assertEqual(nets['START_N'], {('U14', '8'), ('U12', '4')})
        self.assertEqual(nets['ARMED'], {('U11', '1'), ('R71', '2'), ('U13', '4'), ('TP10', '1')})
        self.assertIn(('U12', '3'), nets['GND'])
        self.assertTrue({('U2', '1')} <= nets['MAIN_OK'])          # S9.0: TPS552892 EN/UVLO (pin 1)
        for pin in ('9', '10'):
            self.assertNotIn(('U13', pin), nets['MAIN_OK'] | nets['V20_OK'])
        self.assertNotIn('START_READY', nets)

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

    def test_plus5_removal_negative_controls(self):
        """S9.0: re-attaching any former +5V function must fail the verifier (a +5V net, P5_OK into the fault chain, a
        spare comparator output back on OV_N, a header +5V pin, a former +5V ref)."""
        for ref, pin, net in [('J2', '11', '+12V'), ('J3', '12', 'GND'), ('U14', '4', 'P12_OK'), ('U20', '1', 'OV_N'),
                              ('U18', '2', 'ANY_BAD'), ('U18', '5', 'REF_GOOD'), ('U20', '7', 'REF_OV'),
                              ('U14', '4', 'P5_OK'), ('R94', '2', '+5V')]:
            with self.subTest(ref=ref, pin=pin, net=net):
                bad = Path(self.tmp.name) / f'p5-{ref}-{pin}-{net}.xml'
                rewire(self.xml, bad, [(ref, pin, net)])
                with self.assertRaises(AssertionError):
                    verify_native(bad)

    def test_wrong_pin_role_rejected(self):
        tree = ET.parse(self.xml)
        pin = tree.find('./libparts/libpart[@part="TLV431_DBZ"]/pins/pin[@num="1"]')
        pin.set('name', 'K')
        bad = Path(self.tmp.name) / 'pinrole.xml'
        tree.write(bad)
        with self.assertRaises(AssertionError):
            verify_native(bad)


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
        self.assertEqual({u20[k] for k in ('5', '6', '10')}, {'REF_OV'})
        self.assertEqual((u20['8'], u20['9']), ('GND', 'MON_OVN'))
        self.assertEqual((u20['1'], u20['7'], u20['13'], u20['11']), (None, 'GND', None, 'GND'))   # S9.0: two spares
        self.assertNotIn('REF_GOOD', u20.values())
        self.assertEqual(parts['D22']['pins'], {'1': 'GND', '2': 'MON_OVN', '3': 'MON_OVN'})
        self.assertEqual(parts['R98']['pins'], {'1': 'REF_OV', '2': 'MON_OVN'})
        for r in ('R93', 'R94', 'R98', 'R99'):
            self.assertEqual(parts[r]['fields']['Tolerance'], '0.1%', r)
        self.assertEqual({parts[u]['fields']['MPN'] for u in ('U18', 'U20')}, {'LM2901BIDR'})

    def test_plus5_removed_in_table(self):
        """S9.0 step 1 at the circuit table: U14 gate 1 input 4 high, spare comparators defined, header pins 11/12 open,
        U5 nets MAIN_*, U18/U20 still on always-on VPD with 50 V bypass capacitors."""
        parts = {p['ref']: p for p in circuit_s8.circuit()}
        self.assertEqual(parts['U14']['pins']['4'], 'V3V3')
        self.assertEqual({parts['U14']['pins'][k] for k in ('1', '2', '4', '5')}, {'MAIN_LED_OK', 'P12_OK', 'V3V3', 'N12_OK'})
        self.assertEqual((parts['U18']['pins']['2'], parts['U18']['pins']['4'], parts['U18']['pins']['5']),
                         (None, 'REF_GOOD', 'GND'))
        for j in ('J2', 'J3'):
            self.assertEqual([parts[j]['pins'][str(k)] for k in range(11, 17)], [None] * 6)
        self.assertEqual({v for k, v in parts['U5']['pins'].items() if k in ('1', '7', '8', '10', '11', '14')},
                         {'MAIN_IN', 'MAIN_UV', 'MAIN_OV', 'MAIN_DVDT', 'MAIN_ILM', 'MAIN_IMON'})
        for r in ('U18', 'U20'):
            self.assertEqual(parts[r]['pins']['3'], 'VPD')
        for r in ('C57', 'C65'):
            self.assertEqual(parts[r]['pins']['1'], 'VPD')
            self.assertEqual(parts[r]['fields']['Voltage'], '50V')
        self.assertFalse(any('+5V' in (p['value'] or '') for p in parts.values()))

    def test_b_one_shot_arming_in_table(self):
        """S8.5 B at the circuit table: STARTED = U12 A (PRE_N = START_N, CLR_N = RESET_N, CLK = GND), START_N =
        NAND(MAIN_LED_OK, RUN) on U14 gate 2, TIMER_GO = RUN AND STARTED, ARMED = the U11 output, TP19 = STARTED."""
        by = {p['ref']: p for p in circuit_s8.circuit()}
        u12, u13, u14 = by['U12']['pins'], by['U13']['pins'], by['U14']['pins']
        self.assertEqual((u12['1'], u12['2'], u12['3'], u12['4'], u12['5'], u12['6']),
                         ('RESET_N', 'V3V3', 'GND', 'START_N', 'STARTED', None))
        self.assertEqual((u14['8'], u14['9'], u14['10'], u14['12'], u14['13']),
                         ('START_N', 'MAIN_LED_OK', 'RUN', 'V3V3', 'V3V3'))
        self.assertEqual((u13['9'], u13['10'], u13['8']), ('RUN', 'STARTED', 'TIMER_GO'))
        self.assertEqual((u13['12'], u13['13'], u13['11']), ('MAIN_OK', 'V20_OK', 'MAIN_LED_OK'))
        self.assertEqual((by['U11']['pins']['1'], by['R71']['pins']['2'], u13['4']), ('ARMED', 'ARMED', 'ARMED'))
        self.assertEqual(by['TP19']['pins'], {'1': 'STARTED'})
        self.assertEqual(by['U2']['pins']['1'], 'MAIN_OK')
        self.assertEqual(by['R83']['value'], '100k')                                     # S9.0 (S8.5: 120k at 20 V)
        self.assertEqual(by['R83']['fields']['LCSC'], 'C25803')
        self.assertEqual(by['R2']['fields']['LCSC'], 'C122538')

    def test_c_main_led_ok_and_any_bad_semantics(self):
        """S8.5 C: MAIN_LED_OK = MAIN_OK AND V20_OK where V20_OK is a U5 status-validity floor (above vSafe5V, below the
        U5 turn-off minimum, each with >= 2 V), so MAIN_LED_OK = "U5 on with valid status" and ANY_BAD = NOT(MAIN_LED_OK
        AND the three rail monitors). Regression: the S8.4 200k divider (14.62-17.73 V) violates the floor rule."""
        import s8_calcs as c
        by = {p['ref']: p for p in circuit_s8.circuit()}
        u14 = by['U14']['pins']
        self.assertEqual({u14[k] for k in ('1', '2', '4', '5')}, {'MAIN_LED_OK', 'P12_OK', 'V3V3', 'N12_OK'})
        self.assertEqual(u14['6'], 'ANY_BAD')
        val = c.table()[1]
        a = c.arming(val)
        self.assertTrue(a['V20_OK']['rule_holds'])
        self.assertEqual([round(v, 2) for v in a['V20_OK']['band_V']], [7.67, 8.44, 9.27])
        self.assertFalse(a['V20_OK']['S8.4_200k_rule_holds'])
        self.assertFalse(a['V20_OK']['S8.5_120k_rule_holds_at_15V'], 'the S8.5 120k must not survive the 15 V retarget')
        for r83 in (120e3, 200e3, 220e3):
            self.assertFalse(c.v20_floor_ok(c.v20_band(val, r83), c.u5_window(val)[1]), r83)
        self.assertGreater(a['U5_turn_on_margin_unloaded_V'], 0.2)      # 14.25 V unloaded vs the 13.98 V turn-on maximum
        self.assertGreater(a['U5_running_margin_loaded_V'], 0.3)        # 13.5 V loaded vs the 13.14 V turn-off maximum
        self.assertIn('Not an input-good threshold', by['R83']['fields']['Note'])

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
        self.assertEqual(r['parts_on_board'], COMPONENTS)
        self.assertEqual((r['parked_parts'], r['parts_on_B'], r['tracks'], r['zones']), ([], [], 0, 0))
        self.assertEqual(set(r['headers_vs_contract']), {'J2', 'J3'})
        self.assertTrue(all(h['matches'] for h in r['headers_vs_contract'].values()))
        self.assertEqual(r['board_rear_edge_Z_from_panel_front'], 50.0)
        for ref in ('J1', 'D8', 'J2', 'J3'):
            self.assertEqual(r['hand_solder_2mm'][ref]['violations_lt_2mm'], [], ref)
        # S8.4 M4: the local decoupling / protection-loop contract holds for every row, U23 and U20 included
        loops = r['local_loops']
        self.assertEqual(loops['violations'], [])
        rows = {(x['from'].split('.')[0], x['purpose']): x for x in loops['rows']}
        for (ic, why), x in rows.items():
            self.assertLessEqual(x['distance_mm'], x['limit_mm'], (ic, why))
        self.assertFalse({ic for ic, _ in rows} & {'U23', 'U3'}, 'S9.0: no +5V loop rows')
        u2 = {x['purpose']: x for x in loops['rows'] if x['from'].startswith('U2.')}
        self.assertEqual({x['from'] for x in u2.values()}, {'U2.7', 'U2.11', 'U2.18'}, 'S9.0: TPS552892 VIN/VOUT/VCC rows')
        self.assertEqual({x['to'].split('.')[0] for x in u2.values()}, {'C8', 'C81', 'C82'})
        # S9.2: PGND star (R113 the only AGND_U2/PGND part) and the routing-contract screen of the unrouted board
        self.assertTrue(r['ground_split']['pass'] and r['ground_split']['parts_on_both_nets'] == ['R113'], r['ground_split'])
        self.assertTrue(r['routing_contract_screen']['pass'],
                        [x for x in r['routing_contract_screen']['test_points'] + r['routing_contract_screen']['proximity']
                         if not x['ok']])

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
        # S8.4 M9: both open IDC risks are recorded explicitly, with the numbers from the checks
        risks = {x['id']: x for x in mechanics_s8.risks(g, rep)}
        self.assertEqual(risks['IDC_strain_relief_overshoot']['value_mm'], -0.4)
        self.assertEqual(risks['IDC_envelope_margin']['value_mm'], 1.1)
        rec = json.loads((DESIGN / 'docs/s8-single/mechanical.json').read_text())
        self.assertEqual({x['id'] for x in rec['risks']} >= {'IDC_strain_relief_overshoot', 'IDC_envelope_margin'}, True)


class ReviewRecord(unittest.TestCase):
    """S9.2: docs/s8-single/review-s92.json (tools/review_s8.py) hashes match the files in the tree, and it hashes only
    files git tracks (S8.4 hashed the git-ignored *.kicad_prl files: the suite failed from a fresh checkout)."""

    def test_review_hashes_match(self):
        import hashlib
        self.assertFalse((MODULE / 'docs/s8-single/review-s85.json').exists(), 'S8.5 record replaced (git history)')
        self.assertFalse((MODULE / 'docs/s8-single/review-s91.json').exists(), 'S9.1 record replaced (git history)')
        rec_path = MODULE / 'docs/s8-single/review-s92.json'
        if DESIGN.resolve() != MODULE.resolve() or not rec_path.exists():
            self.skipTest('review record applies to the module tree once generated (tools/review_s8.py)')
        rec = json.loads(rec_path.read_text())
        self.assertEqual(rec['revision'], 'S9.2 / P2.2')
        hashed = [rel for group in ('sources_sha256', 'artifacts_sha256', 'original_S7_R3_hardware_unchanged_sha256')
                  for rel in rec[group]]
        self.assertFalse([rel for rel in hashed if rel.endswith('.kicad_prl') or rel.startswith('research/')])
        ignored = subprocess.run(['git', 'check-ignore', '--no-index', *hashed], cwd=MODULE, capture_output=True,
                                 text=True).stdout.split()
        self.assertEqual(ignored, [], 'the review record must hash only files that are not git-ignored')
        tracked = set(subprocess.run(['git', 'ls-files', '--', '.'], cwd=MODULE, capture_output=True,
                                     text=True).stdout.split())
        self.assertEqual(sorted(set(hashed) - tracked), [], 'the review record must hash only tracked files')
        for rel in ('tools/s90_parts.py', 'hardware/USBPOWER45.pretty/TI_RYQ0021B_VQFN-HR-21_3x5mm.kicad_mod',
                    'panels/front-pcb/usb-power-45w-single-panel.kicad_pcb', 'tools/s92_parts.py', 'tools/s92_netlist.py',
                    'tools/s92_contract.py', 'hardware/USBPOWER45.pretty/R_Shunt_1206_KelvinSplit_RLM12.kicad_mod',
                    'hardware/USBPOWER45.pretty/TestPoint_Pad_D1.5mm.kicad_mod', 'docs/s8-single/routing-notes.md',
                    'docs/s8-single-board.md'):
            self.assertIn(rel, hashed, rel)
        self.assertEqual(rec['routing_notes']['test_pad_rows'], 27)
        self.assertEqual(rec['accepted_residuals']['reverse_current']['decision'][:8], 'ACCEPTED')
        self.assertEqual(rec['accepted_residuals']['rail_overvoltage']['decision'][:8], 'ACCEPTED')
        for group in ('sources_sha256', 'artifacts_sha256', 'original_S7_R3_hardware_unchanged_sha256'):
            for rel, digest in rec[group].items():
                self.assertEqual(hashlib.sha256((MODULE / rel).read_bytes()).hexdigest(), digest, rel)
        self.assertFalse((MODULE / 'docs/s8-single/review-s84.json').exists(), 'S8.4 record replaced (git history)')
        self.assertFalse(rec['tests']['log_committed'])


class Plus5Removed(unittest.TestCase):
    """S9.0 regression: no +5V net, ref or part survives anywhere - schematic files, PCB, BOM, placement and board records
    (the verifier separately checks the native netlist). U5's nets are MAIN_* on the single board (EF_* only in S7)."""

    GONE_REFS = set(circuit_s8.S9_REMOVED) | set(circuit_s8.S8_PLUS5_DROPPED)

    @staticmethod
    def bad_net(name):
        name = name.split('/')[-1]
        return name in ('+5V', 'FIVE_V') or name.startswith(('P5_', 'EF_')) or name in circuit_s8.PLUS5_NETS

    def test_no_plus5_in_schematic_files(self):
        from sexp import parse, nodes, one
        files = sorted((DESIGN / 'hardware/single').glob('*.kicad_sch'))
        self.assertEqual(len(files), 6)
        self.assertFalse((DESIGN / 'hardware/single/03_positive_5v.kicad_sch').exists())
        for f in files:
            tree = parse(f.read_text())
            for sym in nodes(tree, 'symbol'):
                ref = next(p[2] for p in nodes(sym, 'property') if p[1] == 'Reference')
                self.assertNotIn(ref, self.GONE_REFS, f.name)
                self.assertNotEqual(one(sym, 'lib_id')[1], 'USBPOWER45:+5V', f.name)
            for kind in ('label', 'hierarchical_label', 'global_label'):
                for lab in nodes(tree, kind):
                    self.assertFalse(self.bad_net(lab[1]), (f.name, lab[1]))
        lib = parse((DESIGN / 'hardware/single/USBPOWER45.kicad_sym').read_text())
        self.assertFalse({s[1] for s in nodes(lib, 'symbol')} & {'+5V', 'TPS259470_RPW', 'TPS62933F'})

    def test_no_plus5_on_the_pcb(self):
        from sexp import parse, nodes, one
        tree = parse(BOARD.read_text())
        nets = {n[2] for n in nodes(tree, 'net') if len(n) > 2} | {n[1] for n in nodes(tree, 'net') if len(n) == 2}
        self.assertFalse({n for n in nets if isinstance(n, str) and self.bad_net(n)})
        refs = {next(p[2] for p in nodes(f, 'property') if p[1] == 'Reference') for f in nodes(tree, 'footprint')}
        self.assertFalse(refs & self.GONE_REFS)
        self.assertFalse(any('RPW0010A' in f[1] for f in nodes(tree, 'footprint')))

    def test_no_plus5_in_records(self):
        import csv
        with (DESIGN / 'docs/s8-single/bom.csv').open() as fh:
            rows = list(csv.DictReader(fh))
        bom_refs = {r for row in rows for r in row['Refs'].split(',')}
        self.assertFalse(bom_refs & self.GONE_REFS)
        self.assertFalse({row['MPN'] for row in rows} & verify_s8.FORBIDDEN_MPN)
        placed = set(json.loads((DESIGN / 'docs/s8-single/placement.json').read_text())['parts'])
        self.assertFalse(placed & self.GONE_REFS)
        build = json.loads((DESIGN / 'docs/s8-single/build.json').read_text())
        self.assertEqual(set(build['removed_in_S9_plus5']), {r for r in self.GONE_REFS})
        self.assertFalse({n for n in build['inter_sheet_nets'] if self.bad_net(n)})
        board = json.loads((DESIGN / 'docs/s8-single/board-p1.json').read_text())
        self.assertFalse({row['from'].split('.')[0] for row in board['local_loops']['rows']} & self.GONE_REFS)


class Calcs(unittest.TestCase):
    def test_closed_form_screens(self):
        import s8_calcs as c
        parts, val = c.table()
        banks, eff = c.banks(parts)
        self.assertGreater(banks['+12V']['eff_uF'][0], 10)      # TI minimum effective COUT
        self.assertNotIn('+5V', banks)
        ss = c.soft_start(val, eff)
        self.assertEqual(ss['+12V']['rack_allowance_mF'], c.TYPICAL_RACK_MF)     # TI 1000 uF ceiling - bank
        self.assertLess(ss['+12V']['time_to_full_at_allowance_full_load_ms'], 309 * 0.5)
        self.assertGreater(c.startup_window(val)['ratio_min_window_to_budget'], 2)
        rel = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['rail_release']
        ov = c.ov_guard(val, rel)
        self.assertEqual({k for k in ov if k.startswith(('+', '-'))}, {'+12V', '-12V'})
        for rail in ('+12V', '-12V'):
            self.assertGreater(ov[rail]['release_margin_to_guard_min_V'], 0, rail)
            self.assertGreater(ov[rail]['stacked_margin_to_guard_min_V'], 0, rail)
            self.assertGreaterEqual(ov[rail]['margin_guard_max_to_limit_V'], 0, rail)
        self.assertGreater(c.reference(val)['IK_min_mA'], 0.5)
        self.assertGreater(ss['-12V']['rack_allowance_full_load_mF'], c.TYPICAL_RACK_MF)

    def test_m6_minus12_starts_typical_rack(self):
        """S8.4 M6 acceptance: the published -12V allowance = min(LMR38020 hiccup-rule model at the converter input of
        the U5 turn-on minimum, 1 A from 0 V, half the typical-only blanking; TI's ~1000 uF total-COUT guidance) covers
        the typical 0.44 mF rack with margin."""
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        m = c.minus12_startup(val, eff)
        self.assertTrue(m['typical_rack_starts'])
        pub = m['published_allowance_mF']
        self.assertGreater(pub, c.TYPICAL_RACK_MF + 0.3)
        # the published allowance never exceeds TI's total-COUT guidance or the hiccup model, also at the U5 sag corner
        self.assertLessEqual(pub, m['TI_COUT_guidance']['rack_allowance_mF'])
        self.assertLessEqual(pub + m['TI_COUT_guidance']['design_value_mF'], 1.0 + 1e-9)
        self.assertLessEqual(pub, m['hiccup_model_allowance_mF'])
        self.assertTrue(m['model_covers_published_at_sag'])
        self.assertEqual(m['vin_floor_V'], c.converter_vin(c.u5_window(val)[0][0]))
        self.assertEqual(m['vin_sag_sensitivity_V'], c.converter_vin(c.u5_window(val)[1][0]))
        for case in m['cases'].values():
            self.assertGreater(case['rack_allowance_mF'], pub)
            self.assertLess(case['time_to_full_12V_at_that_C_ms'], 309 * 0.5)

    def test_m5_published_rating(self):
        """Published rating: 75 % of the minimum current-limited capability, nearest 0.1 A, +/-12V only."""
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        r = c.rating(val, eff)
        self.assertEqual(set(r['published_A']), {'+12V', '-12V'})
        self.assertGreaterEqual(r['headroom_to_capability_A']['+12V'], .20)
        self.assertLessEqual(r['fraction_of_capability']['-12V'], .77)
        self.assertEqual(r['vin_floor_V'], c.converter_vin(c.VPD_RATED_MIN))
        self.assertLess(r['below_rated_range']['fraction_of_capability']['+12V'], .92)
        self.assertLess(r['below_rated_range']['fraction_of_capability']['-12V'], .87)

    def test_u5_window_arithmetic(self):
        """U5 UVLO thresholds referred to VPD: TI 1.176/1.2/1.224 V rising, 1.09/1.122/1.15 V falling, R2 100k / R3 10k
        (S9.0, 15 V input; 7.5k at 20 V) at 1 % + 1 % TCR, and the 150 nA pin leakage through R2 (I x R2, not I x R2||R3)."""
        import s8_calcs as c
        on, off = c.u5_window(c.table()[1])
        lo,hi=.999*.9975,1.001*1.0025
        leak=150e-9*100e3*hi
        rblo=10000*lo+510*.99*.99; rbhi=10000*hi+510*1.01*1.01
        self.assertAlmostEqual(on[0],1.176*(1+100000*lo/rbhi)-leak,places=9)
        self.assertAlmostEqual(on[2],1.224*(1+100000*hi/rblo)+leak,places=9)
        self.assertAlmostEqual(off[0],1.09*(1+100000*lo/rbhi)-leak,places=9)
        self.assertEqual([round(v,2) for v in on],[12.26,12.62,12.98])
        self.assertEqual([round(v,2) for v in off],[11.37,11.80,12.19])
        self.assertLessEqual(on[2],13.0)
        self.assertGreater(13.5-on[2],.5)
        self.assertAlmostEqual(c.INPUT_DROP_V, 0.75 + 0.053 * 4.698, places=9)      # U5 high-corner limit
        self.assertEqual(c.INPUT_PATH['I_A'], c.input_budget()['U5_limit_screen_A'][2])

    def test_m3_v3v3_loss_bounded(self):
        import s8_calcs as c
        v = c.v3v3_loss(c.table()[1])
        self.assertTrue(all(x['node_current_bound_uA'] < 150 for x in v['minus12_held'].values()))
        self.assertNotIn('replug_REF_OV_settle_ms', v, 'S8.4 replug margin withdrawn (replug_por)')
        self.assertIn('NOT a guaranteed', v['verdict'])

    def test_c_replug_por_race_is_open(self):
        """S8.5 C (Astra S8.4 MAJOR-1): REF_OV (R100/C67, loaded by R98 into the D22-clamped MON_OVN) against the >= 12 ms
        TPS3808 POR when the rack already holds -12V. The nominal case clears, the worst corner does not: the margin is
        NOT established and stays an explicit OPEN item. If a fix makes it pass, update the doc and the review gates."""
        import s8_calcs as c
        r = c.replug_por(c.table()[1])
        self.assertFalse(r['established'])
        self.assertTrue(r['status'].startswith('OPEN'))
        self.assertLess(r['cases']['-12V_nominal']['settle_ms'], r['POR_RESET_release_min_ms'])
        self.assertGreater(r['worst_settle_ms'], r['POR_RESET_release_min_ms'])
        rec = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())
        self.assertEqual(rec['replug_por']['established'], False)

    def test_b_arming_window_budget(self):
        """S8.5 B: the one-shot window (U11 100n, 0.31-0.88 s) is longer than the serial rail-up budget, so a normal
        start is armed with every rail up; calcs.json carries the arming record."""
        import s8_calcs as c
        val = c.table()[1]
        w = c.startup_window(val)
        self.assertGreater(w['ratio_min_window_to_budget'], 2)
        a = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['arming']
        self.assertTrue(a['V20_OK']['rule_holds'])
        self.assertEqual(len(a['required']), 4)
        self.assertEqual(a['topology']['TIMER_GO'][:24], 'U13 gate 3 = RUN AND STA')

    def test_m8_basic_only_counterfactual_fails(self):
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        rel = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['rail_release']
        cf = c.basic_only_counterfactual(val, eff, rel)
        self.assertTrue(cf['failing'], 'with 1 % parts some precision screen must fail (else revisit the policy)')
        self.assertEqual(cf['precision_refs'], ['R93', 'R94', 'R98', 'R99'])
        self.assertEqual(c.ov_guard(val, rel)['+12V']['guard_V'], c.ov_guard(val, rel)['+12V']['guard_V'])
        self.assertEqual(c.corners('R93'), c.R01, 'globals restored')

    def test_comparator_headroom_and_legacy_failure(self):
        import s8_calcs as c
        self.assertLess(3.3*.98-2.0-1.259,0)
        self.assertGreater(c.comparator_supply(c.table()[1])['input_headroom_V'], 8)     # S9.0: VPD down to 11.55 V


class S90Retarget(unittest.TestCase):
    """S9.0 step 2: 15 V input, the TPS552892-Q1 buck-boost (duty resolution), no reverse blocking (owner decision), the
    arming chain without P5_OK end to end, the accepted residuals and the 20 V retarget delta."""

    @classmethod
    def setUpClass(cls):
        cls.by = {p['ref']: p for p in circuit_s8.circuit()}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.xml = Path(cls.tmp.name) / 's90.xml'
        export_netlist(cls.xml)
        root = ET.parse(cls.xml).getroot()
        cls.nets = {n.get('name').split('/')[-1]: {(d.get('ref'), d.get('pin')) for d in n.findall('node')}
                    for n in root.find('nets')}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_15v_input_in_table(self):
        by = self.by
        self.assertEqual((by['R1']['value'], by['R1']['fields']['LCSC'], by['R1']['fields']['MPN']),
                         ('56k', 'C23206', '0603WAF5602T5E'))                   # CH224A CFG1: 15 V request (Basic)
        self.assertEqual((by['R2']['value'], by['R3']['value'], by['R83']['value']), ('100k', '10k', '100k'))
        self.assertEqual((by['R28']['value'], by['R4']['value'], by['R24']['value']), ('10k', '120k', '9.1k'),
                         'S9.2: U5 OVP retuned to the 15 V input (18.34 V nominal), below the D24 stand-off')
        self.assertIn('15 V / 3 A fixed PDO', by['U1']['fields']['Note'])

    def test_plus12_duty_resolution(self):
        """The S8 TPS62933F buck cannot regulate +12V at the 15 V input (fails even unloaded at the setpoint maximum and
        needs more than a compliant source can give); the TPS552892-Q1 regulates at every corner from the U5 sag to 21 V."""
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        b = c.plus12_buckboost(val, eff)
        s8 = b['S8_TPS62933F_at_15V']
        self.assertFalse(s8['regulates_at_rated_min'] or s8['regulates_unloaded_at_rated_min'])
        self.assertGreater(s8['required_duty']['VIN12.5_I0A_max'], s8['D_max'])
        self.assertGreater(s8['min_VPD_for_regulation_V'], c.VPD_UNLOADED_MIN)
        self.assertTrue(b['regulates_everywhere'])
        rows = b['TPS552892_operation']
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(r['margin_to_ILIM_AVG_min_A'] > 2.0 for r in rows.values()), rows)
        self.assertEqual({r['mode'] for r in rows.values()}, {'boost', 'buck-boost (alternating cycles)', 'buck'})
        self.assertLess(b['limits']['L_min_from_inner_loop_uH'], b['limits']['L1_uH'])
        self.assertTrue(all(x['Tj_at_50C_ambient_JEDEC_C'] <= 125 for x in b['losses'].values()))
        self.assertTrue(b['compensation']['pass'],b['compensation']['violations'][:1])
        self.assertGreater(b['compensation']['worst_phase']['phase_margin_deg'],45)
        self.assertGreater(b['compensation']['worst_gain']['gain_margin_dB'],10)

    def test_buckboost_cell_in_table(self):
        by = self.by
        u2 = by['U2']
        self.assertEqual((u2['value'], u2['fp'], u2['fields']['LCSC']), ('TPS552892QWRYQRQ1', 'RYQ21', 'C22375748'))
        self.assertEqual({k: u2['pins'][k] for k in ('1', '7', '11', '12', '13', '2', '21', '18', '5', '9', '17')},
                         {'1': 'MAIN_OK', '7': 'VIN', '11': 'P12_VOUT', '12': 'P12_ISP', '13': 'P12_ISN', '2': '_VCC_U2',
                          '21': '_VCC_U2', '18': '_VCC_U2', '5': 'AGND_U2', '9': 'GND', '17': 'AGND_U2'})
        self.assertEqual((u2['pins']['3'], u2['pins']['4'], u2['pins']['16']), (None, None, None))
        self.assertEqual((by['R109']['value'], by['R109']['fp'], by['R109']['fields']['LCSC'], by['R109']['pins']),
                         ('0.018', 'KELVIN1206', 'C393095', {'1': 'P12_VOUT', '2': 'P12_ISP', '3': 'P12_ISN', '4': '+12V'}))
        self.assertEqual((by['L1']['pins'], by['C10']['pins'], by['C9']['pins']),
                         ({'1': '_SW1_U2', '2': '_SW2_U2'}, {'1': '_BST1_U2', '2': '_SW1_U2'}, {'1': '_BST2_U2', '2': '_SW2_U2'}))
        self.assertEqual((by['R8']['value'], by['R9']['value'], by['R110']['value']), ('68k', '7.5k', '20k'))

    def test_pinned_symbol_and_land_pattern(self):
        """U2 symbol pins = TI SLVSGT7 Table 5-1; the committed footprint is exactly tools/s90_parts.footprint(); every
        copper gap between differently numbered lands >= 0.20 mm and every mask web >= 0.15 mm; 21 numbered pads."""
        import s90_parts
        from sexp import parse, nodes, one, walk
        pins = {one(q, 'number')[1]: one(q, 'name')[1] for q in walk(s90_parts.symbol(), 'pin')}
        self.assertEqual(pins, s90_parts.TPS552892_TI)
        self.assertEqual((MODULE / 'hardware/USBPOWER45.pretty' / (s90_parts.FP_S90['RYQ21'] + '.kicad_mod')).read_text(),
                         s90_parts.footprint())
        pads = [(str(q[1]), *map(float, one(q, 'at')[1:3]), *map(float, one(q, 'size')[1:3]),
                 float(one(q, 'solder_mask_margin')[1])) for q in nodes(parse(s90_parts.footprint()), 'pad') if q[1]]
        self.assertEqual({q[0] for q in pads}, set(s90_parts.TPS552892_TI))
        gaps = []
        for a in pads:
            for b in pads:
                if a[0] < b[0]:
                    dx = abs(a[1] - b[1]) - (a[3] + b[3]) / 2
                    dy = abs(a[2] - b[2]) - (a[4] + b[4]) / 2
                    gaps.append(math.hypot(max(dx, 0), max(dy, 0)) if (dx > 0 and dy > 0) else max(dx, dy))
        self.assertGreaterEqual(round(min(gaps), 6), s90_parts.COPPER_GAP_MIN)
        self.assertGreaterEqual(round(min(gaps) - 2 * s90_parts.MASK_MARGIN, 6), 0.15)

    def test_no_reverse_blocking(self):
        """Owner decision (S9.0): no reverse-current blocking hardware. No ideal-diode controller / series FET part, the
        rail memberships are exact (R109 is the only series element, inside the converter), and inserting a series
        element on a rail fails the verifier. The accepted residual is recorded (calcs, validation)."""
        import s8_calcs as c
        mpns = {p['fields'].get('MPN', '') for p in self.by.values()}
        self.assertFalse({m for m in mpns if m.upper().startswith(verify_s8.REVERSE_BLOCKING_MPN_PREFIXES)})
        for net, members in verify_s8.RAILS_S90.items():
            self.assertEqual({k for k in self.nets[net] if not k[0].startswith('#')}, members, net)
        lib = (DESIGN / 'hardware/single/USBPOWER45.kicad_sym').read_text()
        self.assertFalse(any(s in lib for s in ('LM74700', 'LM5051', 'LTC4357', 'FDS6630A')))
        self.assertFalse((MODULE / 'hardware/USBPOWER45.pretty/SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod').exists())
        for moves in ([('J2', '9', 'P12_BLK'), ('J3', '9', 'P12_BLK'), ('J2', '10', 'P12_BLK'), ('J3', '10', 'P12_BLK')],
                      [('U4', '1', 'N12_BLK'), ('U4', '9', 'N12_BLK')]):
            with self.subTest(moves=moves):
                bad = Path(self.tmp.name) / f'rb-{moves[0][2]}.xml'
                rewire(self.xml, bad, moves)
                with self.assertRaises(AssertionError):
                    verify_native(bad)
        rec = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['residuals']['reverse_current']
        self.assertTrue(rec['decision'].startswith('ACCEPTED'))
        self.assertIn('No powered parallel', rec['rule'])
        self.assertTrue(rec['minus12_active']['finding'].startswith('FIXED'))
        self.assertLess(rec['minus12_active']['enable_logic']['off_relative_max_V'], .95)
        val = json.loads((DESIGN / 'docs/s8-single/validation.json').read_text())
        self.assertTrue(val['accepted_residuals']['reverse_current']['decision'].startswith('ACCEPTED'))
        self.assertTrue(val['accepted_residuals']['rail_overvoltage']['decision'].startswith('ACCEPTED'))
        self.assertEqual(c.PUBLISHED_A, {'+12V': 2.4, '-12V': 0.8})

    def test_arming_chain_end_to_end_without_p5(self):
        """The fault/arming chain from the native netlist: MAIN_OK (U5 FLT + PGOOD) enables U2 and, with V20_OK, makes
        MAIN_LED_OK; START_N = NAND(MAIN_LED_OK, RUN) presets STARTED; TIMER_GO = RUN AND STARTED -> U11 -> ARMED; FAULT is
        clocked by ARMED AND BAD_FILTERED (ANY_BAD = NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3)) and preset by OV_N; RUN = U5
        SHDN. No +5V status anywhere."""
        n = self.nets
        self.assertFalse({k for k in n if k.startswith('P5_') or k in ('+5V', 'FIVE_V')})
        self.assertTrue({('U5', '15'), ('U5', '16'), ('U2', '1'), ('U13', '12'), ('R63', '2')} <= n['MAIN_OK'])
        self.assertTrue({('U13', '11'), ('U14', '1'), ('U14', '9')} <= n['MAIN_LED_OK'])
        self.assertTrue({('U13', '13'), ('U18', '13')} <= n['V20_OK'])
        self.assertEqual(n['START_N'], {('U14', '8'), ('U12', '4')})
        self.assertEqual(n['STARTED'], {('U12', '5'), ('U13', '10'), ('TP19', '1')})
        self.assertEqual(n['TIMER_GO'], {('U13', '8'), ('R69', '1')})
        self.assertTrue({('U11', '1'), ('U13', '4')} <= n['ARMED'])
        self.assertTrue({('U14', '2'), ('U18', '1')} <= n['P12_OK'] and {('U14', '5'), ('U18', '14')} <= n['N12_OK'])
        self.assertIn(('U14', '4'), n['V3V3'])
        self.assertTrue({('U14', '6'), ('R72', '1')} <= n['ANY_BAD'])
        self.assertTrue({('U13', '6'), ('U12', '11')} <= n['FAULT_CLK'])
        self.assertTrue({('U12', '10'), ('U20', '2'), ('U20', '14')} <= n['OV_N'])
        self.assertTrue({('U13', '3'), ('U5', '13')} <= n['RUN'])
        import s8_calcs as c
        a = c.arming(c.table()[1])
        self.assertIn('ANY_BAD', a['topology'])
        self.assertIn('P5_OK input high', a['topology']['ANY_BAD'])

    def test_ratings_and_contract(self):
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        r = c.rating(val, eff)
        self.assertEqual(r['published_A'], {'+12V': 2.4, '-12V': 0.8})
        self.assertEqual(r['published_total_W'], 33)
        self.assertTrue(r['per_rail_ratings_at_once']['exceeds_3A_contract'], 'hence the simultaneous total')
        pd = c.pd_contract(val)
        self.assertEqual((pd['contract_A'], pd['stated_input_range_V']), (3.0, [13.5, 16.5]))
        self.assertIn('>= 45 W', pd['required_adapter'])
        self.assertGreater(pd['max_module_output_W']['nominal_15V_source_worst_mix'], r['published_total_W'])

    def test_residuals_recorded_as_bench_events(self):
        rec = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['residuals']
        for key in ('reverse_current', 'rail_overvoltage'):
            self.assertTrue(rec[key]['decision'].startswith('ACCEPTED'), key)
            bt = rec[key]['bench_test']
            self.assertTrue(bt['conditions'] and bt['status'].startswith('proposed'), key)
        ov = rec['rail_overvoltage']
        self.assertEqual(len(ov['why_no_fuse']), 4)
        self.assertTrue(ov['bench_test']['downstream_qualification'])
        self.assertLessEqual(ov['peak_screens_V']['+12V_D26_rated_clamp_25C'], 24.5)
        self.assertIn('deferred', ov['decision'])

    def test_retarget_20v_includes_clamp_changes(self):
        import s8_calcs as c
        r = c.retarget_20v(c.table()[1])
        self.assertEqual(set(r['changes']), {'R1', 'R3', 'R114', 'R83', 'R24', 'D24', 'D25', 'docs'})
        self.assertLess(r['U5_window_V']['on'][2],18.25)
        self.assertTrue(r['V20_OK_rule_holds'])
        self.assertEqual((r['plus12']['rating_A'], r['minus12']['rating_A']), (2.4, 0.9))
        self.assertGreater(r['plus12']['D'][0], r['plus12']['D_min_tON'])


class S91ReviewFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.xml=Path(cls.tmp.name)/'s91.xml'; export_netlist(cls.xml)
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_self_enable_and_ground_merge_negative_controls(self):
        for ref,pin,net in [('Q1','2','+12V'),('Q1','2','VIN'),('R16','1','GND'),
                            ('Q14','1','+12V'),('Q15','1','V3V3'),('U2','17','GND'),
                            ('C82','2','AGND_U2'),('R110','2','GND'),('R113','1','GND'),     # S9.2: C82.2 is PGND
                            ('D24','1','VPD'),('D25','2','GND'),('D26','1','VIN'),
                            ('R115','1','GND'),('U2','12','P12_VOUT'),('R109','3','+12V')]:
            with self.subTest(ref=ref,pin=pin,net=net):
                bad=Path(self.tmp.name)/'bad.xml'; rewire(self.xml,bad,[(ref,pin,net)])
                with self.assertRaises(AssertionError): verify_native(bad)

    def test_enable_truth_table_and_voltage_bounds(self):
        """S9.2: the record is derived from the generator netlist (s92_netlist.enable_model); the native-netlist version
        and its negative controls are in S92RoutingReady."""
        import s8_calcs as c, s91_analysis as a
        v=c.table()[1]; q=a.enable()
        self.assertTrue(q['pass'], q['violations'][:2])
        self.assertGreater(q['startup_min_relative_V'],1.4)
        self.assertLess(q['off_relative_max_V'],.95)
        for row in q['truth_table']:
            if not row['own_input'] or not row['run'] or not row['main_status']:
                self.assertFalse(row['U4_enabled'])
        # Off-state pull-up is deliberately strong, not the original 100k.
        self.assertEqual((v('R16'),v('R112')),(33000,5100))
        by=c.table()[0]
        self.assertEqual(by['Q1']['pins']['2'],'VPD')
        self.assertEqual(by['Q14']['pins']['1'],'RUN')
        self.assertEqual(by['Q15']['pins']['1'],'MAIN_LED_OK')

    def test_input_divider_really_guarantees_loaded_start(self):
        import s8_calcs as c, s91_analysis as a
        q=a.input_qualification(c.table()[1])
        self.assertLessEqual(q['on_V'][2],13.0)
        self.assertGreaterEqual(q['loaded_start_margin_V'],.5)
        self.assertGreaterEqual(q['running_margin_V'],1.3)
        self.assertTrue(q['recommended_falling_11V8_not_guaranteed'])
        self.assertLess(q['off_V'][0],11.8)  # never conceal the intrinsic comparator spread

    def test_compensation_full_loop_and_old_compensator_rejected(self):
        import s8_calcs as c,s91_analysis as a
        p,v=c.table();_,e=c.banks(p);op=c.p12(v)
        now=a.loop(v,e,c.converter_vin(c.u5_window(v)[1][0]),op)
        self.assertTrue(now['pass'],now['violations'][:1]);self.assertGreaterEqual(now['cases'],10000)
        self.assertGreater(now['worst_phase']['phase_margin_deg'],45)
        self.assertGreater(now['worst_gain']['gain_margin_dB'],10)
        old=lambda ref: {'R111':9100.,'C83':10e-9}.get(ref,v(ref))
        bad=a.loop(old,e,c.converter_vin(c.u5_window(v)[1][0]),op)
        self.assertFalse(bad['pass'],'S9.0 compensator must fail the very same envelope')

    def test_clamps_energy_and_honest_residuals(self):
        rec=json.loads((DESIGN/'docs/s8-single/calcs.json').read_text())
        q=rec['residuals']['reverse_current'];cl=q['clamps']
        self.assertEqual((cl['D24']['MPN'],cl['D24']['stand_off_V'],cl['D24']['peak_pulse_W']),('SMBJ20A',20,600))
        self.assertAlmostEqual(cl['D24']['pulse_budget']['max_energy_J'],1*32.4*.020)
        self.assertGreater(cl['D24']['pulse_budget']['margin'],2.0)
        self.assertLess(cl['D24']['rated_clamp_V'],36)
        self.assertLess(cl['D26']['rated_clamp_V'],25)
        self.assertIn('UNQUALIFIED',q['minus12_passive']['fast_step_residual'])
        self.assertNotIn('expected to FAIL',str(q['bench_test']))
        ov=rec['residuals']['rail_overvoltage']
        self.assertIn('T2-D',str(ov['bench_test']['conditions']))
        self.assertIn('+14.0V',str(ov['bench_test']['conditions']))
        self.assertIn('NEVER require it off while injection remains',str(ov['bench_test']['pass_criteria_this_module']))
        val=json.loads((DESIGN/'docs/s8-single/validation.json').read_text())
        self.assertEqual(val['accepted_residuals'],rec['residuals'])

    def test_current_limit_thermal_not_130C(self):
        import s8_calcs as c
        p,v=c.table();_,e=c.banks(p);r=c.plus12_buckboost(v,e)
        self.assertGreaterEqual(r['R109_cc_limit_A'][0],2.615)     # S9.2: + 0.2 % Kelvin residual (s8_calcs.R109_TOL)
        self.assertLessEqual(r['R109_cc_limit_A'][2],2.946)
        self.assertLessEqual(max(x['Tj_at_50C_ambient_JEDEC_C'] for x in r['losses'].values()),125)
        self.assertLess(max(x['P_R109_W'] for x in r['losses'].values()),.16)

    def test_source_limit_and_power_epochs_cannot_be_hidden(self):
        """S9.2: the 3 A rows come from the netlist-derived plant (S92RoutingReady runs it on the native netlist with
        negative controls). Strict 3 A at the published load + rack must END FAIL-SAFE (FAULT latched, RUN low, input
        off), never armed after hidden U5 retries; the minimal no-load case must start in one attempt."""
        import s91_analysis as a
        r=json.loads((DESIGN/'docs/s8-single/validation.json').read_text())['startup_arming']
        self.assertEqual(r['violations'],[])
        for key,row in r['timelines']['source_limit_3A'].items():
            if key=='why':continue
            self.assertLessEqual(row['max_input_A'],3.)
            self.assertTrue(row['source_limit_observed'])
            self.assertTrue(row['ends_faulted'] and not row['ends_running'] and not row['ends_armed'], row)
            self.assertLessEqual(row['input_after_fault_A'],.05)
            self.assertGreater(row['u5_dropouts_after_first_enable'],0,'the strict 3 A start is NOT a single attempt')
        for key,row in r['timelines']['source_3A_no_load_no_rack'].items():
            if key=='why':continue
            self.assertTrue(row['ends_armed'] and row['ends_running'] and not row['FAULT_ms'], row)
            self.assertEqual(row['u5_dropouts_after_first_enable'],0)
            self.assertLessEqual(row['max_input_A'],3.)
        for key,row in r['timelines']['power_reset_rearm_persistent_short'].items():
            if key=='why':continue
            self.assertEqual(row['power_epochs'],2);self.assertEqual(len(row['FAULT_ms']),2)
            self.assertTrue(row['ends_faulted'])
        events=[{'cause':'source_hard_reset','fault_present':True,'fault_latched':False}]*10
        # A final successful-looking cycle MUST NOT erase ten failed epochs.
        events.append({'cause':'normal','fault_present':False,'fault_latched':False})
        self.assertEqual(a.qualify_epochs(events),'FAIL_REPEATED_POWER_RESET')
        self.assertEqual(a.qualify_epochs([{'cause':'manual','fault_present':True,'fault_latched':False}]),'FAIL_MASKED_FAULT')
        self.assertEqual(a.qualify_epochs([{'cause':'manual','fault_present':True,'fault_latched':True}]),'PASS')

    def test_no_stale_plus5_silk_and_ground_contract(self):
        from sexp import parse,nodes
        t=parse(BOARD.read_text())
        self.assertNotIn('P5',[n[1] for n in nodes(t,'gr_text')])
        p=json.loads((DESIGN/'docs/s8-single/placement.json').read_text())
        self.assertEqual(p['ground_connection']['sole_link'],'R113')
        self.assertEqual(p['ground_connection']['at'],'C82.2')
        self.assertEqual(p['ground_connection']['pgnd_at_star'],['C82.2','R113.2'])
        self.assertEqual(p['revision'],'S9.2 / P2.2')


ROUTING_READY = 'Routing-ready. The items in `routing-notes.md` are post-prototype acceptance tests, not design blockers.'


def routing_notes_problems(notes, doc):
    """What docs/s8-single/routing-notes.md (notes) and docs/s8-single-board.md (doc) get wrong against the design: every
    test pad with its netlist net exactly once, a register row for every acceptance-test ID the contract and the review
    record use, every PENDING copper item named, the key contract rules, and the routing-ready statement. Empty = OK."""
    import review_s8
    import s92_contract
    idx = s92_contract.notes_index(notes)
    want = {p['ref']: p['pins']['1'] for p in circuit_s8.circuit() if p['ref'].startswith('TP')}
    out = [f'pad {r}: notes {idx["pads"].get(r)} != netlist {n}' for r, n in sorted(want.items()) if idx['pads'].get(r) != n]
    out += [f'extra pad row {r}' for r in sorted(set(idx['pads']) - set(want))]
    out += [f'duplicate pad row {r}' for r in idx['duplicate_pads']]
    used = s92_contract.contract_ids() | s92_contract.referenced_ids(*review_s8.OPEN_GATES)
    out += [f'undefined acceptance-test ID {i}' for i in sorted(used - idx['ids'])]
    screen = json.loads((DESIGN / 'docs/s8-single/board-p1.json').read_text())['routing_contract_screen']
    out += [f'PENDING item {x} not listed' for x in screen['pending_after_routing'] if f'`{x}`' not in notes]
    out += [f'rule missing: {x}' for x in ('C82.2 is PGND', 'R_Shunt_1206_KelvinSplit_RLM12', 'TestPoint_Pad_D1.5mm',
                                           'at most one AGND_U2 via pair') if x not in notes]
    if ROUTING_READY not in doc:
        out.append('routing-ready statement missing from s8-single-board.md')
    if '(s8-single/routing-notes.md)' not in doc:
        out.append('s8-single-board.md does not link the routing notes')
    return out


class S92RoutingReady(unittest.TestCase):
    """S9.2 / P2.2 items 1-6, each checked on the exported native netlist / board / records, with negative controls that
    break one net or value in a copy of the netlist and must make the check fail."""

    @classmethod
    def setUpClass(cls):
        import s92_netlist
        cls.n = s92_netlist
        cls.by = {p['ref']: p for p in circuit_s8.circuit()}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.xml = Path(cls.tmp.name) / 's92.xml'
        export_netlist(cls.xml)
        cls.design = s92_netlist.Design.from_xml(cls.xml)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def bad(self, name, moves=None, **component):
        path = Path(self.tmp.name) / f'{name}.xml'
        if moves:
            rewire(self.xml, path, moves)
        else:
            set_component(self.xml, path, **component)
        return path

    # ---- item 4: U4 enable truth table derived from the native netlist ------------------------------------------------
    def test_enable_truth_table_from_native_netlist(self):
        m = self.n.enable_model(self.design)
        self.assertTrue(m['pass'], m['violations'][:3])
        s = m['structure']
        self.assertEqual((s['U4'], s['EN'], s['U4_GND'], s['R_top'], s['R_bot'], s['PNP'], s['emitter'], s['pullups']),
                         ('U4', 'EN_N', '-12V', 'R17', 'R18', 'Q1', 'VPD', ['R112']))
        self.assertEqual(s['sink_chains'], [{'R': 'R16', 'series_nmos': [['Q15', 'MAIN_LED_OK'], ['Q14', 'RUN']],
                                             'end': 'GND', 'node_defaults': {'N_EN_RETURN': ['R115']}}])
        self.assertEqual(len(m['truth_table']), 16)
        for row in m['truth_table']:
            self.assertIs(row['U4_enabled'], row['own_input'] and row['run'] and row['main_status'], row)
            self.assertEqual(row['undefined_nodes'], [], row)
        on = [r for r in m['truth_table'] if r['U4_enabled']]
        self.assertGreater(min(r['EN_relative_V'][0] for r in on), self.n.EN_U4['on_max'])
        self.assertLess(max(r['EN_relative_V'][1] for r in m['truth_table'] if not r['U4_enabled']), self.n.EN_U4['off_min'])
        self.assertLess(m['off_VEB_max_V'], self.n.PNP['veb_off'])
        # the generator table and the native schematic give the same table, and the records carry it
        import s91_analysis
        self.assertEqual(s91_analysis.enable()['truth_table'], m['truth_table'])
        self.assertEqual(json.loads((DESIGN / 'docs/s8-single/validation.json').read_text())['enable_logic']['truth_table'],
                         m['truth_table'])

    def test_enable_negative_controls(self):
        """Break one net (or the R115 value) in a copy of the native netlist: the derived truth table must fail."""
        cases = {'Q1 emitter on +12V (bus self-enable)': [('Q1', '2', '+12V')],
                 'Q1 emitter on VIN': [('Q1', '2', 'VIN')],
                 'Q15 gate on V3V3 (MAIN_LED_OK bypassed)': [('Q15', '1', 'V3V3')],
                 'Q14 gate on V3V3 (RUN bypassed)': [('Q14', '1', 'V3V3')],
                 'R16 sink straight to GND': [('R16', '1', 'GND')],
                 'R115 open (N_EN_RETURN floating)': [('R115', '1', 'R115_OPEN')],
                 'R112 open (no base pull-up)': [('R112', '1', 'R112_OPEN')],
                 'Q14 drain on GND (switch shorted)': [('Q14', '3', 'GND')]}
        for why, moves in cases.items():
            with self.subTest(why):
                d = self.n.Design.from_xml(self.bad(why.split()[0] + moves[0][2], moves))
                try:
                    m = self.n.enable_model(d)
                except AssertionError:
                    continue                               # unmodelled structure: also a failure of the derived check
                self.assertFalse(m['pass'], why)
                self.assertTrue(m['violations'])
        m = self.n.enable_model(self.n.Design.from_xml(self.bad('R115_47k', ref='R115', value='47k')))
        self.assertFalse(m['pass'], 'R115 below ~50k lets the Q15 source follower bias Q1 on with RUN low')
        self.assertTrue(self.n.enable_model(self.n.Design.from_xml(self.bad('R115_1M', ref='R115', value='1M')))['pass'])
        for name, moves in (('verify-Q1', [('Q1', '2', '+12V')]), ('verify-R115', [('R115', '1', 'R115_OPEN')])):
            with self.subTest(name), self.assertRaises(AssertionError):
                verify_native(self.bad(name, moves))
        with self.assertRaises(AssertionError):
            verify_native(self.bad('verify-R115-47k', ref='R115', value='47k'))

    # ---- item 4: 3 A source plant derived from the native netlist ------------------------------------------------------
    def test_three_amp_plant_from_native_netlist(self):
        import s91_analysis
        import s8_calcs as c
        phys = self.n.plant_inputs(self.design)
        prm = phys['params']
        self.assertEqual((prm['U5'], prm['U5_SHDN_net'], prm['U2_EN_net'], phys['U4_gates']),
                         ('U5', 'RUN', 'MAIN_OK', ['MAIN_LED_OK', 'RUN']))
        self.assertEqual((prm['UVLO_divider']['top'], prm['UVLO_divider']['bottom']), (['R2'], ['R3', 'R114']))
        self.assertEqual(sorted(prm['OVP_divider']['top']), ['R28', 'R4'])
        self.assertEqual(prm['OVP_divider']['bottom'], ['R24'])
        q = s91_analysis.input_qualification(c.table()[1])        # independent closed form (s91_analysis)
        for a, b in zip(prm['U5_on_V'], q['on_V']):
            self.assertAlmostEqual(a, b, places=2)
        cl = prm['current_limit']
        self.assertTrue(cl['limited'] and cl['kelvin_4_terminal'])
        self.assertEqual((cl['shunt'], cl['force_nets']), ('R109', ['+12V', 'P12_VOUT']))
        self.assertEqual([round(x, 3) for x in cl['icc_A']], [round(x, 3) for x in c.p12(c.table()[1])['icc_A']])
        self.assertEqual(len(prm['banks']['P12_VOUT']), 6)
        rec = json.loads((DESIGN / 'docs/s8-single/validation.json').read_text())['startup_plant_inputs']
        self.assertEqual(rec['U5_on_V'], [round(x, 3) for x in prm['U5_on_V']])
        results, violations = verify_s8.arming_check(self.xml)
        self.assertEqual(violations, [])
        for key, row in results['source_limit_3A'].items():
            if key != 'why':
                self.assertTrue(row['ends_faulted'] and not row['ends_running'], row)
                self.assertLessEqual(row['max_input_A'], 3.0)
        for key, row in results['source_3A_no_load_no_rack'].items():
            if key != 'why':
                self.assertTrue(row['ends_armed'] and row['u5_dropouts_after_first_enable'] == 0, row)

    def test_three_amp_negative_controls(self):
        """The plant reads its enables, limits and thresholds from the netlist: breaking them changes the result."""
        for name, moves in (('U5 SHDN on V3V3 (input never removed)', [('U5', '13', 'V3V3')]),
                            ('U2 EN on V3V3 (converter not gated by MAIN_OK)', [('U2', '1', 'V3V3')])):
            with self.subTest(name):
                _, violations = verify_s8.arming_check(self.bad(name.split()[0] + moves[0][1], moves))
                self.assertTrue(any(v.startswith('source_limit_3A: not fail-safe') for v in violations), violations[:2])
        tied = self.bad('isp_isn_tied', [('U2', '12', '+12V'), ('U2', '13', '+12V')])
        cl = self.n.current_limit(self.n.Design.from_xml(tied))
        self.assertFalse(cl['limited'], 'ISP tied to ISN disables the CC limit (TI Table 5-1)')
        with self.assertRaises(AssertionError):
            verify_native(tied)
        trim = self.n.startup_params(self.n.Design.from_xml(self.bad('r114_open', [('R114', '1', 'R114_OPEN')])))
        self.assertGreater(trim['U5_on_V'][2], 13.5, 'without R114 the derived turn-on maximum moves above 13.5 V')

    # ---- item 1: D24 / OVP coordination -------------------------------------------------------------------------------
    def test_d24_ovp_coordination(self):
        import s8_calcs as c
        by = self.by
        self.assertEqual((by['D24']['value'], by['D24']['fields']['LCSC'], by['R24']['value']), ('SMBJ20A', 'C151257', '9.1k'))
        v = c.vin_clamp_coordination(c.table()[1])
        self.assertEqual([k for k, r in v['candidates'].items() if r['pass']], ['SMBJ20A + S9.2 R24 9.1k'])
        self.assertEqual({k.split(' + ')[0] for k in v['candidates']}, {'SMBJ16A', 'SMBJ18A', 'SMBJ20A', 'SMBJ24A'})
        ch = v['candidates']['SMBJ20A + S9.2 R24 9.1k']
        self.assertGreaterEqual(ch['VR_V'], 1.15 * 16.5)
        self.assertGreater(ch['VBR_min_0C_V'], ch['OVP_rise_max_V'])
        self.assertLessEqual(ch['VC_V'] * 1.15, 42.0)
        self.assertLess(ch['VC_V'] + 14.02, 50.0)
        self.assertGreater(v['choice']['normal_operation']['OVP_rise_min_V'], 16.5)
        self.assertTrue(v['choice']['normal_operation']['recovers_above_vSrcNew_max_15.75V'])
        self.assertAlmostEqual(v['pulse_budget']['budget_J'], 0.648)
        rec = json.loads((DESIGN / 'docs/s8-single/validation.json').read_text())['vin_clamp_coordination']
        self.assertTrue(all(rec['checks'].values()), rec)
        self.assertLess(rec['U5_OVP_rise_V'][2], rec['VR'])
        self.assertTrue(all(verify_s8.d24_coordination(self.design)[2].values()))
        # negative controls: the S9.1 divider (OVP up to 25.6 V) or the S9.1 TVS on this netlist fail the derived rules,
        # and the verifier rejects both netlists
        for name, comp, failing in (('S9.1 OVP divider', dict(ref='R24', value='6.8k'),
                                     {'OVP_max_below_standoff', 'VBR_min_0C_above_OVP_max'}),
                                    ('S9.1 TVS', dict(ref='D24', value='SMBJ16A', MPN='SMBJ16A'),
                                     {'standoff_ge_1p15_x_16p5', 'OVP_max_below_standoff', 'VBR_min_0C_above_OVP_max'})):
            with self.subTest(name):
                bad = self.bad(name.replace(' ', '_'), **comp)
                checks = verify_s8.d24_coordination(self.n.Design.from_xml(bad))[2]
                self.assertEqual({k for k, ok in checks.items() if not ok}, failing)
                with self.assertRaises(AssertionError):
                    verify_native(bad)

    # ---- item 2: PGND star ----------------------------------------------------------------------------------------------
    def test_pgnd_star_at_c82(self):
        nets = self.design.nets
        self.assertEqual(self.by['C82']['pins'], {'1': '_VCC_U2', '2': 'GND'})
        self.assertEqual(self.by['R113']['pins'], {'1': 'AGND_U2', '2': 'GND'})
        self.assertEqual(nets['AGND_U2'], {('U2', '5'), ('U2', '17'), ('R9', '2'), ('R110', '2'), ('C83', '2'),
                                           ('R113', '1'), ('TP28', '1')})
        both = sorted({r for r, _ in nets['AGND_U2']} & {r for r, _ in nets['GND']} - {'U2'})
        self.assertEqual(both, ['R113'])
        board = json.loads((DESIGN / 'docs/s8-single/board-p1.json').read_text())
        self.assertTrue(board['ground_split']['pass'])
        self.assertEqual(board['ground_split']['parts_on_both_nets'], ['R113'])
        star = next(x for x in board['routing_contract_screen']['proximity'] if x['from'] == 'C82.2')
        self.assertTrue(star['ok'] and star['to'] == 'R113.2' and star['distance_mm'] <= 3.0, star)
        rule = json.loads((DESIGN / 'docs/s8-single/placement.json').read_text())['routing_contract']['ground']['rule']
        self.assertIn('C82.2 is PGND', rule)
        for moves in ([('C82', '2', 'AGND_U2')], [('C83', '2', 'GND')], [('TP28', '1', 'GND')]):
            with self.subTest(moves=moves), self.assertRaises(AssertionError):
                verify_native(self.bad('star-' + moves[0][0], moves))

    # ---- item 3: Kelvin land ----------------------------------------------------------------------------------------------
    def test_r109_true_kelvin_land(self):
        import s92_parts
        pretty = MODULE / 'hardware/USBPOWER45.pretty'
        self.assertEqual((pretty / (s92_parts.FP_S92['KELVIN1206'] + '.kicad_mod')).read_text(), s92_parts.kelvin_footprint())
        self.assertFalse((pretty / 'R_WSLP1206_18m_Kelvin.kicad_mod').exists(), 'S9.1 2-pad "Kelvin" land removed')
        if s92_parts.STOCK_TP.exists():
            self.assertEqual((pretty / (s92_parts.FP_S92['TP15'] + '.kicad_mod')).read_bytes(), s92_parts.STOCK_TP.read_bytes())
        g = s92_parts.kelvin_geometry()
        self.assertEqual({n: p['role'] for n, p in g['pads'].items()}, {'1': 'force', '2': 'sense', '3': 'sense', '4': 'force'})
        self.assertGreaterEqual(g['min_copper_gap_mm'], 0.2)
        self.assertGreaterEqual(g['mask_web_mm'], 0.15)
        self.assertTrue(all(x > 0 for x in g['sense_electrode_overlap_worst_mm']), g)
        nets = self.design.nets
        self.assertEqual(nets['P12_ISP'], {('U2', '12'), ('R109', '2'), ('TP22', '1')})
        self.assertEqual(nets['P12_ISN'], {('U2', '13'), ('R109', '3'), ('TP23', '1')})
        self.assertEqual([self.design.net('R109', p) for p in '1234'], ['P12_VOUT', 'P12_ISP', 'P12_ISN', '+12V'])
        root = ET.parse(self.xml).getroot()
        fp = next(c for c in root.find('components') if c.get('ref') == 'R109').findtext('footprint')
        self.assertEqual(fp, 'USBPOWER45:' + s92_parts.FP_S92['KELVIN1206'])
        board = json.loads((DESIGN / 'docs/s8-single/board-p1.json').read_text())['routing_contract_screen']
        self.assertTrue(board['kelvin']['pass'])

    # ---- item 6 + routing contract ----------------------------------------------------------------------------------------
    def test_thermal_rating_conditional_on_contract(self):
        calcs = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['thermal_contract']
        self.assertTrue(calcs['status'].startswith('CONDITIONAL'))
        self.assertLessEqual(calcs['U2']['Tj_at_50C_limit_C'], 125)
        self.assertGreater(calcs['U2']['allowed_RthetaJA_for_125C_C_W']['at_CC_limit'], calcs['U2']['RthetaJA_model_C_W'])
        self.assertLess(calcs['R109']['P_W_at_limit'], calcs['R109']['rating_W'])
        place = json.loads((DESIGN / 'docs/s8-single/placement.json').read_text())
        rc = place['routing_contract']
        self.assertEqual(place['revision'], rc['revision'])
        self.assertEqual(set(rc['thermal']), {'U2', 'R109', 'D10', 'U4', 'U5'})
        self.assertIn('PGND_vias', rc['thermal']['U2']['requirements'])
        screen = json.loads((DESIGN / 'docs/s8-single/board-p1.json').read_text())['routing_contract_screen']
        self.assertTrue({'thermal.U2.PGND_vias', 'thermal.R109.force_copper', 'thermal.D10.copper'}
                        <= set(screen['pending_after_routing']), 'copper/via items stay PENDING on the unrouted board')

    def test_acceptance_pads_and_netclasses(self):
        import s92_contract
        import build_s8
        for ref, net in circuit_s8.S92_TP.items():
            self.assertEqual((self.by[ref]['fp'], self.by[ref]['pins']), ('TP15', {'1': net}), ref)
        for t in s92_contract.TEST_POINTS:
            self.assertEqual(self.design.net(t['ref'], '1'), t['net'], t['ref'])
        screen = json.loads((DESIGN / 'docs/s8-single/board-p1.json').read_text())['routing_contract_screen']
        self.assertTrue(screen['pass'])
        self.assertEqual({x['ref'] for x in screen['test_points']}, {t['ref'] for t in s92_contract.TEST_POINTS})
        self.assertTrue(all(x['ok'] for x in screen['pairs_2p54']) and len(screen['pairs_2p54']) == 4)
        pro = json.loads((DESIGN / 'hardware/single/usb-power-45w-single.kicad_pro').read_text())['net_settings']
        classes = {c['name']: c for c in pro['classes']}
        self.assertEqual(set(classes), {'Default', *build_s8.NETCLASSES})
        self.assertEqual({c['clearance'] for c in classes.values()}, {classes['Default']['clearance']})
        self.assertEqual({(p['netclass'], p['pattern']) for p in pro['netclass_patterns']},
                         {(n, pat) for n, (_, pats) in build_s8.NETCLASSES.items() for pat in pats})

    def test_sourcing_complete_for_jlcpcb(self):
        import csv
        src = json.loads((DESIGN / 'docs/s8-single/sourcing.json').read_text())
        s = src['summary']
        self.assertTrue(s['live_audit'])
        self.assertEqual((s['failures'], s['missing_codes'], s['S8_zero_stock_codes'], s['S8_unpriced_codes']), ([], [], [], []))
        with (DESIGN / 'docs/s8-single/bom.csv').open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(sorted(r for row in rows if not row['LCSC'] for r in row['Refs'].split(',')), ['D8', 'J2', 'J3'])
        policy = set(src['basic_only_policy']['refs'])
        nonbasic_rc = sorted(r for row in rows if row['LCSC'] and src['codes'][row['LCSC']]['classification'] != 'Basic'
                             for r in row['Refs'].split(',') if r[0] in 'RC')
        self.assertEqual(set(nonbasic_rc), policy)
        self.assertEqual(set(s['alternates']), {'D24', 'D26', 'R109'})

    # ---- routing notes (human half of the contract) -------------------------------------------------------------------
    def test_routing_notes_cover_contract(self):
        """routing-notes.md is consistent with the netlist, the contract and the review record; mutated copies (a pad row
        dropped or on the wrong net, a register row dropped, the routing-ready statement removed) must fail."""
        notes = (DESIGN / 'docs/s8-single/routing-notes.md').read_text()
        doc = (MODULE / 'docs/s8-single-board.md').read_text()
        self.assertEqual(routing_notes_problems(notes, doc), [])
        lines = notes.splitlines()
        tp26 = next(x for x in lines if x.startswith('| TP26 |'))
        cl1 = next(x for x in lines if x.startswith('| **CL-1**'))
        for why, n, d in (('TP26 row dropped', notes.replace(tp26 + '\n', ''), doc),
                          ('TP28 on the wrong net', notes.replace('| TP28 | `AGND_U2`', '| TP28 | `GND`'), doc),
                          ('CL-1 register row dropped', notes.replace(cl1 + '\n', ''), doc),
                          ('PENDING item dropped', notes.replace('`kelvin.sense_routing`', ''), doc),
                          ('statement removed', notes, doc.replace(ROUTING_READY, ''))):
            with self.subTest(why):
                self.assertTrue(routing_notes_problems(n, d), why)


if __name__ == '__main__':
    unittest.main()
