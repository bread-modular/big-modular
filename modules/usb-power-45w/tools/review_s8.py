"""S8 review record: native findings, exact parity, test results, placement/mechanics/sourcing summaries and the
SHA-256 of every source and artifact, assembled from fresh reports (no hand-copied numbers).

  python3 -B tools/review_s8.py --check research/s84/check-final --tests-log research/s84/tests-final.log \
      --out docs/s8-single/review-s84.json

--check is a NEW native check directory of the shared tool (opt/kicad-tools/kicad_tools.py check, summary.json),
--tests-log the verbose unittest output of `python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v`.
Read-only apart from --out. S8.4 replaces the S8.3 record (review-s83.json, kept in git history at a12edd3).
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REVISION = 'S8.4 / P1.4'
S7_R3 = sorted(str(p.relative_to(MODULE)) for p in (MODULE / 'hardware').glob('*.kicad_*')
               if p.suffix in ('.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sym', '.kicad_prl'))
SOURCES = (['hardware/USBPOWER45.pretty/TI_RPW0010A_VQFN-HR-10_2x2mm.kicad_mod']
           + sorted(f'hardware/single/{p.name}' for p in (MODULE / 'hardware/single').glob('*.kicad_*'))
           + [f'tools/{n}.py' for n in ('build_s8', 'build_s8_assembly', 'build_s8_board', 'build_s8_panel',
                                        'check_s8_board', 'circuit_s8', 'hierarchy_s8', 'mechanics_s8', 'place_s8',
                                        'render_s8', 'review_s8', 's83_parts', 's8_calcs', 's8_mechanical',
                                        's8_sourcing', 'test_s8', 'verify_s8')])
CHANGELOG = [
    ('C1', 'U23 FLT (pin 4) taken off P5_OK: own pull-up R108 + test pad TP21 (net P5_FLT_N), diagnostic only. '
           'P5_OK = AUXOFF + U18. Hot plug into a live +5V bus / load release held downstream no longer latches.'),
    ('C2', '<6 V at the header stays NOT guaranteed: 3 us case 6.33 V, ~193 us above 6 V; 30 V / 1 ohm / 3 us '
           'stress case added (6.52 V). Wording kept plain in doc, calcs and validation.'),
    ('M1', 'TIMER_GO = RUN AND MAIN_OK (U13 pin 10 was V20_OK): qualification starts with the U2/U3 enable. R83 '
           '220k -> 200k re-centres V20_OK (14.6-17.7 V) below the 18.25 V minimum loaded PD input.'),
    ('M2', 'R11/R12 0.1 % / 25 ppm (setpoint 4.856-5.114 V); calcs ovlo_release (imposed-current model): a release '
           'from U23 ILIM max peaks 0.109 V below the OVLO minimum and 0.201 V below the U20 guard; OVLO falling band '
           '5.079-5.336 V computed; the -35 mV reconnect corner stays open (fail-safe latch).'),
    ('M3', 'v3v3_loss states: U20 may stay powered from VPD, nothing can be enabled (R64 holds RUN low), node current '
           '<= 0.15 mA; D22 is not a guaranteed cold clamp. Stale "U20 unpowered" rationale removed.'),
    ('M4', 'Local-loop contract (check_s8_board LOCAL_LOOPS, board-p1.json local_loops): U23 IN/OUT 22u <= 3.5 mm, '
           'D21/D23 <= 6 mm, IC bypass <= 4.5/6 mm. U23 cell re-placed (P1.4); every row passes.'),
    ('M5', 'Published conservative rating 2.5 / 2.0 / 0.9 A (+12 / +5 / -12 V), <= 45 W delivered, for VPD >= 18.25 V '
           '(converter input >= 17.25 V after D10 + U5): 75 % of the minimum capability there, nearest 0.1 A; +5V 2.0 A = '
           '75.6 % of U23 ILIM min, 0.65 A headroom with ITIMER open; not specified below (calcs rating).'),
    ('M6', '-12V start-up per the LMR38020 hiccup rule (|Vout| < 40 % after blanking): hiccup model 1.08 mF at the '
           '15.23 V converter input of the U5 turn-on minimum, 1 A, half blanking; published allowance 0.846 mF (TI ~1000 uF '
           'total-COUT guidance minus the rated bank) vs the 0.44 mF typical rack; acceptance test added.'),
    ('M7', 'U23 copper-pad mask expansion 0.05 -> 0.025 mm: every mask web 0.15 mm (IN/OUT incl.); TP18-to-+5V '
           'no-short bring-up check in the notes, validation and doc.'),
    ('M8', 'Basic-only policy decided: Extended accepted for the ten 0.1 % dividers only (sourcing.json / s84-sourcing.json '
           'basic_only_policy); calcs basic_only_counterfactual shows four screens failing with 1 % parts.'),
    ('M9', 'mechanical.json risks: IDC strain relief 0.4 mm past the 4HP edge (not approved), IDC envelope 1.1 mm margin, '
           'case depth, nominal proxies.'),
]
OPEN_GATES = [
    '429 routing opens (unrouted fit placement); the local-loop screens are straight-line distances, not routed loops',
    'No guaranteed <6 V header peak: U23 OVLO response is typical-only, parasitics and stored energy unbounded',
    'OVLO-only short/startup events can auto-recover before the qualified latch; after a genuine OVLO trip U23 may '
    'stay open at stacked corners (latched off until RESET)',
    'VPD ringing at U18/U20, cold MON_OVN clamp, replug into a rack holding -12V, power-down sequences',
    'Converter stability with the banks, DC bias, startup foldback, thermal, load-release and -12V rack start-up tests',
    'Published rating is a datasheet-minimum prototype rating, not measured; connector/cable current and fit',
    'Manual fabrication/CAM and assembly review; U23 mask-web capability confirmation with the fab',
]


def sha(rel):
    return hashlib.sha256((MODULE / rel).read_bytes()).hexdigest()


def tests(log):
    text = Path(log).read_text(errors='replace')
    m = re.search(r'^Ran (\d+) tests? in', text, re.M)
    ok = re.search(r'^OK\b', text, re.M) is not None
    s8 = len(set(re.findall(r'\((test_s8\.[\w.]+)\)', text)))
    return {'ran': int(m.group(1)) if m else None, 'ok': ok, 's8_tests': s8,
            'log': str(Path(log).resolve().relative_to(MODULE)) if Path(log).resolve().is_relative_to(MODULE) else str(log)}


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
        'replaces': 'review-s83.json (S8.3 / P1.3 record, git a12edd3)',
        'changelog': [{'item': k, 'change': v} for k, v in CHANGELOG],
        'native_findings': summary['findings'],
        'exact_native_ref_pin_net_parity': summary['ref_pin_net_parity'],
        'native_sources_unchanged_by_check': summary['source_unchanged'],
        'raw_reports': str(a.check.resolve().relative_to(MODULE)),
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
                      'moved_retained_refs_P13_to_P14': place['moved_retained_refs'],
                      'added_refs': place['added_refs'],
                      'pad_mask_refreshed_from_library': sorted(place.get('pad_mask_refreshed_from_library', {})),
                      'courtyard_fill': board['area_mm2']['fill_of_inset']},
        'mechanical': {'overlaps': len(asm['solid_interference_mm3']), 'proxies': asm['proxies'],
                       'risks': {r['id']: r.get('value_mm') for r in mech['risks']}, 'nominal_only': True},
        'electrical_screens': {
            'FLT_isolated_from_latch': val['disconnect']['FLT_isolated_from_latch'],
            'P5_FLT_N_members': val['disconnect']['P5_FLT_N_members'],
            'startup_arming': val['startup_arming'],
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
        'sourcing': {'selected_part_evidence': 's84-sourcing.json', 'S8_3_selection_evidence': 's83-sourcing.json',
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
    a.out.write_text(json.dumps(rec, indent=2) + '\n')
    print(json.dumps({k: rec[k] for k in ('revision', 'native_findings', 'counts', 'bom_parity', 'tests')}, indent=1))


if __name__ == '__main__':
    main()
