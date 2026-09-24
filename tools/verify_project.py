#!/usr/bin/env python3
"""Independent connectivity/geometry regression checks, NOT operational validation."""
from pathlib import Path
from collections import defaultdict
import csv, itertools, json, math, subprocess, sys
sys.path.insert(0,str(Path(__file__).parent))
from sexp import parse,nodes,one,walk
import pcbnew as pcb
root=Path(__file__).resolve().parent.parent
expected=json.loads((root/'docs/pin-net-audit.json').read_text())
with (root/'BOM.csv').open(newline='') as f:bom=list(csv.DictReader(f))
assert 'D1' not in expected
assert all(p['Reference']!='D1' and 'SMBJ12CA' not in (p['Value']+' '+p['MPN']) for p in bom)
assert len(list((root/'hardware').glob('*.kicad_sch')))==1
sh=parse((root/'hardware/big_modular.kicad_sch').read_text())
assert not nodes(sh,'sheet')
assert not nodes(sh,'global_label')
netlist=parse((root/'reports/big_modular.net').read_text());actual={}
for n in nodes(one(netlist,'nets'),'net'):
    name=one(n,'name')[1].lstrip('/')
    for p in nodes(n,'node'):actual[(one(p,'ref')[1],one(p,'pin')[1])]=name
# Independently traverse real schematic segments (without relying on generated intended nets).
# A crossing without a shared endpoint/junction is not connected.
pos=lambda p:tuple(round(float(x),5) for x in p)
libs={s[1]:s for s in nodes(one(sh,'lib_symbols'),'symbol')}
wires=[tuple(pos(p[1:3]) for p in nodes(one(w,'pts'),'xy')) for w in nodes(sh,'wire')]
labels={pos(one(l,'at')[1:3]):l[1] for l in nodes(sh,'label')}
junctions={pos(one(j,'at')[1:3]) for j in nodes(sh,'junction')}
ncs={pos(one(n,'at')[1:3]) for n in nodes(sh,'no_connect')}
pins={}
for s in nodes(sh,'symbol'):
    ref=next(p[2] for p in nodes(s,'property') if p[1]=='Reference')
    at=one(s,'at');x,y=map(float,at[1:3]);angle=math.radians(float(at[3]));co=round(math.cos(angle));si=round(math.sin(angle))
    for p in walk(libs[one(s,'lib_id')[1]],'pin'):
        n=one(p,'number')[1];a=one(p,'at');px,py=map(float,a[1:3])
        pins[(ref,n)]=pos([x+px*co-py*si,y-px*si-py*co])
points={p for w in wires for p in w}|set(labels)|junctions|set(pins.values())
graph={p:p for p in points}
def find(p):
    while graph[p]!=p:graph[p]=graph[graph[p]];p=graph[p]
    return p
def join(a,b):graph[find(a)]=find(b)
for a,b in wires:
    axis=0 if a[1]==b[1] else 1
    for p in points:
        if p[1-axis]==a[1-axis] and min(a[axis],b[axis])<=p[axis]<=max(a[axis],b[axis]):join(a,p)
connected_labels=defaultdict(set)
for p,n in labels.items():connected_labels[find(p)].add(n)
assert all(len(n)==1 for n in connected_labels.values()),('shorted names',[n for n in connected_labels.values() if len(n)>1])
for key,p in pins.items():
    ref,n=key;want=expected[ref][n]
    if want is None:assert p in ncs,('missing NC',key)
    else:
        names=connected_labels[find(p)]
        assert names=={want},('schematic pin->wire->label',key,want,names)
        if ref=='J2':actual[key]=want
# Explicitly verify interstage wires without using labels at all.
backbone=[(('J1','A4'),('F1','1')),(('F1','2'),('U2','1')),
          (('U2','15'),('U3','2')),(('U3','7'),('L1','1')),
          (('L1','2'),('U4','5')),(('L2','2'),('D2','2')),
          (('D2','1'),('U6','8')),(('D2','1'),('U5','2')),
          (('U4','13'),('D3','1')),(('D3','2'),('U7','8')),
          (('U5','7'),('L4','1')),(('L4','2'),('U8','8')),
          (('U6','1'),('J2','9')),(('U7','1'),('J2','1')),(('U8','1'),('J2','11')),
          (('U1','10'),('R28','1')),(('R28','2'),('Q1','1')),
          (('Q1','3'),('JP1','1')),(('JP1','2'),('U2','7')),
          (('U3','8'),('U4','8')),(('U3','8'),('U4','10'))]
