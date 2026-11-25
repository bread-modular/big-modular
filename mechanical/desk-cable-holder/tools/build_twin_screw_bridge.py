"""Wide desk bridge with two direct-acting printed pressure screws. Additive build only.
FreeCADCmd this file. Local frame: +X into desk, Y along edge, lower jaw top Z=0.
The unchanged hanger imports in its original frame. No old print files are written.
"""
import json
import math
import runpy
import sys
from pathlib import Path

import FreeCAD as App
import Part

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import build_desk_cable_holder as h
import build_plates as plates
from build_desk_cable_holder import V, box, cyl, move, one, prism, prism_xz, print_pose, rev

# Reuse the previous removable keeper exactly. Do not run the wedge-saddle build.
saddles = runpy.run_path(str(TOOLS/'build_twin_saddles.py'))
yz, old_keeper = saddles['yz'], saddles['keeper']
OUT = TOOLS.parent/'print'/'twin-screw-bridge'
SIZES = {'8-22mm': (8,22), '22-36mm': (22,36), '36-50mm': (36,50)}
C, HALF, AXIS = 75.0, 24.0, 14.0              # station centres ±C, 48 mm jaw width
DX, HZ = 6.0, -41.0                           # hanger offset from stock frame
KZ = HZ + 19.0                                # offset of the previous keeper/hook interface
R = dict(r=7.5, depth=1.4, pitch=4.0, crest=0.65)
FIT, NUT_W, NUT_H, NZ = 0.40, 24.0, 16.0, -18.5
KNOB, KH, TIP, FACE = 13.0, 7.0, 49.0, 5.75
SOLES, RAIL_HALF = 3.0, 102.0
ZAX, XAX = V(0,0,1), V(1,0,0)


def cp(*shapes):
    return Part.makeCompound(list(shapes))


def both(shape):
    return cp(*(move(shape,y=y) for y in (-C,C)))


def clear(a,b,label):
    if not a.BoundBox.intersect(b.BoundBox):
        return
    v=abs(a.common(b).Volume)
    assert v < 1e-5, (label,v)


def hit(a,b,label):
    v=abs(a.common(b).Volume)
    assert v > 0.05,(label,v)
    return v


def keyway(male):
    # Rail keys run ALONG the desk edge. The groove runs straight through
    # each side-printed jaw: no floating lip for the slicer to start in mid-air.
    # The lands each side of the key, not the dovetail roof, bear on the rail.
    if male:
        profile=[(-4.7,-0.15),(4.7,-0.15),(4.7,0),(7.1,2.4),(6.8,2.7),(-6.8,2.7),(-7.1,2.4),(-4.7,0)]
        extent=22.0
    else:
        profile=[(-5.15,-1),(5.15,-1),(5.15,0),(7.85,2.7),(7.50,3.05),(-7.50,3.05),(-7.85,2.7),(-5.15,0)]
        extent=HALF+1
    return prism_xz([(AXIS+x,z) for x,z in profile],-extent,extent)


def rail():
    # The plate prints flat. A shallow bevel at each end avoids sharp corners.
    e=RAIL_HALF
    p=prism([(0,-e+3),(3,-e),(26,-e),(29,-e+3),(29,e-3),(26,e),(3,e),(0,e-3),
             (0,4),(2.5,0),(0,-4)],0,SOLES)  # centre V marks the user-facing edge
    p=p.fuse(both(move(keyway(True),z=SOLES)))
    for y in (C-HALF-2.3,-C+HALF+2.3):
        p=p.fuse(box(2,27,y-2,y+2,SOLES-0.1,SOLES+4.2))  # inner stop for side entry
    return one(p, 'bridge')


