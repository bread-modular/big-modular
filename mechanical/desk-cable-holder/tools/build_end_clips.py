"""Two-screw mount and matching one-piece cable carrier. FreeCADCmd this file.
Desk top Z=0, front edge X=0, +X into desk; the two clips slide onto opposite ends along Y.
Both bores take the SAME right-hand screw.
"""
import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import build_desk_cable_holder as h
import build_plates as plates
from build_desk_cable_holder import V, box, cyl, move, one, prism_xz, print_pose
from end_clip_hardware import R, KH, KR, TIP, FACE, screw, tap

OUT = TOOLS.parent/'print'/'end-clips'
BITS = OUT/'parts'
AX, CY = 13., 128.                       # 13 mm reach, screws outside the plug lanes
INNER, END, OUTER = 103., 120.35, 143.  # positive-Y clip before mirroring
HZ = -60.                                # existing flange top; desk independent
BOT, TOP = -66., -53.                    # female thread in the jaw itself
Z, X = V(0,0,1), V(1,0,0)
NAMES = ('left-clip','right-clip','hand-screw')


def yz(points,x0,x1):
    w = Part.makePolygon([V(x0,y,z) for y,z in points+points[:1]])
    return Part.Face(w).extrude(V(x1-x0,0,0))


def clip_blank():
    # Short jaw with a tapered top finger; root radii are INSIDE the C and
    # clear the tabletop. The rectangular lower land is just the tapped boss.
    prof = [(-11,6),(-8,9),(1,9),(16,6.4),(24,4.3),(24,.8),(23.2,0),(1.8,0),
            (.4,.75),(-.65,.75),(-1.1,.3),(-1.1,-1),(-.65,-2),(-.65,-49)]
    # Radius into the lower jaw stays below the thickest (50 mm) desk.
    prof += [(3.35-4*math.cos(a),-49-4*math.sin(a)) for a in [i*math.pi/16 for i in range(1,9)]]
    prof += [(23.5,TOP),(26,-55),(26,-64),(24,BOT),(2,BOT),(-8,-63.5),(-11,-60.5)]
    jaw = prism_xz(prof,INNER,OUTER)
    # This small C-channel encloses only the top flange, never the comb. Its
    # lower shelf carries weight; its far upper lip limits nose-down rotation.
    shelf = HZ-h.FLANGE_T
    socket = prism_xz([(22,-54),(34,-54.8),(42,-56.1),(63.4,-56.1),(65.3,-58),
                       (65.3,-62.9),(64.3,-63.9),(62.45,-63.9),(62.45,HZ+.45),
                       (37.55,HZ+.45),(37.55,shelf),(50.7,shelf),(50.7,shelf-1.8),
                       (49.9,shelf-2.55),(37.6,shelf-2.55),(24.6,-65.9),(22,-64)],INNER,END+2.6)
    # A closed end makes the hanger its own spacing jig. The end wall spans
    # just 4 mm from the channel root in print, supported on three sides.
    stop = box(37.1,41.6,END,END+2.6,shelf-.2,HZ+.65)
    s = one(jaw.multiFuse([socket,stop]),'clip blank')
    # 0.55 mm lead-in on the channel mouth, also relieves first-layer squish.
    top_lead = yz([(INNER-.1,HZ+.42),(INNER+.58,HZ+.42),(INNER-.1,HZ+1.1)],37.5,62.5)
    low_lead = yz([(INNER-.1,shelf+.01),(INNER+.58,shelf+.01),(INNER-.1,shelf-.67)],37.5,51)
    return one(s.cut(top_lead).cut(low_lead),'channel entrance')


def clip(blank,side):
    # Mirror ONLY the blank, never the thread. Both end clips print with
    # their open channel mouth down and their C-shaped walls in the bed plane.
    s = blank if side==1 else blank.mirror(V(0,0,0),V(0,1,0))
    return tap(s, AX, side*CY, BOT, TOP, side)


def placed(s,t,side):
    dz = -t-TIP
    return h.place(s,App.Placement(V(AX,side*CY,dz),App.Rotation(Z,360*dz/R['pitch'])))


def clear(a,b,label):
    if a.BoundBox.intersect(b.BoundBox):
        v = abs(a.common(b).Volume)
        assert v < 1e-5,(label,v)


def hit(a,b,label):
    v = abs(a.common(b).Volume)
    assert v > .01,(label,v)
    return v


