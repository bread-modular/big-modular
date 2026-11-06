"""S9.2 / P2.2 placement-and-routing contract of the board (machine-readable half of
docs/design/routing-notes.md). place_s8.sync_candidate copies it into docs/design/placement.json; check_s8_board.py
checks every item that can be checked on the unrouted board (pad nets, test-pad anchors, star/Kelvin geometry, clamp
proximity) and lists the copper/via items that can only be checked after routing as PENDING (never as passed).

The thermal items put a board behind the screens in calcs.json: the U2 Tj screen uses TI's JEDEC 2s2p RthetaJA, the
R109 rating TA-I's 300 mm2 copper condition and the D10 screen an effective RthetaJA target. The published rating is
conditional on these items being met by the routed board and on the post-prototype thermal tests (TH-1..TH-3).
notes_index() reads the human half back (its test-pad table and the IDs of its uncertainty register) so that the tests
and tools/review_s8.py can check that every pad and every acceptance-test ID used here is documented there.
S9.2b (owner decisions 2026-11-02): via-in-pad is PROHIBITED and only standard JLCPCB 0.3/0.6 mm tented, unfilled through
vias are allowed (VIA_SPEC, VIA_IN_PAD); the drilled exposed pads of U4/U5/U9 became beside-pad thermal fields
(THERMAL_VIA_FIELDS, placed by tools/place_s8.py --apply-thermal-vias) whose thermal cost thermal_via_model() bounds.
"""
import re

from s92_parts import NO_VIA_IN_PAD as _NO_VIA, exposed_pad

NOTES = 'docs/design/routing-notes.md'

# Acceptance test pads. near = (ref, pad) the pad must sit next to, max = straight-line pad-centre limit (mm) checked on
# the unrouted board; pair = the 2.54 mm partner (probe tip + ground spring or differential pair).
TEST_POINTS = [
    dict(ref='TP1', net='VPD', size='1.0 mm round (S7 pad, DC only)', near=('Q3', '2'), max=5.0,
         measure='VPD at the module: UVLO / OVP / input-range tests (IN-1, IN-2), DC', limit='13.5-16.5 V operating; OVP trip 17.30-19.44 V; UVLO on <= 12.98 V'),
    dict(ref='TP26', net='VIN', size='1.5 mm round', near=('D24', '1'), max=9.0, pair='TP27',
         measure='D24 cathode / U2+U4 input: clamp voltage and energy under injection (CL-1), VIN ripple and ringing (EMI-1)',
         limit='CL-1: <= 30.0 V incl. ringing at 1 A / 20 ms, integral(V*I) <= 0.648 J; EMI-1: <= 1.5 V p-p at 20 MHz BW'),
    dict(ref='TP27', net='GND', size='1.5 mm round', near=('D25', '1'), max=6.0, pair='TP26',
         measure='ground-spring reference for TP26 (via to In1 at the pad)', limit='-'),
    dict(ref='TP20', net='P12_VOUT', size='1.5 mm round', near=('R109', '1'), max=11.0, pair='TP24',
         measure='R109 force node (converter side): force drop V(TP20-TP24) vs sense V(TP22-TP23) (KS-1); D26 clamp (CL-2)',
         limit='KS-1: V(TP20-TP24) >= V(TP22-TP23); CL-2: P12_VOUT <= 24.0 V'),
    dict(ref='TP24', net='+12V', size='1.5 mm round', near=('R109', '4'), max=5.0, pair='TP20',
         measure='+12V output after R109: regulation, ripple, load-step, Bode injection point (LS-1)',
         limit='11.54-12.65 V DC; <= 60 mV p-p ripple; PM > 45 deg, GM > 10 dB'),
    dict(ref='TP22', net='P12_ISP', size='1.5 mm round', near=('R109', '2'), max=10.0, pair='TP23',
         measure='Kelvin sense + (U2 ISP): V(TP22-TP23) at the CC limit (KS-1, CC-1)',
         limit='VSNS 48-52 mV at the limit; I = V/18 mOhm within 2.62-2.95 A'),
    dict(ref='TP23', net='P12_ISN', size='1.5 mm round', near=('R109', '3'), max=5.0, pair='TP22',
         measure='Kelvin sense - (U2 ISN)', limit='see TP22'),
    dict(ref='TP25', net='-12V', size='1.5 mm round', near=('U4', '1'), max=6.0,
         measure='-12V at the converter output: regulation, ripple (ground spring on D4 pin 1)',
         limit='-11.38..-12.62 V DC; <= 60 mV p-p'),
    dict(ref='TP28', net='AGND_U2', size='1.5 mm round', near=('R113', '1'), max=5.0, pair='TP29',
         measure='AGND island vs PGND star: DC offset and switching noise (GS-1); sole-bridge check with R113 lifted (GS-2)',
         limit='GS-1: |V| <= 5 mV DC, <= 50 mV p-p (20 MHz); GS-2: AGND-PGND > 10 ohm with R113 removed'),
    dict(ref='TP29', net='GND', size='1.5 mm round', near=('C82', '2'), max=9.0, pair='TP28',
         measure='PGND reference near the C82.2 star (via to In1 at the pad)', limit='-'),
    dict(ref='TP30', net='N_EN_RETURN', size='1.5 mm round', near=('Q15', '2'), max=5.0,
         measure='U4 enable AND gate mid-node: defined default (EN-1)',
         limit=('MAIN_LED_OK low: <= 0.1 V (R115 100k to PGND, <= 1 uA switch leakage); RUN high: <= 0.1 V (Q14 on); '
                'RUN low with MAIN_LED_OK high: <= 3.37 V (Q15 source follower) and U4 EN off')),
    dict(ref='TP19', net='STARTED', size='1.0 mm round (S8.5 logic pad)', near=('U12', '5'), max=25.0,
         measure='one-shot latch: startup sequence S1-S4 (logic analyser, 1 kHz+)', limit='high at first enable; cleared only by RESET/POR'),
    dict(ref='TP10', net='ARMED', size='1.0 mm round (S8.5 logic pad)', near=('U11', '1'), max=33.0,
         measure='arming delay S1-S4', limit='ARMED 0.31-0.88 s after first enable; <= 0.90 s'),
    dict(ref='TP9', net='RUN', size='1.0 mm round (S7 logic pad)', near=('U13', '3'), max=12.0,
         measure='RUN / U5 SHDN: fault latch tests S3/S4, T2', limit='low within 20 us of OV_N low'),
    dict(ref='TP5', net='MAIN_OK', size='1.0 mm round (S7 logic pad)', near=('R63', '2'), max=12.0,
         measure='U5 PGOOD/FLT: OVP/UVLO response (IN-2), source tests S1/S2', limit='low within 14 us + PGOOD deglitch of an OVP trip'),
    dict(ref='TP6', net='OV_N', size='1.0 mm round (S8 logic pad)', near=('U20', '2'), max=10.0,
         measure='rail overvoltage guard T2', limit='low <= 20 us at >= 0.5 V overdrive'),
]
# Every other existing pad is kept unchanged (S7/S8 diagnostic pads, 1.0 mm round): TP2 VPD_U1, TP3 MAIN_IN, TP4 VIN
# (damper), TP7 MAIN_IMON, TP8 GND, TP11 FAULT_LATCH, TP12 P12_OK, TP14 N12_OK, TP15 V20_OK, TP16 V3V3, TP17 REF_OV.
KEPT_DIAGNOSTIC = {'TP2': 'VPD_U1', 'TP3': 'MAIN_IN', 'TP4': 'VIN', 'TP7': 'MAIN_IMON', 'TP8': 'GND', 'TP11': 'FAULT_LATCH',
                   'TP12': 'P12_OK', 'TP14': 'N12_OK', 'TP15': 'V20_OK', 'TP16': 'V3V3', 'TP17': 'REF_OV'}

