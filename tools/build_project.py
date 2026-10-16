#!/usr/bin/env python3
"""Generate a review-only KiCad engineering prototype. Never creates copper routes/zones."""
from pathlib import Path
import sys, json, uuid, copy, csv, math, shutil, argparse
sys.path.insert(0,str(Path(__file__).parent))
from sexp import parse,dump,nodes,one,walk,atom
from interface_contract import RESERVED_LED_REFS, validate_reference
ROOT=Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--schematic-only', action='store_true', help='Render a NEW schematic candidate only; create candidate schematic, libraries, BOM and pin audit; never regenerate boards.')
parser.add_argument('--output', type=Path, help='Required NEW directory for --schematic-only; copies existing project/library context.')
args = parser.parse_args()
if not args.schematic_only:
    parser.error('A4: legacy full regeneration is disabled; use --schematic-only --output NEW, or tools/build_stack.py --output NEW for mechanical candidates')
if args.schematic_only != bool(args.output):
    parser.error('--schematic-only and --output must be used together')
HW = args.output.resolve() if args.schematic_only else ROOT/'hardware'
if args.schematic_only:
    HW.mkdir(parents=True, exist_ok=False)
else:
    HW.mkdir(exist_ok=True)
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL,'big-modular/revA/'+s))
def q(s): return json.dumps(str(s))
LIB={}; CACHE={}
PINNED = ({s[1]: s for s in nodes(parse((ROOT/'hardware/BigModular.kicad_sym').read_text()), 'symbol')}
          if args.schematic_only else {})
def stock(lib,name):
    kind = lib+'_'+name
    if kind in PINNED:
        LIB[kind] = copy.deepcopy(PINNED[kind])
        return kind
    if lib not in CACHE:
        CACHE[lib]={s[1]:s for s in nodes(parse(Path('/usr/share/kicad/symbols',lib+'.kicad_sym').read_text()),'symbol')}
    def resolve(n):
        s=copy.deepcopy(CACHE[lib][n]); parent=one(s,'extends')
        if parent:
            base=resolve(parent[1]); props={p[1]:p for p in nodes(base,'property')}
            props.update({p[1]:p for p in nodes(s,'property')})
            s=[s[0],s[1]]+[x for x in base[2:] if not(isinstance(x,list) and x[0]=='property')]+list(props.values())
        return s
    s=resolve(name); old=s[1]; new=lib+'_'+name; s[1]=new
    for sub in nodes(s,'symbol'):
        # Inheritance geometry uses its parent's name; only unit suffix is significant.
        suffix='_'.join(sub[1].split('_')[-2:]); sub[1]=new+'_'+suffix
    LIB[new]=s; return new

def ic(name,pins,url):
    # (number, pin name, electrical type, side). One real pin per entry, including exposed pad.
    left=[p for p in pins if p[3]=='L']; right=[p for p in pins if p[3]=='R']; n=max(len(left),len(right))
    h=(n+1)*5.08
    parts=[f'(symbol {q(name)} (pin_names (offset 0.7)) (in_bom yes) (on_board yes)',
      '(property "Reference" "U" (at 0 3 0) (effects (font (size 1.27 1.27))))',
      f'(property "Value" {q(name)} (at 0 0 0) (effects (font (size 1.27 1.27))))',
      f'(property "Datasheet" {q(url)} (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
      f'(symbol {q(name+"_0_1")} (rectangle (start -10.16 {h/2}) (end 10.16 {-h/2}) (stroke (width 0.254) (type default)) (fill (type background))))',
      f'(symbol {q(name+"_1_1")}']
    for side,pp in [('L',left),('R',right)]:
        for j,(num,label,typ,_) in enumerate(pp):
            x=-15.24 if side=='L' else 15.24; y=(n-1)*2.54-j*5.08; a=0 if side=='L' else 180
            parts.append(f'(pin {typ} line (at {x} {y} {a}) (length 5.08) (name {q(label)} (effects (font (size 1 1)))) (number {q(num)} (effects (font (size 1 1)))))')
    parts+=['))']; LIB[name]=parse(''.join(parts)); return name

from electrical_design import populate
SHEETS, BOM, CONNS = populate(stock, ic, LIB, ROOT)
used={d['kind'] for sh in SHEETS.values() for d in sh['parts']}
LIB={k:v for k,v in LIB.items() if k in used}
from render_schematic import render
render(HW, SHEETS, LIB, uid)
# Libraries and inventory are emitted ONLY into the new review candidate.
(HW/'BigModular.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+ '\n'.join(dump(v) for _,v in sorted(LIB.items()))+'\n)\n')
for name in ['sym-lib-table','fp-lib-table','big_modular.kicad_pro']:
    shutil.copyfile(ROOT/'hardware'/name, HW/name)
shutil.copytree(ROOT/'hardware/BigModular.pretty', HW/'BigModular.pretty')
# Pin every selected footprint into the project library. No board placement/sync.
for row in BOM:
    fp=row['Footprint']
    if not fp or fp.startswith('BigModular:'): continue
    library,name=fp.split(':',1)
    source=Path('/usr/share/kicad/footprints')/(library+'.pretty')/(name+'.kicad_mod')
    if not source.exists(): raise FileNotFoundError(source)
    target=HW/'BigModular.pretty'/(name+'.kicad_mod')
    if not target.exists(): shutil.copyfile(source,target)
for row in BOM:
    if row['Footprint']:row['Footprint']='BigModular:'+row['Footprint'].split(':')[-1]
# Native symbols already use project-local IDs; fields and inventory agree.
with (HW/'BOM.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(BOM[0]),lineterminator='\n');writer.writeheader();writer.writerows(BOM)
(HW/'pin-net-audit.json').write_text(json.dumps(CONNS,indent=2)+'\n')
print('Created',len(BOM),'components in',len(SHEETS),'functional sheets; source boards untouched:',HW)

# Drop unused native symbol definitions; footprint alternatives used by mechanical
# tooling remain, but retired electrical-only support libraries are not emitted.
