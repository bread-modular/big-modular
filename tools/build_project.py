#!/usr/bin/env python3
"""Generate a review-only KiCad engineering prototype. Never creates copper routes/zones."""
from pathlib import Path
import sys, json, uuid, copy, csv, math, shutil, argparse
sys.path.insert(0,str(Path(__file__).parent))
from sexp import parse,dump,nodes,one,walk,atom
ROOT=Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--schematic-only', action='store_true', help='Render a NEW schematic candidate only; never regenerate boards, BOM, libraries or audit.')
parser.add_argument('--output', type=Path, help='Required NEW directory for --schematic-only; copies existing project/library context.')
args = parser.parse_args()
if args.schematic_only != bool(args.output):
    parser.error('--schematic-only and --output must be used together')
HW = args.output.resolve() if args.schematic_only else ROOT/'hardware'
if args.schematic_only:
    HW.mkdir(parents=True, exist_ok=False)
else:
    HW.mkdir(exist_ok=True)
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL,'big-modular/revA/'+s))
def q(s): return json.dumps(str(s))
LIB={}; CACHE={}
PINNED = ({s[1]: s for s in nodes(parse((ROOT/'hardware/BigModular.kicad_sym').read_text()), 'symbol')}
          if args.schematic_only else {})
def stock(lib,name):
    if args.schematic_only:
        kind = lib+'_'+name
        LIB[kind] = copy.deepcopy(PINNED[kind])
        return kind
    if lib not in CACHE:
        CACHE[lib]={s[1]:s for s in nodes(parse(Path('/usr/share/kicad/symbols',lib+'.kicad_sym').read_text()),'symbol')}
    def resolve(n):
        s=copy.deepcopy(CACHE[lib][n]); parent=one(s,'extends')
        if parent:
            base=resolve(parent[1]); props={p[1]:p for p in nodes(base,'property')}
            props.update({p[1]:p for p in nodes(s,'property')})
            s=[s[0],s[1]]+[x for x in base[2:] if not(isinstance(x,list) and x[0]=='property')]+list(props.values())
        return s
    s=resolve(name); old=s[1]; new=lib+'_'+name; s[1]=new
    for sub in nodes(s,'symbol'):
        # Inheritance geometry uses its parent's name; only unit suffix is significant.
        suffix='_'.join(sub[1].split('_')[-2:]); sub[1]=new+'_'+suffix
    LIB[new]=s; return new

def ic(name,pins,url):
    # (number, pin name, electrical type, side). One real pin per entry, including exposed pad.
    left=[p for p in pins if p[3]=='L']; right=[p for p in pins if p[3]=='R']; n=max(len(left),len(right))
    h=(n+1)*2.54
    parts=[f'(symbol {q(name)} (pin_names (offset 0.7)) (in_bom yes) (on_board yes)',
      '(property "Reference" "U" (at 0 3 0) (effects (font (size 1.27 1.27))))',
      f'(property "Value" {q(name)} (at 0 0 0) (effects (font (size 1.27 1.27))))',
      f'(property "Datasheet" {q(url)} (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
      f'(symbol {q(name+"_0_1")} (rectangle (start -10.16 {h/2}) (end 10.16 {-h/2}) (stroke (width 0.254) (type default)) (fill (type background))))',
      f'(symbol {q(name+"_1_1")}']
    for side,pp in [('L',left),('R',right)]:
        for j,(num,label,typ,_) in enumerate(pp):
            x=-15.24 if side=='L' else 15.24; y=(n-1)*1.27-j*2.54; a=0 if side=='L' else 180
            parts.append(f'(pin {typ} line (at {x} {y} {a}) (length 5.08) (name {q(label)} (effects (font (size 1 1)))) (number {q(num)} (effects (font (size 1 1)))))')
    parts+=['))']; LIB[name]=parse(''.join(parts)); return name

