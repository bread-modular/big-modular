import sys, json, math, itertools, pcbnew
N=pcbnew.ToMM; M=pcbnew.FromMM
new=pcbnew.LoadBoard(sys.argv[1]); old=pcbnew.LoadBoard(sys.argv[2])
out={}
def fp(b,r): return b.FindFootprintByReference(r)
def pads(b,r): return {p.GetNumber():(round(N(p.GetPosition().x),4),round(N(p.GetPosition().y),4),p.GetNetname(),round(N(p.GetSize().x),3),round(N(p.GetSize().y),3)) for p in fp(b,r).Pads()}
for r in ['D29','C78']:
  f=fp(new,r); out[r]={'pos':(N(f.GetPosition().x),N(f.GetPosition().y)),'rot':f.GetOrientationDegrees(),'value':f.GetValue(),'pads':pads(new,r),'oldpads':pads(old,r)}
out['U14']={k:v for k,v in pads(new,'U14').items() if k in ('1','11','12','13','15','16','17')}
# placement diff
mv=[]
for f in new.GetFootprints():
  o=fp(old,f.GetReference()) if f.GetReference() else None
  if o is None: continue
  if (f.GetPosition()!=o.GetPosition()) or f.GetOrientationDegrees()!=o.GetOrientationDegrees() or f.GetLayer()!=o.GetLayer(): mv.append(f.GetReference())
out['moved']=mv
out['mounts_same']=sorted((N(f.GetPosition().x),N(f.GetPosition().y)) for f in new.GetFootprints() if not f.GetReference())==sorted((N(f.GetPosition().x),N(f.GetPosition().y)) for f in old.GetFootprints() if not f.GetReference())
out['back_fps']=[f.GetReference() for f in new.GetFootprints() if f.GetLayer()!=pcbnew.F_Cu]
# hot-loop tracks
box=lambda x,y:127<=x<=136.5 and 76.5<=y<=86.5
tr=[]
for t in new.GetTracks():
  s,e=t.GetStart(),t.GetEnd()
  if box(N(s.x),N(s.y)) or box(N(e.x),N(e.y)):
    d=dict(net=t.GetNetname(),layer=t.GetLayerName(),s=(round(N(s.x),3),round(N(s.y),3)))
    if t.Type()==pcbnew.PCB_VIA_T: d.update(kind='via',drill=N(t.GetDrillValue()),dia=N(t.GetWidth(pcbnew.F_Cu)))
    else: d.update(kind='trk',e=(round(N(e.x),3),round(N(e.y),3)),w=N(t.GetWidth()))
    tr.append(d)
out['loop_items']=tr
# EP vias In1 containment
ep=[t for t in new.GetTracks() if t.Type()==pcbnew.PCB_VIA_T and 129.2<=N(t.GetPosition().x)<=130.4 and 83.8<=N(t.GetPosition().y)<=85.0]
in1=[z for z in new.Zones() if z.IsOnLayer(pcbnew.In1_Cu) and z.GetNetname()=='/GND']
res=[]
for v in ep:
  c=v.GetPosition(); r=v.GetWidth(pcbnew.F_Cu)/2
  isl=set()
  ok=0
  for z in in1:
    poly=z.GetFilledPolysList(pcbnew.In1_Cu)
    for i in range(poly.OutlineCount()):
      if all(poly.Outline(i).PointInside(pcbnew.VECTOR2I(int(c.x+r*math.cos(a*math.pi/32)),int(c.y+r*math.sin(a*math.pi/32)))) and not any(poly.Hole(i,h).PointInside(pcbnew.VECTOR2I(int(c.x+r*math.cos(a*math.pi/32)),int(c.y+r*math.sin(a*math.pi/32)))) for h in range(poly.HoleCount(i))) for a in range(64)):
        isl.add((z.m_Uuid.AsString()[:8],i,round(poly.Outline(i).Area()/1e12,3)))
  res.append(dict(pos=(N(c.x),N(c.y)),net=v.GetNetname(),drill=N(v.GetDrillValue()),dia=N(2*r),in1_islands=sorted(isl)))
out['ep_vias']=res
# via-in-pad counts per footprint (new vs old)
def vip(b):
  vs=[t for t in b.GetTracks() if t.Type()==pcbnew.PCB_VIA_T]; d={}
  for f in b.GetFootprints():
    for p in f.Pads():
      n=sum(1 for v in vs if p.HitTest(v.GetPosition()))
      if n: d[f.GetReference()+'.'+p.GetNumber()]=n
  return d
