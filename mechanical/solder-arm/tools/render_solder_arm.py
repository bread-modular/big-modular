"""Headless previews of the soldering arm (no GUI).

blender -b --python mechanical/solder-arm/tools/render_solder_arm.py -- \
  mechanical/solder-arm/research mechanical/solder-arm/renders
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
base_dir = Path(__file__).resolve().parents[1]/'print'/'two-screw-base'
base_report = json.loads((base_dir/'verification.json').read_text())
BODY = (0.25, 0.44, 0.60)
HARDWARE = (0.93, 0.34, 0.09)
JAW = (0.16, 0.18, 0.20)
BOARD = (0.10, 0.45, 0.22)
DESK = (0.80, 0.72, 0.60)


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
    if stem == 'board':
        return BOARD
    if stem.startswith(('bolt', 'knob', 'thumbscrew', 'screw-', 'hand-screw', 'joint', 'jaw-thumbscrew')):
        return HARDWARE
    if stem.startswith('jaw'):
        return JAW
    return BODY


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


def pose(name, pose_name, target, direction, scale, skip=()):
    scene = setup()
    for path in sorted(src.glob(pose_name + '-*.stl')):
        stem = path.stem[len(pose_name) + 1:]
        if stem not in skip:
            load(path, color(stem))
    shoot(scene, name, target, direction, scale)


def exploded(name, parts, target, direction, scale):
    """Assembly view: the 'work' pose with each part moved along the way it goes on (mm)."""
    scene = setup()
    for stem, shift in parts.items():
        load(src/f'work-{stem}.stl', color(stem), shift)
    shoot(scene, name, target, direction, scale)


def plate(name):
    """Every print file once, in its print pose, laid out in rows (not a slicer plate)."""
    scene = setup((1700, 1100))
    rows = [['wide-base', 'hand-screw', 'swivel-bracket'],
            ['arm-link'], ['head-rail'],
            ['jaw-left', 'jaw-right', 'joint-bolt', 'joint-knob', 'jaw-thumbscrew']]
    # the desk base and its screws are the released print files of build_two_screw_base.py
    files = {n: src/f'print-{n}.stl' for n in report['print']}
    bounds = {n: i['print_bounds_mm'] for n, i in report['print'].items()}
    for n, i in base_report['parts'].items():
        files[n], bounds[n] = base_dir/f'{n}.stl', i['print_bounds_mm']
    y, wide = 0.0, 0.0
    for row in rows:
        x, deep = 0.0, 0.0
        for part in row:
            w, d, _ = bounds[part]
            load(files[part], color('desk-base' if part == 'wide-base' else part), (x, y - d, 0))
            x += w + 14
            deep = max(deep, d)
        wide = max(wide, x - 14)
        y -= deep + 14        # rows go towards -Y
    shoot(scene, name, (wide/2, (y + 14)/2 + 25, 10), (0, -0.6, 1), 600)


c = report['poses']['work']['board_centre_mm']
pose('overview', 'work', (120, 0, 70), (0.7, 1, 0.7), 560)
pose('overview-side', 'work', (120, -30, 80), (0.5, -0.87, 0.05), 520)
pose('head', 'work', (c[0], c[1], c[2]), (0.9, 0.5, 0.9), 300, skip=('desk',))
pose('head-flipped', 'flipped', (c[0], c[1], c[2] + 10), (0.9, 0.5, 0.9), 300, skip=('desk',))
pose('low', 'low', (120, 0, 40), (0.7, 1, 0.7), 560)
pose('tilted', 'tilted', (130, 0, 90), (1, 0.3, 0.6), 560)
pose('easel', 'easel', (60, -60, 100), (1, -0.75, 0.6), 560)
pose('desk-base', 'work', (30, 0, -30), (-0.5, -1, 0.25), 360)
plate('print-parts')
# assembly views: A = J2 / J3 bolt axis (bolt head side), R = along the head rail
A = Vector((0.5, 0.866, 0))
R = Vector((0.866, -0.5, 0))
UP = Vector((0, 0, 1))
exploded('assembly-1-base', {
    'desk-base': (0, 0, 0), 'screw-left': -60*UP, 'screw-right': -60*UP,
    'bolt-1': -42*UP, 'turret': 35*UP, 'knob-1': 75*UP,
}, (35, 0, -40), (0.75, 1, 0.45), 480)
exploded('assembly-2-arm', {
    'desk-base': (0, 0, 0), 'bolt-1': (0, 0, 0), 'turret': (0, 0, 0), 'knob-1': (0, 0, 0),
    'bolt-2': 85*A, 'link': -45*A, 'knob-2': -85*A,
}, (80, -50, 75), (1, 0.27, 0.7), 400)
exploded('assembly-3-head', {
    'link': (0, 0, 0), 'knob-3': -45*A, 'head-rail': 45*A, 'bolt-3': 95*A,
    'jaw-left': 45*A - 95*R, 'thumbscrew-left': 45*A - 95*R - 35*UP,
    'jaw-right': 45*A + 65*R, 'thumbscrew-right': 45*A + 65*R - 35*UP,
}, (170, -60, 125), (0.75, 1, 0.75), 440)
