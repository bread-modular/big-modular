"""Compact two-screw variant and the small reproducible shortlist for the frame study.
FreeCADCmd compact_base.py: print/CAD verification for the compact only.
STUDY_PROXIES=1 FreeCADCmd compact_base.py: frame-analysis STLs in ignored research/.
All desk interfaces are in the released assembly frame. The wide plate is never overwritten.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_two_screw_base as b
from build_solder_arm import box, cyl, move, one, prism, prism_xz
import FreeCAD as App
import MeshPart

ARM=b.ARM
LIFT=24.                         # Six thread pitches, desktop limit 52 -> 28
DIR='compact-28'


def shorten(shape,dz):
    # Join on two identical, straight sections. Do not scale the old STEP: that
    # would alter tooth depth, thread pitch, drive fit and engagement length.
    if not dz: return shape
    z=-9
    hi=shape.common(box(-35,80,-60,60,z,20))
    lo=shape.common(box(-35,80,-60,60,-81,z-dz))
    return one(hi.fuse(move(lo,z=dz)),'shortened frame')


def reduced_back(shape,g):
    # Rejected control: only thin the centre, keeping both original end stations.
    f=13-g; mid=20.
    xy=prism([(-25,-40),(-13,-mid-f),(-g,-mid),(-g,mid),(-13,mid+f),(-25,40)],-70,12)
    xz=prism_xz([(-25,-66),(-13,-58),(-g,-58+f),(-g,2-f),(-13,2),(-25,8)],-57,57)
    return one(shape.cut(xy.common(xz)),'scallop control')


def studies():
    out=ARM/'research'/'frame-study'; out.mkdir(exist_ok=True,parents=True)
    for name,dz,g in [('stock',0,13),('lean8',0,8),('short28',24,13),('short36',16,13),
                      ('waist8-28',24,8),('waist8-36',16,8)]:
        s=b.frame_blank()
        if g<13: s=reduced_back(s,g)
        s=shorten(s,dz).cut(move(cyl(7.2,-1,15),b.arm.J1_X))
        for y in (-b.OFF,b.OFF): s=s.cut(move(cyl(7.4,-76+dz,-53+dz),b.AX,y))
        mesh=MeshPart.meshFromShape(Shape=one(s,name),LinearDeflection=.035,AngularDeflection=.16)
        assert mesh.isSolid();mesh.write(str(out/(name+'.stl')))
    print('FRAME_STUDY_PROXIES_PASS',flush=True)


def build():
    out=b.OUT/DIR; out.mkdir(exist_ok=True,parents=True)
    doc=App.openDocument(str(b.CAD/'assembly.FCStd'))
    try: stock=doc.getObject('wide_base').Shape.copy()
    finally: App.closeDocument(doc.Name)
    body=shorten(stock,LIFT); screw=b.screwfit.screw(b.HEIGHT-LIFT)
    # Exact B-rep comparisons of the complete load-bearing sections, not a check
    # of nominal diameters. Every added/removed cubic mm is in the straight web.
    def same(a,c): return abs(a.cut(c).Volume)+abs(c.cut(a).Volume)
    top=box(-35,80,-60,60,-8.9,20); bottom=box(-35,80,-60,60,-81,-9-LIFT-.1)
    upper_delta=same(stock.common(top),body.common(top))
    lower_delta=same(move(stock.common(bottom),z=LIFT),body.common(move(bottom,z=LIFT)))
    assert upper_delta<1e-5 and lower_delta<1e-5
    assert abs((stock.Volume-body.Volume)-LIFT*13*112)<.01
    b.BOTTOM+=LIFT; b.TOP+=LIFT; b.HEIGHT-=LIFT
    supplied=b.check_hardware(body,screw,b.HEIGHT,(5,8,16,21.5,25,28))
    cable=b.check_hardware(body,b.stock_screw(),b.screwfit.TIP,(5,21.5,28))
    upper,parts,at25=b.check_upper(body,b.original_clamp(),screw)
    b.CAD=b.CAD/DIR; b.PREVIEW=ARM/'research'/'two-screw-base'/DIR/'render'
    b.save_assembly(parts,body,at25)
    b.arm.OUT=b.plates.PRINT=b.plates.OUT=out
    posed={'base':b.arm.print_pose(body,(b.X,90)), 'hand-screw':b.arm.print_pose(screw)}
    details={n:b.arm.export_part(s,n)|b.arm.overhangs(s) for n,s in posed.items()}
    plate=b.plates.build_plate('print-this',[['base','hand-screw','hand-screw']],{n:b.plates.part_mesh(n) for n in posed})
    record=dict(status='CAD_PASS',physical_load_test=False,desk_range_mm=[5,28],screw_spacing_mm=80,
                screw_height_mm=b.HEIGHT,removed_web_height_mm=LIFT,removed_volume_cm3=round((stock.Volume-body.Volume)/1000,3),
                upper_jaw_difference_mm3=round(upper_delta,8),translated_lower_jaw_difference_mm3=round(lower_delta,8),
                parts=details,plate=plate,supplied_screw_fit=supplied,cable_screw_fit=cable,interface=upper)
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n');print('COMPACT_BASE_PASS',flush=True)


if __name__=='__main__' or any(Path(a).resolve()==Path(__file__).resolve() for a in sys.argv[1:]):
    studies() if os.getenv('STUDY_PROXIES')=='1' else build()
