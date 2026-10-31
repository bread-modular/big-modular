"""Build the usb-power-45w M1 3D mechanical-preview assembly with FreeCAD (headless).

Run from the repository root after tools/build_layout.py:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd modules/usb-power-45w/tools/build_assembly.py

All parts share ONE frame (tools/mechanics45.py): X across the panel, Y down, Z into the
case, origin at the panel's upper-left front corner.
- Panel and carrier come from the NATIVE KiCad boards via `kicad-cli pcb export step`
  (board bodies + KiCad library models of the placed parts), transformed by the documented
  native maps. Parked SMD parts are not exported (they are not placed).
- Brackets: tools/bracket45.py (same solid as the printable bracket).
- J1/SW1 have no verified model: dimensioned manufacturer-drawing envelopes.
- M3 screws/nuts: nominal ISO-size proxies. IDC plug/ribbon, tool paths, case rail,
  4HP edge and depth-limit planes: labelled ENVELOPE/PROXY objects, not parts.
Writes docs/mechanical-preview/usb-power-45w-assembly.{step,FCStd} and per-category STL
meshes in research/mech-preview/stl/ for tools/render_preview.py. Nominal geometry only.
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
from mechanics45 import envelopes, fastener_solids  # noqa: E402

G = json.loads((MODULE / 'docs/mechanical-geometry.json').read_text())
OUT = MODULE / 'docs/mechanical-preview'
STL = MODULE / 'research/mech-preview/stl'
CARRIER = MODULE / 'hardware/usb-power-45w.kicad_pcb'
PANEL = MODULE / 'panels/front-pcb/usb-power-45w-panel.kicad_pcb'
PLACED = ['J1', 'SW1', 'J2', 'J3'] + [l['reference'] for l in G['LEDs']] + [c['reference'] for c in G['cans']['parts']]


def matrix(rows):
    m = App.Matrix()
    (m.A11, m.A12, m.A13, m.A14), (m.A21, m.A22, m.A23, m.A24), (m.A31, m.A32, m.A33, m.A34) = rows
    return m


# KiCad STEP (user origin 0,0): x = native x, y = -native y, z up from B.Cu (F face ~1.6).
# Carrier: X = 2.5 + z, Y = x - 35.75, Z = 104.275 + y.  Panel: X = x - 50, Y = -y - 30, Z = 1.6 - z.
M_CARRIER = matrix([(0, 0, 1, G['carrier_X_mm'][0]), (1, 0, 0, -35.75), (0, 1, 0, 104.275)])
ox, oy = G['native_panel_origin_mm']
M_PANEL = matrix([(1, 0, 0, -ox), (0, -1, 0, -oy), (0, 0, -1, G['panel_mm'][2])])


def step_export(pcb, out, extra):
    cmd = ['kicad-cli', 'pcb', 'export', 'step', '--force', '--user-origin', '0x0mm',
           '-D', 'KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels', '-o', str(out)] + extra + [str(pcb)]
    # FreeCAD's AppImage environment breaks the system kicad-cli: run it with a clean environment.
    env = {k: v for k, v in os.environ.items() if k in ('HOME', 'USER', 'LANG', 'TMPDIR')}
    env['PATH'] = '/usr/bin:/bin'
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
    fx = b['front_hole_X_mm']
    sz = b['side_hole_Z_mm']
    for y in b['Y_centres_mm']:
        # Front M3x8 pan/button head: head in front of the panel, 8 mm shank from Z0.
        out['screws'].append(Part.makeCylinder(b['front_head_diameter_max_mm'] / 2, 2.4, App.Vector(fx, y, -2.4)))
        out['screws'].append(Part.makeCylinder(1.5, b['front_length_mm'], App.Vector(fx, y, 0)))
        out['nuts'].append(hexnut((fx, y, b['front_foot_Z_mm'][1]), 'Z', b['nut_AF_max_mm'], b['nut_thickness_max_mm']))
        # Side M3x8 90-degree flat head, flush at the bracket outer face X0.1, nut on F.Cu.
        x0 = b['outer_X_mm'][0]
        out['screws'].append(Part.makeCone(b['side_head_diameter_max_mm'] / 2, 1.5, 1.0, App.Vector(x0, y, sz), App.Vector(1, 0, 0)))
        out['screws'].append(Part.makeCylinder(1.5, b['side_length_mm'], App.Vector(x0, y, sz), App.Vector(1, 0, 0)))
        out['nuts'].append(hexnut((G['carrier_X_mm'][1], y, sz), 'X', b['nut_AF_max_mm'], b['nut_thickness_max_mm']))
        t = fastener_solids(G, y)['tools']
        r = b['side_nut_driver_diameter_max_mm'] / 2
        out['tools'].append(Part.makeCylinder(r, 30 - 6.6, App.Vector(6.6, y, sz), App.Vector(1, 0, 0)))
        out['tools'].append(box(t['front_nut_pliers']))
    return out


def classify(carrier):
    """Split the native STEP compound into board body and per-reference component bodies."""
    centres = {}
    for l in G['LEDs']:
        centres[l['reference']] = (6.1, l['panel_XY_diameter_mm'][1], 3.5)
    for h in G['headers']:
        e = G['envelopes_XYZ_mm'][h['reference']]['XYZ']
        centres[h['reference']] = tuple(sum(v) / 2 for v in e)
    for c in G['cans']['parts']:
        centres[c['reference']] = (8.1, c['YZ_mm'][0], c['YZ_mm'][1])
    groups = {'board': [], 'led': [], 'header': [], 'can': []}
    for s in carrier.childShapes():
        bb = s.BoundBox
        if bb.YLength > 90:
            groups['board'].append(s)
            continue
        c = (bb.Center.x, bb.Center.y, bb.Center.z)
        ref = min(centres, key=lambda r: math.dist(c, centres[r]))
        groups['led' if ref.startswith('D') else 'header' if ref.startswith('J') else 'can'].append(s)
    return groups


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    STL.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        carrier = step_export(CARRIER, Path(tmp) / 'carrier.step', ['--component-filter', ','.join(PLACED)])
        panel = step_export(PANEL, Path(tmp) / 'panel.step', ['--include-silkscreen'])
    carrier = carrier.copy()
    carrier.transformShape(M_CARRIER)
    panel = panel.copy()
    panel.transformShape(M_PANEL)
    groups = classify(carrier)
    pb = panel.BoundBox
    assert abs(pb.XMin) < 1e-6 and abs(pb.XMax - G['panel_mm'][0]) < 1e-6 and abs(pb.YMax - G['panel_mm'][1]) < 1e-6, pb
    cb = Part.makeCompound(groups['board']).BoundBox
    assert abs(cb.XMin - G['carrier_X_mm'][0]) < 1e-6 and abs(cb.YMin - G['carrier_Y_mm'][0]) < 1e-6, cb
    assert abs(cb.ZMin - G['carrier_Z_mm'][0]) < 1e-6 and abs(cb.ZMax - G['carrier_Z_mm'][1]) < 1e-6, cb
    c = contract()
    brackets = []
    for y in c['Y_centres']:
        s = bracket_shape(Part, App, c)
        s.translate(App.Vector(c['origin_XZ'][0], y - c['width_y'] / 2, c['origin_XZ'][1]))
        brackets.append(s)
    env = envelopes(G)
    ui = [box(env[r][1]) for r in ('J1', 'SW1')]
    # SW1 actuator stub (2.0 diameter) from the body front to its tip Z2.05.
    sw = G['switch']
    ui.append(Part.makeCylinder(sw['actuator_diameter_mm'] / 2, sw['body_Z_mm'][0] - sw['actuator_tip_Z_mm'],
                                App.Vector(G['carrier_X_mm'][1] + sw['actuator_axis_height_mm'], G['reset_XY_diameter_mm'][1],
                                           sw['actuator_tip_Z_mm'])))
    plugs = [box(env[h['reference'] + '_plug'][1]) for h in G['headers']]
    ribbons = [box(env[h['reference'] + '_ribbon'][1]) for h in G['headers']]
    mp = G['mating_plug']
    worst = []
    for h in G['headers']:
        e = env[h['reference'] + '_plug'][1]
        worst.append(box([[mp['proposal_X_mm'][1], G['carrier_X_mm'][1] + mp['strain_relief_worst_height_mm']], e[1], e[2]]))
    f = fasteners()
    rp = G['rail_profile_YZ_mm']
    z1 = G['panel_mm'][2]
    rails = [box([[-4, 24], rp['top_Y'], [z1, z1 + rp['depth_behind_rear']]]),
             box([[-4, 24], rp['bottom_Y'], [z1, z1 + rp['depth_behind_rear']]])]
    zl = G['depth_target']['limit_behind_panel_rear_mm'] + z1
    limits = [box([[G['panel_mm'][0], G['panel_mm'][0] + 0.05], [0, G['panel_mm'][1]], [0, zl]]),
              box([[0, G['panel_mm'][0]], [0, G['panel_mm'][1]], [42.0, 42.05]]),
              box([[0, G['panel_mm'][0]], [0, G['panel_mm'][1]], [zl, zl + 0.05]])]
    cats = {
        'panel': ([panel], 'Native 4HP panel PCB (kicad-cli STEP)'),
        'carrier': (groups['board'], 'Native carrier PCB body (kicad-cli STEP)'),
        'leds': (groups['led'], 'KiCad LED_D3.0mm_Horizontal model (THT, hand-soldered)'),
        'headers': (groups['header'], 'KiCad IDC-Header_2x08 model (THT, hand-soldered)'),
        'cans': (groups['can'], 'GENERIC KiCad CP_Elec_6.3x7.7 model (7.7 body; BOM ~8.0 max incl. base/solder, checks use 8.0) - envelope, NOT exact model; PROVISIONAL positions'),
        'ui_envelopes': (ui, 'J1 HRO USB-C / SW1 TL3340 (SMT) drawing envelopes - NO verified model'),
        'brackets': (brackets, 'Plain M3 L brackets x2 (tools/bracket45.py)'),
        'screws': (f['screws'], 'M3x8 pan (panel) + M3x8 90deg flat (side) PROXIES'),
        'nuts': (f['nuts'], 'M3 hex nut AF5.5 x 2.4 PROXIES'),
        'tools': (f['tools'], 'ENVELOPE: 8 mm side nut driver / front-nut pliers paths (out of rack)'),
        'plugs': (plugs, 'ENVELOPE PROPOSAL: mated 16-pin IDC socket, <=14.8 mm above F.Cu'),
        'ribbons': (ribbons, 'ENVELOPE PROPOSAL: 16-way 1.27 mm ribbon leaving +Z (to bus)'),
        'strain_relief_conflict': (worst, 'CONFLICT ENVELOPE: clip strain relief worst case 16.3 mm -> X20.4'),
        'rails': (rails, 'CONTEXT: case rail section (case/tools/build_case.py)'),
        'limits': (limits, 'LIMITS: 4HP edge X20.0; Z42.0 from panel FRONT (=40.4 behind rear) and Z43.6 (=42 behind rear); cable envelope to Z50 is beyond both'),
    }
    doc = App.newDocument('usb_power_45w_assembly')
    report = {}
    for name, (shapes, label) in cats.items():
        comp = Part.makeCompound(shapes)
        o = doc.addObject('Part::Feature', name)
        o.Label = name
        o.Label2 = label
        o.Shape = comp
        bb = comp.BoundBox
        report[name] = {'label': label, 'count': len(shapes),
                        'bbox_XYZ': [[round(bb.XMin, 3), round(bb.XMax, 3)], [round(bb.YMin, 3), round(bb.YMax, 3)],
                                     [round(bb.ZMin, 3), round(bb.ZMax, 3)]]}
        mesh = MeshPart.meshFromShape(Shape=comp, LinearDeflection=0.05, AngularDeflection=0.3)
        mesh.write(str(STL / f'{name}.stl'))
    doc.recompute()
    doc.saveAs(str(OUT / 'usb-power-45w-assembly.FCStd'))
    Part.export([o for o in doc.Objects], str(OUT / 'usb-power-45w-assembly.step'))
    # Solid interference screen between real/proxy parts (envelopes excluded).
    real = ['panel', 'carrier', 'leds', 'headers', 'cans', 'ui_envelopes', 'brackets', 'nuts']
    inter = []
    for i, a in enumerate(real):
        for bname in real[i + 1:]:
            A = Part.makeCompound(cats[a][0])
            B = Part.makeCompound(cats[bname][0])
            if not A.BoundBox.intersect(B.BoundBox):
                continue
            v = A.common(B).Volume
            if v > 1e-3:
                inter.append([a, bname, round(v, 4)])
    report['_solid_interference_mm3'] = inter
    (OUT / 'assembly-report.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report, indent=1))


main()
