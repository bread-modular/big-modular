"""Electrical source of truth for the autonomous 9 V V1 (routed HRO carrier).

All symbol mappings below are manufacturer pin numbers. Datasheet source evidence
and engineering limits live in docs/engineering.md.
Only build_project.py emits these records, into an explicitly NEW candidate.
"""
import json
from sexp import nodes, one, atom
from pathlib import Path
from interface_contract import validate_reference

def populate(stock, ic, lib, root):
    sheets={};bom=[];conns={}
    R=stock('Device','R');C=stock('Device','C');L=stock('Device','L');D=stock('Device','D_Schottky')
    LED=stock('Device','LED');F=stock('Device','Fuse')
    USB=stock('HRO','TYPE_C_31_M_12');IDC=stock('Connector_Generic','Conn_02x08_Odd_Even')
    from hro_connector import symbol_from_usb, SYMBOL, FOOTPRINT, MPN, LCSC, DATASHEET, NOTE, PINS
    FLAG=stock('power','PWR_FLAG')
    def chip(name, defs, url):return ic(name,[(str(n),label,t,side) for n,label,t,side in defs],url)
    CH=chip('CH224A',[(1,'VHV','power_in','L'),(8,'VBUS_SENSE','input','L'),(7,'CC1','bidirectional','L'),(6,'CC2','bidirectional','L'),(4,'DP','bidirectional','L'),(5,'DM','bidirectional','L'),(11,'EP0_GND','power_in','L'),(2,'CFG2_SCL','input','R'),(3,'CFG3_SDA','bidirectional','R'),(9,'CFG1','input','R'),(10,'PG_N','open_collector','R')],'https://done.land/assets/files/ch224a_datasheet.pdf')
    EF=chip('TPS26600PWPR',[(1,'IN','power_in','L'),(2,'IN','passive','L'),(3,'UVLO','input','L'),(5,'OVP','input','L'),(7,'SHDN','input','L'),(9,'GND','power_in','L'),(8,'RTN','power_out','L'),(17,'EP_RTN','passive','L'),(4,'NC','no_connect','L'),(13,'NC','no_connect','L'),(15,'OUT','power_out','R'),(16,'OUT','passive','R'),(14,'FLT_N','open_collector','R'),(11,'ILIM','passive','R'),(12,'dVdT','passive','R'),(6,'MODE','input','R'),(10,'IMON','output','R')],'https://www.ti.com/lit/ds/symlink/tps2660.pdf')
    BUCK=chip('TPS54302DDCR',[(3,'VIN','power_in','L'),(5,'EN','input','L'),(1,'GND','power_in','L'),(6,'BOOT','passive','R'),(2,'SW','output','R'),(4,'FB','input','R')],'https://www.ti.com/lit/ds/symlink/tps54302.pdf')
    from ldo_design import symbols as ldo_symbols
    LDO_P,LDO_N=ldo_symbols(chip)
    from split_rail_design import symbol as boost_symbol
    BOOST=boost_symbol(chip)
    # E-Switch P021301 Rev B: 1 and 3 common, momentary closure to 2.
    # The existing footprint calls BOTH case solder lands MP (not contacts4/5).
    SW=chip('TL3340AF160QG',[(1,'COMMON','passive','L'),(3,'COMMON','passive','L'),(2,'NO','passive','R'),('MP','CASE','passive','R')],'https://configured-product-images.s3.amazonaws.com/2D/specs/TL3340AF160QG.pdf')
    # Retain the prior diagram's contact positions; no neighbouring wire churn.
    for unit in nodes(lib[SW],'symbol'):
        for pin in nodes(unit,'pin'):
            one(pin,'at')[2]=atom({'1':'5.08','3':'0','2':'5.08','MP':'-5.08'}[one(pin,'number')[1]])
    for name,title,notes in [
      ('01_input_protection','USB PD input','USB_VBUS -> F1 -> VIN9 (fused, may be 5 V during negotiation).\nCH224A fixed 9 V via 6.8k CFG1; CFG2/3 and PG unused. DP/DM shorted locally.\nVHV1 and VBUS8 directly VIN9 per WCH table4-1 / section6.1; EP0 -> footprint11.'),
      ('02_hardgate','Autonomous hardware window and retry','UV rising 7.878 V / OV rising 10.781 V nominal; hysteresis applies. RTN is NOT GND.\nSHDN self-biases internally; SW1 shorts SHDN to RTN while pressed, release resets/retries.\nR8 6.04k: 1.987 A nominal. MODE 402k: current limit with thermal latch-off. No PG/MCU permission.'),
      ('03_bucks','Independent +5V buck','U5 remains direct VPROT to P5, 250mA shared-budget reserve.\nU3 moved to direct negative IBB sheet04; no MID net. BOOT C36 to SW, EN floating.'),
      ('04_bipolar','Direct 9V negative IBB','SR2 U3 TPS54302: VIN=VPROT, GND=NRAW, SW through22u L1 to systemGND.\nUpper226.2k/bottom10k gives NRAW-14.07752V nominal. EN100k/(20k+2k) in NRAW domain.\nPrototype only: positive kick, loaded start, loop, transients and thermal tests pending.'),
      ('05_quiet_rails','Quiet bipolar post-regulators','TPS7A4700 ANY-OUT +12.000V; TPS7A3301 -12.020250V before IFB. Both EP21=GND.\n4/6/4/3 x22u IN+/OUT+/IN-/OUT-: bias-screened prototype; lot/stability and reverse/FB tests pending.\n1A IC ratings are NOT supply ratings. Never parallel another PSU; no bench qualification claimed.'),
      ('07_output_rails','Board output and power LED','J7 physical board wire landing: 1/2=-12, 3..8=GND, 9/10=+12, 11/12=+5; 13..16 NC.\nOne manual output harness, no second source. Never parallel another active PSU.\nSingle red D10: final P5 -> 1k -> anode2; cathode1 -> GND. +5 V presence only.')]:
        sheets[name]={'title':title,'notes':notes,'parts':[]}
    sheets['06_positive_boost']={'title':'Direct protected-9V positive boost','notes':'SR1: TPS55340 -> PRAW13.519V; schematic only. PCB unsynchronized.','parts':[]}
    # Catalog records are bounded strict-live snapshots, not procurement approval.
    catalog=json.loads((root/'docs/electrical-catalog.json').read_text())
    # Preserve inherited native metadata; live evidence is audited separately.
    catalog.update({k:v for k,v in json.loads((root/'docs/split-rail-catalog.json').read_text()).items() if k not in catalog})
    selected=json.loads((root/'docs/tps54302-selected-parts.json').read_text())
    catalog.update({p['code']:p for p in selected['selected_parts'] if p['code'] not in catalog})
    # Dated, approved L1/L4/L5 substitutions; historical catalog snapshots stay frozen.
    catalog.update(json.loads((root/'docs/inductor-substitution-catalog.json').read_text()))
    def add(sh,ref,kind,value,nets,fp='',code='',mpn='',note='',manual=False,onboard=True,manufacturer='',dnp=False):
        validate_reference(ref,'rail_indicator' if kind==LED and ref in ('D10','D11','D12') else '')
        if ref in conns:raise ValueError('Duplicate '+ref)
        dnp=dnp or ref=='C62'
        part=catalog.get(code,{})
        if code and mpn and part and mpn!=part['mpn']:raise ValueError((ref,mpn,part['mpn']))
        mpn=mpn or part.get('mpn','')
        revised=sh in ('04_bipolar','05_quiet_rails','06_positive_boost') or ref in ('L4','R12','R13','R14','R15','R60','R75','R76','R4','R8','R36','R77','R78','R79','R80','R81','R82','R9','R10','R18','R83','R84','R85','C6','C8','C9','C19','C37','C38','C68','C69','C70','C71','C72','R16','C1','C4','C5','C18','C16','C17','C10','C11','C12','C13','C14','J1','SW1')
        if revised:manufacturer=manufacturer or part.get('manufacturer','')
        note=note or 'Prototype candidate; qualify ratings, land pattern and operating corners.'
        footprint=('BigModular:'+fp.split(':')[-1]) if fp else ''
        d=dict(ref=ref,kind=kind,value=value,nets={str(k):v for k,v in nets.items()},mpn=mpn,lcsc=code,fp=footprint,note=note,onboard=onboard,manual=manual,dnp=dnp,manufacturer=manufacturer,datasheet=next((x[2] for x in lib[kind] if isinstance(x,list) and x[:2]==['property','Datasheet']),'') or ((part.get('datasheet_url') or '') if revised else ''))
        sheets[sh]['parts'].append(d);conns[ref]=d['nets']
        if not ref.startswith('#'):
            bom.append(dict(Reference=ref,Value=value,MPN=mpn,Footprint=fp,LCSC=code,Manufacturer=manufacturer or part.get('manufacturer',''),Classification='DNP' if dnp else part.get('classification','Manual' if manual else 'UNKNOWN'),DNP='yes' if dnp else 'no',Sourcing='DNP / not fitted; excluded purchasing and JLC' if dnp else 'Manual / excluded from JLC' if manual else 'Catalog candidate; no allocation/qualification guarantee' if part else 'UNRESOLVED sourcing',Notes=note,Block=sh))
        return d
    def rr(sh,ref,v,a,b,code='',note='',tolerance=None):
        defaults={'100':'C22775','470k':'C23178','82k':'C23254','5.6k':'C23189','220':'C22962','300k':'C23024','2k':'C22975','100k':'C25803','10k':'C25804','1k':'C21190','6.8k':'C23212','20k':'C4184','22k':'C31850','150k':'C22807','562k':'C23205','806k':'C23250','402k':'C23048','6.04k':'C25977','16.5k':'C22812','13.5k':'C861118','1.33M':'C482628'}
        tol=tolerance or ('0.1%' if code in ('C2912578','C149921','C20165687') or v=='13.5k' else '1%')
        return add(sh,ref,R,v+' '+tol,{'1':a,'2':b},'Resistor_SMD:R_0603_1608Metric',code or defaults.get(v,''),note=note)
    def cc(sh,ref,v,a,b,code='',size='0603_1608',note='',dnp=False):
        return add(sh,ref,C,v,{'1':a,'2':b},'Capacitor_SMD:C_'+size+'Metric',code or ('C14663' if v=='100n 50V X7R' else ''),note=note or 'Effective capacitance under DC bias and temperature must be verified; no automatic reuse approval.',dnp=dnp)
    def dd(sh,ref,k,a,note=''):return add(sh,ref,D,'SS34 40V',{'1':k,'2':a},'Diode_SMD:D_SMA','C8678',note=note or 'Rectifier polarity, reverse transients and thermal behavior require V1 validation.')
    a='01_input_protection'
    add(a,'J1',USB,MPN,PINS.copy(),'BigModular:'+FOOTPRINT,LCSC,mpn=MPN,note=NOTE+' Economy catalog candidate; front SMT contacts with four plated shell slots requiring explicit supplier solder-process review; not quote approval.',manual=False,manufacturer='HRO (Korean Hroparts Elec)')
    add(a,'F1',F,'3A 32V candidate',{'1':'USB_VBUS','2':'VIN9'},'Fuse:Fuse_1206_3216Metric','C14165',note='0466003.NRHF catalog candidate only; source/fuse/eFuse thermal and I2t coordination NOT qualified.')
    add(a,'U1',CH,'CH224A',{'1':'VIN9','8':'VIN9','2':None,'3':None,'4':'PD_D_SHORT','5':'PD_D_SHORT','6':'CC2','7':'CC1','9':'PD_CFG','10':None,'11':'GND'},'Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm','C42459160',note='WCH V2 table4-1; VHV1 is high-voltage input. EP0 mapped to pad11. Section7.1 typo resolved against pin table4-1, app6.1 and rating8.1.1; see engineering note.')
    cc(a,'C1','1u 50V X7R','VIN9','GND',code='C28323',size='0805_2012');rr(a,'R2','6.8k','PD_CFG','GND')
    a='02_hardgate'
    add(a,'U2',EF,'TPS26600PWPR',{'1':'VIN9','2':'VIN9','3':'UV_EN','4':None,'5':'OV_SET','6':'EF_MODE','7':'EF_SHDN','8':'RTN','9':'GND','10':None,'11':'ILIM','12':'SLEW','13':None,'14':None,'15':'VPROT','16':'VPROT','17':'RTN'},'Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm','C544399')
    for ref,v,x,y in [('R5','100k','UV_EN','RTN'),('R6','806k','VIN9','OV_SET'),('R7','100k','OV_SET','RTN'),('R31','10k','VPROT','GND')]:rr(a,ref,v,x,y)
    # Exact Basic series sums; independent 1% corners preserve the former bounds.
    # New refs are above all occupied/retired references. RTN must never become GND.
    for ref,v,x,y in [('R4','470k','VIN9','UV_SER_1'),('R77','82k','UV_SER_1','UV_SER_2'),('R78','10k','UV_SER_2','UV_EN'),
                       ('R8','5.6k','ILIM','ILIM_SER_1'),('R79','220','ILIM_SER_1','ILIM_SER_2'),('R80','220','ILIM_SER_2','RTN'),
                       ('R36','300k','EF_MODE','MODE_SER_1'),('R81','100k','MODE_SER_1','MODE_SER_2'),('R82','2k','MODE_SER_2','RTN')]:
        rr(a,ref,v,x,y,note='Basic/Economy series member: R4+R77+R78=562k; R8+R79+R80=6.04k; R36+R81+R82=402k. Each 1%, 100ppm/K, 100mW/75V. See basic-passives-disposition.md for independent corners, fault/derating and local RTN review.')
    cc(a,'C2','100n 50V X7R','VIN9','GND');cc(a,'C3','100n 50V X7R','SLEW','RTN');cc(a,'C4','10u 50V X5R','VPROT','GND',code='C13585',size='1206_3216')
    add(a,'SW1',SW,'TL3340AF160QG',{'1':'EF_SHDN','3':'EF_SHDN','2':'RTN','MP':None},'BigModular:SW_TL3340AF160QG_HandSolder',code='C2886925',mpn='TL3340AF160QG',manual=False,note='P021301 Rev B contacts1+3 common; contact2 RTN. Press disables eFuse; release retries latch-off subject to UV/OV. Internal SHDN pullup only; no downstream EN or external supply load. Case MP floating. Extended/Economy catalog candidate; SMT J-leads/case paste retained. No supplier process/quote approval.')
    a='03_bucks'
    for u,prefix,out,Lref,Cs,Rt,Rb,rv,base in [('U5','FIVE','P5','L4',['C18','C19','C20','C36'],'R17','R18','13k',1)]:
        add(a,u,BUCK,'TPS54302DDCR',{'1':'GND','2':prefix+'_SW','3':'VPROT','4':prefix+'_FB','5':None,'6':prefix+'_BOOT'},'Package_TO_SOT_SMD:SOT-23-6','C311983')
        add(a,Lref,L,'6.8uH 20% shielded',{'1':prefix+'_SW','2':out},'BigModular:L_SLO1040H6R8MTT','C207852',manufacturer='Sunltech',note='Sunltech SLO1040H6R8MTT; 6.8uH +/-20%; DCR22mohm typ/25mohm max. Isat typ10A at approx20% L drop/25C; Idc typ7A at approx40C rise. Height4.0mm max. Land engineering-defined, pending vendor drawing: 2 rectangular pads3.5(X)x4.0(Y)mm, 5.0mm gap, 12.0mm overall. Stock4991 observed2026-10-17, not reserved or guaranteed. No guaranteed hot-lot minimum; PCB fit/stack/saturation/thermal qualification pending.')
        cc(a,Cs[0],'22u 25V X5R','VPROT','GND',code='C12891',size='1206_3216');cc(a,Cs[1],'22u 25V X5R',out,'GND','C12891','1206_3216');cc(a,Cs[2],'100n 50V X7R','VPROT','GND');cc(a,Cs[3],'100n 50V X7R',prefix+'_BOOT',prefix+'_SW')
        cc(a,'C37' if u=='U3' else 'C38','22u 25V X5R',out,'GND','C12891','1206_3216')
        cc(a,'C68' if u=='U3' else 'C69','22u 25V X5R','VPROT','GND','C12891','1206_3216',note='Local buck VIN bank: two C12891 per IC; typical-data screen 10.664uF at9.45V, not guaranteed. Remote C4 excluded; input ringing/ripple/startup bench gates remain.')
        for ref in (['C70','C71'] if u=='U3' else ['C72']):
            cc(a,ref,'22u 25V X5R',out,'GND','C12891','1206_3216',note='Local buck output bank: C6+C70+C71 MID; C19+C38+C72 P5. Three C12891 screen27.6315uF at5.5V; remote C37 excluded. Typical-data screen only; loop/load-step bench qualification pending.')
        rr(a,Rt,'100k',out,prefix+'_FB',code='C25803',note='Basic 1%, 100ppm/K; MID/P5 use 100k/(13k+510R), nominal5.007547V. Full independent reference/tolerance/TCR bounds in basic-swaps-checkpoint.md; not a +/-5% output guarantee.' if u=='U3' else 'Independent +5 V divider.')
        rr(a,Rb,rv,prefix+'_FB',prefix+'_DIV_LO',code='C22797',tolerance='1%',note='Basic13k plus510R series bottom leg; retain nominal5V rather than13k alone. 1%,100ppm/K; see basic-swaps-checkpoint.md.')
        rr(a,'R84' if u=='U3' else 'R85','510',prefix+'_DIV_LO','GND',code='C23193',note='Basic510R series with R10/R18; total13.51k bottom leg. 1%,100ppm/K,100mW/75V; dated039 observation lacks raw provenance, release recheck required.')
    from sr2_design import populate as populate_negative
    populate_negative(add,rr,cc,dd,L,BUCK)
    from split_rail_design import populate as populate_boost
    populate_boost(add,rr,cc,dd,L,R,BOOST)
    from ldo_design import populate as populate_ldos
    populate_ldos(add,rr,cc,dd,R,LDO_P,LDO_N)
    a='07_output_rails'
    rr(a,'R32','1k','P5','LED_P_A',note='Ordinary final +5V power indicator only: 1k series limits current, no controller or blink. Manual3mm D10 cathode to GND. At5.5V and Vf=0, resistor power<31mW with1% tolerance; exact LED brightness/MPN still pending.')
    add(a,'D10',LED,'RED 3mm / +5V POWER / DNP',{'1':'GND','2':'LED_P_A'},'BigModular:LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge',dnp=True,note='DNP by user: not purchased or fitted. Retain physical footprint and indicator circuit: P5 -> R32 1k -> anode2; cathode1 GND. No automatic blink, no external control, not proof all rails are healthy. Top-cluster D10 hole/formed-lead envelope; no LED procurement requested.')
    a='07_output_rails'
    n={str(i):('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None) for i in range(1,17)}
    add(a,'J7',IDC,'Manual IDC wire landing',n,'BigModular:WireLanding_2x08_P2.54mm',manual=True,note='ON-CARRIER numbered solder lands, not an extra purchasable box header. Physical output cable boundary; single output, never another active source.')
    for ref,net in [('R25','P12'),('R26','N12'),('R27','P5')]:rr(a,ref,'10k',net,'GND',note='Bleed provision only; does not prove rail discharge time or prevent backfeed.')
    # True passive-source declarations for ERC; no arbitrary error exclusions.
    for ref,sh,net in [('#FLG01','01_input_protection','GND'),('#FLG02','01_input_protection','USB_VBUS'),('#FLG03','01_input_protection','VIN9'),('#FLG07','04_bipolar','NRAW'),('#FLG08','03_bucks','P5')]:
        add(sh,ref,FLAG,'PWR_FLAG',{'1':net})
    add('06_positive_boost','#FLG09',FLAG,'PWR_FLAG',{'1':'PRAW'},note='Real passive L5/D29 rectified source; not an artificial supply. Existing dormant source flag stays separate.')
    # Convert BOM footprint IDs to the same pinned project IDs after copy plan saved.
    return sheets,bom,conns
