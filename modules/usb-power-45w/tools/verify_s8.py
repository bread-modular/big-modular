"""S8 single-board native hierarchy/circuit verifier. Read-only; run native ERC separately.

  python3 -B tools/verify_s8.py --netlist <native kicadxml of hardware/single/usb-power-45w-single.kicad_sch>

Checks exact components, physical pad sets, pin memberships, NCs and fields against
tools/circuit_s8.py; that every S7 eFuse / negative-switch part is gone and nothing else; the
ceramic banks and VIN damper topology; manufacturer pin roles (TPS3808 via verify_design's TI
table, LM2901 comparator pairing against the TI pin table kept here); bounded threshold arithmetic; and a settled
digital model of the latch/LED logic including the overvoltage preset. S8 final: D8 MAIN is the only LED
(rail LEDs removed). S8.1 (review fixes): the guard's own TLV431B reference REF_OV (pin roles against TI's DBZ
table kept here), LM2901B on U18/U20, the -12V channel compared with GND, the D22 clamp on MON_OVN, 0.1 %
dividers and the guard bands against the converter setpoints and the downstream limits. S8.2: the +5V crowbar
(Q11 TS1220 SCR, U22 TLVH432B trigger powered by +5V only, Q12 gate driver, Q13 latch link onto OV_N): pin roles
against the manufacturer tables kept here, net memberships, trip band over corners, gate drive and the latch-link
ordering. Not SPICE or bench proof.
"""
import argparse
import itertools
import json
import math
from pathlib import Path

import circuit45
import circuit_s8
from build_schematic import FP
from sexp import parse, nodes, one
from verify_design import check_tps3808, load_xml

MODULE = Path(__file__).resolve().parents[1]
FP_S8 = FP
# TI LM2901 SOIC-14 (SLCS006Z Table 5-1): output pin -> (inverting, non-inverting) input pins of the same
# comparator, VCC 3, GND 12. Kept apart from the symbol and the circuit table (channel names vary by vendor).
LM2901_SO14 = {'outputs': {'2': ('4', '5'), '1': ('6', '7'), '14': ('8', '9'), '13': ('10', '11')}, 'VCC': '3', 'GND': '12'}
# TI TLV431 DBZ (SOT-23-3), SLVS139Z Table 4-1: pin -> function; symbol pin names K / REF / A.
TLV431_DBZ_TI = {'1': 'REF', '2': 'CATHODE', '3': 'ANODE'}
TLV431_SYMBOL_NAME = {'REF': 'REF', 'CATHODE': 'K', 'ANODE': 'A'}
# Guard screen inputs (S8.1). TLV431BI: 1.224-1.259 V over -40..85 C at IK 10 mA, |zKA| <= 0.4 ohm -> up to 3.6 mV
# lower at ~1 mA (SLVS139Z 5.7). LM2901B: VIO 5.5 mV and IB 50 nA (out of the pin) over -40..125 C (SLCS006Z 6.8).
# Divider resistors: 0.1 % + 25 ppm/C x 100 C. Converter load release, capacitor-study model, N = 16 cycles, low-C
# corner (docs/s8-single/calcs.json rail_release): +12V 1.033 V, +5V 0.358 V, -12V 0.484 V above the setpoint.
VREF_OV = (1.224 - 0.0036, 1.24, 1.259)
# S8.2 crowbar. Manufacturer pin tables (kept apart from the symbols): ST TS1220 DPAK (DocID027645 Fig. 1: pin 1 K,
# pin 2 / tab A, pin 3 G), TI TLVH432 DBZ (SLVS555N Pin Functions: CATHODE 1, REF 2, ANODE 3), AOS AO3401A SOT-23
# (G 1, S 2, D 3), MMBT3904 SOT-23 (B 1, E 2, C 3).
PINS_MFR = {'Q_SCR_KAG': {'1': 'K', '2': 'A', '3': 'G'}, 'TLVH432_DBZ': {'1': 'K', '2': 'REF', '3': 'A'},
            'AO3401A': {'1': 'G', '2': 'S', '3': 'D'}, 'MMBT3904': {'1': 'B', '2': 'E', '3': 'C'}}
