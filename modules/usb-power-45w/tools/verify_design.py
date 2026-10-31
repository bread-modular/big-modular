"""S6 native hierarchy/circuit verifier. Read-only; run native ERC separately.

Checks exact components, physical pad sets, pin memberships, NCs and fields;
manufacturer pin roles; isolation/LED/reset topology; bounded arithmetic; and a
digital latch model derived from native gate pin nets. Not SPICE or bench proof.
"""
import argparse
import itertools
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from circuit45 import circuit
from build_schematic import FP
from sexp import parse, nodes, one


def load_xml(path):
    root=ET.parse(path).getroot()
    comps={c.get('ref'):c for c in root.findall('components/comp')}
    nets={n.get('name'):{(p.get('ref'),p.get('pin')) for p in n.findall('node')} for n in root.findall('nets/net')}
    return root,comps,nets,{pin:name for name,ps in nets.items() for pin in ps}


def verify(netlist,hardware,previous=None):
    root,comps,nets,pins=load_xml(netlist)
    parts={p['ref']:p for p in circuit() if not p['ref'].startswith('#')}
    assert set(parts)==set(comps),'Native/table component mismatch'
    expected={}; netids={}
    for ref,p in parts.items():
        assert comps[ref].findtext('value')==p['value'],(ref,'value')
        assert comps[ref].findtext('footprint')=='USBPOWER45:'+FP[p['fp']],(ref,'footprint')
        for field,val in p['fields'].items():
            assert comps[ref].findtext(f'fields/field[@name="{field}"]')==val,(ref,field)
        f=parse((hardware/'USBPOWER45.pretty'/(FP[p['fp']]+'.kicad_mod')).read_text())
        assert {str(x[1]) for x in nodes(f,'pad') if x[1]}==set(p['pins']),(ref,'pad set')
        for num,net in p['pins'].items():
            key=(ref,num)
            if net is None:
                assert 'unconnected-' in pins[key] and nets[pins[key]]=={key},(key,'NC')
            else:expected.setdefault(net,set()).add(key)
    for net,ps in expected.items():
        match=[n for n,actual in nets.items() if actual==ps]
        assert len(match)==1,(net,'exact pin membership')
        if not net.startswith('_'):assert match[0].split('/')[-1]==net,(net,'name')
        netids[net]=match[0]
    def n(ref,pin):return pins[(ref,str(pin))]
    def isnet(ref,pin,net):assert n(ref,pin)==netids[net],(ref,pin,net)
    def value(ref):
        s=comps[ref].findtext('value')
        return float(s[:-1])*{'k':1e3,'u':1e-6,'n':1e-9}[s[-1]] if s[-1] in 'kun' else float(s)
    # Independently specified manufacturer/function pin expectations.
    crit={
      'U5':{1:'EF_IN',2:'EF_IN',3:'EF_IN',6:'EF_IN',7:'EF_UV',8:'EF_OV',9:'GND',10:'EF_DVDT',11:'EF_ILM',12:'GND',13:'RUN',14:'EF_IMON',15:'MAIN_OK',16:'MAIN_OK',18:'VIN',19:'VIN',20:'VIN',21:'GND'},
      'U6':{1:'P12_RAW',2:'P12_RAW',3:'P12_RAW',6:'P12_RAW',7:'P12_UV',8:'P12_OV',9:'GND',10:'P12_DVDT',11:'P12_ILIM',13:'RUN',15:'P12_OK',16:'P12_OK',18:'+12V',19:'+12V',20:'+12V',21:'GND'},
      'U7':{1:'P5_RAW',2:'P5_RAW',3:'P5_RAW',6:'P5_RAW',7:'P5_UV',8:'P5_OV',9:'GND',10:'P5_DVDT',11:'P5_ILIM',13:'RUN',15:'P5_OK',16:'P5_OK',18:'+5V',19:'+5V',20:'+5V',21:'GND'},
      'U8':{1:'N_VCC',2:'N_UV',3:'N_OV',4:'N_PWR',5:'N12_RAW',6:'N_TIMER',7:'N_SENSE_PIN',8:'N_GATE',9:'N_OUT_PIN',10:'N_PGD'},
      'Q4':{1:'N_GATE',2:'-12V',3:'N_SENSE'},
      'U9':{1:'V3V3',4:'GND',5:'VPD',8:'VPD',9:'GND'},
      'U10':{1:'RESET_N',2:'GND',3:'POR_SENSE',5:'RESET_BTN_N',6:'V3V3'},
      'U11':{1:'START_READY',2:'GND',3:'START_SENSE',4:'START_CT',5:'RESET_N',6:'V3V3'},
      'U12':{1:'RESET_N',2:'V3V3',3:'START_READY',4:'V3V3',5:'ARMED',7:'GND',8:'NOT_FAULT',9:'FAULT_LATCH',10:'V3V3',11:'FAULT_CLK',12:'V3V3',13:'RESET_N',14:'V3V3'},
      'U16':{1:'NEG_OFF_LED',2:'NEG_OFF_K',3:'N12_RAW',4:'N_UV'},
      'U17':{1:'N_PGD_LED',2:'N_PGD',3:'GND',4:'N12_STATUS'},
      'U18':{1:'P12_OK',2:'P5_OK',3:'V3V3',4:'REF_GOOD',5:'MON_P5',6:'REF_GOOD',7:'MON_P12',8:'MON_N12',9:'REF_GOOD',10:'REF_GOOD',11:'MON_20',12:'GND',13:'V20_OK',14:'N12_STATUS'},
      'U19':{2:'N12_STATUS',3:'GND',4:'N12_OK',5:'V3V3'},
      'SW1':{1:'RESET_BTN_N',3:'RESET_BTN_N',2:'GND'},
      'D10':{1:'EF_IN',2:'VPD'},'Q2':{1:'PD_SENSE',2:'VPD_U1',3:'PD_BASE'},
      'U2':{2:'MAIN_OK'},'U3':{2:'MAIN_OK'},'U4':{1:'N12_RAW',9:'N12_RAW'},
      'Q10':{1:'RUN',2:'GND',3:'LED_RETURN'},
    }
    for ref,m in crit.items():
        for pin,net in m.items():isnet(ref,pin,net)
    for ref in ['U5','U6','U7']:
        assert comps[ref].findtext('fields/field[@name="MPN"]')=='TPS16630PWPR'
        assert comps[ref].findtext('fields/field[@name="LCSC"]')=='C1849461'
    for ref in ['U6','U7']:assert 'unconnected-' in n(ref,12),'MODE must be local latch-off'
    for ref in ['J2','J3']:
        for pin in range(3,9):isnet(ref,pin,'GND')
        for pin in (1,2):isnet(ref,pin,'-12V')
        for pin in (9,10):isnet(ref,pin,'+12V')
        for pin in (11,12):isnet(ref,pin,'+5V')
    assert n('R48',1)==n('R49',1)==n('Q4',3)
    assert n('R48',2)==n('R49',2)==n('U8',5)
    for d,r,q,gate in [('D8','R22','Q6','MAIN_LED_OK'),('D16','R86','Q7','P12_OK'),('D17','R87','Q8','P5_OK'),('D18','R88','Q9','N12_OK')]:
        isnet(r,1,'V3V3');assert n(r,2)==n(d,2) and n(d,1)==n(q,3)
        isnet(q,1,gate);isnet(q,2,'LED_RETURN')
    assert n('U9',8)!=n('U5',18),'Latch supply must survive main switch off'
    # Native symbol pin-name checks against manufacturer numbering (separate from net table).
    libparts={p.get('part'):{x.get('num'):x.get('name') for x in p.findall('pins/pin')} for p in root.findall('libparts/libpart')}
    assert libparts['BCX53_NXP']=={'1':'E','2':'C','3':'B'}
    assert libparts['FQD13N06L']=={'1':'G','2':'D','3':'S'}
    for k,v in {'5':'1Q','8':'2Q_N','9':'2Q','13':'2CLR_N'}.items():assert libparts['HC74_DUAL'][k]==v
    for k,v in {'1':'VCC','5':'VEE','7':'SENSE','8':'GATE','9':'OUT'}.items():assert libparts['LM5067MM'][k]==v
    files=list(hardware.glob('*.kicad_sch'));assert len(files)==8,('Hierarchy sheet count',len(files))
    assert len(nodes(parse((hardware/'usb-power-45w.kicad_sch').read_text()),'sheet'))==7
    for f in files:
        for sym in nodes(parse(f.read_text()),'symbol'):
            ref=next(p[2] for p in nodes(sym,'property') if p[1]=='Reference')
            if ref.startswith('TP'):
                assert one(sym,'in_bom')[1]=='no' and one(sym,'in_pos_files')[1]=='no' and one(sym,'on_board')[1]=='yes'

    factors=(.99*.99,1.01*1.01)
    def current(r):
        nom=18000/r;return {'nominal_A':nom,'screened_min_A':nom*.9/factors[1],'screened_max_A':nom*1.1/factors[0]}
    main=current(value('R5')+value('R29'));assert 4.18<main['nominal_A']<4.19
    assert main['screened_max_A']+.05<4.75
    pos=current(value('R34'));assert value('R34')==value('R43')==6800
    assert pos['screened_max_A']<3 and pos['screened_min_A']>2.3
    rs=1/(1/value('R48')+1/value('R49'));assert abs(rs-.05)<1e-9
    neg={'nominal_A':.05/rs,'screened_min_A':.044/(rs*factors[1]),'screened_max_A':.056/(rs*factors[0]),
         'typical_bias_offset_A':6e-6*value('R89')/rs,'nominal_FET_power_W':value('R56')/(142000*rs)}
    assert neg['screened_max_A']<1.15 and neg['nominal_FET_power_W']<3.2
    ref=3.3*value('R74')/(value('R73')+value('R74'))
    mon={'P12_V':ref*(1+value('R75')/value('R76')),'P5_V':ref*(1+(value('R77')+value('R78'))/value('R79')),
         'N12_magnitude_V':3.3*value('R82')/(value('R80')+value('R81'))-ref*(1+value('R82')/(value('R80')+value('R81'))),
         'input_V':ref*(1+value('R83')/value('R84'))}
    por=.405*(1+(value('R65')+value('R91'))/value('R66'))
    por_max=.411*(1+(value('R65')+value('R91'))*factors[1]/(value('R66')*factors[0]))
    assert por_max<3.3*.98,'POR threshold could prevent a valid LDO starting'
    t_start=value('C49')*1e9/175+.0005
    t_insert=4*value('C44')/6e-6; t_fault=4*value('C44')/95e-6
    # Conditional capacitor envelope, not invented measured DC-bias guarantees.
    assert t_start*.6*.7 > 4.16*value('C44')*1.25/2.5e-6+.1

    # Digital gate model uses native connectivity, not a separate imagined wiring.
    gates=[('U13',1,2,3),('U13',4,5,6),('U13',9,10,8),('U13',12,13,11)]
    def comb(inputs,qa,qb):
        s={netids[k]:v for k,v in inputs.items()};s[netids['V3V3']]=True;s[netids['GND']]=False
        s[n('U12',5)]=qa;s[n('U12',9)]=qb;s[n('U12',8)]=not qb
        for _ in range(8):
            s[n('U19',4)]=s[n('U19',2)]
            for u,a,b,y in gates:s[n(u,y)]=bool(s.get(n(u,a),False) and s.get(n(u,b),False))
            s[n('U14',6)]=not all(s.get(n('U14',p),False) for p in [1,2,4,5])
            s[n('U14',8)]=not all(s.get(n('U14',p),False) for p in [9,10,12,13])
            # DC/settled filter model: not an analog timing simulation.
            assert n('R72',1)==n('U14',6) and n('R72',2)==n('C51',1)==n('U15',2)
            s[n('U15',4)]=s[n('R72',1)]
        return s
    cases=0
    for reset,arm,fault,mainok,p12,p5,n12,v20 in itertools.product([False,True],repeat=8):
        i={'RESET_N':reset,'MAIN_OK':mainok,'P12_OK':p12,'P5_OK':p5,'N12_STATUS':n12,'V20_OK':v20,'START_READY':False}
        s=comb(i,arm,fault);run=reset and not fault
        assert s[netids['RUN']]==run and s[netids['NOT_RUN']]==(not run)
        assert s[netids['FAULT_CLK']]==(arm and not(mainok and v20 and p12 and p5 and n12))
        for q,want in [('Q6',mainok and v20),('Q7',p12),('Q8',p5),('Q9',n12)]:
            assert (run and s[n(q,1)])==(run and want)
        cases+=1
    # A persistent fault at the end of startup must trip; bad voltage after
    # arming cannot clear the arm latch; a fault cannot self-restart the system.
    seq=[]
    for missing in ['MAIN_OK','P12_OK','P5_OK','N12_STATUS','V20_OK']:
        inp={k:True for k in ['RESET_N','MAIN_OK','P12_OK','P5_OK','N12_STATUS','V20_OK','START_READY']}
        inp[missing]=False
        s=comb(inp,False,False);assert s[netids['RUN']] and not s[netids['FAULT_CLK']]
        s=comb(inp,True,False);assert s[netids['FAULT_CLK']]
        s=comb(inp,True,True);assert not s[netids['RUN']]
        inp[missing]=True;inp['START_READY']=False
        s=comb(inp,True,True);assert not s[netids['RUN']]
        inp['RESET_N']=False;s=comb(inp,False,False);assert not s[netids['RUN']]
        seq.append(missing)
    report={'status':'S6_schematic_checks_not_bench_qualification','components':len(comps),'nets_including_NC':len(nets),'sheets':len(files),
            'exact_field_pin_NC_pad_parity':True,'digital_combinations_checked':cases,'persistent_fault_reset_scenarios':seq,
            'main_limit':main,'normal_auxiliary_reserve_A':.05,'positive_rail_limit':pos,'negative_rail_limit':neg,
            'nominal_voltage_valid_thresholds':mon,'logic_POR_nominal_V':por,'logic_POR_high_screen_V':por_max,
            'startup_qualification_typ_s':t_start,'negative_insertion_typ_s':t_insert,'negative_local_fault_typ_s':t_fault,
            'warnings':['Current/voltage arithmetic is conditional on tolerances and datasheet test conditions; not a guaranteed board rating.',
                        'Digital truth checks do not model analog propagation, optocoupler CTR/aging, DC-bias or MOSFET transients.',
                        'Shared inspection model-variable blocker, inherited Extended capacitors and unqualified supplier documents remain separate gates.'],
            'order_ready':False}
    if previous:
        _,old,_,oldpins=load_xml(previous)
        assert set(old)-set(comps)=={'R6','R7','R25'}
        for ref in old:
            if ref not in comps:continue
            assert old[ref].findtext('footprint')==comps[ref].findtext('footprint'),(ref,'S5 package preservation')
            rename={'D8':'MAIN LED','TP5':'MAIN_OK','TP6':'FAULT_LATCH'}
            assert comps[ref].findtext('value')==rename.get(ref,old[ref].findtext('value')),(ref,'S5 value or explicit indicator-name delta')
        changed={'U5','U2','U3','TP5','TP6','SW1','D8','R22'}
        count=0
        for key,oldnet in oldpins.items():
            ref,pin=key
            if ref not in comps or ref in changed:continue
            if 'unconnected-' in oldnet:assert 'unconnected-' in pins[key];continue
            before=oldnet.split('/')[-1]
            if ref not in {'J2','J3'}:before={'+12V':'P12_RAW','+5V':'P5_RAW','-12V':'N12_RAW'}.get(before,before)
            assert pins[key].split('/')[-1]==before,(key,'S5 connectivity beyond approved raw-net rename',oldnet,pins[key])
            count+=1
        # Changed enable nodes are intentional; the remaining converter pins still match exactly.
        for ref in ['U2','U3']:
            for (r,p),oldnet in oldpins.items():
                if r==ref and p!='2':assert pins[(r,p)].split('/')[-1]==oldnet.split('/')[-1]
        report['S5_unchanged_connections_checked']=count
        report['intentional_removed_refs']=['R6','R7','R25']
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--netlist',type=Path,required=True);ap.add_argument('--hardware',type=Path,required=True)
    ap.add_argument('--previous-netlist',type=Path,help='Committed S5 XML for preservation checks')
    a=ap.parse_args();print(json.dumps(verify(a.netlist,a.hardware,a.previous_netlist),indent=2))
