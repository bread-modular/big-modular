"""S8 review record: native findings, exact parity, test results, placement/mechanics/sourcing summaries and the
SHA-256 of every source and artifact, assembled from fresh reports (no hand-copied numbers).

  python3 -B tools/review_s8.py --check research/s90/check-final --tests-log research/s90/tests-final.log \
      --out docs/s8-single/review-s90.json

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
REVISION = 'S9.0 / P2.0'
TRACKED_KICAD = ('.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sym')   # *.kicad_prl is git-ignored
S7_R3 = sorted(str(p.relative_to(MODULE)) for p in (MODULE / 'hardware').glob('*.kicad_*') if p.suffix in TRACKED_KICAD)
PANEL = ['panels/front-pcb/usb-power-45w-single-panel.kicad_pcb', 'panels/front-pcb/usb-power-45w-single-panel.kicad_pro']
SOURCES = (sorted(f'hardware/single/{p.name}' for p in (MODULE / 'hardware/single').glob('*.kicad_*')
                  if p.suffix in TRACKED_KICAD)
           + ['hardware/single/fp-lib-table', 'hardware/single/sym-lib-table'] + PANEL
           + [f'tools/{n}.py' for n in ('build_s8', 'build_s8_assembly', 'build_s8_board', 'build_s8_panel',
                                        'check_s8_board', 'circuit_s8', 'hierarchy_s8', 'mechanics_s8', 'place_s8',
                                        'render_s8', 'review_s8', 's8_calcs', 's8_mechanical', 's8_sourcing', 's90_parts',
                                        'test_s8', 'verify_s8')])
CHANGELOG = [
    ('S9.0-1 +5V removed', 'The module is +/-12V only: U3 (TPS62933F +5V buck) and every part that only served +5V are gone '
                           '(U23 eFuse with R108/TP21, OVLO R107/R101/R102, ILM R103/R104, dVdt C68, L2 and the U3 network, '
                           'the raw and delivered +5V banks, D3/D21/D23, the U20 +5V guard channel, the U18 +5V monitor, R44, '
                           'TP13/TP18, J2/J3 pins 11/12 open). No +5V/P5_*/EF_* net or ref survives (regression tests).'),
    ('S9.0-2 15 V input', 'CH224A requests 15 V (R1 56k); U5 UVLO R3 10k (on 12.46-13.98 V, off 11.55-13.13 V); V20_OK '
                          'R83 100k (7.67-9.27 V status floor); stated input range 13.5-16.5 V at the module; needs a 15 V / '
                          '3 A (>= 45 W) PD source; U5 OVP keeps the 20 V setting.'),
    ('S9.0-2 +12V duty', 'The S8 TPS62933F buck needed 0.995-1.053 duty at the 12.5 V low-line converter input (1.033 even '
                         'unloaded at the setpoint maximum) against its 98 % maximum and would need VPD >= 14.42 V: replaced '
                         'by the TPS552892-Q1 four-switch buck-boost (TI RYQ0021B; 966 kHz, L1 6.8 uH kept, R109 15 mR CC '
                         'limit 3.14-3.53 A, FB R8/R9, COMP R111/C83, VCC C82, FPWM, internal LDO) that regulates from the '
                         '10.55 V U5 sag to 21 V. U2 footprint replaced (U2 only), +10 parts placed right of L1.'),
    ('S9.0 ratings', 'Published prototype rating +12V 2.4 A, -12V 0.8 A (75 % of the minimum current-limited capability at '
                     'the 12.5 V converter input), <= 33 W together (3 A contract at the 13.5 V minimum, worst efficiency '
                     'mix); ~36 W is the most a nominal 15 V / 3 A source supports.'),
    ('S9.0 arming', 'Re-derived without P5_OK: ANY_BAD = NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3); S8.5 one-shot STARTED '
                    '(U12 A, U11 -> ARMED, TP19) kept; timelines re-run at the 15 V source corners with a load-aware VPD '
                    'plant (the loaded 13.5 V minimum sits below the 13.98 V turn-on maximum): 0 violations.'),
    ('S9.0 residuals', 'Owner decisions 2026-11-02: no reverse-current blocking (no LM74700/LTC4357-class part, no FETs) and '
                       'no voltage-triggered fuse/crowbar; both recorded as accepted residuals with bench-test conditions '
                       'and pass criteria (calcs residuals, validation accepted_residuals, docs S9.0). Finding: a live +/-12V '
                       'bus can enable U4 through Q1 in an unpowered module and its FPWM can pump VIN: the procedural rule '
                       'is mandatory; a non-blocking mitigation is an open owner decision, not implemented.'),
    ('kept / open', 'Crowbar vs eFuse stays deferred/open (no crowbar restored); replug/POR race (C3) open; U18/U20 on VPD, '
                    'guard thresholds, precision-divider policy, mechanics and the panel geometry unchanged (panel label PD '
                    '15V).'),
]
OPEN_GATES = [
    '365 routing opens (unrouted fit placement); the local-loop screens are straight-line distances, not routed loops',
    'TPS552892-Q1 loop with the real rack capacitance (crossover falls below the 1.7 kHz COMP zero), thermal at the R109 '
    'limit, and the 966 kHz choice against TI\'s < 500 kHz high-power advice: bench Bode / thermal gates',
    'Reverse current (accepted residual): a live bus can enable and power U4 in an unpowered or latched-off module and pump '
    'VIN beyond U2\'s 42 V maximum; procedural rule mandatory; Q1/U4 enable mitigation = open owner decision',
    'Rail overvoltage (accepted residual): the guard + latch opens U5 but does not discharge the rails; downstream modules '
    'must be qualified against the T2 conditions (up to 16.5 V, ~24 V without a rack after a control failure)',
    'Replug / POR race of the U20 -12V channel (calcs replug_por, worst 13.75 ms vs the 12 ms POR minimum): nuisance latch-off',
    'Arming timelines are a logic model with datasheet timings; bench-verify the one-shot window, brown-out and overload '
    'latching at the 15 V corners (U5 turn-on margin 0.27 V unloaded, running margin 0.37 V loaded)',
    'VPD ringing at U18/U20, cold MON_OVN clamp, power-down sequences, -12V start-up into the real rack at 13.5 V',
    'Published rating is a datasheet-minimum prototype rating, not measured; connector/cable current and fit; source '
    'behaviour above the 33 W total (U5 does not enforce the 3 A contract)',
    'Manual fabrication/CAM and assembly review; RYQ land pattern (0.2 mm gaps, 0.15 mm mask webs) with the fab',
    'Crowbar vs eFuse (rail overvoltage protection architecture) remains a deferred, open owner decision',
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


def tests(log):
    text = Path(log).read_text(errors='replace')
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
    s90 = json.loads((docs / 's90-sourcing.json').read_text())
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
        'status': 'verified schematic / fit draft, unrouted and not bench-qualified',
        'replaces': 'review-s85.json (S8.5 / P1.5 record, git 5a3a686)',
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
                      'basis': 'synchronized from the S9.0 step-1 board (P1.5 minus the +5V parts)',
                      'replaced_footprints': place.get('replaced_footprints', {}),
                      'moved_retained_refs': place['moved_retained_refs'],
                      'added_refs': place['added_refs'], 'removed_refs': place['removed_refs'],
                      'courtyard_fill': board['area_mm2']['fill_of_inset']},
        'mechanical': {'overlaps': len(asm['solid_interference_mm3']), 'proxies': asm['proxies'],
                       'risks': {r['id']: r.get('value_mm') for r in mech['risks']}, 'nominal_only': True},
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
        'sourcing': {'selected_part_evidence': 's90-sourcing.json (TPS552892 C22375748, R109 C601098, R1 C23206); every '
                                               'other code from the dated sourcing.json snapshot',
                     'earlier_evidence': ['s84-sourcing.json', 's83-sourcing.json'],
                     'parts_total_q1_snapshot_usd': src['summary']['S8_parts_usd_q1'],
                     'codes': src['summary']['S8_codes'], 'placements': src['summary']['S8_placements'],
                     'all_parts_fresh_live_audit': False,
                     'basic_only_policy': src['basic_only_policy']['decision'],
                     'live_rows': {c: [r['classification'], r['stock'], r['unit_price_q1_usd'],
                                       (r.get('evidence') or {}).get('retrieved_at_utc')] for c, r in s90['codes'].items()},
                     'reverse_blocking_parts': 'none (owner decision)'},
        'original_S7_R3_hardware_unchanged_sha256': {p: sha(p) for p in S7_R3},
        'sources_sha256': {p: sha(p) for p in SOURCES + footprints_used()},
        'artifacts_sha256': {p: sha(p) for p in artifacts},
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
