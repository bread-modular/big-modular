"""Headless Blender previews of the angled case joiner; no GUI interaction.

blender -b --python mechanical/case/tools/render_angle_joiner.py -- \
  mechanical/case/research/angle-joiner mechanical/case/renders/angle-joiner

Assembly previews use actual exported solids plus plain display sheets to indicate
module faces. Those sheets are not module/electronics models or printable parts.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

src, out = (Path(p) for p in sys.argv[sys.argv.index('--')+1:])
out.mkdir(parents=True, exist_ok=True)
ORANGE = (0.88, 0.30, 0.09)
BLUE = (0.31, 0.42, 0.54)
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


def load(path, color, offset=(0,0,0)):
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0]
    obj.scale = (0.001,0.001,0.001)
    obj.location = Vector(offset)*0.001
    mat = bpy.data.materials.new(path.stem)
    mat.diffuse_color = (*color,1)
    obj.data.materials.append(mat)
    return obj


def view(scene, name, target_mm, direction, scale_mm):
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    target = Vector(target_mm)*0.001
    look = Vector(direction).normalized()
    camera.location = target+look*1.2
    camera.rotation_euler = (-look).to_track_quat('-Z','Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale_mm*0.001
    camera.data.clip_start, camera.data.clip_end = 0.01,10
    scene.render.filepath = str(out/f'{name}.png')
    bpy.ops.render.render(write_still=True)


def assembly(name, target, direction, scale, sheets=True, pad_guides=False):
    scene = setup()
    for p in sorted(src.glob('asm-*.stl')):
        n = p.stem
        if 'joiner' in n:
            color = ORANGE
        elif 'screw' in n:
            color = (0.12,0.14,0.17)
        elif 'spacer' in n:
            color = (0.75,0.61,0.30)
        elif 'side_panel' in n:
            color = BLUE
        elif 'rail' in n:
            color = DARK
        else:
            color = GREY
        load(p,color)
    if sheets:
        for p in sorted(src.glob('display-*.stl')):
            load(p, (0.71,0.74,0.77))
    if pad_guides:
        for p in sorted(src.glob('pad-area-*.stl')):
            load(p, (0.08,0.13,0.15))
    view(scene,name,target,direction,scale)


assembly('assembly', (109,142,90), (-1,-1.3,0.8), 490)
assembly('side', (109,142,88), (-1,0,0.04), 335)
assembly('open-assembly', (109,142,90), (-1,-1.3,0.8), 490, False)
scene = setup()
load(src/'part-joiner-left.stl', ORANGE)
view(scene,'plate-outside',(-16,146,80),(-1,-0.3,0.35),325)
scene = setup()
load(src/'part-joiner-left.stl', ORANGE)
view(scene,'plate-inside',(-16,146,80),(1,-0.3,0.35),325)
scene = setup()
load(src/'part-side-panel-left.stl', BLUE)
view(scene,'panel-inside',(-4,64,35),(1,-0.65,0.55),170)

# Dark squares mark the adhesive area only, not a specified pad thickness.
assembly('rubber-pad-locations', (109,142,10), (0,-0.15,-1), 430, False, True)
pads = json.loads((src/'rubber-pad-locations.json').read_text())
cx, cy, cz = pads['positions']['rear_left']['centre_xyz_mm']
scene = setup()
load(src/'part-joiner-left.stl', ORANGE)
load(src/'pad-area-rear_left.stl', (0.08,0.13,0.15))
view(scene,'rubber-pad-detail',(cx,cy,cz+3),(1,0.6,-0.75),60)
