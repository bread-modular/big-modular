"""S8 review record: native findings, exact parity, test results, placement/mechanics/sourcing summaries and the
SHA-256 of every source and artifact, assembled from fresh reports (no hand-copied numbers).

  python3 -B tools/review_s8.py --check research/s93/check --tests-log research/s93/tests.log \
      --out docs/s8-single/review-s93.json

--check is a NEW native check directory of the shared tool (opt/kicad-tools/kicad_tools.py check, summary.json),
--tests-log the verbose unittest output of `python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v`.
Read-only apart from --out. S9.0 replaces the S8.5 record (review-s85.json, kept in git history at 5a3a686). Only files
git TRACKS are hashed (S8.5 item C: no git-ignored *.kicad_prl, nothing under research/; S9.0: membership is checked with
`git ls-files`, so stage new sources before writing the record); the check directory and the tests log are local evidence
(git-ignored research/), recorded by path and summary, never hashed. S9.0 also hashes the pinned TPS552892-Q1 part file
(tools/s90_parts.py), every footprint the single board uses and the single-board panel. S9.2 also records the routing
notes (docs/s8-single/routing-notes.md, hashed with the other artifacts): their test-pad table must list exactly the
board's test pads and their uncertainty register must define every acceptance-test ID the contract and OPEN_GATES use.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
import s92_contract  # noqa: E402
REVISION = 'S9.3 / P2.3'
TRACKED_KICAD = ('.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sym')   # *.kicad_prl is git-ignored
S7_R3 = sorted(str(p.relative_to(MODULE)) for p in (MODULE / 'hardware').glob('*.kicad_*') if p.suffix in TRACKED_KICAD)
PANEL = ['panels/front-pcb/usb-power-45w-single-panel.kicad_pcb', 'panels/front-pcb/usb-power-45w-single-panel.kicad_pro']
SOURCES = (sorted(f'hardware/single/{p.name}' for p in (MODULE / 'hardware/single').glob('*.kicad_*')
                  if p.suffix in TRACKED_KICAD)
           + ['hardware/single/fp-lib-table', 'hardware/single/sym-lib-table'] + PANEL
           + [f'tools/{n}.py' for n in ('build_s8', 'build_s8_assembly', 'build_s8_board', 'build_s8_panel',
                                        'check_s8_board', 'circuit_s8', 'hierarchy_s8', 'mechanics_s8', 'place_s8',
                                        'render_s8', 'review_s8', 's8_calcs', 's8_mechanical', 's8_sourcing', 's90_parts',
                                        's91_analysis', 's92_contract', 's92_netlist', 's92_parts', 'test_s8', 'verify_s8')])
CHANGELOG = [
    ('1 D24 / OVP', 'D24 SMBJ16A -> SMBJ20A (Littelfuse C151257) and U5 OVP R24 6.8k -> 9.1k: OVP rises at 17.30-19.44 V, '
                    'below D24 VR 20 V and VBR 22.2 V (21.70 V at 0 C), so U5 removes a sustained overvoltage before D24 '
                    'conducts; VC 32.4 V at 18.6 A < 42/1.15 V (U2) and +14.02 V < 50 V (C25/C26). SMBJ18A/20A/24A x old/new '
                    'divider evaluated in calcs vin_clamp; 1 A x 32.4 V x 20 ms = 0.648 J against 69.8 W at 20 ms / 50 C.'),
    ('2 PGND star', 'C82.2 on PGND (TI SLVSGT7 8.4.1 items 6/7); R113 pin 2 lands on it, pin 1 feeds AGND_U2; R113 is the '
                    'only part on both nets (netlist, board and verifier checks; C82.2-on-AGND is now a negative control).'),
    ('3 Kelvin R109', 'TA-I RLM12 18 mOhm (C393095) on a 4-terminal split land: force 1/4 on P12_VOUT/+12V, sense 2/3 on '
                      'P12_ISP/P12_ISN (U2 pins 12/13 only); 0.2 % residual in the 2.615-2.946 A CC band.'),
    ('4 Derived tests', 'U4 enable truth table and 3 A source timelines now derive from the netlist (s92_netlist): traced '
                        'EN/PNP/NMOS-chain structure, tolerance bounds, physical 3 A plant with netlist UVLO/CC/banks/enables; '
                        'negative controls (Q1 emitter on +12V, R115 open or < 50k, gate bypass, U5 SHDN off RUN, S8.4 '
                        'arming, ISP tied to ISN) fail.'),
    ('5 N_EN_RETURN', 'R115 100k to PGND: defined default, Q1 VEB <= 0.18 V with Q15 as a source follower; TP30.'),
    ('6 Thermal basis', 'Copper/via requirements for U2, R109, D10, U4, U5 in placement.json routing_contract; rating '
                        'labelled conditional on them and on TH-1..TH-3; allowed U2 RthetaJA 55.8 C/W at the CC limit.'),
    ('Routing', 'Ten 1.5 mm acceptance pads (TP20, TP22-TP30), docs/s8-single/routing-notes.md (test-point table, '
                'uncertainty register, routing constraints), netclasses in the project, D26 moved, R113 turned.'),
    ('Routing notes', 'docs/s8-single/routing-notes.md written: 27 test pads with location, pad, keep-out, measurement '
                      'and limit; 19 uncertainty-register rows with assumption, risk, pad, procedure, pass limit and '
                      'respin/BOM disposition; routing constraint list. Contract made routable (place_s8.py '
                      '--refresh-contract, board unchanged): one AGND_U2 via pair + B.Cu trace allowed (F.Cu cannot join '
                      'U2.17 and U2.5 across the power fan-out), U2 PGND vias within 4 mm, D26/TP20 branch, sense escape.'),
    ('S9.2b DRC contract', 'DeepSeek audit Blocker 2: the routing contract is enforced by native DRC where DRC can express '
                           'it: net classes VIN, PWR_12V, PWR_N12V, GND, SWITCH, SENSE, AGND_U2, QUIET (+ Default) in the '
                           'project, the S92_* custom rules in the .kicad_dru (AGND_U2 to PGND, sense to force, quiet to '
                           'switch, TVS pad clearance, U2 cell/hot-loop/island nets, widths, In1 solid) and the RA_* rule '
                           'areas on the board; the rest is the pre-routing checklist and the post-routing machine screen '
                           'of tools/check_s8_board.py (PENDING until routed, never passed).'),
    ('S9.2b via policy', 'Owner: NO via-in-pad anywhere, standard JLCPCB vias only (0.3 mm drill / 0.6 mm pad, tented, '
                         'unfilled; no POFV/resin fill, no 0.2 mm or laser microvia). U4/U5/U9 use hole-free copies of '
                         'their pinned lands (*_NoViaInPad; the S7 files stay drilled for the S7 boards). Beside-pad thermal '
                         'fields replace the in-pad holes: one via row beyond each short end of each exposed pad, a 0.6 mm '
                         'F.Cu spoke per via and a B.Cu landing pour (TV_U5_B/TV_U4_B/TV_U9_B); C2 and R24/C3 moved '
                         '0.45 mm, R13-R15 0.25 mm. DRC rules S92_via_standard, S92_via_hole_to_copper and '
                         'S92_no_via_in_pad (any pad) and the RA_NOVIA_* areas stop a router from drilling a pad.'),
    ('S9.3 strict 3 A start', 'Neither converter has a soft-start pin, so each gets an FB-injection soft start: C84 220n / '
                              'D27 BAV199 / R116 470k on U2 FB_P12 (tau = R8 x C84 = 15 ms nominal, 4.8-18.9 ms) and C85 '
                              '470n / D28 / R117 470k on U4 FB_N (47 ms nominal, 15-59 ms). U4 is enabled only after +12V '
                              'is good: Q16 tops the U4 enable sink chain, its gate driven from P12_OK through R118 100k / '
                              'C86 100n (U4 EN 3.4-18.3 ms after P12_OK), R119 220k defines N_EN_MID. Strict 3.00 A '
                              'source, published 33 W, 0.44 mF per rail: one attempt, zero U5 drop-outs, input <= 2.955 A '
                              'in every case (startup_qualification); negative controls (D27 open, D28 open, Q16 gate on '
                              'V3V3) fail. FB_P12 is a labelled net now (QUIET class, U2 cell/island net lists).'),
    ('S9.3 placement P2.3', 'The ten S9.3 parts sit in free pockets of the P2.2 floor plan (no P2.2 part moved): D27/C84/'
                            'R116 and Q16/R118/C86 between the U2 VIN bank and U10/U12, D28/C85/R117 by C33, R119 under U11. '
                            'Interim: the FB_P12 / FB_N injection links are 13-15 mm until the U2 sense-escape re-placement.'),
]
OPEN_GATES = [   # S9.2: post-prototype acceptance tests (routing-notes.md), not design blockers
    'Routing itself (P2.3 is unrouted; the contract items are checked after routing; the S9.3 FB-injection parts are in '
    'interim pockets)',
    'S1-S4 source/startup qualification on the bench: the netlist-derived plant starts from a strict 3.00 A source in one '
    'attempt (S9.3 soft starts + U4 sequencing, peak 2.955 A); S1 confirms it with a current probe',
    'TH-1..TH-3 thermal on real copper (U2 Tj <= 125 C needs effective RthetaJA <= 55.8 C/W at the CC limit)',
    'LS-1 loop gain with the real rack (PM > 45 deg, GM > 10 dB), CL-1/T1 clamp energy, T2 rail overvoltage',
    'IN-1/IN-2 UVLO/OVP spread at temperature, EMI-1 switching-node ringing, GS-1/GS-2 ground star, KS-1/CC-1 Kelvin',
    'Backfeed in the field (T1) beyond the bounded injection budget; downstream OV qualification; crowbar vs eFuse deferred',
    'POR-1 replug/POR nuisance race (calcs replug_por), IN-3 USB-C attach transient, HDR-1 header contact current',
]


def thermal_entry(calcs):
    """S9.2b changelog line for the via change, written from calcs.json (no hand-copied numbers)."""
    tc = calcs['thermal_contract']
    u5, ch = tc['U5'], tc['via_change']
    f = ch['fields']
    return (f"no via-in-pad; vias relocated: U5 {f['U5']['in_pad_holes_before']} in-pad -> {f['U5']['beside_pad_vias_after']} "
            f"beside-pad, U4 {f['U4']['in_pad_holes_before']} -> {f['U4']['beside_pad_vias_after']}, U9 "
            f"{f['U9']['in_pad_holes_before']} (0.2 mm) -> {f['U9']['beside_pad_vias_after']}. Thermal penalty "
            f"{u5['thermal_penalty_C']} C at rated load: U5 RthetaJA {u5['RthetaJA_datasheet_C_W']} -> "
            f"{u5['RthetaJA_S92b_C_W']} C/W (upper bound), Tj {u5['Tj_at_50C_in_pad_vias_C']} -> {u5['Tj_at_50C_S92b_C']} C "
            f"at 50 C and the rated 3 A input (limit {u5['limit_C']} C); U2 unchanged (never drilled): Tj "
            f"{ch['U2']['Tj_at_50C_rating_C']} C at 2.4 A, {ch['U2']['Tj_at_50C_limit_C']} C at the CC limit; U4 "
            f"DeltaR +{ch['U4']['delta_R_C_W']} C/W, U9 +{ch['U9']['delta_R_C_W']} C/W. Published rating "
            f"{'CHANGED' if ch['rating']['changed'] else 'unchanged'}: +12 V {ch['rating']['published_A']['+12V']} A / "
            f"-12 V {ch['rating']['published_A']['-12V']} A.")


def ignored(paths):
    """Paths git would ignore (they are absent from a clean clone)."""
    out = subprocess.run(['git', 'check-ignore', '--no-index', *paths], cwd=MODULE, capture_output=True, text=True)
    return set(out.stdout.split())


def tracked():
    """Module-relative paths git tracks (staged files count): what a clean clone of the commit will contain."""
    out = subprocess.run(['git', 'ls-files', '--', '.'], cwd=MODULE, capture_output=True, text=True, check=True)
    return set(out.stdout.split())


def local(path):
    p = Path(path).resolve()
    return str(p.relative_to(MODULE)) if p.is_relative_to(MODULE) else str(path)


def sha(rel):
    return hashlib.sha256((MODULE / rel).read_bytes()).hexdigest()


def footprints_used():
    """Every pinned footprint file the single board references (USBPOWER45 library)."""
    text = (MODULE / 'hardware/single/usb-power-45w-single.kicad_pcb').read_text()
    names = sorted(set(re.findall(r'\(footprint "USBPOWER45:([^"]+)"', text)))
    return [f'hardware/USBPOWER45.pretty/{n}.kicad_mod' for n in names]


ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')      # Python 3.14 unittest colours its own output


def tests(log):
    text = ANSI.sub('', Path(log).read_text(errors='replace'))
    m = re.search(r'^Ran (\d+) tests? in', text, re.M)
    ok = re.search(r'^OK\b', text, re.M) is not None
    skipped = re.search(r'^OK \(skipped=(\d+)\)', text, re.M)
    s8 = len(set(re.findall(r'\((test_s8\.[\w.]+)\)', text)))
    return {'ran': int(m.group(1)) if m else None, 'ok': ok, 'skipped': int(skipped.group(1)) if skipped else 0,
            's8_tests': s8, 'log': local(log),
            'log_committed': not ignored([local(log)]) and Path(log).resolve().is_relative_to(MODULE),
            'note': 'local evidence; the tests log lives in git-ignored research/ and is not hashed'}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', type=Path, required=True)
    ap.add_argument('--tests-log', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    summary = json.loads((a.check / 'summary.json').read_text())
    docs = MODULE / 'docs/s8-single'
    build = json.loads((docs / 'build.json').read_text())
    val = json.loads((docs / 'validation.json').read_text())
    board = json.loads((docs / 'board-p1.json').read_text())
    place = json.loads((docs / 'placement.json').read_text())
    asm = json.loads((docs / 'assembly/assembly-report.json').read_text())
    mech = json.loads((docs / 'mechanical.json').read_text())
    calcs = json.loads((docs / 'calcs.json').read_text())
    src = json.loads((docs / 'sourcing.json').read_text())
    s92 = json.loads((docs / 's92-sourcing.json').read_text())
    s93 = json.loads((docs / 's93-sourcing.json').read_text())
    rows = list(csv.DictReader((docs / 'bom.csv').open()))
    bom_refs = [r for row in rows for r in row['Refs'].split(',')]
    test_pads = sorted(r for r in place['parts'] if r.startswith('TP'))
    t = tests(a.tests_log)
    assert t['ok'] and summary['ref_pin_net_parity']['equal'], (t, 'tests and exact parity must pass')
    artifacts = sorted(str(p.relative_to(MODULE)) for p in docs.rglob('*') if p.is_file() and p.name != a.out.name)
    artifacts.append('docs/usb-power-45w-single-schematic.pdf')
    notes = s92_contract.notes_index((MODULE / s92_contract.NOTES).read_text())
    assert s92_contract.NOTES in artifacts, 'the record must hash the routing notes'
    assert set(notes['pads']) == set(test_pads) and not notes['duplicate_pads'], ('routing notes test-pad table', notes)
    undefined = sorted((s92_contract.contract_ids() | s92_contract.referenced_ids(*OPEN_GATES)) - notes['ids'])
    assert not undefined, ('acceptance-test IDs without a routing-notes register row', undefined)
    res = calcs['residuals']
    b = calcs['plus12_buckboost']
    rec = {
        'revision': REVISION,
        'status': ('routing-ready schematic and placement, unrouted and not bench-qualified; the open items are '
                   'post-prototype acceptance tests, not design blockers'),
        'replaces': 'review-s92.json (S9.2 / P2.2 record in git 9cdb9bd)',
        'changelog': [{'item': k, 'change': v} for k, v in CHANGELOG] + [{'item': 'S9.2b thermal', 'change': thermal_entry(calcs)}],
        'native_findings': summary['findings'],
        'exact_native_ref_pin_net_parity': summary['ref_pin_net_parity'],
        'native_sources_unchanged_by_check': summary['source_unchanged'],
        'raw_reports': local(a.check), 'raw_reports_committed': False,
        'counts': {'components': build['components'], 'nets': build['nets'],
                   'nets_including_NC': val['nets_including_NC'], 'no_connect_pins': build['no_connect_pins'],
                   'drc_unconnected_items': summary['findings']['drc']['categories'].get('unconnected_items')},
        'bom_parity': {'bom_lines': len(rows), 'bom_refs': len(bom_refs), 'unique': len(set(bom_refs)),
                       'test_pads_not_in_bom': len(test_pads), 'components': build['components'],
                       'equal': (len(set(bom_refs)) == len(bom_refs) and not set(bom_refs) & set(test_pads)
                                 and set(bom_refs) | set(test_pads) == set(place['parts']))},
        'tests': t,
        'placement': {'parts': board['parts_on_board'], 'pass': board['pass'],
                      'local_loops_violations': board['local_loops']['violations'],
                      'local_loops': {r['purpose']: [r['from'], r['to'], r['distance_mm'], r['limit_mm']]
                                      for r in board['local_loops']['rows']},
                      'basis': ('S9.3 / P2.3 synchronized from S9.2b / P2.2: the ten S9.3 parts added in free pockets, '
                                'every P2.2 part unmoved; no routing apart from the thermal-via fields'),
                      'routing_contract_screen': board['routing_contract_screen'],
                      'ground_split': board['ground_split'],
                      'replaced_footprints': place.get('replaced_footprints', {}),
                      'moved_retained_refs': place['moved_retained_refs'],
                      'added_refs': place['added_refs'], 'removed_refs': place['removed_refs'],
                      'courtyard_fill': board['area_mm2']['fill_of_inset']},
        'routing_notes': {'doc': s92_contract.NOTES, 'test_pad_rows': len(notes['pads']),
                          'register_ids': sorted(notes['ids']),
                          'status': 'routing-ready; the register items are post-prototype acceptance tests, not design '
                                    'blockers'},
        'mechanical': {'overlaps': len(asm['solid_interference_mm3']), 'proxies': asm['proxies'],
                       'risks': {r['id']: r.get('value_mm') for r in mech['risks']}, 'nominal_only': True},
        'S92_vin_clamp': calcs['vin_clamp'],
        'S92_enable_logic_from_netlist': {k: val['enable_logic'][k] for k in ('structure', 'violations', 'pass', 'method')},
        'S92_startup_plant_from_netlist': val['startup_plant_inputs'],
        'S92_startup_qualification': calcs['startup_qualification'],
        'S92_thermal_contract': calcs['thermal_contract'],
        'S92b_via_policy': {
            'decision': place['routing_contract']['via_in_pad']['decision'],
            'order': place['routing_contract']['via_in_pad']['order'],
            'board': {k: board['pre_routing_checklist']['items']['via_in_pad'][k]
                      for k in ('footprint_holes_in_pads', 'thermal_pad_footprints', 'board_setup', 'vias',
                                'non_standard_vias', 'via_overrides', 'vias_closer_than_0p1mm_to_a_pad',
                                'vias_in_a_mask_opening', 'ok')},
            'thermal_fields': {r: [x['vias'], x['spokes_into_pad'], x['landing_pour'], x['landing_mm2']]
                               for r, x in board['pre_routing_checklist']['items']['thermal_vias']['fields'].items()},
            'thermal_consequence': {k: calcs['thermal_contract']['via_change'][k] for k in ('U5', 'U2', 'U4', 'U9', 'rating')},
            'validation': val['no_via_in_pad']},
        'S92b_drc_contract': {'pre_routing_checklist': {k: v['ok'] for k, v in
                                                        board['pre_routing_checklist']['items'].items()},
                              'netclasses': board['pre_routing_checklist']['items']['netclasses']['per_class'],
                              'drc_rules': board['pre_routing_checklist']['items']['drc_rules']['rules'],
                              'rule_areas': [a['name'] for a in board['pre_routing_checklist']['items']['rule_areas']['areas']],
                              'post_routing_pending': board['routing_contract_screen']['pending_after_routing'],
                              'enforced_by_drc': board['routing_contract_screen']['enforced_by_drc']},
        'S91_input_qualification': calcs['input_qualification'],
        'S91_compensation': b['compensation'],
        'S91_ground_split': val['ground_split'],
        'electrical_screens': {
            'plus12_duty': {'S8_TPS62933F_required_duty': b['S8_TPS62933F_at_15V']['required_duty'],
                            'S8_min_VPD_for_regulation_V': b['S8_TPS62933F_at_15V']['min_VPD_for_regulation_V'],
                            'TPS552892_regulates_everywhere': b['regulates_everywhere'],
                            'R109_cc_limit_A': b['R109_cc_limit_A'], 'setpoint_V': b['setpoint_V'], 'fsw_kHz': b['fsw_kHz'],
                            'losses': b['losses'], 'compensation': b['compensation']['crossover_Hz']},
            'published_rating_A': calcs['rating']['published_A'],
            'published_total_W': calcs['rating']['published_total_W'],
            'pd_contract': {k: calcs['pd_contract'][k] for k in ('stated_input_range_V', 'contract_A', 'required_adapter',
                                                                 'max_module_output_W')},
            'startup_arming': {k: v for k, v in val['startup_arming'].items() if k != 'timelines'},
            'arming_timelines_summary': {name: {k: [r['first_enable_ms'], r['ARMED_ms'], r['FAULT_ms'], r['ends_running']]
                                                for k, r in r_.items() if k != 'why'}
                                         for name, r_ in val['startup_arming']['timelines'].items()},
            'arming_calcs': {k: calcs['arming'][k] for k in ('required', 'topology', 'V20_OK', 'U5_on_V', 'U5_off_V')},
            'guard_margins_V': {k: {x: calcs['ov_guard'][k][x] for x in ('guard_V', 'stacked_margin_to_guard_min_V',
                                                                          'margin_guard_max_to_limit_V')}
                                for k in ('+12V', '-12V')},
            'replug_por': {k: calcs['replug_por'][k] for k in ('worst_settle_ms', 'POR_RESET_release_min_ms', 'margin_ms',
                                                               'established', 'status')},
            'rack_allowance_mF': {'+12V': calcs['soft_start']['+12V']['rack_allowance_mF'],
                                  '-12V': calcs['minus12_startup']['published_allowance_mF']},
            'retarget_20v': {k: calcs['retarget_20v'][k] for k in ('changes', 'U5_window_V', 'V20_OK_band_V')}},
        'accepted_residuals': {
            'reverse_current': {'decision': res['reverse_current']['decision'], 'rule': res['reverse_current']['rule'],
                                'finding': res['reverse_current']['minus12_active']['finding'],
                                'bench_test': res['reverse_current']['bench_test']},
            'rail_overvoltage': {'decision': res['rail_overvoltage']['decision'],
                                 'peak_screens_V': res['rail_overvoltage']['peak_screens_V'],
                                 'bench_test': res['rail_overvoltage']['bench_test']},
            'validation': val['accepted_residuals']},
        'sourcing': {'selected_part_evidence': ('s93-sourcing.json (live, every S9.3 code incl. alternates); s92-sourcing.json '
                                                '(S9.2 codes); sourcing.json full live audit'),
                     'earlier_evidence': ['s92-sourcing.json', 's91-sourcing.json', 's90-sourcing.json', 's84-sourcing.json',
                                          's83-sourcing.json'],
                     'parts_partial_subtotal_q1_usd': src['summary']['S8_parts_usd_q1'],
                     'unpriced_codes': src['summary']['S8_unpriced_codes'],
                     'manual_parts_no_LCSC': src['summary']['manual_parts_no_LCSC']['S8'],
                     'failures': src['summary']['failures'],
                     'codes': src['summary']['S8_codes'], 'placements': src['summary']['S8_placements'],
                     'all_parts_fresh_live_audit': src['summary'].get('live_audit', False),
                     'missing_codes_for_assembled_parts': src['summary'].get('missing_codes', []),
                     'basic_only_policy': src['basic_only_policy']['decision'],
                     'live_rows': {c: [r['classification'], r['stock'], r['unit_price_q1_usd'],
                                       (r.get('evidence') or {}).get('retrieved_at_utc')]
                                   for c, r in {**s92['codes'], **s93['codes']}.items()},
                     'reverse_blocking_parts': 'none (owner decision)'},
        'original_S7_R3_hardware_unchanged_sha256': {p: sha(p) for p in S7_R3},
        'sources_sha256': {p: sha(p) for p in SOURCES + footprints_used()},
        'artifacts_sha256': {p: sha(p) for p in artifacts + ['docs/s8-single-board.md']},
        'open_gates': OPEN_GATES,
        'order_ready': False,
    }
    assert rec['bom_parity']['equal'], rec['bom_parity']
    hashed = [p for g in ('original_S7_R3_hardware_unchanged_sha256', 'sources_sha256', 'artifacts_sha256') for p in rec[g]]
    assert not ignored(hashed), ('hashed files must exist in a clean clone', sorted(ignored(hashed)))
    missing = sorted(set(hashed) - tracked())
    assert not missing, ('hash only tracked files: stage them first (git add)', missing)
    a.out.write_text(json.dumps(rec, indent=2) + '\n')
    print(json.dumps({k: rec[k] for k in ('revision', 'native_findings', 'counts', 'bom_parity', 'tests')}, indent=1))


if __name__ == '__main__':
    main()