R=stock('Device','R'); C=stock('Device','C'); L=stock('Device','L'); D=stock('Device','D_Schottky'); F=stock('Device','Fuse'); JP=stock('Jumper','Jumper_2_Open'); USB=stock('Connector','USB_C_Receptacle_USB2.0_16P'); IDC=stock('Connector_Generic','Conn_02x08_Odd_Even'); FLAG=stock('power','PWR_FLAG')
PNP=stock('Transistor_BJT','MMBT3906'); CH=stock('Interface_USB','CH224K'); EF=stock('Power_Management','TPS26600PWP'); BUCK=stock('Regulator_Switching','TPS62160DSG'); BI=stock('Regulator_Switching','TPS65131RGE')
ldopins=[('8','IN','power_in','L'),('5','EN','input','L'),('6','NR/SS','passive','L'),('3','NC','no_connect','L'),('7','DNC','no_connect','L'),('1','OUT','power_out','R'),('2','FB','input','R'),('4','GND','power_in','R'),('9','EP_GND','passive','R')]
LP=ic('TPS7A4901DGNR',ldopins,'https://www.ti.com/lit/ds/symlink/tps7a49.pdf'); LN=ic('TPS7A3001DGNR',ldopins,'https://www.ti.com/lit/ds/symlink/tps7a30.pdf')
# Custom symbol explicitly corrects pin 4 of TPS62125 (EN_hys, NOT AGND).
B65=ic('TPS62125DSGR',[('2','VIN','power_in','L'),('3','EN','input','L'),('4','EN_hys','open_collector','L'),('1','GND','power_in','L'),('9','EP_GND','passive','L'),('7','SW','output','R'),('6','VOS','input','R'),('5','FB','input','R'),('8','PG','open_collector','R')],'https://www.ti.com/lit/ds/symlink/tps62125.pdf')
# TPS62125 pin 6 VOS checked against local TI datasheet during design; see docs/design-review.md.

SHEETS={}; BOM=[]; CONNS={}
def sheet(name,title,notes): SHEETS[name]={'title':title,'notes':notes,'parts':[]}
def add(sh,ref,kind,value,nets,x,y,mpn='',lcsc='',fp='',note='',onboard=True):
    s=LIB[kind]; defaults={p[1]:p[2] for p in nodes(s,'property')}
    if not fp: fp=defaults.get('Footprint','')
    if kind==R and not fp: fp='Resistor_SMD:R_0603_1608Metric'
    if kind==C and not fp: fp='Capacitor_SMD:C_1206_3216Metric'
    d=dict(ref=ref,kind=kind,value=value,nets={str(k):v for k,v in nets.items()},x=round(round(x/1.27)*1.27,5),y=round(round(y/1.27)*1.27,5),mpn=mpn,lcsc=lcsc,fp=fp,note=note,onboard=onboard)
    SHEETS[sh]['parts'].append(d); CONNS[ref]=d['nets']
    if not ref.startswith('#'): BOM.append(dict(Reference=ref,Value=value,MPN=mpn,Footprint=fp,LCSC=lcsc,Sourcing='LCSC ID verified; stock NOT verified' if lcsc else 'Candidate/specification only; procurement review required',Notes=note,Block=sh))
    return d
COUNTS={'R':0,'C':0,'L':0,'D':0}
def passive(sh,kind,val,n1,n2,x,y,**kw):
    letter={R:'R',C:'C',L:'L',D:'D'}[kind]; COUNTS[letter]+=1
    return add(sh,letter+str(COUNTS[letter]),kind,val,{'1':n1,'2':n2},x,y,**kw)
def r(sh,val,a,b,x,y,**kw):return passive(sh,R,val,a,b,x,y,**kw)
def c(sh,val,a,b,x,y,**kw):return passive(sh,C,val,a,b,x,y,**kw)
def diode(sh,val,k,a,x,y,**kw):return passive(sh,D,val,k,a,x,y,**kw)

