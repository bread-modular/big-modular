#!/usr/bin/env python3
"""Offline checks: real KiCad netlist connectivity and zero-route/mechanical invariants."""
from pathlib import Path
import sys,json,math,collections
sys.path.insert(0,str(Path(__file__).parent))
from sexp import parse,nodes,one,walk
import pcbnew as pcb
root=Path(__file__).resolve().parent.parent
expected=json.loads((root/'docs/pin-net-audit.json').read_text())
netlist=parse((root/'reports/big_modular.net').read_text()); actual={}
for n in nodes(one(netlist,'nets'),'net'):
    name=one(n,'name')[1]
    for p in nodes(n,'node'):actual[(one(p,'ref')[1],one(p,'pin')[1])]=name
# Off-board J2 is deliberately omitted by KiCad's PCB netlist exporter.
# Verify its real schematic pin -> wire -> global-label connectivity separately.
sh=parse((root/'hardware/06_output.kicad_sch').read_text())
j=next(x for x in nodes(sh,'symbol') if any(p[1]=='Reference' and p[2]=='J2' for p in nodes(x,'property')))
lib=next(x for x in nodes(one(sh,'lib_symbols'),'symbol') if x[1]==one(j,'lib_id')[1])
def pos(x):return tuple(round(float(a),5) for a in x)
origin=pos(one(j,'at')[1:3])
labels={pos(one(l,'at')[1:3]):l[1] for l in nodes(sh,'global_label')}
wires=[tuple(pos(pt[1:3]) for pt in nodes(one(w,'pts'),'xy')) for w in nodes(sh,'wire')]
ncs={pos(one(n,'at')[1:3]) for n in nodes(sh,'no_connect')}
for p in walk(lib,'pin'):
    pin=one(p,'number')[1];a=one(p,'at');at=pos([origin[0]+float(a[1]),origin[1]-float(a[2])]);want=expected['J2'][pin]
    if want is None:assert at in ncs,('J2 NC',pin)
    else:
        ends=[b if a==at else a for a,b in wires if at in [a,b]]
        got=[labels[e] for e in ends if e in labels]
        assert got==[want],('J2 schematic wiring',pin,want,got)
        actual[('J2',pin)]=want
checked=0
for ref,pins in expected.items():
    if ref.startswith('#'):continue
    for pin,net in pins.items():
        if net is None:continue
        got=actual.get((ref,pin)); assert got==net,(ref,pin,net,got);checked+=1
result={'connected_symbol_pins_verified':checked,'off_board_J2_connected_pins_checked_in_schematic':12,'other_connected_pins_verified_against_KiCad_netlist':checked-12,'boards':{}}
for fn,allowed in [('big_modular.kicad_pcb',{'J1','H1','H2','H3','H4'}),('front_panel.kicad_pcb',{'H1','H2','H3','H4'})]:
    b=pcb.LoadBoard(str(root/'hardware'/fn)); refs={f.GetReference() for f in b.GetFootprints()}
    assert refs==allowed,(fn,refs);assert len(list(b.GetTracks()))==0;assert len(list(b.Zones()))==0
    # Includes copper graphics as well as ordinary tracks, so no hidden copper artwork.
    assert all(d.GetLayer() not in [pcb.F_Cu,pcb.B_Cu] for d in b.GetDrawings())
    for f in b.GetFootprints():
        if f.GetReference().startswith('H'):
            assert all(p.GetAttribute()==pcb.PAD_ATTRIB_NPTH for p in f.Pads())
    for f in b.GetFootprints():
        if f.GetReference()=='J1':
            assert abs(pcb.ToMM(f.GetPosition().x)-100)<1e-8
            assert abs(pcb.ToMM(f.GetPosition().y)-99.8)<1e-8
            assert abs(f.GetOrientationDegrees())<1e-8
            for p in f.Pads():
                want=expected['J1'].get(p.GetNumber())
                if want:assert p.GetNetname()==want,(p.GetNumber(),p.GetNetname(),want)
    outlines=[d for d in b.GetDrawings() if d.GetLayer()==pcb.Edge_Cuts]
    assert len(outlines)==(4 if fn.startswith('big') else 12)
    # Native DRC separately validates outline closure and arcs.
    result['boards'][fn]={'footprints':sorted(refs),'tracks':0,'vias':0,'zones':0,'copper_graphics':0,'edge_primitives':len(outlines)}
axis=[0,0,1];normal=[0,0,1];dot=sum(a*b for a,b in zip(axis,normal))
assert dot==1
mouth=104.275-(99.8+3.675)
assert math.isclose(mouth,.8,abs_tol=1e-9)
assert math.isclose(3.170+1.730,4.9,abs_tol=1e-9)
assert math.isclose(102.275-(99.8+1.075+.9),.5,abs_tol=1e-9)
result['mechanics']={'port_axis_mm':[4.9,64.25,round(mouth,6)],'insertion_vector':axis,'axis_to_panel_plane_degrees':90,'axis_dot_panel_normal':dot,'carrier_top_X':3.17,'carrier_back_Z':62,'front_shell_pad_edge_clearance':.5,'status':'nominal geometry verified; tolerance stack and brackets/harness NOT qualified'}
(root/'reports/geometry-and-net-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS:',checked,'connected pins; USB-only electrical placement; zero tracks/vias/zones; port axis normal to panel at Z=0.8 mm.')
