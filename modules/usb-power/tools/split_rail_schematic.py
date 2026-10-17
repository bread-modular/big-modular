"""Explicit SR1 schematic-only migration, preserving unaffected native nodes.

Called once by build_project --split-rail-revision into a NEW candidate. Never
loads, repairs, synchronizes, places or routes a PCB. Normal builds use the saved
native presentation and enforce exact pin intent before field updates.
"""
import copy
import json
import math
from sexp import parse,dump,nodes,one,walk,atom
from native_sheet_patch import rewrite


def stage(source,hw,sheets,lib,uid):
    q=json.dumps
    assert not (source/'06_positive_boost.kicad_sch').exists(), 'One-shot SR1 migration already applied'
    for p in source.glob('*.kicad_sch'):(hw/p.name).write_bytes(p.read_bytes())
    parts={d['ref']:d for sh in sheets.values() for d in sh['parts']}
    count=0
    def wire(t,a,b):
        nonlocal count
        if a==b:return
        assert a[0]==b[0] or a[1]==b[1], (a,b)
        count+=1
        t.append(parse(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {q(uid("SR1/wire/"+str(count)))}))'))
    def poly(t,*ps):
        for a,b in zip(ps,ps[1:]):wire(t,a,b)
    def label(t,n,x,y):
        t.append(parse(f'(label {q(n)} (at {x} {y} 0) (effects (font (size 1 1)) (justify left bottom)) (uuid {q(uid("SR1/label/"+n+str((x,y))))}))'))
    def text(t,s,x,y,size=1.15):
        t.append(parse(f'(text {q(s)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left top)) (uuid {q(uid("SR1/text/"+s))}))'))
    def port(t,n,shape,x,y,a):
        t.append(parse(f'(hierarchical_label {q(n)} (shape {shape}) (at {x} {y} {a}) (effects (font (size 1.2 1.2)) (justify {"left" if a==180 else "right"})) (uuid {q(uid("SR1/port/"+n))}))'))
    def split(t):
        # Every endpoint on a wire becomes an explicit T, never a crossing short.
        endpoints={tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:]}
        for w in list(nodes(t,'wire')):
            a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
            inner=[p for p in endpoints if p not in (a,b) and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]) and (b[0]-a[0])*(p[1]-a[1])==(b[1]-a[1])*(p[0]-a[0])]
            if inner:
                t.remove(w); ps=sorted([a,b,*inner]);poly(t,*ps)
        from collections import Counter
        degrees=Counter(tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:])
        old={tuple(map(float,one(j,'at')[1:])) for j in nodes(t,'junction')}
        for (x,y),degree in degrees.items():
            if degree>=3 and (x,y) not in old:
                t.append(parse(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid("SR1/junction/"+str((x,y))))}))'))
    def clone_cap(t,ref,template,x,y):
        s=copy.deepcopy(next(s for s in nodes(t,'symbol') if any(p[1:3]==['Reference',template] for p in nodes(s,'property'))))
        ox,oy=map(float,one(s,'at')[1:3]);dx,dy=x-ox,y-oy
        for n in walk(s,'at'):n[1:3]=[atom(round(float(n[1])+dx,5)),atom(round(float(n[2])+dy,5))]
        for n in walk(s,'uuid'):n[1]=uid('SR1/'+ref+'/'+n[1])
        for p in nodes(s,'property'):
            if p[1]=='Reference':p[2]=ref
        for n in walk(s,'reference'):n[1]=ref
        t.append(s)
        return (x,round(y-3.81,5)),(x,round(y+3.81,5))
    # 04: retain the inactive positive power stage, but remove its inter-sheet port.
    path=source/'04_bipolar.kicad_sch'; original=path.read_text();t=parse(original)
    for key in ('label','hierarchical_label'):
        for n in nodes(t,key):
            if n[1]=='PRAW':
                n[1]='POS_DORMANT'
                if key=='hierarchical_label':
                    t.remove(n);label(t,'POS_DORMANT',370.84,71.12)
    removed=[]
    for w in list(nodes(t,'wire')):
        a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
        if (a,b)==((154.94,132.08),(165.1,132.08)):
            t.remove(w);removed.append(w)
    assert len(removed)==1
    wire(t,(160.02,132.08),(165.1,132.08));label(t,'GND',160.02,132.08)
    # The vertical branch still feeds ENN; only the ENP spur is removed.
    for j in list(nodes(t,'junction')):
        if tuple(map(float,one(j,'at')[1:]))==(154.94,132.08):t.remove(j)
    for ref,x in [('C75',304.8),('C76',342.9)]:
        a,b=clone_cap(t,ref,'C9',x,284.48);poly(t,(x,274.32),a);poly(t,b,(x,299.72))
    wire(t,(304.8,274.32),(342.9,274.32));label(t,'NRAW',304.8,274.32)
    wire(t,(304.8,299.72),(342.9,299.72));label(t,'GND',304.8,299.72)
    a,b=clone_cap(t,'C81','C16',40.64,220.98);poly(t,(40.64,210.82),a);poly(t,b,(40.64,236.22));label(t,'MID',40.64,210.82);label(t,'GND',40.64,236.22)
    for n in nodes(t,'text'):
        if n[1].startswith('04 /'):n[1]='04 / NEGATIVE CONVERTER + ISOLATED DORMANT POSITIVE STAGE'
        elif n[1].startswith('INTERNAL raw'):n[1]='NRAW = -14.185083V nominal: (1.4M precision +15k Basic)/(120k precision +1k Basic).\nENP8 is independently grounded; ENN10 unchanged. VIN/INN only MID, never VPROT.\nPOS_DORMANT retains L2/D2/C8/FB/CP, passively precharges from MID; NOT PRAW or an output port.'
    split(t);(hw/path.name).write_text(rewrite(original,t))
    # 05: retain all existing drawing geometry and add only the two cap branches.
    path=source/'05_quiet_rails.kicad_sch';original=path.read_text();t=parse(original)
    for ref,template,x,top,bottom in [('C73','C59',381.0,182.88,281.94),('C74','C67',35.56,182.88,281.94)]:
        a,b=clone_cap(t,ref,template,x,218.44);poly(t,(x,top),a);poly(t,b,(x,bottom))
    wire(t,(355.6,281.94),(381.,281.94));wire(t,(35.56,182.88),(45.72,182.88));wire(t,(35.56,281.94),(45.72,281.94))
    for n in nodes(t,'text'):
        if n[1].startswith('Raw +'):n[1]='SR1 PRAW +13.519V / NRAW -14.185083V nominal; independent final P5 unchanged.\nSame exact LDOs, no rail-synchronous shutdown. Schematic only: PCB still old and unsynchronized.'
        elif n[1].startswith('U12 ANY'):n[1]='U12 ANY-OUT 5,6,9,11 GND; 4,8,10,12 float; SENSE3=P12. Both EP21=GND.\nC12891 banks IN+/OUT+/IN-/OUT- =4/6/5/4; combined DC+AC bias screening only.\nC60=1u; C61=100n. EN tied to own raw input, no disconnect or tracking promise.'
        elif n[1].startswith('(R72'):n[1]='R72=90.9k 0.1%, R83=0R, R73=1.2k 1%, R74=10k 0.1% -> -11.99675V nominal.\nC62 DNP (pads retained): supported without CFF, noise/PSRR tradeoff; no claimed bench cure.\nD27/D28 discharge paths are NOT isolation or proof of negative0.3V differential compliance.\nHeadroom/temperature/loop/start-stop/reverse-current qualification remains open. No supply current rating.'
    split(t);(hw/path.name).write_text(rewrite(original,t))
    # Overview: preserve all old blocks except the old positive output pin/path.
    path=source/'usb-power.kicad_sch';original=path.read_text();root=parse(original);rootid=one(root,'uuid')[1];sheetid=uid('sheet/06_positive_boost')
    old=next(s for s in nodes(root,'sheet') if any(p[1:3]==['Sheetfile','04_bipolar.kicad_sch'] for p in nodes(s,'property')))
    old.remove(next(p for p in nodes(old,'pin') if p[1]=='PRAW'))
    next(p for p in nodes(old,'property') if p[1]=='Sheetname')[2]='Negative converter'
    for w in list(nodes(root,'wire')):
        pts=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
        if pts==[(330.2,139.7),(330.2,152.4)]:root.remove(w)
    sh=parse(f'''(sheet (at 116.84 193.04) (size 76.2 48.26) (stroke (width 0.1524) (type default)) (fill (color 0 0 0 0)) (uuid {q(sheetid)})
      (property "Sheetname" "Direct 9V positive boost" (at 116.84 191.77 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
      (property "Sheetfile" "06_positive_boost.kicad_sch" (at 116.84 242.57 0) (effects (font (size 1.27 1.27)) (justify left top)))
      (instances (project "usb-power" (path {q('/'+rootid)} (page "8")))))''')
    for n,typ,x,y,a in [('VPROT','input',116.84,205.74,180),('PRAW','output',193.04,218.44,0),('GND','passive',154.94,241.3,270)]:
        sh.append(parse(f'(pin {q(n)} {typ} (at {x} {y} {a}) (effects (font (size 1.15 1.15)) (justify {"left" if a==180 else "right"})) (uuid {q(uid("SR1/rootport/"+n))}))'))
    root.append(sh)
    poly(root,(193.04,81.28),(193.04,180.34),(106.68,180.34),(106.68,205.74),(116.84,205.74))
    poly(root,(193.04,218.44),(289.56,218.44),(289.56,147.32),(330.2,147.32),(330.2,152.4));label(root,'PRAW',203.2,218.44)
    wire(root,(154.94,241.3),(154.94,254));label(root,'GND',154.94,254)
    for n in nodes(root,'text'):
        if n[1].startswith('U4 /'):n[1]='U4 / NEGATIVE ONLY'
        elif n[1].startswith('9 V voltage'):one(n,'at')[1:3]=[atom(20.32),atom(287.02)]
        elif n[1].startswith('J7 is'):n[1]='J7: one manual harness; same +/-12V and independent P5.\nSR1 SCHEMATIC ONLY - PCB UNSYNCHRONIZED.\nOpus review then separate PCB worker; no fabrication export.';one(n,'at')[1:3]=[atom(20.32),atom(264.16)]
        elif 'PROTOTYPE / BENCH' in n[1]:n[1]='SR1 SCHEMATIC REVIEW / PCB UNSYNCHRONIZED / NOT FOR FABRICATION'
    text(root,'U14 / PRAW +13.519V',121.92,231.14)
    split(root);(hw/path.name).write_text(rewrite(original,root))
    # New fully wired boost sheet. Pins follow TI RTE, never HTSSOP numbering.
    t=parse(f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(uid("SR1/06root"))}) (paper "User" 430 345) (title_block (title "Direct protected-9V positive boost") (rev "SR1")) (lib_symbols) (embedded_fonts no))')
    for k in sorted({d['kind'] for d in sheets['06_positive_boost']['parts']}):
        s=copy.deepcopy(lib[k]);s[1]='BigModular:'+k;one(t,'lib_symbols').append(s)
    pins={}
    def part(ref,x,y,a=0):
        d=parts[ref];su=uid('SR1/06/'+ref)
        s=parse(f'(symbol (lib_id {q("BigModular:"+d["kind"])}) (at {x} {y} {a}) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(su)}) (instances (project "usb-power" (path {q("/"+rootid+"/"+sheetid)} (reference {q(ref)}) (unit 1)))))')
        for k,v in [('Reference',ref),('Value',d['value']),('Footprint',d['fp']),('Datasheet',d['datasheet']),('MPN',d['mpn']),('LCSC',d['lcsc']),('NOTE',d['note']),('Manufacturer',d['manufacturer'])]:
            hide=k not in ('Reference','Value') or ref.startswith('#')
            xx=x+3.81 if ref.startswith(('C','R')) else x
            yy=y+(-1.27 if k=='Reference' else 1.27) if ref.startswith(('C','R')) else y+(-31.75 if ref=='U14' else -7.62)+ (2.54 if k=='Value' else 0)
            s.append(parse(f'(property {q(k)} {q(v)} (at {xx} {yy} 0) (effects (font (size 1.05 1.05)) {"(justify left)" if ref.startswith(("C","R")) else ""} {"hide" if hide else ""}))'))
        for p in walk(lib[d['kind']],'pin'):
            n=one(p,'number')[1];px,py=map(float,one(p,'at')[1:3]);r=math.radians(a)
            pins[(ref,n)]=(round(x+px*math.cos(r)-py*math.sin(r),5),round(y-px*math.sin(r)-py*math.cos(r),5))
            s.append(parse(f'(pin {q(n)} (uuid {q(uid(su+"/"+n))}))'))
        t.append(s)
    def pp(r,p):return pins[(r,str(p))]
    part('U14',170.18,137.16)
    part('L5',160.02,66.04,90);part('D29',218.44,66.04,180)
    port(t,'VPROT','input',25.4,66.04,180);label(t,'VPROT',35.56,66.04)
    poly(t,(25.4,66.04),pp('L5',1));poly(t,pp('L5',2),(198.12,66.04),pp('D29',2))
    poly(t,pp('D29',1),(388.62,66.04));port(t,'PRAW','output',388.62,66.04,0);label(t,'PRAW',370.84,66.04)
    for pn in [1,15,16]:poly(t,pp('U14',pn),(198.12,pp('U14',pn)[1]))
    poly(t,(198.12,66.04),(198.12,pp('U14',16)[1]));label(t,'PBOOST_SW',198.12,88.9)
    for pn in [2,3]:poly(t,(116.84,66.04),(116.84,pp('U14',pn)[1]),pp('U14',pn)) if pn==2 else poly(t,(116.84,pp('U14',2)[1]),(116.84,pp('U14',3)[1]),pp('U14',3))
    port(t,'GND','passive',25.4,254,180);wire(t,(25.4,254),(370.84,254));label(t,'GND',30.48,254)
    for ref,x in [('C82',45.72),('C83',71.12),('C84',96.52),('C88',106.68)]:
        part(ref,x,177.8);poly(t,(x,66.04),pp(ref,1));poly(t,pp(ref,2),(x,254))
    for ref,x in [('C77',294.64),('C78',320.04),('C79',345.44),('C80',370.84)]:
        part(ref,x,177.8);poly(t,(x,66.04),pp(ref,1));poly(t,pp(ref,2),(x,254))
    part('R86',269.24,99.06);part('R87',269.24,147.32)
    poly(t,(269.24,66.04),pp('R86',1));poly(t,pp('R86',2),(269.24,116.84),pp('R87',1));poly(t,pp('R87',2),(281.94,pp('R87',2)[1]),(281.94,254))
    poly(t,pp('U14',8),(269.24,pp('U14',8)[1]));label(t,'PBOOST_FB',241.3,pp('U14',8)[1])
    part('R89',223.52,154.94);part('C86',223.52,190.5);part('C87',251.46,190.5)
    poly(t,pp('U14',7),(223.52,pp('U14',7)[1]),pp('R89',1));poly(t,pp('R89',2),pp('C86',1));poly(t,pp('C86',2),(223.52,254))
    poly(t,(223.52,pp('U14',7)[1]),(251.46,pp('U14',7)[1]),pp('C87',1));poly(t,pp('C87',2),(251.46,254))
    label(t,'PBOOST_COMP',223.52,pp('U14',7)[1]);label(t,'PBOOST_COMP_RC',223.52,175.26)
    part('R88',203.2,200.66);part('R90',203.2,226.06)
    poly(t,pp('U14',9),(203.2,pp('U14',9)[1]),pp('R88',1));poly(t,pp('R88',2),pp('R90',1));poly(t,pp('R90',2),(203.2,254));label(t,'PBOOST_FREQ',203.2,182.88);label(t,'PBOOST_FREQ_SER',203.2,213.36)
    part('C85',134.62,215.9);poly(t,pp('U14',4),(134.62,pp('U14',4)[1]),pp('C85',1));poly(t,pp('C85',2),(134.62,254));label(t,'PBOOST_SS',134.62,193.04)
    for pn in [5,6,10,14,17]:poly(t,pp('U14',pn),(147.32,pp('U14',pn)[1]))
    poly(t,(147.32,pp('U14',5)[1]),(147.32,254))
    for pn in [11,12,13]:poly(t,pp('U14',pn),(190.5,pp('U14',pn)[1]))
    poly(t,(190.5,pp('U14',11)[1]),(190.5,254))
    part('#FLG09',388.62,45.72);poly(t,pp('#FLG09',1),(388.62,66.04))
    text(t,'06 / TPS55340 DIRECT VPROT BOOST - PRAW +13.519V',20.32,17.78,2)
    text(t,'R86/R87=100k/10k, both0.1%25ppm/K precision exceptions. R88+R90=120k Basic (~400kHz).\nEN follows VPROT; SS100n ~30ms typical. L5/D29 precharge PRAW even with EN low.\nNo active sequencer, output disconnect or rail-synchronous shutdown claim.',20.32,30.48)
    text(t,'Layout handoff: minimize SW1/15/16-L5-D29-C77..80 loop; Kelvin FB to quiet PRAW/GND.\nSYNC5, RSVD10/14 and EP17 -> AGND; join AGND/PGND locally, ordinary0.300mm thermal vias.\nInput/ground/output branches shown are electrical connectivity, NOT PCB placement or routing.\nCCM compensation and DC+AC capacitance screens only; full-load start/stop/noise/thermal/loop tests pending.',20.32,279.4)
    split(t);(hw/'06_positive_boost.kicad_sch').write_text(dump(t)+'\n')
