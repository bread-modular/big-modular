"""Read-only acceptance contracts for canonical routing, HRO identity and processes.

Adapted from workspace023's useful routing/connected-island verifier, NOT its
abandoned GCT relief implementation. Native all-severity checks remain mandatory.
"""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import math
from sexp import parse, nodes, one
ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def routing_contract(tree):
    tracks=nodes(tree,'segment')+nodes(tree,'arc')+nodes(tree,'via')
    fps=[]
    for f in nodes(tree,'footprint'):
        props={p[1]:p[2] for p in nodes(f,'property')}
        fps.append([props.get('Reference'),props.get('MechanicalID'),one(f,'at'),one(f,'layer'),one(f,'path'),one(f,'locked'),nodes(f,'pad')])
    zones=[[v for v in z if not(isinstance(v,list) and v[0] in ('filled_polygon','fill_segments'))] for z in nodes(tree,'zone')]
    edges=[x for x in nodes(tree,'gr_line') if one(x,'layer')[1]=='Edge.Cuts']
    return {'tracks_and_vias':digest(sorted(tracks,key=repr)),
            'footprints_pin_net_pose':digest(sorted(fps,key=repr)),
            'zones':digest(sorted(zones,key=repr)), 'outline':digest(sorted(edges,key=repr)),
            'layers':digest(one(tree,'layers')), 'setup':digest(one(tree,'setup'))}


def verify_hro(fp, library):
    """Independent literal dimensions, native duplicate shell pads and NC mapping."""
    assert fp[1]=='BigModular:HRO-TYPE-C-31-M-12'
    assert [float(x) for x in one(fp,'at')[1:]]==[69.25,103.475]
    assert not nodes(fp,'model'), 'Never borrow the GCT model'
    lib=parse(library.read_text());assert not nodes(lib,'model')
    expected={'A1':(-3.225,.575),'A4':(-2.45,.575),'B8':(-1.75,.3),'A5':(-1.25,.3),
              'B7':(-.75,.3),'A6':(-.25,.3),'A7':(.25,.3),'B6':(.75,.3),
              'A8':(1.25,.3),'B5':(1.75,.3),'A9':(2.45,.575),'A12':(3.225,.575)}
    signatures=[]
    for tree in [fp,lib]:
        pads=nodes(tree,'pad');assert len(pads)==18
        smd={p[1]:p for p in pads if p[2]=='smd'};assert set(smd)==set(expected)
        for n,(x,w) in expected.items():
            pad=smd[n];assert pad[3]=='rect'
            assert [float(v) for v in one(pad,'at')[1:3]]==[x,-7.695]
            assert [float(v) for v in one(pad,'size')[1:]]==[w,1.45]
            assert set(one(pad,'layers')[1:])=={'F.Cu','F.Mask','F.Paste'}
            assert not any(one(pad,k) for k in ['solder_mask_margin','solder_paste_margin','solder_paste_margin_ratio','primitives'])
        pegs=[p for p in pads if p[1]==''];assert len(pegs)==2
        assert sorted([float(v) for v in one(p,'at')[1:3]] for p in pegs)==[[-2.89,-6.25],[2.89,-6.25]]
        assert all(p[2:4]==['np_thru_hole','circle'] and [float(v) for v in one(p,'drill')[1:]]==[.65] and [float(v) for v in one(p,'size')[1:]]==[.65,.65] for p in pegs)
        shells=[p for p in pads if p[1]=='S1'];assert len(shells)==4
        assert sorted(tuple(float(v) for v in one(p,'at')[1:3]) for p in shells)==[(-4.32,-6.78),(-4.32,-2.6),(4.32,-6.78),(4.32,-2.6)]
        for pad in shells:
            rear=float(one(pad,'at')[2])==-6.78
            assert pad[2:4]==['thru_hole','oval']
            assert one(pad,'drill')[1]=='oval'
            assert [float(v) for v in one(pad,'drill')[2:]]==[.6,1.7 if rear else 1.2]
            assert [float(v) for v in one(pad,'size')[1:]]==[1.,2.1 if rear else 1.6]
            assert set(one(pad,'layers')[1:])=={'*.Cu','*.Mask'}
        def norm(v):
            if isinstance(v,list):return [norm(x) for x in v]
            try:return float(v)
            except (TypeError,ValueError):return v
        signatures.append(sorted([norm([p[1],p[2],p[3],one(p,'at')[1:3],one(p,'size')[1:],one(p,'drill'),sorted(one(p,'layers')[1:])]) for p in pads],key=repr))
        assert any(one(x,'layer')[1]=='F.Fab' for x in nodes(tree,'fp_rect'))
        assert any(one(x,'layer')[1]=='F.CrtYd' for x in nodes(tree,'fp_rect'))
    assert signatures[0]==signatures[1]
    clearance=math.hypot(.335-.575/2,1.445-1.45/2)-.65/2
    assert clearance>.3965
    return {'physical_lands':12,'plated_shell_slots':4,'locator_NPTHs':2,
            'nominal_boss_to_nearest_land_clearance_mm':clearance,
            '3D_model':'absent, explicitly unverified','local_land_length_mm':1.45,
            'drawing_land_length_claim':False}