def check(jaws,s,carrier):
    holder = move(carrier,z=HZ); fixed = Part.makeCompound(list(jaws.values()))
    area = {}; contacts = {}
    # Start off each end of the hanger and slide inward: no bending or snap.
    for side,jaw in jaws.items():
        for travel in (35,20,12,6,2,.5,0): clear(move(jaw,y=side*travel),holder,'fit to hanger end')
        area[side] = round(hit(move(holder,z=-.01),jaw,'shelf bears on flange')/.01,1)
        assert area[side]>185
        for dx,dy,dz in [(-.9,0,0),(.9,0,0),(0,.9*side,0),(0,0,.9)]:
            hit(move(holder,dx,dy,dz),jaw,'captured flange')
    tipped=holder.copy(); tipped.rotate(V(38,0,HZ-h.FLANGE_T),V(0,1,0),-2)
    back_roofs=fixed.common(box(54,62,-150,150,HZ+.45,HZ+5))
    hit(tipped,back_roofs,'rear flange meets upper lip, nose down 2 degrees')
    for t in (8,18,25.5,36.25,50):
        desk=box(0,110,-160,160,-t,0); clear(desk,holder,'desk to flange'); clear(desk,fixed,'desk to frame')
        for side,jaw in jaws.items():
            v=placed(s,t,side); clear(desk,v,'screw face kisses underside'); clear(holder,v,'screw does not clamp hanger')
            tip=hit(move(v,z=.01),desk,'screw tip on desk')/.01
            assert abs(tip-math.pi*FACE**2)<.3
            # Test material overlap, then measure surface-to-surface distance. On the
            # mirrored blank OCC's solid classifier reported a witness at the *top*
            # of the clamp, 59 mm above the end of the screw, for the 50 mm setting.
            clear(v,jaw,'screw clears tapped body')
            g=h.gap(v.Shells[0],jaw.Shells[0]); assert .18<g<.42,('real screw thread fit',t,side,g)
            assert BOT-(-t-TIP+KH)>=3 and min(TOP,-t-3.7)-BOT>12,('knob gap or working thread',t)
            assert hit(move(jaw,z=-.01),desk,'upper jaw on desk')/.01>795
            contacts[f'{t:g}mm']={'thread_normal_gap_mm':g,'contact_per_screw_mm2':round(tip,1)}
            # Loosen one full turn before presenting the holder and clips to the desk.
            loose=Part.makeCompound([holder,jaw,placed(s,t+R['pitch'],side)])
            for x in (-78,-24,-8,0): clear(move(loose,x=x),desk,'push onto desk')
    # Use the full swept knob/shank for every setting, not just end poses.
    sweep=cyl(KR,-50-TIP,-8-TIP+KH).fuse(cyl(R['r'],-50-TIP+KH-.1,-8))
    hardware=Part.makeCompound([fixed]+[move(sweep,AX,side*CY) for side in jaws])
    z=HZ+h.COMB_TOP; r=h.SEAT_D/2
    lanes=Part.makeCompound([box(-35,max(h.SEAT_X)+r,y-r,y+r,z,z+h.PLUG_L+5) for y in h.slot_centres()])
    cables=Part.makeCompound([move(cyl(h.CABLE_D/2,-600,0),x,y,z) for x in h.SEAT_X for y in h.slot_centres()])
    clear(lanes,holder,'plug access above comb'); clear(cables,holder,'cables through comb')
    clear(lanes,hardware,'all plug paths including lift'); clear(cables,hardware,'all hanging cables')
    return {'desk_range_mm':[8,50],'samples':contacts,'shelf_contact_each_mm2':list(area.values()),
            'slots_clear':len(h.slot_centres()),'seats_clear':len(h.SEAT_X)*len(h.slot_centres()),
            'plug_envelope_mm':[2*r,h.PLUG_L,5],'nose_down_stop_checked_deg':2}


def main():
    BITS.mkdir(exist_ok=True,parents=True); blank=clip_blank(); s=screw()
    jaws={side:clip(blank,side) for side in (-1,1)}
    carrier=h.hanger()
    pose=print_pose(carrier,[(V(0,1,0),90),(Z,90)])
    carrier_info=h.export_part(pose,'hanger') | h.overhangs(pose)
    assert carrier_info['bridged_ceiling_mm2']==0 and carrier_info['area_past_50_deg_mm2']==0
    report=check(jaws,s,carrier)
    assembled={'Carrier':move(carrier,z=HZ),'LeftClip':jaws[1],'RightClip':jaws[-1],
               'LeftScrew':placed(s,28,1),'RightScrew':placed(s,28,-1)}
    doc=App.newDocument('CableHolder'); h.CAD.mkdir(exist_ok=True)
    preview=h.HOLDER/'research'; preview.mkdir(exist_ok=True)
    for name,shape in assembled.items():
        MeshPart.meshFromShape(Shape=shape,LinearDeflection=.04,AngularDeflection=.2).write(str(preview/(name+'.stl')))
        doc.addObject('Part::Feature',name).Shape=shape
    doc.recompute(); doc.saveAs(str(h.CAD/'desk-cable-holder-assembly.FCStd'))
    Part.makeCompound(list(assembled.values())).exportStep(str(h.OUT/'assembly-preview.step'))
    App.closeDocument(doc.Name)
    h.OUT=BITS
    # Left/right as seen by the person facing the slot mouths (+X is away).
    poses={name:print_pose(jaws[side],[(X,side*90)]) for name,side in zip(NAMES,(1,-1))}
    poses[NAMES[2]]=print_pose(s)
    report['parts']={'hanger':carrier_info} | {n:h.export_part(p,n)|h.overhangs(p) for n,p in poses.items()}
    plates.PRINT=BITS; plates.OUT=OUT
    report['plate']=plates.build_plate('print-this',[[*NAMES[:2]],[NAMES[2],NAMES[2]]],{n:plates.part_mesh(n) for n in NAMES})
    (OUT/'verification.json').write_text(json.dumps({'status':'CAD_PASS','physical_test':False,**report},indent=2)+'\n')
    print('END_CLIPS_PASS',flush=True)


if __name__ in ('__main__','build_end_clips'):
    main()