# Pre-routing proximity screens (pad-centre straight line, same net unless stated): (from, to-candidates, limit mm, why).
PROXIMITY = [
    (('D24', '1'), [('C8', '1'), ('C6', '1'), ('C7', '1'), ('C77', '1'), ('C78', '1')], 10.0, 'D24 cathode at the U2 VIN bank'),
    (('D25', '2'), [('D24', '1')], 6.0, 'D25 VIN clamp beside D24'),
    (('D26', '1'), [('C80', '1'), ('C79', '1'), ('C14', '1')], 10.0, 'D26 cathode on the P12_VOUT bank pour'),
    (('C82', '2'), [('R113', '2')], 3.0, 'R113 PGND pad on the C82.2 PGND terminal (sole star)'),
    (('R115', '1'), [('Q14', '3'), ('Q15', '2')], 5.0, 'R115 at the AND-gate mid-node'),
    (('R109', '2'), [('U2', '12')], 12.0, 'ISP sense run R109 pad 2 -> U2 pin 12'),
    (('R109', '3'), [('U2', '13')], 13.0, 'ISN sense run R109 pad 3 -> U2 pin 13'),
]

GROUND = {
    'analog_net': 'AGND_U2', 'power_net': 'GND', 'sole_link': 'R113', 'star': 'C82.2 (PGND terminal of the VCC capacitor)',
    'members_AGND_U2': ['U2.5', 'U2.17', 'R9.2', 'R110.2', 'C83.2', 'R113.1', 'TP28.1'],
    'pgnd_at_star': ['C82.2', 'R113.2'], 'maximum_link_to_C82_pad_mm': 3.0,
    'rule': ('C82.2 is PGND. R113 pin 2 (PGND) lands on the C82.2 pad copper with 3-4 PGND vias to In1 at C82.2 (TI SLVSGT7 '
             '8.4.1 items 6/7). AGND_U2 is a trace-only island (U2.17/.5, R9.2, R110.2, C83.2, TP28) fed ONLY from R113 pin 1: '
             'F.Cu traces, plus at most one AGND_U2 via pair and one B.Cu AGND_U2 trace (<= 0.25 mm, over solid In1, not under '
             'L1 or the SW nodes) where the U2 power fan-out separates the north members (U2.17, R113.1, C83.2, R9.2, TP28) from '
             'the south-east members (U2.5, R110.2). No AGND pour on any layer, no AGND_U2 via or copper touching In1/In2/B.Cu '
             'GND, no second 0 ohm, no net tie. In1 stays solid PGND under the island. The checker fails any AGND_U2 copper '
             'touching GND other than through R113.'),
}

KELVIN = {
    'part': 'R109 TA-I RLM12FTCMR018 18 mOhm 1 % 75 ppm 1 W on R_Shunt_1206_KelvinSplit_RLM12',
    'pads': {'1': 'force P12_VOUT (converter bank)', '2': 'sense P12_ISP -> U2 ISP pin 12 only',
             '3': 'sense P12_ISN -> U2 ISN pin 13 only', '4': 'force +12V (rail)'},
    'rule': ('Sense traces leave pads 2/3 on their +y edge within 0.6 mm of the inner (element) end, run as a 0.2 mm '
             'coupled pair (<= 0.3 mm gap; only the last <= 2 mm at U2 follow the pin escape) on F.Cu to U2 pins 12/13, never '
             'touch force copper, P12_VOUT or +12V pours, and carry no current. TP22/TP23 branch from the pair after it leaves '
             'the pads. Force current enters/leaves only through pads 1/4. Sense pads stay free of pour (keep-out 0.3 mm).'),
    'residual_error': '0.2 % sense-point residual allowed in the CC-limit band (calcs plus12_buckboost)',
}

THERMAL = {
    'U2': {
        'model': 'TI SLVSGT7 6.4 RthetaJA 43.4 C/W (JEDEC 2s2p); EVM 27.5 C/W (4-layer 2/1/1/2 oz 91 x 66 mm)',
        'requirements': {
            'In1': 'solid PGND plane (0.5 oz), no slot or cut within 15 mm of the U2 centre (via antipads only)',
            'PGND_vias': '>= 10 vias 0.3/0.6 mm with centres <= 4 mm outside the package outline on the PGND copper of the '
                         'U2 cell: at both PGND land ends where the fan-out leaves room (the bars are on a 0.5 mm pitch: '
                         'SW1/SW2 leave west, VIN/VOUT east), at C8.2 and C81.2 and on the PGND copper joining them; to In1 '
                         'and to the B.Cu GND pour; never in a pad',
            'VIN_area': 'F.Cu VIN pour >= 120 mm2 joining U2 pin 7, C8, C6, C7, C77, C78 and D24 K; >= 6 vias to an In2 VIN '
                        'area >= 300 mm2',
            'VOUT_area': 'F.Cu P12_VOUT pour >= 150 mm2 joining U2 pin 11, C81, C11-C14, C79, C80 and R109 pad 1; >= 6 vias '
                         'to a B.Cu P12_VOUT area >= 200 mm2. D26 K and TP20 (no DC current) join it with >= 1.0 mm copper '
                         'or >= 2 vias from the B.Cu area, never through +12V copper',
            'B_Cu_GND': 'B.Cu GND pour >= 600 mm2 under the U2 / L1 / bank region, stitched to In1 with >= 20 vias'},
        'acceptance': 'TH-1'},
    'R109': {
        'model': 'TA-I RLM12: 1 W at 70 C with 300 mm2 of pad + trace copper; derates to 0 at 155 C',
        'requirements': {'force_copper': 'P12_VOUT (pad 1) and +12V (pad 4) F.Cu copper >= 150 mm2 each within 10 mm '
                                         '(>= 300 mm2 together), each with >= 3 vias to a same-net B.Cu or In2 area',
                         'sense_copper': 'pads 2/3: 0.2 mm traces only (no pour)'},
        'acceptance': 'TH-1 (R109 body), KS-1, CC-1'},
    'D10': {
        'model': 'SS1060 at 0.75 V x 3 A = 2.25 W; needs effective RthetaJA <= 33 C/W for Tj <= 125 C at 50 C ambient',
        'requirements': {'copper': 'VPD (anode) and MAIN_IN (cathode) F.Cu pours >= 400 mm2 each, each with >= 8 vias to a '
                                   'same-net B.Cu area >= 300 mm2'},
        'acceptance': 'TH-2'},
    'U4': {
        'model': 'LMR38020 DDA exposed pad = -12V (IC ground), not GND',
        'requirements': {'copper': 'S9.2b beside-pad field (10 vias, spokes, TV_U4_B landing pour) to a -12V area >= '
                                   '300 mm2 on In2 or B.Cu; no GND on the EP; no via in the pad'},
        'acceptance': 'TH-3'},
    'U5': {
        'model': 'TPS16630 PWP exposed pad = GND; <= 0.48 W at 3 A (53 mOhm max)',
        'requirements': {'copper': 'S9.2b beside-pad field (10 vias, spokes, TV_U5_B landing pour) to the In1 GND plane; '
                                   'no via in the pad'},
        'acceptance': 'TH-2 (with D10)'},
}

NETCLASS_WIDTHS_MM = {   # minimum routed widths on 1 oz outer copper (IPC-2152 screen, <= 10 C rise), pours preferred
    'VBUS / VPD / MAIN_IN / VIN (3 A, U5 limit 4.7 A)': 2.5,
    'P12_VOUT / +12V (2.95 A CC limit)': 1.5,
    '-12V (LMR38020 limit ~1.5 A)': 0.8,
    'switch nodes SW1/SW2 (U2), SW (U4)': 'short pours, no thin tracks',
    'P12_ISP / P12_ISN (Kelvin sense pair)': 0.2,
    'AGND_U2 island, FB/COMP, EN_N, N_EN_*': 0.25,
    'logic / status (QUIET class)': 0.25,
}

