import pcbnew,sys,math
b=pcbnew.LoadBoard(sys.argv[1]);mm=pcbnew.ToMM;V=pcbnew.VECTOR2I;F=pcbnew.FromMM
LN={pcbnew.F_Cu:'F',pcbnew.In1_Cu:'In1',pcbnew.In2_Cu:'In2',pcbnew.B_Cu:'B'}
fp={f.GetReference():f for f in b.GetFootprints()}
SW='/Direct 9V positive boost/PBOOST_SW'
PR=[n for n in set(p.GetNetname() for f in b.GetFootprints() for p in f.Pads()) if n.endswith('PRAW')][0]
print('PRAWnet',PR)
for n in (SW,PR):
  print('NET',n.split('/')[-1])
  for f in b.GetFootprints():
    for p in f.Pads():
      if p.GetNetname()==n: print('  pad %s.%s %.2f,%.2f'%(f.GetReference(),p.GetNumber(),mm(p.GetPosition().x),mm(p.GetPosition().y)))
  for t in b.GetTracks():
    if t.GetNetname()!=n: continue
    if t.GetClass()=='PCB_VIA': print('  via %.2f,%.2f d%.2f %s'%(mm(t.GetPosition().x),mm(t.GetPosition().y),mm(t.GetDrillValue()),t.m_Uuid.AsString()[:8]))
    else: print('  trk %s w%.2f (%.2f,%.2f)-(%.2f,%.2f) L%.2f %s'%(LN.get(t.GetLayer()),mm(t.GetWidth()),mm(t.GetStart().x),mm(t.GetStart().y),mm(t.GetEnd().x),mm(t.GetEnd().y),mm(t.GetLength()),t.m_Uuid.AsString()[:8]))
  for z in b.Zones():
    if z.GetNetname()==n:
      for l in z.GetLayerSet().CuStack():
        fpl=z.GetFilledPolysList(l);bb=fpl.BBox()
        print('  zone %s %s area%.1f n%d bbox(%.1f,%.1f)-(%.1f,%.1f)'%(z.m_Uuid.AsString()[:8],LN.get(l),fpl.Area()/1e12,fpl.OutlineCount(),mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom())))
# GND islands for key pads
def isl(l,pt):
  for z in b.Zones():
    if not z.GetNetname().endswith('GND') or not z.IsOnLayer(l): continue
    fpl=z.GetFilledPolysList(l)
    for i in range(fpl.OutlineCount()):
      s=fpl.Subset(i,i+1)
      if s.Contains(pt): return '%s#%d:%.1fmm2'%(z.m_Uuid.AsString()[:8],i,s.Area()/1e12)
  return None
prcaps=[(f.GetReference(),p) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()==PR and f.GetReference()[0]=='C']
print('PRAW caps',[r for r,_ in prcaps])
for r,pn in [('U14',n) for n in ('5','6','10','11','12','13','14','17')]+[(r,'2') for r,_ in prcaps]+[('C88','2'),('C84','2')]:
  p=[q for q in fp[r].Pads() if q.GetNumber()==pn][0];c=p.GetPosition()
  print('GNDisl %s.%s %s @%.2f,%.2f F=%s In1=%s'%(r,pn,p.GetNetname().split('/')[-1],mm(c.x),mm(c.y),isl(pcbnew.F_Cu,c),isl(pcbnew.In1_Cu,c)))
u=fp['U14'].GetPosition()
vs=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname().endswith('GND') and math.dist((mm(t.GetPosition().x),mm(t.GetPosition().y)),(mm(u.x),mm(u.y)))<4]
print('GND vias <4mm of U14:',[('%.2f,%.2f'%(mm(t.GetPosition().x),mm(t.GetPosition().y)),round(math.dist((mm(t.GetPosition().x),mm(t.GetPosition().y)),(mm(u.x),mm(u.y))),2),isl(pcbnew.F_Cu,t.GetPosition()) is not None) for t in vs])
