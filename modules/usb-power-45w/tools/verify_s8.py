"""S8 single-board native hierarchy/circuit verifier. Read-only; run native ERC separately.

  python3 -B tools/verify_s8.py --netlist <native kicadxml of hardware/single/usb-power-45w-single.kicad_sch>

Checks exact components, physical pad sets, pin memberships, NCs and fields against
tools/circuit_s8.py; that every S7 eFuse / negative-switch part is gone and nothing else; the
ceramic banks and VIN damper topology; manufacturer pin roles (TPS3808 via verify_design's TI
table, LM2901 comparator pairing against the TI pin table kept here); bounded threshold arithmetic; and a settled
digital model of the latch/LED logic including the overvoltage preset. S8 final: D8 MAIN is the only LED
(rail LEDs removed). S8.1 (review fixes): the guard's own TLV431B reference REF_OV (pin roles against TI's DBZ
table kept here), LM2901B on U18/U20, the -12V channel compared with GND, the D22 clamp on MON_OVN, 0.1 %
dividers and the guard bands. S8.3 checks TPS259470A pin roles, split raw/delivered +5V,
OVLO/current programming, VPD-powered comparator headroom, and the absence of every removed crowbar
device/net. S8.4 (review fixes): U23 FLT (pin 4) only reaches its own pull-up R108 and pad TP21, never P5_OK
or the latch (C1); P5_OK = AUXOFF + U18; the startup timer input TIMER_GO = RUN AND MAIN_OK, the converter
enable net, not V20_OK (M1); R11/R12 0.1 % with the OVLO margin from U23's highest current limit (M2).
S8.5 (item B, U23 unchanged): STARTED (U12 A, preset by START_N = NAND(MAIN_LED_OK, RUN), cleared only by RESET_N,
clock low) -> TIMER_GO = RUN AND STARTED -> U11 -> ARMED; TPS3808 roles against TI's DBV table with the S8.5 U11
output; the V20_OK status floor against vSafe5V and the U5 turn-off minimum; an event-driven timing simulation of the
arming logic built from the native gate wiring (arming_timelines) replays cold start at the worst loaded 20 V minimum,
slow PD contract, brown-out after/inside the window, input overload chatter, hot plug into a live bus, load release,
U20 guard before ARMED and a short RESET against four required behaviours (bounded arming, no restart, no early
arming, fail-safe after arming). The S8.4 wiring (TIMER_GO = RUN AND MAIN_OK) fails them (test_s8 regression).
S9.0 step 1: the +5V subsystem is gone - no +5V/P5_* net, none of the S9_REMOVED / S8_PLUS5_DROPPED refs, J2/J3 pins
11/12 open, U14 gate 1 input 4 tied high (ANY_BAD = NOT(MAIN_LED_OK AND P12_OK AND N12_OK)), the freed U18/U20 comparators
spares with defined inputs and open outputs, OV_N driven only by the +12V and -12V guard channels, U5 nets MAIN_*.
S9.0 step 2: 15 V input (R1 56k, R3 10k, R83 100k) and the TPS552892-Q1 +12V buck-boost: pin roles against TI's SLVSGT7
table (kept in tools/s90_parts.py, independent of the symbol), the four-switch cell wiring (L1 SW1-SW2, BOOT capacitors,
MODE/EXTVCC/VCC with C82, R110 FSW, R109 between VOUT/ISP and +12V/ISN, FB from +12V, COMP R111/C83, PG/CC/CDC open), the
rail memberships (no series element on +/-12V other than R109 at the converter: the owner decision of no reverse
blocking, no ideal-diode/FET part anywhere) and the arming timelines at the 15 V source corners.
Static checks, settled logic and logic timing, not a peak-voltage guarantee.
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
from verify_design import TPS3808_DBV, load_xml
from s90_parts import FP_S90, TPS552892_TI
from s92_parts import FP_S92

MODULE = Path(__file__).resolve().parents[1]
FP_S8 = {**FP, **FP_S90, **FP_S92}       # S9.0 TPS552892-Q1 land (s90_parts); S9.2 Kelvin land + 1.5 mm pad (s92_parts)
# TI LM2901 SOIC-14 (SLCS006Z Table 5-1): output pin -> (inverting, non-inverting) input pins of the same
# comparator, VCC 3, GND 12. Kept apart from the symbol and the circuit table (channel names vary by vendor).
LM2901_SO14 = {'outputs': {'2': ('4', '5'), '1': ('6', '7'), '14': ('8', '9'), '13': ('10', '11')}, 'VCC': '3', 'GND': '12'}
# TI TLV431 DBZ (SOT-23-3), SLVS139Z Table 4-1: pin -> function; symbol pin names K / REF / A.
TLV431_DBZ_TI = {'1': 'REF', '2': 'CATHODE', '3': 'ANODE'}
TLV431_SYMBOL_NAME = {'REF': 'REF', 'CATHODE': 'K', 'ANODE': 'A'}
# S8.5 TPS3808 roles (TI DBV pins from verify_design.TPS3808_DBV): U11 RESET is ARMED itself (U13 pin 4), no longer the
# clock of a flip-flop; U10 unchanged.
TPS3808_ROLES_S85 = {'U10': {'SENSE': ('R66', '1'), 'MR': ('SW1', '1'), 'RESET': ('U12', '1')},
                     'U11': {'SENSE': ('R70', '1'), 'MR': ('U10', 'RESET'), 'RESET': ('U13', '4'), 'CT': ('C49', '1')}}
# S8.5 V20_OK status-floor rule (same constants as s8_calcs, kept here independently): USB PD vSafe5V maximum and the
# required clearance to it and to the U5 turn-off minimum.
VSAFE5V_MAX = 5.5
V20_MARGIN_MIN_V = 2.0
# Guard screen inputs (S8.1). TLV431BI: 1.224-1.259 V over -40..85 C at IK 10 mA, |zKA| <= 0.4 ohm -> up to 3.6 mV
# lower at ~1 mA (SLVS139Z 5.7). LM2901B: VIO 5.5 mV and IB 50 nA (out of the pin) over -40..125 C (SLCS006Z 6.8).
# Divider resistors: 0.1 % + 25 ppm/C x 100 C. Converter load release, capacitor-study model, N = 16 cycles, low-C
# corner: +12V 1.033 V, -12V 0.484 V; S8.3 +5V full-load upstream-only screen rounded up to 0.261 V.
VREF_OV = (1.224 - 0.0036, 1.24, 1.259)
VIO_B, IB_B = 0.0055, 50e-9
R01_LO, R01_HI = 0.999 * 0.9975, 1.001 * 1.0025
RELEASE_N16_V = {'+12V': 1.172, '-12V': 0.484}      # S9.0: +12V = TPS552892-Q1 cell, 2.4 A, 869.6 kHz (calcs rail_release)
DOWNSTREAM_MAX_V = {'+12V': 16.0, '-12V': 16.0}    # 16 V module capacitors
VPD_RUN_MIN_V = 11.36               # lowest VPD with the converters running (S9.0 U5 turn-off band minimum, 11.55 V)
VPD_UNLOADED_MIN_V, VPD_LOADED_MIN_V = 14.25, 13.5     # S9.0: 15 V PD source -5 %; less the 0.75 V cable allowance
VIN_BANK = ('C6', 'C7', 'C24', 'C77', 'C78')     # 10u VIN ceramics: TPS552892 x 4 + LMR38020 C24 (S9.0 step 2)
VREF_TPS552892 = (1.188, 1.2, 1.212)             # SLVSGT7 6.5 (independent of s8_calcs)
OVP_TPS552892_MAX = 24.5                         # SLVSGT7 VOVP maximum, absolute
# S9.0 owner decision: no reverse-current blocking. Any ideal-diode controller / series FET on the rails is a regression.
REVERSE_BLOCKING_MPN_PREFIXES = ('LM7470', 'LM5050', 'LM5051', 'LTC4357', 'LTC4359', 'LTC4352', 'MAX4020', 'TPS2121',
                                 'TPS2116', 'AO4354', 'AO4406', 'AO4410', 'IRF7832', 'SI4410', 'AON7410', 'AON6354')
RAILS_S90 = {   # exact rail memberships (S9.0 step 2): a series element on a rail changes them
    '+12V': {('C34', '1'), ('C59', '1'), ('D2', '1'), ('J2', '9'), ('J2', '10'), ('J3', '9'), ('J3', '10'),
             ('R109', '4'), ('R75', '1'), ('R8', '2'), ('R93', '1'), ('TP24', '1')},       # S9.2: ISN on its own sense net
    '-12V': {('C25', '2'), ('C26', '2'), ('C27', '2'), ('C29', '1'), ('C30', '1'), ('C31', '1'), ('C32', '1'), ('C33', '1'),
             ('C36', '2'), ('C61', '2'), ('D4', '2'), ('J2', '1'), ('J2', '2'), ('J3', '1'), ('J3', '2'), ('R13', '1'),
             ('R15', '2'), ('R18', '2'), ('R82', '2'), ('R99', '2'), ('U4', '1'), ('U4', '9'), ('TP25', '1')},
    'P12_VOUT': {('C11', '1'), ('C12', '1'), ('C13', '1'), ('C14', '1'), ('C79', '1'), ('C80', '1'), ('C81', '1'),
                 ('R109', '1'), ('U2', '11'), ('D26', '1'), ('TP20', '1')},
    # S9.2 item 3: the Kelvin sense nets hold only the U2 sense pin, the R109 sense pad and the acceptance pad
    'P12_ISP': {('U2', '12'), ('R109', '2'), ('TP22', '1')}, 'P12_ISN': {('U2', '13'), ('R109', '3'), ('TP23', '1')}}

# Independently specified function pin -> net expectations of the critical parts (S8).
CRIT = {
    'U5': {1: 'MAIN_IN', 2: 'MAIN_IN', 3: 'MAIN_IN', 6: 'MAIN_IN', 7: 'MAIN_UV', 8: 'MAIN_OV', 9: 'GND', 10: 'MAIN_DVDT',
           11: 'MAIN_ILM', 12: 'GND', 13: 'RUN', 14: 'MAIN_IMON', 15: 'MAIN_OK', 16: 'MAIN_OK', 18: 'VIN', 19: 'VIN', 20: 'VIN',
           21: 'GND'},
    # S9.0 step 2: TPS552892-Q1 (pin numbers per TI SLVSGT7 Table 5-1; local nets checked by membership below)
    'U2': {1: 'MAIN_OK', 5: 'AGND_U2', 7: 'VIN', 9: 'GND', 11: 'P12_VOUT', 12: 'P12_ISP', 13: 'P12_ISN', 17: 'AGND_U2'},
    'R109': {1: 'P12_VOUT', 2: 'P12_ISP', 3: 'P12_ISN', 4: '+12V'}, 'R8': {2: '+12V'}, 'R9': {2: 'AGND_U2'},
    'R110': {2: 'AGND_U2'}, 'C83': {2: 'AGND_U2'},
    'C82': {2: 'GND'}, 'C8': {1: 'VIN', 2: 'GND'}, 'C81': {1: 'P12_VOUT', 2: 'GND'},     # S9.2: C82 ground on PGND
    'U4': {3: 'VIN', 1: '-12V', 9: '-12V'},
    'U9': {1: 'V3V3', 4: 'GND', 5: 'VPD', 8: 'VPD', 9: 'GND'},
    'U10': {1: 'RESET_N', 2: 'GND', 3: 'RESET_BTN_N', 5: 'POR_SENSE', 6: 'V3V3'},
    'U11': {1: 'ARMED', 2: 'GND', 3: 'RESET_N', 4: 'START_CT', 5: 'START_SENSE', 6: 'V3V3'},
    # S8.5: flip-flop A = STARTED (PRE_N = START_N, CLR_N = RESET_N, CLK low); B = FAULT (unchanged).
    'U12': {1: 'RESET_N', 2: 'V3V3', 3: 'GND', 4: 'START_N', 5: 'STARTED', 7: 'GND', 8: 'NOT_FAULT', 9: 'FAULT_LATCH',
            10: 'OV_N', 11: 'FAULT_CLK', 12: 'V3V3', 13: 'RESET_N', 14: 'V3V3'},
    # S8.5: gate 3 = TIMER_GO = RUN AND STARTED; gate 4 = MAIN_LED_OK = MAIN_OK AND V20_OK.
    'U13': {1: 'RESET_N', 2: 'NOT_FAULT', 3: 'RUN', 4: 'ARMED', 5: 'BAD_FILTERED', 6: 'FAULT_CLK', 7: 'GND',
            8: 'TIMER_GO', 9: 'RUN', 10: 'STARTED', 11: 'MAIN_LED_OK', 12: 'MAIN_OK', 13: 'V20_OK', 14: 'V3V3'},
    'R69': {1: 'TIMER_GO', 2: 'START_SENSE'}, 'R71': {1: 'V3V3', 2: 'ARMED'}, 'TP19': {1: 'STARTED'},
    # S8.5: gate 2 = START_N = NAND(MAIN_LED_OK, RUN) (spare in S8.4). S9.0: gate 1 input 4 (was P5_OK) tied high.
    'U14': {1: 'MAIN_LED_OK', 2: 'P12_OK', 4: 'V3V3', 5: 'N12_OK', 6: 'ANY_BAD', 7: 'GND', 8: 'START_N', 9: 'MAIN_LED_OK',
            10: 'RUN', 12: 'V3V3', 13: 'V3V3', 14: 'V3V3'},
    # S9.0: comparator out 2 (- 4 / + 5, the former +5V monitor) is a spare: - REF_GOOD, + GND, output open (NC_PINS).
    'U18': {1: 'P12_OK', 3: 'VPD', 4: 'REF_GOOD', 5: 'GND', 6: 'REF_GOOD', 7: 'MON_P12', 8: 'MON_N12',
            9: 'REF_GOOD', 10: 'REF_GOOD', 11: 'MON_20', 12: 'GND', 13: 'V20_OK', 14: 'N12_OK'},
    # S9.0: comparator out 1 (- 6 / + 7, the former +5V guard) is a second spare like out 13 (- 10 / + 11).
    'U20': {2: 'OV_N', 4: 'MON_OV12', 5: 'REF_OV', 6: 'REF_OV', 7: 'GND', 14: 'OV_N', 8: 'GND',
            9: 'MON_OVN', 10: 'REF_OV', 11: 'GND', 3: 'VPD', 12: 'GND'},
    'U21': {1: 'REF_OV', 2: 'REF_OV', 3: 'GND'}, 'R100': {1: 'V3V3', 2: 'REF_OV'}, 'C67': {1: 'REF_OV', 2: 'GND'},
    'D22': {1: 'GND', 2: 'MON_OVN', 3: 'MON_OVN'}, 'TP17': {1: 'REF_OV'},
    'R92': {1: 'VIN'}, 'R93': {1: '+12V', 2: 'MON_OV12'}, 'R94': {1: 'MON_OV12', 2: 'GND'},
    'R98': {1: 'REF_OV', 2: 'MON_OVN'}, 'R99': {1: 'MON_OVN', 2: '-12V'},
    'R35': {1: 'V3V3', 2: 'P12_OK'}, 'R62': {1: 'V3V3', 2: 'N12_OK'},
    'R97': {1: 'V3V3', 2: 'OV_N'},
    'C57': {1: 'VPD', 2: 'GND'}, 'C65': {1: 'VPD', 2: 'GND'},
    'SW1': {1: 'RESET_BTN_N', 3: 'RESET_BTN_N', 2: 'GND'}, 'D10': {1: 'MAIN_IN', 2: 'VPD'},
    'Q2': {1: 'PD_SENSE', 2: 'VPD_U1', 3: 'PD_BASE'}, 'Q1': {1: 'N_EN_BASE', 2: 'VPD'}, 'Q10': {1: 'RUN', 2: 'GND', 3: 'LED_RETURN'},
    'Q14': {1: 'RUN', 2: 'GND', 3: 'N_EN_RETURN'},
    'Q15': {1: 'MAIN_LED_OK', 2: 'N_EN_RETURN', 3: 'N_EN_SINK'},
    'R16': {1: 'N_EN_SINK', 2: 'N_EN_BASE'}, 'R112': {1: 'VPD', 2: 'N_EN_BASE'},
    'R113': {1: 'AGND_U2', 2: 'GND'}, 'R114': {1: 'UV_TRIM', 2: 'GND'}, 'R115': {1: 'N_EN_RETURN', 2: 'GND'},
    'R24': {1: 'MAIN_OV', 2: 'GND'},
    'R3': {1: 'MAIN_UV', 2: 'UV_TRIM'},
    'D24': {1: 'VIN', 2: 'GND'}, 'D25': {1: 'GND', 2: 'VIN', 3: 'VIN'},
    'D26': {1: 'P12_VOUT', 2: 'GND'},
    'D2': {1: '+12V', 2: 'GND'}, 'D4': {1: 'GND', 2: '-12V'},
}
# S9.2 item 1: TVS rows (Littelfuse SMBJ series datasheet table, 600 W 10/1000 us): VR, VBR min/max at 1 mA, VC at IPP,
# temperature coefficient of VBR. Independent of tools/s8_calcs.py.
D24_TABLE = {'SMBJ20A': {'VR': 20.0, 'VBR': (22.2, 24.5), 'VC': 32.4, 'IPP': 18.6, 'alpha_pct_C': 0.091},
             'SMBJ16A': {'VR': 16.0, 'VBR': (17.8, 19.7), 'VC': 26.0, 'IPP': 23.1, 'alpha_pct_C': 0.084}}
# S9.0: pins that must be no-connects (spare comparator outputs, the former +5V header pins, CV/GATE).
NC_PINS = {'U18': ('2',), 'U20': ('1', '13'), 'J2': ('11', '12', '13', '14', '15', '16'),
           'J3': ('11', '12', '13', '14', '15', '16'), 'U2': ('3', '4', '16')}      # S9.0: TPS552892 PG, CC, CDC open
HEADER = {**{n: 'GND' for n in range(3, 9)}, 1: '-12V', 2: '-12V', 9: '+12V', 10: '+12V'}
FORBIDDEN_MPN = {'LM5067MM-2/NOPB', 'FQD13N06LTM', 'LTV-354T', 'MVK50V47M6.3*8 6.3TP', 'MVK 35V100 M 6.3*8',
                 'TPS259470ARPWR', 'SMAJ5.0A', 'RT0603BRD0768KL', 'RT0603BRD0713KL', 'TNPW060337K0BEEA',   # S9.0: +5V-only parts
                 'TPS62933FDRLR'}                                    # S9.0 step 2: the TPS62933F buck is gone (U2 and U3)


def check_tps3808_s85(root, comps, pins):
    """Native symbol pin names, instance pin functions and S8.5 roles against TI's DBV table (verify_design)."""
    plain = lambda name: name[:-2] if name.endswith('_N') else name   # noqa: E731
    lib = {p.get('part'): {x.get('num'): plain(x.get('name')) for x in p.findall('pins/pin')}
           for p in root.findall('libparts/libpart')}
    assert lib.get('TPS3808G01') == TPS3808_DBV, ('TPS3808G01 symbol pin identity differs from TI DBV', lib.get('TPS3808G01'))
    role = {name: num for num, name in TPS3808_DBV.items()}
    for ref, roles in TPS3808_ROLES_S85.items():
        assert comps[ref].findtext('fields/field[@name="MPN"]') == 'TPS3808G01DBVR', (ref, 'TPS3808 MPN')
        for node in root.iter('node'):
            if node.get('ref') == ref:
                num = node.get('pin'); func = node.get('pinfunction').removesuffix('_' + num)
                assert plain(func) == TPS3808_DBV[num], (ref, num, func, 'TPS3808 pin function')
        for name, (other, opin) in roles.items():
            opin = role.get(opin, opin) if other in TPS3808_ROLES_S85 else opin
            assert pins[(ref, role[name])] == pins[(other, opin)], (ref, name, 'TPS3808 role not on', other, opin)


