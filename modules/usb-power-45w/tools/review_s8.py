"""S8 review record: native findings, exact parity, test results, placement/mechanics/sourcing summaries and the
SHA-256 of every source and artifact, assembled from fresh reports (no hand-copied numbers).

  python3 -B tools/review_s8.py --check research/s85/check-final --tests-log research/s85/tests-final.log \
      --out docs/s8-single/review-s85.json

--check is a NEW native check directory of the shared tool (opt/kicad-tools/kicad_tools.py check, summary.json),
--tests-log the verbose unittest output of `python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v`.
Read-only apart from --out. S8.5 replaces the S8.4 record (review-s84.json, kept in git history at 0bc6f62). S8.5 (item
C): only files a clean clone has are hashed - no git-ignored *.kicad_prl, nothing under research/; the check directory
and the tests log are local evidence (git-ignored research/), recorded by path and summary, never hashed.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REVISION = 'S8.5 / P1.5'
TRACKED_KICAD = ('.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sym')   # *.kicad_prl is git-ignored
S7_R3 = sorted(str(p.relative_to(MODULE)) for p in (MODULE / 'hardware').glob('*.kicad_*') if p.suffix in TRACKED_KICAD)
SOURCES = (sorted(f'hardware/single/{p.name}' for p in (MODULE / 'hardware/single').glob('*.kicad_*')
                  if p.suffix in TRACKED_KICAD)
           + [f'tools/{n}.py' for n in ('build_s8', 'build_s8_assembly', 'build_s8_board', 'build_s8_panel',
                                        'check_s8_board', 'circuit_s8', 'hierarchy_s8', 'mechanics_s8', 'place_s8',
                                        'render_s8', 'review_s8', 's8_calcs', 's8_mechanical',
                                        's8_sourcing', 'test_s8', 'verify_s8')])
CHANGELOG = [
    ('B', 'One-shot arming (the blocker of all three S8.4 reviews): U12 flip-flop A = STARTED latch (PRE_N = START_N = '
          'NAND(MAIN_LED_OK, RUN) on the spare U14 gate 2, CLR_N = RESET_N, CLK = GND); TIMER_GO = RUN AND STARTED; the '
          'U11 output IS ARMED (R71); TP19 = STARTED. R83 200k -> 120k: V20_OK 9.06-10.96 V, a U5 status-validity floor '
          '(>= 3.56 V above vSafe5V max, >= 4.08 V below the U5 turn-off minimum); the input qualification is the U5 UVLO. '
          'Arming timelines (cold start at the worst loaded 20 V minimum, slow PD contract, brown-out after/inside the '
          'window, overload chatter, hot plug into a live bus, load release, U20 guard before ARMED, short RESET) pass R1-R4; '
          'the S8.4 wiring fails them (regression test).'),
    ('C-hash', 'Review record hashes only files a clean clone has: the git-ignored *.kicad_prl files are no longer hashed '
               'and the local tests log / check directory (research/, git-ignored) are recorded by path only.'),
    ('C-status', 'MAIN_LED_OK = MAIN_OK AND V20_OK now means "U5 on with valid FLT/PGOOD"; ANY_BAD = NOT(MAIN_LED_OK AND '
                 'P12_OK AND P5_OK AND N12_OK). Notes, page texts and the fault matrix say so.'),
    ('C-POR', 'Replug / power-on-reset race of the U20 -12V channel (R100/C67 loaded by R98, TPS3808 >= 12 ms POR): '
              'calcs replug_por, nominal 9.5 ms, worst 13.75 ms: margin NOT established, explicit OPEN item. The S8.4 '
              '~1 ms margin (v3v3_loss) ignored the R98 load and is withdrawn.'),
    ('kept', 'Every S8.4 decision unchanged: U23 TPS259470ARPWR with R108/TP21 (P5_FLT_N), OVLO R107/R101/R102, ILM '
             'R103/R104, C68, R11/R12 0.1 %, U18/U20 on VPD, local-loop contract, 2.0 A +5V rating, mask webs, -12V '
             'start-up, sourcing decision and mechanical records. The crowbar-vs-eFuse question stays open.'),
]
OPEN_GATES = [
    '430 routing opens (unrouted fit placement); the local-loop screens are straight-line distances, not routed loops',
    'No guaranteed <6 V header peak: U23 OVLO response is typical-only, parasitics and stored energy unbounded',
    'OVLO-only short/startup events can auto-recover before the qualified latch; after a genuine OVLO trip U23 may '
    'stay open at stacked corners (latched off until RESET)',
    'Replug / POR race of the U20 -12V channel (calcs replug_por, worst 13.75 ms vs the 12 ms POR minimum): a nuisance '
    'latch-off (RESET to recover) when the rack already holds -12V; fix not implemented',
    'Arming timelines are a logic model with datasheet timings (U5 PGOOD deglitch, U11 delay corners); bench-verify the '
    'one-shot window, brown-out and overload-chatter latching',
    'VPD ringing at U18/U20, cold MON_OVN clamp, power-down sequences',
    'Converter stability with the banks, DC bias, startup foldback, thermal, load-release and -12V rack start-up tests',
    'Published rating is a datasheet-minimum prototype rating, not measured; connector/cable current and fit',
    'Manual fabrication/CAM and assembly review; U23 mask-web capability confirmation with the fab',
    'Crowbar vs eFuse (+5V protection architecture) remains an open owner decision; S8.5 keeps U23 unchanged',
]


def ignored(paths):
    """Paths git would ignore (they are absent from a clean clone)."""
    out = subprocess.run(['git', 'check-ignore', '--no-index', *paths], cwd=MODULE, capture_output=True, text=True)
    return set(out.stdout.split())


def local(path):
    p = Path(path).resolve()
    return str(p.relative_to(MODULE)) if p.is_relative_to(MODULE) else str(path)


def sha(rel):
    return hashlib.sha256((MODULE / rel).read_bytes()).hexdigest()


def tests(log):
    text = Path(log).read_text(errors='replace')
    m = re.search(r'^Ran (\d+) tests? in', text, re.M)
    ok = re.search(r'^OK\b', text, re.M) is not None
    s8 = len(set(re.findall(r'\((test_s8\.[\w.]+)\)', text)))
    return {'ran': int(m.group(1)) if m else None, 'ok': ok, 's8_tests': s8, 'log': local(log),
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
    s84 = json.loads((docs / 's84-sourcing.json').read_text())
    rows = list(csv.DictReader((docs / 'bom.csv').open()))
    bom_refs = [r for row in rows for r in row['Refs'].split(',')]
    test_pads = sorted(r for r in place['parts'] if r.startswith('TP'))
    t = tests(a.tests_log)
    assert t['ok'] and summary['ref_pin_net_parity']['equal'], (t, 'tests and exact parity must pass')
    artifacts = sorted(str(p.relative_to(MODULE)) for p in docs.rglob('*') if p.is_file() and p.name != a.out.name)
    artifacts.append('docs/usb-power-45w-single-schematic.pdf')
    rec = {
        'revision': REVISION,
        'status': 'verified schematic / fit draft, unrouted and not bench-qualified',
        'replaces': 'review-s84.json (S8.4 / P1.4 record, git 0bc6f62)',
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
                      'moved_retained_refs_P14_to_P15': place['moved_retained_refs'],
                      'added_refs': place['added_refs'],
                      'pad_mask_refreshed_from_library': sorted(place.get('pad_mask_refreshed_from_library', {})),
                      'courtyard_fill': board['area_mm2']['fill_of_inset']},
        'mechanical': {'overlaps': len(asm['solid_interference_mm3']), 'proxies': asm['proxies'],
                       'risks': {r['id']: r.get('value_mm') for r in mech['risks']}, 'nominal_only': True},
        'electrical_screens': {
            'FLT_isolated_from_latch': val['disconnect']['FLT_isolated_from_latch'],
            'P5_FLT_N_members': val['disconnect']['P5_FLT_N_members'],
            'startup_arming': {k: v for k, v in val['startup_arming'].items() if k != 'timelines'},
            'arming_timelines_summary': {name: {k: [r['first_enable_ms'], r['ARMED_ms'], r['FAULT_ms'], r['ends_running']]
                                                for k, r in res.items() if k != 'why'}
                                         for name, res in val['startup_arming']['timelines'].items()},
            'arming_calcs': {k: calcs['arming'][k] for k in ('required', 'topology', 'V20_OK', 'U5_on_V', 'U5_off_V')},
            'replug_por': {k: calcs['replug_por'][k] for k in ('worst_settle_ms', 'POR_RESET_release_min_ms', 'margin_ms',
                                                               'established', 'status')},
            'ovlo_release': {k: calcs['ovlo_release'][k] for k in ('setpoint_V', 'OVLO_rising_V', 'OVLO_falling_V',
                                                                    'imposed_model_release_below_trips',
                                                                    'reconnect_margin_worst_V', 'reconnect_corner_open')},
            'release_from_ILIM_max_margin_to_OVLO_min_V':
                calcs['ovlo_release']['release_cases']['U23_ILIM_max']['margin_to_OVLO_min_V'],
            'minus12_rack_allowance_mF': calcs['minus12_startup']['published_allowance_mF'],
            'published_rating_A': calcs['rating']['published_A'],
            'six_volt_header_peak_guaranteed': calcs['disconnect']['fault_delay_sensitivity']['guaranteed_bound'],
            'C2_cases_V': {k: [v['header_peak_V'], v['header_time_above_6V_us']]
                           for k, v in calcs['disconnect']['fault_delay_sensitivity']['cases'].items()
                           if k in ('L3.3uH_delay3us', 'VIN30_src1ohm_L3.3uH_3us')}},
        'sourcing': {'selected_part_evidence': 's84-sourcing.json (unchanged in S8.5: R83 reuses the R75 Basic code '
                                               'C25808 from the dated sourcing.json snapshot)',
                     'S8_3_selection_evidence': 's83-sourcing.json',
                     'parts_total_q1_snapshot_usd': src['summary']['S8_parts_usd_q1'],
                     'all_parts_fresh_live_audit': False,
                     'basic_only_policy': s84['basic_only_policy']['decision'],
                     'live_rows': {c: [r['classification'], r['stock'], r['unit_price_q1_usd']]
                                   for c, r in s84['codes'].items()}},
        'original_S7_R3_hardware_unchanged_sha256': {p: sha(p) for p in S7_R3},
        'sources_sha256': {p: sha(p) for p in SOURCES},
        'artifacts_sha256': {p: sha(p) for p in artifacts},
        'open_gates': OPEN_GATES,
        'order_ready': False,
    }
    assert rec['bom_parity']['equal'], rec['bom_parity']
    hashed = [p for g in ('original_S7_R3_hardware_unchanged_sha256', 'sources_sha256', 'artifacts_sha256') for p in rec[g]]
    assert not ignored(hashed), ('hashed files must exist in a clean clone', sorted(ignored(hashed)))
    a.out.write_text(json.dumps(rec, indent=2) + '\n')
    print(json.dumps({k: rec[k] for k in ('revision', 'native_findings', 'counts', 'bom_parity', 'tests')}, indent=1))


if __name__ == '__main__':
    main()
