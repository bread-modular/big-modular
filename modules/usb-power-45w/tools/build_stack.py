#!/usr/bin/env python3
"""Create the canonical R2 stacked boards hardware/{base,top}/usb-power-45w-{base,top}.kicad_pcb.

ONE-TIME seed (refuses to overwrite a board that already carries tracks, vias or any electrical
copper zone, filled or not: routed copper is never wiped; the current routed top is refused).
BUILD_STACK_OUT=<dir> writes the seed there instead (isolated validation; hardware/ untouched). Input: the final study variant boards
docs/stacked-fit-study/variant-base-protection/boards/ (placement only, read-only) and the native
per-board schematics from tools/board_schematics.py. Changes, all explicit:

- J3 and its markings removed (S7); J2 stays at its accepted position / pin 1 / -12V marking.
- J2 re-seated from the pinned Wurth 61201621621 land (1.1 mm drill) in hardware/USBPOWER45.pretty
  (the study carries the old generic IDC16 land): same orientation, pad 1 on the study's pad 1,
  every pad centre asserted unchanged, nets from the base native netlist.
- Board-to-board headers re-seated from hardware/USBPOWER45.pretty: power XP 2x10, logic XL 2x3
  (tools/stack_r2.py pin maps); first positions = the study's, the refit moves them.
- Every pad net, Value/field and symbol link (path, sheet file) from the board's own native
  netlist, so native DRC schematic parity runs per board.
- Supports: 5 x M3 through-bolt positions (study 4 + one in the freed J3 volume), board-only
  holes with a copper keep-out annulus r1.7..3.6 (4 overlapping hole-free sector rule areas, see
  keepout_sectors) and a courtyard (top: nut-driver access radius).
- Top outline grown into the freed J3 volume (tools/stack_r2.py TOP_OUTLINE).
- Board setup: 4 layers, 1.0 mm copper-to-edge, Power net class on the real rails.

  python3 -B tools/build_stack.py            # both boards (one process each: SWIG Remove quirk)
"""
import json
import math
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import stack_r2 as st  # noqa: E402

HW = MOD / 'hardware'
STUDY = MOD / 'docs/stacked-fit-study/variant-base-protection/boards'
LIB = HW / 'USBPOWER45.pretty'
POWER_NETS = ['GND', 'VPD', 'EF_IN', 'VIN', 'P12_RAW', 'P5_RAW', 'N12_RAW', '+12V', '+5V', '-12V']
J2_FP = 'IDC-Header_2x08_P2.54mm_Vertical_Wurth_61201621621'
STALE_TEXT = ('M1 PREVIEW', 'PARKED OFF-BOARD', 'PROVISIONAL', 'J3 IDC plug')


KEEPOUT_R_IN = 1.7          # all-layer copper keep-out annulus r1.7..STANDOFF_CU_R; the r1.6 NPTH stays clear
KEEPOUT_STEPS = 72          # 5 deg
KEEPOUT_SECTORS = 4


def keepout_sectors(cx, cy, r_in=KEEPOUT_R_IN, r_out=st.STANDOFF_CU_R):
    """Simple native-mm polygons whose union contains the annulus r_in..r_out around (cx, cy).

    KiCad 10 saves a zone hole by appending its vertices to the outline, so an outline + hole ring
    reloads as ONE contour with a radial seam that admits copper. The annulus is therefore built
    from KEEPOUT_SECTORS hole-free annular sectors, each one step over its neighbours. Outer chain:
    edges tangent to r_out + 1 um (vertices at that / cos(step/2)); inner chain: vertices at
    r_in - 1 um (chords inside r_in). The 1 um absorbs the 1 nm save grid; tools/check_support_copper.py
    tests the union against the ideal annulus.
    """
    d = 2 * math.pi / KEEPOUT_STEPS
    ro, ri = (r_out + 0.001) / math.cos(d / 2), r_in - 0.001
    per = KEEPOUT_STEPS // KEEPOUT_SECTORS
    out = []
    for k in range(KEEPOUT_SECTORS):
        idx = list(range(k * per - 1, (k + 1) * per + 2))
        ring = [(cx + ro * math.cos(i * d), cy + ro * math.sin(i * d)) for i in idx] + \
               [(cx + ri * math.cos(i * d), cy + ri * math.sin(i * d)) for i in reversed(idx)]
        out.append([(round(x, 6), round(y, 6)) for x, y in ring])
    return out


