"""Headless Blender previews of the flat 2 x 2 case set with fused panels; no GUI interaction.

blender -b --python mechanical/case/tools/render_quad_case.py -- \
  mechanical/case/research/quad-case mechanical/case/renders/quad-case

Assembly previews use the exported solids plus plain display sheets that mark the module
faces. Those sheets are not module models or printable parts.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

src, out = (Path(p) for p in sys.argv[sys.argv.index('--')+1:])
out.mkdir(parents=True, exist_ok=True)
meta = json.loads((src/'camera.json').read_text())
ORANGE = (0.88, 0.30, 0.09)
AMBER = (0.93, 0.62, 0.12)
BLUE = (0.16, 0.39, 0.64)
DARK = (0.20, 0.24, 0.29)
GREY = (0.58, 0.63, 0.68)


def setup():
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
    scene.world.color = (0.90, 0.92, 0.94)
    scene.render.resolution_x, scene.render.resolution_y = 1500, 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    return scene


def load(path, color):
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0]
    obj.scale = (0.001, 0.001, 0.001)
    mat = bpy.data.materials.new(path.stem)
    mat.diffuse_color = (*color, 1)
    obj.data.materials.append(mat)
    return obj


def view(scene, name, target_mm, direction, scale_mm):
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    target = Vector(target_mm)*0.001
    look = Vector(direction).normalized()
    camera.location = target+look*1.5
    camera.rotation_euler = (-look).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale_mm*0.001
    camera.data.clip_start, camera.data.clip_end = 0.01, 10
    scene.render.filepath = str(out/f'{name}.png')
    bpy.ops.render.render(write_still=True)


def colour(n):
    if 'fused' in n:
        return ORANGE
    if 'joiner' in n:
        return AMBER
    if 'screw' in n:
        return (0.12, 0.14, 0.17)
    if 'spacer' in n:
        return (0.75, 0.61, 0.30)
    if 'side_panel' in n or 'middle_frame' in n:
        return BLUE
    return DARK if 'rail' in n else GREY


def assembly(name, target, direction, scale, sheets=True, prefix='asm-', only=None):
    """The flat set (asm-) or the set on the angle joiner (stand-)."""
    scene = setup()
    for p in sorted(src.glob(prefix+'*.stl')):
        n = p.stem[len(prefix):]
        if n.startswith('display'):
            continue
        if only and not any(k in n for k in only):
            continue
        load(p, colour(n))
    if sheets:
        shown = 'display-*.stl' if prefix == 'asm-' else 'stand-display-*.stl'
        for p in sorted(src.glob(shown)):
            load(p, (0.71, 0.74, 0.77))
    view(scene, name, target, direction, scale)


def part(name, part_name, target, direction, scale, color=ORANGE):
    scene = setup()
    load(src/f'part-{part_name}.stl', color)
    view(scene, name, target, direction, scale)


cx, cy, cz = meta['centre']
mid, joint = meta['middle_x'], meta['joint_y']
sx, sy, sz = meta['stand_centre']
assembly('assembly', (cx, cy, cz), (-1, -1.3, 0.9), 640)
assembly('open-assembly', (cx, cy, cz), (-1, -1.3, 0.9), 640, sheets=False)
assembly('top', (cx, cy, cz), (0, -0.02, 1), 560)
assembly('underside', (cx, cy, cz), (-0.6, -1, -1.1), 640, sheets=False)
assembly('middle-joint', (mid, joint, 50), (-1, -0.9, 0.7), 190, sheets=False,
         only=('fused_middle', 'right_rail', 'right_bottom'))
part('side-left-inside', 'fused-side-left', (-4, cy, cz), (1, -0.5, 0.45), 330)
part('side-left-outside', 'fused-side-left', (-4, cy, cz), (-1, -0.5, 0.45), 330)
part('side-right-inside', 'fused-side-right', (meta['right_x'], cy, cz), (-1, -0.5, 0.45), 330)
part('side-joint-detail', 'fused-side-left', (-4, joint, 45), (1, -0.25, 0.4), 110)
part('middle-left-face', 'fused-middle', (mid, cy, cz), (-1, -0.5, 0.45), 330)
part('middle-right-face', 'fused-middle', (mid, cy, cz), (1, -0.5, 0.45), 330)
part('middle-underside', 'fused-middle', (mid, cy, cz), (-0.5, -0.4, -1), 330)
assembly('on-stand', (sx, sy, sz), (-1, -1.3, 0.8), 760, prefix='stand-')
assembly('on-stand-open', (sx, sy, sz), (-1, -1.3, 0.8), 760, sheets=False, prefix='stand-')
assembly('on-stand-side', (sx, sy, sz), (-1, 0, 0.04), 470, prefix='stand-')
assembly('on-stand-rear', (sx, sy, sz), (0.9, 1.4, 0.6), 760, sheets=False, prefix='stand-')
