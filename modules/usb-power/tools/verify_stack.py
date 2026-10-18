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
from stack_geometry import physical_fingerprint, verify_ui_clearances
from routed_checks import verify_native
from hro_fit import verify as verify_hro_fit

ROOT=Path(__file__).resolve().parents[1]
def mm(v):return round(pcb.ToMM(v),5)
def xy(v):return (mm(v.GetPosition().x),mm(v.GetPosition().y))
def native(y,z):return (round(y+35.75,5),round(104.275-z,5))


def verify_reset_smt(fp,g):
    """Independent actual pad/side/net checks for the restored E-Switch part."""
    assert fp.GetFPID().GetLibItemName()=='SW_TL3340AF160QG_HandSolder', 'wrong reset footprint'
    assert fp.GetValue()=='TL3340AF160QG' and fp.GetLayer()==pcb.F_Cu
    assert xy(fp)==native(49.5,4.1) and fp.GetOrientationDegrees()==0
    pads=list(fp.Pads());assert len(pads)==7, 'reset needs five SMT pads and two pegs'
    contacts={p.GetNumber():p for p in pads if p.GetNumber() in ['1','2','3']}
    assert set(contacts)=={'1','2','3'}
    for n,y,width,net in [('1',48.275,.75,'EF_SHDN'),
                          ('2',49.5,.6,'RTN'),
                          ('3',50.725,.75,'EF_SHDN')]:
        p=contacts[n]
        assert xy(p)==native(y,5.75), 'SMT signal pad position'
        assert (mm(p.GetSize().x),mm(p.GetSize().y))==(width,2.3), 'hand-solder pad size'
        assert p.GetNetname().rsplit('/',1)[-1]==net, 'reset contact mapping (1+3 common, 2 switched)'
    anchors=[p for p in pads if p.GetNumber()=='MP']
    assert len(anchors)==2 and sorted(xy(p) for p in anchors)==[native(47.35,2.95),native(51.65,2.95)]
    assert all((mm(p.GetSize().x),mm(p.GetSize().y))==(1.9,.7) and (not p.GetNetname() or p.GetNetname().startswith('unconnected-')) for p in anchors)
    for p in list(contacts.values())+anchors:
        assert p.GetAttribute()==pcb.PAD_ATTRIB_SMD and mm(p.GetDrillSize().x)==0
        assert p.IsOnLayer(pcb.F_Cu) and p.IsOnLayer(pcb.F_Paste) and p.IsOnLayer(pcb.F_Mask)
        assert not p.IsOnLayer(pcb.B_Cu), 'SMT pads must face the component/iron side'
    pegs=[p for p in pads if p.GetNumber()=='']
    assert len(pegs)==2 and sorted(xy(p) for p in pegs)==[native(47.375,4.1),native(51.625,4.1)], 'locator positions'
    assert all(p.GetAttribute()==pcb.PAD_ATTRIB_NPTH and not p.GetNetname() and
               (mm(p.GetDrillSize().x),mm(p.GetDrillSize().y))==(.9,.9) and
               not p.IsOnLayer(pcb.F_Paste) for p in pegs), 'locator holes must not be solder pads'
    sw=g['switch']
    assert sw['mpn']=='TL3340AF160QG' and sw['LCSC']=='C2886925'
    assert sw['peg_row_YZ_mm']==[49.5,4.1] and sw['body_height_mm']==3.3
    assert sw['actuator_axis_height_mm']==1.7 and sw['actuator_tip_Z_mm']==2.05
    assert g['reset_XY_diameter_mm']==[5.8,49.5,3.2]
    assert math.isclose(g['carrier_X_mm'][1]+sw['actuator_axis_height_mm'],5.8)
    assert g['carrier_X_mm'][1]+sw['body_height_mm']+.4<g['panel_mm'][0], 'switch body exceeds 2HP'
    assert math.isclose(sw['peg_row_YZ_mm'][1]-2.05,sw['actuator_tip_Z_mm'])
    assert math.isclose(sw['actuator_tip_Z_mm']-g['panel_mm'][2],.45)
    # F.Fab = body; Dwgs.User is a future no-trace reservation, NOT copper.
    assert any(d.GetLayer()==pcb.Dwgs_User for d in fp.GraphicalItems())
    return {'smd_pads':5,'locator_NPTHs':2,'axis_X_mm':5.8,'body_top_X_mm':7.4,
            'nominal_lateral_clearance_mm':2.4,'recess_behind_panel_rear_mm':.45,
            'qualification':'nominal placement only; sample solder/fit trial pending'}


