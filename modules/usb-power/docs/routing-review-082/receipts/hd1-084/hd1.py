import sys,math,pcbnew
N=pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1]); o=pcbnew.LoadBoard(sys.argv[2])
def vias(x): return [t for t in x.GetTracks() if t.Type()==pcbnew.PCB_VIA_T]
print('tracks old/new',len(o.GetTracks()),len(b.GetTracks()),'vias',len(vias(o)),len(vias(b)))
for t in b.GetTracks():
  u=t.m_Uuid.AsString()
  if u.startswith(('8e4785b7','b1dbe53d')): print('STILL PRESENT',u)
  if u.startswith('80dd5e8d'): print('80dd5e8d',N(t.GetPosition().x),N(t.GetPosition().y),t.GetNetname(),b.GetLayerName(t.TopLayer()),b.GetLayerName(t.BottomLayer()),N(t.GetDrillValue()),N(t.GetWidth(pcbnew.F_Cu)))
for ref in ['C78']:
  for p in b.FindFootprintByReference(ref).Pads():
    poly=p.GetEffectivePolygon(pcbnew.F_Cu); best=[]
    for v in vias(b):
      d=math.sqrt(poly.SquaredDistance(v.GetPosition()))-v.GetDrillValue()/2
      best.append((round(N(int(d)),4),v.m_Uuid.AsString()[:8],p.HitTest(v.GetPosition(),v.GetDrillValue()//2)))
    best.sort(); print(ref+'.'+p.GetNumber(),p.GetNetname(),'nearest hole-edge',best[:2],'any_hit',any(x[2] for x in best))
def vip(x):
  vs=vias(x); return {f.GetReference()+'.'+p.GetNumber():sum(1 for v in vs if p.HitTest(v.GetPosition(),v.GetDrillValue()//2)) for f in x.GetFootprints() for p in f.Pads()}
a,c=vip(b),vip(o); print('via-in-pad diff vs081',{k:(c[k],a[k]) for k in a if a[k]!=c[k]})
