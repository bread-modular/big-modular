"""Headless Blender views of the two-skiff joiner (no desktop/GUI interaction).

  blender -b --python case/tools/render_middle_frame.py -- \
      case/research/middle-frame case/renders/middle-frame

Reads only meshes produced by build_middle_frame.py. Renders the standalone
part from both bay faces and the joined assembly; no geometry is modified.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

src, out = (Path(p) for p in sys.argv[sys.argv.index("--") + 1:])
out.mkdir(parents=True, exist_ok=True)
meta = json.loads((src / "camera.json").read_text())


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.curvature_ridge_factor = 1.3
    shading.curvature_valley_factor = 1.1
    shading.show_shadows = True
    shading.show_object_outline = True
    shading.object_outline_color = (0.12, 0.14, 0.16)
    shading.background_type = "WORLD"
    scene.world = bpy.data.worlds.new("Background")
    scene.world.color = (0.90, 0.92, 0.94)
    scene.render.resolution_x, scene.render.resolution_y = 1500, 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    return scene


def load(path, color):
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0]
    obj.scale = (0.001, 0.001, 0.001)
    material = bpy.data.materials.new(path.stem)
    material.diffuse_color = (*color, 1)
    obj.data.materials.append(material)
    return obj


def render(view, target_mm, direction, ortho_mm, assembly=False):
    scene = setup()
    if assembly:
        for path in sorted(src.glob("asm-*.stl")):
            if "middle_frame" in path.stem:
                color = (0.88, 0.32, 0.10)
            elif "rail" in path.stem:
                color = (0.26, 0.31, 0.38)
            elif "side_panel" in path.stem:
                color = (0.40, 0.49, 0.59)
            else:
                color = (0.60, 0.65, 0.70)
            load(path, color)
    else:
        load(src / "connector.stl", (0.88, 0.32, 0.10))
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    target = Vector(target_mm) * 0.001
    look_from = Vector(direction).normalized()
    camera.location = target + look_from * 1.2
    camera.rotation_euler = (-look_from).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = ortho_mm * 0.001
    camera.data.clip_start = 0.01
    camera.data.clip_end = 10
    scene.render.filepath = str(out / f"{view}.png")
    bpy.ops.render.render(write_still=True)


cx, cy = meta["frame_width"] / 2, meta["centre_y"]
render("frame-left", (cx, cy, 36), (-1, -0.65, 0.65), 168)
render("frame-right", (cx, cy, 36), (1, -0.65, 0.65), 168)
render("frame-underside", (cx, cy, 34), (-1, -0.55, -0.70), 168)
render("two-cases", (234, cy, 28), (-0.4, -1, 0.85), 560, True)
render("joint-detail", (meta["left_inner"] + cx, 21, 38), (-1, -1.1, 0.85), 156, True)