for a,b in backbone:assert find(pins[a])==find(pins[b]),('missing VISIBLE interstage wire',a,b)
# Deliberately hand-authored spot checks separate from the generator and its audit file.
reviewed={
 'J1':{'A4':'VBUS_RAW','A5':'CC1','B5':'CC2','SH':'GND'},
 'U1':{'1':'PD_VDD','6':'CC2','7':'CC1','9':'PD_CFG','10':'PD_PG_N','11':'GND'},
 'Q1':{'1':'PG_BASE','2':'PD_VDD','3':'PG_PERMIT'},
 'JP1':{'1':'PG_PERMIT','2':'EF_ENABLE'},
 'R4':{'1':'VBUS_FUSED','2':'UV_EN'},'R5':{'1':'UV_EN','2':'RTN'},
 'R28':{'1':'PD_PG_N','2':'PG_BASE'},'R30':{'1':'EF_ENABLE','2':'RTN'},
 'U2':{'1':'VBUS_FUSED','2':'VBUS_FUSED','3':'UV_EN','5':'OV_SET','7':'EF_ENABLE','8':'RTN','9':'GND','11':'ILIM','15':'VPROT','16':'VPROT','17':'RTN'},
 'U3':{'2':'VPROT','3':'VPROT','5':'MID_FB','6':'V4','7':'MID_SW','8':'MID_GOOD'},
 'U4':{'1':'BOOST_SW','5':'V4','8':'MID_GOOD','10':'MID_GOOD','13':'INV_SW','15':'PRE_N','16':'NEG_FB','17':'BI_REF','22':'POS_FB','23':'PRE_P'},
 'D2':{'1':'PRE_P','2':'BOOST_SW'},'D3':{'1':'INV_SW','2':'PRE_N'},
 'U7':{'1':'N12','2':'N12_FB','4':'GND','5':'PRE_N','8':'PRE_N'},
 'J2':{'1':'N12','2':'N12','9':'P12','10':'P12','11':'P5','12':'P5'},
}
for ref,ps in reviewed.items():
    for pin,want in ps.items():assert actual.get((ref,pin))==want,('independent spot check',ref,pin,want,actual.get((ref,pin)))
checked=0
for ref,ps in expected.items():
    if ref.startswith('#'):continue
    for pin,net in ps.items():
        if net is not None:
            assert actual.get((ref,pin))==net,(ref,pin,net,actual.get((ref,pin)));checked+=1
# Separate threshold envelope, including 1% resistors and +/-100nA input bias from TI table 7.5.
byref={b['Reference']:b for b in bom}
for ref,value in [('R4','562k 1%'),('R5','100k 1%'),('R6','806k 1%'),('R7','100k 1%'),('R30','10k 1%')]:assert byref[ref]['Value']==value

def bounds(rt,threshold):
    vals=[v*(1+(rt*a)/(100e3*b))+i*rt*a for v,a,b,i in itertools.product(threshold,[.99,1.01],[.99,1.01],[-100e-9,100e-9])]
    return [round(min(vals),4),round(max(vals),4)]
uv_r=bounds(562e3,[1.175,1.225]);uv_f=bounds(562e3,[1.08,1.125]);ov_r=bounds(806e3,[1.17,1.225]);ov_f=bounds(806e3,[1.085,1.125])
assert uv_f[0]>5.5 and uv_r[1]<8.55 and ov_r[1]<15 and ov_f[0]>9.45
assert 10e-6*10e3*1.01<.55
# Voltage/PG/RUN logic only: intentionally NOT a PD protocol simulation.
cases=[]
for v,pg,run in itertools.product([0,5,5.5,9,15,20,21],[False,True],[False,True]):
    enabled=7.8778<v<10.7814 and pg and run
    if v!=9 or not pg or not run:assert not enabled
    cases.append({'VBUS':v,'PG_low':pg,'RUN_closed':run,'nominal_gate_enable':enabled})
(root/'reports/pd-gate-check.json').write_text(json.dumps({'UV_rising_V':uv_r,'UV_falling_V':uv_f,'OV_rising_V':ov_r,'OV_falling_V':ov_f,'logic_cases':cases,'limitation':'Voltage/PG/RUN structural checks only. CH224K explicit 9V PDO/current status, dynamic timing and leakage remain UNPROVEN; no fabrication.'},indent=2)+'\n')
info=subprocess.check_output(['pdfinfo',str(root/'docs/schematic.pdf')],text=True)
assert any(l.split()[-1]=='1' for l in info.splitlines() if l.startswith('Pages:'))
result={'schematic_sheets':1,'pdf_pages':1,'BOM_components':len(bom),'connected_symbol_pins_verified':checked,
 'off_board_J2_connected_pins_checked_in_schematic':12,'other_connected_pins_verified_against_KiCad_netlist':checked-12,
 'independent_pin_net_spot_checks':sum(map(len,reviewed.values())), 'visible_wire_only_interstage_checks':len(backbone),
 'voltage_PG_RUN_logic_cases':len(cases),'audit_limit':'Connectivity/threshold regression only, not PD proof, analog simulation, physical fit or operation. Generated audit is not independent; the hardcoded spot checks are.', 'boards':{}}
