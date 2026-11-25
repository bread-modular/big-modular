"""Headless previews of the desk cable holder (no GUI).

blender -b --python mechanical/desk-cable-holder/tools/render_desk_cable_holder.py -- \
  mechanical/desk-cable-holder/research mechanical/desk-cable-holder/renders
"""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

research, out = (Path(p) for p in sys.argv[sys.argv.index('--') + 1:])
src = research/'render'
out.mkdir(parents=True, exist_ok=True)
report = json.loads((research/'build-report.json').read_text())
BODY = (0.25, 0.44, 0.60)
CLAMP_BODY = (0.16, 0.24, 0.34)
HARDWARE = (0.93, 0.34, 0.09)
DESK = (0.80, 0.72, 0.60)
CABLE = {100: (0.85, 0.15, 0.15), 150: (0.95, 0.55, 0.10), 200: (0.95, 0.80, 0.15), 300: (0.20, 0.62, 0.30),
         450: (0.15, 0.40, 0.80), 600: (0.20, 0.20, 0.22)}


def setup(size=(1500, 1100)):
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
    sh.show_shadows = True
    sh.show_object_outline = True
    sh.object_outline_color = (0.12, 0.14, 0.16)
    sh.background_type = 'WORLD'
    scene.world = bpy.data.worlds.new('Background')
    scene.world.color = (0.9, 0.92, 0.94)
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 100
    scene.view_settings.view_transform = 'Standard'
    return scene


def color(stem):
    if stem == 'desk':
        return DESK
    if stem.startswith('cable-'):
        return CABLE[int(stem.split('-')[1])]
    if stem in ('clamp-screw', 'clamp-nut', 'clamp-pad'):
        return HARDWARE
    return CLAMP_BODY if stem == 'clamp-body' else BODY


def load(path, rgb, at=(0, 0, 0)):
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0]
    obj.scale = (0.001, 0.001, 0.001)
    obj.location = Vector(at)*0.001
    mat = bpy.data.materials.new(path.stem)
    mat.diffuse_color = (*rgb, 1)
    obj.data.materials.append(mat)
    return obj


def shoot(scene, name, target, direction, scale):
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    direction = Vector(direction).normalized()
    camera.location = Vector(target)*0.001 + direction*1.5
    camera.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale*0.001
    camera.data.clip_start = 0.01
    camera.data.clip_end = 10
    scene.render.filepath = str(out/(name + '.png'))
    bpy.ops.render.render(write_still=True)


def use(name, target, direction, scale, size=(1500, 1100), cables=True, desk=True, shifts=None):
    """The holder under the desk; shifts = part -> offset in mm for an exploded view."""
    scene = setup(size)
    for path in sorted(src.glob('use-*.stl')):
        stem = path.stem[4:]
        if (stem.startswith('cable-') and not cables) or (stem == 'desk' and not desk):
            continue
        load(path, color(stem), (shifts or {}).get(stem, (0, 0, 0)))
    shoot(scene, name, target, direction, scale)


def plate(name):
    """Every print file once, in its print pose (not a slicer plate)."""
    scene = setup((1500, 1000))
    rows = [['hanger'], ['clamp-body', 'clamp-screw', 'clamp-nut', 'clamp-pad']]
    y = 0.0
    for row in rows:
        x, deep = 0.0, 0.0
        for part in row:
            w, d, _ = report['print'][part]['print_bounds_mm']
            load(src/f'print-{part}.stl', color(part), (x, y - d, 0))
            x += w + 14
            deep = max(deep, d)
        y -= deep + 14        # rows go towards -Y
    shoot(scene, name, (120, -105, 20), (-0.25, -0.75, 1), 400)


# the viewer stands at -X, in front of the desk edge
use('overview', (20, 0, -230), (-1, -0.75, 0.3), 800, size=(1300, 1500))
use('from-above', (60, 0, 0), (-0.3, -0.2, 1), 520, size=(1500, 1000))
use('hanger', (25, -15, -75), (-1, -0.55, -0.12), 330)
use('side', (25, 0, -70), (0, -1, 0), 230, size=(1300, 1300))
use('assembly', (15, 20, -70), (-0.75, -1, -0.25), 430, size=(1400, 1300), cables=False, shifts={
    'hanger': (0, 0, -45), 'clamp-body': (-80, 0, 0), 'clamp-nut': (-80, 65, 0), 'clamp-pad': (-80, 0, -8),
    'clamp-screw': (-80, 0, -75), 'desk': (0, 0, 0)})
plate('print-parts')
