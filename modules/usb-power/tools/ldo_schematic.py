"""Explicit ES1 schematic migration and reproducible new functional-sheet layout.

Only called with --ldo-revision into a NEW candidate. Never loads/saves a PCB.
Native unaffected sheets are copied byte-for-byte. Default build still fails on
pin-intent drift instead of silently regenerating an existing user's drawings.
"""
import copy
import json
import math
from pathlib import Path
from sexp import parse, dump, nodes, one, atom
from native_sheet_patch import rewrite


def stage(source, hw, sheets, lib, uid):
    q=json.dumps
    def wire(a,b,key):
        assert a!=b
        return parse(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {q(uid("ldo-wire/"+key))}))')
    def label(net,x,y,key):
        return parse(f'(label {q(net)} (at {x} {y} 0) (effects (font (size 0.95 0.95)) (justify left bottom)) (uuid {q(uid("ldo-label/"+key))}))')
    for p in source.glob('*.kicad_sch'):(hw/p.name).write_bytes(p.read_bytes())
    assert not (source/'05_quiet_rails.kicad_sch').exists(), 'Migration is one-shot; use default build after promotion'
    root=parse((source/'usb-power.kicad_sch').read_text())
    rootid=one(root,'uuid')[1];sheetid=uid('sheet/05_quiet_rails')
    old=next(s for s in nodes(root,'sheet') if any(p[1:3]==['Sheetfile','04_bipolar.kicad_sch'] for p in nodes(s,'property')))
    for pin in nodes(old,'pin'):
        if pin[1] in ('P12','N12'):pin[1]={'P12':'PRAW','N12':'NRAW'}[pin[1]]
    for w in list(nodes(root,'wire')):
        pts=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
        for x in (330.2,360.68):
            if pts==[(x,139.7),(x,198.12)]:
                root.remove(w)
                root.extend([wire((x,139.7),(x,152.4),str(x)+'raw'),wire((x,175.26),(x,198.12),str(x)+'quiet')])
    for l in nodes(root,'label'):
        if l[1] in ('P12','N12'):one(l,'at')[2]=atom(187.96)
    for text in nodes(root,'text'):
        if text[1]=='U4 / +/-12V':text[1]='U4 / INTERNAL +13.531/-13.921V'
        if text[1].startswith('AUTONOMOUS 9 V INPUT'):text[1]='ES1 ELECTRICAL SOURCE / PCB INTEGRATION PENDING'
    new=parse(f'''(sheet (at 309.88 152.4) (size 76.2 22.86)
      (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
      (stroke (width 0.254) (type solid)) (fill (color 0 0 0 0)) (uuid {q(sheetid)})
      (property "Sheetname" "Quiet bipolar post-regulators" (at 309.88 149.86 0) (effects (font (size 1.1 1.1)) (justify left)))
      (property "Sheetfile" "05_quiet_rails.kicad_sch" (at 309.88 177.8 0) (effects (font (size 0.85 0.85)) hide))
      (instances (project "usb-power" (path {q('/'+rootid)} (page "6")))))''')
    for n,t,x,y,a in [('PRAW','input',330.2,152.4,90),('NRAW','input',360.68,152.4,90),
                       ('P12','output',330.2,175.26,270),('N12','output',360.68,175.26,270),('GND','passive',309.88,165.1,180)]:
        new.append(parse(f'(pin {q(n)} {t} (at {x} {y} {a}) (effects (font (size 1.15 1.15)) (justify {"right" if a==90 else "left"})) (uuid {q(uid("ldo-sheet-pin/"+n))}))'))
    root.append(new);root.extend([wire((302.26,165.1),(309.88,165.1),'rootgnd'),label('GND',302.26,165.1,'rootgnd')])
    for s in nodes(root,'sheet'):
        if any(p[1:3]==['Sheetfile','07_output_rails.kicad_sch'] for p in nodes(s,'property')):
            one(one(one(s,'instances'),'project'),'path')[2][1]='7'
    (hw/'usb-power.kicad_sch').write_text(rewrite((source/'usb-power.kicad_sch').read_text(),root))
    p=hw/'04_bipolar.kicad_sch';t=parse(p.read_text())
    for typ in ('label','hierarchical_label'):
        for v in nodes(t,typ):
            if v[1] in ('P12','N12'):v[1]={'P12':'PRAW','N12':'NRAW'}[v[1]]
    ports={(n[1],tuple(one(n,'at')[1:3])) for n in nodes(t,'hierarchical_label')}
    for n in list(nodes(t,'label')):
        if (n[1],tuple(one(n,'at')[1:3])) in ports:t.remove(n)
    for v in nodes(t,'text'):
        if v[1].startswith('Nominal +/-11.968'):v[1]=sheets['04_bipolar']['notes']
        if v[1].startswith('04 /'):v[1]='04 / INTERNAL RAW BIPOLAR RAILS'
    approved_raw_dividers(t,uid)
    p.write_text(rewrite((source/p.name).read_text(),t))

    parts={p['ref']:p for p in sheets['05_quiet_rails']['parts']}
    t=parse(f'''(kicad_sch (version 20250114) (generator "eeschema")
      (uuid {q(uid('05_quiet_rails'))}) (paper "User" 430 345)
      (title_block (title "Big Modular - quiet bipolar post-regulators") (rev "ES1 source only")
       (company "Big Modular") (comment 1 "PCB INTEGRATION PENDING - NOT FOR FABRICATION"))
      (lib_symbols) (embedded_fonts no))''')
    used=sorted({d['kind'] for d in parts.values()})
    for k in used:
        sym=copy.deepcopy(lib[k]);sym[1]='BigModular:'+k;one(t,'lib_symbols').append(sym)
    pins={};count=0;ends=[]
    def addwire(a,b):
        nonlocal count
        if a==b:return
        count+=1;t.append(wire(a,b,'quiet/'+str(count)));ends.extend([a,b])
    def poly(*ps):
        for a,b in zip(ps,ps[1:]):addwire(a,b)
    def part(ref,x,y,a=0):
        d=parts[ref];su=uid('05_quiet_rails/'+ref)
        s=parse(f'''(symbol (lib_id {q('BigModular:'+d['kind'])}) (at {x} {y} {a}) (unit 1)
          (in_bom yes) (on_board yes) (dnp no) (uuid {q(su)})
          (instances (project "usb-power" (path {q('/'+rootid+'/'+sheetid)} (reference {q(ref)}) (unit 1)))))''')
        for k,v,hide,dy in [('Reference',ref,False,-4),('Value',d['value'],False,-1.5),('Footprint',d['fp'],True,0),('Datasheet',d['datasheet'],True,0),('MPN',d['mpn'],True,0),('LCSC',d['lcsc'],True,0),('NOTE',d['note'],True,0),('Manufacturer',d['manufacturer'],True,0)]:
            # IC fields above their tall bodies, passives just above the body.
            yy=y+(dy-35.56 if ref.startswith('U') else dy)
            xx=x
            if ref.startswith('U') and not hide:
                rect=next(r for unit in nodes(lib[d['kind']],'symbol') for r in nodes(unit,'rectangle'))
                top=y-float(one(rect,'start')[2]);yy=top+(-5.08 if k=='Reference' else -2.54)
            if ref.startswith(('C','R')) and not hide:xx=x+3.81;yy=y+(-1.27 if k=='Reference' else 1.27)
            s.append(parse(f'(property {q(k)} {q(v)} (at {xx} {yy} 0) (effects (font (size 1.05 1.05)) {"(justify left)" if ref.startswith(("R","C")) and not hide else ""} {"hide" if hide else ""}))'))
        for unit in nodes(lib[d['kind']],'symbol'):
            for p in nodes(unit,'pin'):
                n=one(p,'number')[1];px,py=map(float,one(p,'at')[1:3]);r=math.radians(a)
                pos=(round(x+px*math.cos(r)-py*math.sin(r),5),round(y-px*math.sin(r)-py*math.cos(r),5))
                pins[(ref,n)]=pos;s.append(parse(f'(pin {q(n)} (uuid {q(uid(su+'/'+n))}))'))
                if d['nets'][n] is None:t.append(parse(f'(no_connect (at {pos[0]} {pos[1]}) (uuid {q(uid(su+"/NC/"+n))}))'))
        t.append(s)
    def pp(r,p):return pins[(r,str(p))]
    def port(n,shape,x,y,ang):
        t.append(parse(f'(hierarchical_label {q(n)} (shape {shape}) (at {x} {y} {ang}) (effects (font (size 1.15 1.15)) (justify {"right" if ang==0 else "left"})) (uuid {q(uid("ldo-port/"+n))}))'))
    def text(value,x,y,size=1.1):
        t.append(parse(f'(text {q(value)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left top)) (uuid {q(uid("ldo-text/"+value))}))'))
    part('U12',203.2,86.36);part('U13',203.2,210.82)
    for u,base,raw,out,yrail,ygnd,cy,nr,dy in [
        ('U12',48,'PRAW','P12',60.96,127.,91.44,'C60',45.72),
        ('U13',54,'NRAW','N12',182.88,281.94,218.44,'C61',167.64)]:
        xs=(86.36,111.76,137.16);oxs=(284.48,309.88,335.28) if u=='U12' else (304.8,330.2,355.6)
        # Split every T explicitly; junction inference below only adds real 3-way nodes.
        input_xs=[45.72,*xs,157.48,pp(u,15)[0]]
        for x1,x2 in zip(input_xs,input_xs[1:]):addwire((x1,yrail),(x2,yrail))
        poly((157.48,yrail),(157.48,pp(u,16)[1]),pp(u,16))
        poly((157.48,pp(u,16)[1]),(157.48,pp(u,13)[1]),pp(u,13))
        poly(pp(u,1),(248.92,yrail),*( (x,yrail) for x in oxs ),(381.,yrail))
        poly(pp(u,20),(248.92,pp(u,20)[1]),(248.92,yrail))
        if u=='U12':poly(pp(u,3),(243.84,pp(u,3)[1]),(243.84,pp(u,20)[1]))
        groundxs=sorted(set([45.72,*xs,170.18,180.34,182.88,238.76,251.46,*oxs]))
        for x1,x2 in zip(groundxs,groundxs[1:]):addwire((x1,ygnd),(x2,ygnd))
        for j,x in enumerate(xs):
            r='C'+str(base+j);part(r,x,cy);poly((x,yrail),pp(r,1));poly(pp(r,2),(x,ygnd))
        for j,x in enumerate(oxs):
            r='C'+str(base+3+j);part(r,x,cy);poly((x,yrail),pp(r,1));poly(pp(r,2),(x,ygnd))
        nry=101.6 if u=='U12' else 223.52;part(nr,170.18,nry)
        poly(pp(u,14),(170.18,pp(u,14)[1]),pp(nr,1));poly(pp(nr,2),(170.18,ygnd))
        for pn,x in [(7,180.34),(21,182.88)]:poly(pp(u,pn),(x,pp(u,pn)[1]),(x,ygnd))
        if u=='U12':
            for pn in (5,6,9,11):poly(pp(u,pn),(238.76,pp(u,pn)[1]))
            ys=sorted([pp(u,pn)[1] for pn in (5,6,9,11)]+[ygnd])
            for a,b in zip(ys,ys[1:]):addwire((238.76,a),(238.76,b))
        diode='D27' if u=='U12' else 'D28';part(diode,203.2,dy,0 if u=='U12' else 180)
        poly((152.4,yrail),(152.4,dy),pp(diode,1 if u=='U12' else 2))
        poly(pp(diode,2 if u=='U12' else 1),(254.,dy),(254.,yrail))
        port(raw,'input',45.72,yrail,180);port(out,'output',381.,yrail,0)
        if u=='U13':t.append(label('GND',45.72,ygnd,'quiet/'+u))
    port('GND','passive',45.72,127.,180)
    for r,y in [('R72',198.12),('R83',210.82),('R73',223.52),('R74',248.92)]:part(r,251.46,y)
    poly((251.46,182.88),pp('R72',1));poly(pp('R72',2),pp('R83',1));poly(pp('R83',2),pp('R73',1));poly(pp('R73',2),(251.46,233.68),pp('R74',1));poly(pp('R74',2),(251.46,281.94))
    poly(pp('U13',3),(238.76,pp('U13',3)[1]),(238.76,233.68),(251.46,233.68))
    part('C62',274.32,213.36);poly((274.32,182.88),pp('C62',1));poly(pp('C62',2),(274.32,236.22),(251.46,236.22))
    # Add local labels at existing wire points for all distinct nets, including NR/FB.
    for ref,pin,n in [('U12','14','P_NR'),('U13','14','N_NR'),('U13','3','N_LDO_FB'),('R72','2','N_LDO_SER'),('R83','2','N_LDO_DIV')]:
        x,y=pp(ref,pin)
        if n in ('P_NR','N_NR'):x=170.18
        if n=='N_LDO_SER':y=204.47
        if n=='N_LDO_DIV':y=217.17
        t.append(label(n,x,y,n))
    # Segment split at any explicit endpoint touching a wire (never connect crossings).
    allpoints=set(ends)
    for w in list(nodes(t,'wire')):
        a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
        interior=[]
        for p in allpoints:
            if p in (a,b):continue
            if abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<1e-7 and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]):interior.append(p)
        if interior:
            t.remove(w);ps=sorted([a,b,*interior]);
            for aa,bb in zip(ps,ps[1:]):addwire(aa,bb)
    from collections import Counter
    degrees=Counter(tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:])
    for (x,y),d in degrees.items():
        if d>=3:t.append(parse(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid("ldo-junction/"+str((x,y))))}))'))
    text('05 / QUIET BIPOLAR POST-REGULATORS - ELECTRICAL SOURCE ONLY',20.32,17.78,2)
    text('Raw +13.537080/-13.928806V remain internal. Final +5V is unchanged and bypasses this sheet.\nBoth exposed pads 21 are GND. Exact requested RGWR parts; NOT a +/-1A supply.',20.32,27.94)
    text('U12 ANY-OUT: 5,6,9,11 to GND; 4,8,10,12 float. SENSE3 -> final output.\nC60 sees approximately +12V. Three 22u MLCCs per bank = 66u NOMINAL, not effective.\nRequire >=10u effective at each IN/OUT; >=20u at positive OUT for accuracy conditions.',20.32,137.16)
    text('R72+R83+R73 / R74 = 92.3k / 10k -> -12.02025V before IFB; 117.5uA nominal divider current (>5uA required).\nBasic 1%,100ppm/K divider; corners and negative full-temperature dropout are conditional, not a1A guarantee.\nC61 100n: typical ~120ms start, not rail sequencing. C62 10n improves AC; shutdown FB kick remains a test gate.\nD27/D28 divert reverse current, do NOT block it. SS34 Vf does NOT prove the negative -0.3V differential limit.\n800mA aspiration is load-dependent, not a simultaneous rail guarantee. Capacitor bias/ESR, transient and board thermal qualification pending.',20.32,292.1)
    (hw/'05_quiet_rails.kicad_sch').write_text(dump(t)+'\n')