boards={}
for fn,allowed in [('big_modular.kicad_pcb',{'J1','H1','H2','H3','H4'}),('front_panel.kicad_pcb',{'H1','H2','H3','H4'})]:
    b=pcb.LoadBoard(str(root/'hardware'/fn));boards[fn]=b
    refs={f.GetReference() for f in b.GetFootprints()};assert refs==allowed
    assert len(list(b.GetTracks()))==0 and len(list(b.Zones()))==0
    assert all(d.GetLayer() not in [pcb.F_Cu,pcb.B_Cu] for d in b.GetDrawings())
    for f in b.GetFootprints():
        if f.GetReference().startswith('H'):assert all(p.GetAttribute()==pcb.PAD_ATTRIB_NPTH for p in f.Pads())
        if f.GetReference()=='J1':
            assert pos([pcb.ToMM(f.GetPosition().x),pcb.ToMM(f.GetPosition().y)])==(100,99.8)
            assert f.GetOrientationDegrees()==0
            for p in f.Pads():
                want=expected['J1'].get(p.GetNumber())
                if want:assert p.GetNetname()==want
    edges=[d for d in b.GetDrawings() if d.GetLayer()==pcb.Edge_Cuts]
    assert len(edges)==(4 if fn.startswith('big') else 12)
    result['boards'][fn]={'footprints':sorted(refs),'tracks':0,'vias':0,'zones':0,'copper_graphics':0,'edge_primitives':len(edges)}
# Check ACTUAL board holes, not just dimensions asserted in a document.
geom=json.loads((root/'docs/assembly-geometry.json').read_text())
def hole(b,ref):
    f=next(f for f in b.GetFootprints() if f.GetReference()==ref);p=next(iter(f.Pads()))
    return tuple(round(pcb.ToMM(v),5) for v in (f.GetPosition().x,f.GetPosition().y,p.GetDrillSize().x,p.GetDrillSize().y))
for i,(Y,Z) in enumerate(geom['carrier_holes_YZ_mm'],1):
    assert hole(boards['big_modular.kicad_pcb'],'H'+str(i))==(Y+35.75,round(104.275-Z,5),2.2,2.2)
for i,(X,Y,dx,dy) in enumerate(geom['rail_slots_mm'],1):
    assert hole(boards['front_panel.kicad_pcb'],'H'+str(i))==(X+50,Y+30,dx,dy)
for i,(X,Y,d) in enumerate(geom['panel_bracket_holes_mm'],3):
    assert hole(boards['front_panel.kicad_pcb'],'H'+str(i))==(X+50,Y+30,d,d)
assert math.isclose(104.275-(99.8+3.675),.8,abs_tol=1e-8)
assert math.isclose(3.17+1.73,4.9,abs_tol=1e-8)
assert math.isclose(102.275-(99.8+1.075+.9),.5,abs_tol=1e-8)
assert 1.57-1.2>0 and 8.97<9.8
assert math.isclose(4-1.6,geom['interposers']['nominal_engagement_mm'])
assert 1.6+2.8 < 6-1  # Blind bore ends do not intersect perpendicular M2 major-diameter bore.
assert 9.8-7.5-1.6 > 0  # 0.7 mm FR4 web: geometry fits, strength NOT qualified.
assert 7.5+3>9.8  # Standard 6 mm screw head overhangs; explicit mechanical blocker.
# Outer edge extents from the actual Edge.Cuts, ignoring panel aperture for minima/maxima.
for fn,w,h in [('big_modular.kicad_pcb',100.5,60),('front_panel.kicad_pcb',9.8,128.5)]:
    points=[]
    for d in boards[fn].GetDrawings():
        if d.GetLayer()==pcb.Edge_Cuts:
            points.extend([(pcb.ToMM(v.x),pcb.ToMM(v.y)) for v in [d.GetStart(),d.GetEnd()]])
    assert math.isclose(max(p[0] for p in points)-min(p[0] for p in points),w,abs_tol=1e-5)
    assert math.isclose(max(p[1] for p in points)-min(p[1] for p in points),h,abs_tol=1e-5)
result['mechanics']={'actual_NPTH_geometry_checks':8,'port_axis_mm':[4.9,64.25,.8],'insertion_vector':[0,0,1],'axis_to_panel_plane_degrees':90,'front_shell_pad_edge_clearance_mm':.5,'interposer_thread_engagement_mm':2.4,'rail_mount':'Doepfer x=7.5, diameter 3.2; standard head overhang/0.7mm FR4 web are blockers','status':'nominal proposal; strength/tolerances/plug/cable/screws unqualified'}
(root/'reports/geometry-and-net-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {checked} connected pins; 65 independent spot checks; 21 visible interstage wires; 28 gate logic cases; 8 NPTH geometry checks; 1 sheet/page; zero routing.')