def verify(hardware=ROOT/'hardware',geometry_file=ROOT/'docs/assembly-geometry.json',routing_baseline=None,panel=ROOT/'panels/front-pcb'):
    g=json.loads(geometry_file.read_text())
    names=['usb-power','usb-power-panel']
    assert [p.stem for p in hardware.glob('*.kicad_pcb')]==['usb-power'], 'obsolete middle board still active'
    assert [p.stem for p in panel.glob('*.kicad_pcb')]==['usb-power-panel'], 'unexpected panel board'
    boards={n:pcb.LoadBoard(str((panel if n=='usb-power-panel' else hardware)/(n+'.kicad_pcb'))) for n in names}
    fps={n:{(f.GetReference() or f.GetFieldText('MechanicalID')):f for f in b.GetFootprints()} for n,b in boards.items()}
    audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
    allowed={'usb-power':{r for r in audit if not r.startswith('#')}|{'H1','H2','H3','H4'},
             'usb-power-panel':{f'H{i}' for i in range(1,7)}}
    out={'fabrication_ready':False,'boards':{}}
    out['fabrication_ready_scope']='Legacy conservative source-only non-approval flag; this checker does not evaluate bare-PCB artwork release and this false value is not an unresolved fabrication-blocker result.'
    out['bare_pcb_artwork_release_record']='jlcpcb/release-validation.json'
    out['artwork_current_for_migrated_tree']=False
    out['artwork_status']='Recovered Git snapshot; STALE until native re-export and CAM verification'
    out['assembled_product_qualified']=False
    out['physical_validation_pending']=['cable/full insertion','ABS brackets/assembled fit','bench/source-current/thermal validation']
    for n,b in boards.items():
        assert set(fps[n])==allowed[n],(n,'wrong inventory')
        if n=='usb-power-panel':assert not list(b.GetTracks()) and not list(b.Zones()),'passive panel must stay unrouted'
        assert math.isclose(pcb.ToMM(b.GetDesignSettings().GetBoardThickness()),1.6)
        assert all(d.GetLayer() not in [pcb.F_Cu,pcb.B_Cu] for d in b.GetDrawings())
        ts=list(b.GetTracks());nv=sum(t.GetClass()=='PCB_VIA' for t in ts)
        back=sum(f.GetLayer()==pcb.B_Cu for f in b.GetFootprints())
        if n=='usb-power':assert back==0,'component on B.Cu'
        out['boards'][n+'.kicad_pcb']={'footprints':len(fps[n]),'tracks':len(ts)-nv,'vias':nv,'zones':len(list(b.Zones())),'backside_components':back}
    out['routing']=verify_native(boards['usb-power'],hardware,routing_baseline)
    expected=[(14,2),(16.5,2),(16.5,10),(27.5,10),(27.5,2),(101,2),
              (101,10),(112,10),(112,2),(114.5,2),(114.5,32),(14,32)]
    edges=[d for d in boards['usb-power'].GetDrawings() if d.GetLayer()==pcb.Edge_Cuts]
    actual={frozenset(((mm(d.GetStart().x),mm(d.GetStart().y)),(mm(d.GetEnd().x),mm(d.GetEnd().y)))) for d in edges}
    wanted={frozenset((native(*a),native(*b))) for a,b in zip(expected,expected[1:]+expected[:1])}
    assert actual==wanted and len(edges)==12,'main PCB relief/outline mismatch'
    panel_edges=[d for d in boards['usb-power-panel'].GetDrawings() if d.GetLayer()==pcb.Edge_Cuts]
    assert len(panel_edges)==12
    pts=[(mm(v.x),mm(v.y)) for d in panel_edges for v in [d.GetStart(),d.GetEnd()]]
    assert min(x for x,y in pts)==50 and max(x for x,y in pts)==59.8
    assert min(y for x,y in pts)==30 and max(y for x,y in pts)==158.5
    # USB hole includes four segments and four quarter-arcs, preserved corner radius.
    ap=[p for p in pts if p[0] not in [50,59.8]]
    assert (min(x for x,y in ap),max(x for x,y in ap),min(y for x,y in ap),max(y for x,y in ap))==(53.3,58.3,58.1,68.9)
    def npth(n,ref,pos,d):
        pads=list(fps[n][ref].Pads());assert len(pads)==1
        p=pads[0];assert p.GetAttribute()==pcb.PAD_ATTRIB_NPTH
        assert xy(p)==pos and (mm(p.GetDrillSize().x),mm(p.GetDrillSize().y))==(d,d)
        assert not p.GetNetname()
    for i,y in enumerate([3,125.5],1):npth('usb-power-panel',f'H{i}',(52.42,y+30),3.2)
    for i,y in enumerate([22,106.5],1):
        npth('usb-power-panel',f'H{i+2}',(56.4,y+30),3.2)
        npth('usb-power',f'H{i}',native(y,15),3.2)
    for ref,y in [('H5',43)]:
        npth('usb-power-panel',ref,(56.1,y+30),3.6)
    npth('usb-power-panel','H6',(55.8,79.5),3.2)
    for i,y in enumerate([43.5,70.5],3):npth('usb-power',f'H{i}',native(y,27),2.5)
    usb=fps['usb-power']['J1'];assert xy(usb)==(69.25,103.475) and usb.GetOrientationDegrees()==0
    audit=json.loads((ROOT/'docs/pin-net-audit.json').read_text())
    for p in usb.Pads():
        expected_net=audit['J1'].get(p.GetNumber())
        assert p.GetNetname().rsplit('/',1)[-1]==expected_net if expected_net else (not p.GetNetname() or p.GetNetname().startswith('unconnected-'))
    tree=parse((hardware/'usb-power.kicad_pcb').read_text())
    j1=next(f for f in nodes(tree,'footprint') if any(p[1:3]==['Reference','J1'] for p in nodes(f,'property')))
    record=json.loads((ROOT/'docs/mechanical-baseline.json').read_text())
    for ref in ['J1','J7']:
        node=next(f for f in nodes(tree,'footprint') if any(p[1:3]==['Reference',ref] for p in nodes(f,'property')))
        assert physical_fingerprint(node)==record['physical'][ref], (ref,'physical pad/model pattern changed')
    assert g['mouth_axis_XYZ_mm']==[5.73,33.5,.8]
    assert math.isclose(4.1+1.63,5.73) # Intentional assembly plane translation.
    f=fps['usb-power']
    for r,pos in [('D10',native(41.73,6.37)),('SW1',native(49.5,4.1)),('J7',native(48,27))]:
        assert xy(f[r])==pos and f[r].GetLayer()==pcb.F_Cu and f[r].IsLocked()
    silk=[d for d in boards['usb-power'].GetDrawings() if d.GetLayer()==pcb.F_SilkS and isinstance(d,pcb.PCB_TEXT)]
    panel_silk=[d for d in boards['usb-power-panel'].GetDrawings() if d.GetLayer()==pcb.F_SilkS and isinstance(d,pcb.PCB_TEXT)]
    expected_leds=[('D10','+5V POWER',43,'H5')]
    assert len(g['LEDs'])==1 and g['LED']['pin_roles']=={'1':'K (cathode)','2':'A (anode)'}
    for (ref,rail,y,hole),record in zip(expected_leds,g['LEDs']):
        fp=f[ref]
        assert record=={'reference':ref,'rail':rail,'panel_hole_ref':hole,'panel_XY_diameter_mm':[6.1,y,3.6],'pad1_YZ_mm':[y-1.27,6.37]}
        assert fp.GetFPID().GetLibItemName()=='LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge'
        assert fp.GetValue()=='RED 3mm / '+rail+' / DNP' and fp.GetOrientationDegrees()==0
        assert fp.GetAttributes() & pcb.FP_EXCLUDE_FROM_POS_FILES, 'DNP LED must be excluded from JLC BOM/CPL'
        assert fp.GetAttributes() & pcb.FP_DNP, 'D10 is DNP per user: footprint retained, not fitted or purchased'
        led={p.GetNumber():p for p in fp.Pads()};assert set(led)=={'1','2'}
        for pin,py,role in [('1',y-1.27,'K'),('2',y+1.27,'A')]:
            p=led[pin]
            assert xy(p)==native(py,6.37) and p.GetNetname().rsplit('/',1)[-1]==('GND' if pin=='1' else 'LED_P_A')
            assert p.GetAttribute()==pcb.PAD_ATTRIB_PTH and (mm(p.GetDrillSize().x),mm(p.GetDrillSize().y))==(.9,.9)
            assert (mm(p.GetSize().x),mm(p.GetSize().y))==(1.8,1.8)
            assert p.IsOnLayer(pcb.F_Cu) and p.IsOnLayer(pcb.B_Cu) and not p.IsOnLayer(pcb.F_Paste)
            assert any(d.GetText()==role and xy(d)==native(py,8.8) for d in silk), 'missing polarity mark'
        assert led['1'].GetShape()==pcb.PAD_SHAPE_RECT, 'square cathode pad required'
        assert any(d.GetText()=='D10 DNP' and xy(d)==(76.5,94.4) for d in silk), 'DNP indicator callout missing'
        assert any(d.GetText()==rail and xy(d)==(54.9,round(y+33.3,5)) for d in panel_silk), 'LED panel callout alignment'
        assert math.isclose(g['carrier_X_mm'][1]+g['LED']['axis_above_PCB_mm'],6.1)
    assert all(p.GetAttribute()==pcb.PAD_ATTRIB_PTH and mm(p.GetDrillSize().x)>=.8 for p in f['J7'].Pads())
    switch_check=verify_reset_smt(f['SW1'],g)
    assert any(d.GetText()=='RETRY' and xy(d)==(81.4,96.6) for d in silk)
    assert any(d.GetText()=='RETRY' and xy(d)==(54.9,82.5) for d in panel_silk)
    for label,pos in [('1 / -12V / RED',(78,79.5)),('J7 OUTPUT ONLY',(94.75,79.5))]:
        assert any(d.GetText()==label and xy(d)==pos for d in silk), 'routed J7 legend missing'
    pinout={'1':'N12','2':'N12',**{str(i):'GND' for i in range(3,9)},'9':'P12','10':'P12','11':'P5','12':'P5',**{str(i):'' for i in range(13,17)}}
    pads={p.GetNumber():p for p in f['J7'].Pads()};assert set(pads)==set(pinout)
    for n,net in pinout.items():
        assert net==(audit['J7'][n] or '')
        assert pads[n].GetNetname().rsplit('/',1)[-1]==net if net else (not pads[n].GetNetname() or pads[n].GetNetname().startswith('unconnected-'))
        k=int(n)-1;assert xy(pads[n])==native(48+(k//2)*2.54,27+(k%2)*2.54)
    assert g['power_output']['pinout']==pinout and 'OUTPUT ONLY' in g['power_output']['warning']
    assert g['board_count']==2 and 'headers' not in g and 'spacers' not in g
    assert g['reset_XY_diameter_mm']==[5.8,49.5,3.2]
    assert 2.5-g['solder_tail_max_below_B_Cu_mm']>0
    out['clearances_mm']=verify_ui_clearances(g)
    out['HRO_fit']=verify_hro_fit(g)
    out['mechanics']={'actual_NPTH_geometry_checks':10,'LED_PTH_pad_checks':2,'LED_polarity_mark_checks':2,'manual_LED_exclusions':1,'switch_SMT_pad_checks':5,'switch_locator_NPTH_checks':2,'switch_fit':switch_check,'power_pin_checks':16,
       'M3_access':verify_access(g,expected),'carrier_depth_mm':30,'PCB_depth_behind_panel_mm':30.4,
       'main_PCB_plane_X_mm':[2.5,4.1],'port_axis_mm':[5.73,33.5,.8],
       'electrical_status':str(len(allowed['usb-power'])-4)+' active footprints; inspected routing, passive panel; not electrical/thermal qualification',
       'finished_module_depth':'unverified; cable connector not confined to 2HP board envelope'}
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hardware',type=Path,default=ROOT/'hardware')
    p.add_argument('--panel',type=Path,default=ROOT/'panels/front-pcb')
    p.add_argument('--geometry',type=Path,default=ROOT/'docs/assembly-geometry.json')
    p.add_argument('--output',type=Path)
    p.add_argument('--routing-baseline',type=Path,help='Explicit reviewed candidate contract; default remains canonical contract')
    a=p.parse_args();r=verify(a.hardware,a.geometry,a.routing_baseline,a.panel)
    if a.output:
        with a.output.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))