def approved_raw_dividers(tree, uid):
    """Insert the two precise series elements into the reviewed raw-rail drawing.

    Explicit one-shot native circuit edit, not label-only setpoint changes. Called
    by the legacy migration too; the normal renderer independently checks all pins.
    """
    from sexp import walk
    refs={next(p[2] for p in nodes(s,'property') if p[1]=='Reference'):s for s in nodes(tree,'symbol')}
    assert 'R75' not in refs and 'R76' not in refs
    for ref,template,x,y,start,end,net in [
        ('R75','R12',269.24,107.95,100.33,115.57,'POS_DIV'),
        ('R76','R15',274.32,232.41,227.33,236.22,'NEG_REF_DIV')]:
        new=copy.deepcopy(refs[template]);ox,oy=map(float,one(new,'at')[1:3]);dx,dy=x-ox,y-oy
        for node in [n for key in ('uuid','at','reference') for n in walk(new,key)]:
            if node[0]=='uuid':node[1]=uid(ref+'/'+str(node[1]))
            elif node[0]=='at':node[1]=atom(round(float(node[1])+dx,5));node[2]=atom(round(float(node[2])+dy,5))
            elif node[0]=='reference':node[1]=ref
        next(p for p in nodes(new,'property') if p[1]=='Reference')[2]=ref
        tree.append(new)
        old=next(w for w in nodes(tree,'wire') if [tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]==[(x,start),(x,end)])
        tree.remove(old)
        for i,(a,b) in enumerate([(start,round(y-3.81,5)),(round(y+3.81,5),end)]):
            if a==b:continue
            w=copy.deepcopy(old);one(w,'uuid')[1]=uid(ref+'/wire/'+str(i));one(w,'pts')[1:]=[[atom('xy'),atom(x),atom(a)],[atom('xy'),atom(x),atom(b)]];tree.append(w)
        ly=104.14 if ref=='R75' else 228.6
        tree.append(parse(f'(label "{net}" (at {x} {ly} 0) (effects (font (size 0.95 0.95)) (justify left bottom)) (uuid "{uid(ref+"/label")}"))'))
    return tree


