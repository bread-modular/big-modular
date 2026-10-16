#!/usr/bin/env python3
"""Independent native A4.2 fit/placement regression. No manufacturing approval."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import pcbnew as pcb
from m3_fit import verify_access
from sexp import parse,nodes

ROOT=Path(__file__).resolve().parents[1]
def mm(v):return round(pcb.ToMM(v),5)
def xy(v):return (mm(v.GetPosition().x),mm(v.GetPosition().y))
def native(y,z):return (round(y+35.75,5),round(104.275-z,5))


def verify_reset_smt(fp,g):
    """Independent actual pad/side/net checks for the restored E-Switch part."""
    assert fp.GetFPID().GetLibItemName()=='SW_TL3340AF160QG_HandSolder', 'wrong reset footprint'
    assert fp.GetValue()=='TL3340AF160QG' and fp.GetLayer()==pcb.F_Cu
    assert xy(fp)==native(91,4.1) and fp.GetOrientationDegrees()==0
    pads=list(fp.Pads());assert len(pads)==7, 'reset needs five SMT pads and two pegs'
    contacts={p.GetNumber():p for p in pads if p.GetNumber() in ['1','2','3']}
    assert set(contacts)=={'1','2','3'}
    for n,y,width,net in [('1',89.775,.75,'RESET_A_PENDING'),
                          ('2',91,.6,'RESET_B_PENDING'),
                          ('3',92.225,.75,'RESET_A_PENDING')]:
        p=contacts[n]
        assert xy(p)==native(y,5.75), 'SMT signal pad position'
        assert (mm(p.GetSize().x),mm(p.GetSize().y))==(width,2.3), 'hand-solder pad size'
        assert p.GetNetname()==net, 'reset contact mapping (1+3 common, 2 switched)'
    anchors=[p for p in pads if p.GetNumber()=='MP']
    assert len(anchors)==2 and sorted(xy(p) for p in anchors)==[native(88.85,2.95),native(93.15,2.95)]
    assert all((mm(p.GetSize().x),mm(p.GetSize().y))==(1.9,.7) and not p.GetNetname() for p in anchors)
    for p in list(contacts.values())+anchors:
        assert p.GetAttribute()==pcb.PAD_ATTRIB_SMD and mm(p.GetDrillSize().x)==0
        assert p.IsOnLayer(pcb.F_Cu) and p.IsOnLayer(pcb.F_Paste) and p.IsOnLayer(pcb.F_Mask)
        assert not p.IsOnLayer(pcb.B_Cu), 'SMT pads must face the component/iron side'
    pegs=[p for p in pads if p.GetNumber()=='']
    assert len(pegs)==2 and sorted(xy(p) for p in pegs)==[native(88.875,4.1),native(93.125,4.1)], 'locator positions'
    assert all(p.GetAttribute()==pcb.PAD_ATTRIB_NPTH and not p.GetNetname() and
               (mm(p.GetDrillSize().x),mm(p.GetDrillSize().y))==(.9,.9) and
               not p.IsOnLayer(pcb.F_Paste) for p in pegs), 'locator holes must not be solder pads'
    sw=g['switch']
    assert sw['mpn']=='TL3340AF160QG' and sw['LCSC']=='C2886925'
    assert sw['peg_row_YZ_mm']==[91,4.1] and sw['body_height_mm']==3.3
    assert sw['actuator_axis_height_mm']==1.7 and sw['actuator_tip_Z_mm']==2.05
    assert g['reset_XY_diameter_mm']==[6.4,91,3.2]
    assert math.isclose(g['carrier_X_mm'][1]+sw['actuator_axis_height_mm'],6.4)
    assert g['carrier_X_mm'][1]+sw['body_height_mm']+.4<g['panel_mm'][0], 'switch body exceeds 2HP'
    assert math.isclose(sw['peg_row_YZ_mm'][1]-2.05,sw['actuator_tip_Z_mm'])
    assert math.isclose(sw['actuator_tip_Z_mm']-g['panel_mm'][2],.45)
    # F.Fab = body; Dwgs.User is a future no-trace reservation, NOT copper.
    assert any(d.GetLayer()==pcb.Dwgs_User for d in fp.GraphicalItems())
    return {'smd_pads':5,'locator_NPTHs':2,'axis_X_mm':6.4,'body_top_X_mm':8.0,
            'nominal_lateral_clearance_mm':1.8,'recess_behind_panel_rear_mm':.45,
            'qualification':'nominal placement only; sample solder/fit trial pending'}


def verify(hardware=ROOT/'hardware',geometry_file=ROOT/'docs/assembly-geometry.json'):
    g=json.loads(geometry_file.read_text())
    names=['big_modular','front_panel']
    assert sorted(p.stem for p in hardware.glob('*.kicad_pcb'))==sorted(names), 'obsolete middle board still active'
    boards={n:pcb.LoadBoard(str(hardware/(n+'.kicad_pcb'))) for n in names}
    fps={n:{f.GetReference():f for f in b.GetFootprints()} for n,b in boards.items()}
    allowed={'big_modular':{'J1','D10','R32','SW1','J7','H1','H2','H3','H4'},
             'front_panel':{f'H{i}' for i in range(1,7)}}
    out={'fabrication_ready':False,'boards':{}}
    for n,b in boards.items():
        assert set(fps[n])==allowed[n],(n,'wrong inventory')
        assert not list(b.GetTracks()) and not list(b.Zones()),'routing forbidden'
        assert math.isclose(pcb.ToMM(b.GetDesignSettings().GetBoardThickness()),1.6)
        assert all(d.GetLayer() not in [pcb.F_Cu,pcb.B_Cu] for d in b.GetDrawings())
        out['boards'][n+'.kicad_pcb']={'footprints':len(fps[n]),'tracks':0,'vias':0,'zones':0}
    expected=[(14,2),(16.5,2),(16.5,10),(27.5,10),(27.5,2),(101,2),
              (101,10),(112,10),(112,2),(114.5,2),(114.5,32),(14,32)]
    edges=[d for d in boards['big_modular'].GetDrawings() if d.GetLayer()==pcb.Edge_Cuts]
    actual={frozenset(((mm(d.GetStart().x),mm(d.GetStart().y)),(mm(d.GetEnd().x),mm(d.GetEnd().y)))) for d in edges}
    wanted={frozenset((native(*a),native(*b))) for a,b in zip(expected,expected[1:]+expected[:1])}
    assert actual==wanted and len(edges)==12,'main PCB relief/outline mismatch'
    panel_edges=[d for d in boards['front_panel'].GetDrawings() if d.GetLayer()==pcb.Edge_Cuts]
    assert len(panel_edges)==12
    pts=[(mm(v.x),mm(v.y)) for d in panel_edges for v in [d.GetStart(),d.GetEnd()]]
    assert min(x for x,y in pts)==50 and max(x for x,y in pts)==59.8
    assert min(y for x,y in pts)==30 and max(y for x,y in pts)==158.5
    # USB hole includes four segments and four quarter-arcs, preserved corner radius.
    ap=[p for p in pts if p[0] not in [50,59.8]]
    assert (min(x for x,y in ap),max(x for x,y in ap),min(y for x,y in ap),max(y for x,y in ap))==(54.255,58.455,89.35,99.15)
    def npth(n,ref,pos,d):
        pads=list(fps[n][ref].Pads());assert len(pads)==1
        p=pads[0];assert p.GetAttribute()==pcb.PAD_ATTRIB_NPTH
        assert xy(p)==pos and (mm(p.GetDrillSize().x),mm(p.GetDrillSize().y))==(d,d)
        assert not p.GetNetname()
    for i,y in enumerate([3,125.5],1):npth('front_panel',f'H{i}',(52.42,y+30),3.2)
    for i,y in enumerate([22,106.5],1):
        npth('front_panel',f'H{i+2}',(56.4,y+30),3.2)
        npth('big_modular',f'H{i}',native(y,15),3.2)
    npth('front_panel','H5',(56.7,68),3.6)
    npth('front_panel','H6',(56.4,121),3.2)
    for i,y in enumerate([43.5,70.5],3):npth('big_modular',f'H{i}',native(y,27),2.5)
    usb=fps['big_modular']['J1'];assert xy(usb)==(100,99.8) and usb.GetOrientationDegrees()==0
    audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
    for p in usb.Pads():assert p.GetNetname()==(audit['J1'].get(p.GetNumber()) or '')
    tree=parse((hardware/'big_modular.kicad_pcb').read_text())
    j1=next(f for f in nodes(tree,'footprint') if any(p[1:3]==['Reference','J1'] for p in nodes(f,'property')))
    record=json.loads((ROOT/'reports/stack-source-preservation.json').read_text())
    assert hashlib.sha256(json.dumps(j1).encode()).hexdigest()==record['J1_native_AST_sha256'],'native USB changed'
    assert g['mouth_axis_XYZ_mm']==[6.43,64.25,.8]
    assert math.isclose(4.7+1.73,6.43) # Intentional assembly plane translation.
    f=fps['big_modular']
    for r,pos in [('D10',native(36.73,6.37)),('R32',native(43,14)),('SW1',native(91,4.1)),('J7',native(48,27))]:
        assert xy(f[r])==pos and f[r].GetLayer()==pcb.F_Cu and f[r].IsLocked()
    assert f['D10'].GetFPID().GetLibItemName()=='LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge'
    for r,nets in {'D10':{'1':'UI_GND_PENDING','2':'LED_A_PENDING'},
                   'R32':{'1':'UI_P5_PENDING','2':'LED_A_PENDING'},
                   'SW1':{'1':'RESET_A_PENDING','2':'RESET_B_PENDING','3':'RESET_A_PENDING','MP':'','':''}}.items():
        for p in f[r].Pads():assert p.GetNetname()==nets[p.GetNumber()]
    for r in ['D10','R32','J7']:
        assert all(p.GetAttribute()==pcb.PAD_ATTRIB_PTH and mm(p.GetDrillSize().x)>=.8 for p in f[r].Pads())
    led={p.GetNumber():p for p in f['D10'].Pads()}
    assert xy(led['2'])==native(39.27,6.37)
    switch_check=verify_reset_smt(f['SW1'],g)
    pinout={'1':'N12','2':'N12',**{str(i):'GND' for i in range(3,9)},'9':'P12','10':'P12','11':'P5','12':'P5',**{str(i):'' for i in range(13,17)}}
    pads={p.GetNumber():p for p in f['J7'].Pads()};assert set(pads)==set(pinout)
    for n,net in pinout.items():
        assert pads[n].GetNetname()==net==(audit['J2'][n] or '')
        k=int(n)-1;assert xy(pads[n])==native(48+(k//2)*2.54,27+(k%2)*2.54)
    assert g['power_output']['pinout']==pinout and 'OUTPUT ONLY' in g['power_output']['warning']
    assert g['board_count']==2 and 'headers' not in g and 'spacers' not in g
    assert g['led_XY_diameter_mm']==[6.7,38,3.6] and g['reset_XY_diameter_mm']==[6.4,91,3.2]
    assert 3.1-g['solder_tail_max_below_B_Cu_mm']>0
    out['mechanics']={'actual_NPTH_geometry_checks':10,'switch_SMT_pad_checks':5,'switch_locator_NPTH_checks':2,'switch_fit':switch_check,'power_pin_checks':16,
       'M3_access':verify_access(g,expected),'carrier_depth_mm':30,'PCB_depth_behind_panel_mm':30.4,
       'main_PCB_plane_X_mm':[3.1,4.7],'port_axis_mm':[6.43,64.25,.8],
       'electrical_status':'No routing; J7 landing not integrated into schematic; J2 remains on flying lead; D10/R32/SW1 isolated',
       'finished_module_depth':'unverified; cable connector not confined to 2HP board envelope'}
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hardware',type=Path,default=ROOT/'hardware')
    p.add_argument('--geometry',type=Path,default=ROOT/'docs/assembly-geometry.json')
    p.add_argument('--output',type=Path)
    a=p.parse_args();r=verify(a.hardware,a.geometry)
    if a.output:
        with a.output.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))
