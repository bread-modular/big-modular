"""S8 single-board regressions: table derivation, final schematic (rail LEDs removed), S8.1 guard (reference,
clamp, pin map), S8.3 +5V series disconnect, native verifier (negative controls), P1.4 board and mechanics
contract, calcs. S8.4 review fixes: C1 (U23 FLT never reaches P5_OK / the latch), M1 (TIMER_GO follows MAIN_OK,
not V20_OK), M2 (load release vs OVLO, falling threshold), M3 (V3V3 loss), M4 (local loops), M5 (rating),
M6 (-12V start-up into a typical rack), M7 (U23 mask webs), M8 (Basic-only counterfactual), M9 (mechanical risks),
C2 (<6 V not guaranteed, stays exposed).

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
        self.assertEqual(r['components'], 190)
        self.assertEqual(r['digital_combinations_checked'], 512)
        g = r['overvoltage_guard_V']
        self.assertTrue(all(v > 0 for v in g['margin_min_to_peak_V'].values()), g)
        self.assertTrue(all(v >= 0 for v in g['margin_max_to_limit_V'].values()), g)
        ef = r['disconnect']
        self.assertGreater(ef['margin_min_to_stacked_peak_V'], 0.05)
        self.assertFalse(ef['OVLO_latched_internally'])
        self.assertFalse(ef['OVLO_response_max_specified'])
        self.assertGreater(r['comparator_supply']['full_temp_headroom_V'], 10)
        # S8.4 C1 / M1 / M2 records
        self.assertTrue(ef['FLT_isolated_from_latch'])
        self.assertEqual(ef['P5_FLT_N_members'], ['R108.2', 'TP21.1', 'U23.4'])
        self.assertGreater(ef['margin_min_to_ILIM_max_release_peak_V'], 0.05)
        self.assertEqual(r['startup_arming']['TIMER_GO'], 'RUN AND MAIN_OK')
        self.assertFalse(r['startup_arming']['V20_OK_in_arming_path'])
        self.assertTrue(any('NOT guaranteed' in w for w in r['warnings']), 'C2 wording must stay in the record')

    def test_c1_flt_on_p5_ok_rejected(self):
        """Regression (review C1): U23 FLT (pin 4) wired back onto P5_OK must fail the verifier."""
        bad = Path(self.tmp.name) / 'c1.xml'
        move_node(self.xml, bad, 'U23', '4', 'P5_OK')
        with self.assertRaisesRegex(AssertionError, 'C1|P5_OK|P5_FLT_N'):
            verify_native(bad)
        for ref, pin, net in [('R108', '2', 'P5_OK'), ('TP21', '1', 'P5_OK'), ('U23', '4', 'FAULT_CLK'),
                              ('U23', '4', 'BAD_FILTERED'), ('U14', '4', 'P5_FLT_N')]:
            with self.subTest(ref=ref, pin=pin, net=net):
                bad = Path(self.tmp.name) / f'c1-{ref}-{pin}-{net}.xml'
                move_node(self.xml, bad, ref, pin, net)
                with self.assertRaises(AssertionError):
                    verify_native(bad)

    def test_m1_timer_from_v20_ok_rejected(self):
        """Regression (review M1): the startup timer gated by V20_OK instead of MAIN_OK must fail the verifier."""
        bad = Path(self.tmp.name) / 'm1.xml'
        move_node(self.xml, bad, 'U13', '10', 'V20_OK')
        with self.assertRaisesRegex(AssertionError, 'M1|TIMER_GO|MAIN_OK|U13'):
            verify_native(bad)
        for ref, pin, net in [('U13', '9', 'V20_OK'), ('R69', '1', 'RUN'), ('U13', '10', 'V3V3')]:
            with self.subTest(ref=ref, pin=pin, net=net):
                bad = Path(self.tmp.name) / f'm1-{ref}-{pin}-{net}.xml'
                move_node(self.xml, bad, ref, pin, net)
                with self.assertRaises(AssertionError):
                    verify_native(bad)

    def test_native_c1_m1_nets(self):
        """C1 / M1 straight from the exported native netlist (independent of the verifier)."""
        root = ET.parse(self.xml).getroot()
        nets = {n.get('name').split('/')[-1]: {(d.get('ref'), d.get('pin')) for d in n.findall('node')}
                for n in root.find('nets')}
        self.assertEqual(nets['P5_FLT_N'], {('U23', '4'), ('R108', '2'), ('TP21', '1')})
        self.assertNotIn(('U23', '4'), nets['P5_OK'])
        self.assertEqual(nets['P5_OK'], {('U23', '3'), ('U18', '2'), ('R44', '2'), ('TP13', '1'), ('U14', '4')})
        self.assertEqual(nets['TIMER_GO'], {('U13', '8'), ('R69', '1')})
        self.assertIn(('U13', '10'), nets['MAIN_OK'])
        self.assertTrue({('U2', '2'), ('U3', '2')} <= nets['MAIN_OK'])
        self.assertNotIn(('U13', '10'), nets['V20_OK'])
        self.assertNotIn(('U13', '9'), nets['V20_OK'])

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
        self.assertEqual(parts['U23']['pins'], {'1':'RUN','2':'P5_OVLO','3':'P5_OK','4':'P5_FLT_N',
                         '5':'P5_RAW','6':'+5V','7':'P5_DVDT','8':'GND','9':'P5_ILM','10':None})
        self.assertEqual(parts['R108']['pins'], {'1': 'V3V3', '2': 'P5_FLT_N'})
        self.assertEqual(parts['TP21']['pins'], {'1': 'P5_FLT_N'})
        self.assertEqual(parts['R11']['pins']['2'],'P5_RAW')
        for r in ('U18','U20'): self.assertEqual(parts[r]['pins']['3'],'VPD')
        for r in ('C57','C65'):
            self.assertEqual(parts[r]['pins']['1'],'VPD')
            self.assertEqual(parts[r]['fields']['Voltage'],'50V')

    def test_c1_flt_off_the_latch_in_table(self):
        """S8.4 C1 at the circuit table: FLT only on R108/TP21; P5_OK = AUXOFF + U18 + pull-up/pad + U14."""
        parts = circuit_s8.circuit()
        on = lambda net: sorted((p['ref'], k) for p in parts for k, v in p['pins'].items() if v == net)
        self.assertEqual(on('P5_FLT_N'), [('R108', '2'), ('TP21', '1'), ('U23', '4')])
        self.assertEqual(on('P5_OK'), [('R44', '2'), ('TP13', '1'), ('U14', '4'), ('U18', '2'), ('U23', '3')])

    def test_m1_timer_follows_main_ok_in_table(self):
        """S8.4 M1 at the circuit table: TIMER_GO = RUN AND MAIN_OK (the U2/U3 enable); V20_OK only in MAIN_LED_OK;
        R83 re-centred so the V20_OK high corner stays below the minimum loaded 20 V PD input."""
        by = {p['ref']: p for p in circuit_s8.circuit()}
        u13 = by['U13']['pins']
        self.assertEqual((u13['9'], u13['10'], u13['8']), ('RUN', 'MAIN_OK', 'TIMER_GO'))
        self.assertEqual((u13['12'], u13['13'], u13['11']), ('MAIN_OK', 'V20_OK', 'MAIN_LED_OK'))
        self.assertEqual((by['U2']['pins']['2'], by['U3']['pins']['2']), ('MAIN_OK', 'MAIN_OK'))
        self.assertEqual(by['R69']['pins']['1'], 'TIMER_GO')
        self.assertEqual(by['R83']['value'], '200k')
        import s8_calcs as c
        w = c.startup_window(c.table()[1])
        self.assertLess(w['V20_OK_V'][2], w['min_loaded_PD_input_V'])
        self.assertGreater(w['V20_OK_S83_220k_nominal_V'], w['V20_OK_V'][1])

    def test_r11_r12_precision(self):
        by = {p['ref']: p for p in circuit_s8.circuit()}
        for r in ('R11', 'R12'):
            self.assertEqual((by[r]['fields']['Tolerance'], by[r]['fields']['TCR']), ('0.1%', '25ppm'), r)
        self.assertEqual((by['R11']['value'], by['R12']['value']), ('68k', '13k'))

    def test_u23_mask_webs(self):
        """S8.4 M7: every solder-mask web between differently numbered U23 copper pads >= 0.15 mm (was 0.10 mm)."""
        import s83_parts
        from sexp import one, nodes, parse
        pads = []
        for q in nodes(parse(s83_parts.footprint()), 'pad'):
            if q[1] and 'F.Cu' in one(q, 'layers')[1:]:
                (x, y), (w, h) = map(float, one(q, 'at')[1:3]), map(float, one(q, 'size')[1:3])
                pads.append((q[1], x - w / 2, x + w / 2, y - h / 2, y + h / 2, float(one(q, 'solder_mask_margin')[1])))
        webs = []
        for i, a in enumerate(pads):
            for b in pads[i + 1:]:
                if a[0] == b[0]:
                    continue
                dx, dy = max(0, b[1] - a[2], a[1] - b[2]), max(0, b[3] - a[4], a[3] - b[4])
                webs.append((math.hypot(dx, dy) - a[5] - b[5], a[0], b[0]))
        self.assertAlmostEqual(min(w for w, *_ in webs), s83_parts.MASK_WEB_MIN, places=6)
        in_out = min(w for w, a, b in webs if {a, b} == {'5', '6'})
        self.assertGreaterEqual(in_out + 1e-9, 0.15)
        self.assertTrue(all(m == s83_parts.MASK_MARGIN for *_, m in pads))
        placed = [q for f in nodes(parse(BOARD.read_text()), 'footprint')
                  if any(pp[1] == 'Reference' and pp[2] == 'U23' for pp in nodes(f, 'property'))
                  for q in nodes(f, 'pad') if q[1]]
        self.assertEqual({float(one(q, 'solder_mask_margin')[1]) for q in placed}, {s83_parts.MASK_MARGIN})

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
        self.assertEqual(r['parts_on_board'], 190)
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
        u23 = [x for (ic, _), x in rows.items() if ic == 'U23']
        self.assertEqual(len(u23), 4)
        self.assertTrue(all(x['distance_mm'] <= 6.0 for x in u23), u23)

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
    """S8.4: docs/s8-single/review-s84.json (tools/review_s8.py) hashes match the files in the tree."""

    def test_review_hashes_match(self):
        import hashlib
        rec_path = MODULE / 'docs/s8-single/review-s84.json'
        if DESIGN.resolve() != MODULE.resolve() or not rec_path.exists():
            self.skipTest('review record applies to the module tree once generated (tools/review_s8.py)')
        rec = json.loads(rec_path.read_text())
        self.assertEqual(rec['revision'], 'S8.4 / P1.4')
        for group in ('sources_sha256', 'artifacts_sha256', 'original_S7_R3_hardware_unchanged_sha256'):
            for rel, digest in rec[group].items():
                self.assertEqual(hashlib.sha256((MODULE / rel).read_bytes()).hexdigest(), digest, rel)
        self.assertFalse((MODULE / 'docs/s8-single/review-s83.json').exists(), 'S8.3 record replaced (git history)')


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

    def test_m2_load_release_cannot_reach_ovlo(self):
        """S8.4 M2: every release from within U23's current limit stays below the OVLO and U20 +5V minima; the OVLO
        falling threshold is computed for the 0.1 % R11/R12 setpoint."""
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        rel = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['rail_release']
        ov = c.ov_guard(val, rel)
        st = c.disconnect_settings(val)
        r = c.ovlo_release(val, eff, st, ov)
        self.assertTrue(r['imposed_model_release_below_trips'])
        self.assertGreater(r['release_cases']['U23_ILIM_max']['margin_to_OVLO_min_V'], 0.05)
        self.assertGreater(r['max_release_current_clearing_OVLO_min_A'], st['current_min_nom_max_A'][2])
        self.assertEqual([round(v, 3) for v in r['setpoint_V']], [4.856, 4.985, 5.114])
        self.assertLess(r['OVLO_falling_V'][2], r['OVLO_rising_V'][0])
        self.assertGreater(r['reconnect_margin_nominal_V'], 0.15)
        self.assertGreater(r['reconnect_margin_worst_V'], r['S83_reconnect_margin_worst_V'])
        # Still OPEN (documented): at stacked corners the setpoint max sits above the OVLO release minimum. If this
        # ever turns positive, update docs/s8-single-board.md and the review open gates.
        self.assertTrue(r['reconnect_corner_open'])
        self.assertAlmostEqual(r['reconnect_margin_worst_V'], -0.035, places=3)

    def test_m5_published_rating(self):
        """S8.4 M5: published +5V 2.0 A keeps >= 0.6 A to U23's minimum ILIM (ITIMER open) and stays cool."""
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        r = c.rating(val, eff, c.disconnect_settings(val))
        self.assertEqual(r['published_A'], {'+12V': 2.5, '+5V': 2.0, '-12V': 0.9})
        self.assertGreaterEqual(r['headroom_to_capability_A']['+5V'], 0.6)
        self.assertTrue(all(f <= 0.76 for f in r['fraction_of_capability'].values()), r['fraction_of_capability'])
        self.assertEqual(r['vin_floor_V'], c.converter_vin(c.VPD_RATED_MIN))
        # below the rated range (source sagging to the U5 turn-off minimum) the rating is reported, not margined
        self.assertTrue(all(f < 0.85 for f in r['below_rated_range']['fraction_of_capability'].values()))
        self.assertLess(r['plus5_thermal']['dT_C_no_vias_74C5W'], 20)
        self.assertLess(r['simultaneous']['input_A_at_20V_45W_worst_mix'], r['simultaneous']['U5_limit_min_A'])
        self.assertLessEqual(r['simultaneous']['delivered_total_limit_W'], 45.0)

    def test_u5_window_arithmetic(self):
        """U5 UVLO thresholds referred to VPD: TI 1.176/1.2/1.224 V rising, 1.09/1.122/1.15 V falling, R2 100k / R3 7.5k
        at 1 % + 1 % TCR, and the 150 nA pin leakage through R2 (I x R2 = ~15 mV at VPD, not I x R2||R3)."""
        import s8_calcs as c
        on, off = c.u5_window(c.table()[1])
        lo, hi, leak = .99 * .99, 1.01 * 1.01, 150e-9 * 100e3 * 1.01 * 1.01
        self.assertAlmostEqual(on[0], 1.176 * (1 + 100 * lo / (7.5 * hi)) - leak, places=9)
        self.assertAlmostEqual(on[2], 1.224 * (1 + 100 * hi / (7.5 * lo)) + leak, places=9)
        self.assertAlmostEqual(off[0], 1.09 * (1 + 100 * lo / (7.5 * hi)) - leak, places=9)
        self.assertEqual([round(v, 2) for v in on], [16.23, 17.2, 18.23])
        self.assertEqual([round(v, 2) for v in off], [15.04, 16.08, 17.12])
        self.assertAlmostEqual(c.INPUT_DROP_V, 0.75 + 0.053 * 4.698, places=9)      # U5 high-corner limit
        self.assertEqual(c.INPUT_PATH['I_A'], c.input_budget()['U5_limit_screen_A'][2])

    def test_m3_v3v3_loss_bounded(self):
        import s8_calcs as c
        v = c.v3v3_loss(c.table()[1])
        self.assertTrue(all(x['node_current_bound_uA'] < 150 for x in v['minus12_held'].values()))
        self.assertLess(max(v['replug_REF_OV_settle_ms']), v['replug_RESET_release_min_ms'])
        self.assertIn('NOT a guaranteed', v['verdict'])

    def test_m8_basic_only_counterfactual_fails(self):
        import s8_calcs as c
        parts, val = c.table(); _, eff = c.banks(parts)
        rel = json.loads((DESIGN / 'docs/s8-single/calcs.json').read_text())['rail_release']
        cf = c.basic_only_counterfactual(val, eff, rel)
        self.assertTrue(cf['failing'], 'with 1 % parts some precision screen must fail (else revisit the policy)')
        self.assertEqual(c.ov_guard(val, rel)['+5V']['guard_V'], [5.677, 5.828, 5.976], 'globals restored')

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
        # S8.4 C2: the 3 us case and the 30 V / 1 ohm stress case stay above 6 V for most of the window.
        for k in ('L3.3uH_delay3us', 'VIN30_src1ohm_L3.3uH_3us'):
            self.assertGreater(cases[k]['header_peak_V'], 6.0, k)
            self.assertGreater(cases[k]['header_time_above_6V_us'], 150, k)
        self.assertIn('NOT GUARANTEED', ef['qualification'])

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
