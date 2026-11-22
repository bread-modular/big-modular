"""Headless previews of the USB riser (no GUI).

blender -b --python mechanical/case/tools/render_usb_riser.py -- \
  mechanical/case/research/usb-riser/final mechanical/case/renders/accessories/usb-riser
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
src, out = Path(args[0]), Path(args[1])
out.mkdir(parents=True, exist_ok=True)
meta = json.loads((src / 'camera.json').read_text())

BRASS = (0.80, 0.62, 0.22)
COLORS = [
    ('riser-screws', (0.10, 0.11, 0.12)), ('riser-spacers', BRASS), ('riser', (0.93, 0.34, 0.09)),
    ('print-riser', (0.93, 0.34, 0.09)),
    ('m32-panel', (0.13, 0.15, 0.18)), ('m32-pcb', (0.10, 0.36, 0.20)),
    ('m32-jacks', (0.30, 0.32, 0.35)), ('m32-nuts', (0.80, 0.81, 0.83)),
    ('m32-knobs', (0.95, 0.95, 0.93)), ('m32-back', (0.72, 0.73, 0.76)),
    ('m32-screws', (0.10, 0.11, 0.12)),
    ('usb-plug', (0.08, 0.09, 0.10)), ('usb-cable', (0.15, 0.40, 0.75)),
    ('nb-panels', (0.72, 0.75, 0.78)), ('nb-knobs', (0.55, 0.58, 0.62)), ('nb-nuts', (0.62, 0.65, 0.68)),
    ('case-rail', (0.28, 0.32, 0.38)), ('case-side_panel', (0.42, 0.50, 0.59)),
    ('case-cover', (0.50, 0.55, 0.60)), ('case-', (0.36, 0.41, 0.47)),
]
# exploded view: lift per part, mm
LIFT = [('riser-screws', 52.0), ('riser-spacers', 50.0), ('riser', 20.0), ('m32-screws', 112.0), ('m32', 85.0)]


def setup(res, shadows=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.curvature_ridge_factor = 1.3
    sh.curvature_valley_factor = 1.1
    sh.show_shadows = shadows
    sh.show_object_outline = True
    sh.object_outline_color = (0.12, 0.14, 0.16)
    sh.background_type = 'WORLD'
    scene.world = bpy.data.worlds.new('Background')
    scene.world.color = (0.90, 0.92, 0.94)
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    return scene


def mat(obj, color):
    m = bpy.data.materials.new(obj.name)
    m.diffuse_color = (*color, 1)
    obj.data.materials.append(m)


def load(path, name, lift=0.0):
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0]
    obj.scale = (0.001, 0.001, 0.001)
    obj.location.z = lift * 0.001
    mat(obj, next(c for key, c in COLORS if name.startswith(key)))


def axis(x, y, za, zb):
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.0002, depth=(zb - za) * 0.001,
                                        location=(x * 0.001, y * 0.001, (za + zb) / 2 * 0.001))
    mat(bpy.context.object, (0.85, 0.10, 0.10))


def render(name, target, direction, scale, section=None, only=None, skip=(), res=(1500, 1100), exploded=False):
    scene = setup(res, shadows=not exploded)
    for path in sorted(src.glob('*.stl')):
        stem = path.stem
        tag = stem[:4] if stem[:5] in ('secu-', 'secf-') else None
        if tag != section:
            continue
        part = stem[5:] if tag else stem
        if (part == 'print-riser') != (only == ('print-riser',)):
            continue
        if only and not any(part.startswith(k) for k in only):
            continue
        if any(part.startswith(k) for k in skip):
            continue
        load(path, part, next((dz for key, dz in LIFT if part.startswith(key)), 0.0) if exploded else 0.0)
    if exploded:
        z0, zr, z1 = meta['z0'], meta['zr'], meta['z1']
        for x, y in meta['module_screws']:
            axis(x, y, zr - 10 + 20, z1 + 112)           # riser socket -> spacer -> module screw
        for x, y in meta['riser_screws']:
            axis(x, y, z0 - 6, z0 + 4 + 52)              # rail spacer -> riser screw
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    target = Vector(target) * 0.001
    direction = Vector(direction).normalized()
    camera.location = target + direction * 1.5
    camera.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale * 0.001
    camera.data.clip_start = 0.01
    camera.data.clip_end = 10
    scene.render.filepath = str(out / (name + '.png'))
    bpy.ops.render.render(write_still=True)


cx, cy, z0, z1 = meta['cx'], meta['cy'], meta['z0'], meta['z1']
ux, uz = meta['ux'], meta['uz']
ccx, back = meta['case_cx'], meta['back_y']
w, h, t = meta['size']
# whole case from the player's side, and from behind where the cable leaves
render('in-case-front', (ccx, cy, 45), (-0.45, -1.0, 0.85), 330)
render('in-case-rear', (ccx, cy + 15, 45), (0.5, 1.0, 0.7), 340)
# close on the riser from behind: the slot, the plug over the back rail
render('usb-slot', (cx, back - 5, z0 + 6), (0.55, 1.0, 0.55), 120)
# section along the USB centre line, seen from the right
render('section-usb', (ux, back - 18, z0 + 6), (1, 0, 0.12), 78, section='secu', res=(1500, 900))
# section along the front rail's hole line, seen from the front: riser screws, module spacer, module screw
render('section-front-rail', (cx, 3, z0 + 5), (0, -1, 0.10), 78, section='secf', res=(1500, 900),
       skip=('case-cover', 'm32-jacks', 'm32-knobs', 'm32-nuts', 'm32-pcb', 'm32-back'))
# riser on the rails without the module: screws in their counterbores, spacers in their sockets
render('on-rails', (cx, cy, z0), (0.6, 0.9, 0.9), 200, skip=('m32', 'usb'))
render('exploded-rear', (cx, cy, z0 + 62), (0.75, 0.8, 0.5), 235, res=(1300, 1500), exploded=True,
       skip=('nb-knobs', 'nb-nuts', 'usb'))
render('exploded-front', (cx, cy, z0 + 62), (0.75, -0.8, 0.5), 235, res=(1300, 1500), exploded=True,
       skip=('nb-knobs', 'nb-nuts', 'usb'))
# the print file, as exported: rail face on the bed
PRINT = ('print-riser',)
render('print-top', (w / 2, h / 2, t / 2), (0.55, 0.8, 0.9), 175, only=PRINT)
render('print-underside', (w / 2, h / 2, t / 2), (0.55, 0.8, -0.9), 175, only=PRINT)
render('print-usb-end', (w / 2, h, t / 2), (0.25, 1.0, 0.35), 62, only=PRINT, res=(1500, 900))