def frame(gap):
    # The long rear branch carries cable weight, not screw preload. Each C and
    # hook are in one XZ profile, continuous in every perimeter on the print bed.
    z=gap+SOLES
    prof=[(-17,z+10),(-13,z+14),(24,z+14),(29,z+9),(29,z),
          (0.5,z),(-0.8,z+0.8),(-0.8,1.2),(0,0),(31,0),(43,-3),
          (69+DX,-3),(72+DX,-6),(72+DX,-68+KZ),(70+DX,-79+KZ),
          (68+DX,-81+KZ),(62.5+DX,-81+KZ),(62.5+DX,-40+KZ),
          (53+DX,-40+KZ),(51+DX,-38+KZ),(51+DX,-31+KZ),(52+DX,-30+KZ),
          (55.9+DX,-30+KZ),(56.4+DX,-30.5+KZ),(56.4+DX,-34+KZ),
          (62.5+DX,-34+KZ),(62.5+DX,-13+KZ),(61.5+DX,-12+KZ),
          (51+DX,-17),(34,-17),(30,-24),(0,-24),(-6,-28),(-13,-28),(-17,-24)]
    body=prism_xz(prof,-HALF,HALF).cut(move(keyway(False),z=z))
    # Side-entry square nut; screw captures it. A full 5.5 mm floor carries compression.
    halfnut=NUT_W/2+0.25
    slot=box(AXIS-halfnut,AXIS+halfnut,-halfnut,HALF+1,NZ,NZ+NUT_H+0.5)
    r=R['r']+0.55; q=r/math.sqrt(2)
    hole=cyl(r,-30,1).fuse(prism([(-q,q),(0,r*math.sqrt(2)),(q,q)],-30,1))
    port=yz([(-4.5,-17),(4.5,-17),(7.1,-14.4),(4.5,-11.8),(-4.5,-11.8)],61.9,74)
    return one(body.cut(slot).cut(move(hole,x=AXIS)).cut(move(port,DX,0,KZ)), 'C frame')


def nut():
    # Non-standard printed thread, not metric hardware. Ends relieved for starting by hand.
    return one(h.tapped(box(-NUT_W/2,NUT_W/2,-NUT_W/2,NUT_W/2,0,NUT_H),R,FIT,0,NUT_H),'square nut')


def screw():
    # One-piece blunt pressure screw, NOT a screw driven into wood. The smooth tip
    # passes through the nut. Only the chamfered flat face contacts the desk.
    r,root=R['r'],R['r']-R['depth']
    rod=h.thread_rod(R,KH-0.7,TIP-1.5)
    taper=rev([(0,KH-1),(r+0.5,KH-1),(r+0.5,TIP-4),(root-0.12,TIP-1.5),(0,TIP-1.5)])
    rod=rod.common(taper,h.FZ)
    tip=rev([(0,TIP-2.5),(root-0.2,TIP-2.5),(root-0.2,TIP-0.35),(FACE,TIP),(0,TIP)])
    return one(h.lobed(KNOB,KH,6,4,0.7).fuse(rod,h.FZ).fuse(tip,h.FZ),'pressure screw')


def located_screw(s,u):
    base=u-TIP
    return h.place(s,App.Placement(V(AXIS,0,base),App.Rotation(ZAX,360*(base-NZ)/R['pitch'])))


def pressure_envelope(u):
    # Conservative swept knob circle for any rotation, and the major-diameter shaft.
    return move(cyl(KNOB,0,KH).fuse(cyl(R['r'],KH-0.1,TIP)),AXIS,0,u-TIP)


