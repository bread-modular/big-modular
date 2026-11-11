"""Headless previews of the one-piece four-rail middle brace (no GUI).

blender -b --python mechanical/case/tools/render_middle_brace.py -- \
  mechanical/case/research/middle-brace mechanical/case/renders/middle-brace
"""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

src,out=(Path(p) for p in sys.argv[sys.argv.index('--')+1:])
out.mkdir(parents=True,exist_ok=True)
meta=json.loads((src/'camera.json').read_text())
ORANGE=(0.93,0.34,0.09)
BLUE=(0.25,0.44,0.60)


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    sh=scene.display.shading
    sh.light='STUDIO'
    sh.color_type='MATERIAL'
    sh.show_cavity=True
    sh.cavity_type='BOTH'
    sh.curvature_ridge_factor=1.3
    sh.curvature_valley_factor=1.1
    sh.show_shadows=True
    sh.show_object_outline=True
    sh.object_outline_color=(0.12,0.14,0.16)
    sh.background_type='WORLD'
    scene.world=bpy.data.worlds.new('Background')
    scene.world.color=(0.9,0.92,0.94)
    scene.render.resolution_x,scene.render.resolution_y=1500,1100
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='Standard'
    return scene


def load(path,color):
    bpy.ops.wm.stl_import(filepath=str(path))
    obj=bpy.context.selected_objects[0]
    obj.scale=(0.001,0.001,0.001)
    mat=bpy.data.materials.new(path.stem)
    mat.diffuse_color=(*color,1)
    obj.data.materials.append(mat)
    return obj


def render(name,target,direction,scale,assembly=False,sheets=False,only=None):
    scene=setup()
    if assembly:
        for path in sorted(src.glob('asm-*.stl')):
            stem=path.stem
            if only and not any(key in stem for key in only):
                continue
            if 'top_brace' in stem:
                color=ORANGE
            elif 'middle_frame' in stem:
                color=BLUE
            elif 'screw_' in stem or 'spacer_' in stem:
                color=(0.16,0.18,0.20)
            elif 'rail' in stem:
                color=(0.28,0.32,0.38)
            elif 'side_panel' in stem:
                color=(0.42,0.5,0.59)
            else:
                color=(0.62,0.67,0.71)
            load(path,color)
        if sheets:
            for path in src.glob('display-*.stl'):
                load(path,(0.74,0.77,0.80))
    else:
        load(src/'brace.stl',ORANGE)
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    scene.camera=camera
    target=Vector(target)*0.001
    direction=Vector(direction).normalized()
    camera.location=target+direction*1.2
    camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'
    camera.data.ortho_scale=scale*0.001
    camera.data.clip_start=0.01
    camera.data.clip_end=10
    scene.render.filepath=str(out/(name+'.png'))
    bpy.ops.render.render(write_still=True)


cx,cy,cz=meta['cx'],meta['cy'],meta['cz']
render('brace',(cx,cy,cz),(-0.55,-0.7,1.0),205)
render('underside',(cx,cy,cz),(0.6,-0.7,-1.0),205)
# The brace lies on the installed modules: the grey sheets stand in for them.
render('installed-detail',(cx,cy,47),(-0.6,-0.85,0.95),245,True,True)
render('two-cases',(234,cy,35),(-0.4,-1,0.9),560,True,True)
render('top',(cx,cy,cz),(0,0,1),205)
# Top-down installed view: each tab is exactly as wide as the rail under it.
render('installed-top',(cx,cy,cz),(0,0,1),225,True)
# Low view: one flat underside, panel-thick tabs and spine, raised crossbars.
render('thin-profile',(cx,cy,cz),(0,-1,0.24),165)
# Close view of one filleted shoulder and its walled first-screw pocket.
render('shoulder-detail',(meta['left_x']+18,meta['front_y'],cz),(-0.75,-0.9,0.8),62)
render('shoulder-installed',(cx,meta['front_y'],cz),(-0.5,-1,0.75),130,True,True)
# From below: the filleted collar pocket between the shoulders, the stepped
# roof behind it and the 45 degree web down to the flat spine.
render('pocket-underside',(meta['frame_x'],meta['front_y']+6,cz),(0.35,-0.75,-1.0),78)
# Brace on the frame alone: flat on its top and lip, pockets over the collars.
PAIR=('top_brace','middle_frame')
render('on-frame',(cx,cy,52),(-0.85,-0.75,0.55),190,True,only=PAIR)
render('pocket-on-collar',(meta['frame_x'],meta['front_y']-3,66),(-0.12,-1,0.16),60,True,only=PAIR)
render('web-profile',(cx,meta['front_y']+12,62),(-1,-0.12,0.16),52,True,only=PAIR)