sheet('01_input','PD-only input / hardware interlock','5 V is negotiation housekeeping ONLY. No rail operation at 5 V. PG AND 9 V window AND RUN required.\nCH224K PG is generic power-good: explicit PDO/current proof remains a FABRICATION BLOCKER.')
n={p:('VBUS_RAW' if p in ['A4','A9','B4','B9'] else 'GND' if p in ['A1','A12','B1','B12','SH'] else 'CC1' if p=='A5' else 'CC2' if p=='B5' else None) for p in ['A1','A4','A5','A6','A7','A8','A9','A12','B1','B4','B5','B6','B7','B8','B9','B12','SH']}
add('01_input','J1',USB,'USB4105-GF-A',n,42,65,mpn='USB4105-GF-A',fp='BigModular:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',note='Only electrical footprint placed. Drawing Rev B: axis 1.73 mm above PCB top.')
add('01_input','U1',CH,'CH224K',{'1':'PD_VDD','2':None,'3':None,'4':'PD_D_SHORT','5':'PD_D_SHORT','6':'CC2','7':'CC1','8':None,'9':'PD_CFG','10':'PD_PG_N','11':'GND'},125,65,mpn='CH224K',lcsc='C970725',note='WCH v1F fig6.1/6.3; datasheet EP0 maps to library pad11. DP/DM short locally, isolated from USB data.')
r('01_input','1k 1% >=0.5W','VBUS_FUSED','PD_VDD',205,50,fp='Resistor_SMD:R_2010_5025Metric',note='CH224K supply resistor: at 21V fault, VDD>=2.4V, 1% low R, dissipates <=0.350W. Select a real >=0.5W 2010 part, derate at enclosure temperature.'); c('01_input','1u 50V X7R','PD_VDD','GND',270,50); r('01_input','6.8k 1%','PD_CFG','GND',335,50); r('01_input','100k','PD_VDD','PD_PG_N',335,92)
add('01_input','F1',F,'500mA 32V fuse',{'1':'VBUS_RAW','2':'VBUS_FUSED'},42,130,note='Unselected candidate: 32V rating covers steady 20/21V only; interrupt/surge ratings, time-current and source coordination UNQUALIFIED. Not USB current authorization.')
# D1 was the unsafe upstream SMBJ12CA. Reserve its reference so downstream D2.. remain stable.
# Do NOT populate a different TVS until its surge clamp, fuse, connector and eFuse limits are qualified.
COUNTS['D']=1
c('01_input','100n 50V','VBUS_FUSED','GND',270,130,note='TPS26600 local bypass only. Not an ESD/surge clamp; effective capacitance and hot-plug transients unverified.')
add('01_input','U2',EF,'TPS26600PWPR',{'1':'VBUS_FUSED','2':'VBUS_FUSED','3':'UV_EN','4':None,'5':'OV_SET','6':'RTN','7':'EF_ENABLE','8':'RTN','9':'GND','10':None,'11':'ILIM','12':'SLEW','13':None,'14':None,'15':'VPROT','16':'VPROT','17':'RTN'},70,205,mpn='TPS26600PWPR',lcsc='C544399',note='UV rising 7.878V nominal, OVP 10.781V nominal. SHDN low=OFF; PG-permit through JP1 only. RTN must NOT be externally shorted to GND.')
add('01_input','JP1',JP,'RUN / default OPEN',{'1':'PG_PERMIT','2':'EF_ENABLE'},165,190,note='Series permission only; cannot override PG or voltage window. Default OPEN. Not contract proof.')
r('01_input','562k 1%','VBUS_FUSED','UV_EN',230,180); r('01_input','100k 1%','UV_EN','RTN',295,180)
r('01_input','806k 1%','VBUS_FUSED','OV_SET',360,180); r('01_input','100k 1%','OV_SET','RTN',360,225)
r('01_input','40.2k 1%','ILIM','RTN',165,235); c('01_input','100n 50V','SLEW','RTN',230,235); c('01_input','10u 25V X7R','VPROT','GND',295,235)

sheet('02_intermediate','4.016 V intermediate supply / startup','TPS62160: 3..17 V input, nominal 2.25 MHz DCS control, internal compensation.\n2.2uH / 22uF LC follows datasheet baseline. Require effective output C within datasheet stability range.\nPG releases converter enables only after intermediate rail rises. PWM frequency is not an audio-noise guarantee.')
add('02_intermediate','U3',BUCK,'TPS62160DSGR',{'1':'GND','2':'VPROT','3':'VPROT','4':'GND','5':'MID_FB','6':'V4','7':'MID_SW','8':'MID_GOOD','9':'GND'},80,85,mpn='TPS62160DSGR',lcsc='C324077')
passive('02_intermediate',L,'2.2uH / Isat>=2A','MID_SW','V4',175,65,note='Shielded inductor candidate, DCR/thermal/ripple to qualify.')
c('02_intermediate','10u 25V X7R','VPROT','GND',250,65); c('02_intermediate','22u 10V X7R','V4','GND',325,65)
r('02_intermediate','40.2k 0.1%','V4','MID_FB',175,125); r('02_intermediate','10k 0.1%','MID_FB','GND',250,125); r('02_intermediate','100k','V4','MID_GOOD',325,125)
c('02_intermediate','100n 25V','VPROT','GND',80,160)