def verify_native(board, hardware):
    import pcbnew as p
    tree=parse((hardware/'big_modular.kicad_pcb').read_text())
    baseline=json.loads((ROOT/'docs/routed-baseline.json').read_text())
    assert routing_contract(tree)==baseline['routing_contract'], 'accepted routing/stack changed without review'
    tracks=list(board.GetTracks());vias=[t for t in tracks if t.GetClass()=='PCB_VIA']
    assert len(tracks)-len(vias)==421 and len(vias)==133 and len(list(board.Zones()))==4
    assert board.GetCopperLayerCount()==4
    assert all(v.GetPrimaryDrillFilledFlag() and v.GetPrimaryDrillCappedFlag() for v in vias), 'specified uniform Type VII process'
    assert all(round(p.ToMM(v.GetDrill()),6)==.3 for v in vias)
    con=board.GetConnectivity();assert con.Build(board);con.RecalculateRatsnest()
    assert con.GetUnconnectedCount(False)==0
    pads=defaultdict(list);fps=list(board.GetFootprints())
    for f in fps:
        if f.GetReference():assert f.GetLayer()==p.F_Cu
        for pad in f.Pads():
            if pad.GetNumber() and pad.GetNetname():pads[pad.GetNetname()].append(pad)
    connected={}
    for net,ps in pads.items():
        items=list(con.GetConnectedItems(ps[0]));ids={x.m_Uuid.AsString() for x in items}|{ps[0].m_Uuid.AsString()}
        assert all(q.m_Uuid.AsString() in ids for q in ps),(net,'split physical connectivity')
        assert all(x.GetNetname()==net for x in items),(net,'physical short')
        connected[net]=len(ps)
    assert '/GND' in connected and '/Autonomous hardware window and retry/RTN' in connected
    zones=[]
    for z in board.Zones():
        assert z.IsFilled();zones.append({'net':z.GetNetname(),'layer':board.GetLayerName(z.GetLayer()),'contours':z.GetFilledPolysList(z.GetLayer()).OutlineCount()})
    assert [z for z in zones if z['layer']=='In1.Cu']==[{'net':'/GND','layer':'In1.Cu','contours':1}]
    reserved=[(53.25,84.775,62.25,93.775),(137.75,84.775,146.75,93.775),(77.75,72.275,107.75,79.275)]
    for f in fps:
        if not f.GetReference() or f.GetReference() in ('J1','SW1','D10','J7'):continue
        assert f.GetFieldText('Placement')=='PLACED_ROUTED'
        f.BuildCourtyardCaches();box=f.GetCourtyard(p.F_Cu).BBox()
        x,y=p.ToMM(box.GetPosition());w,h=p.ToMM(box.GetSize())
        assert 49.75<x<150.25 and 72.275<y<102.275,(f.GetReference(),'off-board')
        for a,b,c,d in reserved:assert not(min(x+w,c)>max(x,a) and min(y+h,d)>max(y,b)),(f.GetReference(),'reserved access collision')
    usb=next(f for f in nodes(tree,'footprint') if any(q[1:3]==['Reference','J1'] for q in nodes(f,'property')))
    result=verify_hro(usb,hardware/'BigModular.pretty/HRO-TYPE-C-31-M-12.kicad_mod')
    return {'tracks':421,'vias':133,'zones':zones,'native_opens':0,'connected_pad_counts':connected,
            'USB':result,'accepted_routing_preserved':True,'all_components_front':True,'reserved_access_clear':True}
