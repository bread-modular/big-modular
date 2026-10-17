#!/usr/bin/env python3
"""ES1 reproducible DC/tolerance screening, not bench or thermal qualification.

Datasheet electrical-characteristic extrema are used directly; the TPS65131
3% summary is NOT added again. Bias-current signs are bounded conservatively.
Resistor TCR uses independently recorded catalog limits at up to 100 K from 25 C:
the retained R12/R14 precision parts are 0.1%/25 ppm/K, while substituted Basic
parts are 1%/100 ppm/K. The mixed factors are NOT a blanket 0.1%/25 ppm/K model.
Supplier PDF fetch was blocked; manufacturer resistor/TCR and capacitor bias
evidence remain procurement gates.
"""
from itertools import product
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 0.1% tolerance plus 25 ppm/K over a 100 K excursion; R12/R14 retained parts.
PRECISION_FACTORS = [.999 * (1 - 25e-6 * 100), 1.001 * (1 + 25e-6 * 100)]
# 1% tolerance plus 100 ppm/K over a 100 K excursion; substituted Basic parts.
BASIC_FACTORS = [.99 * .99, 1.01 * 1.01]


def _bias_retention(points, voltage):
    a, b = next((a, b) for a, b in zip(points, points[1:]) if a[0] <= voltage <= b[0])
    return 1 + (a[1] + (b[1] - a[1]) * (voltage - a[0]) / (b[0] - a[0])) / 100


def _screened(points, nominal_uF, voltage, count=1):
    return count * nominal_uF * _bias_retention(points, voltage) * .9 * .85 * .95


def capacitor_screen():
    """Exact-MPN typical bias + explicit screening factors, never qualification."""
    d = json.loads((ROOT / 'docs/ldo-evidence/manufacturer-mlcc-data.json').read_text())
    assert (d['mpn'], d['code'], d['nominal_uF']) == ('CL31A226KAHNNNE', 'C12891', 22)
    points = d['dc_bias_V_delta_percent']
    out = {}
    for name, refs, v, need in [('positive_input', [48, 49, 50, 63], 15.0, 10),
            ('positive_output', [51, 52, 53, 64, 65, 66], 12.4, 20),
            ('negative_input', [54, 55, 56, 67], 15.0, 10),
            ('negative_output', [57, 58, 59], 12.9, 10)]:
        screened = _screened(points, 22, v, len(refs))
        out[name] = {'refs': ['C' + str(i) for i in refs], 'bias_V': v,
                     'nominal_uF': 22 * len(refs),
                     'bias_retention_typical': _bias_retention(points, v),
                     'typical_uF': len(refs) * 22 * _bias_retention(points, v),
                     'screened_effective_uF': screened,
                     'required_effective_uF': need, 'screen_pass': screened >= need}
    return out


def accepted_capacitor_plan():
    """Accepted Sol041/Astra043 local-capacitance plan (typical screens only).

    C5/C18 become 22 uF C12891; new C68/C69 add one 22 uF per buck at VPROT/GND
    (2 x 22 uF local screen at 9.45 V). New C70/C71 make three local 22 uF at
    MID/L1 with C6; new C72 makes three local 22 uF at P5/L4 with C19/C38.
    Remote C37 is not counted as local. C4/C16/C17 keep C13585.
    The 10 uF input and <40 kHz crossover figures are application
    recommendations, not absolute IC guarantees; bench evidence is pending.
    """
    bank = json.loads((ROOT / 'docs/ldo-evidence/manufacturer-mlcc-data.json').read_text())
    c13585 = json.loads((ROOT / 'docs/ldo-evidence/C13585-bias.json').read_text())
    assert (bank['mpn'], bank['code'], bank['nominal_uF']) == ('CL31A226KAHNNNE', 'C12891', 22)
    assert (c13585['mpn'], c13585['code']) == ('CL31A106KBHNNNE', 'C13585')
    b_points = bank['dc_bias_V_delta_percent']
    c_points = c13585['dc_bias_V_delta_percent']

    vprot_two = _screened(b_points, 22, 9.45, 2)
    mid_three = _screened(b_points, 22, 5.5, 3)
    p5_three = _screened(b_points, 22, 5.5, 3)
    p5_crossover = 5.1 / (4.712886897200467 * p5_three * 1e-6)
    return {
        'source': 'Accepted Sol041 sizing / Astra043 local implementation plan',
        'C13585_bias_source': {
            'url': c13585['source_url'], 'sha256': c13585['sha256'],
            'conditions': c13585['conditions']},
        'C5_C18_value_uF': 22,
        'C5_C18_refs': ['C5', 'C18'],
        'C68_C69_refs': ['C68', 'C69'],
        'C70_C71_refs': ['C70', 'C71'],
        'C72_refs': ['C72'],
        'VPROT_each_buck_2x22_at9p45V_uF': vprot_two,
        'MID_local_3x22_at5p5V_uF': mid_three,
        'P5_local_3x22_at5p5V_uF': p5_three,
        'P5_crossover_estimate_at5V_Hz': p5_crossover,
        'TI_no_feedforward_crossover_guideline_Hz': 40000,
        'VPROT_local_input_gate': {
            'required_uF': 10.0, 'screened_uF': vprot_two,
            'screen_pass': vprot_two >= 10.0},
        'P5_output_loop_gate': {
            'screened_uF': p5_three, 'estimated_crossover_Hz': p5_crossover,
            'guideline_Hz': 40000, 'screen_pass': p5_crossover <= 40000},
        'C4_C16_C17_C13585_each_at9p45V_uF': _screened(c_points, 10, 9.45),
        'C4_C16_C17_C13585_each_at5p5V_uF': _screened(c_points, 10, 5.5),
        'application_recommendation_not_IC_guarantee': True,
        'bench_pending': True,
    }