sheet('03_bipolar','Bipolar preregulator: approximately +13.95 / -13.95 V','TPS65131: 2.7..5.5 V input; nominal 1.25 MHz. PSP/PSN LOW disables power-save mode.\nNegative feedback references VREF, NOT ground. Positive/negative rectifier polarity follows boost/inverter energy paths.\nBSW unused: positive preregulator can prebias through L/diode. No synchronized rail tracking promised.')
add('03_bipolar','U4',BI,'TPS65131RGER',{'1':'BOOST_SW','2':'GND','3':'GND','4':'ANA_V4','5':'V4','6':'V4','7':None,'8':'MID_GOOD','9':'GND','10':'MID_GOOD','11':'GND','12':None,'13':'INV_SW','14':'INV_SW','15':'PRE_N','16':'NEG_FB','17':'BI_REF','18':'COMP_N','19':'GND','20':None,'21':'COMP_P','22':'POS_FB','23':'PRE_P','24':'BOOST_SW','25':'GND'},65,80,mpn='TPS65131RGER',lcsc='C87663')
passive('03_bipolar',L,'4.7uH / Isat>=3A','V4','BOOST_SW',155,45); diode('03_bipolar','Schottky 1A 40V','PRE_P','BOOST_SW',230,45)
passive('03_bipolar',L,'4.7uH / Isat>=3A','INV_SW','GND',155,100); diode('03_bipolar','Schottky 1A 40V','INV_SW','PRE_N',230,100)
c('03_bipolar','22u 25V X7R','PRE_P','GND',305,45); c('03_bipolar','22u 25V X7R','PRE_N','GND',305,100)
r('03_bipolar','1.05M 0.1%','PRE_P','POS_FB',380,45); r('03_bipolar','100k 0.1%','POS_FB','GND',380,100)
r('03_bipolar','1.15M 0.1%','PRE_N','NEG_FB',65,155); r('03_bipolar','100k 0.1%','NEG_FB','BI_REF',140,155)
c('03_bipolar','6.8p C0G 50V','PRE_P','POS_FB',215,155); c('03_bipolar','6.8p C0G 50V','PRE_N','NEG_FB',290,155)
c('03_bipolar','220n 10V','BI_REF','GND',365,155); c('03_bipolar','10n 50V','COMP_P','GND',65,215); c('03_bipolar','4.7n C0G 50V','COMP_N','GND',140,215)
r('03_bipolar','100R','V4','ANA_V4',215,215); c('03_bipolar','100n 10V','ANA_V4','GND',290,215); c('03_bipolar','4.7u 10V X7R','V4','GND',365,215)
# Separate local input capacitor for the inverting switching loop.
c('03_bipolar','4.7u 10V X7R','V4','GND',65,260)

sheet('04_five_prereg','6.52 V preregulator for clean +5 V','TPS62125 is explicitly used: TPS62160 cannot be substituted here (6 V recommended output limit).\n10uH / 22uF combination is datasheet Table 2 recommendation for 5..10 V output.\nDCS control operates UP TO 1 MHz and enters PFM at light load: strict always-MHz requirement is NOT met.')
add('04_five_prereg','U5',B65,'TPS62125DSGR',{'1':'GND','2':'PRE_P','3':'PRE_P','4':None,'5':'FIVE_PRE_FB','6':'PRE_5','7':'FIVE_SW','8':None,'9':'GND'},80,80,mpn='TPS62125DSGR',note='Pin4 EN_hys intentionally NC per datasheet; custom symbol avoids incorrect AGND name inherited in installed library.')
passive('04_five_prereg',L,'10uH / Isat>=1A','FIVE_SW','PRE_5',175,60,note='Select shielded inductor with verified saturation and thermal curves.')
c('04_five_prereg','10u 25V X7R','PRE_P','GND',255,60); c('04_five_prereg','22u 16V X7R','PRE_5','GND',335,60)
r('04_five_prereg','71.5k 0.1%','PRE_5','FIVE_PRE_FB',175,125); r('04_five_prereg','10k 0.1%','FIVE_PRE_FB','GND',255,125)
c('04_five_prereg','100n 25V','PRE_P','GND',335,125)