# ---------------------------------------------------------------------------------------------------------------------
# Arming timeline simulation (S8.5, item B). The LOGIC is built from the native netlist: the HC08 / HC20 gates, both
# HC74 flip-flops (asynchronous PRE/CLR, rising-edge clock), the U11 TPS3808 delay (sense from the R69 divider top, MR)
# and the R72/C51 + U15 bad-status filter. The PLANT (VPD, U5 UVLO/PGOOD deglitch, converters + U23 ramp, rails, guard,
# rail status) is a scenario model with datasheet timings; it reads RUN and drives RESET_N, OV_N, MAIN_OK, V20_OK and the
# rail status (S9.0: P12_OK and N12_OK; no +5V status, no U23 FLT).
# ---------------------------------------------------------------------------------------------------------------------
PLANT = dict(dt_ms=0.1, t_por_ms=12.0,                 # TPS3808 open-CT RESET delay minimum (12/20/28 ms)
             t_u5_on_to_pgood_ms=12.0 + 11.5,          # U5 dVdt ramp (~12 ms) + tPGOODR 11.5 ms typ (TPS1663)
             t_pgood_fall_ms=10.0,                     # tPGOODF 10 ms typ: PGOOD stays high this long after the FET is off
             t_rails_ms=120.0,                         # after MAIN_OK, conservative: S9.0 budget 66.6 ms (U5 ramp, PGOOD,
                                                       # TPS552892 tSS + rack at the R109 limit, LMR38020 4 + 18 ms)
             t_rail_decay_ms=1.0,                      # rails fall below their U18 thresholds after VIN is lost
             t_filter_ms=0.75,                         # R72/C51 10k/100n to the U15 Schmitt VT+ (0.6-0.9 ms)
             u5_on_V=12.977, u5_off_V=12.193,            # S9.0 U5 UVLO corners at their HIGH end (worst for starting/running)
             u5_status_valid_V=4.95,                   # VPD below 4.5 V + D10 0.45 V: U5 FLT/PGOOD unspecified -> MAIN_OK
                                                       # floats high through R63 (S8.4 Opus review, major 1)
             vpd_5v_phase=4.75,                        # vSafe5V minimum: the PD 5 V phase at its lowest
             vpd_unloaded=14.25, vpd_loaded=13.5)        # S9.0: 15 V PDO -5 %, less the 0.75 V cable allowance
TD_CORNERS_S = (0.31, 0.88)                           # U11 100n: 0.57 s typ, 0.31-0.88 s screen
SHEETS = 5                                            # S9.0: five pages (the +5V converter page is gone)