def add_support_keepout(b, centre, prefix):
    """All-copper-layer rule areas (no tracks/vias/pads/pours) <prefix>_copper_keepout_r<R>_s<j>."""
    import pcbnew
    zones = []
    for j, ring in enumerate(keepout_sectors(*centre), 1):
        zone = pcbnew.ZONE(b)
        zone.SetIsRuleArea(True)
        for fn in (zone.SetDoNotAllowTracks, zone.SetDoNotAllowVias, zone.SetDoNotAllowPads,
                   zone.SetDoNotAllowZoneFills):
            fn(True)
        zone.SetDoNotAllowFootprints(False)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask())
        zone.SetZoneName(f'{prefix}_copper_keepout_r{st.STANDOFF_CU_R}_s{j}')
        o = zone.Outline()
        o.NewOutline()
        for x, y in ring:
            o.Append(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        b.Add(zone)
        zones.append(zone)
    return zones


def netlist(board):
    sch = HW / board / f'usb-power-45w-{board}.kicad_sch'
    xml = Path(f'/tmp/build_stack_{board}.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml), str(sch)],
                   check=True, stdout=subprocess.DEVNULL)
    root = ET.parse(xml).getroot()
    comps = {}
    for c in root.find('components'):
        fields = {f.get('name'): (f.text or '') for f in c.find('fields')}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'fields': fields, 'uuid': c.findtext('tstamps')}
    pins = {}
    for n in root.find('nets'):
        for nd in n.findall('node'):
            pins[(nd.get('ref'), nd.get('pin'))] = n.get('name')
    return comps, pins