# ---- S9.2 routing readiness (DeepSeek audit of main, 2026-11-02): the DRC-enforceable half of the contract -----------
# tools/place_s8.py --apply-rules writes exactly three things from this section and nothing else: NETCLASSES into
# hardware/usb-power-45w.kicad_pro, dru_text() into hardware/usb-power-45w.kicad_dru (the two
# R1 J1/SW1 copper-edge allowances stay first, verbatim) and RULE_AREAS onto the board as named rule areas. Edit them
# here, never in KiCad. What DRC cannot express is in POST_ROUTING, measured by tools/check_s8_board.py once the board
# carries copper (PENDING before that, never passed).
#
# Net classes. Every class keeps the 0.2 mm board clearance because the TPS552892 RYQ and TPS16630 PWP lands are
# 0.20-0.25 mm apart; the separations between classes are custom rules (DRC_RULES). width = router default (KiCad
# netclass track width); floor = DRC minimum (custom rule); max = DRC maximum. The contract's current-path minimums for
# the power classes are POST_ROUTING `min_widths`: DRC cannot tell a 3 A path from a divider tap on the same net.
NETCLASSES = {
    'VIN': dict(width=2.5, floor=0.25, patterns=['*/VBUS', '*/VPD', '*/MAIN_IN', 'VIN'],
                what='3 A input power path VBUS -> F1 -> VPD -> D10 -> MAIN_IN -> U5 -> VIN (U5 limit 4.7 A)'),
    'PWR_12V': dict(width=1.5, floor=0.25, patterns=['*/P12_VOUT', '+12V'],
                    what='+12 V force path U2 VOUT -> P12_VOUT bank -> R109 -> +12V headers (2.95 A CC limit)'),
    'PWR_N12V': dict(width=0.8, floor=0.25, patterns=['-12V'], what='-12 V rail and the U4 IC ground (LMR38020 ~1.5 A limit)'),
    'GND': dict(width=0.5, floor=0.25, patterns=['GND'], what='PGND: In1 plane, star at C82.2, TVS/clamp returns'),
    'SWITCH': dict(width=1.0, floor=0.5, patterns=['*U2-SW1*', '*U2-SW2*', '*U4-SW*'],
                   what='U2 SW1/SW2 and U4 SW: short F.Cu pours, no vias, no thin tracks'),
    'SENSE': dict(width=0.2, floor=0.2, max=0.2, patterns=['*/P12_ISP', '*/P12_ISN'],
                  what='R109 Kelvin pair to U2 ISP/ISN: 0.2 mm coupled pair on F.Cu, no vias, no pour'),
    'AGND_U2': dict(width=0.25, floor=0.25, patterns=['*/AGND_U2'],
                    what='isolated U2 analog ground island, fed only from R113 pin 1 (one via pair, one B.Cu link)'),
    'QUIET': dict(width=0.25, floor=0.25,
                  patterns=['*/FB_P12', '*/SS_P12', '*U2-COMP*', '*C83-Pad1*', '*U2-FSW*', '*/FB_N', '*/SS_N12', '*/EN_N',
                            '*/RT_U4', '*/N_EN_*',
                            'Net-(Q1-C)', '/Always-on control*', '/Two output headers*', '/MAIN_LED_OK', '/MAIN_OK',
                            '/N12_OK', '/OV_N', '/P12_OK', '/RUN', '/V20_OK', 'V3V3', '*/CC1', '*/CC2', '*/MAIN_DVDT',
                            '*/MAIN_ILM', '*/MAIN_IMON', '*/MAIN_OV', '*/MAIN_UV', '*/PD_BASE', '*/PD_SENSE', '*/UV_TRIM',
                            'Net-(R28-Pad2)', 'Net-(R29-Pad1)', 'Net-(U1-CFG1)', 'Net-(U1-DM)', 'Net-(D8-A)', 'Net-(D8-K)'],
                  what='converter control (U2 FB/COMP/FSW, U4 FB_N/EN_N/RT, S9.3 soft-start nodes SS_P12/SS_N12, enable '
                       'chain) and every 3.3 V logic, '
                       'monitor, eFuse-control and status net: >= 0.5 mm from switch-node copper'),
}
# Nets left in KiCad's Default class on purpose (0.2 mm): gate-drive and supply nodes that are neither power-path nor
# quiet. Every other functional net matches exactly one class pattern above (tests and the checker verify it).
DEFAULT_NETS = ['Net-(U2-EXTVCC)', 'Net-(U2-BOOT1)', 'Net-(U2-BOOT2)', 'Net-(U4-BOOT)',
                '/USB PD, main eFuse and VIN damper/VPD_U1', 'Net-(C5-Pad1)']
DEFAULT_CLASS = dict(width=0.2, what='Default (DEFAULT): EXTVCC, BOOT1/BOOT2/U4 BOOT, VPD_U1, the R92/C5 damper node')
CLEARANCE_MM = 0.2


def project_netclasses(meta):
    """Write NETCLASSES into a KiCad project dict: the Default class kept, the others after it sorted by name (the order
    pcbnew itself writes, so a native save does not reorder the file), patterns in NETCLASSES order."""
    ns = meta['net_settings']
    base = next(c for c in ns['classes'] if c['name'] == 'Default')
    ns['classes'] = [base] + [{**base, 'name': name, 'track_width': NETCLASSES[name]['width'], 'clearance': CLEARANCE_MM,
                               'priority': list(NETCLASSES).index(name), 'diff_pair_width': 0.2, 'diff_pair_gap': 0.2}
                              for name in sorted(NETCLASSES)]
    ns['netclass_patterns'] = [{'netclass': name, 'pattern': pat} for name, c in NETCLASSES.items() for pat in c['patterns']]
    return meta


# ---- S9.2b: no via-in-pad, standard JLCPCB vias only (owner decisions 2026-11-02) ------------------------------------
# Every via on the board is the plain JLCPCB standard: 0.3 mm drill / 0.6 mm pad through via (F.Cu-B.Cu), tented on
# both sides, not covered, plugged, filled or capped: no POFV / resin fill, no via-in-pad, no 0.2 mm or laser microvia,
# no blind or buried via. No footprint carries a plated hole inside a pad (U4/U5/U9 use the hole-free copies of
# tools/s92_parts.py NO_VIA_IN_PAD). DRC enforces size, type, the hole-to-copper clearance and the via-to-pad clearance
# (drc_rules S92_via_standard / S92_via_hole_to_copper / S92_no_via_in_pad); the RA_NOVIA_* rule areas stop the
# interactive router from placing any via on the exposed pads and the U2 bars; tools/check_s8_board.py checks the board
# setup (tenting/fill flags), every via's own flags, every footprint and the thermal fields below.
VIA_SPEC = {
    'drill_mm': 0.3, 'diameter_mm': 0.6, 'annular_ring_min_mm': 0.15, 'type': 'through, F.Cu-B.Cu',
    'tenting': {'front': True, 'back': True}, 'covering': False, 'plugging': False, 'filling': False, 'capping': False,
    'hole_to_copper_min_mm': 0.3,         # via drill edge to copper of another net (JLCPCB standard DFM, no special order)
    'via_to_pad_min_mm': 0.1,             # via copper to any pad copper, any net: no via in or touching a pad
    'pitch_min_mm': 0.6,                  # via-to-via pitch in the thermal fields (drill edge to drill edge 0.3 mm)
    'jlc': ('JLCPCB standard multilayer process: 0.3/0.6 mm is above the 0.2 mm preferred minimum hole and carries no small-'
            'via surcharge (0.2-0.25 mm holes with < 0.45 mm pads, and 0.1-0.15 mm holes, cost more); via hole-to-hole '
            '>= 0.2 mm; average hole plating 18 um; Via Covering "Tented" is the default order option. Source: '
            'https://jlcpcb.com/capabilities/pcb-capabilities (read 2026-11-02)'),
}
# Thermal via fields: beside-pad vias for the three exposed pads that used to be drilled. In the footprint's own frame
# the exposed-pad copper is centred with its long axis on y; each field is one row of `per_end` vias beyond each short
# end of the copper (ring FIELD_GAP from the copper, VIA_SPEC pitch, centred on x), each via with its own SPOKE_W spoke
# on F.Cu that runs straight into the pad copper by SPOKE_IN, plus a B.Cu landing pour of the exposed-pad net (frame
# half sizes b_cu_half) that ties the via bottoms together and spreads heat on the back. The long sides have no room:
# the pin rows are 0.375 mm (U5), 0.45 mm (U4) and 0.5 mm (U9) from the pad copper. land = the plane the thermal
# model and the post-routing screen land the vias on (U5/U9 In1 PGND; U4's exposed pad is -12V, not GND).
FIELD_GAP, SPOKE_W, SPOKE_IN = 0.15, 0.6, 0.3
THERMAL_VIA_FIELDS = [
    dict(ref='U5', key='PWP20', net='GND', per_end=5, land='In1.Cu', b_cu_half=(4.4, 4.75),
         what='TPS16630 main eFuse PWP exposed pad (pin 21, GND)', old='15 x 0.3 mm in the pad'),
    dict(ref='U4', key='PPAD8', net='-12V', per_end=5, land='B.Cu', b_cu_half=(4.3, 3.8),
         what='LMR38020 DDA exposed pad (pin 9, -12V = IC ground)', old='8 x 0.3 mm in the pad'),
    dict(ref='U9', key='DGN8', net='GND', per_end=3, land='In1.Cu', b_cu_half=(3.6, 2.8),
         what='TPS7A16 DGN exposed pad (pin 9, GND)', old='4 x 0.2 mm in the pad (non-standard drill)'),
]


