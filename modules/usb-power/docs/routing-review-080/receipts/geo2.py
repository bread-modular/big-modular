import pcbnew,sys,math
b=pcbnew.LoadBoard(sys.argv[1]);mm=pcbnew.ToMM;F=pcbnew.FromMM;V=pcbnew.VECTOR2I
LN={pcbnew.F_Cu:'F',pcbnew.In1_Cu:'In1',pcbnew.In2_Cu:'In2',pcbnew.B_Cu:'B'}
fp={f.GetReference():f for f in b.GetFootprints()}
def pad(r,n): return [p for p in fp[r].Pads() if p.GetNumber()==n][0]
def c(v): return (mm(v.x),mm(v.y))
def s(n): return n.split('/')[-1]
G=lambda n:n.endswith('/GND')
def isl(l,x,y):
  pt=V(F(x),F(y))
  for z in b.Zones():
    if not G(z.GetNetname()) or not z.IsOnLayer(l): continue
    fl=z.GetFilledPolysList(l)
    for i in range(fl.OutlineCount()):
      ss=fl.Subset(i,i+1)
      if ss.Contains(pt): return '%s#%d/%.0f'%(z.m_Uuid.AsString()[:8],i,ss.Area()/1e12)
  return None
def viaconn(v,l):
  x,y=c(v.GetPosition());r=mm(v.GetWidth(pcbnew.F_Cu))/2
  m=isl(l,x,y)
  if m: return 'solid:'+m
  h=[q for q in (isl(l,x+(r+d)*math.cos(a/16*6.2832),y+(r+d)*math.sin(a/16*6.2832)) for a in range(16) for d in (0.03,0.12)) if q]
  return ('spokes%d:'%len(h)+h[0]) if h else 'NONE'
print('ZONES')
for z in b.Zones():
  for l in z.GetLayerSet().CuStack():
    fl=z.GetFilledPolysList(l);print(' ',s(z.GetNetname()),LN.get(l),round(fl.Area()/1e12,1),fl.OutlineCount(),z.m_Uuid.AsString()[:8])
vias=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
print('EP VIA CONNECTIVITY')
for r,n in (('U12','21'),('U13','21'),('U14','17')):
  p=pad(r,n);pc=c(p.GetPosition())
  inp=[v for v in vias if p.HitTest(v.GetPosition())]
  ext=[v for v in vias if not p.HitTest(v.GetPosition()) and G(v.GetNetname()) and math.dist(c(v.GetPosition()),pc)<3.5]
  for tag,L in (('inpad',inp),('ext<3.5',ext)):
    res={}
    for v in L:
      k=(round(mm(v.GetDrillValue()),2),round(mm(v.GetWidth(pcbnew.F_Cu)),2),'F='+viaconn(v,pcbnew.F_Cu),'In1='+viaconn(v,pcbnew.In1_Cu),'B='+viaconn(v,pcbnew.B_Cu).split(':')[0])
      res[k]=res.get(k,0)+1
    print(' ',r,n,s(p.GetNetname()),'%.2f,%.2f'%pc,tag,len(L),res)
print('U14-AREA GND tracks/vias')
for t in b.GetTracks():
  if not G(t.GetNetname()): continue
  if t.GetClass()=='PCB_VIA':
    x,y=c(t.GetPosition())
    if 124<x<142 and 72<y<90: print('  via %.2f,%.2f In1=%s'%(x,y,viaconn(t,pcbnew.In1_Cu)))
    continue
  a,e=c(t.GetStart()),c(t.GetEnd())
  if all(124<q[0]<142 and 72<q[1]<90 for q in (a,e)): print('  %s w%.2f (%.2f,%.2f)-(%.2f,%.2f)'%(LN.get(t.GetLayer()),mm(t.GetWidth()),a[0],a[1],e[0],e[1]))
A=c(pad('C78','2').GetPosition());B=c(pad('U14','13').GetPosition())
out=['%.2f,%.2f'%(A[0]+(B[0]-A[0])*k/40,A[1]+(B[1]-A[1])*k/40) for k in range(41) if not isl(pcbnew.In1_Cu,A[0]+(B[0]-A[0])*k/40,A[1]+(B[1]-A[1])*k/40)]
print('In1 line C78.2->U14.13 samples outside GND fill',len(out),out)
print('U3 REGION')
u=c(fp['U3'].GetPosition())
for f in b.GetFootprints():
  q=c(f.GetPosition())
  if f.GetReference()[:1] in 'CLUR' and math.dist(q,u)<16: print(' ',f.GetReference(),f.GetValue(),'d%.1f'%math.dist(q,u),[(p.GetNumber(),s(p.GetNetname()),'%.2f,%.2f'%c(p.GetPosition())) for p in f.Pads()])
for t in b.GetTracks():
  n=s(t.GetNetname())
  if n not in ('NRAW','VPROT','NINV_SW','GND'): continue
  if t.GetClass()=='PCB_VIA':
    x,y=c(t.GetPosition())
    if math.dist((x,y),u)<9: print('  via %s %.2f,%.2f In1=%s'%(n,x,y,viaconn(t,pcbnew.In1_Cu)))
    continue
  a,e=c(t.GetStart()),c(t.GetEnd())
  if math.dist(a,u)<9 or math.dist(e,u)<9: print('  trk %s %s w%.2f (%.2f,%.2f)-(%.2f,%.2f)'%(n,LN.get(t.GetLayer()),mm(t.GetWidth()),a[0],a[1],e[0],e[1]))
