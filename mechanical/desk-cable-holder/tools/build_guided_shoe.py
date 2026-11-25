"""Build ONLY the optional replacement for the desk holder's round clamp pad.

Run with FreeCADCmd (see print/retrofit/README.md). Local coordinates: X into
 desk, Y along edge, h (+Z) DOWN from the hanger flange, XY origin on screw.
"""
import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import Part

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import build_desk_cable_holder as stock
from build_desk_cable_holder import V, box, cyl, move, one, place, prism, prism_xz

OUT = TOOLS.parent / 'print' / 'retrofit'   # outside stock generator's file cleanup
NAME = 'guided-pressure-shoe'
PLATE = 3.0
KEY_R, KEY_H = 19.8, 1.6
LAND, BLEND, THRUST = 2.5, 4.0, 3.8   # flat radius, edge radius, tip height
HEAD_HALF, NECK_HALF = 8.3, 6.1
LIP, HEIGHT = 9.65, 11.5
FRONT = 0.7 - stock.SCREW_X
BACK = 23.5


def shoe():
    # The load is borne by the perimeter on the flat flange, not by the floor
    # of the shallow pocket. The keyed pilot stops the hanger turning on it.
    plate = prism([(FRONT, -20), (FRONT+4, -24), (BACK-2, -24), (BACK, -22),
                   (BACK, 22), (BACK-2, 24), (FRONT+4, 24), (FRONT, 20)], 0, PLATE)
    # Clearance over the spine's 45-degree jaw gusset on a 50 mm desk.
    plate = plate.cut(prism_xz([(FRONT-2, 1.8), (FRONT, 1.8), (FRONT+3, 4.8), (FRONT-2, 4.8)], -25, 25))
    # A 45-degree chamfer around the pilot both eases alignment and
    # supports the curved rear of the pilot when printing on the edge.
    def teardrop(r, h):
        q = r / math.sqrt(2)
        a, b, tip = V(-q,-q,h), V(-q,q,h), V(-2*q,0,h)
        return Part.Wire([Part.Arc(a,V(r,0,h),b).toShape(),
                          Part.makeLine(b,tip), Part.makeLine(tip,a)])
    key = Part.makeLoft([teardrop(KEY_R-KEY_H,-KEY_H), teardrop(KEY_R+0.1,0.1)], True, True)
    key = key.common(box(FRONT+0.6, BACK, -24, 24, -KEY_H-1, 1))
    # Wider heel is both a stiffener and the print bed contact.
    heel = prism_xz([(BACK-8, PLATE-0.2), (BACK, PLATE-0.2), (BACK, 5.4), (BACK-5.4,5.4)], -21.8,21.8)
    # U-fork opens towards the desk edge. Slip the stock mushroom in from
    # the side; the ledges catch it loosely but are unloaded when clamping.
    fork = prism_xz([(-9,PLATE-0.2), (20,PLATE-0.2), (20,PLATE),
                     (20-(HEIGHT-PLATE),HEIGHT), (-8,HEIGHT), (-9,HEIGHT-1)], -11.4,11.4)
    # The round end of the channel locates the mushroom; open both grooves
    # to the front. Make the mouth a little wider for entry.
    def channel(r, h0, h1):
        return cyl(r,h0,h1).fuse(prism([(-12,-r-1),(-9,-r-1),(-7,-r),(0,-r),
                                        (0,r),(-7,r),(-9,r+1),(-12,r+1)],h0,h1))
    plate = one(plate.fuse(fork), "fork blank")
    plate = one(plate.cut(channel(HEAD_HALF, PLATE, LIP).removeSplitter()), "head track")
    plate = one(plate.cut(channel(NECK_HALF, LIP-0.1, HEIGHT+1).removeSplitter()), "neck track")
    # Small flat thrust land with a circular blend into the plate. A tilted
    # screw face rolls onto the blend instead of catching the retaining fork.
    base = PLATE-0.1
    end = math.acos(1-(THRUST-base)/BLEND)
    def edge(a):
        return V(LAND+BLEND*math.sin(a), 0, THRUST-BLEND*(1-math.cos(a)))
    a, b = V(0,0,base), V(0,0,THRUST)
    wire = Part.Wire([Part.makeLine(a,b), Part.makeLine(b,edge(0)),
                      Part.Arc(edge(0),edge(end/2),edge(end)).toShape(), Part.makeLine(edge(end),a)])
    button = Part.Face(wire).revolve(V(), V(0,0,1), 360)
    for label, solid in [('pilot', key), ('heel', heel), ('button', button)]:
        assert solid.isValid(), label
        plate = one(plate.fuse(solid,1e-5), label+' union')
    return plate


def world(s, desk):
    return place(s, App.Placement(V(stock.SCREW_X,0,-desk-stock.FLANGE_T), App.Rotation(V(1,0,0),180)))


