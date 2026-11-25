"""Independent desk saddles for the existing hanger. Does not run the stock generator.
World: desk edge X=0; +X into desk, Y along edge, underside Z=0. Units: mm.
FreeCADCmd this file; DESK_MM optionally selects a single custom thickness.
"""
import json
import os
import sys
from pathlib import Path

import FreeCAD as App
import Part

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_desk_cable_holder as h
import build_plates as plates
from build_desk_cable_holder import V, box, move, one, prism_xz, print_pose

OUT = Path(__file__).resolve().parents[1] / 'print' / 'twin-saddles'
HALF = 19.5
CENTRE = 79.5
DROP = 19.0
SLOPE = 0.06


def yz(points, x0, x1):
    wire = Part.makePolygon([V(x0, y, z) for y, z in points + points[:1]])
    return Part.Face(wire).extrude(V(x1-x0, 0, 0))


def ramp(y):
    return -3.8 + SLOPE*y


def saddle(t):
    # Short upper jaw ends above the wedge. The rear arm is deliberately
    # below the desk; it carries hanger weight, never the wedge preload.
    blank = prism_xz([(-10,t+5),(-7,t+8),(27,t+8),(30,t+5),(30,t+0.8),
                     (29,t),(2,t),(0,t+0.7),(-0.7,t),(-0.7,0.7),(0,0),
                     (0,-1),(27,-1),(31,-5),(69,-5),(72,-8),(72,-68),
                     (70,-79),(68,-81),(62.5,-81),(62.5,-40),(53,-40),(51,-38),
                     (51,-31),(52,-30),(55.9,-30),(56.4,-30.5),(56.4,-34),
                     (62.5,-34),(62.5,-13),(61.5,-12),(-7,-12),(-10,-9)], -HALF, HALF)
    # Laterally entered wedge runway with fore/aft fences. Slight clearance
    # to the tabletop elsewhere; only the wedge and top jaw grip the desk.
    groove = yz([(-21,ramp(-21)),(21,ramp(21)),(21,2),(-21,2)], 1,26)
    # Through-hole for the anti-lift pin. Pointed +Y roof prints on its side.
    port = yz([(-4.5,-17),(4.5,-17),(7.1,-14.4),(4.5,-11.8),(-4.5,-11.8)], 61.9,74)
    return one(blank.cut(groove).cut(port), 'saddle')


def gauge(t):
    # Narrow nominal desk-opening sample, NOT a mount. The 0.2 mm slip
    # allowance is deliberate: test at both ends of the proposed footprint.
    return prism_xz([(-6,t+3),(26,t+3),(26,t+0.7),(25,t),(2,t),
                     (0,t+0.7),(-0.7,t),(-0.7,-0.2),(25,-0.2),(26,-0.9),
                     (26,-3.2),(-6,-3.2)],-3,3)


def wedge():
    a,b=-27,21
    blade=yz([(a,0),(b,0),(b,ramp(b)),(a,ramp(a))],1.35,25.65)
    # Thumb tab doubles as a hard stop. Do not drive to the stop.
    tab=yz([(a,-4),(-24,-4),(-24,-9),(a,-9)],1.35,25.65)
    return one(blade.fuse(tab),'wedge')


def keeper():
    # Drops 1.2 mm on the sill of the rear port after insertion. Lift its
    # thumb tab to remove. The pin floats clear of the hanger in use.
    return one(prism_xz([(49,-17.2),(50,-18.2),(62.0,-18.2),(62.0,-17),
                         (72.55,-17),(72.55,-22),(77,-22),(79,-20),(79,-13.8),
                         (50,-13.8),(49,-14.8)],-4,4),'keeper')


def clear(a,b,label):
    overlap=abs(a.common(b).Volume)
    assert overlap < 1e-5,(label,overlap)


def hits(a,b,label):
    v=abs(a.common(b).Volume)
    assert v>0.1,(label,v)
    return v


