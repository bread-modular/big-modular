"""Electrical source of truth for the authorized 9 V prototype (not a release).

All symbol mappings below are manufacturer pin numbers. Datasheet source evidence
and unqualified analogue/power-up gates live in docs/electrical-prototype.md.
Only build_project.py emits these records, into an explicitly NEW candidate.
"""
import json
from sexp import nodes, one, atom
from pathlib import Path
from interface_contract import validate_reference

def populate(stock, ic, lib, root):
    sheets={};bom=[];conns={}
    R=stock('Device','R');C=stock('Device','C');L=stock('Device','L');D=stock('Device','D_Schottky')
    LED=stock('Device','LED');F=stock('Device','Fuse');JP=stock('Jumper','Jumper_2_Open')
    USB=stock('Connector','USB_C_Receptacle_USB2.0_16P');IDC=stock('Connector_Generic','Conn_02x08_Odd_Even')
    PNP=stock('Transistor_BJT','MMBT3906');FLAG=stock('power','PWR_FLAG')
    def chip(name, defs, url):return ic(name,[(str(n),label,t,side) for n,label,t,side in defs],url)
    CH=chip('CH224A',[(1,'VHV','power_in','L'),(8,'VBUS_SENSE','input','L'),(7,'CC1','bidirectional','L'),(6,'CC2','bidirectional','L'),(4,'DP','bidirectional','L'),(5,'DM','bidirectional','L'),(11,'EP0_GND','power_in','L'),(2,'CFG2_SCL','input','R'),(3,'CFG3_SDA','bidirectional','R'),(9,'CFG1','input','R'),(10,'PG_N','open_collector','R')],'https://done.land/assets/files/ch224a_datasheet.pdf')
    EF=chip('TPS26600PWPR',[(1,'IN','power_in','L'),(2,'IN','passive','L'),(3,'UVLO','input','L'),(5,'OVP','input','L'),(7,'SHDN','input','L'),(9,'GND','power_in','L'),(8,'RTN','power_out','L'),(17,'EP_RTN','passive','L'),(4,'NC','no_connect','L'),(13,'NC','no_connect','L'),(15,'OUT','power_out','R'),(16,'OUT','passive','R'),(14,'FLT_N','open_collector','R'),(11,'ILIM','passive','R'),(12,'dVdT','passive','R'),(6,'MODE','input','R'),(10,'IMON','output','R')],'https://www.ti.com/lit/ds/symlink/tps2660.pdf')
    BUCK=chip('TPS54302DDCR',[(3,'VIN','power_in','L'),(5,'EN','input','L'),(1,'GND','power_in','L'),(6,'BOOT','passive','R'),(2,'SW','output','R'),(4,'FB','input','R')],'https://www.ti.com/lit/ds/symlink/tps54302.pdf')
    BI=stock('Regulator_Switching','TPS65131RGE')
    AUX=chip('MCP1799T_3302H_DB',[(1,'VIN','power_in','L'),(2,'GND','power_in','L'),(4,'TAB_GND','passive','L'),(3,'VOUT','power_out','R')],'https://ww1.microchip.com/downloads/en/DeviceDoc/MCP1799-Data-Sheet-20006248A.pdf')
    OP=chip('TLV9002IDR',[(3,'IN1+','input','L'),(2,'IN1-','input','L'),(5,'IN2+','input','L'),(6,'IN2-','input','L'),(4,'V-','power_in','L'),(1,'OUT1','output','R'),(7,'OUT2','output','R'),(8,'V+','power_in','R')],'https://www.ti.com/lit/ds/symlink/tlv9002.pdf')
    # E-Switch P021301 Rev B: 1 and 3 common, momentary closure to 2.
    # The existing footprint calls BOTH case solder lands MP (not contacts4/5).
    SW=chip('TL3340AF160QG',[(1,'COMMON','passive','L'),(3,'COMMON','passive','L'),(2,'NO','passive','R'),('MP','CASE','passive','R')],'https://configured-product-images.s3.amazonaws.com/2D/specs/TL3340AF160QG.pdf')
    # Retain the prior diagram's contact positions; no neighbouring wire churn.
    for unit in nodes(lib[SW],'symbol'):
        for pin in nodes(unit,'pin'):
            one(pin,'at')[2]=atom({'1':'5.08','3':'0','2':'5.08','MP':'-5.08'}[one(pin,'number')[1]])
    DEBUG=stock('Connector_Generic','Conn_02x10_Odd_Even')
    for name,title,notes in [
      ('01_input_protection','USB PD and always-on housekeeping','CH224A: VHV1 + VBUS8 directly fused VBUS; EP0 -> pad11.\nWCH section 7.1 contradicts sections 4/6/8 on VBUS rating: vendor confirmation is a POWER-UP BLOCKER.\nAUX3V3 operates at negotiation 5 V; NO output-rail operation from fallback. No mains/input = no LEDs.'),
      ('02_hardgate','Independent hardware gate','7.878 / 10.781 V nominal hardware window. RTN is NOT GND.\nR8 6.04k: 1.987 A nominal, not 3 A. MODE 402k: current limit with thermal latch-off.\nJP1 RUN default OPEN; PG hardware permission; no debug controller required. FLT is aggregate, not per-rail overload proof.'),
      ('03_bucks','Independent buck converters','U3 MID 5.216 V; upper DC corner 5.357 V BEFORE transients. U4 ceiling 5.5 V.\nU5 direct 5.011 V from VPROT, never from positive boost. 100n BOOT-to-SW each.\nEffective ceramic C, magnetic Isat/DCR/thermal and loop/transient response remain qualification gates.'),
      ('04_bipolar','Direct bipolar rails','Nominal +/-11.968 V. FBN returns to VREF, NOT GND; PSP/PSN grounded.\nLocal output feedback: no remote sense or arbitrary LC added. No rail LDOs.\n~800 mA positive is chart interpolation at 25 C, NOT guaranteed continuous or simultaneous +/-800 mA.'),
      ('05_diagnostics','Rail debug and single power LED','J8 KEYED 2x10 DEBUG ONLY - NOT EURORACK POWER. No onboard MCU / no blink. D10 is ordinary +5V power indication.\n3.3 V external controller: inputs Hi-Z, outputs OPEN-DRAIN ONLY; no external pullups/power into AUX.\nNormal operation is hardware PG/window only; qualification JP1 stays OPEN. See docs/debug-interface.md for all pins and sequencing.'),
      ('06_sensing','Rail sensing and input protection','Negative rail uses ground-referenced inverter, NOT AUX-biased divider.\nExternal Schottky clamps + series resistors are provisions, NOT proven powered-off isolation.\nOFF-state injection / clamp Vf / residual rail bleed / reference calibration are POWER-UP BLOCKERS.'),
      ('07_output_rails','Manual output harness','J7 board wire landing -> J2 off-board IDC cable, pin-for-pin.\n1/2=-12, 3..8=GND, 9/10=+12, 11/12=+5; 13..16 NC.\nNever connect another active PSU. Continuity-test red stripe / orientation before use.')]:
        sheets[name]={'title':title,'notes':notes,'parts':[]}
    # Catalog records are bounded strict-live snapshots, not procurement approval.
    catalog={}
    for f in (root/'research/electrical-v1/sourcing').glob('*.json'):
        try:
            d=json.loads(f.read_text())
            for part in ([d['part']] if 'part' in d else d.get('parts',[])):catalog[part['code']]=part
        except (ValueError,KeyError):pass
    # A pinned, reviewable snapshot is the generator's source; regeneration is offline.
    pinned=root/'docs/electrical-catalog.json'
    if pinned.exists():catalog=json.loads(pinned.read_text())
    def add(sh,ref,kind,value,nets,fp='',code='',mpn='',note='',manual=False,onboard=True):
        validate_reference(ref,'rail_indicator' if kind==LED and ref in ('D10','D11','D12') else '')
        if ref in conns:raise ValueError('Duplicate '+ref)
        part=catalog.get(code,{})
        if code and mpn and part and mpn!=part['mpn']:raise ValueError((ref,mpn,part['mpn']))
        mpn=mpn or part.get('mpn','')
        note=note or 'Prototype candidate; qualify ratings, land pattern and operating corners.'
        footprint=('BigModular:'+fp.split(':')[-1]) if fp else ''
        d=dict(ref=ref,kind=kind,value=value,nets={str(k):v for k,v in nets.items()},mpn=mpn,lcsc=code,fp=footprint,note=note,onboard=onboard,manual=manual,datasheet=next((x[2] for x in lib[kind] if isinstance(x,list) and x[:2]==['property','Datasheet']),''))
        sheets[sh]['parts'].append(d);conns[ref]=d['nets']
        if not ref.startswith('#'):
            bom.append(dict(Reference=ref,Value=value,MPN=mpn,Footprint=fp,LCSC=code,Manufacturer=part.get('manufacturer',''),Classification=part.get('classification','Manual' if manual else 'UNKNOWN'),Sourcing='Manual / excluded from JLC' if manual else 'Catalog candidate; no allocation/qualification guarantee' if part else 'UNRESOLVED sourcing',Notes=note,Block=sh))
        return d
    def rr(sh,ref,v,a,b,code='',note=''):
        defaults={'100k':'C25803','10k':'C25804','1k':'C21190','6.8k':'C23212','20k':'C4184','22k':'C31850','150k':'C22807','562k':'C23205','806k':'C23250','402k':'C23048','6.04k':'C25977','16.5k':'C22812','13.5k':'C861118','1.33M':'C482628'}
        return add(sh,ref,R,v+' '+('0.1%' if code in ('C2912578','C149921') or v=='13.5k' else '1%'),{'1':a,'2':b},'Resistor_SMD:R_0603_1608Metric',code or defaults.get(v,''),note=note)
    def cc(sh,ref,v,a,b,code='',size='0603_1608'):
        return add(sh,ref,C,v,{'1':a,'2':b},'Capacitor_SMD:C_'+size+'Metric',code or ('C14663' if v=='100n 50V X7R' else ''),note='Effective capacitance under DC bias and temperature must be verified; no automatic reuse approval.')
    def dd(sh,ref,k,a,clamp=False):return add(sh,ref,D,'BAT54WS-7-F' if clamp else 'SS34 40V',{'1':k,'2':a},'Diode_SMD:D_SOD-323' if clamp else 'Diode_SMD:D_SMA','C124205' if clamp else 'C8678',note='Clamp injection/Vf/leakage unqualified.' if clamp else 'Rectifier Vf/thermal/reverse transients and assembly polarity to qualify.')
    a='01_input_protection'
    n={p:('VBUS_RAW' if p in ['A4','A9','B4','B9'] else 'GND' if p in ['A1','A12','B1','B12','SH'] else 'CC1' if p=='A5' else 'CC2' if p=='B5' else None) for p in ['A1','A4','A5','A6','A7','A8','A9','A12','B1','B4','B5','B6','B7','B8','B9','B12','SH']}
    add(a,'J1',USB,'USB4105-GF-A',n,'BigModular:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',mpn='USB4105-GF-A',manual=True)
    add(a,'F1',F,'3A 32V candidate',{'1':'VBUS_RAW','2':'VBUS_FUSED'},'Fuse:Fuse_1206_3216Metric','C14165',note='0466003.NRHF catalog candidate only; source/fuse/eFuse thermal and I2t coordination NOT qualified.')
    add(a,'U1',CH,'CH224A',{'1':'VBUS_FUSED','8':'VBUS_FUSED','2':'PD_SCL','3':'PD_SDA','4':'PD_D_SHORT','5':'PD_D_SHORT','6':'CC2','7':'CC1','9':'PD_CFG','10':'PD_PG_N','11':'GND'},'Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm','C42459160',note='WCH V2 table4-1; VHV1 is high-voltage input. EP0 mapped to pad11. Section7.1 VBUS contradiction unresolved.')
    cc(a,'C1','1u 50V X7R','VBUS_FUSED','GND',size='0805_2012');rr(a,'R2','6.8k','PD_CFG','GND');rr(a,'R3','100k','AUX3V3','PD_PG_N')
    add(a,'U9',AUX,'MCP1799T-3302H/DB',{'1':'VBUS_FUSED','2':'GND','4':'GND','3':'AUX3V3'},'BigModular:MCP1799_SOT223_Tab4','C3752493',note='Datasheet tab4 internally GND; named custom footprint has separate tab4, both pins2/4 GND. >=1uF effective output required.')
    cc(a,'C33','1u 50V X7R','VBUS_FUSED','GND',size='0805_2012');cc(a,'C34','2.2u 16V X7R','AUX3V3','GND',size='0805_2012');rr(a,'R35','1k','AUX3V3','GND',note='3.3mA bleed; not proven off-state clamp-rail isolation.')
    a='02_hardgate'
    add(a,'U2',EF,'TPS26600PWPR',{'1':'VBUS_FUSED','2':'VBUS_FUSED','3':'UV_EN','4':None,'5':'OV_SET','6':'EF_MODE','7':'EF_ENABLE','8':'RTN','9':'GND','10':None,'11':'ILIM','12':'SLEW','13':None,'14':'EF_FLT_N','15':'VPROT','16':'VPROT','17':'RTN'},'Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm','C544399')
    for ref,v,x,y in [('R4','562k','VBUS_FUSED','UV_EN'),('R5','100k','UV_EN','RTN'),('R6','806k','VBUS_FUSED','OV_SET'),('R7','100k','OV_SET','RTN'),('R8','6.04k','ILIM','RTN'),('R36','402k','EF_MODE','RTN'),('R37','10k','AUX3V3','EF_FLT_N'),('R28','22k','PD_PG_N','PG_BASE'),('R29','100k','AUX3V3','PG_BASE'),('R30','10k','EF_ENABLE','RTN'),('R31','10k','VPROT','GND')]:rr(a,ref,v,x,y)
    cc(a,'C2','100n 50V X7R','VBUS_FUSED','GND');cc(a,'C3','100n 50V X7R','SLEW','RTN');cc(a,'C4','10u 25V X7R','VPROT','GND',size='1206_3216')
    add(a,'Q1',PNP,'MMBT3906',{'1':'PG_BASE','2':'AUX3V3','3':'PG_PERMIT'},'Package_TO_SOT_SMD:SOT-23',mpn='MMBT3906',note='Diodes DS30059: 1=B 2=E 3=C. PG low permits only first stage.')
    add(a,'JP1',JP,'RUN default OPEN',{'1':'PG_PERMIT','2':'EF_ENABLE'},'Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm',manual=True)
    a='03_bucks'
    for u,prefix,out,Lref,Cs,Rt,Rb,rv,base in [('U3','MID','MID','L1',['C5','C6','C7','C35'],'R9','R10','12.9k',0),('U5','FIVE','P5','L4',['C18','C19','C20','C36'],'R17','R18','13.5k',1)]:
        add(a,u,BUCK,'TPS54302DDCR',{'1':'GND','2':prefix+'_SW','3':'VPROT','4':prefix+'_FB','5':'EF_ENABLE','6':prefix+'_BOOT'},'Package_TO_SOT_SMD:SOT-23-6','C311983')
        add(a,Lref,L,'6.8uH shielded CANDIDATE',{'1':prefix+'_SW','2':out},'Inductor_SMD:L_Bourns_SRP5030T','C2042113',note='Exact candidate ZERO STOCK in snapshot; verify 6A switch-limit saturation, DCR, RMS and 290kHz corner before power-up.')
        cc(a,Cs[0],'10u 25V X7R','VPROT','GND',size='1206_3216');cc(a,Cs[1],'22u 25V X7R',out,'GND','C53084530','1210_3225');cc(a,Cs[2],'100n 50V X7R','VPROT','GND');cc(a,Cs[3],'100n 50V X7R',prefix+'_BOOT',prefix+'_SW')
        cc(a,'C37' if u=='U3' else 'C38','22u 25V X7R',out,'GND','C53084530','1210_3225')
        rr(a,Rt,'100k',out,prefix+'_FB',code='C2912578' if u=='U3' else 'C25803',note='MID ratio 0.1% exception required for DC headroom; 108% OVP is NOT a 5.5V transient guarantee.' if u=='U3' else 'Independent +5 V divider.')
        rr(a,Rb,rv,prefix+'_FB','GND',code='C149921' if u=='U3' else 'C861118')
    a='04_bipolar'
    add(a,'U4',BI,'TPS65131RGER',{'1':'BOOST_SW','24':'BOOST_SW','2':'GND','3':'GND','4':'ANA_MID','5':'MID','6':'MID','7':None,'8':'BI_EN','9':'GND','10':'BI_EN','11':'GND','12':None,'13':'INV_SW','14':'INV_SW','15':'N12','16':'NEG_FB','17':'BI_REF','18':'COMP_N','19':'GND','20':None,'21':'COMP_P','22':'POS_FB','23':'P12','25':'GND'},'Package_DFN_QFN:Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm','C87663')
    for ref,n1,n2 in [('L2','MID','BOOST_SW'),('L3','INV_SW','GND')]:add(a,ref,L,'4.7uH shielded / Isat>=3A TBD',{'1':n1,'2':n2},note='Select exact shielded 4.7uH magnetic per TI table and verify Isat/DCR/thermal. PROCUREMENT + POWER-UP BLOCKER.')
    dd(a,'D2','P12','BOOST_SW');dd(a,'D3','INV_SW','N12')
    for ref,net in [('C8','P12'),('C9','N12')]:cc(a,ref,'22u 25V X7R',net,'GND','C53084530','1210_3225')
    for args in [('R12','1.33M','P12','POS_FB'),('R13','150k','POS_FB','GND'),('R14','1.33M','N12','NEG_DIV'),('R60','150k','NEG_DIV','NEG_FB'),('R15','150k','NEG_FB','BI_REF'),('R16','100','MID','ANA_MID'),('R40','100k','BI_EN','GND'),('R38','100k','MID','BI_EN')]:rr(a,*args)
    cc(a,'C10','6.8p 50V C0G','P12','POS_FB');cc(a,'C11','6.8p 50V C0G','N12','NEG_FB');cc(a,'C12','220n 50V X7R','BI_REF','GND');cc(a,'C13','10n 50V X7R','COMP_P','GND');cc(a,'C14','4.7n 50V C0G','COMP_N','GND');cc(a,'C15','100n 50V X7R','ANA_MID','GND')
    cc(a,'C16','10u 25V X7R','MID','GND',size='1206_3216');cc(a,'C17','10u 25V X7R','MID','GND',size='1206_3216')
    a='05_diagnostics'
    # No MCU/UPDI or programming-only bypass capacitor. Button RC remains useful.
    cc(a,'C40','100n 50V X7R','BUTTON_N','GND');rr(a,'R41','10k','AUX3V3','BUTTON_N')
    add(a,'SW1',SW,'TL3340AF160QG',{'1':'BUTTON_N','3':'BUTTON_N','2':'GND','MP':None},'BigModular:SW_TL3340AF160QG_HandSolder',mpn='TL3340AF160QG',manual=True,note='P021301 Rev B: contacts1+3 common BUTTON_N, contact2 GND; duplicate MP case pads floating. Exported user button, NOT direct power bypass.')
    debug={1:'GND',2:'DBG_AUX_MON',3:'ADC_P12',4:'GND',5:'ADC_N12',6:'ADC_P5',7:'ADC_MID',8:'ADC_VBUS',9:'ADC_VPROT',10:'GND',11:'DBG_PG_N',12:'DBG_FLT_N',13:'DBG_SDA',14:'DBG_SCL',15:'DBG_BUTTON_N',16:'GND',17:None,18:None,19:None,20:None}
    add(a,'J8',DEBUG,'KEYED 2x10 DEBUG - NOT POWER',debug,'Connector_IDC:IDC-Header_2x10_P2.54mm_Vertical',manual=True,note='Replaces old 3-pin UPDI. Keyed 20-pin debug IDC; pin1 rectangular pad GND/red stripe. AUX_MON pin2 OUTPUT ONLY via10k, not controller supply. External3.3V Hi-Z/open-drain only; no 5V/USB/PSU cable. Unplaced; mechanical fit and exact keyed MPN pending. See docs/debug-interface.md.')
    for ref,v,x,y in [('R61','10k','AUX3V3','DBG_AUX_MON'),('R62','10k','PD_PG_N','DBG_PG_N'),('R63','10k','EF_FLT_N','DBG_FLT_N'),('R64','1k','PD_SDA','DBG_SDA'),('R65','1k','PD_SCL','DBG_SCL'),('R66','10k','BUTTON_N','DBG_BUTTON_N'),('R70','10k','AUX3V3','PD_SDA'),('R71','10k','AUX3V3','PD_SCL')]:
        rr(a,ref,v,x,y,note='3.3V debug interface: local-supply pullup/current limit; not galvanic or powered-off isolation. Controller must be Hi-Z or open-drain, no external pullups. See docs/debug-interface.md.')
    rr(a,'R32','1k','P5','LED_P_A',note='Ordinary final +5V power indicator only: 1k series limits current, no controller or blink. Manual3mm D10 cathode to GND. At5.5V and Vf=0, resistor power<31mW with1% tolerance; exact LED brightness/MPN still pending.')
    add(a,'D10',LED,'RED 3mm / +5V POWER / MANUAL',{'1':'GND','2':'LED_P_A'},'BigModular:LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge',manual=True,note='Single hand-soldered red3mm power LED: P5 -> R32 1k -> anode2; cathode1 GND. No automatic blink, no external control, not proof all rails are healthy. Retains original D10 hole/formed-lead fit; exact MPN pending.')
    a='06_sensing'
    add(a,'U11',OP,'TLV9002IDR',{'1':'NEG_SENSE','2':'NEG_SUM','3':'GND','4':'GND','5':'GND','6':'OP_UNUSED','7':'OP_UNUSED','8':'AUX3V3'},'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm','C398360')
    rr(a,'R42','100k','N12','NEG_SUM');rr(a,'R43','16.5k','NEG_SUM','NEG_SENSE');cc(a,'C41','100n 50V X7R','AUX3V3','GND')
    # External clamps to both supplies; never assert these provide off-state isolation.
    for i,(net,top,bottom) in enumerate([('P12','100k','20k'),('P5','20k','10k'),('MID','20k','10k'),('VBUS_FUSED','100k','10k'),('VPROT','100k','10k')]):
        sense=['P12','P5','MID','VBUS','VPROT'][i];raw='SENSE_'+sense
        rr(a,'R'+str(44+2*i),top,net,raw);rr(a,'R'+str(45+2*i),bottom,raw,'GND')
    for i,sense in enumerate(['P12','N12','P5','MID','VBUS','VPROT']):
        rr(a,'R'+str(54+i),'10k','NEG_SENSE' if sense=='N12' else 'SENSE_'+sense,'ADC_'+sense)
        cc(a,'C'+str(42+i),'100n 50V X7R','ADC_'+sense,'GND')
        dd(a,'D'+str(13+2*i),'ADC_'+sense,'GND',True);dd(a,'D'+str(14+2*i),'AUX3V3','ADC_'+sense,True)
    dd(a,'D25','NEG_SUM','GND',True);dd(a,'D26','AUX3V3','NEG_SUM',True)
    a='07_output_rails'
    n={str(i):('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None) for i in range(1,17)}
    add(a,'J2',IDC,'16-pin IDC POWER OUT',n,onboard=False,manual=True,note='OFF-BOARD endpoint of ONE J7->J2 flying-lead power harness, not a second active output. Exact keyed male MPN open; manual harness assembly includes J2 once, no PCB/JLC placement. Red stripe pins1/2=-12V. NOT debug J8.')
    add(a,'J7',IDC,'Manual IDC wire landing',n,'BigModular:WireLanding_2x08_P2.54mm',manual=True,note='ON-CARRIER numbered solder lands, not an extra purchasable box header. Physical cable boundary to off-board J2; one power output harness, not two sources. NOT debug J8.')
    for ref,net in [('R25','P12'),('R26','N12'),('R27','P5')]:rr(a,ref,'10k',net,'GND',note='Bleed provision only; does not prove rail discharge time or prevent backfeed.')
    # True passive-source declarations for ERC; no arbitrary error exclusions.
    for i,net in enumerate(['GND','VBUS_RAW','VBUS_FUSED','MID','ANA_MID','P12','N12','P5']):add(a,f'#FLG{i+1:02}',FLAG,'PWR_FLAG',{'1':net})
    # Convert BOM footprint IDs to the same pinned project IDs after copy plan saved.
    return sheets,bom,conns
