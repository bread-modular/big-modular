"""S5 circuit-specific checks on a native KiCad XML netlist (read-only).

Run native ERC separately. This checks exact table/field/pad parity, the new
protection topology, board-current screening and optional S3/S4 preservation.
It is NOT a substitute for prototype, surge, thermal or USB compliance testing.
"""
import argparse
import itertools
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from circuit45 import circuit
from build_schematic import FP
from sexp import parse, nodes, one, walk


def load_xml(path):
    root = ET.parse(path).getroot()
    comps = {c.get('ref'): c for c in root.findall('components/comp')}
    nets = {n.get('name'): {(p.get('ref'), p.get('pin')) for p in n.findall('node')}
            for n in root.findall('nets/net')}
    pins = {pin: name for name, members in nets.items() for pin in members}
    return root, comps, nets, pins


def current_screen(r_ohms):
    """Board-side design constraints, independent of adapter marketing power.

    The 5 A connector class is NOT an instantaneous short-circuit ceiling.
    Keep 0.25 A of static margin; validate thermal and pulse behavior on the PCB.
    """
    assert 3000 <= r_ohms <= 30000, 'Outside U5 recommended ILIM resistance'
    nominal = 18000 / r_ohms
    minimum = nominal * 0.90 / (1.01 * 1.01)
    maximum = nominal * 1.10 / (0.99 * 0.99)
    total = maximum + 0.025
    assert total < 4.75, 'Limit plus auxiliary current violates 5 A path minus 0.25 A guard'
    assert minimum > 3.60, 'Insufficient full-load design headroom; not a continuous rating'
    return {'nominal': nominal, 'screened_min': minimum, 'screened_max': maximum,
            'auxiliary_reserve': 0.025, 'total_screened_max': total,
            'board_input_class': 5.0, 'static_guard': 0.25,
            'full_load_source_PDO': 5.0}