class ArmingLogic:
    """Event-driven logic model from native pin nets (refs U10-U15, R69/R72 and the HC74/HC08/HC20/TPS3808 pinouts)."""

    def __init__(self, pins, netids_by_name):
        self.n = lambda ref, pin: pins[(ref, str(pin))]       # noqa: E731
        self.id = netids_by_name
        n = self.n
        self.and2 = [(n('U13', a), n('U13', b), n('U13', y)) for a, b, y in ((1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11))]
        self.nand4 = [([n('U14', p) for p in ins], n('U14', y)) for ins, y in (((1, 2, 4, 5), 6), ((9, 10, 12, 13), 8))]
        self.ffs = [dict(clr=n('U12', c), d=n('U12', d), clk=n('U12', k), pre=n('U12', p), q=n('U12', q), qn=n('U12', qn))
                    for c, d, k, p, q, qn in ((1, 2, 3, 4, 5, 6), (13, 12, 11, 10, 9, 8))]
        self.timer = dict(sense=n('R69', 1), mr=n('U11', 3), out=n('U11', 1))
        self.filt = dict(src=n('R72', 1), out=n('U15', 4))
        self.const = {self.id['V3V3']: True, self.id['GND']: False}

    def run(self, plant_step, t_end_ms, t_d_s, dt=PLANT['dt_ms']):
        s = dict(self.const)
        qs = [False, False]                     # flip-flop states (A, B)
        prev_clk = [False, False]
        t_ok, t_bad, t_good = 0.0, 0.0, 0.0
        filt = False
        trace = []
        pst = {}
        for k in range(int(t_end_ms / dt)):
            t = k * dt
            plant_step(t, s, pst)               # writes the plant-driven nets
            if not s.get(self.id['V3V3'], False):
                qs=[False,False]; prev_clk=[False,False]; t_ok=t_bad=t_good=0.; filt=False
                for _,_,y in self.and2: s[y]=False
                for _,y in self.nand4: s[y]=False
                for ff in self.ffs: s[ff['q']]=False; s[ff['qn']]=False
                s[self.timer['out']]=False; s[self.filt['out']]=False
            for _ in range(12 if s.get(self.id['V3V3'],False) else 0):                 # settle delta cycles (gates, flip-flops, timer) to a fixed point
                before = dict(s)
                for a, b, y in self.and2:
                    s[y] = bool(s.get(a, False) and s.get(b, False))
                for ins, y in self.nand4:
                    s[y] = not all(s.get(x, False) for x in ins)
                for i, f in enumerate(self.ffs):
                    pre, clr = s.get(f['pre'], True), s.get(f['clr'], True)
                    clk = s.get(f['clk'], False)
                    if not pre and not clr:
                        q, qn = True, True
                    elif not pre:
                        qs[i] = True; q, qn = True, False
                    elif not clr:
                        qs[i] = False; q, qn = False, True
                    else:
                        if clk and not prev_clk[i]:
                            qs[i] = bool(s.get(f['d'], False))
                        q, qn = qs[i], not qs[i]
                    if f['q'] not in self.const:
                        s[f['q']] = q
                    if f['qn'] not in self.const:
                        s[f['qn']] = qn
                tm = self.timer
                cond = s.get(tm['sense'], False) and s.get(tm['mr'], False)
                s[tm['out']] = cond and t_ok >= t_d_s * 1e3
                s[self.filt['out']] = filt
                if s == before:
                    break
            for i, f in enumerate(self.ffs):
                prev_clk[i] = s.get(f['clk'], False)
            t_ok = t_ok + dt if (s.get(self.timer['sense'], False) and s.get(self.timer['mr'], False)) else 0.0
            if s.get(self.filt['src'], False):
                t_bad += dt; t_good = 0.0
            else:
                t_good += dt; t_bad = 0.0
            if not filt and t_bad >= PLANT['t_filter_ms']:
                filt = True
            elif filt and t_good >= PLANT['t_filter_ms']:
                filt = False
            trace.append((t, {k: s.get(self.id[k]) for k in ('RUN', 'ARMED', 'FAULT_LATCH', 'MAIN_OK', 'MAIN_LED_OK',
                                                                'RESET_N', 'OV_N', 'P12_OK', 'N12_OK', 'V3V3', 'STARTED')},
                          dict(pst)))
        return trace


def _plant(netids, scenario, v20_V):
    """Scenario plant: returns plant_step(t, s, pst). pst carries the U5/PGOOD/rail state and 'enabled' (converters
    enabled = RUN AND U5 FET on AND EN (= MAIN_OK) high)."""
    P = PLANT
    ev = scenario
    dt = P['dt_ms']
    t_pgf = ev.get('t_pgood_fall_ms', P['t_pgood_fall_ms'])

    def step(t, s, pst):
        if not pst:
            pst.update(u5=False, t_u5=None, retry_off_until=-1.0, raw_on=0.0, raw_off=1e9, pg=False, enabled=False,
                       first_enable=None, t_en=None, t_dis=-1e9, rails=False, powered=True, power_since=0., epochs=1, charge_J=0.)
        vpd = ev['vpd'](t, pst['enabled'])          # S9.0: the source sags to its loaded value only while loaded
        powered = not any(a<=t<b for a,b in ev.get('power_loss',()))
        if powered and not pst['powered']:
            pst['power_since']=t; pst['epochs']+=1
        if not powered: vpd=0.; pst['u5']=False; pst['pg']=False; pst['raw_on']=0.; pst['raw_off']=1e9; pst['charge_J']=0.
        pst['powered']=powered
        s[netids['V3V3']]=powered
        reset = powered and t-pst['power_since'] >= P['t_por_ms'] and not any(a <= t < b for a, b in ev.get('reset', ()))
        run = s.get(netids['RUN'], False)
        # U5: UVLO with hysteresis, SHDN = RUN, optional auto-retry overload chatter after the first enable
        on_req = powered and run and t >= pst['retry_off_until']
        if pst['u5'] and (not on_req or vpd < P['u5_off_V']):
            pst['u5'] = False
        elif not pst['u5'] and on_req and vpd >= P['u5_on_V']:
            pst['u5'] = True; pst['t_u5'] = t
        chatter = ev.get('chatter')
        if chatter and pst['u5'] and pst['first_enable'] is not None and t - pst['t_u5'] >= chatter[0]:
            pst['u5'] = False; pst['retry_off_until'] = t + chatter[1]
        # PGOOD: FET enhanced after the dVdt ramp; tPGOODR rising / tPGOODF falling deglitch (a short off is filtered)
        raw = pst['u5'] and t - pst['t_u5'] >= 12.0
        pst['raw_on'], pst['raw_off'] = (pst['raw_on'] + dt, 0.0) if raw else (0.0, pst['raw_off'] + dt)
        if not pst['pg'] and pst['raw_on'] >= 11.5:
            pst['pg'] = True
        elif pst['pg'] and pst['raw_off'] >= t_pgf:
            pst['pg'] = False
        main_ok = (pst['pg'] if vpd >= P['u5_status_valid_V'] else True) if powered else False   # undefined U5 status floats high (R63)
        enabled = run and pst['u5'] and main_ok
        if enabled and pst['first_enable'] is None:
            pst['first_enable'] = t
        pst['enabled'] = enabled
        # Rails: good after the soft starts (+ U23 ramp) while enabled; lost t_rail_decay after the enable/VIN goes away
        if enabled:
            pst['t_en'] = t if pst['t_en'] is None else pst['t_en']
            pst['t_dis'] = None
        else:
            pst['t_dis'] = t if pst['t_dis'] is None else pst['t_dis']
            if t - pst['t_dis'] >= P['t_rail_decay_ms']:
                pst['t_en'] = None
        rails = pst['t_en'] is not None and t - pst['t_en'] >= P['t_rails_ms']

        if ev.get('bus_held') is not None and t >= ev['bus_held']:
            rails = True
        if any(a <= t < b for a, b in ev.get('rail_fault', ())):
            rails = False
        pst['rails'] = rails
        ov = any(a <= t < b for a, b in ev.get('ov', ()))
        s[netids['RESET_N']] = reset
        s[netids['OV_N']] = not ov
        s[netids['MAIN_OK']] = main_ok
        s[netids['V20_OK']] = vpd > v20_V
        for k in ('P12_OK', 'N12_OK'):      # a bus-side event on one rail only ('bus_lost': (rail, start, end))
            lost = any(r == k and a <= t < b for r, a, b in ev.get('bus_lost', ()))
            s[netids[k]] = rails and not lost
    return step


def _plant_physical(netids, ev, v20_V, phys, byname):
    """S9.2 item 4: 3 A source scenarios on the netlist-derived input plant (tools/s92_netlist.PhysicalStartup). The
    source current limit, U5 UVLO band, R109 CC limit (from the ISP/ISN shunt connectivity), the banks and the rail
    monitor thresholds all come from the design under test; U5 PGOOD deglitch, POR, power epochs as in _plant. The
    converters are enabled by the logic nets the netlist wires to them: U2 EN = MAIN_OK, U4 = RUN AND MAIN_LED_OK."""
    import s92_netlist
    P = PLANT
    dt = P['dt_ms']
    t_pgf = ev.get('t_pgood_fall_ms', P['t_pgood_fall_ms'])

    def step(t, s, pst):
        if not pst:
            pst.update(sim=s92_netlist.PhysicalStartup(phys['params'], phys['eff'], **ev['physical']),
                       pg=False, raw_on=0.0, raw_off=1e9, enabled=False, first_enable=None, t_en=None, powered=True,
                       power_since=0.0, epochs=1, dropouts_after_enable=0, max_input_A=0.0)
        powered = not any(a <= t < b for a, b in ev.get('power_loss', ()))
        if powered and not pst['powered']:
            pst['power_since'] = t
            pst['epochs'] += 1
        pst['powered'] = powered
        s[netids['V3V3']] = powered
        reset = powered and t - pst['power_since'] >= P['t_por_ms'] and not any(a <= t < b for a, b in ev.get('reset', ()))
        run = bool(s.get(netids['RUN'], False)) and powered
        # enables read from the nets the DESIGN wires to the pins: U5 SHDN, U2 EN/UVLO and the U4 enable AND-chain gates
        net_on = lambda short: powered and bool(s.get(byname.get(short), short == 'V3V3'))      # noqa: E731
        u5_on_cmd = net_on(phys['params']['U5_SHDN_net'])
        en12 = net_on(phys['params']['U2_EN_net'])
        enn = all(net_on(g) for g in phys['U4_gates'])
        before = pst['sim'].dropouts
        r = pst['sim'].step(t, dt, powered, ev['vpd'](t, False), u5_on_cmd, en12, enn)
        if s.get(netids['FAULT_LATCH']) and pst.get('t_fault') is None:
            pst['t_fault'] = t
        if pst.get('t_fault') is not None and t - pst['t_fault'] >= 2.0:
            pst['input_after_fault_A'] = max(pst.get('input_after_fault_A', 0.0), r['i_src'])
        if pst['first_enable'] is not None and pst['sim'].dropouts > before:
            pst['dropouts_after_enable'] += pst['sim'].dropouts - before
        raw = r['u5'] and r['fet_full']
        pst['raw_on'], pst['raw_off'] = (pst['raw_on'] + dt, 0.0) if raw else (0.0, pst['raw_off'] + dt)
        if not pst['pg'] and pst['raw_on'] >= 11.5:
            pst['pg'] = True
        elif pst['pg'] and pst['raw_off'] >= t_pgf:
            pst['pg'] = False
        if not powered:
            pst['pg'] = False
        main_ok = (pst['pg'] if r['vpd'] >= P['u5_status_valid_V'] else True) if powered else False
        enabled = u5_on_cmd and r['u5'] and main_ok
        if enabled and pst['first_enable'] is None:
            pst['first_enable'] = t
        pst['enabled'] = enabled
        pst['max_input_A'] = max(pst['max_input_A'], r['i_src'])
        pst.update(actual_input_A=r['i_src'], v12=r['v12'], vn12=r['vn12'], vin=r['vin'], u5_dropouts=pst['sim'].dropouts,
                   source_limited=r['i_src'] >= ev['physical'].get('source_A', 3.0) - 1e-9,
                   peak_demand_A=pst['sim'].peak_demand_A, over_3A_ms=pst['sim'].t_over_A)
        s[netids['RESET_N']] = reset
        s[netids['OV_N']] = True
        s[netids['MAIN_OK']] = main_ok
        s[netids['V20_OK']] = r['vpd'] > v20_V
        rails12 = r['v12'] >= phys['P12_OK_V'] and not any(a <= t < b for a, b in ev.get('rail_fault', ()))
        s[netids['P12_OK']] = rails12
        s[netids['N12_OK']] = r['vn12'] >= phys['N12_OK_V']
    return step


