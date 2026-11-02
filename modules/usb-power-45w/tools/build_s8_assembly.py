"""FreeCAD half of the S8 3D assembly (run by tools/s8_mechanical.py, not by hand).

  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd tools/build_s8_assembly.py   (env S8_ASM_WORK=<dir>)

Same frame and method as tools/build_assembly.py (M1): X across the 4HP panel, Y down, Z into the case,
origin at the panel's upper-left front corner.
- Panel and board come from the NATIVE KiCad files via `kicad-cli pcb export step` (board + every placed
  part that has a KiCad library model), transformed by the documented native maps.
- Proxies for the parts without a model: L1-L3 (10.3 x 10.3 x 4.0 mm SLO1040-class body), J1 HRO USB-C and
  SW1 TL3340 (the M1 manufacturer-drawing envelopes). Brackets: tools/bracket45.py. M3 screws/nuts: proxies.
- Envelopes (not parts): mated IDC plugs + ribbons (PROPOSAL), 8 mm side-nut driver and front-nut pliers
  paths, case rails, the 4HP edge X20 and the Z50 depth plane.
Writes <work>/assembly.step, <work>/assembly.FCStd, per-category STL meshes and <work>/report.json with
the solid-interference screen (every part body vs brackets, fasteners, tool paths, panel and the other
proxies) and the X / Z extents. Nominal geometry only.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from bracket45 import bracket_shape, contract  # noqa: E402
import mechanics45 as m45  # noqa: E402
import mechanics_s8  # noqa: E402

WORK = Path(os.environ['S8_ASM_WORK'])
# Footprints without a KiCad 3D model get a maximum-body box: {ref: (L along Y, W along Z, H above F.Cu) mm}.
# S9.0 step 1: the U23 RPW0010A proxy left with +5V. Step 2: U2 TPS552892-Q1 (TI RYQ0021B, no 3D model): maximum body
# 5.1 x 3.1 x 1.0 mm (drawing 4228792/A); U2 is turned 90 deg on the board, so the 5.1 mm side runs along Z.
BODY_PROXIES = {'U2': (3.1, 5.1, 1.0), 'R109': (3.4, 1.8, .8)}     # (along Y, along Z, height) mm; R109 TA-I RLM12 max

G = mechanics_s8.geometry()
FP = json.loads((WORK / 'footprints.json').read_text())
DESIGN = Path(os.environ.get('S8_DESIGN_ROOT', str(MODULE)))
BOARD = DESIGN / 'hardware/single/usb-power-45w-single.kicad_pcb'
PANEL = MODULE / 'panels/front-pcb/usb-power-45w-single-panel.kicad_pcb'


def matrix(rows):
    m = App.Matrix()
    (m.A11, m.A12, m.A13, m.A14), (m.A21, m.A22, m.A23, m.A24), (m.A31, m.A32, m.A33, m.A34) = rows
    return m


# KiCad STEP (user origin 0,0): x = native x, y = -native y, z up from B.Cu (F face 1.6).
# Board: X = 2.5 + z, Y = x - 35.75, Z = 104.275 + y.  Panel: X = x - 50, Y = -y - 30, Z = 1.6 - z.
M_BOARD = matrix([(0, 0, 1, G['carrier_X_mm'][0]), (1, 0, 0, -35.75), (0, 1, 0, 104.275)])
ox, oy = G['native_panel_origin_mm']
M_PANEL = matrix([(1, 0, 0, -ox), (0, -1, 0, -oy), (0, 0, -1, G['panel_mm'][2])])
FCU = G['carrier_X_mm'][1]


def step_export(pcb, out, extra):
    cmd = ['kicad-cli', 'pcb', 'export', 'step', '--force', '--user-origin', '0x0mm',
           '-D', 'KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels', '-o', str(out)] + extra + [str(pcb)]
    env = {k: v for k, v in os.environ.items() if k in ('HOME', 'USER', 'LANG', 'TMPDIR')}
    env['PATH'] = '/usr/bin:/bin'          # FreeCAD's AppImage environment breaks the system kicad-cli
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, env=env)
    return Part.read(str(out))


def box(r):
    (x0, x1), (y0, y1), (z0, z1) = r
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def hexnut(centre, axis, af, t):
    r = af / math.sqrt(3)
    pts = [App.Vector(r * math.cos(math.radians(30 + 60 * i)), r * math.sin(math.radians(30 + 60 * i)), 0) for i in range(7)]
    prism = Part.Face(Part.makePolygon(pts)).extrude(App.Vector(0, 0, t))
    prism = prism.cut(Part.makeCylinder(1.5, t + 0.2, App.Vector(0, 0, -0.1)))
    if axis == 'X':
        prism.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), 90)
    prism.translate(App.Vector(*centre))
    return prism


def fasteners():
    b = G['brackets']
    out = {'screws': [], 'nuts': [], 'tools': []}
    fx, sz = b['front_hole_X_mm'], b['side_hole_Z_mm']
    for y in b['Y_centres_mm']:
        out['screws'].append(Part.makeCylinder(b['front_head_diameter_max_mm'] / 2, 2.4, App.Vector(fx, y, -2.4)))
        out['screws'].append(Part.makeCylinder(1.5, b['front_length_mm'], App.Vector(fx, y, 0)))
        out['nuts'].append(hexnut((fx, y, b['front_foot_Z_mm'][1]), 'Z', b['nut_AF_max_mm'], b['nut_thickness_max_mm']))
        x0 = b['outer_X_mm'][0]
        out['screws'].append(Part.makeCone(b['side_head_diameter_max_mm'] / 2, 1.5, 1.0, App.Vector(x0, y, sz), App.Vector(1, 0, 0)))
        out['screws'].append(Part.makeCylinder(1.5, b['side_length_mm'], App.Vector(x0, y, sz), App.Vector(1, 0, 0)))
        out['nuts'].append(hexnut((FCU, y, sz), 'X', b['nut_AF_max_mm'], b['nut_thickness_max_mm']))
        t = m45.fastener_solids(G, y)['tools']
        r = b['side_nut_driver_diameter_max_mm'] / 2
        # 8 mm nut driver from +X down onto the F-side nut (stops on the nut top), front-nut pliers
        out['tools'].append(Part.makeCylinder(r, 30 - (FCU + b['nut_thickness_max_mm']),
                                              App.Vector(FCU + b['nut_thickness_max_mm'], y, sz), App.Vector(1, 0, 0)))
        out['tools'].append(box(t['front_nut_pliers']))
    return out


def classify(board):
    """Board body vs part bodies; each part body is tagged with the nearest footprint (courtyard centre)."""
    body, parts = [], {}
    for s in board.childShapes():
        bb = s.BoundBox
        if bb.YLength > 90 and bb.XLength < 2:
            body.append(s)
            continue
        c = (bb.Center.y, bb.Center.z)
        ref = min(FP, key=lambda r: math.dist(c, FP[r]['centre_YZ']))
        parts.setdefault(ref, []).append(s)
    return body, parts


def main():
    with tempfile.TemporaryDirectory() as tmp:
        board = step_export(BOARD, Path(tmp) / 'board.step', [])
        panel = step_export(PANEL, Path(tmp) / 'panel.step', ['--include-silkscreen'])
    board = board.copy()
    board.transformShape(M_BOARD)
    panel = panel.copy()
    panel.transformShape(M_PANEL)
    pb = panel.BoundBox
    assert abs(pb.XMin) < 1e-6 and abs(pb.XMax - G['panel_mm'][0]) < 1e-6 and abs(pb.YMax - G['panel_mm'][1]) < 1e-6, pb
    body, parts = classify(board)
    cb = Part.makeCompound(body).BoundBox
    assert abs(cb.XMin - G['carrier_X_mm'][0]) < 1e-6 and abs(cb.YMin - G['carrier_Y_mm'][0]) < 1e-6, cb
    assert abs(cb.ZMin - G['carrier_Z_mm'][0]) < 1e-6 and abs(cb.ZMax - G['carrier_Z_mm'][1]) < 1e-6, cb
    modelled = sorted(parts)
    # Proxies for parts without a KiCad model
    env = m45.envelopes(G)
    proxies = {r: [box(env[r][1])] for r in ('J1', 'SW1')}
    sw = G['switch']
    proxies['SW1'].append(Part.makeCylinder(sw['actuator_diameter_mm'] / 2, sw['body_Z_mm'][0] - sw['actuator_tip_Z_mm'],
                                            App.Vector(FCU + sw['actuator_axis_height_mm'], G['reset_XY_diameter_mm'][1],
                                                       sw['actuator_tip_Z_mm'])))
    L, W, H = G['inductor_body']['body_LWH_max_mm']
    for r in G['inductor_body']['parts']:
        y, z = FP[r]['centre_YZ']
        proxies[r] = [box([[FCU, FCU + H], [y - L / 2, y + L / 2], [z - W / 2, z + W / 2]])]
    for r, (bl, bw, bh) in BODY_PROXIES.items():        # parts whose footprint has no 3D model: maximum-body boxes
        y, z = FP[r]['centre_YZ']
        proxies[r] = [box([[FCU, FCU + bh], [y - bl / 2, y + bl / 2], [z - bw / 2, z + bw / 2]])]
    c = contract()
    brackets = []
    for y in c['Y_centres']:
        s = bracket_shape(Part, App, c)
        s.translate(App.Vector(c['origin_XZ'][0], y - c['width_y'] / 2, c['origin_XZ'][1]))
        brackets.append(s)
    f = fasteners()
    plugs = [box(env[h['reference'] + '_plug'][1]) for h in G['headers']]
    ribbons = [box(env[h['reference'] + '_ribbon'][1]) for h in G['headers']]
    rp = G['rail_profile_YZ_mm']
    z1 = G['panel_mm'][2]
    rails = [box([[-4, 24], rp['top_Y'], [z1, z1 + rp['depth_behind_rear']]]),
             box([[-4, 24], rp['bottom_Y'], [z1, z1 + rp['depth_behind_rear']]])]
    zl = G['depth_target']['limit_from_panel_front_mm']
    limits = [box([[G['panel_mm'][0], G['panel_mm'][0] + 0.05], [0, G['panel_mm'][1]], [0, zl]]),
              box([[0, G['panel_mm'][0]], [0, G['panel_mm'][1]], [zl, zl + 0.05]])]
    groups = {'inductors': list(G['inductor_body']['parts']), 'headers': ['J2', 'J3'], 'led': ['D8'], 'ics': [],
              'passives': []}
    cat_parts = {k: [] for k in groups}
    for ref, shapes in parts.items():
        k = next((g for g, refs in groups.items() if ref in refs), None)
        if k is None:
            k = 'ics' if ref[0] in 'UQ' or ref.startswith(('D', 'F')) else 'passives'
        cat_parts[k] += shapes
    cats = {
        'panel': ([panel], 'Native S8 4HP panel PCB (kicad-cli STEP): MAIN LED + RESET + USB-C'),
        'carrier': (body, 'Native S8 board 100.5 x 48 x 1.6, unrouted, every part on F'),
        'ics': (cat_parts['ics'], 'ICs, transistors, diodes, fuse (KiCad library models)'),
        'passives': (cat_parts['passives'], 'R / C (KiCad library models)'),
        'headers': (cat_parts['headers'], 'J2/J3 2x8 box headers (THT, KiCad model)'),
        'led': (cat_parts['led'], 'D8 3 mm MAIN LED (THT)'),
        'inductors': (sum((proxies[r] for r in groups['inductors']), []), 'L1/L3 PROXY 10.3 x 10.3 x 4.0 (no model)'),
        'ui_envelopes': (proxies['J1'] + proxies['SW1'] + sum((proxies[r] for r in BODY_PROXIES), []),
                         'J1 / SW1 maximum body envelopes' + ''.join(f' / {r}' for r in BODY_PROXIES) + ' (no model)'),
        'brackets': (brackets, 'Plain M3 L brackets x2 (tools/bracket45.py)'),
        'screws': (f['screws'], 'M3x8 pan (panel) + M3x8 90deg flat (side) PROXIES'),
        'nuts': (f['nuts'], 'M3 hex nut AF5.5 x 2.4 PROXIES'),
        'tools': (f['tools'], 'ENVELOPE: 8 mm side-nut driver / front-nut pliers paths (out of rack)'),
        'plugs': (plugs, 'ENVELOPE PROPOSAL: mated 16-pin IDC socket, <= 14.8 mm above F.Cu'),
        'ribbons': (ribbons, 'ENVELOPE PROPOSAL: 16-way ribbon leaving +Z toward the bus'),
        'rails': (rails, 'CONTEXT: case rail section'),
        'limits': (limits, 'LIMITS: 4HP edge X20.0 and the Z50 depth plane (user limit)'),
    }
    stl = WORK / 'stl'
    stl.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument('usb_power_45w_single_assembly')
    report = {'categories': {}}
    for name, (shapes, label) in cats.items():
        comp = Part.makeCompound(shapes)
        o = doc.addObject('Part::Feature', name)
        o.Label, o.Label2, o.Shape = name, label, comp
        bb = comp.BoundBox
        report['categories'][name] = {'label': label, 'count': len(shapes),
                                      'bbox_XYZ': [[round(bb.XMin, 3), round(bb.XMax, 3)], [round(bb.YMin, 3), round(bb.YMax, 3)],
                                                   [round(bb.ZMin, 3), round(bb.ZMax, 3)]]}
        MeshPart.meshFromShape(Shape=comp, LinearDeflection=0.05, AngularDeflection=0.3).write(str(stl / f'{name}.stl'))
    doc.recompute()
    doc.saveAs(str(WORK / 'assembly.FCStd'))
    Part.export([o for o in doc.Objects if o.Name not in ('limits',)], str(WORK / 'assembly.step'))
    # Interference screen: every part body / proxy vs every other solid family and vs the others' bodies.
    bodies = {ref: Part.makeCompound(s) for ref, s in parts.items()}
    bodies.update({r: Part.makeCompound(v) for r, v in proxies.items()})
    fixed = {'panel': [panel], 'brackets': brackets, 'nuts': f['nuts'], 'screws': f['screws'], 'tools': f['tools'],
             'plugs': plugs, 'ribbons': ribbons, 'rails': rails}
    hits = []
    refs = sorted(bodies)
    for name, shapes in fixed.items():
        A = Part.makeCompound(shapes)
        for r in refs:
            if r in ('J2', 'J3') and name in ('plugs', 'ribbons'):
                continue                       # the plug mates into its own header by definition
            if r in ('J1', 'SW1', 'D8') and name == 'panel':
                continue                       # panel-registered parts reach into their apertures by design
            B = bodies[r]
            if A.BoundBox.intersect(B.BoundBox):
                v = A.common(B).Volume
                if v > 1e-3:
                    hits.append([name, r, round(v, 4)])
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            if bodies[a].BoundBox.intersect(bodies[b].BoundBox):
                v = bodies[a].common(bodies[b]).Volume
                if v > 1e-3:
                    hits.append([a, b, round(v, 4)])
    allparts = Part.makeCompound(list(bodies.values()))
    pb = allparts.BoundBox
    report['solid_interference_mm3'] = hits
    report['parts_with_model'] = len(modelled)
    report['proxies'] = sorted(proxies)
    report['extents'] = {'parts_X_max': round(pb.XMax, 3), 'parts_X_min': round(pb.XMin, 3),
                         'parts_Z_max': round(pb.ZMax, 3), 'board_Z_max': round(cb.ZMax, 3),
                         'margin_to_X20': round(G['panel_mm'][0] - pb.XMax, 3),
                         'tallest': sorted(((round(s.BoundBox.XMax - FCU, 2), r) for r, s in bodies.items()), reverse=True)[:6]}
    (WORK / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps({k: report[k] for k in ('solid_interference_mm3', 'extents', 'parts_with_model', 'proxies')}, indent=1))


main()
