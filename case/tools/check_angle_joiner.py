"""Independent STL/3MF topology, pose and current-output hash checks (stdlib only).

python3 -B case/tools/check_angle_joiner.py
Does not build CAD. Writes print/side panels/angle-joiner/mesh-verification.json only after PASS.
"""
from collections import Counter, defaultdict, deque
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

CASE = Path(__file__).resolve().parents[1]
OUT = CASE/'print'/'side panels'/'angle-joiner'


def canonical(t):
    return min(t, t[1:]+t[:1], t[2:]+t[:2])


def check_mesh(name, out=None):
    """Check one exported mesh pair; optional folder permits other case variants."""
    path = (OUT if out is None else out)/name
    data = path.with_suffix('.stl').read_bytes()
    count, = struct.unpack_from('<I', data, 80)
    assert len(data) == 84+50*count, 'binary STL length'
    ids, vertices, faces = {}, [], []
    for i in range(count):
        record = struct.unpack_from('<12fH',data,84+50*i)
        face = []
        for j in range(3):
            v = tuple(round(x,5) for x in record[3+3*j:6+3*j])
            assert all(math.isfinite(x) for x in v), 'nonfinite vertex'
            if v not in ids:
                ids[v] = len(vertices)
                vertices.append(v)
            face.append(ids[v])
        assert len(set(face)) == 3, 'degenerate facet'
        faces.append(tuple(face))
    assert len(set(map(canonical,faces))) == len(faces), 'duplicate facet'
    edges, directed, neighbors = Counter(), Counter(), defaultdict(set)
    for a,b,c in faces:
        for u,v in ((a,b),(b,c),(c,a)):
            edges[tuple(sorted((u,v)))] += 1
            directed[u,v] += 1
            neighbors[u].add(v)
            neighbors[v].add(u)
    assert set(edges.values()) == {2}, 'nonmanifold edge'
    assert all(directed[u,v] == directed[v,u] == 1 for u,v in edges), 'inconsistent winding'
    seen, queue = {0}, deque([0])
    while queue:
        for v in neighbors[queue.popleft()]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    assert len(seen) == len(vertices), 'more than one component'
    lo = [min(v[k] for v in vertices) for k in range(3)]
    hi = [max(v[k] for v in vertices) for k in range(3)]
    assert abs(lo[2]) < 1e-5, 'not on print bed'
    assert all(-1e-5 <= lo[i] < 0.006 for i in (0,1)), 'XY tessellation origin tolerance'
    assert all(hi[i]-lo[i] < 252 for i in range(3)), 'bed fit'
    volume = 0
    for f in faces:
        a,b,c = [vertices[i] for i in f]
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    assert volume > 0, 'inward-oriented solid'

    # 3MF XML is decimal; map to binary STL within 1 micron, bijectively.
    cell = 0.001
    grid = defaultdict(list)
    def key(v):
        return tuple(math.floor(x/cell) for x in v)
    for i,v in enumerate(vertices):
        grid[key(v)].append(i)
    with zipfile.ZipFile(path.with_suffix('.3mf')) as z:
        models = [n for n in z.namelist() if n.endswith('.model')]
        assert len(models) == 1, 'multiple 3MF models'
        root = ET.fromstring(z.read(models[0]))
        ns = {'m':root.tag.split('}')[0][1:]}
        assert root.attrib.get('unit','millimeter') == 'millimeter'
        objects = root.findall('./m:resources/m:object', ns)
        items = root.findall('./m:build/m:item', ns)
        assert len(objects) == len(items) == 1, 'multiple meshes/placements'
        if 'transform' in items[0].attrib:
            transform = tuple(float(x) for x in items[0].attrib['transform'].split())
            assert transform == (1,0,0,0,1,0,0,0,1,0,0,0), '3MF instance transform'
        mapped, worst = [], 0
        for node in root.findall('.//m:vertex',ns):
            v = tuple(float(node.attrib[k]) for k in ('x','y','z'))
            k = key(v)
            candidates = []
            for ds in itertools.product((-1,0,1),repeat=3):
                for i in grid[tuple(k[j]+ds[j] for j in range(3))]:
                    distance = sum((a-b)**2 for a,b in zip(v,vertices[i]))
                    candidates.append((distance,i))
            assert candidates, '3MF vertex has no STL counterpart'
            distance, i = min(candidates)
            assert distance < 0.001**2, 'more than 1 micron STL/3MF difference'
            worst = max(worst, math.sqrt(distance))
            mapped.append(i)
        assert len(mapped) == len(set(mapped)) == len(vertices), 'nonbijective vertex mapping'
        mf_faces = [tuple(mapped[int(t.attrib[k])] for k in ('v1','v2','v3'))
                    for t in root.findall('.//m:triangle',ns)]
        assert Counter(map(canonical,faces)) == Counter(map(canonical,mf_faces)), 'oriented topology differs'
    return {'closed_oriented_connected':True, 'vertices':len(vertices), 'triangles':len(faces),
            'volume_mm3':round(volume,3), 'mesh_bounds_mm':[round(hi[i]-lo[i],5) for i in range(3)],
            'bed_z_min_mm':lo[2], 'STL_3MF_topology_identical':True,
            'STL_3MF_max_vertex_difference_mm':round(worst,7)}


def main():
    (OUT/'mesh-verification.json').unlink(missing_ok=True)
    report = json.loads((OUT/'verification.json').read_text())
    assert report['status'] == 'PASS'
    for path, expected in report['export_sha256'].items():
        assert hashlib.sha256((CASE/path).read_bytes()).hexdigest() == expected, path+' stale output'
    results = {name:check_mesh(name) for name in report['print']}
    text = json.dumps({'status':'PASS','output_hashes_verified':len(report['export_sha256']),
                       'meshes':results}, indent=2)+'\n'
    (OUT/'mesh-verification.json').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
