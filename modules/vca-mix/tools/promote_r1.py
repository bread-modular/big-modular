"""Copy the applied R1 candidate onto hardware/ (shared promote is
gated on status=accepted, which D14 blocks). Same content-hash model rebinding as
opt/kicad-tools automation.api.promote; refuses if any model token is unresolved."""
import hashlib, re, sys
from pathlib import Path
cand, target = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
bad = []
def fix(m):
    v = m.group(2)
    if not v.startswith('${KIPRJMOD}/'): return m.group(0)
    rel = v[len('${KIPRJMOD}/'):]
    if (target.parent / rel).is_file(): return m.group(0)
    src = cand.parent / rel; name = Path(rel).name
    keys = {p.parent.name for p in (target.parent / '_kicad_models').glob(f'*/{name}') if sha(p) == sha(src)}
    if len(keys) != 1: bad.append(v); return m.group(0)
    return m.group(1) + '${KIPRJMOD}/_kicad_models/' + keys.pop() + '/' + name + m.group(3)
out = re.sub(r'(\(model\s+")([^"]+)(")', fix, cand.read_text(encoding='utf-8-sig'))
if bad: sys.exit(f'unresolved models: {sorted(set(bad))}')
target.write_text(out, encoding='utf-8'); print('written', target, sha(target))
