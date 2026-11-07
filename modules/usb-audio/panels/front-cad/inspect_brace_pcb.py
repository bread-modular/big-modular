"""Read-only mechanical input for check_usb_brace.py (system Python with pcbnew).

This is NOT an ERC/DRC gate or a replacement for the shared PCB inspector. It reads
native placement/model transforms and bounds solely for this printed brace study.
Never saves a PCB. Usage: /usr/bin/python3 -B .../inspect_brace_pcb.py > snapshot.json
"""
import hashlib
import json
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[2]
HW = MODULE / 'hardware'
geo = json.loads((MODULE / 'docs/geometry.json').read_text())
ox, oy = geo['kicad_origin_mm']
path = HW / 'usb-audio-mcu.kicad_pcb'
b = pcbnew.LoadBoard(str(path))


def xy_box(bb):
    return [pcbnew.ToMM(bb.GetX())-ox, pcbnew.ToMM(bb.GetY())-oy,
            pcbnew.ToMM(bb.GetRight())-ox, pcbnew.ToMM(bb.GetBottom())-oy]


fps = []
for fp in b.GetFootprints():
    shapes = [g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_CrtYd]
    assert shapes, fp.GetReference()
    boxes = [xy_box(bb) for bb in shapes]
    bbox = [min(bb[0] for bb in boxes), min(bb[1] for bb in boxes),
            max(bb[2] for bb in boxes), max(bb[3] for bb in boxes)]
    models = []
    for m in fp.Models():
        filename = m.m_Filename.replace('${KIPRJMOD}', str(HW)).replace(
            '${KICAD10_3DMODEL_DIR}', '/usr/share/kicad/3dmodels')
        models.append({'path': filename, 'offset': [m.m_Offset.x, m.m_Offset.y, m.m_Offset.z],
                       'rotation': [m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z],
                       'scale': [m.m_Scale.x, m.m_Scale.y, m.m_Scale.z]})
    fps.append({'ref': fp.GetReference(), 'angle': fp.GetOrientationDegrees(),
                'xy': [pcbnew.ToMM(fp.GetPosition().x)-ox, pcbnew.ToMM(fp.GetPosition().y)-oy],
                'courtyard': bbox, 'models': models,
                'pads': [{'number': p.GetNumber(), 'bbox': xy_box(p.GetBoundingBox()),
                          'thru': bool(p.GetDrillSize().x)} for p in fp.Pads()]})

# Top edge strip must be genuinely clear, not just visually free of packages.
copper = []
for track in b.GetTracks():
    if track.IsOnLayer(pcbnew.F_Cu) or track.IsOnLayer(pcbnew.B_Cu):
        copper.append(xy_box(track.GetBoundingBox())[1])
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(pcbnew.F_Cu) or pad.IsOnLayer(pcbnew.B_Cu):
            copper.append(xy_box(pad.GetBoundingBox())[1])
for zone in b.Zones():
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        if zone.IsOnLayer(layer):
            polys = zone.GetFilledPolysList(layer)
            for i in range(polys.OutlineCount()):
                outline = polys.COutline(i)
                copper += [pcbnew.ToMM(outline.CPoint(j).y)-oy for j in range(outline.PointCount())]
assert copper
# Header plastic on the carrier occupies the gap where the longer tongue goes.
carrier_path = HW/'usb-audio.kicad_pcb'
carrier = pcbnew.LoadBoard(str(carrier_path))
header_envelopes = []
for fp in carrier.GetFootprints():
    if fp.GetReference() not in ('J6', 'J7'):
        continue
    boxes = [xy_box(g.GetBoundingBox()) for g in fp.GraphicalItems()
             if g.GetLayer() == pcbnew.F_CrtYd]
    assert boxes, fp.GetReference()
    header_envelopes.append({'ref': fp.GetReference(), 'bbox':
        [min(bb[0] for bb in boxes), min(bb[1] for bb in boxes),
         max(bb[2] for bb in boxes), max(bb[3] for bb in boxes)]})
assert len(header_envelopes) == 2
result = {'board': str(path), 'board_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
          'top_surface_copper_min_y': min(copper), 'footprints': fps,
          'carrier_board': str(carrier_path),
          'carrier_sha256': hashlib.sha256(carrier_path.read_bytes()).hexdigest(),
          'carrier_header_envelopes': header_envelopes}
print(json.dumps(result, indent=2))
