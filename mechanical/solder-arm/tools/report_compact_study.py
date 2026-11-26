"""Summarize saved comparison runs; a failing load cannot be averaged away."""
import json
from pathlib import Path

ARM=Path(__file__).resolve().parents[1]
WORK=ARM/'research'/'frame-study'
OUT=ARM/'print'/'two-screw-base'/'compact-28'
MEASURES=('work_Nmm','max_motion_mm','tensile_hot_MPa','mises_hot_MPa',
          'layer_tensile_hot_MPa','tensile_peak_MPa','mises_peak_MPa')


def read(path): return json.loads(path.read_text())


def compare(name,walls,h,y,power):
    suffix=f'i0.35-p{power:g}.json'
    a,b=[read(WORK/f'{n}-h{h:g}-y{y:g}-w{w}-{suffix}')
         for n,w in [('stock',5),(name,walls)]]
    assert a['cases'].keys()==b['cases'].keys() and len(a['cases'])==8
    rows={c:{k:round(b['cases'][c][k]/a['cases'][c][k],5) for k in MEASURES} for c in a['cases']}
    return dict(grid_mm=h,layer_modulus_ratio=y,core_exponent=power,bricks=[a['bricks'],b['bricks']],
                worst={k:max(row[k] for row in rows.values()) for k in MEASURES}, ratios_to_full_base_by_case=rows)


def main():
    winner=[compare('short28',6,*args) for args in [(3,1,1),(2,1,1),(2,.5,2)]]
    assert max(max(r['worst'].values()) for r in winner)<1, 'compact did not pass'
    rej={}
    for n,w in [('lean8',5),('short28',5),('short36',6),('waist8-28',7)]:
        rs=[compare(n,w,h,1,1)['worst'] for h in (3,2)]
        assert max(max(r.values()) for r in rs)>1, ('reconsider candidate',n,w)
        rej[n+f'-w{w}']={'3mm':rs[0],'2mm':rs[1]}
    r=dict(scope='Linear frame-load comparison only. Ratios <= 1 are favourable. Not an ultimate strength, creep, or holding-force test.',
           plate_sha256=read(OUT/'slice.json')['sha256'],original_plate_sha256=read(OUT.parent/'slice.json')['sha256'],
           compact_vs_original=winner,rejected_worst_case_ratios=rej)
    (OUT/'frame-comparison.json').write_text(json.dumps(r,indent=2)+'\n')
    print('COMPARATIVE_SCREEN_PASS')


if __name__=='__main__': main()
