"""Plain M3 L bracket shared by panels/bracket/build_bracket.py and tools/build_assembly.py (FreeCAD).

Identical to modules/usb-power (assembly-geometry.json `brackets`, hardware/mechanics/
corner_braces.scad); the dimensions are read from docs/mechanical-geometry.json, whose
`brackets` block mechanics45.py copies verbatim from the old contract and asserts equal.
Local frame: origin = assembly X0.1, Y = centre-5, Z1.6 (panel rear face); foot X0..9.2,
Z0..3; web X0..2.4 up to Z18.4. Panel M3 hole along Z at X6.3; carrier M3 hole along X at
Z13.4 with a 90-degree countersink on the outer X0 face. Nominal geometry only.
"""
import json
import math
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


def contract():
    b = json.loads((MODULE / 'docs/mechanical-geometry.json').read_text())['brackets']
    x0, x1 = b['outer_X_mm']
    z0, z1 = b['outer_Z_mm']
    web, foot = b['side_web_X_mm'], b['front_foot_Z_mm']
    assert math.isclose(web[1] - web[0], b['web_mm']) and math.isclose(foot[1] - foot[0], b['wall_mm'])
    return {'width_x': round(x1 - x0, 3), 'width_y': b['width_Y_mm'], 'depth_z': round(z1 - z0, 3),
            'foot': b['wall_mm'], 'web': b['web_mm'], 'hole': b['hole_mm'],
            'front_x': round(b['front_hole_X_mm'] - x0, 3), 'side_z': round(b['side_hole_Z_mm'] - z0, 3),
            'sink_d': b['side_countersink_diameter_mm'],
            'sink_depth': round((b['side_countersink_diameter_mm'] - b['hole_mm']) / 2, 3),
            'origin_XZ': [x0, z0], 'Y_centres': b['Y_centres_mm'], 'quantity': b['quantity']}


def bracket_shape(Part, App, c=None):
    c = c or contract()
    body = Part.makeBox(c['width_x'], c['width_y'], c['foot']).fuse(Part.makeBox(c['web'], c['width_y'], c['depth_z']))
    front = Part.makeCylinder(c['hole'] / 2, c['foot'] + 0.2, App.Vector(c['front_x'], c['width_y'] / 2, -0.1))
    side = Part.makeCylinder(c['hole'] / 2, c['web'] + 0.2, App.Vector(-0.1, c['width_y'] / 2, c['side_z']),
                             App.Vector(1, 0, 0))
    sink = Part.makeCone(c['sink_d'] / 2, c['hole'] / 2, c['sink_depth'], App.Vector(0, c['width_y'] / 2, c['side_z']),
                         App.Vector(1, 0, 0))
    shape = body.cut(front.fuse(side).fuse(sink)).removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    assert c['web'] - c['sink_depth'] >= 1.5, 'insufficient material behind countersink'
    return shape