def verify_hanger(f, toprail, pin, hanger):
    frames=both(f); pins=both(pin); s=move(hanger,DX,0,HZ)
    # Sweep the entire knob and shaft through *all* 14 mm of adjustment, not
    # just two end poses. The hanger is fitted only after the screws are snug.
    sweep=cyl(KNOB,2-TIP,16-TIP+KH).fuse(cyl(R['r'],2-TIP+KH-0.1,16))
    iron=cp(frames,toprail,both(move(sweep,AXIS)))
    clear(s,cp(iron,pins),'seated hanger')
    for dz in range(-15,6,2): clear(move(s,x=-16,z=dz),iron,'raise in front')
    for dx in range(-16,1): clear(move(s,x=dx,z=5),iron,'enter windows')
    for dz in range(6): clear(move(s,z=dz),iron,'lower onto hooks')
    for y in (-C,C):
        body=move(f,y=y); k=move(pin,y=y)
        for dx in (35,25,15,8,4,0):
            advance=move(k,x=dx,z=1.35); clear(advance,body,'insert keeper'); clear(advance,s,'keeper to flange')
        clear(k,body,'seated pin'); hit(move(k,x=1),body,'key notch catches')
        hit(move(s,z=3.8),move(k,z=2),'anti-lift'); hit(move(s,x=-1),body,'hook'); hit(move(s,x=1),body,'back stop')
        bearing=hit(move(s,z=-0.02),body,'window bearing')/0.02
        assert 239<bearing<241,bearing
    for dy in (-3,3): hit(move(s,y=dy),frames,'lateral stop')
    tilted=s.copy(); tilted.rotate(V(59.5+DX,0,-34+KZ),V(0,1,0),-1)
    hit(tilted,frames.common(box(62.49+DX,73+DX,-110,110,-82+KZ,-75+KZ)),'heel catches 1 degree nose-down')
    # A conservative swept box from in front of every slot to its fourth seat,
    # including 5 mm plug lift. This covers insertion as well as all 64 rest positions.
    z=HZ+h.COMB_TOP; r=h.SEAT_D/2
    lanes=cp(*(box(-35,DX+max(h.SEAT_X)+r,y-r,y+r,z,z+55) for y in h.slot_centres()))
    cables=cp(*(move(cyl(h.CABLE_D/2,-600,0),x+DX,y,z) for y in h.slot_centres() for x in h.SEAT_X))
    clear(lanes,cp(iron,pins),'all 16 plug insertion lanes'); clear(cables,cp(iron,pins),'64 hanging cables')
    return dict(hook_area_each_mm2=round(bearing,2),seats=64,straight_entry_lanes=16,
                plug_diameter_height_lift_mm=[2*r,50,5],nose_down_stop_checked_deg=1)


def verify_range(tag,lo,hi,f,plate,pin,hanger,sc,nu):
    gap=hi+2; rail_at=move(plate,z=gap); n=move(nu,AXIS,0,NZ)
    clear(f,n,'nut cavity'); hit(move(n,z=-0.05),f,'nut floor')
    nturn=n.copy(); nturn.rotate(V(AXIS,0,NZ),ZAX,3); hit(nturn,f,'nut cannot turn')
    for y in (40,28,15,1,0): clear(move(n,y=y),f,'nut side insertion')
    pair=both(f); clear(rail_at,pair,'two dovetails')
    for side in (-1,1):
        jaw=move(f,y=side*C)
        for offset in (55,42,30,16,6,1,0): clear(move(jaw,y=side*offset),rail_at,'slide on from rail end')
        hit(move(jaw,y=-side),rail_at,'rail inner stop')
        for dx,dz in ((1.2,0),(-1.2,0),(0,1.5)):
            hit(move(jaw,dx,0,dz),rail_at,'dovetail capture')
    area=hit(move(pair,z=-0.02),rail_at,'local top lands')/(2*0.02)
    assert area>800,area
    hw={}
    # The same sweep is repeated in each local frame. Use a few integer and
    # fractional thread phases, including both limits of the adjustment range.
    for t in sorted({float(lo),float(hi),(lo+hi)/2,hi-0.75}):
        u=gap-t; desk=box(0,150,-145,145,u,gap); screw_at=located_screw(sc,u)
        clear(pair,desk,'desk clears frames'); clear(rail_at,desk,'rail rests on top'); clear(n,desk,'nut below desk')
        clear(screw_at,desk,'blunt screw to underside'); clear(pressure_envelope(u),f,'spinning screw clears frame')
        area_tip=hit(move(screw_at,z=0.01),desk,'direct tip contact')/0.01
        assert abs(area_tip-math.pi*FACE**2)<0.3,area_tip
        assert rail_at.distToShape(desk)[0]<1e-6
        # Fully unrelieved screw thread spans the nut; knob does not bottom out.
        low,high=u-TIP+KH,u-4
        assert low <= NZ and high >= NZ+NUT_H-0.01, (t,low,high)
        free=-24-low; assert free>=1.9,(t,free)
        # Distance between the *real helices*, not overlapping proxy cylinders.
        thread=h.gap(screw_at,n); assert 0.19<thread<0.41,(t,thread)
        # The mount, with screws one turn loose and the hanger off, can be
        # pushed on from the edge before either screw sees load.
        loose=cp(pair,rail_at,both(pressure_envelope(u-R['pitch'])))
        for dx in (-80,-28,-12,0): clear(move(loose,x=dx),desk,'slide onto desk')
        hw[f'{t:g}']={'knob_to_lower_jaw_mm':round(free,2),'real_thread_gap_mm':thread,
                     'hanger_top_below_underside_mm':u-HZ,'tip_contact_each_mm2':round(area_tip,2)}
    info=verify_hanger(f,rail_at,pin,hanger)
    return dict(desk_range_mm=[lo,hi],sampled_desk_mm=hw,top_jaw_bearing_each_mm2=round(area,1),**info)


