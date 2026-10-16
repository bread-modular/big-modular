"""Independent reviewed pin-role checks; not derived from generator inventory."""
import csv,json
from pathlib import Path
from schematic_connectivity import Connectivity
from sexp import nodes,one,parse,Atom,walk
import math
REVIEWED={
 'U1':{'1':'VBUS_FUSED','8':'VBUS_FUSED','11':'GND','2':'PD_SCL','3':'PD_SDA','4':'PD_D_SHORT','5':'PD_D_SHORT','6':'CC2','7':'CC1','9':'PD_CFG','10':'PD_PG_N'},
 'U2':{'1':'VBUS_FUSED','2':'VBUS_FUSED','3':'UV_EN','5':'OV_SET','6':'EF_MODE','7':'EF_ENABLE','8':'RTN','9':'GND','11':'ILIM','12':'SLEW','14':'EF_FLT_N','15':'VPROT','16':'VPROT','17':'RTN'},
 'U3':{'1':'GND','2':'MID_SW','3':'VPROT','4':'MID_FB','5':'EF_ENABLE','6':'MID_BOOT'},
 'U5':{'1':'GND','2':'FIVE_SW','3':'VPROT','4':'FIVE_FB','5':'EF_ENABLE','6':'FIVE_BOOT'},
 'U4':{'1':'BOOST_SW','24':'BOOST_SW','2':'GND','3':'GND','4':'ANA_MID','5':'MID','6':'MID','8':'BI_EN','9':'GND','10':'BI_EN','11':'GND','13':'INV_SW','14':'INV_SW','15':'N12','16':'NEG_FB','17':'BI_REF','18':'COMP_N','19':'GND','21':'COMP_P','22':'POS_FB','23':'P12','25':'GND'},
 'U9':{'1':'VBUS_FUSED','2':'GND','4':'GND','3':'AUX3V3'},
 'U11':{'1':'NEG_SENSE','2':'NEG_SUM','3':'GND','4':'GND','5':'GND','6':'OP_UNUSED','7':'OP_UNUSED','8':'AUX3V3'},
 'Q1':{'1':'PG_BASE','2':'AUX3V3','3':'PG_PERMIT'},
 'JP1':{'1':'PG_PERMIT','2':'EF_ENABLE'},'SW1':{'1':'BUTTON_N','3':'BUTTON_N','2':'GND','MP':None},
 'D10':{'1':'GND','2':'LED_P_A'},'R32':{'1':'P5','2':'LED_P_A'},
 'C35':{'1':'MID_BOOT','2':'MID_SW'},'C36':{'1':'FIVE_BOOT','2':'FIVE_SW'},
 'R8':{'1':'ILIM','2':'RTN'},'R36':{'1':'EF_MODE','2':'RTN'},'R14':{'1':'N12','2':'NEG_DIV'},'R60':{'1':'NEG_DIV','2':'NEG_FB'},'R15':{'1':'NEG_FB','2':'BI_REF'},
}
# Independent external interface contract, intentionally not imported from generator.
DEBUG_PINS={'1':'GND','2':'DBG_AUX_MON','3':'ADC_P12','4':'GND',
 '5':'ADC_N12','6':'ADC_P5','7':'ADC_MID','8':'ADC_VBUS','9':'ADC_VPROT','10':'GND',
 '11':'DBG_PG_N','12':'DBG_FLT_N','13':'DBG_SDA','14':'DBG_SCL','15':'DBG_BUTTON_N',
 '16':'GND','17':None,'18':None,'19':None,'20':None}
REVIEWED.update({'J8':DEBUG_PINS,'R38':{'1':'MID','2':'BI_EN'},'R40':{'1':'BI_EN','2':'GND'},
 'R61':{'1':'AUX3V3','2':'DBG_AUX_MON'},'R62':{'1':'PD_PG_N','2':'DBG_PG_N'},
 'R63':{'1':'EF_FLT_N','2':'DBG_FLT_N'},'R64':{'1':'PD_SDA','2':'DBG_SDA'},
 'R65':{'1':'PD_SCL','2':'DBG_SCL'},'R66':{'1':'BUTTON_N','2':'DBG_BUTTON_N'},
 'R70':{'1':'AUX3V3','2':'PD_SDA'},'R71':{'1':'AUX3V3','2':'PD_SCL'}})

LOCAL=[(('U1','9'),('R2','1')),(('U1','1'),('F1','2')),(('U1','4'),('U1','5')),
 (('U2','3'),('R4','2')),(('U2','5'),('R7','1')),(('U2','11'),('R8','1')),(('U2','12'),('C3','1')),(('U2','6'),('R36','1')),(('U2','14'),('R37','2')),
 (('R28','2'),('Q1','1')),(('Q1','3'),('JP1','1')),(('JP1','2'),('U2','7')),
 (('U3','2'),('L1','1')),(('U3','4'),('R9','2')),(('U3','4'),('R10','1')),(('U3','6'),('C35','1')),(('U3','2'),('C35','2')),
 (('U5','2'),('L4','1')),(('U5','4'),('R17','2')),(('U5','4'),('R18','1')),(('U5','6'),('C36','1')),(('U5','2'),('C36','2')),
 (('U4','22'),('R12','2')),(('U4','22'),('R13','1')),(('U4','16'),('R60','2')),(('U4','16'),('R15','1')),(('U4','17'),('R15','2')),(('U4','17'),('C12','1')),
 (('U4','21'),('C13','1')),(('U4','18'),('C14','1')),(('U11','2'),('R42','2')),(('U11','2'),('R43','1')),(('U11','1'),('R43','2')),(('U11','6'),('U11','7')),
 (('R32','2'),('D10','2')),(('R38','2'),('R40','1')),
 (('SW1','1'),('SW1','3')),(('R41','2'),('SW1','1')),(('SW1','1'),('C40','1'))]