def strengthen_cap_banks(source, hw, uid):
    """Bounded one-shot parallel-cap migration; preserve all other native objects."""
    from collections import Counter
    for p in source.glob('*.kicad_sch'):(hw/p.name).write_bytes(p.read_bytes())
    path=hw/'05_quiet_rails.kicad_sch';original=path.read_text();t=parse(original)
    syms={next(p[2] for p in nodes(s,'property') if p[1]=='Reference'):s for s in nodes(t,'symbol')}
    assert not set(syms)&{'C63','C64','C65','C66','C67'},'Already migrated'
    one(t,'paper')[2]=atom(460)
    def line(a,b,key):
        if a==b:return
        t.append(parse(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {json.dumps(uid("cap-revision/"+key))}))'))
    for ref,old,x,y,rail,ground in [('C63','C48',60.96,91.44,60.96,127.),
            ('C64','C51',360.68,91.44,60.96,127.),('C65','C51',386.08,91.44,60.96,127.),
            ('C66','C51',411.48,91.44,60.96,127.),('C67','C54',60.96,218.44,182.88,281.94)]:
        sym=copy.deepcopy(syms[old]);ox,oy=map(float,one(sym,'at')[1:3]);dx,dy=x-ox,y-oy
        one(sym,'uuid')[1]=uid('05_quiet_rails/'+ref);one(sym,'at')[1:3]=[atom(x),atom(y)]
        for prop in nodes(sym,'property'):
            if prop[1]=='Reference':prop[2]=ref
            a=one(prop,'at');a[1:3]=[atom(float(a[1])+dx),atom(float(a[2])+dy)]
        inst=one(one(one(sym,'instances'),'project'),'path');one(inst,'reference')[1]=ref
        for pin in nodes(sym,'pin'):one(pin,'uuid')[1]=uid('cap-revision/'+ref+'/'+pin[1])
        t.append(sym)
        # Device:C native pin1 is +3.81mm in symbol coordinates (screen y minus).
        line((x,rail),(x,y-3.81),ref+'/rail');line((x,y+3.81),(x,ground),ref+'/gnd')
    line((381.,60.96),(411.48,60.96),'P12-extension')
    line((335.28,127.),(411.48,127.),'GND-extension')
    points={tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:]}
    for i,w in enumerate(list(nodes(t,'wire'))):
        a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]
        inside=[p for p in points if p not in (a,b) and abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<1e-7 and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1])]
        if inside:
            t.remove(w);ps=sorted([a,b,*inside])
            for j,(a,b) in enumerate(zip(ps,ps[1:])):line(a,b,f'split/{i}/{j}')
    degree=Counter(tuple(map(float,p[1:])) for w in nodes(t,'wire') for p in one(w,'pts')[1:])
    junctions={tuple(map(float,one(j,'at')[1:])) for j in nodes(t,'junction')}
    for (x,y),d in degree.items():
        if d>=3 and (x,y) not in junctions:
            t.append(parse(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {json.dumps(uid("cap-junction/"+str((x,y))))}))'))
    for text in nodes(t,'text'):
        text[1]=text[1].replace('ELECTRICAL SOURCE ONLY','LDO-R1 PROTOTYPE')
        text[1]=text[1].replace('Three 22u MLCCs per bank = 66u NOMINAL, not effective.','4/6/4/3 x22u on IN+/OUT+/IN-/OUT-; typical bias + tolerance/temp/aging screen passes.')
    path.write_text(rewrite(original,t))
