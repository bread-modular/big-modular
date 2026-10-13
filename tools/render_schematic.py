"""Three functional A3 subsheets and an A4 navigation overview.

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


SHEET_NAMES = ('01_input_protection', '02_power_conversion', '03_output_rails')
SHEET_TITLES = ('Input and protection', 'Power conversion', 'Output rails')


def render(hw, sheets, lib, uid):
    parts = {d['ref']: copy.deepcopy(d) for sh in sheets.values() for d in sh['parts']}
    q = lambda s: json.dumps(str(s))
    def effects(size=1.05, just=''):
        return f'(effects (font (size {size} {size}))' + (f' (justify {just})' if just else '') + ')'
    def mm(p): return tuple(round(float(v)*2.54, 5) for v in p)

    class Drawing:
        def __init__(self, name, title, page, paper='A3'):
            self.name, self.title, self.page = name, title, page
            self.root = name == 'big_modular'
            self.uuid = uid('root' if self.root else 'page/'+name)
            self.path = '/'+uid('root') + ('' if self.root else '/'+uid('sheet/'+name))
            self.out = [f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(self.uuid)}) (paper {q(paper)})',
                        f'(title_block (title {q("Big Modular - "+title)}) (rev "Hierarchy WIP") (company "Big Modular") (comment 1 "INCOMPLETE / NON-OPERATIONAL / DO NOT FABRICATE"))']
            self.parts, self.pins, self.used = {}, {}, set()
            self.segments, self.labels, self.ports = [], {}, {}

        def place(self, ref, x, y, angle=0):
            assert ref not in assigned, ('Duplicate placement', ref)
            assigned.add(ref)
            d=parts[ref];d.update(x=x, y=y, angle=angle)
            self.parts[ref]=d
            a=math.radians(angle);co=round(math.cos(a));si=round(math.sin(a))
            for pin in walk(lib[d['kind']], 'pin'):
                n=str(one(pin,'number')[1]);at=one(pin,'at')
                lx=float(at[1])/2.54;ly=float(at[2])/2.54
                p=(round(x+lx*co-ly*si,5),round(y-lx*si-ly*co,5))
                self.pins[(ref,n)]=(p,(int(at[3])+angle)%360,d['nets'][n])

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
            self.ports[net]=p;x,y=mm(p)
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
                assert net in ('GND','RTN') or key[0].startswith('#'), ('Unwired local branch',self.name,key,net)
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
            ends=defaultdict(set)
            for net,a,b in sorted(emitted):
                x1,y1=mm(a);x2,y2=mm(b)
                self.out.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid {q(uid(self.name+"/wire/"+str((net,a,b))))}))')
                ends[(net,a)].add(b);ends[(net,b)].add(a)
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
                for k,v in [('Footprint',d['fp']),('MPN',d['mpn']),('LCSC',d['lcsc']),('NOTE',d['note'])]:
                    inst.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1 1)) hide))')
                for n in d['nets']:inst.append(f'(pin {q(n)} (uuid {q(uid(ref+"pin"+n))}))')
                inst.append(f'(instances (project "big_modular" (path {q(self.path)} (reference {q(ref)}) (unit 1)))) )')
                self.out.append(''.join(inst))
            if self.root:self.out.append('(sheet_instances (path "/" (page "1")))')
            self.out.append('(embedded_fonts no))')
            (hw/(self.name+'.kicad_sch')).write_text('\n'.join(self.out)+'\n')

    assigned=set()
    drawings=[Drawing(n,t,i+2) for i,(n,t) in enumerate(zip(SHEET_NAMES,SHEET_TITLES))]
    for i,s in enumerate(drawings,1):
        s.text(f'0{i} / {s.title.upper()}',8,8,2.4)
        s.text('WIP - DO NOT FABRICATE | Read docs/schematic-guide.md | Return to overview using the sheet navigator',8,13,1.05)

    s=drawings[0];p=s.p;w=s.wire;c=s.connect
    for args in [('J1',16,34),('F1',34,28,90),('U1',46,49),('R1',47,34),('C1',57,43),('R2',58,54),('R3',65,43),
                 ('U2',109,33),('C2',68,29),('R4',88,26.5),('R5',88,43),('R6',77,26.5),('R7',77,43),
                 ('R8',121,43),('C3',134,43),('C4',141,33),('R31',153,33),
                 ('Q1',82,73),('R28',72,73,90),('R29',76,81,270),('JP1',96,71),('R30',108,78)]:s.place(*args)
    c(('J1','A4'),('F1','1'));s.label('VBUS_RAW',(25,28))
    c(('F1','2'),('U2','1'),(40,28),(40,22),(99,22),(99,28));s.label('VBUS_FUSED',(51,22))
    for ref in ['R1','C2','R4','R6']:w('VBUS_FUSED',(parts[ref]['x'],22),p(ref,1))
    c(('R1','2'),('U1','1'));w('PD_VDD',(47,39),(65,39),p('R3',1));w('PD_VDD',(57,39),p('C1',1));s.label('PD_VDD',(49,39))
    c(('J1','A5'),('U1','7'),(29,30),(29,47));c(('J1','B5'),('U1','6'),(31,31),(31,48))
    s.label('CC1',(32,47));s.label('CC2',(32,48))
    c(('U1','4'),('U1','5'),(39,51),(39,50));s.label('PD_D_SHORT',(39,51))
    c(('U1','9'),('R2','1'),(58,49));s.label('PD_CFG',(58,49))
    s.ground(('U1','11'),('R2','2'),y=59)
    s.ground(('J1','A1'),('J1','SH'),y=45)
    c(('U1','10'),('R3','2'),(65,47));s.label('PD_PG_N',(58,47))
    c(('U1','10'),('R28','1'),(65,47),(65,73))
    c(('R28','2'),('Q1','1'));s.label('PG_BASE',(77,73))
    w('PG_BASE',(78,73),(78,77),(73,77),(73,81),p('R29','2'))
    c(('R29','1'),('Q1','2'),(88,81),(88,75));s.label('PD_VDD',(88,81))
    c(('Q1','3'),('JP1','1'));s.label('PG_PERMIT',(86,71))
    c(('JP1','2'),('U2','7'),(102,71),(102,38));s.label('EF_ENABLE',(102,66))
    w('EF_ENABLE',(102,71),(108,71),p('R30',1))
    c(('R4','2'),('R5','1'));w('UV_EN',(88,31),p('U2','3'));s.label('UV_EN',(91,31))
    c(('R6','2'),('R7','1'));w('OV_SET',(77,34),p('U2','5'));s.label('OV_SET',(92,34))
    w('RTN',p('R7',2),(77,50),(134,50));w('RTN',p('R5',2),(88,50))
    w('RTN',p('U2',8),(108,50));w('RTN',p('U2',6),(100,37),(100,50));s.label('RTN',(117,50))
    c(('U2',11),('R8',1),(121,37));s.label('ILIM',(121,37))
    c(('U2',12),('C3',1),(128,38),(128,40),(134,40));s.label('SLEW',(134,40))
    w('RTN',p('R8',2),(121,50));w('RTN',p('C3',2),(134,50))
    w('VPROT',p('U2',15),(158,28));s.port('VPROT',(158,28),'output',180)
    for ref in ['C4','R31']:w('VPROT',(parts[ref]['x'],28),p(ref,1))
    s.ground(('C4',2),('R31',2),y=38)
    s.port('GND',(12,79),'passive');w('GND',(12,79),(19,79));s.label('GND',(19,79))
    s.text('USB data / SBU intentionally unused.\nDP and DM short only at U1 (PD-only).\nR2 requests 9 V; 5 V is housekeeping only.',9,57)
    s.text('UV / OV dividers return to RTN, NOT GND.\nNominal rising window: 7.878 .. 10.781 V.\nR8: 0.2985 A nominal limit, not a guaranteed rating.\nPG + window does NOT prove a 9 V PDO/current contract.',111,57,1.05)
    s.text('PG low -> Q1 on -> series RUN -> SHDN high.\nDefault RUN OPEN; R30 defaults SHDN low.\nR31 bleeds VPROT; zero residual voltage is NOT guaranteed.',67,88,1.05)
    s.text('No qualified VBUS / CC ESD or surge protection. D1 is absent.\nAll converter bulk is downstream of U2. See design-review.md.',9,87,1.1)
    for ref,x in [('#FLG01',17),('#FLG02',33),('#FLG03',49),('#FLG04',65)]:s.place(ref,x,101)
    s.text('ERC source declarations (not physical parts)',9,96,1.05)

    s=drawings[1];p=s.p;w=s.wire;c=s.connect
    for args in [('U3',35,33),('L1',48,30,90),('C5',17,39),('C7',26,39),('C6',62,39),('R9',52,38),('R10',52,44),('R11',43,50),
                 ('U4',99,47),('L2',90,25,90),('D2',110,25,180),('L3',112,65),('D3',123,59),
                 ('C8',144,34),('C9',147,68),('R12',122,34),('R13',122,45),('C10',134,34),
                 ('R14',124,70),('R15',124,84),('C11',136,70),('C12',112,92),('C13',116,75),('C14',108,75),
                 ('R16',82,46,90),('C15',87,57),('C16',70,38),('C17',78,38),
                 ('U5',35,83),('L4',49,81,90),('C18',17,88),('C20',25,88),('C19',68,89),('R17',55,87),('R18',55,96)]:s.place(*args)
    s.port('VPROT',(10,30));w('VPROT',(10,30),p('U3',2));c(('U3',2),('U3',3),(30,30),(30,31))
    for ref in ['C5','C7']:w('VPROT',(parts[ref]['x'],30),p(ref,1))
    c(('U3',7),('L1',1));s.label('MID_SW',(41,30))
    w('V4',p('L1',2),(86,30),(86,45),p('U4',5));s.label('V4',(57,30))
    w('V4',(62,30),p('C6',1));w('V4',p('U3',6),(40,31),(40,34),(62,34))
    w('V4',(52,34),p('R9',1));c(('R9',2),('R10',1))
    c(('U3',5),('R9',2),(42,32),(42,41),(52,41));s.label('MID_FB',(44,41))
    w('V4',(67,30),(67,47),(43,47),p('R11',1))
    w('MID_GOOD',p('U3',8),(29,34),(29,55),(72,55),(72,48),p('U4',8))
    w('MID_GOOD',p('R11',2),(43,55));w('MID_GOOD',(92,48),(92,50),p('U4',10));s.label('MID_GOOD',(51,55))
    s.ground(('C5',2),('C7',2),('U3',1),('U3',4),('U3',9),('R10',2),('C6',2),y=46)
    w('V4',(86,30),(86,25),p('L2',1))
    c(('L2',2),('D2',2));w('BOOST_SW',(94,25),(94,41),p('U4',1));s.label('BOOST_SW',(96,25))
    w('PRE_P',p('D2',1),(158,25));s.port('PRE_P',(158,25),'output',180)
    w('PRE_P',(118,25),(118,39),(107,39),(107,41),p('U4',23))
    for ref in ['C8','R12','C10']:w('PRE_P',(parts[ref]['x'],25),p(ref,1))
    c(('R12',2),('R13',1));w('POS_FB',p('U4',22),(134,42),p('C10',2));s.label('POS_FB',(114,42))
    for ref in ['C16','C17']:w('V4',(parts[ref]['x'],30),p(ref,1))
    s.ground(('C16',2),('C17',2),y=42)
    w('V4',(86,45),(80,45),(80,46),p('R16',1))
    c(('R16',2),('U4',4));w('ANA_V4',(87,46),p('C15',1));s.label('ANA_V4',(88,46))
    w('GND',p('U4',9),(91,49),(91,63));w('GND',p('U4',11),(91,51))
    s.ground(('C15',2),('U4',19),('U4',25),('U4',2),y=63)
    w('INV_SW',p('U4',13),(112,49),p('L3',1));w('INV_SW',(112,59),p('D3',1));s.label('INV_SW',(113,59))
    w('PRE_N',p('D3',2),(158,59));s.port('PRE_N',(158,59),'output',180)
    w('PRE_N',p('U4',15),(109,47),(109,54),(149,54),(149,59))
    w('PRE_N',(147,59),p('C9',1));w('PRE_N',(130,59),(130,63),(124,63),p('R14',1))
    w('PRE_N',(136,59),p('C11',1))
    w('NEG_FB',p('U4',16),(106,45),(106,78),(136,78),p('C11',2))
    c(('R14',2),('R15',1));s.label('NEG_FB',(126,78))
    w('BI_REF',p('U4',17),(105,43),(105,89),(124,89),p('R15',2));w('BI_REF',(112,89),p('C12',1));s.label('BI_REF',(115,89))
    c(('U4',18),('C14',1),(108,50))
    c(('U4',21),('C13',1),(110,52),(110,70),(116,70))
    s.label('COMP_N',(108,71));s.label('COMP_P',(116,71))
    s.ground(('C13',2),('C14',2),y=80)
    s.text('4.016 V intermediate',9,20,1.4)
    s.text('Bipolar preregulator: about +/-13.95 V',83,18,1.4)
    s.text('U3 PG sequences U4 in normal startup, not a fault latch.\nU3 PG is high-impedance in shutdown / UVLO.\nU4 negative divider returns to BI_REF, NOT ground.\nPRE_P also supplies the +5 V branch below.',9,64,1.05)
    s.text('About 6.5 V preregulator (from PRE_P above)',9,74,1.4)
    w('PRE_P',(10,81),p('U5',2));s.label('PRE_P',(10,81));c(('U5',2),('U5',3),(27,81),(27,82))
    for ref in ['C18','C20']:w('PRE_P',(parts[ref]['x'],81),p(ref,1))
    c(('U5',7),('L4',1));s.label('FIVE_SW',(42,81))
    w('PRE_5',p('L4',2),(78,81));s.port('PRE_5',(78,81),'output',180)
    w('PRE_5',(68,81),p('C19',1));w('PRE_5',p('U5',6),(44,82),(44,84),(68,84));w('PRE_5',(55,84),p('R17',1))
    c(('R17',2),('R18',1));w('FIVE_PRE_FB',p('U5',5),(43,83),(43,92),(55,92));s.label('FIVE_PRE_FB',(44,92))
    w('GND',p('U5',1),(28,84),(28,101));w('GND',p('U5',9),(28,85))
    s.ground(('C18',2),('C20',2),('R18',2),('C19',2),y=101)
    s.port('GND',(10,106),'passive');w('GND',(10,106),(17,106),(17,101))
    for ref,x,y in [('#FLG05',24,60),('#FLG06',87,69),('#FLG07',150,45),('#FLG08',150,84),('#FLG09',86,97)]:s.place(ref,x,y)

    s=drawings[2];p=s.p;w=s.wire;c=s.connect
    for u,cy,cin,cout,nr,ff,rt,rb,rev,clamp,bleed,inp,out in [
        ('U6',29,'C21','C22','C23','C24','R19','R20','D4','D5','R25','PRE_P','P12'),
        ('U7',55,'C25','C26','C27','C28','R21','R22','D6','D7','R26','PRE_N','N12'),
        ('U8',82,'C29','C30','C31','C32','R23','R24','D8','D9','R27','PRE_5','P5')]:
        negative=u=='U7'
        for args in [(u,40,cy),(cin,20,cy+8),(cout,98,cy+8),(nr,30,cy+8),(ff,85,cy+4),
                     (rt,69,cy+4),(rb,69,cy+12),(rev,40,cy-7,180 if negative else 0),
                     (clamp,110,cy+8,90 if negative else 270),(bleed,122,cy+8)]:s.place(*args)
        s.port(inp,(10,cy-2));w(inp,(10,cy-2),p(u,8));c((u,8),(u,5),(33,cy-2),(33,cy-1))
        w(inp,(20,cy-2),p(cin,1))
        w(inp,(25,cy-2),(25,cy-7),p(rev,2 if negative else 1))
        w(out,p(rev,1 if negative else 2),(96,cy-7),(96,cy-2))
        w(out,p(u,1),(128 if out=='P12' else 133 if out=='N12' else 138,cy-2));s.label(out,(118,cy-2))
        for ref in [rt,ff,cout,bleed]:w(out,(parts[ref]['x'],cy-2),p(ref,1))
        w(out,(110,cy-2),p(clamp,2 if negative else 1))
        fb=parts[u]['nets']['2'];w(fb,p(u,2),(50,cy-1),(50,cy+8),(85,cy+8),p(ff,2));c((rt,2),(rb,1));s.label(fb,(54,cy+8))
        c((u,6),(nr,1),(30,cy))
        s.label(parts[u]['nets']['6'],(30,cy+3))
        w('GND',p(u,4),(48,cy),(48,cy+16));w('GND',p(u,9),(48,cy+1))
        s.ground((cin,2),(nr,2),(rb,2),(cout,2),(clamp,1 if negative else 2),(bleed,2),y=cy+16)
        s.text({'U6':'+12 V / low-noise LDO','U7':'-12 V / negative LDO','U8':'+5 V / low-noise LDO'}[u],8,cy-12,1.25)
    s.place('J2',148,57)
    w('P12',(128,27),(128,58),p('J2',9))
    w('N12',(133,53),(133,54),p('J2',1))
    w('P5',(138,80),(138,59),p('J2',11))
    for pin,net in [(2,'N12'),(10,'P12'),(12,'P5')]:
        pt=p('J2',pin);end=(157,pt[1]);w(net,pt,end);s.label(net,end)
    for pins,x,y in [([3,5,7],143,64),([4,6,8],152,66)]:
        for pin in pins:pt=p('J2',pin);w('GND',pt,(x,pt[1]),(x,y))
        s.label('GND',(x,y))
    s.port('GND',(10,106),'passive');w('GND',(10,106),(20,106),(20,98))
    s.text('J2 OFF-BOARD\n16-pin POWER OUT\n1/2: -12 V / red stripe\n3..8: ground\n9/10: +12 V\n11/12: +5 V\n13..16: NC',137,33,1.05)
    s.text('Negative LDO: IN / EN use PRE_N.\nGND and EP remain at 0 V.\nDiodes address reverse differential / polarity,\nNOT precision overvoltage protection.',8,109,1.0)
    s.text('10uF MLCCs: verify capacitance under bias.\nNo rail-current rating, tracking or rapid-discharge guarantee.',55,108,1.0)
    assert assigned==set(parts), ('Missing placements',set(parts)-assigned)
    for s in drawings:s.finish()

    root=Drawing('big_modular','Overview and sheet navigation',1,'A4')
    root.text('BIG MODULAR / SCHEMATIC MAP',8,8,2.5)
    root.text('Three functional subsheets | 88 real components | Circuit connectivity retained',8,13,1.2)
    root.text('INCOMPLETE / NON-OPERATIONAL / DO NOT FABRICATE',8,19,1.5)
    boxes=[(SHEET_NAMES[0],SHEET_TITLES[0],8,27,27,25,[('VPROT','output',35,34,180),('GND','passive',22,52,90)]),
           (SHEET_NAMES[1],SHEET_TITLES[1],45,27,28,25,[('VPROT','input',45,34,0),('PRE_P','output',73,33,180),('PRE_N','output',73,39,180),('PRE_5','output',73,45,180),('GND','passive',59,52,90)]),
           (SHEET_NAMES[2],SHEET_TITLES[2],84,27,26,25,[('PRE_P','input',84,33,0),('PRE_N','input',84,39,0),('PRE_5','input',84,45,0),('GND','passive',97,52,90)])]
    for i,(name,title,x,y,width,height,ports) in enumerate(boxes,2):
        xx,yy=mm((x,y));ww,hh=mm((width,height))
        root.out.append(f'(sheet (at {xx} {yy}) (size {ww} {hh}) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid("sheet/"+name))})')
        for prop,value,py in [('Sheetname',title,y-1.5),('Sheetfile',name+'.kicad_sch',y+height+2)]:
            px,py=mm((x,py));root.out.append(f'(property {q(prop)} {q(value)} (at {px} {py} 0) {effects(.95,"left")} )')
        for net,direction,px,py,a in ports:
            px,py=mm((px,py))
            root.out.append(f'(pin {q(net)} {direction} (at {px} {py} {(a+180)%360}) {effects(1.1,"right" if a==180 else "left")} (uuid {q(uid(name+"/sheetpin/"+net))}))')
        root.out.append(f'(instances (project "big_modular" (path {q("/"+uid("root"))} (page {q(i)})))) )')
    root.wire('VPROT',(35,34),(45,34));root.label('VPROT',(39,34))
    for net,y in [('PRE_P',33),('PRE_N',39),('PRE_5',45)]:root.wire(net,(73,y),(84,y));root.label(net,(77,y))
    root.wire('GND',(22,52),(22,60),(97,60),(97,52));root.wire('GND',(59,52),(59,60));root.label('GND',(40,60))
    root.text('USB-C / CH224K\nFuse + eFuse\nPG / RUN / voltage gate\nSee page 2',10,42,1.45)
    root.text('V4 intermediate\nBipolar boost / inverter\n+5 V preregulation\nSee page 3',47,42,1.45)
    root.text('Three LDOs / J2\nSee page 4',86,48,1.45)
    root.text('HOW TO READ\nOpen each sheet in KiCad or click its box in the PDF.\nLocal feedback, filtering and protection networks use real wires.\nNamed ports carry power between sheets; GND is shared, RTN is not.',8,68,1.3)
    root.text('LIMITS: No PDO/current proof, qualified input surge protection or completed PCB layout.\nRead docs/schematic-guide.md and docs/component-guide.md.',8,23,1.05)
    root.finish()
