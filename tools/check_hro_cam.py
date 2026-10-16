"""Narrow HRO release inspection using existing Gerbonara parser/SVG renderer.

No Gerber parser, board renderer or exporter is implemented here. Shapely evaluates
actual CAM primitive areas at <=0.0001mm chord error. Unknown/invalid inputs fail.
"""
from collections import Counter, defaultdict
from pathlib import Path
from html import escape
import copy, json, math, subprocess, warnings
from gerbonara import GerberFile, ExcellonFile, ipc356
from gerbonara import graphic_objects as go, graphic_primitives as gp
from gerbonara.rs274x import GerberParser
from gerbonara.utils import MM, approximate_arc
from shapely.geometry import Polygon, Point, LineString, GeometryCollection
from shapely.ops import unary_union
from shapely import make_valid


class RegionAttributeParser(GerberParser):
    # Gerbonara 1.6.3 forgets current X2 object attrs on Region; retain its parsed
    # dictionary at G36/G37. No token/coordinate/aperture/geometry parser replacement.
    def _parse_region_start(self, match):
        super()._parse_region_start(match)
        self.region_attrs=dict(self.graphics_state.object_attrs)
    def _parse_region_end(self, match):
        assert self.region_attrs==self.graphics_state.object_attrs, 'attrs changed within region'
        self.current_region.attrs=dict(self.region_attrs)
        super()._parse_region_end(match)


def read_gerber(path):
    result=GerberFile()
    with warnings.catch_warnings():
        warnings.simplefilter('error') # No silently ignored Gerber commands.
        RegionAttributeParser(result).parse(path.read_text(),filename=str(path))
    return result


def object_area(obj):
    obj=copy.copy(obj);obj.polarity_dark=True
    result=GeometryCollection()
    for p in obj.to_primitives(MM):
        if isinstance(p,gp.Circle):shape=Point(p.x,p.y).buffer(p.r,quad_segs=128)
        elif isinstance(p,gp.Line):shape=LineString([(p.x1,p.y1),(p.x2,p.y2)]).buffer(p.width/2,quad_segs=128)
        else:shape=make_valid(Polygon(p.to_arc_poly().approximate_arcs(max_error=.0001).outline))
        result=result.union(shape) if p.polarity_dark else result.difference(shape)
    return result


def area(objects):
    # Respect sequential dark/clear polarity; union same-polarity runs for speed.
    out=GeometryCollection();batch=[];dark=True
    for o in objects:
        if o.polarity_dark!=dark:
            chunk=unary_union(batch);out=out.union(chunk) if dark else out.difference(chunk)
            batch=[];dark=o.polarity_dark
        batch.append(object_area(o))
    chunk=unary_union(batch)
    return out.union(chunk) if dark else out.difference(chunk)


def outlines(g):
    adj=defaultdict(list);parts=[]
    for i,o in enumerate(g.objects):
        assert isinstance(o,(go.Line,go.Arc)), 'non-centreline outline object'
        a=tuple(round(v,6) for v in (o.x1,o.y1));b=tuple(round(v,6) for v in (o.x2,o.y2))
        adj[a].append(i);adj[b].append(i)
        if isinstance(o,go.Arc):
            points=list(approximate_arc(o.x1+o.cx,o.y1+o.cy,o.x1,o.y1,o.x2,o.y2,o.clockwise,max_error=.0001))
        else:points=[a,b]
        parts.append((a,b,points))
    assert all(len(v)==2 for v in adj.values()), 'open or branching exported outline'
    unused=set(range(len(parts)));loops=[]
    while unused:
        i=min(unused);start,end,points=parts[i];unused.remove(i);path=list(points)
        while end!=start:
            nxt=next(j for j in adj[end] if j in unused);unused.remove(nxt)
            a,b,pts=parts[nxt]
            if a!=end:a,b,pts=b,a,list(reversed(pts))
            assert a==end;path.extend(pts[1:]);end=b
        poly=Polygon(path);assert poly.is_valid and poly.area>0
        loops.append(poly)
    return sorted(loops,key=lambda p:p.area,reverse=True)


def drill_signature(obj):
    d=round(obj.aperture.diameter,6)
    if isinstance(obj,go.Flash):return ('round',round(obj.x,6),round(obj.y,6),d)
    assert isinstance(obj,go.Line),'unsupported drill object'
    a,b=sorted([(round(obj.x1,6),round(obj.y1,6)),(round(obj.x2,6),round(obj.y2,6))])
    return ('slot',*a,*b,d)


