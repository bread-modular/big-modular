"""Small S-expression reader/writer for deterministic KiCad source generation."""
import re, json
class Atom(str): pass

def parse(text):
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+', text)
    stack=[]; result=None
    for t in tokens:
        if t=='(':
            n=[]
            if stack: stack[-1].append(n)
            stack.append(n)
        elif t==')': result=stack.pop()
        else: stack[-1].append(json.loads(t) if t.startswith('"') else Atom(t))
    return result

def dump(x):
    if isinstance(x,list): return '('+' '.join(map(dump,x))+')'
    if isinstance(x,Atom): return str(x)
    if isinstance(x,str): return json.dumps(x,ensure_ascii=False)
    return str(x)

def nodes(x,key): return [c for c in x if isinstance(c,list) and c and c[0]==key]
def one(x,key,default=None): return next(iter(nodes(x,key)),default)
def walk(x,key):
    if isinstance(x,list):
        if x and x[0]==key: yield x
        for c in x: yield from walk(c,key)

def atom(s): return Atom(str(s))