def _vpd(phase_ms, sag=None, loaded_after=None):
    """VPD(t, loaded): vSafe5V phase, ramp to the unloaded PD voltage, then the loaded minimum while the converters
    draw (S9.0: at the 15 V input the loaded minimum 13.5 V is below the U5 turn-on maximum 13.98 V, so a source that is
    unloaded again after U5 opens must return to its 14.25 V unloaded minimum; S8.5 at 20 V never needed the distinction)."""
    P = PLANT

    def f(t, loaded=True):
        if sag and sag[0] <= t < sag[1]:
            return sag[2]
        if t < phase_ms:
            return P['vpd_5v_phase']
        if t < phase_ms + 30.0:
            return P['vpd_5v_phase'] + (P['vpd_unloaded'] - P['vpd_5v_phase']) * (t - phase_ms) / 30.0
        if loaded_after is not None and t < loaded_after:
            return P['vpd_unloaded']
        return P['vpd_loaded'] if loaded else P['vpd_unloaded']
    return f


SCENARIOS = {
    'cold_start_worst_loaded_15V': dict(vpd=_vpd(300.0, loaded_after=380.0), t_end=1700.0,
                                        why='15 V PD source at -5 % (14.25 V unloaded, U5 turns on at its 13.98 V maximum), '
                                            '13.5 V loaded after the start; MAIN_OK floats high during the 5 V phase'),
    'slow_PD_contract_2s5': dict(vpd=_vpd(2500.0, loaded_after=2580.0), t_end=4000.0,
                                 why='5 V phase longer than the qualification window, U5 status floating high (S8.4 armed '
                                     'here and latched off before the PD voltage arrived)'),
    'brownout_after_ARMED': dict(vpd=_vpd(300.0, sag=(1500.0, 1550.0, 10.5)), t_end=3000.0, reset=((1900.0, 1915.0),),
                                 why='VPD sags to 10.5 V (below the 11.55 V U5 turn-off minimum, above the 9.27 V V20_OK '
                                     'maximum) for 50 ms after ARMED (U5 off), recovers; RESET pressed later'),
    'brownout_inside_window': dict(vpd=_vpd(300.0, sag=(450.0, 500.0, 10.5)), t_end=1800.0,
                                   why='VPD sags to 10.5 V for 50 ms right after the first enable; the window is NOT restarted'),
    'input_overload_chatter': dict(vpd=_vpd(300.0), t_end=1800.0, chatter=(30.0, 20.0),
                                   why='U5 current limit / auto-retry: on 30 ms, off 20 ms, forever (S8.4: timer restarted '
                                       'every cycle, never armed)'),
    'hot_plug_live_bus': dict(vpd=_vpd(300.0), t_end=1700.0, bus_held=0.0,
                              why='outputs plugged into a bus another supply already holds inside the monitor windows: '
                                  'the rail monitors read good from 0 ms; nothing else reaches the logic'),
    'load_release_after_ARMED': dict(vpd=_vpd(300.0), t_end=1700.0,
                                     why='+/-12V load released after ARMED: the release peak stays below the U20 guard '
                                         'minimum (calcs ov_guard) and the rails stay above their monitor thresholds, so no '
                                         'logic input changes (the run must stay armed without a FAULT)'),
    'load_release_inside_window': dict(vpd=_vpd(300.0), t_end=1700.0,
                                       why='the same +/-12V load release during the qualification window'),
    'ov_guard_before_ARMED': dict(vpd=_vpd(300.0), t_end=1200.0, ov=((420.0, 421.0),),
                                  why='+12V or -12V beyond the U20 guard 60 ms after the first enable: OV_N low for 1 ms'),
    'short_RESET_while_running': dict(vpd=_vpd(300.0), t_end=2600.0, reset=((1500.0, 1512.0),), t_pgood_fall_ms=13.0,
                                      why='RESET pulse of the 12 ms POR minimum while PGOOD (13 ms falling-deglitch '
                                          'screen) is still high when RESET releases'),
}

SCENARIOS.update({
 'source_limit_3A':dict(vpd=_vpd(300.),t_end=1500.,physical=dict(i12=2.4,in12=0.33,source_A=3.0,r_cable=0.25,rack_F=0.44e-3),
    why='S1 condition on the netlist-derived plant: strict 3.00 A source at 14.25 V + 0.25 ohm, published 33 W load (2.4 A / 0.33 A), 0.44 mF per rail; must end fail-safe (single-attempt armed start, or FAULT latched with RUN low), never armed with a bad rail'),
 'source_3A_no_load_no_rack':dict(vpd=_vpd(300.),t_end=1500.,physical=dict(i12=0.0,in12=0.0,source_A=3.0,r_cable=0.25,rack_F=0.0),
    why='Minimal start on the same plant: strict 3.00 A source, no load, no rack: must start in ONE attempt, no U5 dropout, input <= 3 A'),
 'power_reset_rearm_persistent_short':dict(vpd=_vpd(300.),t_end=3600.,power_loss=((1600.,1750.),),rail_fault=((0.,4000.),),
    why='Persistent short; fault must latch in EACH of two power epochs. V3V3 fully lost, POR re-arms legitimately; original failed epoch is retained'),
 'repeated_power_reset_rejected':dict(vpd=_vpd(300.),t_end=2600.,power_loss=tuple((450.+200*k,500.+200*k) for k in range(10)),rail_fault=((0.,3000.),),
    why='Adversarial source resets before ARMED; volatile STARTED clears. Logic semantics expected, but external qualification MUST reject repeated resets, never report success')})


def _check_timeline(name, trace, t_d_s):
    """The four S8.5 arming requirements on one simulated timeline; returns (summary, violations)."""
    dt = PLANT['dt_ms']
    v = []
    arm_times, fault_times, reset_edges = [], [], []
    prev = None
    for t, s, p in trace:
        if prev is not None:
            if s['ARMED'] and not prev['ARMED']:
                arm_times.append(t)
            if s['FAULT_LATCH'] and not prev['FAULT_LATCH']:
                fault_times.append(t)
            if s['RESET_N'] and not prev['RESET_N']:
                reset_edges.append(t)
        prev = s
    # first converter enable after each RESET release (the plant restarts U5 after RESET)
    enables = []
    last_reset = -1.0
    for t, s, p in trace:
        if s['RESET_N'] is False:
            last_reset = t
        if p.get('enabled') and (not enables or enables[-1][0] < last_reset):
            enables.append((last_reset, t))
    t_win = t_d_s * 1e3
    # R3: no early arming - every ARMED rise follows a converter enable of the same RESET interval by >= t_d - 2 dt
    for ta in arm_times:
        en = [te for tr, te in enables if tr < ta and te <= ta]
        if not en or ta - en[-1] < t_win - 2 * dt:
            v.append(f'{name}: R3 ARMED at {ta:.1f} ms before/without a converter enable (enable {en[-1] if en else None})')
    # R1/R2: bounded, non-restartable arming - converters enabled and unarmed only within t_d of the first enable
    for t, s, p in trace:
        if p.get('enabled') and not s['ARMED'] and not s['FAULT_LATCH']:
            en = [te for tr, te in enables if te <= t]
            if en and t - en[-1] > t_win + 2 * dt:
                v.append(f'{name}: R1/R2 converters enabled and NOT armed {t - en[-1]:.1f} ms after the first enable')
                break
    # R2: ARMED rises at most once per RESET interval
    for a, b in zip([0.0] + reset_edges, reset_edges + [1e12]):
        if len([x for x in arm_times if a <= x < b]) > 1:
            v.append(f'{name}: R2 ARMED rose more than once between RESET releases')
    # R4: after ARMED any bad status longer than the filter latches FAULT; FAULT keeps RUN low until RESET
    bad_since = None
    for t, s, p in trace:
        bad = not (s['MAIN_LED_OK'] and s['P12_OK'] and s['N12_OK'])
        if s['ARMED'] and bad and s['RESET_N']:
            bad_since = t if bad_since is None else bad_since
            if t - bad_since > PLANT['t_filter_ms'] + 3 * dt and not s['FAULT_LATCH']:
                v.append(f'{name}: R4 bad status {t - bad_since:.1f} ms after ARMED without FAULT')
                break
        else:
            bad_since = None
        if s['FAULT_LATCH'] and s['RUN']:
            v.append(f'{name}: R4 RUN high while FAULT is latched')
            break
        if not s['OV_N'] and s['RUN'] and s['RESET_N']:
            v.append(f'{name}: R4 OV_N low without FAULT/RUN low')
            break
    summary = dict(first_enable_ms=[round(te, 1) for _, te in enables], ARMED_ms=[round(x, 1) for x in arm_times],
                   FAULT_ms=[round(x, 1) for x in fault_times], RESET_release_ms=[round(x, 1) for x in reset_edges],
                   ends_running=bool(trace[-1][1]['RUN']), ends_armed=bool(trace[-1][1]['ARMED']),
                   ends_faulted=bool(trace[-1][1]['FAULT_LATCH']))
    summary['power_epochs']=trace[-1][2].get('epochs',1)
    summary['max_input_A']=round(max(p.get('actual_input_A',0.) for _,_,p in trace), 4)
    summary['source_limit_observed']=any(p.get('source_limited',False) for _,_,p in trace)
    last = trace[-1][2]
    if 'u5_dropouts' in last:                                  # S9.2 physical 3 A plant records
        summary.update(u5_dropouts=last['u5_dropouts'], u5_dropouts_after_first_enable=last['dropouts_after_enable'],
                       peak_demand_A=round(last['peak_demand_A'], 3), demand_over_3A_ms=round(last['over_3A_ms'], 2),
                       final_rails_V=[round(last['v12'], 2), round(last['vn12'], 2)],
                       input_after_fault_A=round(last.get('input_after_fault_A', 0.0), 3))
    return summary, v


def arming_timelines(pins, nets, v20_band_V, phys=None):
    """Run every scenario at both U11 delay corners and both V20_OK band corners; returns (results, violations).
    phys: netlist-derived plant inputs (s92_netlist.plant_inputs) for the physical 3 A source scenarios."""
    netids = {}
    for name in ('RUN', 'ARMED', 'FAULT_LATCH', 'MAIN_OK', 'MAIN_LED_OK', 'RESET_N', 'OV_N', 'P12_OK', 'N12_OK',
                 'V20_OK', 'V3V3', 'GND', 'STARTED'):
        match = [k for k in nets if k.split('/')[-1] == name]
        assert len(match) == 1, (name, match)
        netids[name] = match[0]
    logic = ArmingLogic(pins, netids)
    results, violations = {}, []
    for name, sc in SCENARIOS.items():
        for t_d in TD_CORNERS_S:
            for v20 in (v20_band_V[0], v20_band_V[2]):
                if sc.get('physical'):
                    assert phys is not None, 'physical scenario needs the netlist-derived plant inputs'
                    plant = _plant_physical(netids, sc, v20, phys, {k.split('/')[-1]: k for k in nets})
                else:
                    plant = _plant(netids, sc, v20)
                trace = logic.run(plant, sc['t_end'], t_d)
                summary, v = _check_timeline(name, trace, t_d)
                violations += [f'{x} (t_d {t_d} s, V20_OK {v20:.2f} V)' for x in v]
                results.setdefault(name, {'why': sc['why']})[f't_d_{t_d}s_V20_{v20:.2f}V'] = summary
    # Scenario expectations beyond the four rules (fail-safe outcomes the doc states).
    for key, r in results['brownout_after_ARMED'].items():
        if key.startswith('t_d') and not (r['FAULT_ms'] and r['FAULT_ms'][0] >= 1500.0 and r['ends_running']
                                          and len(r['ARMED_ms']) == 2):
            violations.append(f'brownout_after_ARMED: expected FAULT at the sag, recovery only after RESET ({key}: {r})')
    for key, r in results['input_overload_chatter'].items():
        if key.startswith('t_d') and not (r['FAULT_ms'] and r['ends_faulted']):
            violations.append(f'input_overload_chatter: overload never latched ({key}: {r})')
    for name in ('cold_start_worst_loaded_15V', 'slow_PD_contract_2s5', 'brownout_inside_window', 'hot_plug_live_bus',
                 'load_release_after_ARMED', 'load_release_inside_window', 'short_RESET_while_running'):
        for key, r in results[name].items():
            if key.startswith('t_d') and (r['FAULT_ms'] or not r['ends_armed']):
                violations.append(f'{name}: expected armed and running without FAULT ({key}: {r})')
    for key, r in results['ov_guard_before_ARMED'].items():
        if key.startswith('t_d') and not (r['FAULT_ms'] and r['FAULT_ms'][0] < 430.0 and not r['ends_running']):
            violations.append(f'ov_guard_before_ARMED: OV_N must latch FAULT before ARMED ({key}: {r})')
    # S9.2 item 4: the 3 A source cases on the netlist-derived plant. Strict 3 A at the published load + rack: the outcome
    # must be fail-safe - a clean single-attempt start (armed, running, no U5 dropout after the first enable) OR FAULT
    # latched with RUN low at the end; armed-and-running after hidden U5 retries is a FAIL (the S1 rule). Minimal case:
    # a clean single attempt is REQUIRED (the design must start from a strict 3 A source with nothing connected).
    for key, r in results['source_limit_3A'].items():
        if key == 'why':
            continue
        clean = r['ends_armed'] and r['ends_running'] and not r['FAULT_ms'] and r['u5_dropouts_after_first_enable'] == 0
        safe_fault = r['ends_faulted'] and not r['ends_running'] and r['input_after_fault_A'] <= 0.05
        if r['max_input_A'] > 3.0 + 1e-9 or not (clean or safe_fault):
            violations.append(f'source_limit_3A: not fail-safe ({key}: {r})')
    for key, r in results['source_3A_no_load_no_rack'].items():
        if key != 'why' and not (r['ends_armed'] and r['ends_running'] and not r['FAULT_ms']
                                 and r['u5_dropouts_after_first_enable'] == 0 and r['max_input_A'] <= 3.0 + 1e-9):
            violations.append(f'source_3A_no_load_no_rack: no clean single-attempt start ({key}: {r})')
    for key,r in results['power_reset_rearm_persistent_short'].items():
        if key!='why' and not (r['power_epochs']==2 and len(r['FAULT_ms'])==2 and r['ends_faulted']):
            violations.append(f'power_reset_rearm_persistent_short: {key}: {r}')
    return results, violations


