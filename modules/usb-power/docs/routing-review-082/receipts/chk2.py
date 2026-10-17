import sys, json, math, pcbnew
N=pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1]); o=pcbnew.LoadBoard(sys.argv[2])
vs=[t for t in b.GetTracks() if t.Type()==pcbnew.PCB_VIA_T]
out={}
for ref,num in [('C78','2'),('U14','')]:
  for p in b.FindFootprintByReference(ref).Pads():
    if p.GetNumber()!=num: continue
    for v in vs:
      if p.HitTest(v.GetPosition()):
        c=v.GetPosition()
        out.setdefault(ref+'.'+num,[]).append(dict(via=(N(c.x),N(c.y)),net=v.GetNetname(),uuid=v.m_Uuid.AsString()[:8],drill=N(v.GetDrillValue()),dia=N(v.GetWidth(pcbnew.F_Cu)),pad=(N(p.GetPosition().x),N(p.GetPosition().y),N(p.GetSize().x),N(p.GetSize().y)),pad_layers=[b.GetLayerName(l) for l in p.GetLayerSet().Seq()],pad_net=p.GetNetname(),in_old=any(t.Type()==pcbnew.PCB_VIA_T and t.GetPosition()==c for t in o.GetTracks()),tented=(v.GetFrontTentingMode() if hasattr(v,'GetFrontTentingMode') else None)))
# U5.2 mask opening vs hole
u5=[p for p in b.FindFootprintByReference('U5').Pads() if p.GetNumber()=='2'][0]
v=[t for t in vs if abs(N(t.GetPosition().x)-105.95)<.01 and abs(N(t.GetPosition().y)-95.15)<.01][0]
exp=u5.GetSolderMaskExpansion(pcbnew.F_Mask) if hasattr(u5,'GetSolderMaskExpansion') else None
d=math.sqrt(u5.GetEffectivePolygon(pcbnew.F_Cu).SquaredDistance(v.GetPosition()))
out['U5.2']=dict(pad=(N(u5.GetPosition().x),N(u5.GetPosition().y),N(u5.GetSize().x),N(u5.GetSize().y)),mask_exp=N(exp) if exp is not None else None,hole_edge_to_pad_cu=round(N(int(d))-N(v.GetDrillValue())/2,4),hole_edge_to_mask_opening=(round(N(int(d))-N(v.GetDrillValue())/2-N(exp),4) if exp is not None else None),board_mask_margin=N(b.GetDesignSettings().m_SolderMaskExpansion),board_min_web=N(b.GetDesignSettings().m_SolderMaskMinWidth))
# loop copper widths between U14 SW/GND pins and D29/C78
for t in b.GetTracks():
  if t.Type()!=pcbnew.PCB_TRACE_T: continue
  s,e=t.GetStart(),t.GetEnd(); xs=[N(s.x),N(e.x)]; ys=[N(s.y),N(e.y)]
  if min(xs)>=127.5 and max(xs)<=134.5 and min(ys)>=77 and max(ys)<=84.5 and t.GetNetname().endswith(('PBOOST_SW','PRAW','/GND')):
    out.setdefault('loop_tracks',[]).append((t.GetNetname().split('/')[-1],t.GetLayerName(),N(t.GetWidth()),round(xs[0],3),round(ys[0],3),round(xs[1],3),round(ys[1],3)))
out['loop_tracks'].sort()
z=[(zz.GetNetname(),[b.GetLayerName(l) for l in zz.GetLayerSet().Seq()],zz.GetIsRuleArea()) for zz in b.Zones()]
out['zones']=z
json.dump(out,open(sys.argv[3],'w'),indent=1)