def native_drills(board):
    import pcbnew as p
    signatures={True:[],False:[]}
    for v in board.GetTracks():
        if v.GetClass()=='PCB_VIA':signatures[True].append(('round',round(p.ToMM(v.GetPosition().x),6),round(-p.ToMM(v.GetPosition().y),6),round(p.ToMM(v.GetDrill()),6)))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            w,h=p.ToMM(pad.GetDrillSize());x,y=p.ToMM(pad.GetPosition());y=-y
            if not w:continue
            if abs(w-h)<1e-8:sig=('round',round(x,6),round(y,6),round(w,6))
            else:
                # Transform endpoints of actual native slotted drill, not pad bounds.
                angle=math.radians(pad.GetOrientationDegrees())
                dx,dy=((w-h)/2,0) if w>h else (0,(h-w)/2)
                # KiCad screen-positive Y; pad rotation is CCW in mathematical plane.
                vx=dx*math.cos(angle)+dy*math.sin(angle);vy=dx*math.sin(angle)-dy*math.cos(angle)
                a,b=sorted([(round(x-vx,6),round(y-vy,6)),(round(x+vx,6),round(y+vy,6))])
                sig=('slot',*a,*b,round(min(w,h),6))
            signatures[pad.GetAttribute()==p.PAD_ATTRIB_PTH].append(sig)
    return {k:Counter(v) for k,v in signatures.items()}


def compare_drills(actual,expected):
    # KiCad Excellon decimal export is 3 places; native nm coordinates can differ
    # by half its 0.001mm quantum. Pair every hole uniquely, never round away a
    # missing/extra hole, tool-size change, slot orientation or endpoint error.
    remaining=list(expected.elements());largest=0
    for sig in actual:
        hits=[(i,n) for i,n in enumerate(remaining) if sig[0]==n[0] and sig[-1]==n[-1]
              and max(abs(a-b) for a,b in zip(sig[1:-1],n[1:-1]))<=.000501]
        assert len(hits)==1, ('drill mismatch',sig,hits)
        i,n=hits[0];largest=max(largest,max(abs(a-b) for a,b in zip(sig[1:-1],n[1:-1])));remaining.pop(i)
    assert not remaining,('missing drill',remaining)
    return round(largest,9)


def render_grid(path,title,cells,width=1100):
    """Only page composition; actual artwork is rendered by Gerbonara.svg_objects."""
    cols=2;cw=120;ch=49;rows=(len(cells)+1)//2
    tags=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{cw*cols}mm" height="{rows*ch+12}mm" viewBox="0 0 {cw*cols} {rows*ch+12}">',
          '<rect width="100%" height="100%" fill="#101b29"/>',
          f'<text x="4" y="7" fill="white" font-family="sans-serif" font-size="3.4">{escape(title)}</text>']
    for n,(label,bounds,layers) in enumerate(cells):
        (x0,y0),(x1,y1)=bounds;s=min((cw-8)/(x1-x0),(ch-10)/(y1-y0));ox=n%cols*cw+4;oy=n//cols*ch+12
        tags.append(f'<text x="{ox}" y="{oy+3}" fill="white" font-family="sans-serif" font-size="2.7">{escape(label)}</text>')
        tags.append(f'<svg x="{ox}" y="{oy+6}" width="{cw-8}" height="{ch-10}" viewBox="{x0} {-y1} {x1-x0} {y1-y0}" preserveAspectRatio="xMinYMin meet"><defs><clipPath id="crop{n}"><rect x="{x0}" y="{-y1}" width="{x1-x0}" height="{y1-y0}"/></clipPath></defs><g clip-path="url(#crop{n})"><g transform="scale(1,-1)">')
        for obj,color in layers:tags.extend(str(t) for t in obj.svg_objects(svg_unit=MM,fg=color,bg='#101b29',aperture_map={}))
        tags.append('</g></g></svg>')
    tags.append('</svg>');path.write_text('\n'.join(tags)+'\n')
    subprocess.run(['rsvg-convert','-w',str(width),'-o',str(path.with_suffix('.png')),str(path)],check=True)


