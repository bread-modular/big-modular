"""Read-only S3 input-protection regression checks.

Run with KiCad's Python from the repository root:
  /usr/bin/python3 -B modules/line-in/tools/check_input_protection.py

Reuses the module's native netlist export helper; no second netlist parser,
source writes, simulator, or substitute for the shared full ERC/DRC gate.
"""
import json
import math
from build_layout import schematic_netlist


def check():
    parts, nets = schematic_netlist()
    pins = {net: set(members) for net, members in nets.items()}
    for ch, cap, bias, limiter, amp, positive, negative in [
        ('L', 'C9', 'R1', 'R13', 'U1', 'D3', 'D4'),
        ('R', 'C10', 'R2', 'R14', 'U2', 'D5', 'D6'),
    ]:
        assert pins['/COUP_' + ch] == {(cap, '2'), (bias, '1'), (limiter, '1')}
        assert pins['/AC_' + ch] == {(limiter, '2'), (amp, '3'), (positive, '1'), (negative, '2')}
        assert {(bias, '2'), (positive, '2'), (negative, '1')} <= pins['GND']
        for ref in (positive, negative):
            matches = [net for net, members in pins.items() if (ref, '3') in members]
            assert len(matches) == 1 and matches[0].startswith('unconnected-'), (ref, matches)
            assert pins[matches[0]] == {(ref, '3')}
            assert parts[ref]['value'] == 'BAV199'
            assert parts[ref]['footprint'] == 'LineIn:SOT-23'
            assert parts[ref]['fields']['LCSC'] == 'C40919'
            assert parts[ref]['fields']['MPN'] == 'BAV199,215'
        assert parts[limiter]['value'] == '10k'
        assert parts[limiter]['fields']['LCSC'] == 'C25804'
        assert parts[bias]['value'] == '1M'
        assert parts[cap]['value'] == '1u'
        assert parts[cap]['fields']['LCSC'] == 'C28323'
        assert parts[cap]['fields']['Voltage'] == '50V'
    for ref in ('R7', 'R8', 'R12'):
        assert parts[ref]['value'] == '1k'
        assert parts[ref]['footprint'] == 'LineIn:R_1206_3216Metric'
        assert parts[ref]['fields']['LCSC'] == 'C2074262'
        assert parts[ref]['fields']['MPN'] == 'ESR18EZPF1001'
    vmax, rmin, rmax = 25.2, 9900.0, 10100.0
    imax = vmax / rmin
    p_voltage = vmax ** 2 / rmin
    # The assembly auditor independently envelopes V and I tolerance corners.
    p_independent = max(p_voltage, imax ** 2 * rmax)
    assert imax < 0.00255 and p_independent < 0.1 * 0.7
    result = {
        'topology_and_exact_parts': 'pass',
        'diode_midpoints_externally_nc': 4,
        'unchanged_output_resistor_identity': 'pass',
        'reversal_envelope_v': vmax,
        'limiter_current_upper_a': imax,
        'limiter_voltage_driven_power_upper_w': p_voltage,
        'independent_audit_power_upper_w': p_independent,
        'nominal_unloaded_gain': -100000 / 5100,
        'nominal_highpass_hz': 1 / (2 * math.pi * 1e6 * 1e-6),
        'powered_off_immunity_qualified': False,
        'hardware_tested': False,
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    check()