sheet('05_clean_rails','Low-noise postregulators / three output rails','Positive LDO VFB=1.185 V; negative LDO VFB=-1.176 V (not the headline reference values).\nNegative IN and EN connect to PRE_N; GND and exposed pad stay at 0 V. All capacitors here are non-polar MLCC.\n10uF outputs must retain >=2.2uF under bias. 10nF NR/SS + feedforward: verify overshoot and startup on bench.\nDiodes bypass reverse differential and clamp wrong-polarity excursions, NOT precise output overvoltage protection.')
for idx,(ref,kind,inp,out,fb,nr,top,mpn) in enumerate([
 ('U6',LP,'PRE_P','P12','P12_FB','P12_NR','91.2k 0.1%','TPS7A4901DGNR'),
 ('U7',LN,'PRE_N','N12','N12_FB','N12_NR','92k 0.1%','TPS7A3001DGNR'),
 ('U8',LP,'PRE_5','P5','P5_FB','P5_NR','32.2k 0.1%','TPS7A4901DGNR')]):
    y=55+idx*76
    add('05_clean_rails',ref,kind,mpn,{'1':out,'2':fb,'3':None,'4':'GND','5':inp,'6':nr,'7':None,'8':inp,'9':'GND'},60,y,mpn=mpn,lcsc='C16430' if kind==LP else '',note='Package and pad map from TI datasheet; no footprint selected/placed.')
    c('05_clean_rails','10u 25V X7R',inp,'GND',135,y-14); c('05_clean_rails','10u 25V X7R',out,'GND',200,y-14)
    r('05_clean_rails',top,out,fb,265,y-14); r('05_clean_rails','10k 0.1%',fb,'GND',330,y-14)
    c('05_clean_rails','10n 50V',nr,'GND',135,y+21); c('05_clean_rails','10n 50V',out,fb,200,y+21)
    diode('05_clean_rails','Schottky 1A 40V',out if kind==LN else inp,inp if kind==LN else out,265,y+21)
    diode('05_clean_rails','Schottky 1A 40V','GND' if kind==LN else out,out if kind==LN else 'GND',330,y+21)

