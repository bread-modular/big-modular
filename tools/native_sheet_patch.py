"""Schematic-only changed-top-level-node rewrite preserving all untouched bytes.

Reuses the project's reviewed quote-aware span walker. Not a PCB rebuild/sync.
"""
from sexp import parse, dump, one
from hro_merge_overlay import spans


def rewrite(original, tree):
    old=parse(original)
    if old==tree:return original
    def key(v):
        u=one(v,'uuid')
        return ('uuid',u[1]) if u else ('tag',v[0])
    oldnodes={key(v):v for v in old[1:] if isinstance(v,list)}
    newnodes={key(v):v for v in tree[1:] if isinstance(v,list)}
    assert len(oldnodes)==len(old)-1 and len(newnodes)==len(tree)-1, 'Unsupported duplicate top-level key'
    edits=[]
    for a,b,depth in spans(original):
        if depth!=1:continue
        v=parse(original[a:b]);k=key(v)
        if k not in newnodes:
            left=original.rfind('\n',0,a)+1
            right=original.find('\n',b)
            if right!=-1 and not original[left:a].strip() and not original[b:right].strip():a,b=left,right+1
            edits.append((a,b,''))
        elif v!=newnodes[k]:edits.append((a,b,dump(newnodes[k])))
    result=original
    for a,b,value in sorted(edits,reverse=True):result=result[:a]+value+result[b:]
    added=[v for v in tree[1:] if key(v) not in oldnodes]
    if added:
        end=result.rfind(')');result=result[:end]+''.join('\n\t'+dump(v) for v in added)+'\n'+result[end:]
    # Top-level KiCad node ordering is not connectivity/identity; key identity is.
    reread=parse(result)
    assert {key(v):v for v in reread[1:]}==newnodes
    return result
