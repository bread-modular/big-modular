"""One-time S4 start: the routed modules/usb-audio S5 / R5 carrier becomes the 32bit S4 carrier.

Run from modules/32bit with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/carrier_from_usb_audio.py            # dry run: what changes, copper conflicts
  python3 -B tools/carrier_from_usb_audio.py --write    # writes hardware/32bit.kicad_{pro,pcb}

What it does (what KiCad's "Update PCB from Schematic" would do, plus the copper bookkeeping):
- copies ../usb-audio/hardware/usb-audio.kicad_{pro,pcb} (footprint library USBAUDIO -> 32BIT, the
  footprints are byte-identical apart from the name: tools/import_footprints.py), title block S4;
- drops the footprints the 32bit schematic no longer has (RV3, RV4, U7, C31, C32, J8), adds the new
  ones parked right of the board (B side SMD), and gives every kept footprint the 32bit symbol link,
  value, fields and pad nets of the native netlist;
- re-nets the copper: each connected piece of track / via copper (old net) takes the new net of the
  pads it touches; a piece touching pads of two new nets is reported (and, with --write, the
  segments listed in CUT are deleted first) and deleted, a piece touching no pad is deleted.
The routed board then owns placement and copper (root AGENTS.md); this script is not run again.
"""
import json
import shutil
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_layout as BL  # noqa: E402  (schematic_netlist, place, vendor_model)

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
SRC = MODULE.parent / 'usb-audio/hardware'
OX, OY = 100.0, 50.0

# Segments cut before re-netting (panel-frame start/end, mm, layer): copper that joined two pads whose
# nets the S4 schematic separates.
CUT = []


def copy_sources():
    pro = json.loads((SRC / 'usb-audio.kicad_pro').read_text())
    pro['meta']['filename'] = '32bit.kicad_pro'
    sch = (HW / '32bit.kicad_sch').read_text()
    sheet = pro['schematic']['top_level_sheets'][0]
    sheet.update(filename='32bit.kicad_sch', name='32bit', uuid=sch.split('(uuid "', 1)[1].split('"', 1)[0])
    rails = ['GND', '+3V3', '+3V3_C', '+5VA', '+12V', '-12V', '+12V_F', '-12V_F']
    pro['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': r} for r in rails]
    (HW / '32bit.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n')
    text = (SRC / 'usb-audio.kicad_pcb').read_text().replace('"USBAUDIO:', '"32BIT:')
    (HW / '32bit.kicad_pcb').write_text(text)
    models = HW / '_kicad_models'
    for d in (SRC / '_kicad_models').iterdir():
        if not (models / d.name).exists():
            shutil.copytree(d, models / d.name)


def mm(v):
    return round(pcbnew.ToMM(v), 4)


def clusters(board):
    """Connected pieces of track / via copper (same old net, touching geometry)."""
    items = [t for t in board.GetTracks()]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def shape(t):
        return t.GetEffectiveShape(t.GetLayer() if t.GetClass() != 'PCB_VIA' else pcbnew.F_Cu)

    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            b = items[j]
            if a.GetNetCode() != b.GetNetCode():
                continue
            la = {a.GetLayer()} if a.GetClass() != 'PCB_VIA' else set(a.GetLayerSet().CuStack())
            lb = {b.GetLayer()} if b.GetClass() != 'PCB_VIA' else set(b.GetLayerSet().CuStack())
            common = la & lb
            if not common:
                continue
            layer = next(iter(common))
            if a.GetEffectiveShape(layer).Collide(b.GetEffectiveShape(layer), 0):
                parent[find(i)] = find(j)
    groups = {}
    for i, t in enumerate(items):
        groups.setdefault(find(i), []).append(t)
    return list(groups.values())


def touched_pads(board, group):
    pads = {}
    for t in group:
        layers = [t.GetLayer()] if t.GetClass() != 'PCB_VIA' else list(t.GetLayerSet().CuStack())
        for fp in board.GetFootprints():
            for p in fp.Pads():
                for layer in layers:
                    if p.IsOnLayer(layer) and p.GetEffectiveShape(layer).Collide(t.GetEffectiveShape(layer), 0):
                        pads[(fp.GetReference(), p.GetNumber())] = p
    return list(pads.values())