sheet('06_output','16-pin Eurorack POWER OUT / harness only','+5 V is on a separate STANDARD 16-pin interface, never added to the 10-pin standard.\nJ2 is an OFF-BOARD harness connector, not placed on either PCB. Exact crimp/IDC part and strain relief remain open.\nRED STRIPE / pins 1 and 2 = -12 V. CV (13/14) and GATE (15/16) intentionally NC.\nDo not trust key position alone. Continuity-test each cable; do not parallel this output with another supply.')
n={str(i):('N12' if i<=2 else 'GND' if i<=8 else 'P12' if i<=10 else 'P5' if i<=12 else None) for i in range(1,17)}
add('06_output','J2',IDC,'16-pin IDC POWER OUT',n,75,70,onboard=False,note='2x8 / 2.54 mm keyed cable connector; exact MPN and mounting unselected. Pinout per Doepfer/Division6.')
for i,(net,val) in enumerate([('P12','100k'),('N12','100k'),('P5','47k')]):r('06_output',val,net,'GND',175+i*70,65)
# Hardware AND gate. A generic PG flag is NOT explicit PDO/current authorization.
# PNP 1=B, 2=E, 3=C: active-low PG sources SHDN only while powered.
add('01_input','Q1',PNP,'MMBT3906',{'1':'PG_BASE','2':'PD_VDD','3':'PG_PERMIT'},0,0,mpn='MMBT3906',note='Pin1 B, pin2 E, pin3 C per Diodes DS30059. PG low turns ON. Gate electrical/timing margins need bench qualification.')
r('01_input','22k 1%','PD_PG_N','PG_BASE',0,0)
r('01_input','100k 1%','PD_VDD','PG_BASE',0,0)
r('01_input','10k 1%','EF_ENABLE','RTN',0,0,note='SHDN default-low despite internal pullup: 10uA x 10k = 0.1V, below 0.55V minimum falling threshold.')
r('01_input','10k 1%','VPROT','GND',0,0,note='Bleed off-state leakage; leakage maxima and residual rail voltages NOT qualified. No precontract rail operation allowed.')
# ERC declarations: real power sources at passive input / filtered converter nodes, not arbitrary error masking.
for i,net in enumerate(['GND','VBUS_RAW','VBUS_FUSED','PD_VDD','V4','ANA_V4','PRE_P','PRE_N','PRE_5']):
    add('06_output',f'#FLG{i+1:02}',FLAG,'PWR_FLAG',{'1':net},50+(i%5)*70,155+(i//5)*45)

from render_schematic import render
if args.schematic_only:
    # Use the pinned project symbols rather than silently upgrading installed libraries.
    assert set(LIB) <= set(PINNED), 'Missing pinned symbol'
    LIB = {name: PINNED[name] for name in LIB}
render(HW, SHEETS, LIB, uid)
if args.schematic_only:
    for name in ['BigModular.kicad_sym', 'sym-lib-table', 'fp-lib-table', 'big_modular.kicad_pro']:
        shutil.copyfile(ROOT/'hardware'/name, HW/name)
    shutil.copytree(ROOT/'hardware/BigModular.pretty', HW/'BigModular.pretty')
    print('Created', len(BOM), 'components in three functional subsheets plus an overview; boards/BOM unchanged:', HW)
    sys.exit(0)
(HW/'BigModular.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(dump(s) for s in LIB.values())+'\n)')
(HW/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "BigModular") (type "KiCad") (uri "${KIPRJMOD}/BigModular.kicad_sym") (options "") (descr "Pinned project symbols; see pin audit")))')
(HW/'big_modular.kicad_pro').write_text(json.dumps({'meta':{'filename':'big_modular.kicad_pro','version':1},'text_variables':{'STATUS':'ENGINEERING PROTOTYPE - DO NOT FABRICATE'}},indent=2)+'\n')
with (ROOT/'BOM.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(BOM[0]),lineterminator="\n");w.writeheader();w.writerows(BOM)
(ROOT/'docs/pin-net-audit.json').write_text(json.dumps(CONNS,indent=2)+'\n')
# Board creation uses the locally installed KiCad engine. No routing functions are called.
import pcbnew as pcb
MM=pcb.FromMM
def v(x,y):return pcb.VECTOR2I(MM(x),MM(y))
def line(b,a,z,layer=pcb.Edge_Cuts):
    s=pcb.PCB_SHAPE();s.SetShape(pcb.SHAPE_T_SEGMENT);s.SetStart(v(*a));s.SetEnd(v(*z));s.SetLayer(layer);s.SetWidth(MM(.05 if layer==pcb.Edge_Cuts else .15));b.Add(s)
def arc(b,a,m,z):
    s=pcb.PCB_SHAPE();s.SetShape(pcb.SHAPE_T_ARC);s.SetArcGeometry(v(*a),v(*m),v(*z));s.SetLayer(pcb.Edge_Cuts);s.SetWidth(MM(.05));b.Add(s)
def rect(b,x,y,w,h):
    pts=[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]
    for a,z in zip(pts,pts[1:]):line(b,a,z)
def roundrect(b,x,y,w,h,r):
    k=r/math.sqrt(2)
    line(b,(x+r,y),(x+w-r,y));arc(b,(x+w-r,y),(x+w-r+k,y+r-k),(x+w,y+r))
    line(b,(x+w,y+r),(x+w,y+h-r));arc(b,(x+w,y+h-r),(x+w-r+k,y+h-r+k),(x+w-r,y+h))
    line(b,(x+w-r,y+h),(x+r,y+h));arc(b,(x+r,y+h),(x+r-k,y+h-r+k),(x,y+h-r))
    line(b,(x,y+h-r),(x,y+r));arc(b,(x,y+r),(x+r-k,y+r-k),(x+r,y))
def txt(b,s,x,y,size=.8,layer=pcb.Dwgs_User):
    t=pcb.PCB_TEXT(b);t.SetText(s);t.SetPosition(v(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(MM(.12));t.SetLayer(layer);b.Add(t)
def hole(b,ref,x,y,dx,dy=None):
    dy=dx if dy is None else dy
    fp=pcb.FOOTPRINT(b);fp.SetReference(ref);fp.SetValue('MECHANICAL_NPTH');fp.SetPosition(v(x,y));fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
    p=pcb.PAD(fp);p.SetAttribute(pcb.PAD_ATTRIB_NPTH);p.SetShape(pcb.PAD_SHAPE_CIRCLE if dx==dy else pcb.PAD_SHAPE_OVAL);p.SetSize(v(dx,dy));p.SetDrillSize(v(dx,dy))
    if dx!=dy:p.SetDrillShape(pcb.PAD_DRILL_SHAPE_OBLONG)
    p.SetLayerSet(pcb.LSET.AllCuMask());p.SetPosition(v(x,y));fp.Add(p);b.Add(fp)
def board():
    b=pcb.BOARD();b.SetCopperLayerCount(2);b.GetDesignSettings().SetBoardThickness(MM(1.6));return b
fname='USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'
pretty=HW/'BigModular.pretty';pretty.mkdir(exist_ok=True)
shutil.copyfile('/usr/share/kicad/footprints/Connector_USB.pretty/'+fname+'.kicad_mod',pretty/(fname+'.kicad_mod'))
(HW/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "BigModular") (type "KiCad") (uri "${KIPRJMOD}/BigModular.pretty") (options "") (descr "Unmodified installed GCT USB4105 footprint")))')
b=board();rect(b,49.75,42.275,100.5,60)
fp=pcb.FootprintLoad(str(pretty),fname);fp.SetReference('J1');fp.SetValue('USB4105-GF-A');fp.SetPosition(v(100,99.8));fp.SetFPID(pcb.LIB_ID('BigModular',fname));fp.SetLocked(True);b.Add(fp)
nets={}
for name in ['VBUS_RAW','GND','CC1','CC2']:
    n=pcb.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
for p in fp.Pads():
    net=CONNS['J1'].get(p.GetNumber())
    if net:p.SetNet(nets[net])
for i,(Y,Z) in enumerate([(45,6),(83.5,6),(45,52),(83.5,52)]):hole(b,'H'+str(i+1),Y+35.75,104.275-Z,2.2)
txt(b,'PLACEMENT ONLY / NO ROUTING / NOT BUILDABLE',100,35,1.2)
txt(b,'Carrier: Y=14..114.5; Z=2..62 mm',100,39,.9)
txt(b,'J1 MOUTH Z=+0.800 / insertion +Z / panel normal',100,108,.9)
txt(b,'Carrier top X=3.170; PCB bottom X=1.570',100,113,.9)
txt(b,'2 machined corner blocks: see ../docs/assembly.svg',100,117,.9)
for Y in [45,83.5]:
    pts=[(Y-4+35.75,104.275-1.6),(Y+4+35.75,104.275-1.6),(Y+4+35.75,104.275-10),(Y-4+35.75,104.275-10)]
    for a,z in zip(pts,pts[1:]+pts[:1]):line(b,a,z,pcb.Dwgs_User)
line(b,(100,101.0),(100,93),pcb.Dwgs_User)
for a,z in [((100,93),(98.8,95)),((100,93),(101.2,95))]:line(b,a,z,pcb.Dwgs_User)
# Native data has pads only: no generated tracks, vias, copper graphics or zones.
pcb.SaveBoard(str(HW/'big_modular.kicad_pcb'),b)
p=board();rect(p,50,30,9.8,128.5)
roundrect(p,50+2.725,30+59.35,4.2,9.8,.6)
hole(p,'H1',57.5,33,3.2);hole(p,'H2',57.5,155.5,3.2)
hole(p,'H3',54.9,75,2.2);hole(p,'H4',54.9,113.5,2.2)
txt(p,'BIG',54.9,45,.95,pcb.F_SilkS);txt(p,'MOD',54.9,48,.95,pcb.F_SilkS);txt(p,'PD 9V',54.9,57,.8,pcb.F_SilkS);txt(p,'ONLY',54.9,61,.8,pcb.F_SilkS)
txt(p,'IN',54.9,104,.8,pcb.F_SilkS);txt(p,'PROTO',54.9,143,.8,pcb.F_SilkS)
txt(p,'2HP: 9.8 x 128.5 x 1.6 mm',82,40,1)
txt(p,'USB cutout: 4.2 x 9.8, R0.6',82,45,1)
txt(p,'Port axis (X,Y,Z)=(4.900,64.250,0.800)',97,50,1)
txt(p,'Front face Z=0; inward +Z; NO copper',92,55,1)
txt(p,'Doepfer X=7.5 / dia3.2: 0.7mm FR4 web; M3 head overhang BLOCKER',114,65,.85)
txt(p,'Mounting proposal: ../docs/assembly.svg / mechanics.md',112,70,.85)
pcb.SaveBoard(str(HW/'front_panel.kicad_pcb'),p)
(HW/'front_panel.kicad_pro').write_text(json.dumps({'meta':{'filename':'front_panel.kicad_pro','version':1}},indent=2)+'\n')
print('Created',len(BOM),'schematic components, three subsheets + overview, two unrouted boards.')