def inspect_cam(root, hardware, native_audit):
    import pcbnew as p
    reports={};preview=root/'previews';preview.mkdir()
    parser_warnings=[]
    all_files={}
    for key,stem in [('carrier','big_modular'),('passive-panel','front_panel')]:
        folder=root/key;board=p.LoadBoard(str(hardware/(stem+'.kicad_pcb')))
        cam={f.name.removeprefix(stem+'-').removesuffix('.gbr'):read_gerber(f) for f in folder.glob('*.gbr')}
        all_files[key]=cam
        loops=outlines(cam['Edge_Cuts']);assert len(loops)==(1 if key=='carrier' else 2)
        x0,y0,x1,y1=loops[0].bounds
        dim=[round(x1-x0,6),round(y1-y0,6)];assert dim==([100.5,30] if key=='carrier' else [9.8,128.5])
        if key!='carrier':
            assert tuple(round(v,6) for v in loops[1].bounds)==(53.9,-68.9,58.9,-58.1)
            assert abs(loops[1].area-(5*10.8-(4-math.pi)*.6**2))<.0002
            assert not cam['F_Cu'].objects and not cam['B_Cu'].objects
            assert not cam['F_Mask'].objects and not cam['B_Mask'].objects
        expected=native_drills(board);drills={};tool_counts={};slots=[];drill_errors={}
        for plated,label in [(True,'PTH'),(False,'NPTH')]:
            drillpath=folder/f'{stem}-{label}.drl'
            expected_function=f'TF.FileFunction,{"Plated" if plated else "NonPlated"},1,{4 if key=="carrier" else 2},{label}'
            assert expected_function in drillpath.read_text(), 'actual Excellon plating metadata mismatch'
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always');d=ExcellonFile.open(drillpath,plated=plated)
            for w in caught:
                # Native KiCad's G90 location is understood; record, never hide.
                msg=str(w.message).split(': ',1)[-1]
                assert 'G90 header statement found after end of header' in msg,msg
                parser_warnings.append({'file':f'{key}/{stem}-{label}.drl','message':'G90 after M48 header; accepted by parser, absolute coordinates independently verified'})
            drills[label]=d;drill_errors[label]=compare_drills([drill_signature(o) for o in d.objects],expected[plated])
            # Gerbonara leaves KiCad X2-in-comment plating as None even with
            # the documented plated hint. Require the actual native file metadata
            # above and every tool's native classification, not a filename guess.
            tool_lines=[line for line in drillpath.read_text().splitlines() if 'TA.AperFunction' in line]
            assert all(f'AperFunction,{"Plated" if plated else "NonPlated"},{label},' in line for line in tool_lines)
            assert all(o.aperture.plated in (None,plated) for o in d.objects)
            tool_counts[label]=dict(sorted(Counter(f'{o.aperture.diameter:.3f}' for o in d.objects).items()))
            slots.extend(drill_signature(o) for o in d.objects if isinstance(o,go.Line))
        cam.update(drills)
        reports[key]={'outline_centerline_dimensions_mm':dim,'closed_outline_loops':len(loops),
            'Gerber_objects':{k:len(v.objects) for k,v in cam.items()},'drill_tools_mm_hits':tool_counts,
            'slot_centreline_endpoints_CAM_mm':slots,'native_drills_all_uniquely_matched':True,'max_drill_coordinate_quantization_error_mm':drill_errors}
        job=json.loads((folder/f'{stem}-job.gbrjob').read_text())
        assert job['GeneralSpecs']['Size']=={'X':dim[0],'Y':dim[1]}
        assert all((folder/f['Path']).is_file() for f in job['FilesAttributes'])
    cam=all_files['carrier'];paste=read_gerber(root/'assembly-stencil-support-only/big_modular-F_Paste.gbr')
    topmask=area(cam['F_Mask'].objects);pasteshape=area(paste.objects)
    copperpads=[o for o in cam['F_Cu'].objects if isinstance(o,go.Flash) and '.P' in o.attrs]
    # Native independent expected HRO centres/dimensions, not inferred from plot count.
    lands={'A1':(-3.225,.575),'A4':(-2.45,.575),'B8':(-1.75,.3),'A5':(-1.25,.3),
           'B7':(-.75,.3),'A6':(-.25,.3),'A7':(.25,.3),'B6':(.75,.3),
           'A8':(1.25,.3),'B5':(1.75,.3),'A9':(2.45,.575),'A12':(3.225,.575)}
    for pin,(dx,w) in lands.items():
        hits=[o for o in copperpads if o.attrs['.P'][:2]==('J1',pin)];assert len(hits)==1
        o=hits[0];shape=object_area(o)
        assert abs(o.x-(69.25+dx))<1e-6 and abs(o.y+95.78)<1e-6
        assert abs(shape.area-w*1.45)<1e-6
        assert shape.difference(topmask).area<1e-7 and shape.difference(pasteshape).area<1e-7
    shells=[o for o in copperpads if o.attrs['.P'][:2]==('J1','S1')];assert len(shells)==4
    bottommask=area(cam['B_Mask'].objects)
    for o in shells:
        shape=object_area(o);assert shape.intersection(pasteshape).area<1e-7
        assert shape.difference(topmask).area<1e-7 and shape.difference(bottommask).area<1e-7
    # Actual via barrel/paste and exposed SMT pad geometry cross-check.
    smd=[o for o in copperpads if any(k=='.AperFunction' and v[0] in ('SMDPad','HeatsinkPad') for k,v in o.aperture.attrs)]
    smdshape=area(smd).intersection(topmask)
    cam_vip=[];cam_paste=[]
    for v in native_audit['vias']:
        x,y=v['xy_mm'];disk=Point(x,-y).buffer(v['drill_mm']/2,quad_segs=128)
        if disk.intersection(smdshape).area>1e-9:cam_vip.append(v['uuid'])
        if disk.intersection(pasteshape).area>1e-9:cam_paste.append(v['uuid'])
    assert set(cam_vip)=={v['uuid'] for v in native_audit['vias'] if v['exposed_SMD_copper_hits']}
    assert set(cam_paste)=={v['uuid'] for v in native_audit['vias'] if v['paste_overlap_sides']}
    assert len(cam_vip)==len(cam_paste)==35
    # Net-attributed CAM copper: RTN and GND must be distinct at every layer.
    net_geometries={};isolation={}
    for layer in ['F_Cu','In1_Cu','In2_Cu','B_Cu']:
        nets=defaultdict(list)
        for o in cam[layer].objects:
            if '.N' in o.attrs:nets[o.attrs['.N'][0]].append(o)
        shapes={n:area(os) for n,os in nets.items()};net_geometries[layer]=shapes
        gnd=shapes['/GND'];rtn=shapes['/Autonomous hardware window and retry/RTN']
        assert gnd.intersection(rtn).area<1e-9
        isolation[layer]={'GND_RTN_gap_mm':round(gnd.distance(rtn),6),'GND_area_mm2':round(gnd.area,6),'RTN_area_mm2':round(rtn.area,6)}
    assert net_geometries['In1_Cu']['/GND'].geom_type=='Polygon','split exported GND plane'
    # Every IPC point maps to an actual native pad/via; detect truncated-name collision.
    board=p.LoadBoard(str(hardware/'big_modular.kicad_pcb'));native=[]
    for f in board.GetFootprints():
        for pad in f.Pads():
            if pad.GetNumber() and pad.GetNetname():native.append((f.GetReference(),pad.GetNumber(),*p.ToMM(pad.GetPosition()),pad.GetNetname()))
    for v in board.GetTracks():
        if v.GetClass()=='PCB_VIA':native.append((None,None,*p.ToMM(v.GetPosition()),v.GetNetname()))
    ipc=ipc356.Netlist.open(root/'carrier/big_modular.d356');netmap={};mapped=[]
    for rec in ipc.test_records:
        if not rec.is_connected:continue
        x=MM(rec.x,rec.unit);y=-MM(rec.y,rec.unit);pin=None if rec.is_via else rec.pin
        hits=[n for n in native if n[0]==rec.ref_des and n[1]==pin and math.hypot(x-n[2],y-n[3])<.003]
        assert len(hits)==1, (str(rec),hits)
        n=hits[0];mapped.append(n)
        if rec.net_name in netmap:assert netmap[rec.net_name]==n[-1],'IPC truncated net-name collision'
        netmap[rec.net_name]=n[-1]
    assert Counter(mapped)==Counter(native),'IPC omission/duplication'
    (root/'carrier/ipc-net-name-map.json').write_text(json.dumps(netmap,indent=2,sort_keys=True)+'\n')
    for pin,net in [('8','/Autonomous hardware window and retry/RTN'),('17','/Autonomous hardware window and retry/RTN'),('9','/GND')]:
        hits=[o for o in copperpads if o.attrs['.P'][:2]==('U2',pin)];assert len(hits)==1 and hits[0].attrs['.N']==(net,)
    reports['carrier'].update({'HRO_SMT_lands_copper_mask_paste':12,'HRO_shells_copper_masks_no_paste':4,
        'via_barrels_exposed_SMD_Cu':len(cam_vip),'via_barrels_paste':len(cam_paste),'native_CAM_VIP_UUID_sets_equal':True,'boundary_only_barrels_native':native_audit['barrels_at_SMD_boundary_only'],
        'IPC_records_checked':len(mapped),'IPC_net_aliases_unique':len(netmap),'RTN_GND_CAM_isolation':isolation,
        'In1_GND_connected_polygon':True,'U2_8_17_RTN_9_GND_verified':True})
    outline=cam['Edge_Cuts'];pth=cam['PTH'];npth=cam['NPTH'];bound=((49,-103),(151,-71.5))
    render_grid(preview/'carrier-copper-cam.svg','ACTUAL EXPORTED CAM | four copper layers, drills + closed profile',[
        (n,bound,[(cam[n],'#eda942'),(outline,'#bfd0dd'),(pth,'#101b29'),(npth,'#f46c65')]) for n in ['F_Cu','In1_Cu','In2_Cu','B_Cu']],1600)
    render_grid(preview/'carrier-mask-silk-cam.svg','ACTUAL EXPORTED CAM | mask OPENINGS / silkscreen',[
        (n,bound,[(cam[n],'#6dded5' if 'Mask' in n else '#eeeeee'),(outline,'#bfd0dd')]) for n in ['F_Mask','B_Mask','F_Silkscreen','B_Silkscreen']],1600)
    close=((63.9,-102.5),(74.6,-94.8))
    render_grid(preview/'hro-cam.svg','HRO C165948 | ACTUAL GERBER / EXCELLON | no shell paste',[
        ('Front copper + plated/NPTH holes',close,[(cam['F_Cu'],'#eda942'),(pth,'#101b29'),(npth,'#f46c65')]),
        ('Front mask OPENINGS',close,[(cam['F_Mask'],'#6dded5')]),
        ('Front paste: 12 contact lands only',close,[(paste,'#bf86ed')]),
        ('Drills: 4 plated slots + 2 locator NPTH',close,[(pth,'#eda942'),(npth,'#f46c65'),(outline,'#bfd0dd')])],1400)
    close=((77,-91),(89,-82))
    render_grid(preview/'efuse-cam.svg','ACTUAL CAM | orange: eFuse RTN / green: main GND',[
        (n,close,[(GerberFile(objects=[o for o in cam[n].objects if o.attrs.get('.N')==('/GND',)]),'#4cc8a6'),
                  (GerberFile(objects=[o for o in cam[n].objects if o.attrs.get('.N')==('/Autonomous hardware window and retry/RTN',)]),'#eeaa55')]) for n in ['F_Cu','In1_Cu','In2_Cu','B_Cu']],1400)
    panel=all_files['passive-panel'];g=GerberFile(objects=panel['Edge_Cuts'].objects+panel['F_Silkscreen'].objects+panel['NPTH'].objects)
    # Native library renderer; shape points come from CAM, not PCB geometry.
    import xml.etree.ElementTree as ET
    for name,bounds,height in [('passive-panel-cam',None,1400),('passive-panel-detail',((49,-85),(61,-49)),1000)]:
        svg=ET.fromstring(str(g.to_svg(margin=1,fg='#19334b',bg='white',force_bounds=bounds)))
        x,y,w,h=svg.attrib['viewBox'].split()
        svg.insert(0,ET.Element('{http://www.w3.org/2000/svg}rect',{'x':x,'y':y,'width':w,'height':h,'fill':'white'}))
        path=preview/(name+'.svg');path.write_text(ET.tostring(svg,encoding='unicode')+'\n')
        subprocess.run(['rsvg-convert','-h',str(height),'-o',str(path.with_suffix('.png')),str(path)],check=True)
    reports['parser_notices']=parser_warnings
    reports['geometry_chord_error_mm']=.0001
    reports['status']='actual CAM checks passed; no assembly/product qualification'
    return reports