def main(write):
    if write:
        copy_sources()
    for f in (HW / '32BIT.pretty').glob('*.kicad_mod'):
        BL.FP_CACHE[f.stem] = pcbnew.FootprintLoad(str(HW / '32BIT.pretty'), f.stem)
    board = pcbnew.LoadBoard(str(HW / '32bit.kicad_pcb' if write else SRC / 'usb-audio.kicad_pcb'))
    comps, nets = BL.schematic_netlist('32bit')
    tb = board.GetTitleBlock()   # before any Remove (pcbnew 10 Python loses SWIG types after one)
    tb.SetTitle('Big Modular - 32BIT carrier (jack board)')
    tb.SetRevision('S4')
    tb.SetComment(0, 'S4 / R1: modules/usb-audio S5 / R5 carrier copper, adapted by hand (docs/research.md section 9)')
    tb.SetComment(1, 'Front (F) faces the panel; jacks/pots/MODE/LED/headers hand-soldered; SMD on B; 4 layers')
    tb.SetComment(2, 'ESP32-S3 MCU board (32bit-mcu) sits on J6/J7 below the two M3x10 standoffs; docs/geometry.json')
    fps = {fp.GetReference(): fp for fp in board.GetFootprints() if fp.GetReference()}
    drop = sorted(set(fps) - set(comps))
    add = sorted(set(comps) - set(fps))
    print('drop', drop, '\nadd', add)
    for s in list(board.GetTracks()):
        if s.GetClass() == 'PCB_TRACK':
            key = ((mm(s.GetStart().x) - OX, mm(s.GetStart().y) - OY), (mm(s.GetEnd().x) - OX, mm(s.GetEnd().y) - OY),
                   s.GetLayerName())
            if any(abs(key[0][0] - c[0][0]) < 0.01 and abs(key[0][1] - c[0][1]) < 0.01 and abs(key[1][0] - c[1][0]) < 0.01
                   and abs(key[1][1] - c[1][1]) < 0.01 and key[2] == c[2] for c in CUT):
                board.Delete(s)
    dropped = [fps.pop(ref) for ref in drop]   # removed at the end: pcbnew 10 Python loses SWIG types after a Remove
    # nets of the new schematic
    netinfo = {}
    for name in nets:
        n = board.FindNet(name)
        if n is None:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            n.thisown = 0
        netinfo[name] = n
    BL.OX, BL.OY = OX, OY
    x, y = 38.0, 10.0
    for ref in add:
        name = comps[ref]['footprint'].split(':')[1]
        fp = BL.place(board, ref, name, x, y, 0, comps[ref], back=name not in ('SW_PUSH_6mm_H7.3mm', 'LED_D3.0mm'),
                      project='32bit')
        fps[ref] = fp
        y += 6.0
    for ref, fp in fps.items():
        c = comps[ref]
        fp.SetValue(c['value'])
        fp.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
        fp.SetSheetfile('32bit.kicad_sch')
        for key, val in c['fields'].items():
            fp.SetField(key, val)
            fp.GetField(key).SetVisible(False)
    pin_net = {(r, p): n for n, members in nets.items() for r, p in members}
    for ref, fp in fps.items():
        for p in fp.Pads():
            n = pin_net.get((ref, p.GetNumber()))
            if p.GetNumber() == '':
                continue
            assert n, (ref, p.GetNumber())
            p.SetNet(netinfo[n])
    for fp in dropped:
        for p in fp.Pads():
            p.SetNetCode(0)
    dropped_refs = set(drop)
    # re-net the copper piece by piece
    conflicts, orphans = [], []
    for group in clusters(board):
        old = group[0].GetNetname()
        new = {p.GetNetname() for p in touched_pads(board, group)
               if p.GetParentFootprint().GetReference() not in dropped_refs}
        if len(new) == 1:
            n = netinfo[new.pop()]
            for t in group:
                t.SetNet(n)
            if n.GetNetname() != old:
                print(f'  {old} -> {n.GetNetname()} ({len(group)} items)')
        elif not new:
            orphans.append((old, len(group)))
            for t in group:
                board.Delete(t)
        else:   # joins pads the S4 schematic separates: removed, routed again by hand
            conflicts.append((old, sorted(new), [(t.GetClass(), (mm(t.GetStart().x) - OX, mm(t.GetStart().y) - OY),
                                                  (mm(t.GetEnd().x) - OX, mm(t.GetEnd().y) - OY), t.GetLayerName())
                                                 for t in group]))
            for t in group:
                board.Delete(t)
    print('orphan copper removed:', orphans)
    for old, new, items in conflicts:
        print('CONFLICT (removed)', old, new)
        for it in items:
            print('   ', it)
    for fp in dropped:
        board.Delete(fp)
    if write:
        BL.save_canonical(HW / '32bit.kicad_pcb', board)
        print('written', HW / '32bit.kicad_pcb')


if __name__ == '__main__':
    main('--write' in sys.argv[1:])