def field_geometry(field, copper):
    """Vias, spokes and the B.Cu landing rectangle of one thermal field in its footprint's frame (mm), from the exposed-pad
    copper rectangle (x0, y0, x1, y1) of the hole-free footprint (tools/s92_parts.exposed_pad)."""
    x0, y0, x1, y1 = copper
    assert abs(x0 + x1) < 1e-9 and abs(y0 + y1) < 1e-9 and y1 > x1, (field['ref'], 'centred pad, long axis on y')
    n, pitch, r = field['per_end'], VIA_SPEC['pitch_min_mm'], VIA_SPEC['diameter_mm'] / 2
    vias, spokes = [], []
    for side in (-1, 1):
        yv = side * round(y1 + FIELD_GAP + r, 4)
        for i in range(n):
            xv = round((i - (n - 1) / 2) * pitch, 4)
            vias.append((xv, yv))
            spokes.append(((xv, yv), (xv, side * round(y1 - SPOKE_IN, 4))))
    hx, hy = field['b_cu_half']
    return {'vias': vias, 'spokes': spokes, 'spoke_width': SPOKE_W, 'b_cu': [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]}


def to_board(at, pts):
    """Footprint-frame points -> native board mm for a footprint at (x, y, orientation in degrees); KiCad's y-down frame,
    positive orientation counter-clockwise on screen."""
    import math
    x, y, a = at
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [(round(x + px * c + py * s, 4), round(y - px * s + py * c, 4)) for px, py in pts]


def field_items(at):
    """Board items of every thermal field for the parts at {ref: (x, y, orientation)}: vias, F.Cu spokes and the B.Cu
    landing pour, native mm, in a fixed order. tools/place_s8.py writes exactly these, tools/check_s8_board.py compares
    the board with them."""
    out = []
    for f in THERMAL_VIA_FIELDS:
        geo, a = field_geometry(f, exposed_pad(f['key'])['copper']), at[f['ref']]
        out += [{'kind': 'via', 'ref': f['ref'], 'i': i, 'net': f['net'], 'at': p, 'drill': VIA_SPEC['drill_mm'],
                 'diameter': VIA_SPEC['diameter_mm']} for i, p in enumerate(to_board(a, geo['vias']))]
        out += [{'kind': 'spoke', 'ref': f['ref'], 'i': i, 'net': f['net'], 'layer': 'F.Cu', 'start': s, 'end': e,
                 'width': geo['spoke_width']} for i, (s, e) in enumerate(to_board(a, list(pair)) for pair in geo['spokes'])]
        out.append({'kind': 'landing', 'ref': f['ref'], 'net': f['net'], 'layer': 'B.Cu', 'name': f"TV_{f['ref']}_B",
                    'polygon': to_board(a, geo['b_cu'])})
    return out


# Rule areas (KiCad zones with keepout settings), native board frame in mm. blocks = what NO net may put there
# (KiCad keepout flags, enforced by DRC and by the interactive router); the net-scoped limits are drc_rules() that name
# the area. Polygons follow the P2.2 courtyards. tools/check_s8_board.py verifies board == contract and the fit:
# courtyard_in / pads_in parts lie wholly inside, and no pad on the area's layers intersects it unless its part is
# listed (touch = may cross the edge).
RULE_AREAS = [
    dict(name='RA_U2_CELL', layers=['F.Cu', 'B.Cu'], blocks=[],
         courtyard_in=['U2', 'L1', 'C8', 'C9', 'C10', 'C81', 'C82', 'R110', 'R113', 'R9', 'R111', 'C83', 'R8'],
         # R1 (2026-11-04, B223): a superset of the S9.2 polygon, grown round the settled R1 cell placement (R113/R111/
         # C83/R8/R110 courtyards wholly inside); no S9.2 area removed. TP23 (P12_ISN, already a CELL_NETS net) may touch
         touch=['TP23'],
         polygon=[(88.45, 70.5), (100.9, 70.5), (100.9, 69.5), (104.95, 69.5), (104.95, 69.95), (109.9, 69.95),
                  (109.9, 69.15), (113.1, 69.15), (113.1, 70.85), (111.55, 70.85), (111.55, 73.5), (109.15, 73.5),
                  (109.15, 80.0), (106.15, 80.0), (106.15, 83.0), (104.3, 83.0), (104.3, 82.1), (99.3, 82.1),
                  (99.3, 83.15), (88.45, 83.15)],
         why='U2/L1 buck-boost cell (3.4 keep-out): only the cell\'s own nets route or drop vias here; on B.Cu only PGND '
             'and the AGND_U2 link'),
    dict(name='RA_U2_HOT_LOOP', layers=['F.Cu'], blocks=['tracks'], pads_in=['C8', 'C81'],
         polygon=[(106.35, 74.1), (108.85, 74.1), (108.85, 79.6), (106.35, 79.6), (106.35, 78.06), (105.75, 78.06),
                  (105.75, 75.62), (106.35, 75.62)],
         why='input (C8 - VIN bar - PGND bar) and output (C81 - VOUT bar - PGND bar) hot loops east of U2: pour-only '
             'copper, no track of any net, only PGND vias; the DITH/FSW and ISP/ISN side-pin channels stay outside'),
    dict(name='RA_U2_SW_B', layers=['B.Cu'], blocks=['tracks'], courtyard_in=['L1'], pads_in=['C9', 'C10'],
         polygon=[(88.45, 70.5), (99.3, 70.5), (99.3, 73.7), (102.3, 73.7), (102.3, 76.1), (105.75, 76.1),
                  (105.75, 77.6), (102.3, 77.6), (102.3, 81.2), (99.3, 81.2), (99.3, 83.15), (88.45, 83.15)],
         why='B.Cu under L1, the SW1/SW2 pours and the U2 SW bars: the GND pour only, no signal or AGND track'),
    dict(name='RA_L1_IN2', layers=['In2.Cu'], blocks=['tracks', 'pours'], courtyard_in=['L1'],
         polygon=[(88.45, 70.5), (99.3, 70.5), (99.3, 83.15), (88.45, 83.15)],
         why='no In2 copper directly under the L1 body (3.1)'),
    dict(name='RA_L3_IN2', layers=['In2.Cu'], blocks=['tracks', 'pours'], courtyard_in=['L3'],
         polygon=[(136.3, 73.65), (149.0, 73.65), (149.0, 84.55), (136.3, 84.55)],
         why='no In2 copper directly under the L3 body (3.1)'),
    dict(name='RA_TVS_D24', layers=['F.Cu'], blocks=['tracks', 'vias'], pads_in=['D24'],
         polygon=[(99.3, 84.25), (106.3, 84.25), (106.3, 86.75), (99.3, 86.75)],
         why='D24 land (VIN TVS): pads join the VIN pour and the PGND anode copper as solid pours; no track, no via in or '
             'under the land'),
    dict(name='RA_TVS_D26', layers=['F.Cu'], blocks=['tracks', 'vias'], pads_in=['D26'],
         polygon=[(123.9, 67.75), (130.9, 67.75), (130.9, 70.25), (123.9, 70.25)],
         why='D26 land (P12_VOUT TVS): pour-only pad connections, no via in or under the land'),
    dict(name='RA_TVS_D1', layers=['F.Cu'], blocks=['tracks', 'vias'], pads_in=['D1'],
         polygon=[(74.5, 84.3), (81.5, 84.3), (81.5, 86.8), (74.5, 86.8)],
         why='D1 land (VPD TVS): pour-only pad connections, no via in or under the land'),
    dict(name='RA_AGND_ISLAND', layers=['F.Cu'], blocks=['pours'], pads_in=['TP28', 'R113', 'R111', 'C83', 'R9'],
         touch=['C82'],
         polygon=[(97.6, 67.0), (100.3, 67.0), (100.3, 69.7), (109.95, 69.7), (109.95, 73.95), (101.95, 73.95),
                  (101.95, 71.3), (97.6, 71.3)],
         why='AGND_U2 north island and corridor TP28 - R113.1 - C82 gap - U2.17 - C83.2/R9.2: no pour of any net (the '
             'island stays trace-only, PGND/P12_VOUT/+12V pours stop at its edge); only the island\'s own nets route here'),
    dict(name='RA_U2_SENSE_ESCAPE', layers=['F.Cu'], blocks=[], touch=['U2'],
         polygon=[(105.05, 73.9), (106.35, 73.9), (106.35, 75.6), (105.05, 75.6)],
         why='the <= 2 mm pin escape of U2.12/U2.13 into the 0.68 mm channel west of C81.1: sense copper wholly inside '
             'keeps the 0.2 mm board clearance to force copper instead of 0.3 mm'),
    # S9.2b: no via on the pads a router (or a thermal habit) would drill: the four exposed pads and the U2 power bars.
    # Each polygon is exactly the pad copper (pad_cover); S92_no_via_in_pad covers every other pad of the board.
    dict(name='RA_NOVIA_U5_EP', layers=['F.Cu'], blocks=['vias'], touch=['U5'], pad_cover=['U5.21'],
         polygon=[(56.8, 78.6), (63.3, 78.6), (63.3, 82.0), (56.8, 82.0)],
         why='U5 exposed pad: no via in the pad (its 10 thermal vias sit beside both short ends)'),
    dict(name='RA_NOVIA_U4_EP', layers=['F.Cu'], blocks=['vias'], touch=['U4'], pad_cover=['U4.9'],
         polygon=[(129.325, 76.95), (132.275, 76.95), (132.275, 81.45), (129.325, 81.45)],
         why='U4 exposed pad (-12V): no via in the pad (its 10 thermal vias sit beside both short ends)'),
    dict(name='RA_NOVIA_U9_EP', layers=['F.Cu'], blocks=['vias'], touch=['U9'], pad_cover=['U9.9'],
         polygon=[(83.5, 91.2), (86.5, 91.2), (86.5, 93.2), (83.5, 93.2)],
         why='U9 exposed pad: no via in the pad (its 6 thermal vias sit beside both short ends)'),
    dict(name='RA_NOVIA_U1_EP', layers=['F.Cu'], blocks=['vias'], touch=['U1'], pad_cover=['U1.11'],
         polygon=[(83.3, 82.3), (86.6, 82.3), (86.6, 84.4), (83.3, 84.4)],
         why='U1 (CH224A) exposed pad: no via in the pad; ground it beside the pad'),
    dict(name='RA_NOVIA_U2_BARS', layers=['F.Cu'], blocks=['vias'], touch=['U2'],
         pad_cover=['U2.7', 'U2.8', 'U2.9', 'U2.10', 'U2.11'],
         polygon=[(102.3, 75.675), (105.7, 75.675), (105.7, 78.005), (102.3, 78.005)],
         why='U2 VIN/SW1/PGND/SW2/VOUT bars: no via in a bar; the PGND vias sit beside the bar ends (thermal.U2.PGND_vias)'),
]
RULE_AREA_NOTE = 'generated by tools/place_s8.py --apply-rules from tools/s92_contract.py RULE_AREAS; edit there'

