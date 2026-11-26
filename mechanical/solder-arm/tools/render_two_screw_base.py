"""blender -b --python mechanical/solder-arm/tools/render_two_screw_base.py
Render the build's assembled CAD meshes, not the print-oriented files.
VARIANT=narrow-56 renders the 56 mm wide base (tools/narrow_base.py) into its own folder.
"""
import os
from pathlib import Path

import bpy
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

ARM = Path(__file__).resolve().parents[1]
VARIANT = os.environ.get('VARIANT', '')
SRC = ARM/'research'/'two-screw-base'/VARIANT/'render'
OUT = ARM/'print'/'two-screw-base'/VARIANT
WIDTH, SPACING = {'': ('112', '80'), 'narrow-56': ('56', '32')}[VARIANT]
BLUE, AMBER = (.055, .32, .40), (.94, .33, .045)
GRAY, DARK, BOARD, DESK = (.44, .49, .50), (.16, .19, .20), (.10, .43, .27), (.68, .52, .35)


def add_material(obj, colour):
    m = bpy.data.materials.new(obj.name)
    m.diffuse_color = (*colour, 1)
    obj.data.materials.append(m)


def render(label, detail, direction):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.curvature_ridge_factor = 1.0
    sh.curvature_valley_factor = 1.1
    sh.show_shadows = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x, scene.render.resolution_y = 704, 450
    scene.render.resolution_percentage = 100
    objects = []
    for path in sorted(SRC.glob('*.stl')):
        n = path.stem
        new = n in ('wide_base', 'left_screw', 'right_screw')
        if detail and not new:
            continue
        bpy.ops.wm.stl_import(filepath=str(path))
        obj = bpy.context.selected_objects[0]
        obj.scale = (.001,)*3
        color = (BLUE if n == 'wide_base' else AMBER if new else BOARD if n == 'board'
                 else DARK if n.startswith(('bolt', 'knob', 'jaw', 'thumbscrew')) else GRAY)
        add_material(obj, color)
        objects.append(obj)
    if not detail:
        # Local piece of a 25 mm desktop; limit its extent to expose the mount.
        bpy.ops.mesh.primitive_cube_add(size=1, location=(.095, 0, -.0125))
        table = bpy.context.object
        table.dimensions = (.190, .169, .025)
        add_material(table, DESK)
        objects.append(table)
    bpy.context.view_layer.update()
    look = Vector(direction).normalized()
    rot = (-look).to_track_quat('-Z', 'Y')
    right, up = [rot @ Vector(v) for v in [(1, 0, 0), (0, 1, 0)]]
    coords = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    ranges = [(min(v.dot(axis) for v in coords), max(v.dot(axis) for v in coords)) for axis in (right, up, look)]
    target = sum((axis*((lo+hi)/2) for axis, (lo, hi) in zip((right, up, look), ranges)), Vector((0, 0, 0)))
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = target + look
    camera.rotation_euler = rot.to_euler()
    camera.data.type = 'ORTHO'
    w, h = [hi-lo for lo, hi in ranges[:2]]
    camera.data.ortho_scale = max(w, h*704/450)*1.05
    scene.camera = camera
    scene.render.filepath = str(SRC/(label+'.png'))
    bpy.ops.render.render(write_still=True)
    return Image.open(scene.render.filepath).convert('RGBA')


left = render('detail', True, (1.3, -.8, .55))
right = render('mounted', False, (.24, 1.1, .83))
canvas = Image.new('RGBA', (1480, 695), '#f8f8f4')
draw = ImageDraw.Draw(canvas)
fonts = Path('/usr/share/fonts/truetype/dejavu')

def text(x, y, words, size, bold=False, color='#23383a'):
    font = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    draw.text((x, y), words, fill=color, font=ImageFont.truetype(str(fonts/font), size))

text(34, 20, 'SOLDER ARM    /    TWO-SCREW DESK MOUNT', 24, True)
draw.line((34, 66, 1446, 66), fill='#b5c4c2', width=2)
text(34, 86, 'Replacement base', 30, True)
text(759, 86, 'Original arm on the new base', 30, True)
text(34, 128, 'Two printed screws press directly on the desk underside.', 21)
text(759, 128, 'The swivel, link, joints and PCB jaws all stay.', 21)
canvas.alpha_composite(left, (14, 163))
canvas.alpha_composite(right, (751, 163))
draw.line((740, 88, 740, 601), fill='#d0d9d6', width=2)
draw.rounded_rectangle((34, 618, 1446, 677), 10, fill='#e4ede9')
text(55, 632, f'{WIDTH} mm wide', 23, True)
text(502, 632, f'{SPACING} mm between screws', 23, True)
text(1040, 632, 'Flat desk: 5–52 mm', 23, True)
canvas.convert('RGB').save(OUT/'fit.png', optimize=True)
