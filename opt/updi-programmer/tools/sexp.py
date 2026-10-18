"""Minimal KiCad s-expression reader/writer (stdlib only)."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


class Sym(str):
    """Unquoted atom (keywords, numbers, yes/no)."""


def parse(text):
    stack, cur, pos = [], [], 0
    while True:
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        lp, rp, qs, atom = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done, cur = cur, stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(re.sub(r'\\(.)', r'\1', qs))
        else:
            cur.append(Sym(atom))
    assert not stack and len(cur) == 1, 'unbalanced s-expression'
    return cur[0]


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(node, indent=0):
    if not isinstance(node, list):
        if isinstance(node, Sym):
            return str(node)
        if isinstance(node, bool):
            return 'yes' if node else 'no'
        if isinstance(node, (int, float)):
            return fmt(node)
        return q(node)
    flat = all(not isinstance(x, list) for x in node)
    if flat:
        return '(' + ' '.join(dump(x) for x in node) + ')'
    pad = '\t' * (indent + 1)
    head = [dump(node[0])] if node else []
    parts, i = head, 1
    while i < len(node) and not isinstance(node[i], list):
        parts.append(dump(node[i]))
        i += 1
    out = '(' + ' '.join(parts)
    for x in node[i:]:
        out += '\n' + pad + dump(x, indent + 1)
    return out + '\n' + '\t' * indent + ')'


def fmt(v):
    if isinstance(v, int):
        return str(v)
    s = ('%.4f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def nodes(tree, name):
    return [x for x in tree if isinstance(x, list) and x and x[0] == name]


def one(tree, name):
    found = nodes(tree, name)
    return found[0] if found else None
