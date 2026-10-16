"""Independent reviewed pin-role checks; not derived from generator inventory."""
import csv,json
from pathlib import Path
from schematic_connectivity import Connectivity
from sexp import nodes,one
REVIEWED={
 'U1':{'1':'VBUS_FUSED','8':'VBUS_FUSED','11':'GND','2':'PD_SCL','3':'PD_SDA','4':'PD_D_SHORT','5':'PD_D_SHORT','6':'CC2','7':'CC1','9':'PD_CFG','10':'PD_PG_N'},
 'U2':{'1':'VBUS_FUSED','2':'VBUS_FUSED','3':'UV_EN','5':'OV_SET','6':'EF_MODE','7':'EF_ENABLE','8':'RTN','9':'GND','11':'ILIM','12':'SLEW','14':'EF_FLT_N','15':'VPROT','16':'VPROT','17':'RTN'},
 'U3':{'1':'GND','2':'MID_SW','3':'VPROT','4':'MID_FB','5':'EF_ENABLE','6':'MID_BOOT'},
 'U5':{'1':'GND','2':'FIVE_SW','3':'VPROT','4':'FIVE_FB','5':'EF_ENABLE','6':'FIVE_BOOT'},
 'U4':{'1':'BOOST_SW','24':'BOOST_SW','2':'GND','3':'GND','4':'ANA_MID','5':'MID','6':'MID','8':'BI_EN','9':'GND','10':'BI_EN','11':'GND','13':'INV_SW','14':'INV_SW','15':'N12','16':'NEG_FB','17':'BI_REF','18':'COMP_N','19':'GND','21':'COMP_P','22':'POS_FB','23':'P12','25':'GND'},
 'U9':{'1':'VBUS_FUSED','2':'GND','4':'GND','3':'AUX3V3'},
 'U10':{'1':'AUX3V3','20':'GND','2':'ADC_P12','3':None,'4':'ADC_N12','5':'ADC_P5','6':'ADC_MID','7':'ADC_VBUS','10':'ADC_VPROT','12':'LED_P_K','13':'LED_N_K','14':'LED_5_K','9':'MCU_PERMIT_N','8':'BI_EN','11':'EF_FLT_N','15':'RESET_N','16':'UPDI','17':'PD_SDA','18':'PD_SCL','19':'PD_PG_N'},
 'U11':{'1':'NEG_SENSE','2':'NEG_SUM','3':'GND','4':'GND','5':'GND','6':'OP_UNUSED','7':'OP_UNUSED','8':'AUX3V3'},
 'Q1':{'1':'PG_BASE','2':'AUX3V3','3':'PG_PERMIT'},'Q2':{'1':'MCU_BASE','2':'PG_PERMIT','3':'MCU_PERMIT'},
 'JP1':{'1':'MCU_PERMIT','2':'EF_ENABLE'},'SW1':{'1':'RESET_N','3':'RESET_N','2':'GND','MP':None},
 'D10':{'1':'LED_P_K','2':'LED_P_A'},'D11':{'1':'LED_N_K','2':'LED_N_A'},'D12':{'1':'LED_5_K','2':'LED_5_A'},
 'C35':{'1':'MID_BOOT','2':'MID_SW'},'C36':{'1':'FIVE_BOOT','2':'FIVE_SW'},
 'R8':{'1':'ILIM','2':'RTN'},'R36':{'1':'EF_MODE','2':'RTN'},'R14':{'1':'N12','2':'NEG_DIV'},'R60':{'1':'NEG_DIV','2':'NEG_FB'},'R15':{'1':'NEG_FB','2':'BI_REF'},
}
LOCAL=[(('U1','9'),('R2','1')),(('U1','1'),('F1','2')),(('U1','4'),('U1','5')),
 (('U2','3'),('R4','2')),(('U2','5'),('R7','1')),(('U2','11'),('R8','1')),(('U2','12'),('C3','1')),(('U2','6'),('R36','1')),(('U2','14'),('R37','2')),
 (('R28','2'),('Q1','1')),(('R38','2'),('Q2','1')),(('Q1','3'),('Q2','2')),(('Q2','3'),('JP1','1')),(('JP1','2'),('U2','7')),
 (('U3','2'),('L1','1')),(('U3','4'),('R9','2')),(('U3','4'),('R10','1')),(('U3','6'),('C35','1')),(('U3','2'),('C35','2')),
 (('U5','2'),('L4','1')),(('U5','4'),('R17','2')),(('U5','4'),('R18','1')),(('U5','6'),('C36','1')),(('U5','2'),('C36','2')),
 (('U4','22'),('R12','2')),(('U4','22'),('R13','1')),(('U4','16'),('R60','2')),(('U4','16'),('R15','1')),(('U4','17'),('R15','2')),(('U4','17'),('C12','1')),
 (('U4','21'),('C13','1')),(('U4','18'),('C14','1')),(('U11','2'),('R42','2')),(('U11','2'),('R43','1')),(('U11','1'),('R43','2')),(('U11','6'),('U11','7')),
 (('R32','2'),('D10','2')),(('D10','1'),('U10','12')),(('R33','2'),('D11','2')),(('D11','1'),('U10','13')),(('R34','2'),('D12','2')),(('D12','1'),('U10','14'))]

def check(hw,audit,bom):
    graph=Connectivity(hw);actual=graph.named_pins();expected=json.loads(Path(audit).read_text())
    assert actual=={(r,p):n for r,pins in expected.items() for p,n in pins.items()},'Full pin/no-connect inventory mismatch'
    rows={r['Reference']:r for r in csv.DictReader(Path(bom).open())}
    assert set(rows)=={r for r,p in actual if not r.startswith('#')},'BOM/native refs differ'
    for r,pins in REVIEWED.items():
        for p,n in pins.items():assert actual[(r,p)]==n,('independent pin-role',r,p,n)
    for a,b in LOCAL:assert graph.wire_connected(a,b),('Visible wire missing',a,b)
    for obsolete in ['U6','U7','U8','R1','D1']:
        assert obsolete not in rows,('obsolete device',obsolete)
    assert not any('TPS621' in r['MPN'] for r in rows.values())
    for ref,val in [('R8','6.04k 1%'),('R36','402k 1%'),('R9','100k 0.1%'),('R10','12.9k 0.1%')]:assert rows[ref]['Value']==val,(ref,val)
    for r in ['R32','R33','R34']:assert rows[r]['LCSC']=='C21190' and rows[r]['Value']=='1k 1%'
    for r in ['D10','D11','D12']:assert rows[r]['Classification']=='Manual'
    assert actual[('U2','8')]!=actual[('U2','9')]
    assert actual[('U4','17')]!=actual[('U4','19')]
    for ref in ['J2','J7']:
        for i in range(1,17):assert actual[(ref,str(i))]==('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None)
    # Native instance fields must equal BOM exactly, including off-board J2.
    for ref,(_,symbol) in graph.refs.items():
        if ref.startswith('#'):continue
        props={p[1]:p[2] for p in nodes(symbol,'property')}
        for field in ['Value','MPN','Footprint','LCSC']:assert props.get(field,'')==rows[ref][field],(ref,field,'BOM mismatch')
    return {'parts':len(rows),'pins_including_NC':len(actual),'independent_pin_checks':sum(map(len,REVIEWED.values())),'local_visible_wire_checks':len(LOCAL),'hierarchical_ports':len(graph.hierarchy_links),'fabrication_ready':False}
