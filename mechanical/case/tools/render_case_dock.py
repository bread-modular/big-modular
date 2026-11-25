"""Headless Workbench previews of the case dock (input meshes from build_case_dock)."""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

src, out = (Path(p) for p in sys.argv[sys.argv.index('--') + 1:])
out.mkdir(parents=True, exist_ok=True)


def render(name, center, direction, width):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_object_outline = True
    sh.object_outline_color = (0.18, 0.20, 0.22)
    sh.background_type = 'WORLD'
    scene.world = bpy.data.worlds.new('Background')
    scene.world.color = (0.89, 0.91, 0.93)
    scene.view_settings.view_transform = 'Standard'
    assert list((src / name).glob('*.stl')), name
    for path in sorted((src / name).glob('*.stl')):
        bpy.ops.wm.stl_import(filepath=str(path))
        obj = bpy.context.selected_objects[0]
        obj.scale = (0.001,) * 3
        if path.stem == 'Dock_receiver':
            color = (0.88, 0.30, 0.09)
        elif path.stem == 'Dock_slider':
            color = (0.07, 0.45, 0.68)
        elif 'rail' in path.stem:
            color = (0.32, 0.36, 0.43)
        else:
            color = (0.62, 0.67, 0.73)
        mat = bpy.data.materials.new(path.stem)
        mat.diffuse_color = (*color, 1)
        obj.data.materials.append(mat)
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera = camera
    ray = Vector(direction).normalized()
    camera.location = Vector(center) * 0.001 + ray * 1.2
    camera.rotation_euler = (-ray).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = width * 0.001
    camera.data.clip_start, camera.data.clip_end = 0.01, 10
    scene.render.resolution_x, scene.render.resolution_y = 1200, 850
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(out / (name + '.png'))
    bpy.ops.render.render(write_still=True)


render('seated', (109, 135, 29), (0.90, -0.70, 0.95), 415)
render('loading', (109, 135, 43), (1, -0.20, 0.48), 390)
render('detail', (109, 55, 2), (0.18, -0.42, 1), 258)
