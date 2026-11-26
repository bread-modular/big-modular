"""Print plates for the soldering arm: one 3MF per plate with every copy of its parts laid out
on the bed, made from the per-part 3MF files of build_solder_arm.py (plain Python, no FreeCAD).

Run by tools/build_solder_arm.sh after the CAD build:
  python3 -B mechanical/solder-arm/tools/build_plates.py

The plates are geometry only (no printer, process or filament settings). Each part is one
object in the file and each copy a build item of it, in the part's print pose.
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ARM = Path(__file__).resolve().parents[1]
PRINT = ARM/'print'
OUT = PRINT/'plates'

BED = 256.0           # Bambu Lab P2S
MARGIN = 6.0          # bed edge to the nearest part
GAP = 8.0             # between parts

# plate -> rows (front to back) of parts (left to right); the order is the print order
PLATES = {
    'plate-1-thread-test': [['joint-bolt', 'joint-knob']],
    'plate-2-screws-and-knobs': [['joint-bolt', 'joint-bolt', 'joint-knob', 'joint-knob'],
                                 ['jaw-thumbscrew', 'jaw-thumbscrew']],
    'plate-3-jaws': [['jaw-left', 'jaw-right']],
    'plate-4-swivel-bracket': [['swivel-bracket']],
    'plate-5-link-and-rail': [['arm-link'], ['head-rail']],
}

TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def part_mesh(name):
    """The <mesh> block of a part file, with its bounding box and facet count."""
    with zipfile.ZipFile(PRINT/f'{name}.3mf') as archive:
        text = archive.read('3D/3dmodel.model').decode()
    assert text.count('<object ') == 1 and 'transform="1 0 0 0 1 0 0 0 1 0 0 0"' in text, name
    mesh = text[text.index('<mesh>'):text.index('</mesh>') + len('</mesh>')]
    points = [tuple(map(float, p)) for p in re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', mesh)]
    lo, hi = ([f(p[i] for p in points) for i in range(3)] for f in (min, max))
    # a faceted round part stops a few um short of its CAD bounding box
    assert all(abs(v) < 0.05 for v in lo), (name, 'not at the origin', lo)
    return mesh, hi, mesh.count('<triangle ')


def build_plate(plate, rows, parts):
    names = sorted({n for row in rows for n in row})
    ids = {n: i for i, n in enumerate(names, 1)}
    widths = [sum(parts[n][1][0] for n in row) + GAP*(len(row) - 1) for row in rows]
    depths = [max(parts[n][1][1] for n in row) for row in rows]
    span = [max(widths), sum(depths) + GAP*(len(rows) - 1)]
    assert max(span) <= BED - 2*MARGIN, (plate, 'does not fit the bed', span)
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
             ' <metadata name="Application">big-modular mechanical/solder-arm/tools/build_plates.py</metadata>',
             f' <metadata name="Title">{plate}</metadata>',
             ' <resources>']
    for n in names:
        model += [f'  <object id="{ids[n]}" name="{n}" type="model">', '   ' + parts[n][0], '  </object>']
    model += [' </resources>', ' <build>']
    placed = []
    y = (BED - span[1])/2
    for row, width, depth in zip(rows, widths, depths):
        x = (BED - width)/2
        for n in row:
            sx, sy, sz = parts[n][1]
            px, py = round(x, 3), round(y + (depth - sy)/2, 3)
            model.append(f'  <item objectid="{ids[n]}" transform="1 0 0 0 1 0 0 0 1 {px:g} {py:g} 0"/>')
            placed.append({'part': n, 'bed_xy_mm': [px, py], 'size_mm': [round(sx, 2), round(sy, 2), round(sz, 2)]})
            x += sx + GAP
        y += depth + GAP
    model += [' </build>', '</model>']
    path = OUT/f'{plate}.3mf'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, text in (('[Content_Types].xml', TYPES), ('_rels/.rels', RELS), ('3D/3dmodel.model', '\n'.join(model) + '\n')):
            # fixed date: a rebuild writes the same bytes
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text)
    # read back: every copy on the bed and clear of the others
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        back = archive.read('3D/3dmodel.model').decode()
    assert back.count('<item ') == len(placed) and back.count('<object ') == len(names), plate
    assert back.count('<triangle ') == sum(parts[n][2] for n in names), plate
    boxes = [(p['bed_xy_mm'][0], p['bed_xy_mm'][1], p['bed_xy_mm'][0] + p['size_mm'][0], p['bed_xy_mm'][1] + p['size_mm'][1]) for p in placed]
    for i, a in enumerate(boxes):
        assert a[0] >= MARGIN - 1e-6 and a[1] >= MARGIN - 1e-6 and a[2] <= BED - MARGIN + 1e-6 and a[3] <= BED - MARGIN + 1e-6, (plate, placed[i])
        for b in boxes[i + 1:]:
            assert a[2] + GAP <= b[0] + 0.01 or b[2] + GAP <= a[0] + 0.01 or a[3] + GAP <= b[1] + 0.01 or b[3] + GAP <= a[1] + 0.01, (plate, a, b)
    return {'pieces': len(placed), 'footprint_mm': [round(v, 2) for v in span],
            'height_mm': max(p['size_mm'][2] for p in placed), 'items': placed,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    report = json.loads((PRINT/'verification.json').read_text())
    assert report['status'] == 'PASS'
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob('*'):
        old.unlink()
    parts = {n: part_mesh(n) for n in report['print']}
    plates = {plate: build_plate(plate, rows, parts) for plate, rows in PLATES.items()}
    # the plates hold exactly the copies the build asks for
    for n, info in report['print'].items():
        got = sum(1 for p in plates.values() for item in p['items'] if item['part'] == n)
        assert got == info['copies'], (n, got, info['copies'])
        size = next(item['size_mm'] for p in plates.values() for item in p['items'] if item['part'] == n)
        assert all(abs(a - b) < 0.02 for a, b in zip(size, info['print_bounds_mm'])), (n, size, info['print_bounds_mm'])
    out = {'bed_mm': BED, 'edge_margin_mm': MARGIN, 'part_gap_mm': GAP,
           'pieces': sum(p['pieces'] for p in plates.values()), 'plates': plates}
    (OUT/'plates.json').write_text(json.dumps(out, indent=2) + '\n')
    print('SOLDER_ARM_PLATES_PASS', {k: v['pieces'] for k, v in plates.items()})


if __name__ == '__main__':
    main()