def d24_coordination(design):
    """S9.2 item 1 on a netlist view (tools/s92_netlist.Design): the D24 datasheet row picked by its MPN against the U5
    OVP band derived from the divider connectivity. Rules: VR >= 1.15 x 16.5 V; OVP maximum below VR and below VBR minimum
    at 0 C (OVP acts first); VC below the U2 42 V absolute maximum and VC + 14.02 V (-12V guard) below the 50 V C25/C26.
    Returns (row, VBR minimum at 0 C, checks)."""
    import s92_netlist
    tvs = D24_TABLE[design.mpn('D24')]
    ovp_max = s92_netlist.startup_params(design)['OVP_rise_V'][2]
    vbr_cold = tvs['VBR'][0] * (1 - tvs['alpha_pct_C'] / 100 * 25)
    return tvs, vbr_cold, {'standoff_ge_1p15_x_16p5': tvs['VR'] >= 1.15 * 16.5, 'OVP_max_below_standoff': ovp_max < tvs['VR'],
                           'VBR_min_0C_above_OVP_max': vbr_cold > ovp_max, 'VC_below_U2_42V': tvs['VC'] < 42.0,
                           'VC_plus_guard_below_50V_C25_C26': tvs['VC'] + 14.02 < 50.0}


def arming_check(netlist, v20_band_V=(7.67, 8.44, 9.27)):      # S9.0 V20_OK band (R83 100k)
    """Arming timelines of any native netlist (test_s8 runs it on the S8.4 wiring as the regression control)."""
    import s92_netlist
    _, _, nets, pins = load_xml(netlist)
    return arming_timelines(pins, nets, v20_band_V, s92_netlist.plant_inputs(s92_netlist.Design.from_xml(netlist)))


def u5_thresholds(value):
    """U5 TPS16630 UVLO referred to VPD: TI 1.176/1.2/1.224 V rising, 1.09/1.122/1.15 V falling, +/-150 nA pin leakage
    through R2; R2/R3 at 1 % + 1 % TCR (independent of s8_calcs.u5_window)."""
    lo, hi = .999*.9975, 1.001*1.0025
    bl, bh = .99*.99, 1.01*1.01
    leak = 150e-9 * value('R2') * hi
    rbot_min = value('R3')*lo + value('R114')*bl
    rbot_max = value('R3')*hi + value('R114')*bh
    def band(vmin, vtyp, vmax):
        return [vmin*(1+value('R2')*lo/rbot_max)-leak,
                vtyp*(1+value('R2')/(value('R3')+value('R114'))),
                vmax*(1+value('R2')*hi/rbot_min)+leak]
    return band(1.176,1.2,1.224),band(1.09,1.122,1.15)


def v20_band(value):
    """V20_OK trip over V3V3 +-2 % (TPS7A16), R73/R74 and R83/R84 at 1 % + 1 % TCR, LM2901B VIO 5.5 mV and IB 0-50 nA
    out of the pin (lowers the trip by up to IB x R83: minimum corner only)."""
    lo, hi = .99 * .99, 1.01 * 1.01

    def ref(v3, a, b, e):
        return v3 * value('R74') * b / (value('R73') * a + value('R74') * b) + e
    return [ref(3.3 * .98, hi, lo, -VIO_B) * (1 + value('R83') * lo / (value('R84') * hi)) - IB_B * value('R83'),
            ref(3.3, 1, 1, 0) * (1 + value('R83') / value('R84')),
            ref(3.3 * 1.02, lo, hi, VIO_B) * (1 + value('R83') * hi / (value('R84') * lo))]


def enable_record():
    import s8_calcs, s91_analysis
    return s91_analysis.enable(s8_calcs.table()[1])


def startup_qualification_record():
    import s8_calcs, s91_analysis
    p, v = s8_calcs.table(); _, eff = s8_calcs.banks(p)
    return s91_analysis.qualification(v, eff, s8_calcs.p12(v))


def residual_record():
    import s8_calcs
    p,v=s8_calcs.table(); _,eff=s8_calcs.banks(p)
    # thresholds calculated directly, not copied from docs/calcs.json.
    release={r:{'N=16':[0,RELEASE_N16_V[r]], 'vo_hi_V':0} for r in ('+12V','-12V')}
    # ov_guard needs only peak increments; use a current circuit-derived release screen below.
    op=s8_calcs.p12(v)
    release['+12V']['vo_hi_V']=op['setpoint_V'][2]
    release['-12V']['vo_hi_V']=12.624
    release['+12V_from_R109_limit_max']={'N=16':[0,1.447]}
    return s8_calcs.residuals(v,eff,s8_calcs.ov_guard(v,release))


def holes_in_pads(f):
    """Plated holes of a parsed footprint whose centre lies inside the copper of another pad of the same footprint
    (exposed-pad thermal holes); a THT pin's own hole in its own pad does not count. Axis-aligned pad rectangles."""
    pads = nodes(f, 'pad')
    out = []
    for h in pads:
        if h[2] not in ('thru_hole', 'np_thru_hole'):
            continue
        hx, hy = map(float, one(h, 'at')[1:3])
        for q in pads:
            if q is h or not any(str(l).endswith('Cu') for l in one(q, 'layers')[1:]):
                continue
            (qx, qy), (qw, qh) = map(float, one(q, 'at')[1:3]), map(float, one(q, 'size')[1:3])
            if abs(hx - qx) <= qw / 2 and abs(hy - qy) <= qh / 2:
                out.append(f'{h[1]}@({hx:g},{hy:g}) in pad {q[1]}')
                break
    return out


def via_policy_record(footprints_checked):
    """S9.2b record: via-in-pad prohibited (every footprint the board uses checked above), the via spec, the hole-free
    thermal-pad footprints, and the thermal consequence from s8_calcs (U5/U2 Tj at the rated load; rating unchanged or
    reduced)."""
    import s8_calcs
    import s92_contract
    p, v = s8_calcs.table()
    _, eff = s8_calcs.banks(p)
    change = s8_calcs.thermal_contract(v, eff)['via_change']
    return {'decision': s92_contract.VIA_IN_PAD['decision'], 'footprints_checked': len(footprints_checked),
            'plated_holes_in_pads': 0,
            'thermal_pad_footprints': {f['ref']: FP_S8[f['key']] for f in s92_contract.THERMAL_VIA_FIELDS},
            'via_spec': {k: s92_contract.VIA_SPEC[k] for k in ('drill_mm', 'diameter_mm', 'annular_ring_min_mm', 'type',
                                                               'tenting', 'filling', 'hole_to_copper_min_mm')},
            'beside_pad_vias': {r: x['beside_pad_vias_after'] for r, x in change['fields'].items()},
            'in_pad_holes_removed': {r: x['in_pad_holes_before'] for r, x in change['fields'].items()},
            'U5': change['U5'], 'U2': {k: change['U2'][k] for k in ('Tj_at_50C_rating_C', 'Tj_at_50C_limit_C',
                                                                      'thermal_penalty_C')},
            'published_rating_A': change['rating']['published_A'], 'rating_changed': change['rating']['changed'],
            'rating_note': change['rating']['why']}


