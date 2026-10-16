"""Seven functional review subsheets and a wired power-flow overview.

Presentation only: inventory, symbol UUIDs, pin numbers and component fields remain
owned by build_project.py. Explicit local wires replace label-only branches.
The shared toolkit supports flat wire edits, not sheet/symbol reorganization;
this project-specific renderer therefore owns hierarchy as well as placement.
Coordinates use 2.54 mm units. Labels identify wires, not hidden local connections.
"""
import copy
import json
import math
from collections import defaultdict
from sexp import dump, one, walk


SHEET_NAMES = ('01_input_protection', '02_hardgate', '03_bucks', '04_bipolar', '05_diagnostics', '06_sensing', '07_output_rails')
SHEET_TITLES = ('USB PD and housekeeping', 'Hardware gate', 'Independent bucks', 'Direct bipolar rails', 'Rail debug and power LED', 'Protected sensing', 'Output harness')


def render(hw, sheets, lib, uid):
    parts = {d['ref']: copy.deepcopy(d) for sh in sheets.values() for d in sh['parts']}
    q = lambda s: json.dumps(str(s))
    def effects(size=1.05, just=''):
        return f'(effects (font (size {size} {size}))' + (f' (justify {just})' if just else '') + ')'
    def mm(p): return tuple(round(float(v)*2.54, 5) for v in p)

    class Drawing:
        def __init__(self, name, title, page, paper='A2'):
            self.name, self.title, self.page = name, title, page
            self.root = name == 'big_modular'
            self.uuid = uid('root' if self.root else 'page/'+name)
            self.path = '/'+uid('root') + ('' if self.root else '/'+uid('sheet/'+name))
            self.out = [f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(self.uuid)}) (paper "User" 430 345)',
                        f'(title_block (title {q("Big Modular - "+title)}) (rev "Wired review") (company "Big Modular") (comment 1 "INCOMPLETE / NON-OPERATIONAL / DO NOT FABRICATE"))']
            self.parts, self.pins, self.used = {}, {}, set()
            self.segments, self.labels, self.ports = [], {}, {}
            self.port_types = {}

        def place(self, ref, x, y, angle=0, mirror=None):
            assert ref not in assigned, ('Duplicate placement', ref)
            assigned.add(ref)
            d=parts[ref];d.update(x=x, y=y, angle=angle, mirror=mirror)
            self.parts[ref]=d
            a=math.radians(angle);co=round(math.cos(a));si=round(math.sin(a))
            for pin in walk(lib[d['kind']], 'pin'):
                n=str(one(pin,'number')[1]);at=one(pin,'at')
                lx=float(at[1])/2.54;ly=float(at[2])/2.54
                px,py=lx*co-ly*si,-lx*si-ly*co
                pa=(int(at[3])+angle)%360
                if mirror=='y':px=-px;pa=(180-pa)%360
                if mirror=='x':py=-py;pa=(-pa)%360
                p=(round(x+px,5),round(y+py,5))
                self.pins[(ref,n)]=(p,pa,d['nets'][n])

        def p(self, ref, pin):
            key=(ref,str(pin));pos,_,net=self.pins[key]
            for k,(p,_,n) in self.pins.items():
                if p==pos and n==net:self.used.add(k)
            return pos

        def wire(self, net, *points):
            for a,b in zip(points,points[1:]):
                a,b=tuple(a),tuple(b)
                if a==b:continue
                assert a[0]==b[0] or a[1]==b[1], (self.name,net,a,b)
                self.segments.append((net,a,b))

        def connect(self, a, b, *via):
            na=self.pins[(a[0],str(a[1]))][2];nb=self.pins[(b[0],str(b[1]))][2]
            assert na is not None and na==nb,(a,b,na,nb)
            self.wire(na,self.p(*a),*via,self.p(*b))

        def label(self, net, p, angle=0):
            p=tuple(p)
            if p in self.labels:
                assert self.labels[p]==net
                return
            self.labels[p]=net;x,y=mm(p)
            self.out.append(f'(label {q(net)} (at {x} {y} {angle}) {effects(.95,"left bottom")} (uuid {q(uid(self.name+"/label/"+str((net,p))))}))')

        def port(self, net, p, direction='input', angle=0):
            assert net not in self.ports
            self.ports[net]=p;self.port_types[net]=direction;x,y=mm(p)
            self.out.append(f'(hierarchical_label {q(net)} (shape {direction}) (at {x} {y} {angle}) {effects(1.1,"left" if angle==0 else "right")} (uuid {q(uid(self.name+"/port/"+net))}))')

        def text(self, s, x, y, size=1.15):
            x,y=mm((x,y))
            self.out.append(f'(text {q(s)} (at {x} {y} 0) {effects(size,"left")} (uuid {q(uid(self.name+"/text/"+str((s,x,y))))}))')

        def ground(self, *keys, y):
            points=[]
            for key in keys:
                assert self.pins[(key[0],str(key[1]))][2]=='GND'
                p=self.p(*key);self.wire('GND',p,(p[0],y));points.append((p[0],y))
            points.sort()
            self.wire('GND',*points)
            self.label('GND',points[0])

        def finish(self):
            # Ground/RTN and ERC declarations may use short named stubs; every
            # other real pin MUST be explicitly wired by the layout below.
            for key,(p,a,net) in self.pins.items():
                if key in self.used:continue
                self.p(*key);x,y=mm(p)
                if net is None:
                    self.out.append(f'(no_connect (at {x} {y}) (uuid {q(uid(key[0]+"nc"+key[1]))}))')
                    continue
                # Remaining pins are explicitly named inter-block continuations.
                # Sensitive local paths are connected and independently asserted below.
                dx,dy={0:(-2,0),90:(0,2),180:(2,0),270:(0,-2)}[a]
                end=(p[0]+dx,p[1]+dy)
                self.wire(net,p,end);self.label(net,end,0)
            bynet=defaultdict(set)
            for net,a,b in self.segments:bynet[net].update([a,b])
            for net,a,b in self.segments:
                if a[1] != b[1]:continue
                for other,c,d in self.segments:
                    if other==net and c[0]==d[0] and min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(c[1],d[1])<=a[1]<=max(c[1],d[1]):
                        bynet[net].add((c[0],a[1]))
            for p,net in self.labels.items():bynet[net].add(p)
            for net,p in self.ports.items():bynet[net].add(p)
            # Split at same-net pins, labels and tees; deterministic output.
            for p,_,net in self.pins.values():
                if net is not None:bynet[net].add(p)
            emitted=set()
            for net,a,b in self.segments:
                axis=0 if a[1]==b[1] else 1
                ps=sorted((p for p in bynet[net] if p[1-axis]==a[1-axis] and min(a[axis],b[axis])<=p[axis]<=max(a[axis],b[axis])), key=lambda p:p[axis])
                emitted.update((net,p1,p2) for p1,p2 in zip(ps,ps[1:]))
            points={(n,p) for n,a,b in emitted for p in (a,b)}
            points.update((n if n is not None else 'NC:'+str(k),p) for k,(p,_,n) in self.pins.items())
            conflicts=set()
            for n,a,b in emitted:
                axis=0 if a[1]==b[1] else 1
                for other,p in points:
                    if other!=n and p[1-axis]==a[1-axis] and min(a[axis],b[axis])<=p[axis]<=max(a[axis],b[axis]):
                        conflicts.add((n,other,p))
            assert not conflicts, ('Cross-net or NC wire contact',self.name,sorted(conflicts))
            ends=defaultdict(set)
            for net,a,b in sorted(emitted):
                x1,y1=mm(a);x2,y2=mm(b)
                self.out.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid {q(uid(self.name+"/wire/"+str((net,a,b))))}))')
                ends[(net,a)].add(b);ends[(net,b)].add(a)
            # Name each physically connected wire cluster once, rather than
            # labelling every pin or leaving native autogenerated net names.
            seen=set()
            for start in sorted(ends):
                if start in seen:continue
                net,p=start;stack=[p];cluster=set()
                while stack:
                    pt=stack.pop()
                    if pt in cluster:continue
                    cluster.add(pt);seen.add((net,pt));stack.extend(ends[(net,pt)])
                if not any(self.labels.get(pt)==net or self.ports.get(net)==pt for pt in cluster):
                    candidates=sorted(((a,b) for n,a,b in emitted if n==net and a in cluster and a[1]==b[1]),
                                      key=lambda e:(-abs(e[0][0]-e[1][0]),e))
                    def clear(pt):
                        return not any(n!=net and
                            ((a[1]==b[1]==pt[1] and min(a[0],b[0])<=pt[0]<=max(a[0],b[0])) or
                             (a[0]==b[0]==pt[0] and min(a[1],b[1])<=pt[1]<=max(a[1],b[1])))
                            for n,a,b in emitted)
                    choices=[(round(a[0]+b[0])/2,a[1]) for a,b in candidates]
                    choices += sorted(cluster)
                    self.label(net,next(pt for pt in choices if clear(pt)))
            for (net,p),e in sorted(ends.items()):
                if len(e)>2:
                    x,y=mm(p)
                    self.out.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid(self.name+"/junction/"+str((net,p))))}))')
            caches=[]
            for kind in sorted({d['kind'] for d in self.parts.values()}):
                s=copy.deepcopy(lib[kind]);s[1]='BigModular:'+kind;caches.append(dump(s))
            self.out.insert(2,'(lib_symbols '+''.join(caches)+')')
            for ref,d in self.parts.items():
                x,y=mm((d['x'],d['y']));a=d['angle']
                if (ref[0] in 'RCLF' and a in (0,180)) or (ref.startswith('D') and a in (90,270)):
                    tx,ty=x+3,y-1.2;just='right' if a==90 else 'left'
                else:
                    top=min(p[0][1] for k,p in self.pins.items() if k[0]==ref)*2.54
                    tx,ty=x,top-6;just=''
                if ref=='U1':tx-=7.62  # keep the value clear of the vertical VDD wire
                inst=[f'(symbol (lib_id {q("BigModular:"+d["kind"])}) (at {x} {y} {a}) (unit 1) (in_bom {"no" if ref.startswith("#") else "yes"}) (on_board {"yes" if d["onboard"] else "no"}) (dnp no) (uuid {q(uid(ref))})',
                      f'(property "Reference" {q(ref)} (at {tx} {ty} {90 if a in (90,270) else 0}) {effects(1.27,just)})',
                      f'(property "Value" {q(d["value"])} (at {tx} {ty+2.54} {90 if a in (90,270) else 0}) {effects(1.15,just)})']
                if d.get('mirror'):inst.append(f'(mirror {d["mirror"]})')
                for k,v in [('Footprint',d['fp']),('MPN',d['mpn']),('LCSC',d['lcsc']),('NOTE',d['note']),('Datasheet',d.get('datasheet','')),('JLCPCB Exclude','yes' if d.get('manual') else 'no'),('JLCPCB Audit Requirements',json.dumps({'assembly':'manual','reason':'User-selected manual interface/LED, excluded from JLC placement.'}) if d.get('manual') else '{}')]:
                    inst.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1 1)) hide))')
                for n in d['nets']:inst.append(f'(pin {q(n)} (uuid {q(uid(ref+"pin"+n))}))')
                inst.append(f'(instances (project "big_modular" (path {q(self.path)} (reference {q(ref)}) (unit 1)))) )')
                self.out.append(''.join(inst))
            if self.root:self.out.append('(sheet_instances (path "/" (page "1")))')
            self.out.append('(embedded_fonts no))')
            (hw/(self.name+'.kicad_sch')).write_text('\n'.join(self.out)+'\n')

    assigned=set()
    drawings=[]
    for i,name in enumerate(SHEET_NAMES):
        sh=sheets[name];s=Drawing(name,sh['title'],i+2);drawings.append(s)
        s.text(f'{i+1:02} / {sh["title"].upper()}',8,7,2.2)
        s.text(sh['notes'],8,12,1.02)

    def place(s,*items):
        for item in items:s.place(*item)
    def join(s,a,b,*via):
        pa=s.p(*a);pb=s.p(*b)
        if not via and pa[0]!=pb[0] and pa[1]!=pb[1]:via=((pb[0],pa[1]),)
        s.connect(a,b,*via)
    def stub(s,ref,pin):
        key=(ref,str(pin));p,a,n=s.pins[key]
        if n is None:return
        dx,dy={0:(-3,0),90:(0,3),180:(3,0),270:(0,-3)}[a]
        end=(p[0]+dx,p[1]+dy);s.wire(n,s.p(ref,pin),end);s.label(n,end)
    def net(s,ref,pin):return s.pins[(ref,str(pin))][2]
    def divider(s,top,bottom,chip,pin,via=()):
        join(s,(top,2),(bottom,1));join(s,(chip,pin),(top,2),*via)

    def port(s, ref, pin, at, direction='input', angle=180, via=()):
        n=net(s,ref,pin);p=s.p(ref,pin)
        s.port(n,at,direction,angle)
        if not via and p[0]!=at[0] and p[1]!=at[1]:via=((at[0],p[1]),)
        s.wire(n,p,*via,at)

    s=drawings[0]
    place(s,('J1',18,32),('F1',38,26,90),('U1',64,46),('C1',47,36),('R2',88,53),('R3',108,51),('U9',47,83),('C33',28,83),('C34',72,83),('R35',90,83))
    join(s,('J1','A4'),('F1',1));join(s,('F1',2),('U1',1),(47,26),(54,26),(54,40))
    join(s,('U1',1),('U1',8),(54,40),(54,42));join(s,('F1',2),('C1',1),(47,26))
    join(s,('J1','A5'),('U1',7),(32,28),(32,44));join(s,('J1','B5'),('U1',6),(35,29),(35,46))
    join(s,('U1',4),('U1',5),(54,48),(54,50));join(s,('U1',9),('R2',1),(88,44))
    join(s,('U1',10),('R3',2),(96,46),(96,57),(108,57))
    join(s,('U9',1),('C33',1),(35,81),(35,76),(28,76))
    join(s,('U9',3),('C34',1),(64,81),(64,76),(72,76));join(s,('C34',1),('R35',1))
    s.text('Direct VBUS feed replaces the old CH224K 1k supply dropper.\nI2C 0x22/0x23; status 0x09 bit3 = PD active; current 0x50 x50mA.\nPG alone is not proof. Verify WCH silicon/document discrepancy before power.',8,64,1.1)

    # Housekeeping is one locally wired regulator with a common return.
    s.ground(('C33',2),('C34',2),('R35',2),y=91)
    join(s,('U9',2),('U9',4),(38,83),(38,85))
    s.wire('GND',s.p('U9',4),(38,85),(38,91))
    port(s,'F1',1,(36.5,21),'output',0)
    port(s,'F1',2,(122,26),'output',0)
    port(s,'U9',3,(106,81),'output',0,((64,81),))
    port(s,'U1',10,(122,57),'output',0,((96,46),(96,57)))
    port(s,'U1',2,(82,35),'bidirectional',0,((77,40),(77,35)))
    port(s,'U1',3,(82,40),'bidirectional',0,((79,42),(79,40)))
    port(s,'C33',2,(23,91),'passive',180,((28,91),))

    s=drawings[1]
    place(s,('U2',84,42),('R4',27,36),('R5',27,44),('R6',48,40),('R7',48,48),('R8',112,50),('R36',139,60),('R37',116,31),('C2',15,54),('C3',125,55),('C4',144,31),('R31',153,31),('Q1',34,79),('R28',23,79,90),('R29',45,88),('JP1',113,77),('R30',129,86))
    divider(s,'R4','R5','U2',3,((65,37),(65,30),(34,30),(34,40.5),(27,40.5)))
    divider(s,'R6','R7','U2',5,((68,39),(68,44.5),(48,44.5)))
    join(s,('U2',11),('R8',1),(112,39));join(s,('U2',12),('C3',1),(125,41));join(s,('U2',6),('R36',1),(139,43))
    join(s,('U2',14),('R37',2),(104,37),(104,36),(116,36))
    join(s,('U2',15),('C4',1),(136,33),(136,25),(144,25));join(s,('C4',1),('R31',1))
    join(s,('R28',2),('Q1',1))
    join(s,('Q1',2),('R29',1),(45,81));join(s,('Q1',1),('R29',2),(30,79),(30,94),(45,94))
    join(s,('Q1',3),('JP1',1));join(s,('JP1',2),('R30',1),(129,77))
    join(s,('JP1',2),('U2',7),(120,77),(120,69),(71,69),(71,41))
    s.text('Hardware PG -> Q1 -> JP1 -> SHDN, always subject to UV/OV window.\nRUN must be deliberately closed only after power-up blockers are cleared.',8,104,1.05)

    # Fuse input, output reservoir and independent RTN bias branches.
    s.wire('VBUS_FUSED',(15,23),(74,23),(74,33),s.p('U2',1))
    join(s,('U2',1),('U2',2),(74,33),(74,35))
    for ref in ('R4','R6','C2'):
        p=s.p(ref,1);s.wire('VBUS_FUSED',(p[0],23),p)
    join(s,('U2',15),('U2',16),(99,33),(99,35))
    join(s,('U2',8),('U2',17),(75,45),(75,47))
    s.wire('RTN',s.p('U2',17),(75,47),(75,63))
    for ref in ('R5','R7','R8','R36','C3'):
        p=s.p(ref,2);s.wire('RTN',p,(p[0],63))
    s.wire('RTN',(27,63),(139,63));s.label('RTN',(139,63))
    s.ground(('C4',2),('R31',2),y=40)
    port(s,'C2',1,(10,23),via=((15,23),))
    port(s,'U2',15,(156,25),'output',0,((136,33),(136,25)))
    port(s,'JP1',2,(136,77),'output',0)
    port(s,'R37',2,(124,36),'output',0,((116,36),))
    port(s,'R37',1,(104,23),via=((116,23),))
    port(s,'R28',1,(12,79))
    port(s,'C2',2,(10,60),'passive',180,((15,60),))

    s=drawings[2]
    for cy,u,l,ci,co,dec,boot,co2,rt,rb,prefix,out in [(37,'U3','L1','C5','C6','C7','C35','C37','R9','R10','MID','MID'),(81,'U5','L4','C18','C19','C20','C36','C38','R17','R18','FIVE','P5')]:
        place(s,(u,39,cy),(l,73,cy,90),(ci,15,cy+12),(dec,24,cy+12),(co,99,cy+12),(co2,116,cy+12),(boot,59,cy-11),(rt,82,cy+7),(rb,82,cy+15))
        join(s,(u,3),(ci,1),(29,cy-2),(29,cy-7),(15,cy-7));join(s,(ci,1),(dec,1))
        join(s,(u,2),(l,1));join(s,(u,6),(boot,1),(53,cy-2),(53,cy-17),(59,cy-17))
        join(s,(boot,2),(u,2),(63,cy-9.5),(63,cy))
        join(s,(l,2),(co,1),(99,cy));join(s,(co,1),(co2,1));join(s,(l,2),(rt,1),(82,cy))
        divider(s,rt,rb,u,4,((52,cy+2),(52,cy+11),(82,cy+11)))
        s.ground((ci,2),(dec,2),(co,2),(co2,2),(rb,2),y=cy+21)
        s.wire('GND',s.p(u,1),(30,cy+2),(30,cy+21))
        s.wire('VPROT',(9,cy-7),(15,cy-7))
        s.wire('EF_ENABLE',(27,cy),s.p(u,5))
        port(s,l,2,(133,cy),'output',0)
        s.text(f'{u}: {out} / '+('5.216 V' if u=='U3' else '5.011 V'),9,cy-17,1.35)
    s.text('BOOT caps are switch-node referenced, not grounded.\nKelvin FB ground to IC GND; keep high di/dt loops off analog return.\n6.8uH magnetics here are explicit candidates, not qualified choices.',105,68,1.0)

    s.wire('VPROT',(9,25),(9,74));s.port('VPROT',(9,25),'input',180)
    s.wire('EF_ENABLE',(27,37),(27,81));s.port('EF_ENABLE',(20,37),'input',180)
    s.wire('EF_ENABLE',(20,37),(27,37))
    port(s,'C5',2,(12,60),'passive',180,((15,60),))

    # Retain the proven readable U4 layout with direct-output net names.
    s=drawings[3];p=s.p;w=s.wire;c=s.connect
    place(s,('U4',69,51),('L2',55,28,90),('D2',82,28,180),('L3',85,69),('D3',97,63),('C8',137,37),('C9',140,72),('R12',106,38),('R13',106,49),('C10',122,38),('R14',108,70),('R60',108,77),('R15',108,88),('C11',125,74),('C12',90,97),('C13',90,79),('C14',78,79),('R16',41,50,90),('C15',51,62),('C16',16,35),('C17',31,35),('R40',27,67),('R38',16,57))
    c(('L2',2),('D2',2));w('BOOST_SW',(63,28),(63,45),p('U4',1))
    w('P12',p('D2',1),(146,28));s.label('P12',(146,28));w('P12',(98,28),(98,43),(77,43),(77,45),p('U4',23))
    for ref in ['C8','R12','C10']:w('P12',(parts[ref]['x'],28),p(ref,1))
    c(('R12',2),('R13',1));w('POS_FB',p('U4',22),(122,46),p('C10',2));s.label('POS_FB',(96,46))
    c(('R16',2),('U4',4));w('ANA_MID',(51,50),p('C15',1))
    c(('U4',5),('R16',1),(52,49),(52,45),(34,45),(34,50))
    # Local capacitors on the actual MID input, and the boost inductor input.
    w('MID',p('L2',1),(46,28),(46,23),(16,23),p('C16',1));w('MID',(31,23),p('C17',1));w('MID',(46,28),(46,45),(52,45))
    c(('U4',8),('U4',10),(61,52),(61,54));w('BI_EN',p('U4',8),(57,52),(57,62),(27,62),p('R40',1))
    c(('R38',2),('R40',1),(16,62),(27,62))
    w('INV_SW',p('U4',13),(85,53),p('L3',1));w('INV_SW',(85,63),p('D3',1))
    w('N12',p('D3',2),(146,63));s.label('N12',(146,63));w('N12',p('U4',15),(79,51),(79,58),(142,58),(142,63))
    for ref in ['C9','C11']:w('N12',(parts[ref]['x'],63),p(ref,1))
    w('N12',(114,63),(114,67),(108,67),p('R14',1))
    w('NEG_FB',p('U4',16),(76,49),(76,82),(125,82),p('C11',2));c(('R14',2),('R60',1));c(('R60',2),('R15',1));s.label('NEG_FB',(112,82))
    w('BI_REF',p('U4',17),(75,47),(75,93),(108,93),p('R15',2));w('BI_REF',(90,93),p('C12',1));s.label('BI_REF',(93,93))
    c(('U4',18),('C14',1),(78,54));c(('U4',21),('C13',1),(80,56),(80,74),(90,74))
    s.text('Separate INP/INN local ceramic loops; shielded L2/L3.\nNo arbitrary output LC. Compensation and Cff require loop validation.',8,102,1.0)

    w('MID',p('R38',1),(16,47),(34,47),(34,45))
    s.ground(('C16',2),('C17',2),y=40)
    s.ground(('U4',2),('U4',19),('U4',25),y=61)
    s.ground(('C13',2),('C14',2),y=87)
    port(s,'L2',1,(10,23),via=((46,28),(46,23)))
    port(s,'D2',1,(146,28),'output',0)
    port(s,'D3',2,(146,63),'output',0)
    port(s,'C15',1,(45,58),'output',180,((51,58),))
    port(s,'C16',2,(10,40),'passive',180,((16,40),))

    s=drawings[4]
    # Fan out each side of J8 without using local labels as series-resistor jumpers.
    place(s,('J8',85,50),('R62',50,63,90),('R64',50,75,90),('R66',50,87,90),
          ('R61',130,30,270),('R63',130,63,270),('R65',130,75,270),
          ('R70',38,69),('R71',142,69),('SW1',32,102),('R41',18,96),('C40',49,102),
          ('R32',29,30,90),('D10',49,30,180))
    for pin,ref,y,x in [(11,'R62',63,74),(13,'R64',75,76),(15,'R66',87,78)]:
        p=s.p('J8',pin);join(s,('J8',pin),(ref,2),(x,p[1]),(x,y))
    for pin,ref,y,x in [(2,'R61',30,110),(12,'R63',63,96),(14,'R65',75,94)]:
        p=s.p('J8',pin);join(s,('J8',pin),(ref,2),(x,p[1]),(x,y))
    join(s,('R70',2),('R64',1),(38,75))
    join(s,('R71',2),('R65',1),(142,75))
    port(s,'R62',1,(22,63))
    port(s,'R64',1,(22,75),'bidirectional',180)
    port(s,'R63',1,(153,63),'input',0)
    port(s,'R65',1,(153,75),'bidirectional',0)
    port(s,'R61',1,(153,30),'input',0)
    for pin,x,y in [(3,65,47),(5,55,48),(7,45,49),(9,35,50),(6,120,48),(8,135,49)]:
        port(s,'J8',pin,(x,y),'input',180 if pin%2 else 0)
    port(s,'J8',1,(73,43),'passive',180,((79,46),(79,43)))
    # One locally powered red LED and an independent optional debug button.
    port(s,'R32',1,(16,30))
    join(s,('R32',2),('D10',2));stub(s,'D10',1)
    join(s,('R66',1),('R41',2),(12,87),(12,98),(18,98))
    join(s,('R41',2),('SW1',1),(18,100))
    join(s,('SW1',1),('SW1',3),(23,100),(23,102))
    join(s,('R66',1),('C40',1),(45,87),(45,98),(49,98))
    s.ground(('C40',2),y=112)
    s.wire('GND',s.p('SW1',2),(42,100),(42,112),(49,112))
    s.text('ONE RED D10, HAND SOLDERED / ONE PANEL HOLE\nFinal +5V indication only; no blink or all-rail health claim.',12,23,1.0)
    s.text('J8: OPTIONAL 20-PIN SENSING / DEBUG - NOT POWER\nPin1 = GND / red stripe;17..20 explicitly NC.\nAUX_MON through10k is monitor ONLY, not controller power.',71,23,1.05)
    s.text('Local10k pullups only. External I2C must be OPEN DRAIN.\nNo external supply or pullups; no external enable dependency.\nSW1 is a debug input, NOT a power bypass. JP1 stays OPEN for qualification.',86,94,1.05)

    s=drawings[5]
    # Divider/filter/clamp rows use actual wires, with labels only at rail and debug boundaries.
    for i,(sense,top,bottom,series) in enumerate([('P12','R44','R45','R54'),('P5','R46','R47','R56'),('MID','R48','R49','R57'),('VBUS','R50','R51','R58'),('VPROT','R52','R53','R59')]):
        x=16+(i%3)*49;y=29+(i//3)*35;ci={'P12':0,'P5':2,'MID':3,'VBUS':4,'VPROT':5}[sense]
        place(s,(top,x,y),(bottom,x,y+9),(series,x+12,y+4.5,90),('C'+str(42+ci),x+27,y+10),('D'+str(13+2*ci),x+36,y+10,270),('D'+str(14+2*ci),x+36,y-1,270))
        join(s,(top,2),(bottom,1));join(s,(top,2),(series,1),(x,y+4.5));join(s,(series,2),('C'+str(42+ci),1),(x+27,y+4.5))
        join(s,(series,2),('D'+str(13+2*ci),1),(x+36,y+4.5));join(s,('D'+str(13+2*ci),1),('D'+str(14+2*ci),2))
        port(s,top,1,(x-5,y-6),via=((x,y-6),))
        port(s,series,2,(x+41,y+4.5),'output',0)
        s.ground((bottom,2),('C'+str(42+ci),2),('D'+str(13+2*ci),2),y=y+17)

    place(s,('U11',40,96),('R42',18,94,90),('R43',40,85,90),('R55',71,92,90),('C43',87,99),('D15',99,99,270),('D16',99,87,270),('D25',19,105,270),('D26',28,105,270),('C41',65,103))
    join(s,('R42',2),('U11',2));join(s,('U11',2),('R43',1),(29,94),(29,85))
    join(s,('R43',2),('U11',1),(54,85),(54,92));join(s,('U11',1),('R55',1));join(s,('R55',2),('C43',1),(87,92));join(s,('R55',2),('D15',1),(99,92));join(s,('D15',1),('D16',2))
    join(s,('U11',2),('D25',1),(30,94),(30,101),(19,101));join(s,('D25',1),('D26',2),(19,101),(25,101),(25,109),(28,109))
    join(s,('U11',6),('U11',7),(31,98),(31,112),(56,112),(56,94))
    s.text('U11A: -VNEG x 16.5k/100k = 1.98 V at -12 V.\nU11B unused follower: +input GND; -input tied OUT.',110,75,1.0)

    s.label('NEG_SENSE',(56,92))
    port(s,'R42',1,(10,94))
    port(s,'R55',2,(111,92),'output',0)
    join(s,('U11',8),('C41',1),(65,96))
    port(s,'C41',1,(64,87),'input',0,((65,96),(64,96)))
    s.ground(('C43',2),('D15',2),y=106)
    port(s,'C43',2,(83,106),'passive',180,((87,106),))

    s=drawings[6]
    place(s,('J7',38,45),('J2',121,45,0,'y'),('R25',29,81),('R26',53,81),('R27',77,81))
    s.text('J7: PCB WIRE LANDING',27,25,1.2)
    s.text('J2: OFF-BOARD KEYED ENDPOINT',104,25,1.2)
    x,y1=mm((81,28));_,y2=mm((81,70))
    s.out.append(f'(polyline (pts (xy {x} {y1}) (xy {x} {y2})) (stroke (width 0.254) (type dash)) (fill (type none)) (uuid {q(uid("power-cable-boundary"))}))')
    # Six even contacts go directly across; six odd contacts wrap outside the
    # unchanged two-row bodies. J2 is mirrored graphically, never renumbered.
    for pin in range(2,13,2):join(s,('J7',pin),('J2',pin))
    for pin,xl,xr,y in [(1,18,141,29),(3,21,138,32),(5,24,135,35),
                         (7,24,135,58),(9,21,138,61),(11,18,141,64)]:
        a=s.p('J7',pin);b=s.p('J2',pin)
        join(s,('J7',pin),('J2',pin),(xl,a[1]),(xl,y),(xr,y),(xr,b[1]))
        s.text(f'{pin} -> {pin}',85,y-1,.85)
    for pin in range(2,13,2):s.text(f'{pin} -> {pin}',85,41+(pin//2)-.6,.8)
    # Adjacent same-rail contacts are common at the PCB landing, not extra PSUs.
    for odd,even,x,y in [(1,2,31,38),(3,4,32,39),(5,6,33,40),(7,8,34,52),(9,10,32,54),(11,12,30,56)]:
        a=s.p('J7',odd);b=s.p('J7',even)
        join(s,('J7',odd),('J7',even),(x,a[1]),(x,y),(62-even,y),(62-even,b[1]))
    # Local bleed loads are supplied from the same landing rails.
    for ref,pin,x,y in [('R26',1,12,71),('R25',9,14,73),('R27',11,16,75)]:
        a=s.p('J7',pin);b=s.p(ref,1)
        join(s,('J7',pin),(ref,1),(x,a[1]),(x,y),(b[0],y))
        port(s,ref,1,(x,y),'input',180,((b[0],y),))
    s.ground(('R25',2),('R26',2),('R27',2),y=88)
    port(s,'J7',3,(10,43),'passive',180)
    s.text('TWELVE WIRED CONDUCTORS /13..16 NC AT BOTH ENDS\nJ7 copper landing + one manual flying lead + J2 keyed endpoint.\nMirrored J2 drawing faces the cable; numbers, not appearance, define continuity.',87,77,1.05)
    for i in range(8):s.place(f'#FLG{i+1:02}',15+i*18,102)
    for i in (1,2,3,4):
        ref=f'#FLG{i+1:02}';port(s,ref,1,(15+i*18,107),'passive',0)
    s.text('Independent ERC power declarations only - NOT additional physical supplies.\nPassive flags retain the existing circuit; never parallel another active rack PSU.',10,116,1.0)

    assert assigned==set(parts),('Missing placements',set(parts)-assigned)
    # Every exported net must have an intentional, physically attached port.
    memberships=defaultdict(set)
    for s in drawings:
        for _,_,n in s.pins.values():
            if n is not None:memberships[n].add(s.name)
    exports={n for n,ss in memberships.items() if len(ss)>1}
    for s in drawings:
        assert set(s.ports)=={n for n in exports if s.name in memberships[n]}, (s.name,set(s.ports))
        s.finish()

    root=Drawing('big_modular','Electrical prototype / hierarchy',1)
    root.text('BIG MODULAR / WIRED POWER FLOW',8,7,2.4)
    root.text('REVIEW ONLY - NOT QUALIFIED FOR POWER-UP OR FABRICATION',8,13,1.4)
    # Positions are in page units. Direction is relative to each child sheet.
    # Ground and flag-only declarations are passive, not fake signal outputs.
    layouts=[
      (8,27,25,28,{'VBUS_FUSED':('R',5),'PD_PG_N':('R',11),'AUX3V3':('R',17),
                   'VBUS_RAW':('L',5),'PD_SDA':('L',17),'PD_SCL':('L',22),'GND':('B',12)}),
      (46,27,25,28,{'VBUS_FUSED':('L',5),'PD_PG_N':('L',11),'AUX3V3':('L',17),
                    'VPROT':('R',5),'EF_ENABLE':('R',11),'EF_FLT_N':('R',22),'GND':('B',12)}),
      (84,27,25,28,{'VPROT':('L',5),'EF_ENABLE':('L',11),'MID':('R',5),'P5':('R',17),'GND':('B',12)}),
      (122,27,30,28,{'MID':('L',5),'ANA_MID':('R',10),'P12':('B',8),'N12':('B',20),'GND':('L',23)}),
      (72,78,35,34,{'ADC_P12':('L',4),'ADC_N12':('L',8),'ADC_P5':('L',12),'ADC_MID':('L',16),
                     'ADC_VBUS':('L',20),'ADC_VPROT':('L',24),'AUX3V3':('T',6),'P5':('T',14),
                     'PD_PG_N':('R',4),'EF_FLT_N':('R',10),'PD_SDA':('R',18),'PD_SCL':('R',24),'GND':('B',17)}),
      (19,78,32,34,{'P12':('L',4),'N12':('L',8),'P5':('L',12),'MID':('L',16),
                     'VBUS_FUSED':('L',20),'VPROT':('L',24),'AUX3V3':('T',16),'GND':('B',16),
                     'ADC_P12':('R',4),'ADC_N12':('R',8),'ADC_P5':('R',12),'ADC_MID':('R',16),
                     'ADC_VBUS':('R',20),'ADC_VPROT':('R',24)}),
      (122,68,30,28,{'P12':('T',8),'N12':('T',20),'P5':('L',4),'GND':('R',10),
                     'VBUS_RAW':('B',4),'VBUS_FUSED':('B',11),'MID':('B',19),'ANA_MID':('B',26)})]
    rp={}
    for i,(s,(x,y,width,height,ports)) in enumerate(zip(drawings,layouts)):
        assert set(ports)==set(s.ports)
        xx,yy=mm((x,y));ww,hh=mm((width,height))
        root.out.append(f'(sheet (at {xx} {yy}) (size {ww} {hh}) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid("sheet/"+s.name))})')
        for prop,value,py in [('Sheetname',s.title,y-2),('Sheetfile',s.name+'.kicad_sch',y+height+2)]:
            px,py=mm((x,py))
            if prop=='Sheetname' and i in (4,5):px,py=mm((x,y-7))
            if prop=='Sheetname' and i==6:px,py=mm((133,y-4))
            fx=effects(1.1,'left') if prop=='Sheetname' else '(effects (font (size .85 .85)) hide)'
            root.out.append(f'(property {q(prop)} {q(value)} (at {px} {py} 0) {fx})')
        for n,(side,offset) in ports.items():
            p={'L':(x,y+offset),'R':(x+width,y+offset),'T':(x+offset,y),'B':(x+offset,y+height)}[side]
            angle={'L':180,'R':0,'T':90,'B':270}[side];px,py=mm(p);rp[(i,n)]=p
            root.out.append(f'(pin {q(n)} {s.port_types[n]} (at {px} {py} {angle}) {effects(1.15,'left' if side in ('L','B') else 'right')} (uuid {q(uid(s.name+"/sheetpin/"+n))}))')
        root.out.append(f'(instances (project "big_modular" (path {q("/"+uid("root"))} (page {q(i+2)})))) )')
    for i,caption in enumerate(('USB-C / PD + AUX','U2 / UV-OV + PG','U3 MID / U5 +5V','U4 / +/-12V','J8 DEBUG / D10 LED','6 protected channels','J7 -> cable -> J2')):
        x,y,w,h,_=layouts[i]
        root.text(caption,x+3,y+h-5,1.35)
    wired=set()
    def link(a,b,n,*via):
        root.wire(n,rp[(a,n)],*via,rp[(b,n)]);wired.update([(a,n),(b,n)])
    for n in ('VBUS_FUSED','PD_PG_N','AUX3V3'):link(0,1,n)
    for n in ('VPROT','EF_ENABLE'):link(1,2,n)
    link(2,3,'MID')
    link(2,6,'P5',(116,44),(116,72))
    for n in ('P12','N12'):link(3,6,n)
    for n in ('ADC_P12','ADC_N12','ADC_P5','ADC_MID','ADC_VBUS','ADC_VPROT'):link(5,4,n)
    # Short annotated continuations for shared supplies/returns and long controls.
    for (i,n),p in rp.items():
        if (i,n) in wired:continue
        side=layouts[i][4][n][0]
        dx,dy={'L':(-3,0),'R':(3,0),'T':(0,-5),'B':(0,5)}[side]
        end=(p[0]+dx,p[1]+dy);root.wire(n,p,end)
        root.label(n,end,0)
    # Annotate physical rail trunks for the named sense/flag continuations.
    for i,n in [(0,'VBUS_FUSED'),(0,'PD_PG_N'),(0,'AUX3V3'),(1,'VPROT'),(2,'MID'),(2,'P5'),(3,'P12'),(3,'N12')]:
        p=rp[(i,n)]
        if n in ('P12','N12'):root.label(n,(p[0],62),90)
        else:root.label(n,(p[0]+2,p[1]))
    root.text('SENSE -> DEBUG: six protected analog outputs\nJ8 optional20-pin DEBUG ONLY; NOT POWER.\nNo MCU, blink or external enable dependency.',20,65,1.1)
    root.text('J7 PCB landing -> one flying lead -> J2 keyed POWER OUT\nFlag-only ports at bottom preserve independent ERC declarations.\nRTN stays local to hardware gate; never substitute GND.',116,115,1.0)
    root.finish()
