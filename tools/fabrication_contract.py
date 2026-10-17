"""Explicit bare-PCB manufacturing contract; no supplier approval is implied.

Only stack/finish metadata may change in the frozen routed carrier. No board save
or routing action is performed by these helpers. All dimensions are millimetres.
"""
import hashlib
import math
from pathlib import Path
from sexp import parse, one, nodes

CARRIER_STACK = '''(stackup
 (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
 (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))
 (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4 Tg170") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "In1.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 2" (type "core") (thickness 1.04) (material "FR4 Tg170") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4 Tg170") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035))
 (layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste"))
 (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
 (copper_finish "ENIG") (dielectric_constraints no))'''

# Passive panel has TWO LOGICAL KiCad copper layers but ZERO retained copper.
# Zero copper thickness is intentional, not an invented 1oz surviving layer.
PANEL_STACK = '''(stackup
 (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
 (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))
 (layer "F.Cu" (type "copper") (thickness 0))
 (layer "dielectric 1" (type "core") (thickness 1.58) (material "FR4 Tg170") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0))
 (layer "B.Mask" (type "Bottom Solder Mask") (color "Black") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste"))
 (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
 (copper_finish "None") (dielectric_constraints no))'''


def with_stack(text, stack):
    # Reuse byte-preserving span scanner; never serialize/reformat unrelated copper.
    from hro_merge_overlay import spans
    matches=[(a,b) for a,b,d in spans(text) if d==2 and text[a:b].startswith('(stackup')]
    assert len(matches)<=1
    if matches:
        a,b=matches[0]; return text[:a]+stack+text[b:]
    at=text.index('(setup')+len('(setup')
    return text[:at]+'\n\t\t'+stack+text[at:]


def validate_stack(path, carrier=True):
    tree=parse(Path(path).read_text())
    stack=one(one(tree,'setup'),'stackup')
    assert stack==parse(CARRIER_STACK if carrier else PANEL_STACK), 'native stack/finish differs from fabrication requirements'
    assert float(one(one(tree,'general'),'thickness')[1])==1.6
    assert abs(sum(float(one(l,'thickness')[1]) for l in nodes(stack,'layer') if one(l,'thickness'))-1.6)<1e-9
    return stack


def via_audit(path):
    """Native shape intersections: barrel disk vs exposed SMD copper and paste.

    Uses actual positioned/rotated rounded native pad polygons, not bounding boxes
    or centre-in-pad tests. Mask and paste-only windows are unioned by side. This
    board has zero pad mask/paste expansion; reject new unsupported margins rather
    than silently ignore them. Boundary proximity <=1um is conservatively counted.
    Exported-CAM audit independently confirms the result from Gerbers.
    """
    import pcbnew as p
    board=p.LoadBoard(str(path))
    pads=[(fp,pad) for fp in board.GetFootprints() for pad in fp.Pads()]
    sides=[]
    for cu,mask,paste in [(p.F_Cu,p.F_Mask,p.F_Paste),(p.B_Cu,p.B_Mask,p.B_Paste)]:
        mask_poly=p.SHAPE_POLY_SET();paste_poly=p.SHAPE_POLY_SET();exposed=[]
        for fp,pad in pads:
            for layer,target in [(mask,mask_poly),(paste,paste_poly)]:
                if not pad.IsOnLayer(layer):continue
                if layer==mask:assert pad.GetSolderMaskExpansion(layer)==0
                else:assert tuple(pad.GetSolderPasteMargin(layer))==(0,0)
                poly=p.SHAPE_POLY_SET();pad.TransformShapeToPolygon(poly,layer,0,1000,p.ERROR_OUTSIDE)
                target.BooleanAdd(poly)
        for fp,pad in pads:
            if pad.GetAttribute()!=p.PAD_ATTRIB_SMD or not pad.IsOnLayer(cu):continue
            poly=p.SHAPE_POLY_SET();pad.TransformShapeToPolygon(poly,cu,0,1000,p.ERROR_OUTSIDE)
            poly.BooleanIntersection(mask_poly)
            if poly.OutlineCount():exposed.append((fp,pad,poly))
        sides.append((board.GetLayerName(cu),paste_poly,exposed))
    records=[]
    for v in sorted((v for v in board.GetTracks() if v.GetClass()=='PCB_VIA'),key=lambda v:v.m_Uuid.AsString()):
        hits=[];paste_hits=[];boundary=[];paste_boundary=[]
        disk=p.SHAPE_POLY_SET();disk.NewOutline()
        cx,cy=v.GetPosition();radius=v.GetDrill()/2
        for i in range(1024):
            a=i*2*math.pi/1024;disk.Append(round(cx+radius*math.cos(a)),round(cy+radius*math.sin(a)))
        def overlaps(poly):
            cut=p.SHAPE_POLY_SET();cut.BooleanIntersection(poly,disk)
            return cut.Area()/1e12>1e-9
        for side,paste_poly,exposed in sides:
            for fp,pad,poly in exposed:
                if poly.Collide(v.GetPosition(),v.GetDrill()//2+1000):
                    (hits if overlaps(poly) else boundary).append({'side':side,'ref':fp.GetReference(),'pad':pad.GetNumber(),'pad_uuid':pad.m_Uuid.AsString()})
            if paste_poly.Collide(v.GetPosition(),v.GetDrill()//2+1000):(paste_hits if overlaps(paste_poly) else paste_boundary).append(side)
        assert v.GetPrimaryDrillFilledFlag() and v.GetPrimaryDrillCappedFlag()
        records.append({'uuid':v.m_Uuid.AsString(),'xy_mm':[round(p.ToMM(c),6) for c in v.GetPosition()],
            'net':v.GetNetname(),'drill_mm':round(p.ToMM(v.GetDrill()),6),
            'diameter_mm':round(p.ToMM(v.GetWidth(p.F_Cu)),6),
            'exposed_SMD_copper_hits':hits,'paste_overlap_sides':paste_hits,
            'exposed_SMD_boundary_near_hits':boundary,'paste_boundary_near_sides':paste_boundary,
            'process':'IPC-4761 Type VII; nonconductive epoxy fill + planarized copper cap, both sides'})
    return {'board_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'method':'Native polygon BooleanIntersection against 1024-vertex actual drill disk; positive area >1e-9mm2. Native curves <=0.001mm error; boundary/tangency within0.001mm recorded separately, not counted as positive overlap.',
        'via_count':len(records),'barrels_over_exposed_SMD_copper':sum(bool(v['exposed_SMD_copper_hits']) for v in records),
        'barrels_over_paste':sum(bool(v['paste_overlap_sides']) for v in records),
        'barrels_at_SMD_boundary_only':sum(bool(v['exposed_SMD_boundary_near_hits']) and not v['exposed_SMD_copper_hits'] for v in records),
        'barrels_at_paste_boundary_only':sum(bool(v['paste_boundary_near_sides']) and not v['paste_overlap_sides'] for v in records),
        'uniform_process_scope':f'ALL {len(records)} through vias, not all PTH component holes/slots. Not every via independently needs filling. No ordinary tenting substitution.',
        'vias':records}
