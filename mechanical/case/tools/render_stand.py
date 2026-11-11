"""Blender preview of the stand assembly (meshes from build_stand.py in mechanical/case/research/stand/).

  blender -b --python mechanical/case/tools/render_stand.py -- <mechanical/case/research/stand> <out.png> <view>
view: front | side | back | detail (row joints from the front-left) | bottom (the stand without the
      cases, straight up from under the desk: the feet) | feet (left cheek from below and inboard, no cases: tier 1 and 2 front pads)
      | inside (left cheeks from inboard, ortho, no cases or right side) | row1..3 / stop1..3 / load2 / stretcher2 / bar3 / bar3x: case fit cutaways (meshes + camera.json in <src>/fit/<view>/)
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

src, out, view = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.display.shading.show_shadows = True
scene.render.resolution_x, scene.render.resolution_y = 1400, 1100
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("w")
scene.world.color = (0.93, 0.93, 0.93)

COL = {"tier1": (0.75, 0.55, 0.32), "tier2": (0.20, 0.20, 0.22), "tier3": (0.75, 0.55, 0.32),
       "splice": (0.85, 0.25, 0.15), "stretcher": (0.35, 0.35, 0.38), "topbar": (0.85, 0.25, 0.15), "case": (0.30, 0.47, 0.72), "screws": (0.12, 0.12, 0.12),
       "standoffs": (0.85, 0.7, 0.2)}

fit = Path(src) / "fit" / view
if fit.is_dir():
    src = fit
for f in sorted(Path(src).glob("asm-*.stl")):
    bpy.ops.wm.stl_import(filepath=str(f))
    ob = bpy.context.selected_objects[0]
    ob.scale = (0.001, 0.001, 0.001)
    key = next(k for k in COL if f.stem[4:].startswith(k))
    if view in ("bottom", "feet", "inside") and key in ("case", "screws", "standoffs"):   # the stand only
        bpy.data.objects.remove(ob)
        continue
    if view == "inside" and (f.stem.endswith("right") or key == "stretcher"):   # left cheeks only
        bpy.data.objects.remove(ob)
        continue
    m = bpy.data.materials.new(f.stem)
    m.diffuse_color = (*COL[key], 1)
    ob.data.materials.append(m)

cx, cy, cz = 0.105, 0.17, 0.17
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 50
pos = {"front": (-0.55, -0.75, 0.55), "side": (-0.95, 0.17, 0.2), "back": (0.75, 0.95, 0.5),
       "detail": (-0.2, -0.05, 0.45)}.get(view, (-0.55, -0.75, 0.55))
cam.location = Vector(pos) + (Vector((cx, 0, 0)) if view != "side" else Vector((0, 0, 0)))
d = Vector((cx, cy, cz)) - cam.location
if view == "detail":
    cam.location = Vector((0.02, -0.02, 0.42))
    d = Vector((0.06, 0.17, 0.15)) - cam.location
if view == "feet":   # left cheek from below, inboard: tier 2 front pad by the 1-2 joint
    cam.location = Vector((0.03, 0.09, -0.09))
    d = Vector((-0.024, 0.15, 0.0)) - cam.location
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
if view == "side":
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 0.48
    cam.location = (-0.8, 0.17, 0.18)
    cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
if view == "inside":
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 0.46
    cam.location = (0.4, 0.19, 0.17)
    cam.rotation_euler = (math.radians(90), 0, math.radians(90))
if view == "bottom":
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 0.46
    cam.location = (cx + 0.01, 0.19, -0.6)
    cam.rotation_euler = (math.radians(180), 0, math.radians(90))
if fit == src:
    c = json.loads((fit / "camera.json").read_text())
    tgt, d = Vector(c["target_mm"]) * 0.001, Vector(c["look_dir"])
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = c["ortho_mm"] * 0.001
    cam.location = tgt - d * 0.6
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = scene.render.resolution_y = 1100
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
