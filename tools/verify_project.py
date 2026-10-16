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
from schematic_connectivity import Connectivity, pos
graph = Connectivity(root/'hardware')
pin_names = graph.named_pins()
for ref, ps in expected.items():
    for pin, want in ps.items():
        assert pin_names.get((ref, pin), 'MISSING') == want, ('schematic wire/hierarchy connectivity', ref, pin, want, pin_names.get((ref, pin)))
assert set(pin_names) == {(ref, pin) for ref, ps in expected.items() for pin in ps}, 'Inventory changed'
netlist=parse((root/'reports/big_modular.net').read_text());actual={}
for n in nodes(one(netlist,'nets'),'net'):
    # Native hierarchy adds a sheet path. All original leaf net names stay unique.
    name=one(n,'name')[1].rsplit('/',1)[-1]
    for p in nodes(n,'node'):actual[(one(p,'ref')[1],one(p,'pin')[1])]=name
# Off-board harness connectivity is checked geometrically even if an export omits it.
for pin in expected['J2']:
    if ('J2', pin) not in actual:actual[('J2', pin)] = pin_names[('J2', pin)]
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
# One intentionally remote continuation avoids running PRE_P across U4's feedback
# and ground network to U5. Retain its electrical assertion; do not call it wire-only.
remote_pair = (('D2','1'),('U5','2'))
for a,b in backbone:
    assert actual.get(a) == actual.get(b), ('interstage net changed', a, b)
    if (a,b) != remote_pair:
        assert graph.wire_connected(a,b), ('missing VISIBLE interstage wire or hierarchy path',a,b)
# Newly visible local circuits: these must NEVER regress to label-only wiring.
local_wires = [
 (('U1','9'),('R2','1')), (('U1','10'),('R3','2')),
 (('U2','3'),('R4','2')), (('U2','3'),('R5','1')),
 (('U2','5'),('R6','2')), (('U2','5'),('R7','1')),
 (('U2','11'),('R8','1')), (('U2','12'),('C3','1')),
 (('U3','2'),('C5','1')), (('U3','2'),('C7','1')),
 (('U3','8'),('R11','2')), (('U3','6'),('L1','2')),
 (('U4','22'),('R12','2')), (('U4','22'),('R13','1')), (('U4','22'),('C10','2')),
 (('U4','16'),('R14','2')), (('U4','16'),('R15','1')), (('U4','16'),('C11','2')),
 (('U4','17'),('R15','2')), (('U4','17'),('C12','1')),
 (('U4','18'),('C14','1')), (('U4','21'),('C13','1')),
 (('U4','4'),('R16','2')), (('U4','4'),('C15','1')),
 (('U5','6'),('L4','2')), (('U5','5'),('R17','2')), (('U5','5'),('R18','1')),
]
for u,cin,cout,nr,ff,rt,rb,rev,clamp,bleed in [
 ('U6','C21','C22','C23','C24','R19','R20','D4','D5','R25'),
 ('U7','C25','C26','C27','C28','R21','R22','D6','D7','R26'),
 ('U8','C29','C30','C31','C32','R23','R24','D8','D9','R27')]:
    local_wires.extend([((u,'8'),(cin,'1')), ((u,'1'),(cout,'1')),
        ((u,'6'),(nr,'1')), ((u,'2'),(ff,'2')), ((u,'2'),(rt,'2')),
        ((u,'2'),(rb,'1')), ((u,'1'),(bleed,'1')),
        ((u,'1'),(clamp,'2' if u=='U7' else '1')),
        ((u,'8'),(rev,'2' if u=='U7' else '1')),
        ((u,'1'),(rev,'1' if u=='U7' else '2'))])
for a,b in local_wires:assert graph.wire_connected(a,b), ('local branch reverted to labels', a,b)
assert pin_names[('U2','8')] != pin_names[('U2','9')], 'RTN must stay separate from GND'
assert pin_names[('U4','17')] != pin_names[('U4','19')], 'BI_REF must stay separate from GND'

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
assert any(l.split()[-1]=='4' for l in info.splitlines() if l.startswith('Pages:'))
result={'schematic_sheets':4,'functional_subsheets':3,'pdf_pages':4,'BOM_components':len(bom),'connected_symbol_pins_verified':checked,
 'off_board_J2_connected_pins_checked_in_schematic':12,'other_connected_pins_verified_against_KiCad_netlist':checked-12,
 'independent_pin_net_spot_checks':sum(map(len,reviewed.values())), 'visible_wire_or_hierarchy_interstage_checks':len(backbone)-1, 'named_remote_interstage_checks':1, 'visible_local_branch_checks':len(local_wires), 'hierarchy_port_links':len(graph.hierarchy_links),
 'voltage_PG_RUN_logic_cases':len(cases),'audit_limit':'Connectivity/threshold regression only, not PD proof, analog simulation, physical fit or operation. Generated audit is not independent; the hardcoded spot checks are.', 'boards':{}}
from verify_stack import verify as verify_stack
stack = verify_stack(root/'hardware', root/'docs/assembly-geometry.json')
result['boards'] = stack['boards']
result['mechanics'] = stack['mechanics']
result['fabrication_ready'] = False
(root/'reports/geometry-and-net-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {checked} connected pins; 65 independent spot checks; {len(backbone)-1} wired/hierarchical interstage paths + 1 named continuation; {len(local_wires)} local wire paths; 28 gate cases; 10 mechanical NPTH + 5 switch SMT pad + 2 locator NPTH + 16 power pin + 2 M3 bracket checks; 2 unrouted boards. NOT fabrication approval.')