def budget():
    factors = {'precision_0p1pct_25ppm': PRECISION_FACTORS,
               'basic_1pct_100ppm': BASIC_FACTORS}
    f, g = PRECISION_FACTORS, BASIC_FACTORS

    # Positive raw: R12 precision, R75 Basic, R13 Basic.
    positive = [v * (1 + (1.5e6 * a + 24e3 * c) / (150e3 * b)) + i * (1.5e6 * a + 24e3 * c)
                for v, a, b, c, i in product([1.189, 1.237], f, g, g, [-50e-9, 50e-9])]
    # Negative raw: R14 precision, R60/R15/R76 Basic.
    negative = []
    for vr, vfb, a, b, c, d, i in product([1.2, 1.225], [-.024, .024], f, g, g, g,
                                           [-50e-9, 50e-9]):
        rt = 1.6e6 * a + 150e3 * b
        ratio = rt / (150e3 * c + 2.4e3 * d)
        negative.append(vr * ratio - vfb * (1 + ratio) + i * rt)
    # Negative LDO divider: R72/R83/R73/R74 are all Basic 1%, 100 ppm/K.
    neg_out = []
    for v, a, b, c, d, i in product([1.175 * .975, 1.175 * 1.025], g, g, g, g,
                                    [-100e-9, 100e-9]):
        rt = 82000 * a + 9100 * b + 1200 * c
        neg_out.append(v * (1 + rt / (10e3 * d)) + i * rt)
    # MID/P5 buck divider: R9/R17 and R10/R18/R84/R85 are Basic 1%, 100 ppm/K.
    buck = [v * (1 + 100000 * a / (13000 * b + 510 * c))
            for v, a, b, c in product([.581, .611], g, g, g)]

    raw_p_nom = 1.213 * (1 + 1524000 / 150000)
    raw_n_nom = 1.213 * 1750000 / 152400
    neg_nom = 1.175 * (1 + 92300 / 10000)
    pp = [min(positive), max(positive)]
    nn = [min(negative), max(negative)]
    outp = [12 * .975, 12 * 1.025]
    outn = [min(neg_out), max(neg_out)]
    # A design ALLOCATION, not a measurement/promise of converter ripple.
    ripple = .1
    hp = pp[0] - ripple - outp[1]
    hn = nn[0] - ripple - outn[1]

    caps = capacitor_screen()
    gates = accepted_capacitor_plan()
    ldo_bank_pass = all(v['screen_pass'] for v in caps.values())
    mid_upper = max(buck)
    mid_peak = mid_upper + ripple
    mid_margin = 5.5 - mid_peak
    # Explicit voltage gate on the highest-bias electrolytic/ceramic bank.
    cap_voltage_margin = 25 - (max(nn[1], pp[1]) + ripple)

    assert mid_peak < 5.5, 'MID/P5 upper DC corner plus stated ripple exceeds 5.5 V'
    assert mid_margin > 0
    assert cap_voltage_margin > 0, 'capacitor voltage rating gate failed'
    raw_trough_min = min(pp[0], nn[0]) - ripple

    losses = {}
    for current in [.25, .8, 1.]:
        losses[str(current)] = {
            'positive_pass_nominal_W': (raw_p_nom - 12) * current,
            'negative_pass_nominal_W': (raw_n_nom - neg_nom) * current,
            'positive_pass_corner_W': (pp[1] + ripple - outp[0]) * current,
            'negative_pass_corner_W': (nn[1] + ripple - outn[0]) * current}
    # Illustrative CCM screen only. 1.8A table limit is specified at particular
    # VIN/VPOS conditions, not a newly guaranteed rail-current rating here.
    screen = {}
    vin = 5.
    vd = .5
    freq = 1.25e6
    ind = 4.7e-6 * .8
    for name, duty in [('boost', 1 - vin / (raw_p_nom + vd)),
                       ('inverter', (raw_n_nom + vd) / (vin + raw_n_nom + vd))]:
        di = vin * duty / (freq * ind)
        screen[name] = {'assumed_duty': duty, 'inductor_ripple_A': di,
                        'ideal_output_at_1p8A_peak_A': (1.8 - di / 2) * (1 - duty)}
    return {
        'status': 'static design screening; NOT qualified hardware',
        'raw_nominal_magnitudes_V': {'positive': raw_p_nom, 'negative': raw_n_nom},
        'raw_resistors_ohm': {'R12': 1500000, 'R75': 24000, 'R13': 150000,
                              'R14': 1600000, 'R60': 150000, 'R15': 150000,
                              'R76': 2400, 'R72': 82000, 'R83': 9100,
                              'R73': 1200, 'R74': 10000,
                              'R9': 100000, 'R10': 13000, 'R84': 510,
                              'R17': 100000, 'R18': 13000, 'R85': 510},
        'MID_and_P5': {
            'nominal_V': .596 * (1 + 100000 / 13510),
            'DC_V': [min(buck), max(buck)],
            'peak_with_allocation_V': mid_peak,
            'MID_limit_V': 5.5,
            'MID_margin_V': mid_margin,
            'upper_with_ripple_below_5p5': mid_peak < 5.5,
            'five_percent_accuracy_guaranteed': False},
        'positive_input_trough_V': pp[0] - ripple,
        'negative_input_trough_magnitude_V': nn[0] - ripple,
        'raw_input_trough_min_V': raw_trough_min,
        'raw_trough_above_13V': raw_trough_min > 13,
        'raw_feedback_bias_assumption_A': [-50e-9, 50e-9],
        'positive_raw_DC_V': pp,
        'negative_raw_DC_magnitude_V': nn,
        'positive_final_nominal_V': 12.,
        'negative_final_nominal_V': -neg_nom,
        'positive_final_DC_V': outp,
        'negative_final_DC_magnitude_V': outn,
        'resistor_tolerance_plus_TCR_factors': factors,
        'ripple_transient_allocation_peak_V': ripple,
        'positive_worst_headroom_V': hp,
        'negative_worst_headroom_V': hn,
        'positive_dropout_max_at_1A_V': .45,
        'negative_dropout_max_at_1A_V': .8,
        'positive_dropout_reserve_V': hp - .45,
        'negative_dropout_reserve_V': hn - .8,
        'positive_full_corner_1A_drop_out_pass': hp >= .45,
        'negative_full_corner_1A_drop_out_pass': hn >= .8,
        'negative_headroom_status': ('PASS' if hn >= .8 else
            'FAIL: full-temperature 1 A negative dropout/accuracy not assured; '
            'conditional prototype limit accepted under looser Basic passives'),
        'no_new_current_guarantee': True,
        'pass_dissipation_excludes_ground_current': losses,
        'thermal_additional_loss': 'Add |VIN| * IGND; no full-load maximum IGND is established. JEDEC thetaJA is not this board.',
        'cap_voltage_rating_margin_V': cap_voltage_margin,
        'capacitor_banks': caps,
        'ldo_bank_screen_passed': ldo_bank_pass,
        'capacitor_release_gates': gates,
        'capacitor_plan_screens_pass': (ldo_bank_pass and
            gates['VPROT_local_input_gate']['screen_pass'] and
            gates['P5_output_loop_gate']['screen_pass']),
        # Screens pass and the plan is implemented; bench/lot physics is still unverified.
        'capacitor_release_ready': bool(ldo_bank_pass and gates['VPROT_local_input_gate']['screen_pass'] and gates['P5_output_loop_gate']['screen_pass']),
        'capacitor_bench_qualified': False,
        'cap_effective_C_verified': False,
        'cap_ESR_verified': False,
        'cap_prototype_screen_passed': (ldo_bank_pass and
            gates['VPROT_local_input_gate']['screen_pass'] and
            gates['P5_output_loop_gate']['screen_pass']),
        'cap_bank_disposition': ('LDO 4/6/4/3 banks PASS the explicit typical-data '
            'prototype screen; the accepted 043 local-cap plan screens 10.664 uF per '
            'buck at 9.45 V and 27.631 uF at 5.5 V with 39.164 kHz estimated P5 '
            'crossover, and the plan is implemented independently in the 043 native source. '
            'Bench/lot/loop evidence remains pending; application recommendations, not '
            'guaranteed minima.'),
        'accuracy_headroom_budget_applicable_to_present_capacitors': 'conditional on screened capacitance and stated ripple/temperature/lot assumptions; not bench verified',
        'positive_startup_typ_s_at_nominal_1uF': 100000 * 1e-6 * math.log((12 + 5) / 5),
        'negative_startup_typ_s_at_nominal_100nF': .12,
        'screening_only_CCM_at_5V': screen,
        # R8 5.6k + R79 220 + R80 220 = 6.04k effective ILIM.
        'nominal_efuse_input_power_W_at_9V': 9 * 12000 / 6040,
        'simultaneous_12V_800mA_rail_output_power_W': 2 * 12 * .8,
        'current_rating_claim': None,
        'PCB_integration_completed': True,
        'reverse_and_shutdown_qualification_completed': False,
        'assembly_Basic_policy_exception_approved': False,
    }


if __name__ == '__main__':
    print(json.dumps(budget(), indent=2))
