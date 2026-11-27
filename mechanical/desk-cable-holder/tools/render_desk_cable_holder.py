"""Render fresh meshes from the assembled fit (Blender in background mode)."""
from pathlib import Path
import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
out = root/'renders'
out.mkdir(exist_ok=True)
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


scene = setup((1152, 680))
for part, rgb in [('Carrier',(.12,.48,.53)), ('LeftClip',(.16,.22,.28)), ('RightClip',(.16,.22,.28)),
                  ('LeftScrew',(.88,.43,.10)), ('RightScrew',(.88,.43,.10))]:
    load(root/'research'/(part+'.stl'), rgb)
shoot(scene, 'assembly', (25,0,-61), (-1,-.38,.43), 335)
