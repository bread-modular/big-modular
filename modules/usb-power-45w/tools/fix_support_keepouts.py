#!/usr/bin/env python3
"""Replace the seamed M3 support keep-outs of a ROUTED stack board in place (R3 repair).

  python3 -B tools/fix_support_keepouts.py top|base

The R2 seed drew each support keep-out as outline r3.6 + hole r1.7; KiCad 10 saves the hole by
appending it to the outline, so each reloads as ONE 72-vertex contour with a radial seam at +X
that lets zone fill (and could let tracks/vias) into the r1.7..3.6 spacer annulus. This script:

- backs the board up to /tmp, then natively (pcbnew) removes exactly the five old
  MH<T|B><k>_copper_keepout_r3.6 rule areas (asserted: one 72-vertex contour, no hole, centred on
  its Stack_M3_Spacer footprint) and adds the tools/build_stack.py sector keep-outs
  (add_support_keepout, same construction as a fresh seed);
- refills every copper zone natively and saves;
- reloads and asserts nothing else moved: footprints (ref, FPID, position, rotation, side, pad
  nets), tracks and vias (uuid, net, layer, geometry, width, drill) and copper zone outlines,
  nets, layers, priorities and settings are identical; only rule areas and fills differ.
Refuses a board whose keep-outs are already sectors. Copper is never stripped or rerouted.
"""
import hashlib
import shutil
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import build_stack as bs  # noqa: E402
import stack_r2 as st  # noqa: E402


def snapshot(b):
    import pcbnew
    fps = sorted((f.GetReference(), f.GetFPIDAsString(), f.GetPosition().x, f.GetPosition().y,
                  f.GetOrientationDegrees(), f.GetLayer(),
                  tuple(sorted((p.GetNumber(), p.GetNetname(), p.GetPosition().x, p.GetPosition().y) for p in f.Pads())))
                 for f in b.GetFootprints())
    trk = []
    for t in b.GetTracks():
        k = (t.m_Uuid.AsString(), t.GetClass(), t.GetNetname(), t.GetStart().x, t.GetStart().y, t.GetEnd().x,
             t.GetEnd().y, t.GetLayer())
        if t.GetClass() == 'PCB_VIA':
            k += (t.GetWidth(pcbnew.F_Cu), t.GetDrillValue(), t.TopLayer(), t.BottomLayer())
        else:
            k += (t.GetWidth(),)
        trk.append(k)
    zones = []
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        o = z.Outline()
        zones.append((z.m_Uuid.AsString(), z.GetNetname(), tuple(z.GetLayerSet().CuStack()), z.GetAssignedPriority(),
                      z.GetLocalClearance(), z.GetMinThickness(), z.GetPadConnection(), z.GetThermalReliefGap(),
                      z.GetThermalReliefSpokeWidth(), z.GetIslandRemovalMode(),
                      tuple((o.CVertex(i).x, o.CVertex(i).y) for i in range(o.TotalVertices()))))
    draws = sorted((d.GetClass(), d.GetLayer(), d.GetPosition().x, d.GetPosition().y) for d in b.GetDrawings())
    return {'footprints': fps, 'tracks': sorted(trk), 'copper_zones': sorted(zones), 'drawings': draws}


def main(board):
    import pcbnew
    pre = 'T' if board == 'top' else 'B'
    path = MOD / 'hardware' / board / f'usb-power-45w-{board}.kicad_pcb'
    sha0 = hashlib.sha256(path.read_bytes()).hexdigest()
    bak = Path(f'/tmp/usb-power-45w-{board}-pre-support-keepout-{sha0[:12]}.kicad_pcb')
    shutil.copy(path, bak)
    b = pcbnew.LoadBoard(str(path))
    before = snapshot(b)
    sup = {}
    for f in b.GetFootprints():
        if f.GetFPID().GetLibItemName().wx_str().startswith('Stack_M3_Spacer'):
            sup[(pcbnew.ToMM(f.GetPosition().x), pcbnew.ToMM(f.GetPosition().y))] = f
    want = {(round(y + 35.75, 6), round(104.275 - z, 6)): k for k, (y, z) in enumerate(st.STANDOFFS, 1)}
    assert sorted(sup) == sorted(want), (sorted(sup), sorted(want))
    old = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith(f'MH{pre}')]
    names = sorted(z.GetZoneName() for z in old)
    assert names == sorted(f'MH{pre}{k}_copper_keepout_r{st.STANDOFF_CU_R}' for k in range(1, 6)), \
        f'unexpected keep-outs {names} (already repaired?)'
    for z in old:
        o = z.Outline()
        assert o.OutlineCount() == 1 and o.HoleCount(0) == 0 and o.TotalVertices() == 72, z.GetZoneName()
        k = int(z.GetZoneName()[3])
        c = next(p for p, kk in want.items() if kk == k)
        xs = [pcbnew.ToMM(o.CVertex(i).x) for i in range(36)]
        ys = [pcbnew.ToMM(o.CVertex(i).y) for i in range(36)]
        assert abs((max(xs) + min(xs)) / 2 - c[0]) < 1e-3 and abs((max(ys) + min(ys)) / 2 - c[1]) < 1e-3, z.GetZoneName()
    for z in old:
        b.Remove(z)
    for c, k in sorted(want.items(), key=lambda t: t[1]):
        bs.add_support_keepout(b, c, f'MH{pre}{k}')
    pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])
    pcbnew.SaveBoard(str(path), b)
    after = snapshot(pcbnew.LoadBoard(str(path)))
    for k in before:
        assert before[k] == after[k], f'{k} changed'
    sha1 = hashlib.sha256(path.read_bytes()).hexdigest()
    print({'board': str(path), 'backup': str(bak), 'sha256_before': sha0, 'sha256_after': sha1,
           'removed': names, 'unchanged': list(before)})


if __name__ == '__main__':
    main(sys.argv[1])
