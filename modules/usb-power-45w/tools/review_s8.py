"""S8 review record: native findings, exact parity, test results, placement/mechanics/sourcing summaries and the
SHA-256 of every source and artifact, assembled from fresh reports (no hand-copied numbers).

  python3 -B tools/review_s8.py --check research/s91/check-final --tests-log research/s91/tests-final.log \
      --out docs/s8-single/review-s91.json

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
REVISION = 'S9.1 / P2.1'
TRACKED_KICAD = ('.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sym')   # *.kicad_prl is git-ignored
S7_R3 = sorted(str(p.relative_to(MODULE)) for p in (MODULE / 'hardware').glob('*.kicad_*') if p.suffix in TRACKED_KICAD)
PANEL = ['panels/front-pcb/usb-power-45w-single-panel.kicad_pcb', 'panels/front-pcb/usb-power-45w-single-panel.kicad_pro']
SOURCES = (sorted(f'hardware/single/{p.name}' for p in (MODULE / 'hardware/single').glob('*.kicad_*')
                  if p.suffix in TRACKED_KICAD)
           + ['hardware/single/fp-lib-table', 'hardware/single/sym-lib-table'] + PANEL
           + [f'tools/{n}.py' for n in ('build_s8', 'build_s8_assembly', 'build_s8_board', 'build_s8_panel',
                                        'check_s8_board', 'circuit_s8', 'hierarchy_s8', 'mechanics_s8', 'place_s8',
                                        'render_s8', 'review_s8', 's8_calcs', 's8_mechanical', 's8_sourcing', 's90_parts',
                                        's91_analysis', 'test_s8', 'verify_s8')])
CHANGELOG = [
    ('1 Critical', 'Q1 now takes its emitter supply from own VPD, with RUN AND MAIN_LED_OK series base sinks Q14/Q15 and R112 off pullup. D24 SMBJ16A finite-energy VIN clamp; D25 slew-limited negative clamp; D26 local output backstop. No self-enable from output bus. Hard hotplug and powered paralleling remain unqualified.'),
    ('2 Input minimum', 'R2/R3 precision 100k/10k plus R114 510 ohm: on 12.263-12.976V, off 11.365-12.193V. 13.5V at module includes 0.75V cable drop at 3A. Falling >=11.8V is not guaranteed and is explicitly not claimed.'),
    ('3 Thermal', 'R109 18mOhm WSLP1206R0180FEA: 2.621-2.940A. Screen Tj at 50C ambient 108.2C maximum vs 125C recommendation. Procurement remains open.'),
    ('4 Ground', 'AGND_U2 contains U2.5/.17 and analog returns, joined to GND/PGND only through R113 at C82.2; explicit placement and native regression.'),
    ('5 Loop', 'R111 6.8k / C83 100nF; full complex PI/boost/buck plant across 13824 sampled corners. External positive capacitance restricted to 0-440uF with documented cable/passive-load bounds; no arbitrary active-rack stability claim.'),
    ('6 Startup', '3A source resource/qualification matrix and full power-reset/epoch tests; repeated autonomous resets FAIL qualification rather than restarting a passing record. STARTED remains volatile and one-shot per powered epoch.'),
    ('7 Preserved', '+5V absent; 15V PD R1=56k; TPS552892-Q1 retained; S8.5 STARTED retained; crowbar deferred/open; 20V retarget includes clamp replacements. No tracks, vias or zones added.'),
]
OPEN_GATES = [
    'Unrouted placement; all connectivity opens are intentional at P2.1, not a fabrication release',
    'Bench Bode and thermal validation; sampled model is not measured arbitrary-rack stability',
    'Hard/fast live-bus hotplug, cold negative VIN clamp and sustained enabled reverse power remain unqualified',
    'TVS clamps are finite-energy backstops, not a sustained bus shunt or downstream 16V protection',
    '3A source/startup and full power-reset qualification not performed on hardware; no nonvolatile lockout',
    'R109 lacks verified supplier C-code; new-code prices and Economic eligibility unknown; sourcing gate open',
    'Replug/POR nuisance race remains open; downstream OV qualification and crowbar vs eFuse deferred',
    'Routed loops, connector/cable thermal and mechanical fit, CAM/assembly signoff remain open',
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
        'replaces': 'review-s90.json (S9.0 / P2.0 record in git d7d7219)',
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
                      'basis': 'S9.1 / P2.1 synchronized from S9.0; no routing',
                      'replaced_footprints': place.get('replaced_footprints', {}),
                      'moved_retained_refs': place['moved_retained_refs'],
                      'added_refs': place['added_refs'], 'removed_refs': place['removed_refs'],
                      'courtyard_fill': board['area_mm2']['fill_of_inset']},
        'mechanical': {'overlaps': len(asm['solid_interference_mm3']), 'proxies': asm['proxies'],
                       'risks': {r['id']: r.get('value_mm') for r in mech['risks']}, 'nominal_only': True},
        'S91_input_qualification': calcs['input_qualification'],
        'S91_enable_logic': calcs['enable_logic'],
        'S91_compensation': b['compensation'],
        'S91_startup_qualification': calcs['startup_qualification'],
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
        'sourcing': {'selected_part_evidence': 's91-sourcing.json for new parts (unknown live eligibility/prices); s90/s84/s83 and sourcing.json for dated retained parts',
                     'earlier_evidence': ['s84-sourcing.json', 's83-sourcing.json'],
                     'parts_partial_subtotal_q1_usd': src['summary']['S8_parts_usd_q1'],
                     'unpriced_codes': src['summary']['S8_unpriced_codes'],
                     'manual_parts_no_LCSC': src['summary']['manual_parts_no_LCSC']['S8'],
                     'failures': src['summary']['failures'],
                     'codes': src['summary']['S8_codes'], 'placements': src['summary']['S8_placements'],
                     'all_parts_fresh_live_audit': False,
                     'basic_only_policy': src['basic_only_policy']['decision'],
                     'live_rows': {c: [r['classification'], r['stock'], r['unit_price_q1_usd'],
                                       (r.get('evidence') or {}).get('retrieved_at_utc')] for c, r in s90['codes'].items()},
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