# Nets that may route or place vias inside RA_U2_CELL / RA_AGND_ISLAND (full native names). The checker verifies that
# CELL_NETS is exactly the set of nets on the pads of the RA_U2_CELL members (NC pins excluded).
P12 = '/+12 V buck-boost converter/'
CELL_NETS = ['VIN', 'GND', P12 + 'P12_VOUT', '+12V', 'Net-(U2-SW1)', 'Net-(U2-SW2)', 'Net-(U2-BOOT1)', 'Net-(U2-BOOT2)',
             'Net-(U2-EXTVCC)', '/MAIN_OK', 'Net-(U2-FSW)', P12 + 'AGND_U2', P12 + 'FB_P12', 'Net-(U2-COMP)',
             'Net-(C83-Pad1)', P12 + 'P12_ISP', P12 + 'P12_ISN']
ISLAND_NETS = [P12 + 'AGND_U2', 'GND', 'Net-(U2-EXTVCC)', P12 + 'FB_P12', 'Net-(U2-COMP)', 'Net-(C83-Pad1)',
               P12 + 'P12_ISP', P12 + 'P12_ISN', '+12V']
R1_RULES = 'tools/edge-allowances.kicad_dru'   # the two R1 J1/SW1 edge allowances
TVS = ['D1', 'D24', 'D26']                        # SMBJ TVS diodes (D25 BAT54S and D2/D4 SS34 are clamps, POST_ROUTING)
TVS_CLEARANCE_MM = 0.4      # IPC-2221B table 6-1 A6 (uncoated component terminations), 31-50 V: D1 VC 35.5 V, D24 32.4 V
SOLID_PADS = {'U2': ['7', '8', '9', '10', '11'], 'C8': None, 'C81': None, 'L1': None}   # None = every pad


def _not_nets(nets):
    return ' && '.join(f"A.NetName != '{n}'" for n in nets)


def _refs(refs):
    return '(' + ' || '.join(f"A.Reference == '{r}'" for r in refs) + ')'


