"""Headless previews of the cable-holder cover and its clip-on holder (no GUI).

blender -b --python mechanical/case/tools/render_cable_holder.py -- \
  mechanical/case/research/cable-holder mechanical/case/print/cable-holder \
  mechanical/case/renders/cable-holder
"""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

src,prints,out=(Path(p) for p in sys.argv[sys.argv.index('--')+1:])
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


def color(stem):
    if 'holder' in stem:
        return ORANGE
    if stem.endswith('panel'):
        return BLUE
    if 'screw' in stem or 'spacer' in stem or 'standoffs' in stem:
        return (0.16,0.18,0.20)
    if 'rail' in stem:
        return (0.28,0.32,0.38)
    if 'side_panel' in stem or 'joiner' in stem or 'tier' in stem or 'splice' in stem or 'stretcher' in stem:
        return (0.42,0.5,0.59)
    return (0.62,0.67,0.71)


def render(name,target,direction,scale,prefix=None,skip=(),part=None):
    scene=setup()
    if part:
        load(prints/(part+'.stl'),BLUE if part.endswith('panel') else ORANGE)
    else:
        for path in sorted(src.glob(prefix+'-*.stl')):
            stem=path.stem[len(prefix)+1:]
            if any(key in stem for key in skip):
                continue
            load(path,color(stem))
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


seat,stand=meta['seat'],meta['stand_seat']
w,h=meta['panel']
# Two cases on the 60 degree angle joiners, seen from behind: the upper case's back cover faces up.
render('on-joiner',(seat[0],150,95),(0.55,1,0.6),470,'joiner',skip=('holder_centre',))
render('on-joiner-side',(seat[0],150,95),(1,0.12,0.1),400,'joiner',skip=('holder_centre',))
render('holder-detail',(meta['left_x']+20,seat[1]+10,seat[2]),(0.45,1,0.75),210,'joiner',skip=('holder_centre',))
# One holder in the two middle slots, and the cover alone: flat, nothing past the frame.
render('one-holder',(seat[0],seat[1],seat[2]),(0.3,1,0.9),330,'joiner',skip=('holder_left','holder_right'))
render('panel-only',(seat[0],seat[1],seat[2]),(0.3,1,0.9),330,'joiner',skip=('holder',))
# Cut through the first tongue: tongue top on the slot's inner edge, barb behind the cover.
render('section',(meta['tongue_x'],seat[1]+8,seat[2]+2),(-1,0,0),105,'section')
# Tiered stand, row 2 at 40 degrees.
render('on-stand',(seat[0],150,80),(0.55,1,0.6),470,'stand',skip=('holder_centre',))
render('on-stand-side',(seat[0],150,80),(1,0.12,0.1),400,'stand',skip=('holder_centre',))
# Print poses, as exported.
render('print-panel',(w/2,h/2,2),(-0.35,-0.8,1),250,part='cable-holder-panel')
render('print-holder-joiner-60',(50,30,5),(-0.5,-0.8,0.9),140,part='cable-holder-joiner-60')
render('print-holder-stand-40',(50,30,7),(-0.5,-0.8,0.9),140,part='cable-holder-stand-40')
render('holder-end-joiner-60',(50,30,5),(-1,0,0),90,part='cable-holder-joiner-60')
render('holder-end-stand-40',(50,30,7),(-1,0,0),90,part='cable-holder-stand-40')
