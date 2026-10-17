#!/usr/bin/env python3
"""Read-only collision screen for explicit common operations, not a router.
No coordinates are generated or modified. Native DRC remains authoritative.
"""
import argparse,json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'opt/kicad-tools/automation'))
import _worker as w

def assess(board,doc):
    b=w.p.LoadBoard(str(board));result=w.perform(b,doc);created=set(result['created']);items=w.index(b)[0];pairs={}
    obstacles=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
    for key in sorted(created):
        t=items[key]
        if not isinstance(t,w.p.PCB_TRACK):continue
        for other in obstacles:
            uid=w.uid(other)
            if uid==key or t.GetNetname()==other.GetNetname():continue
            for layer in (w.p.F_Cu,w.p.B_Cu,w.p.In1_Cu,w.p.In2_Cu):
                if t.IsOnLayer(layer) and other.IsOnLayer(layer) and t.GetEffectiveShape(layer).Collide(other.GetEffectiveShape(layer),200000):
                    pair=tuple(sorted([key,uid]))
                    pairs[pair]={'new_uuid':key,'new_net':t.GetNetname(),'other_uuid':uid,'other_kind':w.kind(other),'other_ref':other.GetParentFootprint().GetReference() if isinstance(other,w.p.PAD) else None,'other_pin':other.GetNumber() if isinstance(other,w.p.PAD) else None,'other_net':other.GetNetname(),'other_is_new':uid in created,'other_at':w.xy(other.GetPosition())}
                    break
    return list(pairs.values())

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--board',required=True);ap.add_argument('--ops',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    out=assess(a.board,json.loads(Path(a.ops).read_text()))
    with Path(a.output).open('x') as f:json.dump(out,f,indent=2);f.write('\n')
    print('pairs',len(out),dict(Counter((x['other_kind'],x['other_is_new']) for x in out)))
    for x in out:
        if x['other_kind']=='pad' or x['other_is_new']: print(x['new_uuid'],x['new_net'],'->',x['other_ref'],x['other_pin'],x['other_net'],x['other_uuid'])
    seen=set()
    print('Existing copper obstacles:')
    for x in out:
        if x['other_kind'] in ('track','via') and not x['other_is_new'] and x['other_uuid'] not in seen:
            seen.add(x['other_uuid']);print(x['other_uuid'],x['other_kind'],x['other_net'],x['other_at'])