# TLVH432BI VREF 1.224-1.259 V (-40..85 C, IK 10 mA), up to 4 mV lower at the ~1.3 mA trip current (|zKA| <= 0.4 ohm);
# Iref <= 0.5 uA + 0.4 uA deviation (SLVS555N 5.7). TS1220 (DocID027645): IGT <= 200 uA, VGT <= 0.8 V at 25 C, IGT
# x 1.9 at -40 C (Fig. 6); VGT assumed +2 mV/C below 25 C (0.93 V at -40 C) and >= 0.30 V at 125 C (screen, not
# specified). Q13 must sink 0.25 mA (R97 10k, OV_N below 0.9 V) with hFE >= 50: VBE <= 0.75 V (25 C) / 0.88 V (-40 C).
VREF_CB = (1.224 - 0.004, 1.24, 1.259)
IREF_CB_MAX = 0.9e-6
IGT_MAX = {'-40C': 380e-6, '25C': 200e-6}
VGT_MAX = {'-40C': 0.93, '25C': 0.8}
VGT_MIN = {'-40C': 0.60, '25C': 0.45, '125C': 0.30}
Q13_ON_MAX_V = {'-40C': 0.93, '25C': 0.80, '125C': 0.60}   # VBE max + 5 uA x R106 (10k)
VIO_B, IB_B = 0.0055, 50e-9
R01_LO, R01_HI = 0.999 * 0.9975, 1.001 * 1.0025
RELEASE_N16_V = {'+12V': 1.033, '+5V': 0.358, '-12V': 0.484}
DOWNSTREAM_MAX_V = {'+12V': 16.0, '+5V': 6.0, '-12V': 16.0}    # 16 V module caps / 6.0 V 5 V-logic absolute maxima

# Independently specified function pin -> net expectations of the critical parts (S8).
CRIT = {
    'U5': {1: 'EF_IN', 2: 'EF_IN', 3: 'EF_IN', 6: 'EF_IN', 7: 'EF_UV', 8: 'EF_OV', 9: 'GND', 10: 'EF_DVDT', 11: 'EF_ILM',
           12: 'GND', 13: 'RUN', 14: 'EF_IMON', 15: 'MAIN_OK', 16: 'MAIN_OK', 18: 'VIN', 19: 'VIN', 20: 'VIN', 21: 'GND'},
    'U2': {2: 'MAIN_OK', 3: 'VIN', 4: 'GND'}, 'U3': {2: 'MAIN_OK', 3: 'VIN', 4: 'GND'},
    'U4': {3: 'VIN', 1: '-12V', 9: '-12V'},
    'U9': {1: 'V3V3', 4: 'GND', 5: 'VPD', 8: 'VPD', 9: 'GND'},
    'U10': {1: 'RESET_N', 2: 'GND', 3: 'RESET_BTN_N', 5: 'POR_SENSE', 6: 'V3V3'},
    'U11': {1: 'START_READY', 2: 'GND', 3: 'RESET_N', 4: 'START_CT', 5: 'START_SENSE', 6: 'V3V3'},
    'U12': {1: 'RESET_N', 2: 'V3V3', 3: 'START_READY', 4: 'V3V3', 5: 'ARMED', 7: 'GND', 8: 'NOT_FAULT', 9: 'FAULT_LATCH',
            10: 'OV_N', 11: 'FAULT_CLK', 12: 'V3V3', 13: 'RESET_N', 14: 'V3V3'},
    'U14': {1: 'MAIN_LED_OK', 2: 'P12_OK', 4: 'P5_OK', 5: 'N12_OK', 6: 'ANY_BAD', 7: 'GND', 9: 'GND', 10: 'GND',
            12: 'GND', 13: 'GND', 14: 'V3V3'},
    'U18': {1: 'P12_OK', 2: 'P5_OK', 3: 'V3V3', 4: 'REF_GOOD', 5: 'MON_P5', 6: 'REF_GOOD', 7: 'MON_P12', 8: 'MON_N12',
            9: 'REF_GOOD', 10: 'REF_GOOD', 11: 'MON_20', 12: 'GND', 13: 'V20_OK', 14: 'N12_OK'},
    'U20': {2: 'OV_N', 4: 'MON_OV12', 5: 'REF_OV', 1: 'OV_N', 6: 'MON_OV5', 7: 'REF_OV', 14: 'OV_N', 8: 'GND',
            9: 'MON_OVN', 10: 'REF_OV', 11: 'GND', 3: 'V3V3', 12: 'GND'},
    'U21': {1: 'REF_OV', 2: 'REF_OV', 3: 'GND'}, 'R100': {1: 'V3V3', 2: 'REF_OV'}, 'C67': {1: 'REF_OV', 2: 'GND'},
    'D22': {1: 'GND', 2: 'MON_OVN', 3: 'MON_OVN'}, 'TP17': {1: 'REF_OV'},
    'R92': {1: 'VIN'}, 'R93': {1: '+12V', 2: 'MON_OV12'}, 'R94': {1: 'MON_OV12', 2: 'GND'},
    'R95': {1: '+5V', 2: 'MON_OV5'}, 'R96': {1: 'MON_OV5', 2: 'GND'},
    'R98': {1: 'REF_OV', 2: 'MON_OVN'}, 'R99': {1: 'MON_OVN', 2: '-12V'},
    'R35': {1: 'V3V3', 2: 'P12_OK'}, 'R44': {1: 'V3V3', 2: 'P5_OK'}, 'R62': {1: 'V3V3', 2: 'N12_OK'},
    'R97': {1: 'V3V3', 2: 'OV_N'}, 'D21': {1: '+5V', 2: 'GND'},
    'Q11': {1: 'GND', 2: '+5V', 3: 'CROW_GATE'}, 'U22': {1: 'CROW_TRIP_N', 2: 'CROW_SENSE', 3: 'GND'},
    'Q12': {1: 'CROW_TRIP_N', 2: '+5V', 3: 'CROW_DRV'}, 'Q13': {2: 'GND', 3: 'OV_N'},
    'R101': {1: '+5V', 2: 'CROW_SENSE'}, 'R102': {1: 'CROW_SENSE', 2: 'GND'}, 'C68': {1: 'CROW_SENSE', 2: 'GND'},
    'R103': {1: '+5V', 2: 'CROW_TRIP_N'}, 'R104': {1: 'CROW_DRV', 2: 'CROW_GATE'}, 'R105': {1: 'CROW_GATE', 2: 'GND'},
    'R106': {1: 'CROW_DRV'},
    'SW1': {1: 'RESET_BTN_N', 3: 'RESET_BTN_N', 2: 'GND'}, 'D10': {1: 'EF_IN', 2: 'VPD'},
    'Q2': {1: 'PD_SENSE', 2: 'VPD_U1', 3: 'PD_BASE'}, 'Q1': {2: '+12V'}, 'Q10': {1: 'RUN', 2: 'GND', 3: 'LED_RETURN'},
    'D2': {1: '+12V', 2: 'GND'}, 'D3': {1: '+5V', 2: 'GND'}, 'D4': {1: 'GND', 2: '-12V'},
}
HEADER = {**{n: 'GND' for n in range(3, 9)}, 1: '-12V', 2: '-12V', 9: '+12V', 10: '+12V', 11: '+5V', 12: '+5V'}
FORBIDDEN_MPN = {'LM5067MM-2/NOPB', 'FQD13N06LTM', 'LTV-354T', 'MVK50V47M6.3*8 6.3TP', 'MVK 35V100 M 6.3*8'}