def drc_rules():
    """(name, layer or None, condition or None, [constraints], why) in file order. KiCad evaluates the file last rule
    first and stops at the first rule that matches a pair for a constraint type, so of two overlapping clearance rules
    the stricter comes later (TVS 0.4 after AGND/SENSE 0.3)."""
    width = lambda c: f"(constraint track_width (min {c['floor']}mm) (opt {c['width']}mm)" + (
        f" (max {c['max']}mm))" if 'max' in c else ')')
    power = ' || '.join(f"A.hasNetclass('{n}')" for n in ('VIN', 'PWR_12V', 'PWR_N12V', 'GND'))
    solid = ' || '.join(f"A.Reference == '{r}'" if pads is None else
                        f"(A.Reference == '{r}' && (" + ' || '.join(f"A.Pad_Number == '{p}'" for p in pads) + '))'
                        for r, pads in SOLID_PADS.items())
    c = NETCLASSES
    v = VIA_SPEC
    return [
        # S9.2b first in the file: a later, more specific disallow rule (switch nodes, sense pair, U2 cell) still applies
        ('S92_via_standard', None, "A.Type == 'Via'",
         [f"(constraint via_diameter (min {v['diameter_mm']}mm) (opt {v['diameter_mm']}mm) (max {v['diameter_mm']}mm))",
          f"(constraint hole_size (min {v['drill_mm']}mm) (opt {v['drill_mm']}mm) (max {v['drill_mm']}mm))",
          f"(constraint annular_width (min {v['annular_ring_min_mm']}mm))",
          '(constraint disallow micro_via blind_via buried_via)'],
         'S9.2b: every via is the plain JLCPCB 0.3/0.6 mm through via (annular ring 0.15 mm); no other size, no microvia, '
         'no blind or buried via'),
        ('S92_via_hole_to_copper', None, "A.Type == 'Via'",
         [f"(constraint hole_clearance (min {v['hole_to_copper_min_mm']}mm))"],
         'S9.2b: via drill >= 0.3 mm from copper of any other net (JLCPCB standard DFM, no special order)'),
        ('S92_In1_solid_PGND', 'In1.Cu', None, ['(constraint disallow track)'],
         'In1 is the solid PGND plane: no track of any net (3.1)'),
        ('S92_power_width_floor', None, power, ['(constraint track_width (min 0.25mm))'],
         'no logic-width track on a power net; the current-path minimums are POST_ROUTING min_widths'),
        ('S92_QUIET', None, "A.hasNetclass('QUIET')", [width(c['QUIET'])], 'control and logic tracks >= 0.25 mm'),
        ('S92_SWITCH', None, "A.hasNetclass('SWITCH')", [width(c['SWITCH']), '(constraint disallow via)'],
         'switch nodes: F.Cu pours, no vias, no thin tracks (3.4/3.5)'),
        ('S92_SENSE_pair', None, "A.hasNetclass('SENSE')",
         [width(c['SENSE']), '(constraint diff_pair_gap (min 0.2mm) (opt 0.2mm) (max 0.3mm))',
          '(constraint disallow via zone)'], 'Kelvin pair: 0.2 mm, coupled gap 0.2-0.3 mm, no via, no pour (3.7)'),
        ('S92_SENSE_F_Cu_only', None, "A.hasNetclass('SENSE') && A.Layer != 'F.Cu'", ['(constraint disallow track)'],
         'the sense pair runs on F.Cu only'),
        ('S92_AGND_U2_island', None, "A.hasNetclass('AGND_U2')",
         [width(c['AGND_U2']), '(constraint via_count (max 2))', '(constraint disallow zone)'],
         'AGND_U2: trace-only, at most one via pair, no pour on any layer (3.3)'),
        ('S92_AGND_U2_no_inner_copper', 'inner', "A.hasNetclass('AGND_U2')", ['(constraint disallow track)'],
         'no AGND_U2 track on In1/In2'),
        ('S92_AGND_U2_B_Cu_link', 'B.Cu', "A.hasNetclass('AGND_U2')",
         ['(constraint track_width (min 0.25mm) (opt 0.25mm) (max 0.25mm))'], 'the single B.Cu AGND_U2 link is 0.25 mm'),
        ('S92_AGND_U2_to_PGND', None, "A.hasNetclass('AGND_U2') && B.hasNetclass('GND')",
         ['(constraint clearance (min 0.3mm))'],
         'AGND_U2 copper keeps 0.3 mm from every PGND item; the only bridge is the R113 body (pads 0.85 mm apart)'),
        ('S92_SENSE_to_force', None, ("A.hasNetclass('SENSE') && B.hasNetclass('PWR_12V') && !(A.Type == 'Pad' && "
                                      "B.Type == 'Pad' && A.Reference == B.Reference) && "
                                      "!A.enclosedByArea('RA_U2_SENSE_ESCAPE')"),
         ['(constraint clearance (min 0.3mm))'],
         'sense pair >= 0.3 mm from P12_VOUT/+12V force copper; exempt: the R109/U2 land gaps and the U2 pin escape'),
        ('S92_QUIET_to_SWITCH', None, "A.hasNetclass('QUIET') && B.hasNetclass('SWITCH')",
         ['(constraint clearance (min 0.5mm))'], 'quiet nets >= 0.5 mm from switch-node copper (3.4/3.5)'),
        ('S92_TVS_pad_stress', None, f"A.Type == 'Pad' && {_refs(TVS)}",
         [f'(constraint clearance (min {TVS_CLEARANCE_MM}mm))'],
         'every D1/D24/D26 pad >= 0.4 mm from copper of any other net (the clamp voltage appears across these gaps)'),
        ('S92_U2_cell_own_nets', None, f"A.intersectsArea('RA_U2_CELL') && {_not_nets(CELL_NETS)}",
         ['(constraint disallow track via)'], 'no foreign-net track or via inside the U2/L1 cell (3.4)'),
        ('S92_U2_cell_B_Cu', 'B.Cu', ("A.intersectsArea('RA_U2_CELL') && !A.hasNetclass('GND') && "
                                      "!A.hasNetclass('AGND_U2')"), ['(constraint disallow track)'],
         'on B.Cu inside the cell only the PGND pour and the AGND_U2 link (3.1)'),
        ('S92_U2_hot_loop_vias', None, "A.intersectsArea('RA_U2_HOT_LOOP') && !A.hasNetclass('GND')",
         ['(constraint disallow via)'], 'only PGND vias inside the hot loops; C8/C81 connect on F.Cu (3.4)'),
        ('S92_AGND_island_nets', None, f"A.intersectsArea('RA_AGND_ISLAND') && {_not_nets(ISLAND_NETS)}",
         ['(constraint disallow track via)'], 'only the island\'s own nets inside RA_AGND_ISLAND'),
        ('S92_no_via_in_pad', None, "A.Type == 'Via' && B.Type == 'Pad'",
         [f"(constraint physical_clearance (min {v['via_to_pad_min_mm']}mm))"],
         'S9.2b: no via in or touching any pad, any net, SMD or THT (owner: no via-in-pad anywhere); no footprint carries a '
         'plated hole in a pad either (tools/check_s8_board.py)'),
        ('S92_TVS_pads_solid', None, f"A.Type == 'Pad' && {_refs(TVS)}", ['(constraint zone_connection solid)'],
         'TVS pads join their pours solid, no thermal spokes'),
        ('S92_hot_loop_pads_solid', None, f"A.Type == 'Pad' && ({solid})", ['(constraint zone_connection solid)'],
         'U2 VIN/SW/PGND/VOUT bars, C8, C81 and L1 join their pours solid'),
    ]


DRU_HEADER = '''
# ---- S9.2 / P2.2 routing contract: GENERATED by tools/place_s8.py --apply-rules from tools/s92_contract.py ----
# Do not edit by hand. Net classes live in usb-power-45w.kicad_pro, the RA_* rule areas on the board.
# Rules are evaluated last first; of two overlapping clearance rules the stricter comes later.
# docs/design/routing-notes.md section 3.12 explains every rule.
'''


def dru_text(r1_text):
    """The board's .kicad_dru: the R1 J1/SW1 copper-edge allowances (verbatim apart from the old 'ONLY custom rules'
    header line) followed by the generated routing-contract rules."""
    assert r1_text.startswith('(version 1)\n'), 'R1 rules header changed'
    head = r1_text.replace('allowances. The ONLY custom rules.', 'allowances: the ONLY copper-edge exceptions.')
    out = [head.rstrip('\n') + '\n', DRU_HEADER]
    for name, layer, cond, cons, why in drc_rules():
        out.append(f'\n# {why}\n(rule "{name}"\n')
        if layer:
            out.append(f'\t(layer {layer})\n' if layer in ('inner', 'outer') else f'\t(layer "{layer}")\n')
        if cond:
            out.append(f'\t(condition "{cond}")\n')
        out.append(''.join(f'\t{x}\n' for x in cons[:-1]) + f'\t{cons[-1]})\n')
    return ''.join(out)


# Board stack-up the routing contract assumes (JLC04161H-7628, the board's own stack-up): checked on the board.
STACKUP = {'layers': 4, 'thickness_mm': 1.6, 'copper_um': {'F.Cu': 35, 'In1.Cu': 15.2, 'In2.Cu': 15.2, 'B.Cu': 35},
           'dielectric_mm': [0.2104, 1.065, 0.2104],
           'jlc': 'JLC04161H-7628, FR4 Tg155, 1 oz outer / 0.5 oz inner, HASL (SnPb)'}

# Via-in-pad decision (audit should-fix 3), resolved by the owner on 2026-11-02 as PROHIBITED (overrides the S9.2 audit
# round's POFV proposal). check_s8_board.py -> pre_routing_checklist.via_in_pad / thermal_vias proves it on the board.
VIA_IN_PAD = {
    'decision': ('PROHIBITED: no via in any pad and no plated hole in any footprint pad, anywhere on the board (owner '
                 'decision 2026-11-02). Standard JLCPCB vias only (VIA_SPEC): 0.3 mm drill / 0.6 mm pad through vias, '
                 'tented, unfilled; no POFV, no resin fill, no copper cap, no 0.2 mm or laser microvia, no blind/buried via'),
    'footprints': {f['ref']: {'part': f['what'], 'before': f['old'], 'after': 'no hole in any pad',
                              'footprint': f'USBPOWER45:{_NO_VIA[f["key"]][1]}',
                              'pinned_S7_source_unchanged': f'USBPOWER45:{_NO_VIA[f["key"]][0]}'}
                   for f in THERMAL_VIA_FIELDS},
    'replacement': ('beside-pad thermal fields (THERMAL_VIA_FIELDS): one row of standard vias beyond each short end of '
                    'the exposed pad (ring 0.15 mm from the pad copper, 0.6 mm pitch), each via with its own 0.6 mm F.Cu '
                    'spoke into the pad copper, and a B.Cu landing pour of the pad net under the part; U5 10 vias (was 15 '
                    'in the pad), U4 10 (was 8), U9 6 (was 4 x 0.2 mm). C2, R24/C3 and R13/R14/R15 moved 0.45 / 0.45 / '
                    '0.25 mm to make room. The long sides have no room (pin rows 0.375-0.5 mm from the pad copper)'),
    'why': ('Owner decision: a via in a pad needs a fill/cap order option or wicks solder down the barrel (exposed-pad '
            'voids, lifted parts); standard tented vias beside the pad need neither and pass JLCPCB standard DFM. The '
            'cost is a longer heat path: the heat now crosses the outer copper from the solder window to the via rows '
            '(calcs.json thermal_contract.via_change: U5 +DeltaR and Tj at the rated 3 A input against 125 C, U2 '
            'unchanged because its pads were never drilled, U4/U9 DeltaR recorded)'),
    'order': ('Standard JLCPCB order, nothing exotic: Via Covering = "Tented" (the default); no "Epoxy Filled & Capped" '
              '/ POFV option and no via-in-pad remark; minimum via 0.3/0.6 mm (no small-hole surcharge); 4 layers, '
              'JLC04161H-7628, 1 oz outer / 0.5 oz inner. Pre-order checklist: confirm U4, U5 and U9 are the '
              '*_NoViaInPad footprints with no plated hole in their pads, that every via in the drill file is 0.3 mm and '
              'that no hole is below 0.3 mm'),
    'not_chosen': ('Keeping the in-pad holes with JLCPCB "Epoxy Filled & Capped" (POFV): rejected by the owner (an order '
                   'option with its own surcharge on 4-layer boards). Ordering the in-pad holes open: rejected '
                   '(solder wicking). Copper-only pad extensions with holes outside the paste but inside pad copper: '
                   'rejected, a hole would still sit in pad copper'),
    'sources': ['https://jlcpcb.com/capabilities/pcb-capabilities'],
}