def one(board):
    import pcbnew
    out = HW / board / f'usb-power-45w-{board}.kicad_pcb'
    if os.environ.get('BUILD_STACK_OUT'):
        out = Path(os.environ['BUILD_STACK_OUT']) / board / out.name
    for chk in {out, HW / board / out.name}:      # never wipe copper, wherever the seed is written
        if chk.exists():
            old = pcbnew.LoadBoard(str(chk))
            cu = [z.GetNetname() for z in old.Zones() if not z.GetIsRuleArea()]
            assert not len(old.GetTracks()) and not cu, \
                f'{chk} carries copper (tracks or zones {sorted(set(cu))}): refusing to rebuild'
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    nat = lambda y, z: pcbnew.VECTOR2I(pcbnew.FromMM(y + 35.75), pcbnew.FromMM(104.275 - z))  # noqa: E731
    yz = lambda v: (pcbnew.ToMM(v.x) - 35.75, 104.275 - pcbnew.ToMM(v.y))                     # noqa: E731
    # preload library footprints before any Board.Remove()
    pool = {name: [io.FootprintLoad(str(LIB), name) for _ in range(n)] for name, n in
            (('PinHeader_2x10_P2.54mm_Vertical', 1), ('PinHeader_2x03_P2.54mm_Vertical', 1),
             ('Stack_M3_Spacer_Top' if board == 'top' else 'Stack_M3_Spacer_Base', len(st.STANDOFFS)),
             (J2_FP, 1 if board == 'base' else 0))}
    for name, fps in pool.items():
        for f in fps:
            f.SetFPID(pcbnew.LIB_ID('USBPOWER45', name))
    b = pcbnew.LoadBoard(str(STUDY / board / f'usb-power-45w-{board}.kicad_pcb'))
    comps, pins = netlist(board)
    doomed = []
    old_hdr = {}
    old_j2 = None
    for f in b.GetFootprints():
        r = f.GetReference()
        if r == 'J2':
            assert board == 'base' and f.GetFPIDAsString() == 'USBPOWER45:IDC-Header_2x08_P2.54mm_Vertical', \
                (board, f.GetFPIDAsString())
            old_j2 = f
            doomed.append(f)
        elif r in ('J3',) or r.startswith('MH'):
            doomed.append(f)
        elif r in ('XB1', 'XB2', 'XT1', 'XT2'):
            old_hdr[r] = yz(f.FindPadByNumber('1').GetPosition())
            doomed.append(f)
    for d in b.GetDrawings():
        t = d.GetText() if hasattr(d, 'GetText') else ''
        y, z = yz(d.GetPosition())
        if board == 'base' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and t and y > 84.0 and z > 25:
            doomed.append(d)          # J3 '1 / -12V / RED' and its B-silk pin names
        elif board == 'top' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and t:
            doomed.append(d)          # J2/J3 header markings belong to the base board only
        elif any(t.startswith(s) for s in STALE_TEXT):
            doomed.append(d)
        elif d.GetLayer() == pcbnew.Dwgs_User and d.GetClass() == 'PCB_SHAPE' and abs(y - 85.51) < 0.01:
            doomed.append(d)          # J3 plug envelope
        elif board == 'top' and d.GetLayer() == pcbnew.Edge_Cuts:
            doomed.append(d)
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetZoneName().startswith('MH'):
            doomed.append(z)
    # headers: same pin 1 as the study, pin 2 toward +Z, pin 3 toward +Y
    pre = 'XB' if board == 'base' else 'XT'
    for ref, name in ((pre + '1', 'PinHeader_2x10_P2.54mm_Vertical'), (pre + '2', 'PinHeader_2x03_P2.54mm_Vertical')):
        f = pool[name].pop()
        b.Add(f)
        f.SetReference(ref)
        p1 = old_hdr[ref]
        for rot in (0, 90, 180, 270):
            f.SetOrientationDegrees(rot)
            f.SetPosition(nat(*p1))
            q = {p.GetNumber(): yz(p.GetPosition()) for p in f.Pads()}
            if abs(q['2'][1] - q['1'][1] - 2.54) < 1e-3 and abs(q['3'][0] - q['1'][0] - 2.54) < 1e-3:
                break
        else:
            raise SystemExit(f'{ref}: orientation')
        f.SetPosition(nat(*p1))
    # J2: pinned Wurth land at the study's accepted position / orientation / pad 1
    if board == 'base':
        f = pool[J2_FP].pop()
        b.Add(f)
        f.SetReference('J2')
        f.SetOrientationDegrees(old_j2.GetOrientationDegrees())
        f.SetPosition(old_j2.GetPosition())
        f.Move(old_j2.FindPadByNumber('1').GetPosition() - f.FindPadByNumber('1').GetPosition())
        want = {p.GetNumber(): yz(p.GetPosition()) for p in old_j2.Pads()}
        got = {p.GetNumber(): yz(p.GetPosition()) for p in f.Pads()}
        assert set(want) == set(got) and all(math.dist(want[n], got[n]) < 1e-3 for n in want), 'J2 pad map'
        for t in ('Reference', 'Value'):
            new_t, old_t = getattr(f, t)(), getattr(old_j2, t)()
            new_t.SetPosition(old_t.GetPosition())
            new_t.SetTextAngle(old_t.GetTextAngle())
            new_t.SetVisible(old_t.IsVisible())
    # supports
    for k, (y, z) in enumerate(st.STANDOFFS, 1):
        f = pool['Stack_M3_Spacer_Top' if board == 'top' else 'Stack_M3_Spacer_Base'].pop()
        b.Add(f)
        f.SetReference('')      # board-only mechanical: no reference (shared parity), like the carrier holes
        f.SetValue('M3 through bolt + 5.0 mm plain spacer (R2 stack)')
        f.SetPosition(nat(y, z))
        f.Reference().SetVisible(False)
        f.Value().SetVisible(False)
        add_support_keepout(b, (y + 35.75, 104.275 - z), f'MH{pre[1]}{k}')
    if board == 'top':
        poly = st.TOP_OUTLINE
        for a, c in zip(poly, poly[1:] + poly[:1]):
            s = pcbnew.PCB_SHAPE(b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.05))
            s.SetStart(nat(*a))
            s.SetEnd(nat(*c))
            b.Add(s)
    # nets, values, fields, symbol links from the board's native netlist
    nets = {}

    def net(name):
        if name not in nets:
            n = b.FindNet(name)
            if n is None:
                n = pcbnew.NETINFO_ITEM(b, name)
                b.Add(n)
            nets[name] = n
        return nets[name]
    sheetfile = f'usb-power-45w-{board}.kicad_sch'
    seen = set()
    for f in b.GetFootprints():
        r = f.GetReference()
        if f in doomed or not r:
            continue
        c = comps[r]
        seen.add(r)
        assert f.GetFPIDAsString() == c['footprint'], (r, f.GetFPIDAsString(), c['footprint'])
        f.SetValue(c['value'])
        for k, v in c['fields'].items():
            if k == 'Footprint':
                continue
            had = f.HasField(k)
            f.SetField(k, v)
            if not had:
                f.GetField(k).SetVisible(False)
        f.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
        f.SetSheetname('/')
        f.SetSheetfile(sheetfile)
        for p in f.Pads():
            num = p.GetNumber()
            if not num:
                continue
            name = pins[(r, num)]
            if name.startswith('Net-('):      # XML prints the {slash} escape of auto names as '/'
                name = name.replace('/', '{slash}')
            p.SetNet(net(name))
    assert seen == set(comps), sorted(set(comps) ^ seen)
    # board setup
    ds = b.GetDesignSettings()
    ds.m_CopperEdgeClearance = pcbnew.FromMM(1.0)
    b.SetCopperLayerCount(4)
    for d in doomed:
        b.Remove(d)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(out), b)
    return {'board': board, 'footprints': len(seen), 'nets': len(nets)}


def project(board):
    """Board project: net classes on the real rails; base keeps the J1/SW1 edge windows."""
    pro = HW / board / f'usb-power-45w-{board}.kicad_pro'
    d = json.loads(pro.read_text())
    d['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': n} for n in POWER_NETS]
    d['board']['design_settings']['rules']['min_copper_edge_clearance'] = 1.0
    d.setdefault('meta', {})['filename'] = pro.name
    pro.write_text(json.dumps(d, indent=2) + '\n')
    if board == 'base':
        shutil.copy(HW / 'usb-power-45w.kicad_dru', HW / board / 'usb-power-45w-base.kicad_dru')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--side':
        print(json.dumps(one(sys.argv[2])))
        sys.stdout.flush()
        os._exit(0)
    for name in ('base', 'top'):
        project(name)
        subprocess.run([sys.executable, '-B', __file__, '--side', name], check=True, stderr=subprocess.DEVNULL)