def validate(t, s, w, k, hanger):
    desk=box(0,150,-150,150,0,t)
    clear(s,desk,'desk/frame'); clear(w,desk,'desk/wedge'); clear(s,w,'wedge fit'); clear(s,k,'pin fit')
    assert s.distToShape(desk)[0]<1e-6 and w.distToShape(desk)[0]<1e-6 and s.distToShape(w)[0]<1e-6
    for shift in (-53,-30,-10,-2):
        travel=move(w,y=shift,z=SLOPE*shift)
        clear(travel,s,'wedge entry'); clear(travel,desk,'loose wedge')
    hits(move(w,y=5.5,z=SLOPE*5.5),s,'wedge travel stop')
    locs=(-CENTRE,CENTRE)
    bodies=Part.makeCompound([move(s,y=y) for y in locs]); keys=Part.makeCompound([move(k,y=y) for y in locs]); wedges=Part.makeCompound([move(w,y=y) for y in locs])
    bracket=Part.makeCompound([bodies,wedges]); fixed=Part.makeCompound([bracket,keys,desk]); bare=Part.makeCompound([bracket,desk]);
    seated=move(hanger,z=-DROP)
    clear(seated,fixed,'assembled hanger')
    # Loading path: lift just ahead of the hooks, push back through both
    # windows, lower. Test each swept segment via continuous box sections
    # of the bracket or intermediate positions at 1 mm intervals.
    for drop in (20,15,10,5,0):
        clear(move(seated,x=-16,z=5-drop),bare,'approach')
    for dx in range(-16,1): clear(move(seated,x=dx,z=5),bare,'window entry')
    for dz in range(6): clear(move(seated,z=dz),bare,'drop onto ledges')
    for off in locs:
        body=move(s,y=off); pin=move(k,y=off)
        for dx in (35,20,11,5,0):
            moving=move(pin,x=dx,z=1.35)
            clear(moving,body,'insert key'); clear(moving,seated,'key above flange')
        clear(move(pin,z=1.35),desk,'key to desk')
        hits(move(pin,x=1),body,'key notch resists withdrawal')
        # Can neither raise the hanger off its 4 mm hook nor withdraw it,
        # even if it lifts the pin against the roof of the port.
        hits(move(seated,z=3.8),move(pin,z=2),'keeper blocks unhook')
        hits(move(seated,x=-1),body,'hook stops outward movement')
        hits(move(seated,x=1),body,'rear stop')
        contact=hits(move(seated,z=-0.02),body,'window ledge is load bearing')/0.02
        assert 193<contact<197,contact
    # The rear stop extends below the window: the *solid lower rail*, not
    # the empty middle of the window, bears against it if the comb noses down.
    tipped=seated.copy(); tipped.rotate(V(59.5,0,-34),V(0,1,0),-1)
    heels=bodies.common(box(62.49,73,-120,120,-82,-75))
    hits(tipped,heels,'rear heels catch nose-down rotation at 1 degree')
    for dy in (-3,3): hits(move(seated,y=dy),bodies,'lateral window stop')
    # Check cylinders for actual plug width as well as cable tails, every seat.
    plug=h.cyl(4.75,0,50); wire=h.cyl(2.5,-100,0)
    keepout=Part.makeCompound([move(Part.makeCompound([plug,wire]),x,y,h.COMB_TOP-DROP) for x in h.SEAT_X for y in h.slot_centres()]); clear(keepout,bracket,'all 64 cables/plugs');clear(keepout,keys,'cables/keys')
    return {'centres_mm':2*CENTRE,'hook_bearing_each_mm2':round(contact,2),'hanger_drop_mm':DROP,'plug_envelope_mm':[9.5,50],'seats_checked':64,'lift_to_install_mm':5,'nominal_keeper_to_flange_mm':0.8}


def main():
    sizes=[float(os.environ['DESK_MM'])] if 'DESK_MM' in os.environ else [18,25,28]
    hanger=h.hanger(); w=wedge(); k=keeper()
    for t in sizes:
        assert 8<=t<=50,'use a measured thickness, 8..50 mm'
        tag=f'{t:g}mm'; dest=OUT/tag; dest.mkdir(exist_ok=True,parents=True)
        s=saddle(t)
        checks=validate(t,s,w,k,hanger)
        h.OUT=plates.PRINT=plates.OUT=dest
        models={'saddle':print_pose(s,[(V(1,0,0),90)]),'wedge':print_pose(w,[(V(1,0,0),180)]),'keeper':print_pose(k,[(V(1,0,0),90)])}
        models['fit-gauge']=print_pose(gauge(t),[(V(1,0,0),90)])
        clear(gauge(t),box(0,150,-150,150,0,t),'fit gauge')
        parts={}
        for n,m in models.items():
            v=h.overhangs(m); assert v['area_past_50_deg_mm2']<0.1 and v['bridged_ceiling_mm2']<0.1,(n,v)
            parts[n]=h.export_part(m,n)|v
        meshes={n:plates.part_mesh(n) for n in parts}
        plate=plates.build_plate('twin-saddles-'+tag,[['saddle','saddle'],['wedge','keeper','wedge','keeper']],meshes)
        data={'nominal_desk_mm':t,'status':'CAD_PASS','physical_test':False,'fit':checks,'parts':parts,'plate':plate}
        (dest/'verification.json').write_text(json.dumps(data,indent=2)+'\n')
        print('TWIN_SADDLE_PASS',tag,flush=True)


if __name__=='__main__' or __name__=='build_twin_saddles':
    main()