def check(s):
    # Read-only copies in the original CAD reference frame. Exact mushroom
    # geometry; thread-free screw/nut proxies as in the stock interference test.
    original = stock.Holder(plain=True)
    dz = stock.PAD_T-stock.POCKET-THRUST   # shift screw down by 2.8 mm
    reports = {}
    for desk in stock.DESKS:
        asm = original.assemble(desk)
        asm['clamp-pad'] = world(s, desk)
        asm['clamp-screw'] = move(asm['clamp-screw'], z=dz)
        # Do not use the stock check's 0.05 mm³ touching tolerance for the new part.
        pad = asm['clamp-pad']
        for n, other in asm.items():
            if n != 'clamp-pad':
                assert abs(pad.common(other).Volume) < 1e-5, (desk, n)
        stock.interference(asm)
        screw, nut = asm['clamp-screw'], asm['clamp-nut']
        start = screw.BoundBox.ZMin + stock.SCREW_KNOB_H
        assert start <= nut.BoundBox.ZMin and start+stock.SCREW_THREAD >= nut.BoundBox.ZMax
        assert abs(screw.distToShape(pad)[0]) < 1e-6
        # Area from 0.02 mm virtual closure; pilot still clears pocket floor.
        contact = move(pad,z=0.02).common(asm['hanger']).Volume / 0.02
        assert contact > 700, ('flange contact', contact)
        # Test both rotation directions: the front edge hits the fixed spine,
        # and the asymmetric pilot hits the fixed pocket, rather than spinning.
        for angle in (-5, 5):
            yaw = pad.copy()
            yaw.rotate(V(stock.SCREW_X,0,0), V(0,0,1), angle)
            assert all(yaw.common(asm[n]).Volume > 0.01 for n in ('clamp-body','hanger')), angle
        gap = pad.distToShape(asm['clamp-body'])[0]
        # Worst tall plug envelope, 9.5 mm wide, in the nearest lanes.
        for x in stock.SEAT_X:
            for y in (-stock.SLOT_FIRST, stock.SLOT_FIRST):
                z = stock.COMB_TOP-desk
                assert pad.distToShape(move(cyl(stock.SEAT_D/2,z,z+stock.PLUG_L),x,y))[0] > 1
        reports[f'{desk:g}'] = {'flange_contact_mm2': round(contact,1), 'shoe_to_clamp_gap_mm': round(gap,2)}
    # Socket articulation in isolation, not a claim that the threaded shank
    # can tilt that far in its nut. Test the actual stock screw nose and neck.
    nose = original.screw.common(box(-12,12,-12,12,original.screw_len-13,original.screw_len+1))
    nose = place(move(nose,z=-original.screw_len), App.Placement(V(),App.Rotation(V(1,0,0),180)))
    for deg in (0,2,4):
        t = math.radians(deg)
        # Height of the center of a plane tangent to the rounded land.
        h = THRUST + LAND*math.tan(t) + BLEND*(1/math.cos(t)-1)
        for az in range(0,360,45):
            axis = V(math.cos(math.radians(az)),math.sin(math.radians(az)),0)
            tipped = place(nose, App.Placement(V(0,0,h),App.Rotation(axis,deg)))
            assert abs(tipped.common(s).Volume) < 1e-6, (deg,az)
            # A 0.02 mm advance must hit the bearing (OCC can miss a
            # tangency at the seam of a revolved face in distToShape).
            assert move(tipped,z=-0.02).common(s).Volume > 1e-4, (deg,az)
    # The head slides down the whole open channel off the desk without
    # flexing, but cannot pull straight down past the two capture lips.
    for x in range(-34,1):
        assert abs(move(nose,x=x,z=THRUST+0.2).common(s).Volume) < 1e-6, ('entry', x)
    assert move(nose,z=THRUST+3).common(s).Volume > 1
    return reports


def main():
    s = shoe()
    desks = check(s)
    posed = stock.print_pose(s, [(V(0,1,0),90)])  # long rear edge on bed, fork opens upward
    overhangs = stock.overhangs(posed)
    assert overhangs['bridged_ceiling_mm2'] == overhangs['area_past_50_deg_mm2'] == 0, overhangs
    OUT.mkdir(exist_ok=True)
    stock.OUT = OUT  # stock.export_part writes only this basename
    info = stock.export_part(posed, NAME)
    (OUT/'verification.json').write_text(json.dumps({'part': NAME, 'desks_mm': desks,
        'socket_tilts_checked_deg': [0,2,4], 'yaw_stop_checked_deg': [-5,5],
        'side_entry_and_axial_capture': True, **info, **overhangs}, indent=2)+'\n')
    print('GUIDED_SHOE_PASS')


if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
