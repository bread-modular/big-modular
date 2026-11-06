"""S8 4HP front panel with only the MAIN LED hole (rail LEDs removed, user 2026-11-01). S9.1: the input
label reads PD 15V (15 V PD input; PD 20V again at the 20 V retarget), silk only, no geometry change. S9.2: the label
names the required contract, PD 15V 3A (a >= 45 W source; the start into a full rack needs ~4.65 A for ~2.5 ms, test S1),
silk only, no geometry change.

  python3 -B tools/build_s8_panel.py

Writes panels/front-pcb/usb-power-45w-panel.kicad_{pcb,pro}: outline, rail holes, M3 bracket holes,
USB-C aperture, MAIN LED and RESET holes and labels. Geometry: tools/mechanics_s8.py. Passive FR4, NPTH only,
no copper.
"""
import json
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_layout as bl  # noqa: E402
import mechanics_s8  # noqa: E402
from build_layout import PV, line, npth, rect, shape, text  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
PANEL = MODULE / 'panels/front-pcb/usb-power-45w-panel.kicad_pcb'
PD_LABEL = 'PD 15V 3A'        # S9.2: the requested PD contract (R1 56k, 15 V fixed PDO at 3 A)


def build():
    G = mechanics_s8.geometry()
    board = bl.new_board('Big Modular - usb-power-45w S9.2 board 4HP front panel', [
        'Passive panel, NPTH only, no copper. 4HP 20.0 x 128.5 x 1.6',
        'S8: one panel LED (MAIN); rail LEDs removed. S9.2: PD 15V 3A label.',
        'Geometry: ../../docs/design/mechanical.json'], 'S9.2')
    pw, ph, _ = G['panel_mm']
    E = pcbnew.Edge_Cuts
    rect(board, E, PV(0, 0), PV(pw, ph))
    x, y, w, h, r = G['aperture_XYWHR_mm']
    line(board, E, PV(x + r, y), PV(x + w - r, y))
    line(board, E, PV(x + w, y + r), PV(x + w, y + h - r))
    line(board, E, PV(x + w - r, y + h), PV(x + r, y + h))
    line(board, E, PV(x, y + h - r), PV(x, y + r))
    k = r * (1 - 2 ** -0.5)
    for (sx, sy), (mx, my), (ex, ey) in [
            ((x, y + r), (x + k, y + k), (x + r, y)),
            ((x + w - r, y), (x + w - k, y + k), (x + w, y + r)),
            ((x + w, y + h - r), (x + w - k, y + h - k), (x + w - r, y + h)),
            ((x + r, y + h), (x + k, y + h - k), (x, y + h - r))]:
        shape(board, E, pcbnew.SHAPE_T_ARC, 0.05, start=PV(sx, sy), mid=PV(mx, my), end=PV(ex, ey))
    holes = ([('rail', *hh) for hh in G['rail_holes_mm']] + [('bracket', *hh) for hh in G['panel_bracket_holes_mm']]
             + [(l['reference'], *l['panel_XY_diameter_mm']) for l in G['LEDs']]
             + [('SW1', *G['reset_XY_diameter_mm'])])
    for i, (role, hx, hy, d) in enumerate(holes, 1):
        npth(board, f'H{i}', f'H{i}', PV(hx, hy), d, f'NPTH {role}')
    S = pcbnew.F_SilkS
    lx = 13.6
    text(board, S, 'USB', PV(10.0, 10.6), 1.6)
    text(board, S, 'POWER', PV(10.0, 13.4), 1.6)
    text(board, S, 'USB-C', PV(lx, 32.4), 1.2)
    text(board, S, PD_LABEL, PV(lx, 34.8), 1.2)
    for l in G['LEDs']:
        text(board, S, l['label'], PV(lx, l['panel_XY_diameter_mm'][1]), 1.2)
    text(board, S, 'RESET', PV(lx, G['reset_XY_diameter_mm'][1]), 1.2)
    text(board, S, 'BIG MOD', PV(10.0, 116.0), 1.0)
    D = pcbnew.Dwgs_User
    for i, note in enumerate([
            '4HP 20.0 x 128.5 x 1.6; rail holes X12.58 Y3/125.5 (blank 4HP precedent)',
            'M3 bracket holes X6.4 Y22/106.5; USB aperture/LED X6.1/SW1 X5.8 copied from usb-power',
            'S8: D8 MAIN LED only (THT, hand-soldered); SW1 TL3340 SMT side reset; rail LEDs removed',
            'S9.2: +/-12V only, 15 V / 3 A PD input (label PD 15V 3A; PD 20V at the later 20 V retarget)',
            'S8 board: not supplier-accepted, not a release']):
        text(board, D, note, PV(pw + 40, 6 + 3 * i), 0.9)
    src_pro = PANEL.with_suffix('.kicad_pro')
    bl.save_canonical(board, PANEL, src_pro)
    pro = json.loads(src_pro.read_text())
    pro['meta']['filename'] = PANEL.with_suffix('.kicad_pro').name
    PANEL.with_suffix('.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n')
    return PANEL


if __name__ == '__main__':
    print(build())