def part(dest,name,model):
    h.OUT=dest; ov=h.overhangs(model)
    # Overhangs inside an 0.8 mm detail of the key or the thread runout are
    # evaluated from the reported facets and by the support-disabled slice.
    return h.export_part(model,name)|ov


def make_plate(dest,name,rows,meshes):
    plates.OUT=dest
    return plates.build_plate(name,rows,meshes)


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    pin=move(old_keeper(),DX,0,KZ); plate=rail(); sc=screw(); nu=nut(); hanger=h.hanger()
    posed={'top-bridge':print_pose(plate,[(ZAX,90)]),'thumbscrew':print_pose(sc),'square-nut':print_pose(nu),
           'keeper':print_pose(pin,[(XAX,90)])}
    info={n:part(OUT,n,obj) for n,obj in posed.items()}
    plates.PRINT=OUT; mesh={n:plates.part_mesh(n) for n in posed}
    first=make_plate(OUT,'01-thread-test',[['thumbscrew','square-nut']],mesh)
    common=make_plate(OUT,'02-common-parts',[['top-bridge'],['thumbscrew','square-nut','keeper','keeper']],mesh)
    sizes={}
    for tag,(lo,hi) in SIZES.items():
        f=frame(hi+2); report=verify_range(tag,lo,hi,f,plate,pin,hanger,sc,nu)
        dest=OUT/tag; dest.mkdir(exist_ok=True); name='side-jaw'
        report['side_jaw']=part(dest,name,print_pose(f,[(XAX,90)]))
        plates.PRINT=dest; m=mesh|{name:plates.part_mesh(name)}
        report['jaw_pair']=make_plate(dest,'03-jaw-pair',[[name,name]],m)
        report['all_parts']=make_plate(dest,'complete-mount',[[name,name],['top-bridge'],['thumbscrew','square-nut','keeper']*2],m)
        (dest/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        sizes[tag]=report['desk_range_mm']; print('TWIN_SCREW_SIZE_PASS',tag,flush=True)
    (OUT/'verification.json').write_text(json.dumps({'status':'CAD_PASS','physical_test':False,'thread':R|{'radial_clearance_mm':FIT},'parts':info,'first_plate':first,'remaining_common_plate':common,'sizes':sizes},indent=2)+'\n')
    print('TWIN_SCREW_BRIDGE_PASS',flush=True)


if __name__ in ('__main__','build_twin_screw_bridge'):
    main()
