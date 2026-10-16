"""Project wire/hierarchy regression graph using the existing sexp reader.

Not a replacement for native KiCad netlisting/ERC. In particular, a geometric
crossing is connected only when a pin, endpoint or explicit junction is present.
Keeps physical paths separate from local-label equivalence for readability tests.
"""
from collections import defaultdict
import math
from pathlib import Path
from sexp import parse, nodes, one, walk


def pos(values):
    return tuple(round(float(v), 5) for v in values)


class Connectivity:
    def __init__(self, hardware):
        self.hardware = Path(hardware)
        self.sheets = {p.name: parse(p.read_text()) for p in self.hardware.glob('*.kicad_sch')}
        self.pins, self.refs, self.labels, self.ports, self.ncs = {}, {}, {}, {}, set()
        self.wires, points = [], set()
        self.port_types, self.sheet_pins = {}, {}
        root_name = 'big_modular.kicad_sch'
        root = self.sheets[root_name]
        children = nodes(root, 'sheet')
        assert len(children) == 7, 'Exactly seven authorized electrical subsheets required'
        files = {next(p[2] for p in nodes(ch, 'property') if p[1] == 'Sheetfile') for ch in children}
        assert files | {root_name} == set(self.sheets), 'Missing or orphan sheet files'
        assert not nodes(root, 'symbol'), 'Overview must not duplicate circuit components'
        for filename, sheet in self.sheets.items():
            if filename != root_name:assert not nodes(sheet, 'sheet'), 'Unexpected nested/repeated hierarchy'
            assert not nodes(sheet, 'global_label'), 'Power crosses sheets through explicit ports only'
            local = lambda coords: (filename, *pos(coords))
            libs = {s[1]: s for s in nodes(one(sheet, 'lib_symbols'), 'symbol')}
            for wire in nodes(sheet, 'wire'):
                a, b = [local(p[1:3]) for p in nodes(one(wire, 'pts'), 'xy')]
                assert a[1] == b[1] or a[2] == b[2], 'Non-orthogonal wire'
                self.wires.append((a, b));points.update([a, b])
            for label in nodes(sheet, 'label') + nodes(sheet, 'hierarchical_label'):
                point = local(one(label, 'at')[1:3])
                assert point not in self.labels or self.labels[point] == label[1]
                self.labels[point] = label[1];points.add(point)
                if label[0] == 'hierarchical_label':
                    key = (filename, label[1])
                    assert key not in self.ports, 'Duplicate port'
                    self.ports[key] = point
                    self.port_types[key] = one(label,'shape')[1]
            points.update(local(one(j, 'at')[1:3]) for j in nodes(sheet, 'junction'))
            self.ncs.update(local(one(n, 'at')[1:3]) for n in nodes(sheet, 'no_connect'))
            for s in nodes(sheet, 'symbol'):
                props = {p[1]: p[2] for p in nodes(s, 'property')}
                ref = props['Reference'];assert ref not in self.refs, ('Duplicate ref', ref)
                self.refs[ref] = (filename, s)
                at = one(s, 'at');x, y = map(float, at[1:3]);angle = math.radians(float(at[3]))
                co, si = round(math.cos(angle)), round(math.sin(angle))
                for pin in walk(libs[one(s, 'lib_id')[1]], 'pin'):
                    n = one(pin, 'number')[1];px, py = map(float, one(pin, 'at')[1:3])
                    dx,dy=px*co-py*si,-px*si-py*co
                    mirror=one(s,'mirror',['mirror',''])[1]
                    if mirror=='y':dx=-dx
                    if mirror=='x':dy=-dy
                    point = local([x+dx, y+dy])
                    self.pins[(ref, n)] = point;points.add(point)
        links = []
        for child in children:
            filename = next(p[2] for p in nodes(child, 'property') if p[1] == 'Sheetfile')
            names = {pin[1] for pin in nodes(child, 'pin')}
            assert names == {n for f, n in self.ports if f == filename}, ('Sheet port mismatch', filename)
            for pin in nodes(child, 'pin'):
                point = (root_name, *pos(one(pin, 'at')[1:3]));points.add(point)
                key=(filename,pin[1])
                assert pin[2]==self.port_types[key], ('Sheet port direction mismatch',key)
                self.sheet_pins[key]=point
                links.append((point, self.ports[key]))
        self.graph = {p: p for p in points}
        for a, b in self.wires:
            axis = 1 if a[2] == b[2] else 2
            other = 3-axis
            for p in points:
                if p[0] == a[0] and p[other] == a[other] and min(a[axis], b[axis]) <= p[axis] <= max(a[axis], b[axis]):
                    self.join(a, p)
        # Count/preserve all physical sheet-pin links independently of local labels.
        self.hierarchy_links = links
        for a, b in links:self.join(a, b)
        self.connected_labels = defaultdict(set)
        for p, name in self.labels.items():self.connected_labels[self.find(p)].add(name)
        assert all(len(names) == 1 for names in self.connected_labels.values()), ('Shorted nets', [n for n in self.connected_labels.values() if len(n)>1])

    def find(self, p):
        while self.graph[p] != p:
            self.graph[p] = self.graph[self.graph[p]];p = self.graph[p]
        return p

    def join(self, a, b):
        self.graph[self.find(a)] = self.find(b)

    def named_pins(self):
        result = {}
        for pin, p in self.pins.items():
            names = self.connected_labels[self.find(p)]
            if p in self.ncs:
                assert not names, ('NC pin connected', pin, names)
                result[pin] = None
            else:
                assert len(names) == 1, ('Unnamed or disconnected pin', pin, names)
                result[pin] = next(iter(names))
        return result

    def wire_connected(self, a, b):
        return self.find(self.pins[a]) == self.find(self.pins[b])