def verify(netlist, hardware=MODULE / 'hardware', root=None):
    xml_root, comps, nets, pins = load_xml(netlist)
    parts = {p['ref']: p for p in circuit_s8.circuit() if not p['ref'].startswith('#')}
    assert set(parts) == set(comps), ('Native/table component mismatch', sorted(set(parts) ^ set(comps)))
    expected = {}; netids = {}
    for ref, p in parts.items():
        assert comps[ref].findtext('value') == p['value'], (ref, 'value')
        assert comps[ref].findtext('footprint') == 'USBPOWER45:' + FP_S8[p['fp']], (ref, 'footprint')
        for field, val in p['fields'].items():
            assert comps[ref].findtext(f'fields/field[@name="{field}"]') == val, (ref, field)
        f = parse((hardware / 'USBPOWER45.pretty' / (FP_S8[p['fp']] + '.kicad_mod')).read_text())
        assert {str(x[1]) for x in nodes(f, 'pad') if x[1]} == set(p['pins']), (ref, 'pad set')
        for num, net in p['pins'].items():
            key = (ref, num)
            if net is None:
                assert 'unconnected-' in pins[key] and nets[pins[key]] == {key}, (key, 'NC')
            else:
                expected.setdefault(net, set()).add(key)
    for net, ps in expected.items():
        match = [n for n, actual in nets.items() if actual == ps]
        assert len(match) == 1, (net, 'exact pin membership')
        if not net.startswith('_'):
            assert match[0].split('/')[-1] == net, (net, 'name')
        netids[net] = match[0]

    def n(ref, pin):
        return pins[(ref, str(pin))]

    def isnet(ref, pin, net):
        assert n(ref, pin) == netids[net], (ref, pin, net)

    def value(ref):
        s = comps[ref].findtext('value')
        return float(s[:-1]) * {'k': 1e3, 'u': 1e-6, 'n': 1e-9}[s[-1]] if s[-1] in 'kun' else float(s)

    # ---- What S8 removes and keeps
    s7 = {p['ref'] for p in circuit45.circuit() if not p['ref'].startswith('#')}
    removed = {r for r in circuit_s8.S8_REMOVED if not r.startswith('#')}
    added = set(comps) - s7
    assert removed <= s7 and not removed & set(comps), 'S8_REMOVED refs must be S7 refs and absent'
    assert s7 - set(comps) == removed, ('Only the listed S7 refs may disappear', sorted(s7 - set(comps) - removed))
    assert added == {'J3', 'C59', 'C60', 'C61', 'C62', 'R92', 'U20', 'R93', 'R94', 'R95', 'R96', 'R97', 'R98', 'R99',
                     'C63', 'C64', 'C65', 'C66', 'D21', 'U21', 'R100', 'C67', 'D22', 'TP17',
                     *circuit_s8.CROWBAR}, sorted(added)
    tps1663 = sorted(r for r in comps if comps[r].findtext('fields/field[@name="MPN"]') == 'TPS16630PWPR')
    assert tps1663 == ['U5'], ('U5 must be the only TPS16630', tps1663)
    assert not any(comps[r].findtext('fields/field[@name="MPN"]') in FORBIDDEN_MPN for r in comps)
    assert not any('CP_Elec' in comps[r].findtext('footprint') for r in comps), 'No electrolytic footprints'
    assert not {'P12_RAW', 'P5_RAW', 'N12_RAW', 'N12_STATUS', 'NOT_RUN'} & {k.split('/')[-1] for k in nets}

    for ref, m in CRIT.items():
        for pin, net in m.items():
            isnet(ref, pin, net)
    assert 'unconnected-' in n('U14', 8), 'U14 gate 2 output must stay open'
    check_tps3808(xml_root, comps, pins)
    libparts = {p.get('part'): {x.get('num'): x.get('name') for x in p.findall('pins/pin')}
                for p in xml_root.findall('libparts/libpart')}
    lm = libparts['LM2901_QUAD']
    assert lm[LM2901_SO14['VCC']] == 'VCC' and lm[LM2901_SO14['GND']] == 'GND'
    for out, (inv, non) in LM2901_SO14['outputs'].items():    # same comparator: kOUT, k-, k+
        k = lm[out].removesuffix('OUT')
        assert (lm[inv], lm[non]) == (k + '-', k + '+'), ('LM2901 symbol pairing differs from TI table', out, inv, non)
    for u in ('U18', 'U20'):
        assert comps[u].findtext('fields/field[@name="MPN"]') == 'LM2901BIDR', (u, 'S8.1: LM2901B')
    assert 'unconnected-' in n('U20', 13), 'spare comparator output stays open'
    tlv = libparts['TLV431_DBZ']
    assert {k: tlv[k] for k in TLV431_DBZ_TI} == {k: TLV431_SYMBOL_NAME[v] for k, v in TLV431_DBZ_TI.items()}, \
        ('TLV431 symbol pins differ from TI SLVS139Z Table 4-1 (DBZ)', tlv)
    assert comps['U21'].findtext('fields/field[@name="MPN"]') == 'TLV431BIDBZR'
    assert n('U21', 1) == n('U21', 2) == netids['REF_OV'] and n('U21', 3) == netids['GND'], 'U21: REF tied to CATHODE'
    assert nets[netids['REF_OV']] == {('U21', '1'), ('U21', '2'), ('R100', '2'), ('C67', '1'), ('TP17', '1'),
                                      ('U20', '5'), ('U20', '7'), ('U20', '10'), ('R98', '1')}, 'REF_OV members'
    assert netids['V3V3'] not in {n('R98', 1), n('R99', 1)}, '-12V guard divider must not depend on V3V3'
    assert nets[netids['MON_OVN']] == {('R98', '2'), ('R99', '1'), ('C66', '1'), ('D22', '2'), ('D22', '3'),
                                       ('U20', '9')}, 'MON_OVN members (D22 clamp at the comparator node)'
    for r in ('R93', 'R94', 'R95', 'R96', 'R98', 'R99', 'R101', 'R102'):
        assert comps[r].findtext('fields/field[@name="Tolerance"]') == '0.1%', (r, '0.1 % divider')
    # ---- S8.2 crowbar: pin roles, memberships, self-powered trigger, latch link
    for sym, table in PINS_MFR.items():
        assert {k: libparts[sym][k] for k in table} == table, ('crowbar symbol pins differ from the maker table', sym)
    for ref, mpn in (('Q11', 'TS1220-600B-TR'), ('U22', 'TLVH432BIDBZR'), ('Q12', 'AO3401A'), ('Q13', 'MMBT3904')):
        assert comps[ref].findtext('fields/field[@name="MPN"]') == mpn, (ref, mpn)
    assert comps['Q11'].findtext('footprint') == 'USBPOWER45:TO-252-2', 'DPAK: pad 2 = tab = anode'
    assert nets[netids['CROW_SENSE']] == {('R101', '2'), ('R102', '1'), ('C68', '1'), ('U22', '2')}, 'CROW_SENSE'
    assert nets[netids['CROW_TRIP_N']] == {('U22', '1'), ('R103', '2'), ('Q12', '1')}, 'CROW_TRIP_N'
    assert nets[netids['CROW_DRV']] == {('Q12', '3'), ('R104', '1'), ('R106', '1')}, 'CROW_DRV'
    assert nets[netids['CROW_GATE']] == {('R104', '2'), ('R105', '1'), ('Q11', '3')}, 'CROW_GATE'
    assert nets[n('R106', 2)] == {('R106', '2'), ('Q13', '1')}, 'Q13 base only through R106'
    cb_nets = {n(r, k) for r in circuit_s8.CROWBAR for k in parts[r]['pins']}
    assert not cb_nets & {netids['V3V3'], netids['REF_OV'], netids['REF_GOOD'], netids['MON_OV5']}, \
        'crowbar trigger must be powered and referenced by +5V alone (no V3V3 / REF_OV / guard divider)'
    assert cb_nets & {netids['OV_N']} == {netids['OV_N']} and ('Q13', '3') in nets[netids['OV_N']], 'latch link on OV_N'
    assert value('R101') == value('R95') and value('R102') == value('R96'), 'crowbar ratio = U20 +5V guard ratio'
    for k, v in {'5': '1Q', '8': '2Q_N', '9': '2Q', '10': '2PRE_N', '13': '2CLR_N'}.items():
        assert libparts['HC74_DUAL'][k] == v, ('HC74 pin', k, libparts['HC74_DUAL'][k])
    for j in ('J2', 'J3'):
        for pin, net in HEADER.items():
            isnet(j, pin, net)
        for pin in range(13, 17):
            assert 'unconnected-' in n(j, pin), (j, pin, 'CV/GATE open')
    leds = sorted(r for r in comps if ':LED' in comps[r].findtext('footprint'))
    assert leds == ['D8'], ('S8 final: D8 MAIN is the only LED (rail LEDs removed)', leds)
    assert not set(circuit_s8.LED_REMOVED) & set(comps), 'rail LED parts must be gone'
    for d, r, q, gate in [('D8', 'R22', 'Q6', 'MAIN_LED_OK')]:
        isnet(r, 1, 'V3V3'); assert n(r, 2) == n(d, 2) and n(d, 1) == n(q, 3)
        isnet(q, 1, gate); isnet(q, 2, 'LED_RETURN')
    assert nets[netids['LED_RETURN']] == {('Q6', '2'), ('Q10', '3')}, 'LED return: Q6 source + Q10 drain only'
    for net, tp in (('P12_OK', 'TP12'), ('P5_OK', 'TP13'), ('N12_OK', 'TP14')):   # status: logic + pull-up + pad
        assert {r for r, _ in nets[netids[net]]} == {'U18', 'U14', {'P12_OK': 'R35', 'P5_OK': 'R44', 'N12_OK': 'R62'}[net], tp}, net
    assert n('U9', 8) != n('U5', 18), 'Latch supply must survive main switch off'

    # ---- Ceramic banks and the VIN damper (no electrolytics)
    def bank(net, val):
        return sorted(r for r, p in parts.items() if p['value'] == val and p['fp'] == 'C1206'
                      and netids[net] in {n(r, 1), n(r, 2)} and netids['GND'] in {n(r, 1), n(r, 2)})
    banks = {'+12V': bank('+12V', '22u'), '+5V': bank('+5V', '22u'), '-12V': bank('-12V', '22u'),
             'VIN': bank('VIN', '10u')}
    assert len(banks['+12V']) == 6 and len(banks['+5V']) == 6 and len(banks['-12V']) == 7, banks
    damp = n('R92', 2)
    assert {(r, '1') for r in ('C5', 'C62')} | {('R92', '2')} == nets[damp], 'damper node = R92.2 + C5.1 + C62.1'
    for r in ('C5', 'C62'):
        isnet(r, 2, 'GND'); assert math.isclose(value(r), 10e-6)
    assert math.isclose(value('R92'), 1.0)
    assert sorted(banks['VIN']) == ['C15', 'C16', 'C24', 'C6', 'C7'], banks['VIN']
    for r in ('C9', 'C18', 'C49'):
        assert math.isclose(value(r), 100e-9), r

    # ---- Bounded arithmetic, brute force over every corner. U18 monitors (unchanged): V3V3 +-2 % (TPS7A16 SBVS171F),
    # 1 % resistors + 1 % TCR drift (as the S6 screens). S8.1 guard: REF_OV (TLV431BI), LM2901B offset and bias
    # current, 0.1 % dividers (constants above); the converter setpoints keep the 1 % + 1 % TCR corners.
    lo, hi = .99 * .99, 1.01 * 1.01

    def ref(v3, a, b):
        return v3 * value('R74') * b / (value('R73') * a + value('R74') * b)

    def guard(f):
        vals = [f(v, a, b, e, ib) for v in (VREF_OV[0], VREF_OV[2]) for a in (R01_LO, R01_HI) for b in (R01_LO, R01_HI)
                for e in (-VIO_B, VIO_B) for ib in (0.0, IB_B)]
        return [min(vals), f(VREF_OV[1], 1, 1, 0, 0), max(vals)]

    def positive(top, bot):          # trips when the divider tap (+ bias current x Thevenin R) exceeds REF_OV + offset
        def f(v, a, b, e, ib):
            rt, rb = value(top) * a, value(bot) * b
            return (v + e - ib * rt * rb / (rt + rb)) * (rt + rb) / rb
        return guard(f)

    def negative(v, a, b, e, ib):    # MON_OVN = (REF_OV x R99 + V x R98) / (R98 + R99) + ib x Rth falls to 0 V + offset
        r98, r99 = value('R98') * a, value('R99') * b
        return (v * r99 + (ib * r98 * r99 / (r98 + r99) - e) * (r98 + r99)) / r98
    ov12, ov5, ovneg = positive('R93', 'R94'), positive('R95', 'R96'), guard(negative)

    def setpoint(top, bot, vfb):
        return vfb * (1 + value(top) * hi / (value(bot) * lo))
    p12_max, p5_max = setpoint('R8', 'R9', .816), setpoint('R11', 'R12', .816)    # SLUSEA4D VFB max
    n12_max = setpoint('R14', 'R15', 1.015)                                        # SNVSC40E FB max
    ovp12_max, ovp5_max = 1.18 * p12_max, 1.18 * p5_max                           # OVP 118 % max
    assert 14.7 < ov12[1] < 15.0 and 5.75 < ov5[1] < 5.9 and 13.5 < ovneg[1] < 13.8, (ov12, ov5, ovneg)
    # Crowbar trip: VREF_CB x (1 + R101/R102) + Iref x R101, every corner (S8.2)
    cb = [(v * (1 + value('R101') * a / (value('R102') * b)) + i * value('R101') * a)
          for v in (VREF_CB[0], VREF_CB[2]) for a in (R01_LO, R01_HI) for b in (R01_LO, R01_HI) for i in (0, IREF_CB_MAX)]
    crow = [min(cb), VREF_CB[1] * (1 + value('R101') / value('R102')), max(cb)]
    peak = {'+12V': p12_max + RELEASE_N16_V['+12V'], '+5V': p5_max + RELEASE_N16_V['+5V'],
            '-12V': n12_max + RELEASE_N16_V['-12V']}
    bands = {'+12V': ov12, '+5V': ov5, '-12V': ovneg}
    for rail, band in bands.items():
        assert band[0] > peak[rail], (rail, 'guard minimum must clear the stacked setpoint + N=16 release', band, peak[rail])
        assert band[2] <= DOWNSTREAM_MAX_V[rail], (rail, 'guard maximum above the downstream limit', band)
    assert crow[0] > peak['+5V'] and crow[2] <= DOWNSTREAM_MAX_V['+5V'], ('crowbar band', crow, peak['+5V'])
    # Gate drive at the lowest trip with cold IGT/VGT; latch-link ordering: Q13 pulls OV_N before the SCR can fire
    r104, r105 = value('R104'), value('R105')
    drive = {t: (crow[0] - VGT_MAX[t]) / (r104 * 1.01) - VGT_MAX[t] / (r105 * .99) for t in VGT_MAX}
    assert all(drive[t] >= 2.5 * IGT_MAX[t] for t in drive), ('SCR gate overdrive below 2.5 x IGT max', drive)
    fire_min = {t: v * (1 + r104 * .99 / (r105 * 1.01)) for t, v in VGT_MIN.items()}
    assert all(fire_min[t] - Q13_ON_MAX_V[t] > 0.3 for t in fire_min), ('latch link must lead the SCR', fire_min)
    # REF_OV bias: R100 must keep U21 above IK(min) 0.1 mA with the -12V divider drawing (1.26 + 20 V) / (R98 + R99)
    ik_min = ((3.3 * .98 - VREF_OV[2]) / (value('R100') * 1.01)
              - (VREF_OV[2] + 20.0) / ((value('R98') + value('R99')) * R01_LO) - 4 * IB_B)
    assert ik_min > 0.5e-3, ('U21 cathode current too low', ik_min)
    assert value('C67') >= 4.7e-6, 'C67 must stay right of the TLV431 instability region (SLVS139Z Fig. 5-18)'
    r0 = ref(3.3, 1, 1)
    mon = {'P12_V': r0 * (1 + value('R75') / value('R76')),
           'P5_V': r0 * (1 + (value('R77') + value('R78')) / value('R79')),
           'N12_magnitude_V': 3.3 * value('R82') / (value('R80') + value('R81')) - r0 * (1 + value('R82') / (value('R80') + value('R81'))),
           'input_V': r0 * (1 + value('R83') / value('R84'))}
    por_max = .411 * (1 + (value('R65') + value('R91')) * hi / (value('R66') * lo))
    assert por_max < 3.3 * .98, 'POR threshold could prevent a valid LDO starting'
    t_start = value('C49') * 1e9 / 175 + .0005                                      # TPS3808 SBVS050N eq. 1
    assert .5 < t_start < .65 and t_start * .6 * .9 > .2

    # ---- Digital model from native gate pin nets (settled; not an analog timing simulation)
    gates = [('U13', 1, 2, 3), ('U13', 4, 5, 6), ('U13', 9, 10, 8), ('U13', 12, 13, 11)]
    assert n('R72', 1) == n('U14', 6) and n('R72', 2) == n('C51', 1) == n('U15', 2)

    def comb(inputs, qa, qb):
        s = {netids[k]: v for k, v in inputs.items()}; s[netids['V3V3']] = True; s[netids['GND']] = False
        clr, pre = s[n('U12', 13)], s[n('U12', 10)]
        q = True if not pre else (False if not clr else qb)           # HC74: /PRE and /CLR asynchronous
        nq = True if not clr else (False if not pre else not qb)        # both low: Q = /Q = H
        s[n('U12', 5)] = qa and s[n('U12', 1)]; s[n('U12', 9)] = q; s[n('U12', 8)] = nq
        for _ in range(8):
            for u, a, b, y in gates:
                s[n(u, y)] = bool(s.get(n(u, a), False) and s.get(n(u, b), False))
            s[n('U14', 6)] = not all(s.get(n('U14', p), False) for p in [1, 2, 4, 5])
            s[n('U15', 4)] = s[n('R72', 1)]
        return s
    cases = 0
    for reset, ovn, arm, fault, mainok, p12, p5, n12, v20 in itertools.product([False, True], repeat=9):
        i = {'RESET_N': reset, 'OV_N': ovn, 'MAIN_OK': mainok, 'P12_OK': p12, 'P5_OK': p5, 'N12_OK': n12,
             'V20_OK': v20, 'START_READY': False}
        s = comb(i, arm, fault)
        run = reset and ovn and not fault
        assert s[netids['RUN']] == run, (i, arm, fault)
        assert s[netids['FAULT_CLK']] == (arm and reset and not (mainok and v20 and p12 and p5 and n12))
        for qg, want in [('Q6', mainok and v20)]:
            assert (run and s[n(qg, 1)]) == (run and want)
        if not ovn:
            assert not s[netids['RUN']], 'overvoltage must stop RUN in every state, also before ARMED'
        cases += 1
    seq = []
    base = {k: True for k in ['RESET_N', 'OV_N', 'MAIN_OK', 'P12_OK', 'P5_OK', 'N12_OK', 'V20_OK', 'START_READY']}
    for missing in ['MAIN_OK', 'P12_OK', 'P5_OK', 'N12_OK', 'V20_OK']:
        inp = dict(base); inp[missing] = False
        s = comb(inp, False, False); assert s[netids['RUN']] and not s[netids['FAULT_CLK']]   # startup window
        s = comb(inp, True, False); assert s[netids['FAULT_CLK']]                            # armed -> clock FAULT
        s = comb(inp, True, True); assert not s[netids['RUN']]
        inp[missing] = True
        s = comb(inp, True, True); assert not s[netids['RUN']]                               # no self-restart
        inp['RESET_N'] = False; s = comb(inp, False, False); assert not s[netids['RUN']]
        seq.append(missing)
    inp = dict(base); inp['OV_N'] = False
    assert not comb(inp, False, False)[netids['RUN']], 'OV preset acts inside the startup window'
    inp['OV_N'] = True
    assert not comb(inp, False, True)[netids['RUN']], 'FAULT set by OV stays latched after OV clears'
    seq.append('OV_N preset (unarmed) + latched after release')

    root = Path(root) if root else hardware / 'single' / f'{circuit_s8.PROJECT}.kicad_sch'
    sheets = nodes(parse(root.read_text()), 'sheet'); assert len(sheets) == 6, ('Hierarchy sheet count', len(sheets))
    files = [root] + [root.parent / next(p[2] for p in nodes(s, 'property') if p[1] == 'Sheetfile') for s in sheets]
    assert len(set(files)) == 7 and all(f.exists() for f in files), files
    for f in files:
        for sym in nodes(parse(f.read_text()), 'symbol'):
            r = next(p[2] for p in nodes(sym, 'property') if p[1] == 'Reference')
            if r.startswith('TP'):
                assert one(sym, 'in_bom')[1] == 'no' and one(sym, 'in_pos_files')[1] == 'no' and one(sym, 'on_board')[1] == 'yes'
    return {'status': 'S8_schematic_checks_not_bench_qualification', 'components': len(comps),
            'nets_including_NC': len(nets), 'sheets': len(files), 'exact_field_pin_NC_pad_parity': True,
            'removed_S7_refs': len(removed), 'added_refs': sorted(added),
            'ceramic_banks_22u_or_10u': banks, 'vin_damper': {'R92_ohm': value('R92'), 'C5_C62_uF': [10, 10]},
            'overvoltage_guard_V': {'+12V_min_nom_max': [round(v, 3) for v in ov12],
                                    '+5V_min_nom_max': [round(v, 3) for v in ov5],
                                    '-12V_magnitude_min_nom_max': [round(v, 3) for v in ovneg],
                                    'model': 'REF_OV TLV431BI 1.2204-1.259 V, LM2901B 5.5 mV / 50 nA, 0.1 % + 25 ppm x 100 C',
                                    'converter_setpoint_max_V': {'+12V': round(p12_max, 3), '+5V': round(p5_max, 3),
                                                                 '-12V': round(n12_max, 3)},
                                    'stacked_normal_peak_V': {k: round(v, 3) for k, v in peak.items()},
                                    'margin_min_to_peak_V': {k: round(bands[k][0] - peak[k], 3) for k in bands},
                                    'downstream_limit_V': DOWNSTREAM_MAX_V,
                                    'margin_max_to_limit_V': {k: round(DOWNSTREAM_MAX_V[k] - bands[k][2], 3) for k in bands},
                                    'converter_OVP_max_V': {'+12V': round(ovp12_max, 2), '+5V': round(ovp5_max, 2)},
                                    'corner_overlap_with_converter_OVP': {'+12V': ov12[0] < ovp12_max, '+5V': ov5[0] < ovp5_max},
                                    'U21_cathode_current_min_mA': round(ik_min * 1e3, 3)},
            'crowbar': {'trip_+5V_min_nom_max_V': [round(v, 3) for v in crow],
                        'model': 'TLVH432BI 1.220-1.259 V, Iref <= 0.9 uA, 0.1 % + 25 ppm x 100 C (R101/R102)',
                        'margin_min_to_stacked_peak_V': round(crow[0] - peak['+5V'], 3),
                        'margin_max_to_6V_V': round(DOWNSTREAM_MAX_V['+5V'] - crow[2], 3),
                        'gate_drive_at_trip_min_mA': {t: round(v * 1e3, 2) for t, v in drive.items()},
                        'gate_overdrive_x_IGT_max': {t: round(drive[t] / IGT_MAX[t], 1) for t in drive},
                        'CROW_DRV_at_SCR_fire_min_V': {t: round(v, 2) for t, v in fire_min.items()},
                        'Q13_turn_on_max_V': Q13_ON_MAX_V,
                        'self_powered': 'no crowbar net touches V3V3, REF_OV, REF_GOOD or MON_OV5'},
            'nominal_voltage_valid_thresholds': mon, 'logic_POR_high_screen_V': por_max,
            'startup_qualification_typ_s': t_start, 'digital_combinations_checked': cases, 'scenarios': seq,
            'warnings': ['Arithmetic stacks every tolerance at once; it is a screen, not a rating.',
                         'Digital truth checks do not model analog propagation, comparator/LED timing or MOSFET transients.',
                         'No PCB placement/routing, thermal, start-up-into-rack or overload bench result exists for S8.'],
            'order_ready': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--netlist', type=Path, required=True)
    ap.add_argument('--hardware', type=Path, default=MODULE / 'hardware')
    ap.add_argument('--root', type=Path, help='S8 root (default <hardware>/single/usb-power-45w-single.kicad_sch)')
    a = ap.parse_args()
    print(json.dumps(verify(a.netlist, a.hardware, a.root), indent=2))