# Exposed-pad-to-plane conduction model for the via change (S9.2b). Steady state; heat enters the board copper uniformly
# over the solder window (the package's exposed pad) and leaves into the landing plane, treated as isothermal (it is
# the same downstream board in both arrangements, so it cancels in DeltaR). Paths in parallel: (1) each via row: lateral
# conduction in the 35 um outer copper from the solder-window edge to the row (exposed-pad copper width, then the spoke
# strip beyond the pad edge) plus the row's barrels in parallel (drill 0.3 mm, 18 um JLCPCB average plating) down to the
# landing layer; vias inside the window have no lateral term; (2) the prepreg under the copper into In1 (any net). Every
# watt of the exposed pad is assumed to take this path (leads and top copper ignored), so DeltaR is an upper bound on the
# change of RthetaJA.
THERMAL_MODEL = {'k_cu_W_mK': 385.0, 'k_fr4_W_mK': 0.30, 'plating_um': 18.0,
                 'basis': ('copper 385 W/m K (electro-deposited), FR4 7628 through-plane 0.30 W/m K, JLCPCB average hole '
                           'plating 18 um, board STACKUP thicknesses; upper bound (all exposed-pad heat through this path)')}


def layer_depth_mm(layer):
    """Distance from the F.Cu mid-plane to the mid-plane of a copper layer of the contract STACKUP."""
    names = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')
    cu = [STACKUP['copper_um'][n] / 1000 for n in names]
    k = names.index(layer)
    return round(cu[0] / 2 + sum(STACKUP['dielectric_mm'][:k]) + sum(cu[1:k]) + cu[k] / 2, 6) if k else 0.0


def ep_path(ep, vias, drill, land, spoke_width=None):
    """Exposed-pad copper -> landing plane thermal resistance (K/W) of one arrangement (THERMAL_MODEL), frame mm. vias
    beyond the pad copper (a field) are fed through a spoke strip of n x spoke_width; holes in the pad have none."""
    import math
    m = THERMAL_MODEL
    x0, y0, x1, y1 = ep['copper']
    wx, wy = ep['window'][2], ep['window'][3]
    sheet = 1 / (m['k_cu_W_mK'] * STACKUP['copper_um']['F.Cu'] * 1e-6)         # K/W per square of outer copper
    r_out = drill / 2 * 1e-3
    r_in = r_out - m['plating_um'] * 1e-6
    barrel = layer_depth_mm(land) * 1e-3 / (m['k_cu_W_mK'] * math.pi * (r_out ** 2 - r_in ** 2))
    rows = {}
    for x, y in vias:
        assert abs(x) <= wx + 1e-9, ('via beside the window across the long axis', x, y)
        rows.setdefault('window' if abs(y) <= wy + 1e-9 else round(y, 4), []).append((x, y))
    out, g, area = [], 0.0, (x1 - x0) * (y1 - y0)
    for key, vs in rows.items():
        n = len(vs)
        lateral = 0.0
        if key != 'window':
            d = abs(key)
            beyond = max(0.0, d - y1)
            assert not beyond or spoke_width, ('a via beyond the pad copper needs a spoke', key)
            lateral = sheet * ((min(d, y1) - wy) / (x1 - x0) + (beyond / (n * spoke_width) if beyond else 0.0))
            area += n * spoke_width * beyond if beyond else 0.0
        area -= sum(math.pi * (drill / 2) ** 2 for x, y in vs if abs(y) <= y1)       # holes in the pad copper
        r = lateral + barrel / n
        g += 1 / r
        out.append({'row': 'in the solder window' if key == 'window' else f'y {key:+g} mm', 'vias': n,
                    'lateral_K_W': round(lateral, 2), 'barrels_K_W': round(barrel / n, 2), 'row_K_W': round(r, 2)})
    diel = STACKUP['dielectric_mm'][0] * 1e-3 / (m['k_fr4_W_mK'] * area * 1e-6)
    return {'rows': out, 'barrel_K_W_per_via': round(barrel, 2), 'dielectric_K_W': round(diel, 2),
            'total_K_W': round(1 / (g + 1 / diel), 2)}


def thermal_via_model():
    """Per thermal field: the in-pad arrangement it replaces (pinned S7 footprint) and the beside-pad field, with
    DeltaR = R(new) - R(old) (THERMAL_MODEL, upper bound on the RthetaJA change)."""
    out = {}
    for f in THERMAL_VIA_FIELDS:
        old, new = exposed_pad(f['key'], copy=False), exposed_pad(f['key'])
        assert old['copper'] == new['copper'] and old['window'] == new['window'] and not new['holes'], f['ref']
        drills = {d for _, _, d in old['holes']}
        assert len(drills) == 1, f['ref']
        geo = field_geometry(f, new['copper'])
        before = ep_path(old, [(x, y) for x, y, _ in old['holes']], drills.pop(), f['land'])
        after = ep_path(new, geo['vias'], VIA_SPEC['drill_mm'], f['land'], geo['spoke_width'])
        out[f['ref']] = {'pad': f"{f['ref']}.{new['pad']}", 'net': f['net'], 'land': f['land'],
                         'in_pad_holes_before': len(old['holes']), 'beside_pad_vias_after': len(geo['vias']),
                         'before': before, 'after': after,
                         'delta_R_K_W': round(after['total_K_W'] - before['total_K_W'], 2)}
    return out


PRE_ROUTING = [   # (id, what must be true before routing starts); check_s8_board.py -> pre_routing_checklist
    ('netclasses', 'the 8 contract net classes are in the project and every functional net is in exactly one of them '
                   '(DEFAULT_NETS on purpose in Default)'),
    ('drc_rules', 'the board .kicad_dru equals dru_text(): the R1 edge allowances plus every S92_* rule'),
    ('rule_areas', 'the board carries exactly the RULE_AREAS (names, layers, keepout flags, polygons), each holding its '
                   'listed parts and no other part\'s pad'),
    ('via_in_pad', 'via-in-pad PROHIBITED (S9.2b): no footprint has a plated hole inside a pad (U4/U5/U9 are the '
                   'hole-free *_NoViaInPad copies), no via touches a pad or its mask opening, every via is the standard '
                   '0.3/0.6 mm through via without per-via tenting/fill overrides and the board setup is tented and unfilled'),
    ('thermal_vias', 'the board carries exactly the THERMAL_VIA_FIELDS (U5 10, U4 10, U9 6 vias beside the exposed pads, '
                     'one F.Cu spoke each into the pad copper, one B.Cu landing pour each) on the parts\' actual positions'),
    ('stackup', 'stack-up and copper weights are the contract STACKUP (4 layers, 1.6 mm, 35/15.2/15.2/35 um copper, '
                '0.2104/1.065/0.2104 mm dielectric)'),
    ('test_pads', 'all 27 test pads are bare F.Cu with a mask opening and no paste'),
    ('placement', 'placement, local-loop, ground-split and routing-contract screens pass (P2.2 with the S9.2b moves of '
                  'C2, R24/C3 and R13-R15)'),
]

