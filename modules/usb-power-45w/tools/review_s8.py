"""S8 review record: native findings, exact parity, test results, placement/mechanics/sourcing summaries and the
SHA-256 of every source and artifact, assembled from fresh reports (no hand-copied numbers).

  python3 -B tools/review_s8.py --check research/s92/check-final --tests-log research/s92/tests-final.log \
      --out docs/s8-single/review-s92.json

--check is a NEW native check directory of the shared tool (opt/kicad-tools/kicad_tools.py check, summary.json),
--tests-log the verbose unittest output of `python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v`.
Read-only apart from --out. S9.0 replaces the S8.5 record (review-s85.json, kept in git history at 5a3a686). Only files
git TRACKS are hashed (S8.5 item C: no git-ignored *.kicad_prl, nothing under research/; S9.0: membership is checked with
`git ls-files`, so stage new sources before writing the record); the check directory and the tests log are local evidence
(git-ignored research/), recorded by path and summary, never hashed. S9.0 also hashes the pinned TPS552892-Q1 part file
(tools/s90_parts.py), every footprint the single board uses and the single-board panel.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REVISION = 'S9.2 / P2.2'
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
]
OPEN_GATES = [   # S9.2: post-prototype acceptance tests (routing-notes.md), not design blockers
    'Routing itself (P2.2 is routing-ready and unrouted; the contract items are checked after routing)',
    'S1-S4 source/startup qualification: strict 3.00 A sources fail safe at full load + rack (needs ~4.65 A for ~2.5 ms)',
    'TH-1..TH-3 thermal on real copper (U2 Tj <= 125 C needs effective RthetaJA <= 55.8 C/W at the CC limit)',
    'LS-1 loop gain with the real rack (PM > 45 deg, GM > 10 dB), CL-1/T1 clamp energy, T2 rail overvoltage',
    'IN-1/IN-2 UVLO/OVP spread at temperature, EMI-1 switching-node ringing, GS-1/GS-2 ground star, KS-1/CC-1 Kelvin',
    'Backfeed in the field (T1) beyond the bounded injection budget; downstream OV qualification; crowbar vs eFuse deferred',
    'Replug/POR nuisance race (calcs replug_por) remains a documented acceptance item',
]


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
    rows = list(csv.DictReader((docs / 'bom.csv').open()))
    bom_refs = [r for row in rows for r in row['Refs'].split(',')]
    test_pads = sorted(r for r in place['parts'] if r.startswith('TP'))
    t = tests(a.tests_log)
    assert t['ok'] and summary['ref_pin_net_parity']['equal'], (t, 'tests and exact parity must pass')
    artifacts = sorted(str(p.relative_to(MODULE)) for p in docs.rglob('*') if p.is_file() and p.name != a.out.name)
    artifacts.append('docs/usb-power-45w-single-schematic.pdf')
    res = calcs['residuals']
    b = calcs['plus12_buckboost']
    rec = {
        'revision': REVISION,
        'status': ('routing-ready schematic and placement, unrouted and not bench-qualified; the open items are '
                   'post-prototype acceptance tests, not design blockers'),
        'replaces': 'review-s91.json (S9.1 / P2.1 record in git 5df64c7)',
        'changelog': [{'item': k, 'change': v} for k, v in CHANGELOG],
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
                      'basis': 'S9.2 / P2.2 synchronized from S9.1; no routing',
                      'routing_contract_screen': board['routing_contract_screen'],
                      'ground_split': board['ground_split'],
                      'replaced_footprints': place.get('replaced_footprints', {}),
                      'moved_retained_refs': place['moved_retained_refs'],
                      'added_refs': place['added_refs'], 'removed_refs': place['removed_refs'],
                      'courtyard_fill': board['area_mm2']['fill_of_inset']},
        'mechanical': {'overlaps': len(asm['solid_interference_mm3']), 'proxies': asm['proxies'],
                       'risks': {r['id']: r.get('value_mm') for r in mech['risks']}, 'nominal_only': True},
        'S92_vin_clamp': calcs['vin_clamp'],
        'S92_enable_logic_from_netlist': {k: val['enable_logic'][k] for k in ('structure', 'violations', 'pass', 'method')},
        'S92_startup_plant_from_netlist': val['startup_plant_inputs'],
        'S92_startup_qualification': calcs['startup_qualification'],
        'S92_thermal_contract': calcs['thermal_contract'],
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
        'sourcing': {'selected_part_evidence': 's92-sourcing.json (live, every S9.2 code incl. alternates); sourcing.json full live audit',
                     'earlier_evidence': ['s91-sourcing.json', 's90-sourcing.json', 's84-sourcing.json', 's83-sourcing.json'],
                     'parts_partial_subtotal_q1_usd': src['summary']['S8_parts_usd_q1'],
                     'unpriced_codes': src['summary']['S8_unpriced_codes'],
                     'manual_parts_no_LCSC': src['summary']['manual_parts_no_LCSC']['S8'],
                     'failures': src['summary']['failures'],
                     'codes': src['summary']['S8_codes'], 'placements': src['summary']['S8_placements'],
                     'all_parts_fresh_live_audit': src['summary'].get('live_audit', False),
                     'missing_codes_for_assembled_parts': src['summary'].get('missing_codes', []),
                     'basic_only_policy': src['basic_only_policy']['decision'],
                     'live_rows': {c: [r['classification'], r['stock'], r['unit_price_q1_usd'],
                                       (r.get('evidence') or {}).get('retrieved_at_utc')] for c, r in s92['codes'].items()},
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