def check(hw,audit,bom):
    graph=Connectivity(hw);actual=graph.named_pins();expected=json.loads(Path(audit).read_text())
    assert actual=={(r,p):n for r,pins in expected.items() for p,n in pins.items()},'Full pin/no-connect inventory mismatch'
    with Path(bom).open() as f:rows={r['Reference']:r for r in csv.DictReader(f)}
    assert set(rows)=={r for r,p in actual if not r.startswith('#')},'BOM/native refs differ'
    for r,pins in REVIEWED.items():
        for p,n in pins.items():assert actual[(r,p)]==n,('independent pin-role',r,p,n)
    for a,b in LOCAL:assert graph.wire_connected(a,b),('Visible wire missing',a,b)
    for obsolete in ['U6','U7','U8','R1','D1','U10','C39','Q2','Q3','R39','R33','R34','D11','D12','R67','R68','R69']:
        assert obsolete not in rows,('obsolete device',obsolete)
    assert not any('TPS621' in r['MPN'] or 'ATTINY' in r['MPN'].upper() for r in rows.values())
    assert not any(n and ('MCU' in n or 'UPDI' in n or 'EXT_PERMIT' in n or 'EXT_BI' in n or 'LED_' in n and n!='LED_P_A' or n=='RESET_N') for n in actual.values())
    assert 'default OPEN' in rows['JP1']['Value']
    for r,v in [('R38','100k'),('R40','100k'),('R61','10k'),('R62','10k'),('R63','10k'),('R64','1k'),('R65','1k'),('R66','10k'),('R70','10k'),('R71','10k')]:
        assert rows[r]['Value']==v+' 1%',('debug current limit/default',r,v)
    assert rows['J8']['Footprint']=='BigModular:IDC-Header_2x10_P2.54mm_Vertical'
    # All six original analogue paths: pin roles, ratio, RC and individual clamps.
    for top,bottom,rail,raw,tv,bv in [('R44','R45','P12','SENSE_P12','100k','20k'),('R46','R47','P5','SENSE_P5','20k','10k'),('R48','R49','MID','SENSE_MID','20k','10k'),('R50','R51','VBUS_FUSED','SENSE_VBUS','100k','10k'),('R52','R53','VPROT','SENSE_VPROT','100k','10k')]:
        assert (actual[(top,'1')],actual[(top,'2')],actual[(bottom,'1')],actual[(bottom,'2')])==(rail,raw,raw,'GND')
        assert rows[top]['Value']==tv+' 1%' and rows[bottom]['Value']==bv+' 1%'
    assert {p:actual[('R42',p)] for p in ('1','2')}=={'1':'N12','2':'NEG_SUM'}
    assert {p:actual[('R43',p)] for p in ('1','2')}=={'1':'NEG_SUM','2':'NEG_SENSE'}
    assert rows['R42']['Value']=='100k 1%' and rows['R43']['Value']=='16.5k 1%'
    assert rows['U11']['MPN']=='TLV9002IDR'
    for i,channel in enumerate(['P12','N12','P5','MID','VBUS','VPROT']):
        r='R'+str(54+i);c='C'+str(42+i);lo='D'+str(13+2*i);hi='D'+str(14+2*i);out='ADC_'+channel
        assert (actual[(r,'1')],actual[(r,'2')])==('NEG_SENSE' if channel=='N12' else 'SENSE_'+channel,out)
        assert rows[r]['Value']=='10k 1%' and rows[c]['Value']=='100n 50V X7R'
        assert (actual[(c,'1')],actual[(c,'2')],actual[(lo,'1')],actual[(lo,'2')],actual[(hi,'1')],actual[(hi,'2')])==(out,'GND',out,'GND','AUX3V3',out)
    for r in [f'D{i}' for i in range(13,27)]:
        assert rows[r]['Value']=='BAT54WS-7-F' and rows[r]['LCSC']=='C124205'
        assert rows[r]['Footprint']=='BigModular:D_SOD-323'
    footprint_maps=0
    for ref,row in rows.items():
        if not row['Footprint']:continue
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
    for ref in ['J2','J7']:
        for i in range(1,17):assert actual[(ref,str(i))]==('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None)
    # Native instance fields must equal BOM exactly, including off-board J2.
    for ref,(_,symbol) in graph.refs.items():
        if ref.startswith('#'):continue
        props={p[1]:p[2] for p in nodes(symbol,'property')}
        for field in ['Value','MPN','Footprint','LCSC']:assert props.get(field,'')==rows[ref][field],(ref,field,'BOM mismatch')
    return {'parts':len(rows),'pins_including_NC':len(actual),'independent_pin_checks':sum(map(len,REVIEWED.values())),'local_visible_wire_checks':len(LOCAL),'hierarchical_ports':len(graph.hierarchy_links),'footprint_pin_maps':footprint_maps,'fabrication_ready':False}