def verify(netlist, hardware=MODULE / 'hardware', root=None):
    xml_root, comps, nets, pins = load_xml(netlist)
    parts = {p['ref']: p for p in circuit_s8.circuit() if not p['ref'].startswith('#')}
    assert set(parts) == set(comps), ('Native/table component mismatch', sorted(set(parts) ^ set(comps)))
    expected = {}; netids = {}; footprints_checked = set()
    for ref, p in parts.items():
        assert comps[ref].findtext('value') == p['value'], (ref, 'value')
        assert comps[ref].findtext('footprint') == 'USBPOWER45:' + FP_S8[p['fp']], (ref, 'footprint')
        for field, val in p['fields'].items():
            assert comps[ref].findtext(f'fields/field[@name="{field}"]') == val, (ref, field)
        f = parse((hardware / 'USBPOWER45.pretty' / (FP_S8[p['fp']] + '.kicad_mod')).read_text())
        assert {str(x[1]) for x in nodes(f, 'pad') if x[1]} == set(p['pins']), (ref, 'pad set')
        drilled = holes_in_pads(f)              # S9.2b: no via-in-pad, footprint level
        assert not drilled, (ref, FP_S8[p['fp']], 'plated hole inside a pad (via-in-pad is prohibited)', drilled)
        footprints_checked.add(FP_S8[p['fp']])
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
        return float(s[:-1]) * {'k': 1e3, 'M': 1e6, 'u': 1e-6, 'n': 1e-9}[s[-1]] if s[-1] in 'kMun' else float(s)

    # ---- What S8/S9 removes and keeps
    s7 = {p['ref'] for p in circuit45.circuit() if not p['ref'].startswith('#')}
    removed = {r for r in set(circuit_s8.S8_REMOVED) | set(circuit_s8.S9_REMOVED) if not r.startswith('#')}
    added = set(comps) - s7
    assert removed <= s7 and not removed & set(comps), 'S8/S9_REMOVED refs must be S7 refs and absent'
    assert s7 - set(comps) == removed, ('Only the listed S7 refs may disappear', sorted(s7 - set(comps) - removed))
    assert added == {'J3', 'C59', 'C61', 'C62', 'R92', 'U20', 'R93', 'R94', 'R97', 'R98', 'R99',
                     'C63', 'C65', 'C66', 'U21', 'R100', 'C67', 'D22', 'TP17', *circuit_s8.ARMING_ADDED,
                     *circuit_s8.BUCKBOOST_ADDED, *circuit_s8.S91_ADDED, *circuit_s8.S92_ADDED}, sorted(added)
    # ---- S9.0 step 1: no +5V net, ref or part survives
    netnames = {k.split('/')[-1] for k in nets}
    assert not set(circuit_s8.PLUS5_NETS) & netnames, ('S9.0: +5V nets must be gone', sorted(set(circuit_s8.PLUS5_NETS) & netnames))
    assert not {k for k in netnames if k.startswith(('P5_', 'EF_')) or k == '+5V'}, 'S9.0: no P5_*/EF_*/+5V net'
    assert not (set(circuit_s8.S8_PLUS5_DROPPED) | set(circuit_s8.S9_REMOVED)) & set(comps), 'S9.0: +5V refs must be gone'
    for ref, nc in NC_PINS.items():
        for pin in nc:
            assert 'unconnected-' in pins[(ref, pin)], (ref, pin, 'S9.0: must be a no-connect')
    tps1663 = sorted(r for r in comps if comps[r].findtext('fields/field[@name="MPN"]') == 'TPS16630PWPR')
    assert tps1663 == ['U5'], ('U5 must be the only TPS16630', tps1663)
    assert not any(comps[r].findtext('fields/field[@name="MPN"]') in FORBIDDEN_MPN for r in comps)
    assert not any('CP_Elec' in comps[r].findtext('footprint') for r in comps), 'No electrolytic footprints'
    assert not {'P12_RAW', 'N12_RAW', 'N12_STATUS', 'NOT_RUN', 'START_READY'} & {k.split('/')[-1] for k in nets}

    for ref, m in CRIT.items():
        for pin, net in m.items():
            isnet(ref, pin, net)
    # ---- S9.2 item 4: U4 enable truth table and the 3 A plant inputs DERIVED from this netlist (tools/s92_netlist.py)
    import s92_netlist
    design = s92_netlist.Design.from_xml(netlist)
    enable = s92_netlist.enable_model(design)
    assert enable['pass'], ('S9.2: netlist-derived U4 enable truth table', enable['violations'][:4])
    phys = s92_netlist.plant_inputs(design)
    cl = phys['params']['current_limit']
    assert cl['limited'] and cl['kelvin_4_terminal'] and cl['shunt'] == 'R109', ('S9.2: R109 Kelvin CC limit', cl)
    # ---- S9.2 item 1: D24 coordination from the netlist OVP divider and the D24 datasheet row (independent table)
    tvs, vbr_cold, clamp = d24_coordination(design)
    assert all(clamp.values()), ('S9.2 D24 / OVP coordination', clamp, phys['params']['OVP_rise_V'], vbr_cold)
    check_tps3808_s85(xml_root, comps, pins)
    libparts = {p.get('part'): {x.get('num'): x.get('name') for x in p.findall('pins/pin')}
                for p in xml_root.findall('libparts/libpart')}
    lm = libparts['LM2901_QUAD']
    assert lm[LM2901_SO14['VCC']] == 'VCC' and lm[LM2901_SO14['GND']] == 'GND'
    for out, (inv, non) in LM2901_SO14['outputs'].items():    # same comparator: kOUT, k-, k+
        k = lm[out].removesuffix('OUT')
        assert (lm[inv], lm[non]) == (k + '-', k + '+'), ('LM2901 symbol pairing differs from TI table', out, inv, non)
    for u in ('U18', 'U20'):
        assert comps[u].findtext('fields/field[@name="MPN"]') == 'LM2901BIDR', (u, 'S8.1: LM2901B')
    for u, out, inv, non, ref_net in (('U20', '13', '10', '11', 'REF_OV'), ('U20', '1', '6', '7', 'REF_OV'),
                                      ('U18', '2', '4', '5', 'REF_GOOD')):
        assert 'unconnected-' in n(u, out), (u, out, 'spare comparator output stays open')
        assert (n(u, inv), n(u, non)) == (netids[ref_net], netids['GND']), (u, out, 'spare: - at the reference, + at GND')
    tlv = libparts['TLV431_DBZ']
    assert {k: tlv[k] for k in TLV431_DBZ_TI} == {k: TLV431_SYMBOL_NAME[v] for k, v in TLV431_DBZ_TI.items()}, \
        ('TLV431 symbol pins differ from TI SLVS139Z Table 4-1 (DBZ)', tlv)
    assert comps['U21'].findtext('fields/field[@name="MPN"]') == 'TLV431BIDBZR'
    assert n('U21', 1) == n('U21', 2) == netids['REF_OV'] and n('U21', 3) == netids['GND'], 'U21: REF tied to CATHODE'
    assert nets[netids['REF_OV']] == {('U21', '1'), ('U21', '2'), ('R100', '2'), ('C67', '1'), ('TP17', '1'),
                                      ('U20', '5'), ('U20', '6'), ('U20', '10'), ('R98', '1')}, 'REF_OV members'
    assert netids['V3V3'] not in {n('R98', 1), n('R99', 1)}, '-12V guard divider must not depend on V3V3'
    assert nets[netids['MON_OVN']] == {('R98', '2'), ('R99', '1'), ('C66', '1'), ('D22', '2'), ('D22', '3'),
                                       ('U20', '9')}, 'MON_OVN members (D22 clamp at the comparator node)'
    for r in ('R93', 'R94', 'R98', 'R99'):
        assert comps[r].findtext('fields/field[@name="Tolerance"]') == '0.1%', (r, '0.1 % divider')
    assert not set(circuit_s8.CROWBAR_REMOVED) & set(comps)
    assert not any('CROW_' in k for k in nets), 'crowbar nets must be absent'
    # S9.0: OV_N is driven only by the +12V (out 2) and -12V (out 14) guard channels; the spares stay off it.
    assert nets[netids['OV_N']] == {('U20', '2'), ('U20', '14'), ('U12', '10'), ('R97', '2'), ('TP6', '1')}, \
        ('S9.0: OV_N = the +12V and -12V guard outputs only', sorted(nets[netids['OV_N']]))
    for ref in ('C57', 'C65'):
        assert comps[ref].findtext('fields/field[@name="Voltage"]') == '50V', (ref, 'VPD bypass rating')
    # Common-mode headroom of the VPD-powered comparators at the lowest VPD the system can run from (VPD_RUN_MIN_V).
    cm_headroom = VPD_RUN_MIN_V - 2.0 - (VREF_OV[2]+VIO_B)
    assert cm_headroom > 5 and VPD_RUN_MIN_V >= 5.0, 'CM and offset test-supply conditions'
    for k, v in {'5': '1Q', '8': '2Q_N', '9': '2Q', '10': '2PRE_N', '13': '2CLR_N'}.items():
        assert libparts['HC74_DUAL'][k] == v, ('HC74 pin', k, libparts['HC74_DUAL'][k])
    for j in ('J2', 'J3'):
        for pin, net in HEADER.items():
            isnet(j, pin, net)
        for pin in range(11, 17):
            assert 'unconnected-' in n(j, pin), (j, pin, 'S9.0: +5V pins 11/12 and CV/GATE open')
    leds = sorted(r for r in comps if ':LED' in comps[r].findtext('footprint'))
    assert leds == ['D8'], ('S8 final: D8 MAIN is the only LED (rail LEDs removed)', leds)
    assert not set(circuit_s8.LED_REMOVED) & set(comps), 'rail LED parts must be gone'
    for d, r, q, gate in [('D8', 'R22', 'Q6', 'MAIN_LED_OK')]:
        isnet(r, 1, 'V3V3'); assert n(r, 2) == n(d, 2) and n(d, 1) == n(q, 3)
        isnet(q, 1, gate); isnet(q, 2, 'LED_RETURN')
    assert nets[netids['LED_RETURN']] == {('Q6', '2'), ('Q10', '3')}, 'LED return: Q6 source + Q10 drain only'
    for net, tp in (('P12_OK', 'TP12'), ('N12_OK', 'TP14')):   # status: logic + pull-up + pad
        assert {r for r, _ in nets[netids[net]]} == {'U18', 'U14', {'P12_OK': 'R35', 'N12_OK': 'R62'}[net], tp}, net
    # ---- S9.0: the fault chain without +5V. ANY_BAD = NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3) (U14 gate 1).
    assert {n('U14', q) for q in (1, 2, 4, 5)} == {netids['MAIN_LED_OK'], netids['P12_OK'], netids['N12_OK'],
                                                   netids['V3V3']}, 'S9.0: ANY_BAD inputs'
    assert n('U14', 4) == netids['V3V3'], 'S9.0: the former +5V input of U14 gate 1 is tied high'
    # ---- S8.5 (B): one-shot arming. STARTED = U12 A preset by START_N = NAND(MAIN_LED_OK, RUN), cleared only by RESET_N,
    # clock tied low; TIMER_GO = RUN AND STARTED; ARMED is the U11 output. MAIN_OK/V20_OK never drive the timer directly.
    assert nets[netids['STARTED']] == {('U12', '5'), ('U13', '10'), ('TP19', '1')}, 'B: STARTED members'
    assert nets[netids['START_N']] == {('U14', '8'), ('U12', '4')}, 'B: START_N drives only the STARTED preset'
    assert {n('U14', q) for q in (9, 10, 12, 13)} == {netids['MAIN_LED_OK'], netids['RUN'], netids['V3V3']}, \
        'B: START_N = NAND(MAIN_LED_OK, RUN)'
    assert n('U14', 9) == netids['MAIN_LED_OK'] and n('U14', 10) == netids['RUN'], 'B: START_N = NAND(MAIN_LED_OK, RUN)'
    assert n('U12', 3) == netids['GND'] and n('U12', 1) == netids['RESET_N'], 'B: STARTED has no clock, RESET clears it'
    assert nets[netids['TIMER_GO']] == {('U13', '8'), ('R69', '1')}, 'B: TIMER_GO drives only the U11 sense divider'
    assert {n('U13', 9), n('U13', 10)} == {netids['RUN'], netids['STARTED']}, 'B: TIMER_GO = RUN AND STARTED'
    assert not {netids['MAIN_OK'], netids['V20_OK']} & {n('U13', 9), n('U13', 10)}, 'B: no arming from MAIN_OK/V20_OK'
    assert nets[netids['ARMED']] == {('U11', '1'), ('R71', '2'), ('U13', '4'), ('TP10', '1')}, 'B: ARMED = U11 output'
    assert nets[netids['MAIN_LED_OK']] == {('U13', '11'), ('U14', '1'), ('U14', '9'), ('Q6', '1'), ('Q15', '1')}, 'MAIN_LED_OK members'
    assert {('U2', '1'), ('U13', '12'), ('U5', '15'), ('U5', '16')} <= nets[netids['MAIN_OK']]   # S9.0: U2 EN/UVLO is pin 1
    assert nets[netids['V20_OK']] == {('U18', '13'), ('R85', '2'), ('TP15', '1'), ('U13', '13')}, 'V20_OK -> MAIN_LED_OK only'
    assert n('U9', 8) != n('U5', 18), 'Latch supply must survive main switch off'

    # ---- Ceramic banks and the VIN damper (no electrolytics)
    def bank(net, val):
        return sorted(r for r, p in parts.items() if p['value'] == val and p['fp'] == 'C1206'
                      and netids[net] in {n(r, 1), n(r, 2)} and netids['GND'] in {n(r, 1), n(r, 2)})
    banks = {'P12_VOUT': bank('P12_VOUT', '22u'), '+12V': bank('+12V', '22u'), '-12V': bank('-12V', '22u'),
             'VIN': bank('VIN', '10u')}
    assert len(banks['P12_VOUT']) == 6 and len(banks['+12V']) == 2 and len(banks['-12V']) == 7, banks
    damp = n('R92', 2)
    assert {(r, '1') for r in ('C5', 'C62')} | {('R92', '2')} == nets[damp], 'damper node = R92.2 + C5.1 + C62.1'
    for r in ('C5', 'C62'):
        isnet(r, 2, 'GND'); assert math.isclose(value(r), 10e-6)
    assert math.isclose(value('R92'), 1.0)
    assert sorted(banks['VIN']) == sorted(VIN_BANK), banks['VIN']
    assert math.isclose(value('C49'), 100e-9), 'C49 (U11 delay)'
    # ---- S9.0 step 2: TPS552892-Q1 four-switch cell. Pin names of the native symbol against TI's table (s90_parts),
    # independent function checks per pin, and the cell wiring.
    tps = libparts['TPS552892_RYQ']
    assert tps == TPS552892_TI, ('TPS552892 symbol pins differ from TI SLVSGT7 Table 5-1', tps)
    assert comps['U2'].findtext('fields/field[@name="MPN"]') == 'TPS552892QWRYQRQ1', 'U2 MPN'
    role = {name: num for num, name in TPS552892_TI.items()}
    u2 = lambda name: n('U2', role[name])        # noqa: E731
    assert u2('VIN') == netids['VIN'] and u2('EN/UVLO') == netids['MAIN_OK'], 'U2 VIN / EN = MAIN_OK'
    assert u2('MODE') == u2('EXTVCC') == u2('VCC') == n('C82', 1) and n('C82', 2) == netids['GND'], \
        'U2 FPWM (MODE = VCC) and internal LDO (EXTVCC = VCC) with the VCC capacitor C82 (ground terminal on PGND, S9.2)'
    assert nets[u2('VCC')] == {('U2', role['MODE']), ('U2', role['EXTVCC']), ('U2', role['VCC']), ('C82', '1')}
    assert u2('DITH/SYNC') == u2('AGND') == netids['AGND_U2'] != u2('PGND'), 'S9.1 split grounds'
    assert u2('PGND') == netids['GND']
    assert nets[netids['AGND_U2']] == {('U2','5'),('U2','17'),('C83','2'),('R9','2'),('R110','2'),('R113','1'),('TP28','1')}, \
        'S9.2 quiet island exact membership (C82.2 is PGND; R113 the only bridge)'
    both = sorted(r for r in comps if r != 'U2' and {n(r, q) for q in {k[1] for k in pins if k[0] == r}}
                  >= {netids['AGND_U2'], netids['GND']})
    assert both == ['R113'], ('S9.2: R113 must be the only AGND_U2/PGND bridge', both)
    assert value('R113') == 0 and value('R114') == 510, 'S9.1 ground star / UVLO trim'
    assert nets[netids['N_EN_RETURN']] == {('Q14', '3'), ('Q15', '2'), ('R115', '1'), ('TP30', '1')}, 'S9.2 N_EN_RETURN default'
    assert value('R115') >= 50e3, 'S9.2: R115 below ~50k lets the Q15 source follower bias Q1 on with RUN low'
    assert comps['D24'].findtext('fields/field[@name="MPN"]') == 'SMBJ20A' and value('R24') == 9100, 'S9.2 D24/OVP pair'
    assert value('R109') == .018 and value('R111') == 6800 and math.isclose(value('C83'),100e-9)
    assert nets[u2('FSW')] == {('U2', role['FSW']), ('R110', '1')} and n('R110', 2) == netids['AGND_U2'], 'U2 FSW -> R110'
    assert nets[u2('SW1')] == {('U2', role['SW1']), ('L1', '1'), ('C10', '2')}, 'SW1: L1 + BOOT1 capacitor'
    assert nets[u2('SW2')] == {('U2', role['SW2']), ('L1', '2'), ('C9', '2')}, 'SW2: L1 + BOOT2 capacitor'
    assert nets[u2('BOOT1')] == {('U2', role['BOOT1']), ('C10', '1')} and nets[u2('BOOT2')] == {('U2', role['BOOT2']), ('C9', '1')}
    assert u2('VOUT') == netids['P12_VOUT'] and u2('ISP') == netids['P12_ISP'] and u2('ISN') == netids['P12_ISN'], \
        'S9.2: U2 ISP/ISN on their own Kelvin sense nets'
    assert (n('R109', 1), n('R109', 2), n('R109', 3), n('R109', 4)) == (
        netids['P12_VOUT'], netids['P12_ISP'], netids['P12_ISN'], netids['+12V']), 'S9.2: R109 force 1/4, sense 2/3'
    assert comps['R109'].findtext('footprint') == 'USBPOWER45:R_Shunt_1206_KelvinSplit_RLM12', 'S9.2 Kelvin land'
    assert nets[u2('FB')] == {('U2', role['FB']), ('R8', '1'), ('R9', '1')}, 'FB divider R8 (from +12V) / R9'
    assert nets[u2('COMP')] == {('U2', role['COMP']), ('R111', '1')} and n('R111', 2) == n('C83', 1), 'COMP R111 + C83'
    for name in ('PG', 'CC', 'CDC'):
        assert 'unconnected-' in u2(name), ('U2', name, 'open')
    for net, members in RAILS_S90.items():
        got = {k for k in nets[netids[net]] if not k[0].startswith('#')}
        assert got == members, (net, 'S9.0 rail membership (no series element added)', sorted(got ^ members))
    for ref in comps:
        mpn = comps[ref].findtext('fields/field[@name="MPN"]') or ''
        assert not mpn.upper().startswith(REVERSE_BLOCKING_MPN_PREFIXES), (ref, mpn, 'S9.0: no reverse-blocking part')
    assert not {k.split('/')[-1] for k in nets} & {'P12_BLK', 'N12_BLK', 'P12_OUT_BLOCKED', 'N12_GATE'}

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
    ov12, ovneg = positive('R93', 'R94'), guard(negative)

    def fac(ref):                     # each divider resistor's own tolerance (R11/R12 are 0.1 % since S8.4)
        t = comps[ref].findtext('fields/field[@name="Tolerance"]')
        return (R01_LO, R01_HI) if t == '0.1%' else (lo, hi)

    def setpoint(top, bot, vfb):
        return vfb * (1 + value(top) * fac(top)[1] / (value(bot) * fac(bot)[0]))
    p12_max = setpoint('R8', 'R9', VREF_TPS552892[2])                              # SLVSGT7 VREF max (S9.0)
    p12_min = VREF_TPS552892[0] * (1 + value('R8') * fac('R8')[0] / (value('R9') * fac('R9')[1]))
    n12_max = setpoint('R14', 'R15', 1.015)                                        # SNVSC40E FB max
    ovp12_max = OVP_TPS552892_MAX                                                  # absolute output OVP, not 12 V-relative
    assert 14.7 < ov12[1] < 15.0 and 13.5 < ovneg[1] < 13.8, (ov12, ovneg)
    peak = {'+12V': p12_max + RELEASE_N16_V['+12V'], '-12V': n12_max + RELEASE_N16_V['-12V']}
    bands = {'+12V': ov12, '-12V': ovneg}
    for rail, band in bands.items():
        assert band[0] > peak[rail], (rail, 'guard minimum must clear the stacked setpoint + N=16 release', band, peak[rail])
        assert band[2] <= DOWNSTREAM_MAX_V[rail], (rail, 'guard maximum above the downstream limit', band)
    # REF_OV bias: R100 must keep U21 above IK(min) 0.1 mA with the -12V divider drawing (1.26 + 20 V) / (R98 + R99)
    ik_min = ((3.3 * .98 - VREF_OV[2]) / (value('R100') * 1.01)
              - (VREF_OV[2] + 20.0) / ((value('R98') + value('R99')) * R01_LO) - 4 * IB_B)
    assert ik_min > 0.5e-3, ('U21 cathode current too low', ik_min)
    assert value('C67') >= 4.7e-6, 'C67 must stay right of the TLV431 instability region (SLVS139Z Fig. 5-18)'
    r0 = ref(3.3, 1, 1)
    mon = {'P12_V': r0 * (1 + value('R75') / value('R76')),
           'N12_magnitude_V': 3.3 * value('R82') / (value('R80') + value('R81')) - r0 * (1 + value('R82') / (value('R80') + value('R81'))),
           'V20_OK_status_floor_V': r0 * (1 + value('R83') / value('R84'))}
    por_max = .411 * (1 + (value('R65') + value('R91')) * hi / (value('R66') * lo))
    assert por_max < 3.3 * .98, 'POR threshold could prevent a valid LDO starting'
    t_start = value('C49') * 1e9 / 175 + .0005                                      # TPS3808 SBVS050N eq. 1
    assert .5 < t_start < .65 and t_start * .6 * .9 > .2
    # ---- S8.5 (B, C): V20_OK is a U5 status-validity floor: above the PD 5 V phase and below the U5 turn-off minimum, so
    # MAIN_LED_OK = MAIN_OK wherever U5 can be on (V20_OK never drops first) and no V20_OK corner can arm or disarm.
    u5_on, u5_off = u5_thresholds(value)
    v20 = v20_band(value)
    assert v20[0] >= VSAFE5V_MAX + V20_MARGIN_MIN_V, ('V20_OK minimum too close to the PD 5 V phase', v20)
    assert v20[2] <= u5_off[0] - V20_MARGIN_MIN_V, ('V20_OK maximum not below the U5 turn-off minimum', v20, u5_off)
    assert u5_on[2] <= 13.0 and u5_on[2] < VPD_LOADED_MIN_V and u5_off[2] < VPD_LOADED_MIN_V, \
        ('U5 UVLO vs the PD source (-5 %) / loaded minimum', u5_on, u5_off)

    # ---- Digital model from native gate pin nets (settled; not an analog timing simulation)
    gates = [('U13', 1, 2, 3), ('U13', 4, 5, 6), ('U13', 9, 10, 8), ('U13', 12, 13, 11)]
    assert n('R72', 1) == n('U14', 6) and n('R72', 2) == n('C51', 1) == n('U15', 2)

    def comb(inputs, qa, qb, timer_done):
        """Settled values with flip-flop A/B states qa/qb (asynchronous PRE/CLR applied), U11 'delay elapsed' flag."""
        s = {netids[k]: v for k, v in inputs.items()}; s[netids['V3V3']] = True; s[netids['GND']] = False
        for _ in range(8):
            for u, a, b, y in gates:
                s[n(u, y)] = bool(s.get(n(u, a), False) and s.get(n(u, b), False))
            s[n('U14', 6)] = not all(s.get(n('U14', q), False) for q in [1, 2, 4, 5])
            s[n('U14', 8)] = not all(s.get(n('U14', q), False) for q in [9, 10, 12, 13])
            s[n('U15', 4)] = s[n('R72', 1)]
            for (clr, pre, q, qn), st in (((1, 4, 5, None), qa), ((13, 10, 9, 8), qb)):
                c, pr = s[n('U12', clr)], s[n('U12', pre)]
                s[n('U12', q)] = True if not pr else (False if not c else st)
                if qn:
                    s[n('U12', qn)] = True if not c else (False if not pr else not st)
            s[n('U11', 1)] = timer_done and s[n('R69', 1)] and s[n('U11', 3)]
        return s
    cases = 0
    for reset, ovn, mainok, p12, n12, v20ok, qa, qb, done in itertools.product([False, True], repeat=9):
        i = {'RESET_N': reset, 'OV_N': ovn, 'MAIN_OK': mainok, 'P12_OK': p12, 'N12_OK': n12, 'V20_OK': v20ok}
        s = comb(i, qa, qb, done)
        fault = (not ovn) or (reset and qb)              # preset by OV_N wins; RESET clears
        run = reset and not fault
        assert s[netids['RUN']] == run, (i, qa, qb)
        started = (not s[netids['START_N']]) or (reset and qa)
        assert s[netids['START_N']] == (not (mainok and v20ok and run)), ('B: START_N', i)
        assert s[netids['STARTED']] == started, ('B: STARTED latch', i, qa)
        assert s[netids['TIMER_GO']] == (run and started), ('B: TIMER_GO = RUN AND STARTED', i, qa)
        assert s[netids['ARMED']] == (done and run and started and reset), ('B: ARMED = U11 output', i)
        assert s[netids['FAULT_CLK']] == (s[netids['ARMED']] and not (mainok and v20ok and p12 and n12))
        assert s[n('Q6', 1)] == (mainok and v20ok)
        if not ovn:
            assert not s[netids['RUN']], 'overvoltage must stop RUN in every state, also before ARMED'
        if not mainok or not v20ok:
            assert s[netids['START_N']], 'B: no start while U5 is off or its status is not validated by V20_OK'
        cases += 1
    seq = []
    base = {k: True for k in ['RESET_N', 'OV_N', 'MAIN_OK', 'P12_OK', 'N12_OK', 'V20_OK']}
    for missing in ['MAIN_OK', 'P12_OK', 'N12_OK', 'V20_OK']:
        inp = dict(base); inp[missing] = False
        s = comb(inp, True, False, False); assert s[netids['RUN']] and not s[netids['FAULT_CLK']]   # window
        s = comb(inp, True, False, True); assert s[netids['FAULT_CLK']]                            # armed -> clock FAULT
        s = comb(inp, True, True, True); assert not s[netids['RUN']]
        inp[missing] = True
        s = comb(inp, True, True, True); assert not s[netids['RUN']]                               # no self-restart
        inp['RESET_N'] = False; s = comb(inp, False, False, False); assert not s[netids['RUN']]
        seq.append(missing)
    inp = dict(base); inp['MAIN_OK'] = False
    s = comb(inp, True, False, True)
    assert s[netids['STARTED']] and s[netids['TIMER_GO']] and s[netids['ARMED']] and s[netids['FAULT_CLK']], \
        'B: a MAIN_OK drop after the start neither clears STARTED nor stops the timer; once armed it latches'
    seq.append('STARTED survives MAIN_OK drops (no restart); armed + MAIN_OK low -> FAULT clock')
    inp = dict(base); inp['V20_OK'] = False
    assert comb(inp, False, False, False)[netids['START_N']], 'B: floating MAIN_OK without V20_OK cannot start'
    seq.append('MAIN_OK floating high with V20_OK low (PD 5 V phase) does not start the window')
    inp = dict(base); inp['OV_N'] = False
    assert not comb(inp, False, False, False)[netids['RUN']], 'OV preset acts inside the startup window'
    inp['OV_N'] = True
    assert not comb(inp, False, True, False)[netids['RUN']], 'FAULT set by OV stays latched after OV clears'
    seq.append('OV_N preset (unarmed) + latched after release')

    # ---- Arming timelines (event-driven, native gate wiring, U11 delay corners, V20_OK band corners)
    timelines, tl_violations = arming_timelines(pins, nets, v20, phys)
    assert not tl_violations, ('B: arming timeline violations', tl_violations[:6])

    root = Path(root) if root else hardware / 'single' / f'{circuit_s8.PROJECT}.kicad_sch'
    sheets = nodes(parse(root.read_text()), 'sheet')
    assert len(sheets) == SHEETS, ('Hierarchy sheet count', len(sheets))
    files = [root] + [root.parent / next(p[2] for p in nodes(s, 'property') if p[1] == 'Sheetfile') for s in sheets]
    assert len(set(files)) == SHEETS + 1 and all(f.exists() for f in files), files
    for f in files:
        tree = parse(f.read_text())
        for sym in nodes(tree, 'symbol'):
            r = next(p[2] for p in nodes(sym, 'property') if p[1] == 'Reference')
            if r.startswith('TP'):
                assert one(sym, 'in_bom')[1] == 'no' and one(sym, 'in_pos_files')[1] == 'no' and one(sym, 'on_board')[1] == 'yes'
            assert one(sym, 'lib_id')[1] != 'USBPOWER45:+5V', (f.name, 'S9.0: no +5V power symbol')
        for kind in ('label', 'hierarchical_label', 'global_label'):
            for lab in nodes(tree, kind):
                assert not (lab[1] == '+5V' or lab[1].startswith(('P5_', 'EF_'))), (f.name, lab[1], 'S9.0: +5V/EF_ label')
    return {'status': 'S9_schematic_checks_not_bench_qualification', 'components': len(comps),
            'nets_including_NC': len(nets), 'sheets': len(files), 'exact_field_pin_NC_pad_parity': True,
            'removed_S7_refs': len(removed), 'added_refs': sorted(added),
            'ceramic_banks_22u_or_10u': banks, 'vin_damper': {'R92_ohm': value('R92'), 'C5_C62_uF': [10, 10]},
            'overvoltage_guard_V': {'+12V_min_nom_max': [round(v, 3) for v in ov12],
                                    '-12V_magnitude_min_nom_max': [round(v, 3) for v in ovneg],
                                    'model': 'REF_OV TLV431BI 1.2204-1.259 V, LM2901B 5.5 mV / 50 nA, 0.1 % + 25 ppm x 100 C',
                                    'converter_setpoint_max_V': {'+12V': round(p12_max, 3), '-12V': round(n12_max, 3)},
                                    'stacked_normal_peak_V': {k: round(v, 3) for k, v in peak.items()},
                                    'margin_min_to_peak_V': {k: round(bands[k][0] - peak[k], 3) for k in bands},
                                    'downstream_limit_V': DOWNSTREAM_MAX_V,
                                    'margin_max_to_limit_V': {k: round(DOWNSTREAM_MAX_V[k] - bands[k][2], 3) for k in bands},
                                    'converter_OVP_max_V': {'+12V': round(ovp12_max, 2)},
                                    'corner_overlap_with_converter_OVP': {'+12V': ov12[0] < ovp12_max},
                                    'U21_cathode_current_min_mA': round(ik_min * 1e3, 3),
                                    'OV_N_members': sorted(f'{r}.{q}' for r, q in nets[netids['OV_N']])},
            'plus12_buckboost': {'U2': 'TPS552892QWRYQRQ1 (TI RYQ0021B)', 'pin_roles': 'native symbol = TI SLVSGT7 Table 5-1',
                                 'setpoint_V': [round(p12_min, 3), round(VREF_TPS552892[1] * (1 + value('R8') / value('R9')), 3),
                                                round(p12_max, 3)],
                                 'fSW_kHz': round(1000 / (0.05 * value('R110') + 35) * 1e3),
                                 'cc_limit_A': [round(0.048 / (value('R109') * 1.01 * 1.0075), 3),
                                                round(0.052 / (value('R109') * 0.99 * 0.9925), 3)],
                                 'wiring': 'L1 SW1-SW2; C10 BOOT1-SW1, C9 BOOT2-SW2; MODE/EXTVCC/VCC + C82 (FPWM, internal '
                                           'LDO); DITH/AGND AGND_U2, PGND GND; R113 sole join at C82; R110 FSW; VOUT/ISP -> R109 -> +12V/ISN; FB R8 (+12V) '
                                           '/ R9; COMP R111 + C83; PG/CC/CDC open; EN/UVLO = MAIN_OK',
                                 'rails_exact': {k: sorted(f'{r}.{q}' for r, q in v) for k, v in RAILS_S90.items()},
                                 'reverse_blocking': 'none (owner decision S9.0): no ideal-diode controller or series FET; '
                                                     'R109 is the only series element (current sense, inside the converter)'},
            'accepted_residuals': residual_record(),
            'no_via_in_pad': via_policy_record(footprints_checked),
            'enable_logic': enable,
            'vin_clamp_coordination': {'D24': comps['D24'].findtext('fields/field[@name="MPN"]'), **tvs,
                                       'VBR_min_at_0C_V': round(vbr_cold, 3),
                                       'U5_OVP_rise_V': [round(x, 3) for x in phys['params']['OVP_rise_V']],
                                       'U5_OVP_fall_V': [round(x, 3) for x in phys['params']['OVP_fall_V']],
                                       'checks': clamp},
            'startup_plant_inputs': {'U5_on_V': [round(x, 3) for x in phys['params']['U5_on_V']],
                                     'U5_off_V': [round(x, 3) for x in phys['params']['U5_off_V']],
                                     'current_limit': {k: (v if not isinstance(v, list) else [round(x, 4) if isinstance(x, float) else x for x in v])
                                                       for k, v in cl.items()},
                                     'banks': phys['params']['banks'],
                                     'P12_OK_V': round(phys['P12_OK_V'], 3), 'N12_OK_V': round(phys['N12_OK_V'], 3)},
            'startup_qualification': startup_qualification_record(),
            'ground_split': {'analog': 'AGND_U2', 'power': 'GND', 'only_link':'R113 at C82.2'},
            'plus5_removed': {'S7_refs_removed': sorted(circuit_s8.S9_REMOVED),
                              'S8_refs_dropped': sorted(circuit_s8.S8_PLUS5_DROPPED),
                              'nets_absent': sorted(circuit_s8.PLUS5_NETS), 'header_pins_11_12': 'no-connect',
                              'ANY_BAD': 'NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3)',
                              'spare_comparators': {'U18': 'out 2 open, - REF_GOOD, + GND',
                                                    'U20': 'out 1 open: - REF_OV, + MON_OVN; out 13 open: - REF_OV, + GND'},
                              'U5_nets': 'MAIN_* (EF_* in S7)'},
            'startup_arming': {'topology': 'STARTED = U12 A (PRE_N = START_N = NAND(MAIN_LED_OK, RUN), CLR_N = RESET_N, '
                                           'CLK low); TIMER_GO = RUN AND STARTED; ARMED = U11 output',
                               'TIMER_GO': 'RUN AND STARTED', 'START_N': 'NAND(MAIN_LED_OK, RUN)',
                               'MAIN_OK_in_timer_path': False, 'V20_OK_in_timer_path': False,
                               'TIMER_GO_members': sorted(f'{r}.{q}' for r, q in nets[netids['TIMER_GO']]),
                               'STARTED_members': sorted(f'{r}.{q}' for r, q in nets[netids['STARTED']]),
                               'ARMED_members': sorted(f'{r}.{q}' for r, q in nets[netids['ARMED']]),
                               'V20_OK_band_V': [round(v, 3) for v in v20],
                               'U5_on_V': [round(v, 3) for v in u5_on], 'U5_off_V': [round(v, 3) for v in u5_off],
                               'V20_OK_margin_below_U5_off_min_V': round(u5_off[0] - v20[2], 3),
                               'V20_OK_margin_above_vSafe5V_max_V': round(v20[0] - VSAFE5V_MAX, 3),
                               'U11_delay_s': [TD_CORNERS_S[0], round(t_start, 3), TD_CORNERS_S[1]],
                               'plant_model': PLANT,
                               'requirements': {'R1': 'bounded arming: converters enabled and unarmed only within the '
                                                      'U11 delay after the first enable since RESET',
                                                'R2': 'no restart: ARMED rises once per RESET, t_d after the first enable, '
                                                      'whatever MAIN_OK/VPD/rails do',
                                                'R3': 'no early arming: never before a genuine converter enable (U5 on with '
                                                      'valid status); the PD 5 V phase cannot start it',
                                                'R4': 'fail-safe: after ARMED any bad status > ~1 ms latches FAULT; FAULT '
                                                      'keeps RUN low until RESET; OV_N presets FAULT at any time'},
                               'timelines': timelines, 'violations': tl_violations},
            'comparator_supply': {'supply': 'VPD', 'output_pullups': 'V3V3',
                                  'full_temp_headroom_V': cm_headroom, 'bypass_rating_V': 50},
            'nominal_voltage_valid_thresholds': mon, 'logic_POR_high_screen_V': por_max,
            'startup_qualification_typ_s': t_start, 'digital_combinations_checked': cases, 'scenarios': seq,
            'warnings': ['Arithmetic stacks every tolerance at once; it is a screen, not a rating.',
                         'Digital truth checks and the arming timelines use datasheet timings; they do not model analog '
                         'propagation, comparator/LED timing or MOSFET transients.',
                         'No routed PCB, thermal/startup/fault-injection qualification.'],
            'order_ready': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--netlist', type=Path, required=True)
    ap.add_argument('--hardware', type=Path, default=MODULE / 'hardware')
    ap.add_argument('--root', type=Path, help='S8 root (default <hardware>/single/usb-power-45w-single.kicad_sch)')
    a = ap.parse_args()
    print(json.dumps(verify(a.netlist, a.hardware, a.root), indent=2))
