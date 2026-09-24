"""Single-sheet A1 layout. Coordinates below are in 2.54 mm drawing units.
Real wires form the power backbone; small local labels serve feedback/decoupling.
No hierarchy, no imported schematic images. Does not change the circuit inventory.
"""
import copy, json, math
from collections import defaultdict
from sexp import dump, nodes, one, walk


def render(hw, sheets, lib, uid):
    parts = {d['ref']: d for sh in sheets.values() for d in sh['parts']}
    q = lambda s: json.dumps(str(s))
    effects = lambda size=1.05, just='': f'(effects (font (size {size} {size}))' + (f' (justify {just})' if just else '') + ')'
    def mm(p): return tuple(round(float(v)*2.54, 5) for v in p)
    def place(ref, x, y, angle=0):
        parts[ref].update(x=x, y=y, angle=angle)
    # Common horizontal signal/power flow; returns and branch labels stay local.
    for ref, x, y, angle in [
        ('J1',15,66,0),('F1',35,60,90),('U1',45,105,0),
        ('R1',46,88,0),('C1',56,94,0),('R2',57,112,0),('R3',64,98,0),
        ('C2',67,64,0),('U2',83,65,0),('R4',62,73,0),('R5',62,82,0),
        ('R6',72,82,0),('R7',70,87,0),('R8',95,88,0),('C3',105,88,0),
        ('C4',95,66,0),('Q1',76,105,0),('R28',64,103,90),('R29',74,95,90),
        ('JP1',87,112,0),('R30',96,116,0),('R31',105,68,0),
        ('U3',116,63,0),('L1',132,60,90),('C5',111,80,0),('C7',123,80,0),
        ('C6',142,67,0),('R9',133,70,0),('R10',133,80,0),('R11',145,84,0),
        ('U4',173,78,0),('L2',153,56,90),('D2',173,56,180),
        ('L3',183,101,0),('D3',190,87,0),('C8',195,63,0),('C9',210,95,0),
        ('R12',191,72,0),('R13',191,81,0),('R14',219,108,0),('R15',231,108,0),
        ('C10',204,72,0),('C11',219,119,0),('C12',177,116,0),
        ('C13',191,116,0),('C14',203,116,0),('R16',153,96,0),
        ('C15',153,106,0),('C16',153,119,0),('C17',165,119,0),
        ('U5',217,150,0),('L4',236,148,90),('C18',206,170,0),
        ('C20',218,170,0),('C19',247,159,0),('R17',233,161,0),('R18',233,171,0),
        ('U6',245,58,0),('U7',245,103,0),('U8',271,150,0),
        ('J2',306,98,0),('R25',305,121,0),('R26',305,132,0),('R27',305,143,0),
    ]: place(ref,x,y,angle)
    for u, cx, cy, caps, resistors, diodes in [
        ('U6',245,58,[21,22,23,24],[19,20],[4,5]),
        ('U7',245,103,[25,26,27,28],[21,22],[6,7]),
        ('U8',271,150,[29,30,31,32],[23,24],[8,9]),
    ]:
        for ref,x,y,a in [
            (f'C{caps[0]}',cx-13,cy+9,0),(f'C{caps[1]}',cx+13,cy+9,0),
            (f'C{caps[2]}',cx-13,cy+20,0),(f'C{caps[3]}',cx+13,cy+20,0),
            (f'R{resistors[0]}',cx+24,cy+9,0),(f'R{resistors[1]}',cx+24,cy+20,0),
            (f'D{diodes[0]}',cx,cy-11,0),(f'D{diodes[1]}',cx+24,cy+31,0),
        ]: place(ref,x,y,a)
    for i,ref in enumerate(r for r in parts if r.startswith('#')):
        place(ref,18+i*20,191)

    out = [f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(uid("root"))}) (paper "A1")',
           '(title_block (title "Big Modular - PD ONLY / one-sheet circuit proposal") (date "2026-09-24") (rev "A1 WIP") (company "Big Modular") (comment 1 "INCOMPLETE / NON-OPERATIONAL / DO NOT FABRICATE"))']
    caches=[]
    for kind in sorted({d['kind'] for d in parts.values()}):
        s=copy.deepcopy(lib[kind]);s[1]='BigModular:'+kind;caches.append(dump(s))
    out.append('(lib_symbols '+''.join(caches)+')')
    def text(s,x,y,size=1.3):
        x,y=mm((x,y));out.append(f'(text {q(s)} (at {x} {y} 0) {effects(size,"left")} (uuid {q(uid("text"+str((s,x,y))))}))')
    text('BIG MODULAR | PD-ONLY 9 V | ONE CONNECTED CIRCUIT | A1 WIP',8,10,3)
    text('STOP: PCB has only J1 and mechanical holes. No tracks / vias / zones. Neither board is operational.',8,17,1.8)
    text('5 V VBUS powers negotiation only. Gate = PG active LOW AND 7.88..10.78 V nominal window AND RUN. NO 5 V OUTPUT MODE.',8,22,1.6)
    text('BLOCKERS: PG does NOT prove PDO/current. No qualified input ESD/surge protection. J1 has four physical DRC violations.',8,27,1.6)
    text('9 V must be independently verified by PD analyzer at >=0.5 A contract before any test. About 40 mA/rail simultaneous TEST LOADS ONLY; no rating.',8,32,1.4)
    for s,x,y in [('USB-C / FUSE',9,47),('eFUSE / UV + OV',74,47),('4.016 V BUCK',113,47),
                  ('BIPOLAR +/-13.95 V',162,47),('+12 V POSTREG',239,39),('-12 V POSTREG',239,84),
                  ('6.52 V BUCK',209,139),('+5 V POSTREG',264,132),('OFF-BOARD J2',299,87),
                  ('9 V REQUEST / PG INTERLOCK',36,130)]: text(s,x,y,1.6)
    text('R4/R5: 562k/100k UV; R6/R7: 806k/100k OV.\nSHDN LOW = OFF. JP1 cannot override either window limit.\nPG generic active-low OD, not authenticated contract/current.\nDefault RUN OPEN. RTN is NOT externally shorted to GND.',36,140,1.2)
    text('U4 PSP/PSN grounded; BSW intentionally unused.\nPositive boost can prebias only AFTER the gated V4 supply exists.\nNegative feedback lower resistor returns to BI_REF, not GND.\nPG of U3 holds both U4 enables low during intermediate startup.',133,136,1.15)
    text('POWER/RETURN DECLARATIONS (not PCB pads)',9,181,1.2)
    text('No TVS fitted: D1 reference reserved. Do not substitute a 12 V-standoff clamp on upstream USB VBUS.\nLDOs are not precision output-OVP devices. No all-rail shutdown/tracking or rapid discharge guarantee.\nRead docs/design-review.md, mechanics.md and reports/validation-summary.md. Converter stability, thermals, surge and physical fit remain untested.',8,203,1.35)

    pins={}; used=set(); segments=[]; label_at={}; junctions=set()
    for ref,d in parts.items():
        a=math.radians(d['angle']);co=round(math.cos(a));si=round(math.sin(a))
        for p in walk(lib[d['kind']],'pin'):
            n=str(one(p,'number')[1]);at=one(p,'at');lx=float(at[1])/2.54;ly=float(at[2])/2.54
            pos=(round(d['x']+lx*co-ly*si,5),round(d['y']-lx*si-ly*co,5))
            direction=(int(at[3])+d['angle'])%360
            pins[(ref,n)]=(pos,direction,d['nets'][n])
    def point(ref,pin): return pins[(ref,str(pin))][0]
    def wire(net,*pts):
        for a,b in zip(pts,pts[1:]):
            a=tuple(a);b=tuple(b)
            if a==b:continue
            assert a[0]==b[0] or a[1]==b[1],(net,a,b)
            segments.append((net,a,b))
    def mark(ref,pin):
        pos,_,net=pins[(ref,str(pin))]
        for key,(p,_,n) in pins.items():
            if p==pos and n==net:used.add(key)
        return pos
    def connect(net,a,b,*via):
        assert pins[(a[0],str(a[1]))][2]==net,(a,net)
        assert pins[(b[0],str(b[1]))][2]==net,(b,net)
        wire(net,mark(*a),*via,mark(*b))
    def label(net,p,angle=0):
        p=tuple(p)
        if p in label_at: assert label_at[p]==net
        else:
            label_at[p]=net;x,y=mm(p)
            out.append(f'(label {q(net)} (at {x} {y} {angle}) {effects(.95,"left bottom")} (uuid {q(uid("label"+str((net,p))))}))')
    # Visible interstage backbone; these are electrical KiCad wires, not graphics.
    connect('VBUS_RAW',('J1','A4'),('F1','1'));label('VBUS_RAW',(25,60))
    connect('VBUS_FUSED',('F1','2'),('U2','1'));label('VBUS_FUSED',(50,60))
    wire('VBUS_FUSED',(46,60),mark('R1','1'))
    wire('VBUS_FUSED',(67,60),mark('C2','1'))
    connect('PD_VDD',('R1','2'),('U1','1'));label('PD_VDD',(46,97))
    wire('PD_VDD',(46,92.5),(56,92.5),mark('C1','1'))
    connect('CC1',('J1','A5'),('U1','7'),(28,62),(28,103));label('CC1',(28,96))
    connect('CC2',('J1','B5'),('U1','6'),(30,63),(30,104));label('CC2',(30,99))
    connect('PD_D_SHORT',('U1','4'),('U1','5'),(38,107),(38,106));label('PD_D_SHORT',(38,107))
    connect('VPROT',('U2','15'),('U3','2'));label('VPROT',(100,60))
    for ref in ['C4','R31']:wire('VPROT',(parts[ref]['x'],60),mark(ref,'1'))
    connect('VPROT',('U3','2'),('U3','3'),(109,60),(109,61))
    connect('MID_SW',('U3','7'),('L1','1'));label('MID_SW',(124,60))
    connect('V4',('L1','2'),('U4','5'),(147,60),(147,76));label('V4',(147,60))
    wire('V4',(142,60),mark('C6','1'))
    wire('V4',(147,60),(147,56),mark('L2','1'))
    connect('BOOST_SW',('L2','2'),('D2','2'));label('BOOST_SW',(160,56))
    wire('BOOST_SW',(159,56),(159,72),mark('U4','1'))
    connect('PRE_P',('D2','1'),('U6','8'));label('PRE_P',(220,56))
    wire('PRE_P',(195,56),mark('C8','1'))
    wire('PRE_P',(198,56),(198,72),mark('U4','23'))
    wire('PRE_P',(207,56),(207,148),mark('U5','2'))
    connect('PRE_P',('U5','2'),('U5','3'),(210,148),(210,149))
    connect('INV_SW',('U4','13'),('D3','1'),(183,80),(183,87));label('INV_SW',(183,87))
    wire('INV_SW',(183,87),mark('L3','1'))
    connect('PRE_N',('D3','2'),('U7','8'),(214,87),(214,101));label('PRE_N',(225,101))
    wire('PRE_N',(210,87),mark('C9','1'))
    wire('PRE_N',mark('U4','15'),(201,78),(201,87))
    connect('FIVE_SW',('U5','7'),('L4','1'));label('FIVE_SW',(227,148))
    connect('PRE_5',('L4','2'),('U8','8'));label('PRE_5',(254,148))
    wire('PRE_5',(247,148),mark('C19','1'))
    for ref,net in [('U6','PRE_P'),('U7','PRE_N'),('U8','PRE_5')]:
        x,y=point(ref,'8');connect(net,(ref,'8'),(ref,'5'),(x-1,y),(x-1,y+1))
    connect('P12',('U6','1'),('J2','9'),(283,56),(283,99));label('P12',(278,56))
    connect('N12',('U7','1'),('J2','1'),(288,101),(288,95));label('N12',(278,101))
    connect('P5',('U8','1'),('J2','11'),(294,148),(294,100));label('P5',(286,148))
    # Feedback/VOS and enable continuity is explicit where it clarifies each stage.
    connect('MID_FB',('U3','5'),('R9','2'),(127,62),(127,71.5));label('MID_FB',(127,71.5))
    connect('MID_FB',('R9','2'),('R10','1'));wire('V4',(142,64),(133,64),mark('R9','1'))
    wire('V4',mark('U3','6'),(124,61),(124,64),(142,64))
    wire('MID_GOOD',mark('U3','8'),(108,64),(108,92),(162,92),(162,79),mark('U4','8'));label('MID_GOOD',(140,92))
    wire('MID_GOOD',(162,81),mark('U4','10'))
    # Active-low PG is inverted by a powered PNP; RUN is in SERIES, not a bypass.
    connect('PD_PG_N',('U1','10'),('R28','1'),(60,103));label('PD_PG_N',(55,103))
    connect('PG_BASE',('R28','2'),('Q1','1'),(70,103),(70,105));label('PG_BASE',(70,105))
    wire('PD_VDD',(56,92.5),(81,92.5),(81,107),mark('Q1','2'))
    wire('PD_VDD',(71,92.5),(71,95),mark('R29','1'))
    wire('PG_BASE',mark('R29','2'),(75.5,100),(71,100),(71,105))
    connect('PG_PERMIT',('Q1','3'),('JP1','1'),(79,103),(79,112));label('PG_PERMIT',(79,112))
    connect('EF_ENABLE',('JP1','2'),('U2','7'),(100,112),(100,97),(80,97),(80,75),(78,75));label('EF_ENABLE',(100,107))
    wire('EF_ENABLE',(96,112),mark('R30','1'))
    for ref,net,cx,cy,cap,rt,rb in [('U6','P12',245,58,'C22','R19','R20'),('U7','N12',245,103,'C26','R21','R22'),('U8','P5',271,150,'C30','R23','R24')]:
        wire(net,mark(ref,'1'),(cx+24,cy-2),mark(rt,'1'))
        wire(net,(cx+13,cy-2),mark(cap,'1'))
        fb=parts[ref]['nets']['2']
        connect(fb,(ref,'2'),(rt,'2'),(cx+10,cy-1),(cx+10,cy+15),(cx+24,cy+15))
        connect(fb,(rt,'2'),(rb,'1'));label(fb,(cx+24,cy+15))
    # Remaining local branches receive short wires and local (NOT global) labels.
    for key,(pos,a,net) in pins.items():
        if key in used:continue
        ref,num=key;mark(ref,num)
        x,y=mm(pos)
        if net is None:
            out.append(f'(no_connect (at {x} {y}) (uuid {q(uid(ref+"nc"+num))}))');continue
        dx,dy={0:(-2,0),90:(0,2),180:(2,0),270:(0,-2)}[a]
        end=(pos[0]+dx,pos[1]+dy);wire(net,pos,end)
        label(net,end,90 if dy else 0)
    # Every named backbone segment must actually touch a same-net pin, wire or label.
    # Split at same-net tees so KiCad's junction semantics are explicit.
    bynet=defaultdict(set)
    for net,a,b in segments:bynet[net].update([a,b])
    for p,net in label_at.items():bynet[net].add(p)
    emitted=set()
    for net,a,b in segments:
        axis=0 if a[1]==b[1] else 1
        ps=[p for p in bynet[net] if p[1-axis]==a[1-axis] and min(a[axis],b[axis])<=p[axis]<=max(a[axis],b[axis])]
        ps.sort(key=lambda p:p[axis])
        for p1,p2 in zip(ps,ps[1:]):
            edge=(net,p1,p2)
            if edge in emitted:continue
            emitted.add(edge);x1,y1=mm(p1);x2,y2=mm(p2)
            out.append(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid {q(uid("wire"+str(edge)))}))')
    ends=defaultdict(list)
    for net,a,b in emitted:ends[(net,a)].append(b);ends[(net,b)].append(a)
    for (net,p),e in ends.items():
        if len(e)>2:
            x,y=mm(p);out.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(uid("junc"+str((net,p))))}))')
    for ref,d in parts.items():
        x,y=mm((d['x'],d['y']));a=d['angle'];s=lib[d['kind']]
        # IC/reference text is above the symbol; passive text to the right when vertical.
        ispassive=ref[0] in 'RCLFD' and not ref.startswith('#')
        if ispassive and a in (0,180):tx,ty=x+4,y-1.2;just='left'
        else:
            top=min(p[0][1] for key,p in pins.items() if key[0]==ref)*2.54
            tx,ty=x,top-6.0;just=''
        inst=[f'(symbol (lib_id {q("BigModular:"+d["kind"])}) (at {x} {y} {a}) (unit 1) (in_bom {"no" if ref.startswith("#") else "yes"}) (on_board {"yes" if d["onboard"] else "no"}) (dnp no) (uuid {q(uid(ref))})',
              f'(property "Reference" {q(ref)} (at {tx} {ty} 0) {effects(1.15,just)})',
              f'(property "Value" {q(d["value"])} (at {tx} {ty+2.54} 0) {effects(.95,just)})']
        for k,v in [('Footprint',d['fp']),('MPN',d['mpn']),('LCSC',d['lcsc']),('NOTE',d['note'])]:
            inst.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1 1)) hide))')
        for num in d['nets']:inst.append(f'(pin {q(num)} (uuid {q(uid(ref+"pin"+num))}))')
        inst.append(f'(instances (project "big_modular" (path {q("/"+uid("root"))} (reference {q(ref)}) (unit 1)))) )')
        out.append(''.join(inst))
    out.append('(embedded_fonts no))')
    (hw/'big_modular.kicad_sch').write_text('\n'.join(out)+'\n')
    # Obsolete hierarchy is removed on every regeneration, never left as stale alternatives.
    for name in sheets:
        (hw/(name+'.kicad_sch')).unlink(missing_ok=True)
