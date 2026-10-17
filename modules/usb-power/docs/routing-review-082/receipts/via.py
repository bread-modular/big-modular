import sys,math,pcbnew
N=pcbnew.ToMM;F=pcbnew.FromMM
b=pcbnew.LoadBoard(sys.argv[1]); ds=b.GetDesignSettings()
print('min_clear',N(ds.m_MinClearance),'hole2hole',N(ds.m_HoleToHoleMin),'holeclear',N(ds.m_HoleClearance),'tentF',getattr(ds,'m_TentViasFront',None),'tentB',getattr(ds,'m_TentViasBack',None))
v=[t for t in b.GetTracks() if t.Type()==pcbnew.PCB_VIA_T and t.m_Uuid.AsString().startswith('8e4785b7')][0]
print('via layers',v.TopLayer(),v.BottomLayer(),'conns',[(t.GetLayerName(),N(t.GetWidth()),N(t.GetStart().x),N(t.GetStart().y),N(t.GetEnd().x),N(t.GetEnd().y)) for t in b.GetTracks() if t.Type()==pcbnew.PCB_TRACE_T and v.GetPosition() in (t.GetStart(),t.GetEnd())])
p=[q for q in b.FindFootprintByReference('C78').Pads() if q.GetNumber()=='2'][0]
print('C78.2 hole-edge inside pad by',round(N(int(math.sqrt(0)))+0,3),'pad bbox y',N(p.GetBoundingBox().GetBottom()),'hole ymax',N(v.GetPosition().y)+0.15)
# feasibility of moving via to candidate point
for cx,cy in [(131.65,81.8),(131.65,82.2)]:
  c=pcbnew.VECTOR2I(F(cx),F(cy)); r=F(0.325); worst=[]
  for L in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]:
    for t in b.GetTracks():
      if t.GetNetname()=='/GND' or not t.IsOnLayer(L) or t.m_Uuid==v.m_Uuid: continue
      sh=t.GetEffectiveShape(L); d=math.sqrt(sh.SquaredDistance(c)) if False else None
      if t.Type()==pcbnew.PCB_TRACE_T:
        s,e=t.GetStart(),t.GetEnd(); dx,dy=e.x-s.x,e.y-s.y; L2=dx*dx+dy*dy or 1; u=max(0,min(1,((c.x-s.x)*dx+(c.y-s.y)*dy)/L2)); d=math.hypot(s.x+u*dx-c.x,s.y+u*dy-c.y)-t.GetWidth()/2
      else: d=math.hypot(t.GetPosition().x-c.x,t.GetPosition().y-c.y)-t.GetWidth(L)/2
      worst.append((round(N(int(d-r)),3),b.GetLayerName(L),t.GetNetname().split('/')[-1]))
    for f in b.GetFootprints():
      for q in f.Pads():
        if q.GetNetname()=='/GND' or not q.IsOnLayer(L) or not q.GetNetname(): continue
        d=math.sqrt(q.GetEffectivePolygon(L).SquaredDistance(c))-r
        worst.append((round(N(int(d)),3),b.GetLayerName(L),f.GetReference()+'.'+q.GetNumber()))
  worst.sort(); inpad=[f.GetReference()+'.'+q.GetNumber() for f in b.GetFootprints() for q in f.Pads() if q.HitTest(c,F(0.15))]
  print('candidate',cx,cy,'nearest foreign',worst[:3],'hole hits pads',inpad)
