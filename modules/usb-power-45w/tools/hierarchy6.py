"""Readable S6 hierarchy, following usb-power's wired power-flow overview.

Consumes the exact, native-verified flat candidate in memory. It does not change
component fields or circuit connectivity. Explicit functional groups and wire
waypoints below own presentation; native XML parity is checked after splitting.
Uses the module's existing sexp and drawing primitives, not an assembly exporter.
"""
import copy
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from sexp import parse, dump, nodes, one, walk, atom

PAGES = {
 1: ('01_usb_input', 'USB PD and main eFuse', (420,297)),
 2: ('02_positive_12v', '+12 V converter and output eFuse', (420,297)),
 3: ('03_positive_5v', '+5 V converter and output eFuse', (420,297)),
 4: ('04_negative_converter', 'Negative converter - raw rail', (420,297)),
 5: ('05_negative_protection', 'Negative rail protection and level shifting', (510,340)),
 6: ('06_fault_reset', 'Always-on control - all-rail fault latch and RESET', (550,420)),
 7: ('07_outputs_status', 'Protected outputs - voltage monitors and panel LEDs', (550,350)),
}


def layout(parts):
    """Return page and translation per reference; whole wired islands move together."""
    plan={}
    def put(refs,page,dx,dy):
        for ref in refs:
            assert ref in parts and ref not in plan,ref
            plan[ref]=(page,dx,dy)
    rr=lambda prefix,a,b:[prefix+str(i) for i in range(a,b+1)]
    put(['U2','L1','R8','R9',*rr('C',6,14),'#FLG04'],2,-276.86,0)
    put(['U3','L2','R10','R11','R12',*rr('C',15,23),'#FLG05'],3,-276.86,-127)
    put(['U4','L3','Q1',*rr('R',13,18),*rr('C',24,33),'#FLG03'],4,0,-147.32)
    put(['C34','D2','R19','D5'],2,-25.4,-203.2)
    put(['C35','D3','R20','D6'],3,-88.9,-203.2)
    put(['C36','D4','R21','D7'],4,-50.8,-241.3)
    put(['J2','J3'],7,0,-86.36)
    put(['SW1'],6,-38.1,-254)
    put(['U6','D12'],2,-464.82,0)
    put(rr('R',30,38)+rr('C',37,39),2,-464.82,68.58)
    put(['U7','D13'],3,-718.82,0)
    put(rr('R',39,46)+rr('C',40,42),3,-718.82,68.58)
    put(['U8','Q4','Q5','U16','U17','D14','D19','D20',*rr('R',48,62),'R89','R90',*rr('C',43,45),'#FLG08','#FLG09'],5,-599.44,-180.34)
    put(['U9','U10','U11','U12','U13','U14','U15',*rr('R',63,72),'R91',*rr('C',46,55),*rr('TP',9,16)],6,0,-393.7)
    put(['TP6'],6,203.2,213.36)
    put(['U18','U19','D15',*rr('R',73,85),'C56','C57','C58'],7,-599.44,-508)
    put(['D8','R22','D16','D17','D18',*rr('R',86,88),*rr('Q',6,10)],7,-599.44,-508)
    # Input section: source-owned coordinates fit an A3 sheet without scaling.
    put([ref for ref in parts if ref not in plan],1,0,0)
    return plan