# What DRC cannot express, measured by tools/check_s8_board.py once the board carries copper (PENDING before that).
POST_ROUTING = {
    'tvs.D24': 'D24.1 sits in the F.Cu VIN pour island that holds C8.1 and the C6/C7/C77/C78 bank; >= 3 GND vias '
               'within 1.5 mm of the D24.2 pad edge',
    'tvs.D26': 'D26.1 in an F.Cu P12_VOUT pour island with the C14/C79/C80 bank, or >= 2 vias from it to the B.Cu '
               'P12_VOUT area; >= 3 GND vias within 1.5 mm of D26.2',
    'tvs.D1': 'D1.1 in the F.Cu VPD pour island with D10.2; >= 3 GND vias within 1.5 mm of D1.2',
    'tvs.D25': 'one GND via within 1.5 mm of D25.1 (pins 2/3 join VIN: native unconnected check)',
    'ground.agnd_link': 'AGND_U2 has <= 1 track run on B.Cu (the link) and its copper joins only the 7 member pads '
                        '(via count and width: DRC)',
    'kelvin.sense_routing': 'each sense track leaves R109 pads 2/3 on the +y edge within 0.6 mm of the inner end; '
                            'the pair is coupled (<= 0.3 mm gap) except <= 2 mm at U2 and the TP22/TP23 branches',
    'thermal.U2.In1': 'In1 is one GND piece; within 15 mm of the U2 centre its only holes are via antipads',
    'thermal.U2.PGND_vias': '>= 10 GND vias 0.3/0.6 mm with centres <= 4 mm outside the U2 outline, none in a pad',
    'thermal.U2.VIN_area': 'one F.Cu VIN island >= 120 mm2 holding U2.7, C8.1, C6/C7/C77/C78 and D24.1 with >= 6 '
                           'vias to an In2 VIN island >= 300 mm2',
    'thermal.U2.VOUT_area': 'one F.Cu P12_VOUT island >= 150 mm2 holding U2.11, C81.1, C11-C14, C79, C80 and R109.1 '
                            'with >= 6 vias to a B.Cu P12_VOUT island >= 200 mm2',
    'thermal.U2.B_Cu_GND': 'the B.Cu GND island under U2 is >= 600 mm2 with >= 20 GND vias',
    'thermal.R109.force_copper': 'P12_VOUT and +12V F.Cu copper >= 150 mm2 each within 10 mm of R109 pads 1/4, '
                                 'each with >= 3 same-net vias',
    'thermal.D10.copper': 'VPD and MAIN_IN F.Cu islands at D10 >= 400 mm2 each with >= 8 vias to a same-net B.Cu '
                          'island >= 300 mm2',
    'thermal.U4.copper': 'the 10 U4 field vias land in one -12V island >= 300 mm2 on In2 or B.Cu (the TV_U4_B landing '
                         'pour may be grown into it)',
    'thermal.U5.copper': 'every U5 field via lands in the In1 GND fill',
    'thermal.U9.copper': 'every U9 field via lands in the In1 GND fill',
    'min_widths': 'current-path tracks meet the class minimum (VIN 2.5, PWR_12V 1.5, PWR_N12V 0.8 mm); a track whose '
                  'chain reaches only tap pads (dividers, test pads, monitors, clamps) needs only the 0.25 mm floor',
}
# min_widths: class minimum on current paths; a track chain that reaches only tap pads (no load current) needs the
# tap minimum instead (routing-notes 1 and 3.4: power test pads >= 0.8 mm, TP20 >= 1.0 mm, R92.1 >= 0.5 mm).
CURRENT_MIN_MM = {'VIN': 2.5, 'PWR_12V': 1.5, 'PWR_N12V': 0.8}
TAP_MIN_MM = {'R109': None, 'R92': 0.5, 'TP20': 1.0, 'TP24': 0.8, 'TP25': 0.8, 'TP26': 0.8,
              **{r: 0.25 for r in ('U1', 'U9', 'U18', 'U20', 'Q1', 'Q3', 'D11', 'D25', 'C46', 'C57', 'C65')}}
TAP_PREFIX_MIN_MM = {'R': 0.25, 'TP': 0.25}       # dividers, the other test pads


def tap_min(ref):
    """Width a track chain needs when it reaches only this part's pads; None = the part carries load current."""
    if ref in TAP_MIN_MM:
        return TAP_MIN_MM[ref]
    return TAP_PREFIX_MIN_MM.get(''.join(ch for ch in ref if ch.isalpha()))


def contract():
    return {'revision': 'S9.3 / P2.3', 'status': ('routing contract for the unrouted P2.3 board (S9.2b: no via-in-pad, '
                                                  'standard JLCPCB vias, beside-pad thermal fields placed); DRC-enforced '
                                                  'items (netclasses, drc_rules, rule_areas) are in the native project, '
                                                  'rules file and board; pre-routing items checked by '
                                                  'tools/check_s8_board.py; post_routing items PENDING until routed'),
            'test_points': TEST_POINTS, 'kept_diagnostic_pads': KEPT_DIAGNOSTIC, 'proximity': [
                {'from': f'{a}.{b}', 'to_any': [f'{r}.{p}' for r, p in to], 'limit_mm': lim, 'why': why}
                for (a, b), to, lim, why in PROXIMITY],
            'ground': GROUND, 'kelvin': KELVIN, 'thermal': THERMAL, 'min_widths_mm': NETCLASS_WIDTHS_MM,
            'netclasses': {**{n: {k: v for k, v in c.items()} for n, c in NETCLASSES.items()},
                           'Default': {**DEFAULT_CLASS, 'nets': DEFAULT_NETS}, 'clearance_mm': CLEARANCE_MM},
            'drc_rules': [{'name': n, 'layer': l, 'why': w} for n, l, _, _, w in drc_rules()],
            'rule_areas': [{k: (list(map(list, v)) if k == 'polygon' else v) for k, v in a.items()} for a in RULE_AREAS],
            'stackup': STACKUP, 'via_in_pad': VIA_IN_PAD, 'via_spec': VIA_SPEC,
            'thermal_via_fields': [{**f, 'spoke_width_mm': SPOKE_W, 'spoke_into_pad_mm': SPOKE_IN, 'ring_gap_mm': FIELD_GAP,
                                    'frame': field_geometry(f, exposed_pad(f['key'])['copper'])}
                                   for f in THERMAL_VIA_FIELDS],
            'thermal_via_model': {**THERMAL_MODEL, 'fields': thermal_via_model()},
            'pre_routing_checklist': [{'id': i, 'must_hold': t} for i, t in PRE_ROUTING],
            'post_routing': POST_ROUTING, 'doc': NOTES}


# Acceptance-test IDs as written in this contract, tools/review_s8.py and the notes (S1..S4 share one register row).
TEST_ID = re.compile(r'\b(?:CL|TH|LS|IN|EMI|GS|KS|CC|EN|POR|HDR)-\d\b|\bT[12]\b|\bS[1-4]\b')


def referenced_ids(*texts):
    """Acceptance-test IDs used in free text (S1..S4 map to the shared 'S1-S4' row)."""
    return {'S1-S4' if i[0] == 'S' else i for t in texts for i in TEST_ID.findall(t)}


def notes_index(text):
    """routing-notes.md read back: {'pads': {TP: net}, 'duplicate_pads': [...], 'ids': {...}} from its test-pad table
    rows ('| TPn | `net` |') and the bold first cells of its register rows ('| **ID** ...')."""
    pads, dup = {}, []
    for ref, net in re.findall(r'^\| (TP\d+) \| `([^`]+)`', text, re.M):
        if ref in pads:
            dup.append(ref)
        pads[ref] = net
    ids = set()
    for line in re.findall(r'^\| \*\*.*$', text, re.M):
        first = line.split(' | ')[0]
        ids |= {i.replace('\u2013', '-') for i in re.findall(r'\*\*([^*]+)\*\*', first)}
    return {'pads': pads, 'duplicate_pads': dup, 'ids': ids}


def contract_ids():
    """Every acceptance-test ID this contract refers to."""
    return referenced_ids(*(t['measure'] + ' ' + t['limit'] for t in TEST_POINTS),
                          *(v['acceptance'] for v in THERMAL.values()))
