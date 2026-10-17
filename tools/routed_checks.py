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


def verify_native(board, hardware, baseline_file=None):
    import pcbnew as p
    tree=parse((hardware/'big_modular.kicad_pcb').read_text())
    baseline=json.loads(Path(baseline_file or ROOT/'docs/routed-baseline.json').read_text())
    inventory=baseline.get('inventory',{'tracks':421,'vias':133,'zones':4})
    assert routing_contract(tree)==baseline['routing_contract'], 'accepted routing/stack changed without review'
    tracks=list(board.GetTracks());vias=[t for t in tracks if t.GetClass()=='PCB_VIA']
    assert {'tracks':len(tracks)-len(vias),'vias':len(vias),'zones':len(list(board.Zones()))}==inventory
    assert board.GetCopperLayerCount()==4
    assert all(v.GetPrimaryDrillFilledFlag() and v.GetPrimaryDrillCappedFlag() for v in vias), 'specified uniform Type VII process'
    assert all(round(p.ToMM(v.GetDrill()),6)==.3 for v in vias)
    con=board.GetConnectivity();assert con.Build(board);con.RecalculateRatsnest()
    assert con.GetUnconnectedCount(False)==0
    pads=defaultdict(list);fps=list(board.GetFootprints())
    for f in fps:
        if f.GetReference():assert f.GetLayer()==(p.B_Cu if f.GetReference() in BACK_CAP_POSES else p.F_Cu)
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
        f.BuildCourtyardCaches();box=f.GetCourtyard(f.GetLayer()).BBox()
        x,y=p.ToMM(box.GetPosition());w,h=p.ToMM(box.GetSize())
        assert 49.75<x and x+w<150.25 and 72.275<y and y+h<102.275,(f.GetReference(),'off-board')
        for a,b,c,d in [(52.25,94.275,63.25,102.275),(136.75,94.275,147.75,102.275)]:
            assert not(min(x+w,c)>max(x,a) and min(y+h,d)>max(y,b)),(f.GetReference(),'bracket relief, no FR4')
        for a,b,c,d in reserved:assert not(min(x+w,c)>max(x,a) and min(y+h,d)>max(y,b)),(f.GetReference(),'reserved access collision')
    usb=next(f for f in nodes(tree,'footprint') if any(q[1:3]==['Reference','J1'] for q in nodes(f,'property')))
    result=verify_hro(usb,hardware/'BigModular.pretty/HRO-TYPE-C-31-M-12.kicad_mod')
    return {'tracks':len(tracks)-len(vias),'vias':len(vias),'zones':zones,'native_opens':0,'connected_pad_counts':connected,
            'USB':result,'accepted_routing_preserved':True,'backside':verify_backside_caps(board,json.loads((ROOT/'docs/assembly-geometry.json').read_text())),'reserved_access_clear':True}


# Narrow LDO-R1 side exception; no other part may move to the back.
BACK_CAP_POSES={'C63':(113.3,86.1,0),'C64':(98.8,81.,180),
                'C65':(98.8,83.6,180),'C66':(98.8,87.9,180)}


def verify_backside_caps(board, geometry, height_mm=1.8):
    """Fixed B.Cu datum X3.1; conservative full courtyard+solder 3D envelopes.

    This checks the back independently, not by reusing the front 5.1mm budget.
    Neighbor boundary is module X=0. Brackets, mounting/tool volumes, all THT
    tail projections and a reserved 4mm strain-relief strap corridor are checked.
    The corridor is a routing constraint for prototype harness assembly, not an
    unverified cable/support solid or a promise about a neighboring module.
    """
    import pcbnew as p
    g=geometry;assert g['carrier_X_mm']==[3.1,4.7]
    assert height_mm==1.8,'Only exact reviewed CL31 max-height package allowed'
    fps={f.GetReference():f for f in board.GetFootprints() if f.GetReference()}
    assert {r for r,f in fps.items() if f.GetLayer()==p.B_Cu}==set(BACK_CAP_POSES),'unreviewed back-side population'
    occupied={};report={}
    def overlap(a,b):return all(min(hi,hj)>max(lo,lj) for (lo,hi),(lj,hj) in zip(a,b))
    obstacles={'panel':[[0,9.8],[0,128.5],[0,1.76]],
               'harness':g['harness_envelope_XYZ_mm'],
               'reserved_back_strap_corridor':[[0,3.1],[41.5,72.5],[25,29]]}
    br=g['brackets']
    for i,y in enumerate(br['Y_centres_mm']):
        obstacles[f'bracket{i}']=[br['outer_X_mm'],[y-5.1,y+5.1],[1.5,20.1]]
        # Conservative full approach span around each side screw, 8mm driver.
        obstacles[f'mount_tool{i}']=[[-10,30],[y-4.1,y+4.1],[10.9,19.1]]
    for f in board.GetFootprints():
        for pad in f.Pads():
            if pad.GetAttribute()!=p.PAD_ATTRIB_PTH:continue
            x,y=p.ToMM(pad.GetPosition());w,h=p.ToMM(pad.GetSize())
            r=max(w,h)/2+.1
            obstacles[f'tail/{f.GetReference()}/{pad.m_Uuid.AsString()}']=[[1.2,3.1],[x-35.75-r,x-35.75+r],[104.275-y-r,104.275-y+r]]
    for ref,(x,y,angle) in BACK_CAP_POSES.items():
        f=fps[ref]
        assert tuple(round(v,5) for v in p.ToMM(f.GetPosition()))==(x,y)
        assert (f.GetOrientationDegrees()%360)==angle
        assert f.GetFPID().GetLibItemName()=='C_1206_3216Metric'
        assert f.GetFieldText('MPN')=='CL31A226KAHNNNE' and f.GetFieldText('LCSC')=='C12891'
        assert f.GetValue()=='22u 25V X5R'
        f.BuildCourtyardCaches();bb=f.GetCourtyard(p.B_Cu).BBox()
        left,top=p.ToMM(bb.GetPosition());w,h=p.ToMM(bb.GetSize())
        assert w>=3.4 and h>=1.8 # body max already enclosed by actual courtyard
        env=[[3.1-height_mm-.15-.10,3.1],
             [left-35.75-.1,left+w-35.75+.1],
             [104.275-(top+h)-.1,104.275-top+.1]]
        assert env[0][0]>0,'neighbor/module-boundary overhang'
        assert 14<env[1][0]<env[1][1]<114.5 and 2<env[2][0]<env[2][1]<32
        for name,box in {**obstacles,**occupied}.items():assert not overlap(env,box),(ref,'back envelope collision',name)
        occupied[ref]=env
        report[ref]={'side':'B.Cu','native_pose_mm_deg':[x,y,angle],
                     'max_body_height_mm':height_mm,'solder_mm':.15,'registration_mm':.10,
                     'worst_case_module_XYZ_mm':env,'left_module_boundary_margin_mm':round(env[0][0],3)}
    return {'caps':report,'all_other_components_front':True,'B_Cu_datum_fixed_mm':3.1,
            'checked_obstacle_count':len(obstacles),'brackets_mount_tools_THT_tails_clear':True,
            'strap_keepout_XYZ_mm':obstacles['reserved_back_strap_corridor'],
            'scope':'dimensioned prototype fit; actual solder/reflow, harness/support and neighbor trial-fit remain required'}