def split(output_root, api):
    """api is the existing build_schematic module (shared symbol/pin helpers)."""
    hw=Path(output_root)/'hardware'; out=hw/'usb-power-45w.kicad_sch'
    flat=parse(out.read_text()); rootid=one(flat,'uuid')[1]
    partlist=api.circuit(); parts={p['ref']:p for p in partlist}; plan=layout(parts)
    flatxml=hw.parent/'docs/flat-parity.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(flatxml),str(out)],check=True,stdout=subprocess.DEVNULL)
    expected=ET.parse(flatxml).getroot()
    libs={s[1]:s for s in nodes(one(flat,'lib_symbols'),'symbol')}
    symbols=nodes(flat,'symbol'); refs={next(p[2] for p in nodes(s,'property') if p[1]=='Reference'):s for s in symbols}
    # Geometric islands were split at every endpoint by the flat drawing engine.
    parent={}
    def find(p):
        parent.setdefault(p,p)
        if parent[p]!=p:parent[p]=find(parent[p])
        return parent[p]
    def union(a,b):parent[find(a)]=find(b)
    xy=lambda n:tuple(map(float,one(n,'at')[1:3]))
    for w in nodes(flat,'wire'):
        a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]];union(a,b)
    pins={}; directions={}; owners=defaultdict(set); islandnets=defaultdict(set)
    for ref,s in refs.items():
        tab=api.pin_table(libs[one(s,'lib_id')[1]],int(one(s,'unit')[1]));x,y=xy(s);rot=float(one(s,'at')[3]);mir=one(s,'mirror') is not None
        for num,(px,py,ang,typ) in tab.items():
            dx,dy=api.xform(px,-py if mir else py,rot);pt=(round(x+dx,2),round(y+dy,2));pins[(ref,num)]=pt
            if ref in plan:
                owners[find(pt)].add(plan[ref])
                islandnets[find(pt)].add(parts[ref]['pins'][num] or ('NC:'+ref+'.'+num))
                directions[ref+'.'+num]=api.outward(-ang if mir else ang,rot)
    def island(pt):
        opts=owners[find(pt)]
        assert len(opts)==1,('island not a single planned placement transform',pt,opts)
        return next(iter(opts))
    sheetids={i:api.uid('S6/sheet/'+name) for i,(name,_,_) in PAGES.items()}
    trees={}
    for i,(name,title,size) in PAGES.items():
        trees[i]=parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
          (uuid "{api.uid('S6/file/'+name)}") (paper "User" {size[0]} {size[1]})
          (title_block (title {json.dumps(title)}) (rev "S6") (company "Big Modular")
          (comment 1 "Schematic only - see design.md and s6-rail-protection.md"))
          (lib_symbols) (embedded_fonts no))''')
        one(trees[i],'lib_symbols').extend(copy.deepcopy(nodes(one(flat,'lib_symbols'),'symbol')))
    def move(node,dx,dy):
        # Only the top item's coordinates and its direct properties are absolute.
        for loc in [one(node,'at'),*[one(p,'at') for p in nodes(node,'property')]]:
            if loc:loc[1]=round(float(loc[1])+dx,2);loc[2]=round(float(loc[2])+dy,2)
        if node[0]=='wire':
            for p in one(node,'pts')[1:]:p[1]=round(float(p[1])+dx,2);p[2]=round(float(p[2])+dy,2)
    for n in flat:
        if not isinstance(n,list):continue
        kind=n[0]
        if kind=='symbol':
            ref=next(p[2] for p in nodes(n,'property') if p[1]=='Reference')
            pg,dx,dy=plan[ref] if ref in plan else island(xy(n))
        elif kind=='wire':pg,dx,dy=island(tuple(map(float,one(n,'pts')[1][1:])))
        elif kind in ('label','junction','no_connect'):pg,dx,dy=island(xy(n))
        else:continue
        nn=copy.deepcopy(n);move(nn,dx,dy)
        if kind=='symbol':
            for path in walk(one(nn,'instances'),'path'):path[1]='/'+rootid+'/'+sheetids[pg]
        trees[pg].append(nn)
    ends={}
    for (ref,pin),pt in pins.items():
        if ref in plan:
            pg,dx,dy=plan[ref];ends[ref+'.'+pin]=(round(pt[0]+dx,2),round(pt[1]+dy,2))
    pin_nets={p['ref']+'.'+n: v or ('NC:'+p['ref']+'.'+n) for p in partlist for n,v in p['pins'].items()}
    obstacles=defaultdict(list); pinpoints=defaultdict(dict)
    for key,pt in ends.items():pinpoints[plan[key.split('.')[0]][0]][pt]=pin_nets[key]
    for w in nodes(flat,'wire'):
        a,b=[tuple(map(float,p[1:])) for p in one(w,'pts')[1:]]; pg,dx,dy=island(a)
        ns=islandnets[find(a)];assert len(ns)==1
        obstacles[pg].append(((round(a[0]+dx,2),round(a[1]+dy,2)),(round(b[0]+dx,2),round(b[1]+dy,2)),next(iter(ns))))
    routes=[]
    count=0
    def text(t,s,x,y,size=1.25):
        nonlocal count
        count+=1;t.append(parse(f'(text {json.dumps(s)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left top)) (uuid "{api.uid("S6/text/"+str(count))}"))'))
    def line(t,*points):
        nonlocal count
        pts=[ends[p] if isinstance(p,str) else p for p in points]
        for a,b in zip(pts,pts[1:]):
            if a==b:continue
            assert a[0]==b[0] or a[1]==b[1],('nonorthogonal',points,a,b)
            count+=1;t.append(parse(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid "{api.uid("S6/wire/"+str(count))}"))'))
    def link(pg,a,b,lane=None):
        """Connect this explicitly requested schematic net, avoiding unrelated pins/stubs.

        This is a schematic-only lane chooser for the listed connections, not a
        PCB router. Proper unjoined crossings are allowed, endpoint contacts are
        not. Native flat/hierarchy parity independently rejects any accidental join.
        """
        aa,bb=ends[a],ends[b]; net=pin_nets[a];assert net==pin_nets[b],(a,b,net,pin_nets[b])
        def on(p,x,y):return min(x[0],y[0])<=p[0]<=max(x[0],y[0]) and min(x[1],y[1])<=p[1]<=max(x[1],y[1]) and (x[0]==y[0]==p[0] or x[1]==y[1]==p[1])
        def clear(path):
            for x,y in zip(path,path[1:]):
                if x==y:continue
                for pt,n in pinpoints[pg].items():
                    if n!=net and on(pt,x,y):return False
                for c,d,n in obstacles[pg]:
                    if n==net:continue
                    if any(on(pt,c,d) for pt in (x,y)) or any(on(pt,x,y) for pt in (c,d)):return False
            return True
        da,db=directions[a],directions[b]
        candidates=[]
        if aa[0]==bb[0] or aa[1]==bb[1]:candidates.append([aa,bb])
        for escape in (5.08,3.81,2.54,6.35,7.62,8.89,10.16,11.43,12.7,15.24):
            sa=(round(aa[0]+da[0]*escape,2),round(aa[1]+da[1]*escape,2));sb=(round(bb[0]+db[0]*escape,2),round(bb[1]+db[1]*escape,2))
            for axis in ('x','y'):
                dim=0 if axis=='x' else 1; size=PAGES[pg][2][dim]
                target=lane[1] if lane and lane[0]==axis else (sa[dim]+sb[dim])/2
                values=sorted([round(15.24+k*1.27,3) for k in range(int((size-30.48)/1.27))],key=lambda v:abs(v-target))
                if lane and lane[0]==axis:values=[lane[1]]+values
                for v in values:
                    path=[aa,sa,(v,sa[1]),(v,sb[1]),sb,bb] if axis=='x' else [aa,sa,(sa[0],v),(sb[0],v),sb,bb]
                    if clear(path):
                        candidates.append(path);break
        candidates=[p for p in candidates if clear(p)]
        if not candidates:
            (hw.parent/'docs/lane-debug.json').write_text(json.dumps({'a':aa,'b':bb,'net':net,'directions':[da,db],'pins':list(pinpoints[pg].items()),'obstacles':obstacles[pg]},indent=2))
        assert candidates,('No safe schematic lane',pg,a,b)
        def score(path):
            manual = lane and any(abs(pt[0 if lane[0]=='x' else 1]-lane[1])<.001 for pt in path[1:-1])
            return (0 if manual else 1, sum(abs(x[0]-y[0])+abs(x[1]-y[1]) for x,y in zip(path,path[1:])))
        path=min(candidates,key=score)
        line(trees[pg],*path)
        obstacles[pg].extend((x,y,net) for x,y in zip(path,path[1:]) if x!=y)
        routes.append({'page':pg,'from':a,'to':b,'net':net,'path':path})
    # Readable series power paths; input and setting resistor chains are already
    # wired in the native flat source, not rendered as disconnected symbols.
    for pg,u,l in [(2,'U6','L1'),(3,'U7','L2')]:
        link(pg,l+'.2',u+'.1',('x',205.74))
        link(pg,u+'.3',u+'.6')
        # Rail clamp physically at the protected output.
        d='D12' if pg==2 else 'D13'
        link(pg,u+'.18',d+'.1',('x',304.8))
        for i,net in enumerate(['UV','OV','ILIM','DVDT']):
            pin={'UV':'7','OV':'8','ILIM':'11','DVDT':'10'}[net]
            ref=({'UV':'R31','OV':'R33','ILIM':'R34','DVDT':'C37'} if pg==2 else {'UV':'R40','OV':'R42','ILIM':'R43','DVDT':'C40'})[net]
            # Dividers reach the chip by staggered lanes, avoiding the power bus.
            if net in ('UV','OV'):link(pg,ref+'.1',u+'.'+pin,('x',182.88+i*7.62))
            else:link(pg,ref+'.1',u+'.'+pin,('x',330.2+i*7.62))
    # Remove redundant power glyphs exactly on these bank pins now that the
    # continuous power path is drawn (avoids four-way symbol junctions).
    for pg,u in [(2,'U6'),(3,'U7')]:
        remove_at={ends[u+'.1'],ends[u+'.18']}
        trees[pg][:]=[n for n in trees[pg] if not (isinstance(n,list) and n[0]=='symbol' and xy(n) in remove_at and any(p[1]=='Reference' and p[2].startswith('#PWR') for p in nodes(n,'property')))]
    # Negative pass path: sense resistors in parallel; controller gate, sense,
    # power-limit/timer links and OUT sense are explicit.
    link(5,'R48.1','R49.1');link(5,'R48.2','R49.2')
    link(5,'Q4.3','R49.1',('x',228.6))
    link(5,'U8.8','Q4.1',('y',88.9))
    link(5,'U8.7','R89.2',('x',137.16));link(5,'R89.1','R48.1',('y',66.04))
    link(5,'U8.9','R90.2',('x',129.54));link(5,'R90.1','Q4.2',('y',53.34))
    for pin,ref in [('2','R53'),('3','R55'),('4','R56'),('6','C44')]:
        link(5,'U8.'+pin,ref+'.1',('x',25.4+int(pin)*5.08))
    link(5,'U16.4','R53.1',('y',246.38))
    link(5,'U17.2','U8.10',('y',226.06))
    # Logic chain. POR reset fanout and shared good inputs use short named
    # inter-sheet ports; critical stored-state feedback and clocks are wired.
    link(6,'U10.1','U12.1',('y',152.4));link(6,'U12.1','U12.13',('x',27.94))
    link(6,'U11.1','U12.3',('y',162.56))
    link(6,'U12.5','U13.4',('y',180.34))
    link(6,'U12.8','U13.2',('y',271.78))
    link(6,'U13.6','U12.11',('y',281.94))
    link(6,'U14.6','R72.1',('x',396.24))
    link(6,'R72.2','C51.1');link(6,'C51.1','U15.2',('x',485.14))
    link(6,'U15.4','U13.5',('y',297.18))
    # Panel LED strings are already resistor -> LED -> sink wired in the flat
    # drawing. Common return/enable and voltage-sense connections are shown too.
    for pin,ref in [('7','R76'),('5','R79'),('8','R82'),('11','R84')]:
        link(7,'U18.'+pin,ref+'.1',('x',20.32+int(pin)*5.08))
    link(7,'U18.14','U19.2',('y',124.46))
    link(7,'U19.4','Q9.1',('y',248.92))
    link(7,'U18.1','Q7.1',('y',238.76));link(7,'U18.2','Q8.1',('y',228.6))
    for q in ['Q6','Q7','Q8','Q9']:link(7,q+'.2','Q10.3',('y',205.74))


    # Complete the local pull-up, supply, timing and optocoupler signal chains.
    for pg,u,pull,cout in [(2,'U6','R35','C38'),(3,'U7','R44','C41')]:
        link(pg,u+'.15',u+'.16',('x',279.4))
        link(pg,u+'.16',pull+'.2',('x',292.1))
        link(pg,u+'.18',cout+'.1',('x',383.54))
    for a,b,lane in [('R50.2','R51.2',None),('R51.2','C43.1',None),('C43.1','U8.1',('x',91.44)),
                     ('R59.2','R60.2',None),('R60.2','U16.1',('x',292.1)),('U16.2','Q5.3',None),
                     ('R61.2','U17.1',('x',393.7)),('U17.4','R62.2',('x',449.58)),
                     ('D19.2','D19.3',None),('D20.2','D20.3',None)]:link(5,a,b,lane)
    for a,b,lane in [('U9.1','C47.1',None),('R66.1','U10.5',('x',139.7)),('U10.3','SW1.1',('y',45.72)),
                     ('R70.1','U11.5',('x',259.08)),('U11.4','C49.1',('x',335.28))]:link(6,a,b,lane)
    link(7,'D15.3','R82.1',('y',185.42))
    (hw.parent/'docs/schematic-wiring.json').write_text(json.dumps(routes,indent=2)+'\n')

    # Inter-sheet nets are discovered from the circuit table (not inferred by
    # spelling). Each gets a real hierarchical pin. Ground alone is global.
    netpages=defaultdict(set)
    for p in partlist:
        for n in p['pins'].values():
            if n is not None:netpages[n].add(plan[p['ref']][0])
    crossing={n:pgs for n,pgs in netpages.items() if len(pgs)>1 and n!='GND'}
    # Hierarchical labels at short named interface stubs: root is the explicit
    # power-flow diagram; child labels also document their direction/role.
    for pg,t in trees.items():
        text(t,PAGES[pg][1].upper(),20.32,12.7,2)
        names=sorted(n for n,pgs in crossing.items() if pg in pgs)
        width,height=PAGES[pg][2]
        for i,n in enumerate(names):
            cols=4 if width<500 else 5
            x=25.4+(i%cols)*88.9;y=round(round((height-50.8)/1.27)*1.27+(i//cols)*10.16,2)
            line(t,(x,y),(x+15.24,y))
            count+=1
            t.append(parse(f'(hierarchical_label {json.dumps(n)} (shape bidirectional) (at {x} {y} 180) (effects (font (size 1.1 1.1)) (justify right)) (uuid "{api.uid("S6/port/"+str(pg)+n)}"))'))
            t.append(parse(f'(label {json.dumps(n)} (at {x+15.24} {y} 0) (effects (font (size 1.1 1.1)) (justify left bottom)) (uuid "{api.uid("S6/port-label/"+str(pg)+n)}"))'))
        text(t,'INTER-SHEET INTERFACE (see wired power-flow overview)',20.32,height-71.12,1.2)
    notes={
      1:'20 V PD request; U5 TPS16630 remains 60 V, 4.186 A nominal. RUN from retained fault latch.\nMAIN_OK is wired FLT + PGOOD at 3.3 V, NOT a raw-voltage logic output.',
      2:'TPS62933F converter unchanged. RAW feedback/bulk stay BEFORE U6.\nU6: 2.647 A nominal, 2.335-2.971 A screened. No guaranteed 2.5 A minimum; MODE latch-off.',
      3:'TPS62933F converter unchanged. U7 input must remain >=4.5 V.\nU7: 2.647 A nominal, 2.335-2.971 A screened. Output-valid and FLT/PGOOD share P5_OK.',
      4:'LMR38020F ground/exposed pad = N12_RAW, not system GND.\nQ1 follows P12_RAW; load reaches N12_RAW ONLY through page 05 series protection.',
      5:'System GND is continuous. R48 || R49 = 50 mOhm; Q4 is in the NEGATIVE conductor.\nU8 VCC is resistor-fed from VIN. U16 disables via UVLO; U17 level shifts PGD.\nNominal 1 A / 3.1 W MOSFET limit. Reverse-collapse pin clamps do not block reverse power.',
      6:'RESET clears ARMED and FAULT; RUN is forced low while reset is asserted.\nStartup qualification ~5.7 s typical, then any persistent bad status latches OFF until RESET.\nARMED does not clear just because a rail/input disappears. Local protection is active at startup.',
      7:'D8 MAIN: input-valid AND main-eFuse status AND RUN. D16/+12, D17/+5, D18/-12: delivered-rail status AND RUN.\nAny latched common fault turns all four panel LEDs OFF. D5/D6/D7 on converter pages indicate RAW rails.\nVoltage-present thresholds are not +/-5% regulation guarantees; retained external charge is not actively discharged.'}
    for pg,msg in notes.items():text(trees[pg],msg,20.32,30.48 if pg in [5,7] else 220.98 if pg in [2,3] else 180.34 if pg in [1,4] else 345.44,1.15)
    # Overview sheet, with main power paths physically connected and control
    # interfaces named at each block to avoid a spaghetti web of crossing lines.
    root=copy.deepcopy(flat)
    root[:]=[n for n in root if not isinstance(n,list) or n[0] in ['version','generator','generator_version','uuid','paper','title_block','lib_symbols','embedded_fonts']]
    one(root,'paper')[1:]=['User',650,530];one(root,'lib_symbols')[1:]=[]
    one(one(root,'title_block'),'title')[1]='USB power - wired power flow and protection overview'
    text(root,'USB POWER / ALL-RAIL PROTECTION AND RESET',20.32,15.24,2.4)
    text(root,'S6 schematic only. All three converters retained; main and + rails TPS16630; negative LM5067 + MOSFET.',20.32,25.4,1.2)
    boxes={1:(40.64,60.96,81.28,111.76),2:(177.8,50.8,101.6,81.28),3:(177.8,162.56,101.6,81.28),
           4:(177.8,284.48,101.6,71.12),5:(340.36,284.48,101.6,101.6),6:(40.64,406.4,259.08,96.52),7:(497.84,60.96,96.52,243.84)}
    # Preferred power pins at right; control/input/status ports at left.
    outputs={1:['VPD','VIN','MAIN_OK'],2:['+12V','P12_RAW'],3:['+5V'],4:['N12_RAW'],5:['-12V','N12_STATUS'],6:['RUN','V3V3','MAIN_LED_OK','FAULT_LATCH'],7:['P12_OK','P5_OK','N12_OK','V20_OK']}
    rootpins={}
    for pg,(x,y,w,h) in boxes.items():
        names=sorted(n for n,pgs in crossing.items() if pg in pgs);right=[n for n in outputs[pg] if n in names];left=[n for n in names if n not in right]
        sh=parse(f'''(sheet (at {x} {y}) (size {w} {h}) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0))
          (uuid "{sheetids[pg]}") (property "Sheetname" {json.dumps(PAGES[pg][1])} (at {x} {y-2.54} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
          (property "Sheetfile" {json.dumps(PAGES[pg][0]+'.kicad_sch')} (at {x} {y+h+2.54} 0) (effects (font (size 1.1 1.1)) (justify left top)))
          (instances (project "usb-power-45w" (path "/{rootid}" (page "{pg+1}")))))''')
        for side,ns in [('L',left),('R',right)]:
            for k,n in enumerate(ns):
                px=x if side=='L' else x+w;py=round(y+10.16+k*7.62,2);ang=180 if side=='L' else 0
                rootpins[(pg,n)]=(px,py)
                sh.append(parse(f'(pin {json.dumps(n)} bidirectional (at {px} {py} {ang}) (effects (font (size 1.1 1.1)) (justify {"left" if side=="L" else "right"})) (uuid "{api.uid("S6/sheetpin/"+str(pg)+n)}"))'))
        root.append(sh)
        descriptions={1:'CH224A: 20 V request\nTPS16630: 4.186 A nominal',2:'TPS62933F -> TPS16630\n+12 V protected output',3:'TPS62933F -> TPS16630\n+5 V protected output',4:'LMR38020F inverting buck-boost\nRAW negative supply',5:'LM5067 + external N-MOSFET\n1.0 A nominal / optical control',6:'60 V always-on LDO / retained ARMED + FAULT\nManual RESET disables all three rails',7:'Parallel Eurorack headers\nMAIN, +12, +5 and -12 LEDs'}
        text(root,descriptions[pg],x+10.16,y+h-20.32,1.4)
    # Explicit root wires for power flow; other interfaces use named wire stubs.
    routed=set()
    def rootlink(a,b,lane):
        aa,bb=rootpins[a],rootpins[b];line(root,aa,(lane,aa[1]),(lane,bb[1]),bb);routed.update([a,b])
    for pg in [2,3,4]:rootlink((1,'VIN'),(pg,'VIN'),137.16)
    rootlink((4,'N12_RAW'),(5,'N12_RAW'),314.96)
    rootlink((2,'+12V'),(7,'+12V'),457.2)
    rootlink((3,'+5V'),(7,'+5V'),467.36)
    rootlink((5,'-12V'),(7,'-12V'),477.52)
    for key,pt in rootpins.items():
        n=key[1];side='R' if n in outputs[key[0]] else 'L';dx=7.62 if side=='R' else -7.62
        # Add a name even on wired power nets; labels do not replace those wires.
        target=(round(pt[0]+dx,2),pt[1]);line(root,pt,target)
        count+=1;root.append(parse(f'(label {json.dumps(n)} (at {target[0]} {target[1]} {0 if side=="R" else 180}) (effects (font (size 1 1)) (justify {"left" if side=="R" else "right"} bottom)) (uuid "{api.uid("S6/rootlabel/"+str(count))}"))'))
    text(root,'FAULT POLICY\nEach rail detects independently.\nPersistent fault -> all OFF until RESET.\nMain LED is not merely a +5 V lamp.',340.36,431.8,1.4)
    text(root,'OUTPUTS: +12 / +5 / -12\nNominal limits: 2.647 / 2.647 / 1.0 A\nTolerance and thermal limits apply.\nNot a guaranteed 54.5 W simultaneous rating.',340.36,472.44,1.2)
    trees[0]=root
    # Split added wires at endpoints AND actual pin ends, then add junctions.
    for pg,t in trees.items():
        allpins={pt for key,pt in ends.items() if plan[key.split('.')[0]][0]==pg} if pg else set(rootpins.values())
        anchors=allpins|{xy(n) for typ in ['label','hierarchical_label','junction'] for n in nodes(t,typ)}
        wires=[tuple(tuple(map(float,p[1:])) for p in one(w,'pts')[1:]) for w in nodes(t,'wire')]
        anchors|={p for seg in wires for p in seg}
        t[:]=[n for n in t if not (isinstance(n,list) and n[0] in ('wire','junction'))]
        segments=set()
        for a,b in wires:
            pts=[p for p in anchors if min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]) and (a[0]==b[0]==p[0] or a[1]==b[1]==p[1])]
            pts.sort(key=lambda p:abs(p[0]-a[0])+abs(p[1]-a[1]))
            segments.update(tuple(sorted([aa,bb])) for aa,bb in zip(pts,pts[1:]) if aa!=bb)
        degree=defaultdict(int)
        for a,b in sorted(segments):line(t,a,b);degree[a]+=1;degree[b]+=1
        for pt,d in degree.items():
            if d>=3 or (d>=2 and pt in allpins):
                count+=1;t.append(parse(f'(junction (at {pt[0]} {pt[1]}) (diameter 0) (color 0 0 0 0) (uuid "{api.uid("S6/junction/"+str(count))}"))'))
        if pg:
            t.append(parse(f'(sheet_instances (path "/{rootid}/{sheetids[pg]}" (page "{pg+1}")))'))
        else:t.append(parse('(sheet_instances (path "/" (page "1")))'))
        dest=out if pg==0 else hw/(PAGES[pg][0]+'.kicad_sch')
        dest.write_text(dump(t)+'\n')
    subprocess.run(['kicad-cli','sch','upgrade','--force',str(out)],check=True,stdout=subprocess.DEVNULL)
    xml=hw.parent/'docs/hierarchy-parity.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(out)],check=True,stdout=subprocess.DEVNULL)
    actual=ET.parse(xml).getroot()
    def identity(root):
        comps={c.get('ref'):(c.findtext('value'),c.findtext('footprint'),tuple(sorted((f.get('name'),f.text) for f in c.findall('fields/field')))) for c in root.findall('components/comp')}
        nets={frozenset((p.get('ref'),p.get('pin')) for p in n.findall('node')) for n in root.findall('nets/net')}
        return comps,nets
    want,got=identity(expected),identity(actual)
    assert want[0]==got[0], 'Hierarchy changed component values/fields/footprints'
    assert want[1]==got[1],('Hierarchy changed nets; inspect native XML',len(want[1]^got[1]))
    (hw.parent/'docs/hierarchy-parity.json').write_text(json.dumps({'equal_pin_sets':True,'components':len(got[0]),'sheets':len(PAGES)+1,'note':'Net paths intentionally change; exact component/pin memberships and native fields preserved.'},indent=2)+'\n')
    flatxml.unlink();xml.unlink()
    print('Native hierarchy:',len(PAGES)+1,'pages;',len(got[0]),'parts; exact flat/hierarchy parity')
