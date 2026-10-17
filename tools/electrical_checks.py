"""Independent reviewed pin-role checks; not derived from generator inventory."""
import csv,json
from pathlib import Path
from schematic_connectivity import Connectivity
from sexp import nodes,one,parse,Atom,walk
import math
REVIEWED={
 'U1':{'1':'VIN9','8':'VIN9','11':'GND','2':None,'3':None,'4':'PD_D_SHORT','5':'PD_D_SHORT','6':'CC2','7':'CC1','9':'PD_CFG','10':None},
 'U2':{'1':'VIN9','2':'VIN9','3':'UV_EN','4':None,'5':'OV_SET','6':'EF_MODE','7':'EF_SHDN','8':'RTN','9':'GND','10':None,'11':'ILIM','12':'SLEW','13':None,'14':None,'15':'VPROT','16':'VPROT','17':'RTN'},
 'U3':{'1':'GND','2':'MID_SW','3':'VPROT','4':'MID_FB','5':None,'6':'MID_BOOT'},
 'U5':{'1':'GND','2':'FIVE_SW','3':'VPROT','4':'FIVE_FB','5':None,'6':'FIVE_BOOT'},
 'U4':{'1':'BOOST_SW','24':'BOOST_SW','2':'GND','3':'GND','4':'ANA_MID','5':'MID','6':'MID','7':None,'8':'BI_EN','9':'GND','10':'BI_EN','11':'GND','12':None,'13':'INV_SW','14':'INV_SW','15':'NRAW','16':'NEG_FB','17':'BI_REF','18':'COMP_N','19':'GND','20':None,'21':'COMP_P','22':'POS_FB','23':'PRAW','25':'GND'},
 'SW1':{'1':'EF_SHDN','3':'EF_SHDN','2':'RTN','MP':None},
 'D10':{'1':'GND','2':'LED_P_A'},'R32':{'1':'P5','2':'LED_P_A'},
 'C35':{'1':'MID_BOOT','2':'MID_SW'},'C36':{'1':'FIVE_BOOT','2':'FIVE_SW'},
 'R8':{'1':'ILIM','2':'RTN'},'R36':{'1':'EF_MODE','2':'RTN'},
 'R4':{'1':'VIN9','2':'UV_EN'},'R5':{'1':'UV_EN','2':'RTN'},'R6':{'1':'VIN9','2':'OV_SET'},'R7':{'1':'OV_SET','2':'RTN'},
 'R14':{'1':'NRAW','2':'NEG_DIV'},'R60':{'1':'NEG_DIV','2':'NEG_FB'},'R15':{'1':'NEG_FB','2':'NEG_REF_DIV'},'R76':{'1':'NEG_REF_DIV','2':'BI_REF'},'R12':{'1':'PRAW','2':'POS_DIV'},'R75':{'1':'POS_DIV','2':'POS_FB'},
 'R38':{'1':'MID','2':'BI_EN'},'R40':{'1':'BI_EN','2':'GND'},
 'J7':{str(i):('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None) for i in range(1,17)},
 'L1':{'1':'MID_SW','2':'MID'},'L4':{'1':'FIVE_SW','2':'P5'},'L2':{'1':'MID','2':'BOOST_SW'},'L3':{'1':'INV_SW','2':'GND'},
}
# Literal independent manufacturer pin map: never imported from the generator.
REVIEWED['U12']={'1':'P12','2':None,'3':'P12','4':None,'5':'GND','6':'GND','7':'GND','8':None,'9':'GND','10':None,'11':'GND','12':None,'13':'PRAW','14':'P_NR','15':'PRAW','16':'PRAW','17':None,'18':None,'19':None,'20':'P12','21':'GND'}
REVIEWED['U13']={'1':'N12','2':None,'3':'N_LDO_FB','4':None,'5':None,'6':None,'7':'GND','8':None,'9':None,'10':None,'11':None,'12':None,'13':'NRAW','14':'N_NR','15':'NRAW','16':'NRAW','17':None,'18':None,'19':None,'20':'N12','21':'GND'}
for refs,net in [([48,49,50,63],'PRAW'),([51,52,53,64,65,66],'P12'),([54,55,56,67],'NRAW'),([57,58,59],'N12'),([60],'P_NR'),([61],'N_NR')]:
    for i in refs:REVIEWED['C'+str(i)]={'1':net,'2':'GND'}
REVIEWED.update({'C62':{'1':'N12','2':'N_LDO_FB'},'R72':{'1':'N12','2':'N_LDO_DIV'},'R73':{'1':'N_LDO_DIV','2':'N_LDO_FB'},'R74':{'1':'N_LDO_FB','2':'GND'},'D27':{'1':'PRAW','2':'P12'},'D28':{'1':'N12','2':'NRAW'}})
LOCAL=[(('U1','9'),('R2','1')),(('U1','1'),('F1','2')),(('U1','4'),('U1','5')),
 (('U2','3'),('R4','2')),(('U2','5'),('R7','1')),(('U2','11'),('R8','1')),(('U2','12'),('C3','1')),(('U2','6'),('R36','1')),
 (('SW1','1'),('SW1','3')),(('U2','7'),('SW1','1')),(('U2','8'),('SW1','2')),
 (('U3','2'),('L1','1')),(('U3','4'),('R9','2')),(('U3','4'),('R10','1')),(('U3','6'),('C35','1')),(('U3','2'),('C35','2')),
 (('U5','2'),('L4','1')),(('U5','4'),('R17','2')),(('U5','4'),('R18','1')),(('U5','6'),('C36','1')),(('U5','2'),('C36','2')),
 (('U4','22'),('R75','2')), (('R12','2'),('R75','1')),(('U4','22'),('R13','1')),(('U4','16'),('R60','2')),(('U4','16'),('R15','1')),(('U4','17'),('R76','2')), (('R15','2'),('R76','1')),(('U4','17'),('C12','1')),
 (('U4','21'),('C13','1')),(('U4','18'),('C14','1')),(('R32','2'),('D10','2')),(('R38','2'),('R40','1'))]

LOCAL += [(('U12','15'),('U12','16')),(('U12','13'),('U12','15')),(('U12','1'),('U12','20')),(('U12','1'),('U12','3')),
          (('U12','14'),('C60','1')),(('U12','21'),('U12','7')),
          (('U13','15'),('U13','16')),(('U13','13'),('U13','15')),(('U13','1'),('U13','20')),
          (('U13','14'),('C61','1')),(('U13','21'),('U13','7')),
          (('R72','2'),('R73','1')),(('U13','3'),('R73','2')),(('U13','3'),('R74','1')),
          (('U13','3'),('C62','2')),(('U13','1'),('C62','1')),
          (('D27','1'),('U12','15')),(('D27','2'),('U12','1')),
          (('D28','1'),('U13','1')),(('D28','2'),('U13','15'))]

def check(hw,audit,bom):
    graph=Connectivity(hw);actual=graph.named_pins();expected=json.loads(Path(audit).read_text())
    assert actual=={(r,p):n for r,pins in expected.items() for p,n in pins.items()},'Full pin/no-connect inventory mismatch'
    with Path(bom).open() as f:rows={r['Reference']:r for r in csv.DictReader(f)}
    assert set(rows)=={r for r,p in actual if not r.startswith('#')},'BOM/native refs differ'
    for r,pins in REVIEWED.items():
        for p,n in pins.items():assert actual[(r,p)]==n,('independent pin-role',r,p,n)
    for a,b in LOCAL:assert graph.wire_connected(a,b),('Visible wire missing',a,b)
    retired=['U6','U7','U8','U9','U10','U11','J2','J8','JP1','Q1','Q2','Q3','R1','R3','R28','R29','R30','R35','R37','D1','D11','D12','C33','C34','C39','C40','C41']
    retired += [f'R{i}' for i in range(41,60)]+[f'R{i}' for i in range(61,72)]+[f'D{i}' for i in range(13,27)]+[f'C{i}' for i in range(42,48)]
    for obsolete in retired:assert obsolete not in rows,('obsolete device',obsolete)
    assert not any('TPS621' in r['MPN'] or 'ATTINY' in r['MPN'].upper() or 'MCP1799' in r['MPN'] for r in rows.values())
    assert not any(n and any(t in n for t in ('AUX','ADC_','SENSE_','DBG_','UPDI','MCU','VBUS_RAW','VBUS_FUSED','PERMIT','EF_ENABLE','BUTTON')) for n in actual.values())
    assert rows['R38']['Value']==rows['R40']['Value']=='100k 1%'
    for r,mpn,code,fp in [('L1','MDA1040-6R8M','C2847552','L_KOHER_MDA1040'),('L4','MDA1040-6R8M','C2847552','L_KOHER_MDA1040'),('L2','CKCS6045-4.7uH/M','C5291878','L_CENKER_CKCS6045'),('L3','CKCS6045-4.7uH/M','C5291878','L_CENKER_CKCS6045')]:
        assert (rows[r]['MPN'],rows[r]['LCSC'],rows[r]['Footprint'])==(mpn,code,'BigModular:'+fp)
    footprint_maps=0
    for ref,row in rows.items():
        assert row['Footprint'],('active footprint missing',ref)
        footprint=parse((Path(hw)/'BigModular.pretty'/(row['Footprint'].split(':')[-1]+'.kicad_mod')).read_text())
        pads=nodes(footprint,'pad')
        assert {p[1] for p in pads if p[1]}==set(expected[ref]),('numeric pin/pad mismatch',ref)
        for pad in pads:
            for key in ('at','size'):
                for v in one(pad,key)[1:]:assert isinstance(v,Atom) and math.isfinite(float(v)),('quoted/non-numeric pad geometry',ref,key,v)
        footprint_maps+=1
    for ref,val in [('R8','6.04k 1%'),('R36','402k 1%'),('R9','100k 0.1%'),('R10','12.9k 0.1%')]:assert rows[ref]['Value']==val,(ref,val)
    for r in ['R32']:assert rows[r]['LCSC']=='C21190' and rows[r]['Value']=='1k 1%'
    for r in ['D10']:assert rows[r]['Classification']=='Manual'
    assert actual[('U2','8')]!=actual[('U2','9')]
    assert actual[('U4','17')]!=actual[('U4','19')]
    for ref in ['J7']:
        for i in range(1,17):assert actual[(ref,str(i))]==('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None)
    # Native instance fields must equal BOM exactly, including manual J7.
    for ref,(_,symbol) in graph.refs.items():
        if ref.startswith('#'):continue
        props={p[1]:p[2] for p in nodes(symbol,'property')}
        for field in ['Value','MPN','Footprint','LCSC']:assert props.get(field,'')==rows[ref][field],(ref,field,'BOM mismatch')
    return {'parts':len(rows),'pins_including_NC':len(actual),'independent_pin_checks':sum(map(len,REVIEWED.values())),'local_visible_wire_checks':len(LOCAL),'hierarchical_ports':len(graph.hierarchy_links),'footprint_pin_maps':footprint_maps,'fabrication_ready':False}