a,b2=vip(new),vip(old); out['via_in_pad_new']=a; out['via_in_pad_diff']={k:(b2.get(k),a.get(k)) for k in set(a)|set(b2) if a.get(k)!=b2.get(k)}
# dogbones
for ref,pin,xy in [('U3','5',(131.95,96.64)),('U5','2',(105.95,95.15))]:
  v=[t for t in new.GetTracks() if t.Type()==pcbnew.PCB_VIA_T and abs(N(t.GetPosition().x)-xy[0])<0.01 and abs(N(t.GetPosition().y)-xy[1])<0.01]
  p=[q for q in fp(new,ref).Pads() if q.GetNumber()==pin][0]
  vv=v[0]; hole=vv.GetDrillValue()/2
  sh=p.GetEffectivePolygon(pcbnew.F_Cu)
  near=[]
  for q in fp(new,ref).Pads():
    dd=q.GetEffectivePolygon(pcbnew.F_Cu).SquaredDistance(vv.GetPosition())
    near.append((q.GetNumber(),q.GetNetname(),round(N(int(math.sqrt(dd)))-N(hole),4),round(N(int(math.sqrt(dd)))-N(vv.GetWidth(pcbnew.F_Cu)/2),4)))
  near.sort(key=lambda x:x[2])
  conn=[(t.GetLayerName(),N(t.GetWidth()),round(N(t.GetStart().x),3),round(N(t.GetStart().y),3),round(N(t.GetEnd().x),3),round(N(t.GetEnd().y),3)) for t in new.GetTracks() if t.Type()==pcbnew.PCB_TRACE_T and (t.GetStart()==vv.GetPosition() or t.GetEnd()==vv.GetPosition())]
  out['dog_'+ref]=dict(net=vv.GetNetname(),pad_net=p.GetNetname(),drill=N(vv.GetDrillValue()),dia=N(vv.GetWidth(pcbnew.F_Cu)),hole_in_any_pad=any(q.HitTest(vv.GetPosition()) for f in new.GetFootprints() for q in f.Pads()),nearest_pads_holeedge_annedge=near[:3],tracks=conn)
# different-net hole min
def holes(b):
  h=[(t.GetPosition(),t.GetDrillValue()/2,t.GetNetname(),'via') for t in b.GetTracks() if t.Type()==pcbnew.PCB_VIA_T]
  for f in b.GetFootprints():
    for p in f.Pads():
      if p.GetDrillSize().x>0: h.append((p.GetPosition(),min(p.GetDrillSize().x,p.GetDrillSize().y)/2,p.GetNetname(),f.GetReference()+'.'+p.GetNumber()))
  best=[]
  for x,y in itertools.combinations(h,2):
    if x[2]==y[2] and x[2]: continue
    g=math.hypot(x[0].x-y[0].x,x[0].y-y[0].y)-x[1]-y[1]
    best.append((N(int(g)),x[2],y[2],(N(x[0].x),N(x[0].y)),(N(y[0].x),N(y[0].y))))
  best.sort(); return best[:4]
out['hole_min_new']=holes(new); out['hole_min_old']=holes(old)[:1]
named=[t for t in new.GetTracks() if t.Type()==pcbnew.PCB_VIA_T and t.GetNetname().endswith(('EF_MODE','OV_SET')) and 79<N(t.GetPosition().x)<80.2 and 86.5<N(t.GetPosition().y)<87.8]
out['ef_ov']=[(v.GetNetname(),N(v.GetPosition().x),N(v.GetPosition().y),N(v.GetDrillValue())) for v in named]
if len(named)==2: out['ef_ov_gap']=N(int(math.hypot(named[0].GetPosition().x-named[1].GetPosition().x,named[0].GetPosition().y-named[1].GetPosition().y)))-N(named[0].GetDrillValue())/2-N(named[1].GetDrillValue())/2
out['counts']=dict(tracks=sum(1 for t in new.GetTracks() if t.Type()==pcbnew.PCB_TRACE_T),vias=sum(1 for t in new.GetTracks() if t.Type()==pcbnew.PCB_VIA_T),fps=len(new.GetFootprints()),zones=len(list(new.Zones())))
json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