def verify(netlist, hardware, baseline=None, previous=None):
    root, comps, nets, pins = load_xml(netlist)
    parts = {p['ref']: p for p in circuit() if not p['ref'].startswith('#')}
    assert set(comps) == set(parts), 'Component set mismatch'
    wanted = {}
    for ref, p in parts.items():
        assert comps[ref].findtext('value') == p['value'], (ref, 'value')
        assert comps[ref].findtext('footprint') == 'USBPOWER45:' + FP[p['fp']], (ref, 'footprint')
        for field, value in p['fields'].items():
            assert comps[ref].findtext(f'fields/field[@name="{field}"]') == value, (ref, field)
        fp = parse((hardware / 'USBPOWER45.pretty' / (FP[p['fp']] + '.kicad_mod')).read_text())
        pads = {str(pad[1]) for pad in nodes(fp, 'pad') if pad[1]}
        assert pads == set(p['pins']), (ref, 'physical pad-number set', pads, set(p['pins']))
        for pin, net in p['pins'].items():
            key = (ref, pin)
            if net is None:
                assert pins[key].startswith('unconnected-') and nets[pins[key]] == {key}, (key, 'NC')
            else:
                wanted.setdefault(net, set()).add(key)
    for net, members in wanted.items():
        actual = [name for name, ms in nets.items() if ms == members]
        assert len(actual) == 1, (net, 'net membership')
        if not net.startswith('_'):
            assert actual[0].lstrip('/') == net, (net, actual)

    # Independent manufacturer pin-role/topology expectations, not inferred from the drawing.
    critical = {
        'U5': {'1': 'EF_IN', '2': 'EF_IN', '3': 'EF_IN', '6': 'EF_IN', '7': 'EF_UV', '8': 'EF_OV',
               '9': 'GND', '10': 'EF_DVDT', '11': 'EF_ILM', '12': 'GND', '13': 'EF_SHDN',
               '14': 'EF_IMON', '15': 'EF_FLT', '16': 'EN_P', '18': 'VIN', '19': 'VIN',
               '20': 'VIN', '21': 'GND'},
        'D10': {'1': 'EF_IN', '2': 'VPD'},  # K, A: USB reverse-blocking diode
        'D9': {'1': 'VPD_U1', '2': 'GND'},
        'D11': {'1': 'VPD', '2': 'VPD_U1'},  # auxiliary capacitor reverse-discharge clamp
        'D1': {'1': 'VPD', '2': 'GND'},
        'Q2': {'1': 'PD_SENSE', '2': 'VPD_U1', '3': 'PD_BASE'},  # Nexperia E,C,B
        'Q3': {'1': 'PD_SENSE', '2': 'VPD', '3': 'PD_BASE'},     # onsemi B,E,C
        'R23': {'1': 'VPD', '2': 'PD_SENSE'},
        'R27': {'1': 'PD_BASE', '2': 'GND'},
        'SW1': {'1': 'EF_SHDN', '3': 'EF_SHDN', '2': 'GND'},
        'U1': {'1': 'VPD_U1', '8': 'VPD_U1'},
        'U2': {'2': 'EN_P'}, 'U3': {'2': 'EN_P'},
    }
    for ref, mapping in critical.items():
        for pin, expected in mapping.items():
            assert pins[(ref, pin)].lstrip('/') == expected, (ref, pin, expected)
    q2 = next(lp for lp in root.findall('libparts/libpart') if lp.get('part') == 'BCX53_NXP')
    assert {p.get('num'): p.get('name') for p in q2.findall('pins/pin')} == {'1': 'E', '2': 'C', '3': 'B'}
    assert comps['U5'].findtext('fields/field[@name="MPN"]') == 'TPS16630PWPR'
    assert comps['U5'].findtext('fields/field[@name="LCSC"]') == 'C1849461'
    assert 'C4' not in comps, 'Old overload timer must not survive the IC change'
    assert comps['D10'].findtext('fields/field[@name="MPN"]') == 'SS1060'
    assert comps['D10'].findtext('fields/field[@name="LCSC"]') == 'C2917888'
    assert comps['D10'].findtext('fields/field[@name="Manufacturer"]') == 'ZHIDE'
    assert comps['D10'].findtext('footprint') == 'USBPOWER45:D_SMC'
    assert nets[pins[('U5', '11')]] == {('U5', '11'), ('R5', '1')}
    assert nets[pins[('R5', '2')]] == {('R5', '2'), ('R29', '1')}, 'ILIM resistors must be series'
    assert pins[('R29', '2')] == 'GND'
    assert comps['R5'].findtext('value') == '3.3k' and comps['R29'].findtext('value') == '1k'
    assert comps['R5'].findtext('fields/field[@name="LCSC"]') == 'C22978'
    assert comps['R29'].findtext('fields/field[@name="LCSC"]') == 'C21190'
    sch = parse((hardware / 'usb-power-45w.kicad_sch').read_text())
    for symbol in nodes(sch, 'symbol'):
        props = {p[1]: p[2] for p in nodes(symbol, 'property')}
        if props.get('Reference', '').startswith('TP'):
            assert one(symbol, 'in_bom')[1] == 'no'
            assert one(symbol, 'in_pos_files')[1] == 'no'
            assert one(symbol, 'on_board')[1] == 'yes'
    assert (hardware / 'usb-power-45w.kicad_pro').exists()

    # Independent nominal values, and full-temperature screening including R TCR.
    def resistance(ref):
        s = comps[ref].findtext('value')
        return float(s[:-1]) * 1000 if s.endswith('k') else float(s)

    factors = (0.99 * 0.99, 1.01 * 1.01)  # 1% tolerance and 100 ppm/K over 100 K
    def trip(top, bottom, threshold):
        rt, rb = resistance(top) + (resistance('R28') if top == 'R4' else 0), resistance(bottom)
        v = [vt * (1 + rt * a / (rb * b)) + leak * rt * a
             for a, b, vt, leak in itertools.product(factors, factors, threshold, (-150e-9, 150e-9))]
        return {'min_V': min(v), 'max_V': max(v)}

    uv_r = trip('R2', 'R3', (1.176, 1.224))
    uv_f = trip('R2', 'R3', (1.09, 1.15))
    ov_r = trip('R4', 'R24', (1.176, 1.224))
    ov_f = trip('R4', 'R24', (1.09, 1.15))
    assert uv_r['min_V'] > 15.75 and uv_r['max_V'] < 19
    assert ov_r['min_V'] > 21 and ov_r['max_V'] < 30
    assert ov_f['min_V'] > 21, 'OVP must recover after a surge at the highest valid 20 V PDO voltage'
    current = current_screen(resistance('R5') + resistance('R29'))
    imax = current['screened_max']
    imon_max = imax * 29.58e-6 * resistance('R26') * factors[1]
    assert imon_max < 4, 'IMON must remain within recommended output range'
    # Treat 0.75 V D10 drop as a screening value, not a cold/hot curve guarantee.
    # 50 mOhm additional path resistance is a validation allowance, not measured.
    power = sum(v * i / eta for v, i, eta in
                ((0.8 * (1 + resistance('R8') / resistance('R9')), 2.5, .91),
                 (0.8 * (1 + resistance('R11') / resistance('R12')), 2.5, .86),
                 (1 + resistance('R14') / resistance('R15'), 1, .84)))
    load_estimates = []
    for bus_v in (18.5, 19, 20, 21):
        series_r = .053 + .050
        # bus_v is USB-receptacle voltage, not adapter-terminal voltage.
        i = ((bus_v - .75) - math.sqrt((bus_v - .75)**2 - 4 * series_r * power)) / (2 * series_r)
        assert i < current['screened_min'], 'Estimated full load exceeds minimum current threshold'
        load_estimates.append({'receptacle_V': bus_v, 'load_path_A': i,
                               'total_USB_A': i + .025, 'USB_W': bus_v * (i + .025)})
    assert comps['C3'].findtext('value') == '22n'
    result = {
        'components': len(comps), 'nets_including_nc': len(nets), 'parity_mismatches': 0,
        'physical_pad_number_parity': True, 'critical_pin_checks': True,
        'UVLO_rising': uv_r, 'UVLO_falling': uv_f, 'OVP_rising': ov_r, 'OVP_falling': ov_f,
        'current_A': current, 'IMON_screened_max_V': imon_max,
        'estimated_converter_input_W': power, 'full_load_estimates': load_estimates,
        'protection_path_loss_at_screened_limit_W': {'U5_at_53mOhm': imax**2 * .053,
                                                    'D10_at_075V': imax * .75},
        'D10_required_effective_thetaJA_50C_ambient_125C_junction_C_per_W': 75 / (imax * .75),
        'assumptions': ['R: 1% tolerance plus 100 ppm/K over 100 K, multiplied corners',
                        'U5 threshold and leakage limits from TI SLVSET9G',
                        'Conservative +/-10% ILIM screen, wider than TI +/-7% at the nearby 4.02k/4.5A test point; prototype verification required',
                        'Static limiting only: fast-trip/short-circuit pulses can exceed the 5 A path class',
                        'Power estimates use unmeasured efficiencies .91/.86/.84, D10 .75V and .050 ohm additional input path allowance',
                        'No automatic PD-current tracking or independent per-output-rail eFuse limits',
                        'Q2/Q3 clamp, startup, thermal and dynamic behavior require prototype qualification'],
        'order_ready': False,
    }
    if baseline:
        _, old, _, opins = load_xml(baseline)
        changed = {'U1', 'U5', 'F1', 'D1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'C1', 'C2', 'C3', 'C4', 'SW1'}
        unchanged = sorted(set(old) - changed)
        for ref in unchanged:
            assert ref in comps
            for field in ('value', 'footprint'):
                assert old[ref].findtext(field) == comps[ref].findtext(field), (ref, field, 'S3 preservation')
            for key in (key for key in opins if key[0] == ref):
                assert opins[key] == pins[key], (key, 'S3 net-name preservation')
        result['unchanged_S3_components_checked'] = unchanged
    if previous:
        _, old, _, opins = load_xml(previous)
        assert set(comps) - set(old) == {'R29'} and not (set(old) - set(comps)), 'Unexpected S4/S5 ref delta'
        assert old['R5'].findtext('value') == '9.1k' and old['D10'].findtext('value') == 'SS56'
        preserved = []
        for ref, oc in old.items():
            if ref not in {'R5', 'D10'}:
                for field in ('value', 'footprint'):
                    assert oc.findtext(field) == comps[ref].findtext(field), (ref, field, 'S4 preservation')
                for f in oc.findall('fields/field'):
                    if f.get('name') != 'Note':
                        actual = comps[ref].find(f'fields/field[@name="{f.get("name")}"]')
                        assert actual is not None and f.text == actual.text, (ref, f.get('name'))
                preserved.append(ref)
            for key in (key for key in opins if key[0] == ref):
                if key != ('R5', '2'):
                    assert opins[key] == pins[key], (key, 'unexpected S4/S5 wiring change')
        result['unchanged_S4_components_checked'] = sorted(preserved)
        result['intentional_S4_delta'] = {'added': ['R29'], 'changed': ['R5', 'D10'],
                                        'rewired_pin': 'R5.2 through R29 to GND'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--hardware', type=Path, required=True)
    parser.add_argument('--baseline-netlist', type=Path, help='Optional original S3 XML for unchanged converter checks')
    parser.add_argument('--previous-netlist', type=Path, help='Optional S4 XML for strict S5-only delta checks')
    args = parser.parse_args()
    print(json.dumps(verify(args.netlist, args.hardware, args.baseline_netlist, args.previous_netlist), indent=2))
