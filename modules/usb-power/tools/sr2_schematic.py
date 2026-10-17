"""One-shot SR1 -> SR2 native schematic edit in a NEW candidate, never a PCB.
Existing module generator owns fields; this file owns explicit revised wires.
"""
import copy,json,math
from collections import Counter
from sexp import parse,dump,nodes,one,walk,atom
from native_sheet_patch import rewrite
from sr2_design import INPUT_REFS,SPAN_REFS,OUTPUT_REFS


def stage(source,hw,sheets,lib,uid):
    q=json.dumps;count=0
    for p in source.glob('*.kicad_sch'):(hw/p.name).write_bytes(p.read_bytes())
    parts={d['ref']:d for sh in sheets.values() for d in sh['parts']}
    def wire(t,a,b):
        nonlocal count
        if a==b:return
        assert a[0]==b[0] or a[1]==b[1],(a,b)
        count+=1
        t.append(parse(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {q(uid("SR2/wire/"+str(count)))}))'))
    def poly(t,*ps):
        for a,b in zip(ps,ps[1:]):wire(t,a,b)
    def label(t,n,x,y):
        t.append(parse(f'(label {q(n)} (at {x} {y} 0) (effects (font (size 1 1)) (justify left bottom)) (uuid {q(uid("SR2/label/"+n+str((x,y))))}))'))
    def text(t,s,x,y,size=1.15):
        t.append(parse(f'(text {q(s)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left top)) (uuid {q(uid("SR2/text/"+s))}))'))
    def port(t,n,shape,x,y,a):
        t.append(parse(f'(hierarchical_label {q(n)} (shape {shape}) (at {x} {y} {a}) (effects (font (size 1.2 1.2)) (justify {"right" if a==180 else "left"})) (uuid {q(uid("SR2/port/"+n+str((x,y))))}))'))
    def split(t):
        endpoints={tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:]}
        for w in list(nodes(t,'wire')):
            a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
            inner=[p for p in endpoints if p not in (a,b) and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]) and (b[0]-a[0])*(p[1]-a[1])==(b[1]-a[1])*(p[0]-a[0])]
            if inner:t.remove(w);poly(t,*sorted([a,b,*inner]))
        degrees=Counter(tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:])
        old={tuple(map(float,one(j,'at')[1:])) for j in nodes(t,'junction')}
        for (x,y),degree in degrees.items():
            if degree>=3 and (x,y) not in old:t.append(parse(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid("SR2/junction/"+str((x,y))))}))'))
    root=parse((source/'usb-power.kicad_sch').read_text());rootid=one(root,'uuid')[1]
    neg=next(s for s in nodes(root,'sheet') if any(p[1:3]==['Sheetfile','04_bipolar.kicad_sch'] for p in nodes(s,'property')))
    sheetid=one(neg,'uuid')[1]
    assert next(p for p in nodes(neg,'pin') if p[1]=='MID')
    next(p for p in nodes(neg,'pin') if p[1]=='MID')[1]='VPROT'
    next(p for p in nodes(neg,'property') if p[1]=='Sheetname')[2]='Direct 9V negative IBB'
    buck=next(s for s in nodes(root,'sheet') if any(p[1:3]==['Sheetfile','03_bucks.kicad_sch'] for p in nodes(s,'property')))
    buck.remove(next(p for p in nodes(buck,'pin') if p[1]=='MID'))
    next(p for p in nodes(buck,'property') if p[1]=='Sheetname')[2]='Independent +5V buck'
    for w in list(nodes(root,'wire')):
        if [tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]==[(276.86,81.28),(309.88,81.28)]:root.remove(w)
    for l in list(nodes(root,'label')):
        if l[1]=='MID':root.remove(l)
    poly(root,(205.74,81.28),(205.74,55.88),(294.64,55.88),(294.64,81.28),(309.88,81.28))
    label(root,'VPROT',246.38,55.88)
    for n in nodes(root,'text'):
        if n[1]=='U4 / NEGATIVE ONLY':n[1]='U3 / NRAW -14.07752V'
        elif n[1]=='U3 MID / U5 +5V':n[1]='U5 / INDEPENDENT +5V'
        elif 'SR1' in n[1]:n[1]=n[1].replace('SR1','SR2').replace('Opus review then separate PCB worker','Opus + DeepSeek reviews, corrections, user ACK; then PCB worker')
    one(one(root,'title_block'),'rev')[1]='SR2'
    for n in nodes(one(root,'title_block'),'comment'):
        if 'SR1' in n[-1]:n[-1]=n[-1].replace('SR1','SR2')
    split(root);(hw/'usb-power.kicad_sch').write_text(rewrite((source/'usb-power.kicad_sch').read_text(),root))
    # Keep the actual U5 lower-half drawing/UUIDs. Remove only U3/MID branches.
    from schematic_connectivity import Connectivity
    graph=Connectivity(source);name='03_bucks.kicad_sch';original=(source/name).read_text();t=parse(original)
    keep={d['ref'] for d in sheets['03_bucks']['parts']}
    for n in list(t):
        if not isinstance(n,list):continue
        k=n[0]
        if k=='symbol' and next(p[2] for p in nodes(n,'property') if p[1]=='Reference') not in keep:t.remove(n)
        elif k=='wire':
            pts=[tuple(map(float,p[1:])) for p in one(n,'pts')[1:]]
            names=graph.connected_labels[graph.find((name,*pts[0]))]
            if min(p[1] for p in pts)<160 or 'MID' in names:t.remove(n)
        elif k in ('junction','no_connect','label'):
            x,y=map(float,one(n,'at')[1:3])
            if y<160 or (k=='label' and n[1].startswith('MID')):t.remove(n)
        elif k=='hierarchical_label' and n[1]!='P5':t.remove(n)
        elif k=='text':
            if n[1].startswith('U3:'):t.remove(n)
            elif n[1].startswith('U3 MID'):n[1]='U5 remains direct VPROT -> P5, nominal5.007547V; 250mA shared-budget reserve.\nEN5 NC with internal pullup. U3 moved to sheet04, no MID converter or net remains.'
            elif n[1].startswith('03 /'):n[1]='03 / INDEPENDENT +5V BUCK - U5 UNCHANGED'
            elif 'Sunlord' in n[1]:n[1]='BOOT C36 returns to SW, not GND. L4 is exact MDA1040-6R8M.\nRetained divider100k/(13k+510R), local C19/C38/C72.\nElectrical intent and U5 native component geometry retained; PCB remains unsynchronized.'
    port(t,'VPROT','input',22.86,187.96,180);label(t,'VPROT',22.86,187.96)
    grounds=[n for n in nodes(t,'label') if n[1]=='GND'];gx,gy=map(float,one(grounds[0],'at')[1:3])
    port(t,'GND','passive',gx,gy,180)
    one(one(t,'title_block'),'rev')[1]='SR2'
    split(t);(hw/name).write_text(rewrite(original,t))
    # New negative sheet, same hierarchy UUID; exact manufacturer pin roles.
    old=parse((source/'04_bipolar.kicad_sch').read_text())
    t=parse(f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(one(old,"uuid")[1])}) (paper "User" 430 345) (title_block (title "Direct protected-9V negative IBB") (rev "SR2")) (lib_symbols) (embedded_fonts no))')
    for k in sorted({d['kind'] for d in sheets['04_bipolar']['parts']}):
        s=copy.deepcopy(lib[k]);s[1]='BigModular:'+k;one(t,'lib_symbols').append(s)
    pins={}
    def part(ref,x,y,a=0):
        d=parts[ref];su=uid('SR2/04/'+ref)
        s=parse(f'(symbol (lib_id {q("BigModular:"+d["kind"])}) (at {x} {y} {a}) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(su)}) (instances (project "usb-power" (path {q("/"+rootid+"/"+sheetid)} (reference {q(ref)}) (unit 1)))))')
        for k,v in [('Reference',ref),('Value',d['value']),('Footprint',d['fp']),('Datasheet',d['datasheet']),('MPN',d['mpn']),('LCSC',d['lcsc']),('NOTE',d['note']),('Manufacturer',d['manufacturer'])]:
            hide=k not in ('Reference','Value') or ref.startswith('#');passive=ref.startswith(('C','R')) or ref=='D30'
            xx=x+(18 if a==180 else 3.81) if passive else x;yy=y+(-1.27 if k=='Reference' else 1.27) if passive else y+(-17.78 if ref=='U3' else -7.62)+(2.54 if k=='Value' else 0)
            s.append(parse(f'(property {q(k)} {q(v)} (at {xx} {yy} {90 if ref in ('L1','D30') else 0}) (effects (font (size 1.05 1.05)) {"(justify left)" if passive else ""} {"hide" if hide else ""}))'))
        for p in walk(lib[d['kind']],'pin'):
            n=one(p,'number')[1];px,py=map(float,one(p,'at')[1:3]);r=math.radians(a)
            pins[(ref,n)]=(round(x+px*math.cos(r)-py*math.sin(r),5),round(y-px*math.sin(r)-py*math.cos(r),5))
            s.append(parse(f'(pin {q(n)} (uuid {q(uid(su+"/"+n))}))'))
        t.append(s)
    def pp(r,p):return pins[(r,str(p))]
    part('U3',185.42,137.16)
    part('L1',248.92,137.16,90);part('C35',223.52,106.68)
    poly(t,pp('U3',2),(223.52,137.16),pp('L1',1));poly(t,pp('L1',2),(281.94,137.16));label(t,'GND',281.94,137.16)
    poly(t,pp('U3',6),(210.82,pp('U3',6)[1]),(210.82,91.44),(223.52,91.44),pp('C35',1));poly(t,pp('C35',2),(223.52,137.16))
    label(t,'NINV_SW',226.06,137.16);label(t,'NINV_BOOT',210.82,91.44)
    # Source bank and local span bank are deliberately drawn in separate rows.
    port(t,'VPROT','input',25.4,66.04,180);poly(t,(25.4,66.04),(160.02,66.04),(160.02,pp('U3',3)[1]),pp('U3',3));label(t,'VPROT',30.48,66.04)
    for ref,x in zip(INPUT_REFS,[45.72,83.82]):
        part(ref,x,91.44);poly(t,(x,66.04),pp(ref,1));poly(t,pp(ref,2),(x,111.76));label(t,'GND',x,111.76)
    for ref,x in zip((*SPAN_REFS,'C7'),[30.48,66.04,101.6,137.16,172.72]):
        part(ref,x,231.14);poly(t,(x,213.36),pp(ref,1));poly(t,pp(ref,2),(x,254))
    wire(t,(30.48,213.36),(172.72,213.36));label(t,'VPROT',30.48,213.36)
    wire(t,(30.48,254),(401.32,254));label(t,'NRAW',30.48,254);port(t,'NRAW','output',401.32,254,0)
    poly(t,pp('U3',1),(160.02,pp('U3',1)[1]),(160.02,190.5));label(t,'NRAW',160.02,190.5)
    part('R91',119.38,116.84);part('R92',119.38,172.72);part('R93',119.38,193.04)
    poly(t,(119.38,66.04),pp('R91',1));poly(t,pp('R91',2),(119.38,137.16),pp('R92',1));poly(t,(119.38,137.16),pp('U3',5));poly(t,pp('R92',2),pp('R93',1));label(t,'NINV_EN_LO',119.38,182.88);poly(t,pp('R93',2),(119.38,205.74));label(t,'NRAW',119.38,205.74);label(t,'NINV_EN',129.54,137.16)
    for ref,y in [('R9',83.82),('R15',104.14),('R84',124.46),('R10',172.72)]:part(ref,322.58,y)
    poly(t,(322.58,66.04),pp('R9',1));label(t,'GND',322.58,66.04)
    for a,b,n in [('R9','R15','NINV_DIV1'),('R15','R84','NINV_DIV2'),('R84','R10','NINV_FB')]:
        poly(t,pp(a,2),pp(b,1));label(t,n,322.58,pp(a,2)[1])
    poly(t,pp('U3',4),(322.58,pp('U3',4)[1]));poly(t,pp('R10',2),(322.58,190.5));label(t,'NRAW',322.58,190.5)
    # DNP footprint spans ALL THREE upper resistors, never just R84.
    part('C93',383.54,104.14)
    poly(t,(322.58,66.04),(383.54,66.04),pp('C93',1))
    poly(t,pp('C93',2),(383.54,149.86),(322.58,149.86))
    text(t,'DNP / NOT PURCHASED\nAcross R9+R15+R84\nNo tuning value selected',365.76,157.48,1.0)
    for ref,x in zip(OUTPUT_REFS,[213.36,243.84,274.32,304.8,335.28,365.76,396.24]):
        # Capacitor pin1=NRAW below, pin2=GND above.
        part(ref,x,231.14,180)
        poly(t,pp(ref,1),(x,254));poly(t,(x,205.74),pp(ref,2))
    # Cathode1 at top/system GND, anode2 at bottom/NRAW.
    part('D30',195.58,231.14,270)
    poly(t,pp('D30',1),(195.58,205.74));poly(t,pp('D30',2),(195.58,254))
    wire(t,(195.58,205.74),(396.24,205.74));label(t,'GND',213.36,205.74);port(t,'GND','passive',213.36,205.74,180)
    part('#FLG07',401.32,271.78);poly(t,pp('#FLG07',1),(401.32,254))
    text(t,'04 / U3 TPS54302 DIRECT 9V INVERTING BUCK-BOOST',20.32,17.78,2)
    text(t,'NRAW nominal -14.07752V -> retained TPS7A3301 -> N12 -11.99675V. Conditional -300mA objective, NOT a rating.\nIC GND1 = NRAW. L1 returns to SYSTEM GND. EN/FB are referenced to NRAW, never EF_SHDN/BI_EN.\nU4, MID and dormant-positive/VREF/compensation network removed. U5 +5V and U14 positive boost remain independent.',20.32,30.48)
    text(t,'L1: Bourns SRP1245A-220M / C1848803,22uH. 5.0mm max body vs5.1mm allowance, only0.1mm BEFORE solder; NO fit approval.\nC89..92: four Basic2.2u50V C50254 span bypasses; conservative3.01uF screen, not8.8uF effective.\nSeven local22u25V C12891 output caps; separate five-cap U13 input bank. Kelvin NRAW to FB/EN and local IC bypass.\nR9+R15+R84=100k+120k precision +6.2k Basic; R10=10k precision. Upper not entirely0.1%.\n28V recommended VIN/SW span; eFuse OV threshold is NOT clamp. Start/stop, ringing, hot L, loop and reverse paths need bench tests.\nD30 A=NRAW/K=system GND: startup mitigation ONLY, no +0.3V guarantee. Measure U13 IN/NR/FB/OUT. C93 DNP, no selected CFF.\nSR2 SCHEMATIC REVIEW ONLY. Opus + DeepSeek -> corrections/recheck -> user view + explicit ACK -> separate PCB worker.',20.32,284.48)
    split(t);(hw/'04_bipolar.kicad_sch').write_text(dump(t)+'\n')
    path=source/'05_quiet_rails.kicad_sch';original=path.read_text();t=parse(original)
    for n in nodes(t,'text'):
        if n[1].startswith('SR1 PRAW'):n[1]='SR2 PRAW +13.519V / NRAW -14.07752V nominal; independent P5 unchanged.\nSame exact LDOs and N12 precision divider. No rail-synchronous shutdown. PCB remains old/unsynchronized.'
    one(one(t,'title_block'),'rev')[1]='SR2'
    (hw/path.name).write_text(rewrite(original,t))
