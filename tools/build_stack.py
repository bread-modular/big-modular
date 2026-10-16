#!/usr/bin/env python3
"""Build a NEW unrouted A4.2 mechanical/placement candidate, never overwrite hardware.

Common-tool pcb inspect rejects the retained USB model dependency; its edit subset
also cannot change these NPTHs/arcs or introduce schematic-less UI reservations.
This deliberately narrow native generator complements (does not replace) the
common check tool. The original J1 object and entire circuit hierarchy are kept.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shutil
import uuid
import pcbnew as pcb
from sexp import parse,dump
from stack_geometry import geometry, carrier_xy, panel_xy, carrier_outline

ROOT = Path(__file__).resolve().parents[1]
G = geometry()
MM = pcb.FromMM


def vec(x, y):
    return pcb.VECTOR2I(MM(x), MM(y))


def line(board, start, end, layer=pcb.Edge_Cuts):
    obj = pcb.PCB_SHAPE()
    obj.SetShape(pcb.SHAPE_T_SEGMENT)
    obj.SetStart(vec(*start)); obj.SetEnd(vec(*end)); obj.SetLayer(layer)
    obj.SetWidth(MM(.05 if layer == pcb.Edge_Cuts else .15)); board.Add(obj)


def polygon(board, points, layer=pcb.Edge_Cuts):
    for a, b in zip(points, points[1:] + points[:1]):
        line(board, a, b, layer)


def rounded_aperture(board, x, y, w, h, r):
    k = r / math.sqrt(2)
    segments = [((x+r,y),(x+w-r,y)), ((x+w,y+r),(x+w,y+h-r)),
                ((x+w-r,y+h),(x+r,y+h)), ((x,y+h-r),(x,y+r))]
    arcs = [((x+w-r,y),(x+w-r+k,y+r-k),(x+w,y+r)),
            ((x+w,y+h-r),(x+w-r+k,y+h-r+k),(x+w-r,y+h)),
            ((x+r,y+h),(x+r-k,y+h-r+k),(x,y+h-r)),
            ((x,y+r),(x+r-k,y+r-k),(x+r,y))]
    for a, b in segments: line(board, a, b)
    for a, m, b in arcs:
        obj = pcb.PCB_SHAPE(); obj.SetShape(pcb.SHAPE_T_ARC)
        obj.SetArcGeometry(vec(*a), vec(*m), vec(*b)); obj.SetLayer(pcb.Edge_Cuts)
        obj.SetWidth(MM(.05)); board.Add(obj)


def text(board, value, x, y, size=.8, layer=pcb.Dwgs_User):
    obj = pcb.PCB_TEXT(board); obj.SetText(value); obj.SetPosition(vec(x, y))
    obj.SetTextSize(vec(size, size)); obj.SetTextThickness(MM(.12)); obj.SetLayer(layer)
    board.Add(obj)


def hole(board, ref, at, diameter, dy=None, contact_radius=2.1):
    dy = diameter if dy is None else dy
    fp = pcb.FOOTPRINT(board); fp.SetReference(ref); fp.SetValue('MECHANICAL_NPTH')
    fp.SetPosition(vec(*at)); fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    pad = pcb.PAD(fp); pad.SetAttribute(pcb.PAD_ATTRIB_NPTH)
    pad.SetShape(pcb.PAD_SHAPE_CIRCLE if diameter == dy else pcb.PAD_SHAPE_OVAL)
    pad.SetSize(vec(diameter, dy)); pad.SetDrillSize(vec(diameter, dy))
    if diameter != dy: pad.SetDrillShape(pcb.PAD_DRILL_SHAPE_OBLONG)
    pad.SetLayerSet(pcb.LSET.AllCuMask()); pad.SetPosition(vec(*at))
    fp.Add(pad); board.Add(fp)
    # Drawing-only screw/washer contact reservation: deliberately NOT copper zones.
    if contact_radius:
        obj = pcb.PCB_SHAPE(); obj.SetShape(pcb.SHAPE_T_CIRCLE)
        obj.SetCenter(vec(*at)); obj.SetEnd(vec(at[0]+contact_radius, at[1]))
        obj.SetLayer(pcb.Dwgs_User); obj.SetWidth(MM(.1)); board.Add(obj)


def board():
    b = pcb.BOARD(); b.SetCopperLayerCount(2)
    b.GetDesignSettings().SetBoardThickness(MM(1.6))
    return b


def placed(b, hw, lib, name, ref, value, at, nets, rotation=0, back=False):
    target = hw/'BigModular.pretty'/f'{name}.kicad_mod'
    if not target.exists():
        shutil.copyfile(Path('/usr/share/kicad/footprints')/(lib+'.pretty')/(name+'.kicad_mod'), target)
    fp = pcb.FootprintLoad(str(target.parent), name)
    fp.SetFPID(pcb.LIB_ID('BigModular', name)); fp.SetReference(ref); fp.SetValue(value)
    fp.SetPosition(vec(*at))
    b.Add(fp)  # Native Flip needs a parent board/layer stack.
    if back: fp.Flip(fp.GetPosition(), pcb.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rotation)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    fp.SetLocked(True)
    for pad in fp.Pads():
        name = nets.get(pad.GetNumber(), '')
        if name:
            net = b.FindNet(name)
            if not net:
                net = pcb.NETINFO_ITEM(b, name); b.Add(net)
            pad.SetNet(net)
    return fp


def stable_ids(b, name):
    # Deterministic generated IDs; preserve every existing J1 child/UUID verbatim.
    ns = uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/A4/'+name)
    def setid(obj, key): obj.SetUuid(pcb.KIID(str(uuid.uuid5(ns, key))))
    for i, d in enumerate(b.GetDrawings()): setid(d, f'drawing:{i}')
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref == 'J1': continue
        setid(fp, ref)
        for i, obj in enumerate(list(fp.Pads())+list(fp.GraphicalItems())+list(fp.GetFields())):
            setid(obj, f'{ref}:child:{i}')


def switch_footprint(pretty):
    """Reuse the reviewed A4 SMT land pattern verbatim, not the THT alternatives.

    Library source is canonical: three exposed signal lands, two solder anchors
    and two NPTH pegs. Manufacturer pin1+3 common, pin2 other contact. The
    hand-solder pattern has already been trimmed around the locating pegs.
    """
    name=G['switch']['footprint']
    assert name=='SW_TL3340AF160QG_HandSolder'
    shutil.copyfile(ROOT/'hardware/BigModular.pretty'/(name+'.kicad_mod'),
                    pretty/(name+'.kicad_mod'))


def led_footprint(pretty):
    """Use the existing pinned 3mm formed-lead footprint without library refresh."""
    target=pretty/(G['LED']['footprint']+'.kicad_mod')
    assert target.is_file(), 'missing pinned 3mm LED footprint'


def wire_landing(pretty):
    a = ['(footprint "WireLanding_2x08_P2.54mm" (version 20260206)(generator "pcbnew")(layer "F.Cu")(attr through_hole)',
         '(descr "Numbered solder-through lands for insulated J2 flying output lead; NOT a populated header")',
         '(property "Reference" "REF**" (at 0 -3)(layer "F.SilkS")(effects(font(size 1 1)(thickness .15))))',
         '(property "Value" "IDC OUTPUT PIGTAIL" (at 0 -5)(layer "F.Fab")(effects(font(size 1 1)(thickness .15))))']
    for row in range(8):
        for col in range(2):
            n=2*row+col+1
            a.append(f'(pad "{n}" thru_hole {"rect" if n==1 else "oval"} (at {col*2.54} {row*2.54})(size 1.8 1.8)(drill 1)(layers "*.Cu" "*.Mask"))')
    a.append(')');(pretty/'WireLanding_2x08_P2.54mm.kicad_mod').write_text('\n'.join(a)+'\n')


def build(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    hw = output/'hardware'; hw.mkdir()
    pretty = hw/'BigModular.pretty'
    shutil.copytree(ROOT/'hardware/BigModular.pretty', pretty)
    for name in ['fp-lib-table', 'big_modular.kicad_pro', 'front_panel.kicad_pro']:
        shutil.copyfile(ROOT/'hardware'/name, hw/name)
    # Preserve board setup/net definitions and J1's native object exactly.
    b = pcb.LoadBoard(str(ROOT/'hardware/big_modular.kicad_pcb'))
    assert not list(b.GetTracks()) and not list(b.Zones()), 'Refuse to erase routed design'
    refs = {f.GetReference() for f in b.GetFootprints()}
    assert refs <= {'J1','J3','J4','J7','D10','D11','D12','R32','SW1','H1','H2','H3','H4'} and 'J1' in refs, 'Unexpected placed circuitry'
    # KiCad's Python Remove wrapper corrupts ownership on this engine; use the
    # same native-detach/retained-lifetime pattern as the shared edit worker.
    retired = list(b.GetDrawings()) + [f for f in b.GetFootprints() if f.GetReference() != 'J1']
    for item in retired:
        b.RemoveNative(item)
        item.thisown = False
    polygon(b, [carrier_xy(*p) for p in carrier_outline()])
    for i, point in enumerate(G['carrier_holes_YZ_mm'], 1):
        hole(b, f'H{i}', carrier_xy(*point), 3.2, contact_radius=3.5)
    led_footprint(pretty)
    for led in G['LEDs']:
        ref=led['reference']
        fp=placed(b,hw,'LED_THT',G['LED']['footprint'],ref,'RED 3mm / '+led['rail']+' / MANUAL',
                  carrier_xy(*led['pad1_YZ_mm']),{'1':ref+'_K_PENDING','2':ref+'_A_PENDING'})
        # Manual installation is NOT DNP. Position exclusion also excludes both
        # assembly CSVs in the shared exporter; keep engineering BOM inclusion.
        fp.SetAttributes(fp.GetAttributes() | pcb.FP_EXCLUDE_FROM_POS_FILES)
    switch_footprint(pretty)
    placed(b,hw,'',G['switch']['footprint'],'SW1',G['switch']['mpn'],
           carrier_xy(*G['switch']['peg_row_YZ_mm']),G['switch']['pins'])
    power = G['power_output']
    wire_landing(pretty)
    placed(b,hw,'','WireLanding_2x08_P2.54mm','J7','EURORACK OUTPUT PIGTAIL / NOT INPUT',
           carrier_xy(*power['launch_pad1_YZ_mm']),power['pinout'],rotation=90)
    for i,yz in enumerate(power['strain_relief_holes_YZ_mm'],3):
        hole(b,f'H{i}',carrier_xy(*yz),2.5,contact_radius=1.75)
    text(b,'1 / -12V / RED',*carrier_xy(44,22),.8,pcb.F_SilkS)
    text(b,'J7 -> J2 OUTPUT ONLY',*carrier_xy(59,23),.8,pcb.F_SilkS)
    text(b, 'A4.2 / MAIN PCB / TWO-BOARD PLACEMENT / NO ROUTING',100,65,1)
    text(b, 'USB + 3 RED 3mm THT LEDs + hand-solder SMT reset; no middle board',100,68)
    text(b, 'UI nets isolated; not a working reset/power indicator circuit',100,110)
    text(b, 'M3 ONLY: two bracket holes; no standoffs / no board-to-board headers',100,114)
    for yc in G['brackets']['Y_centres_mm']:
        polygon(b,[carrier_xy(y,z) for y,z in [(yc-5,10),(yc+5,10),(yc+5,20),(yc-5,20)]],pcb.Dwgs_User)
    # Drawing reservations only; no copper, tracks, vias or zones.
    for led in G['LEDs']:
        y=led['panel_XY_diameter_mm'][1]
        text(b,led['reference']+' '+led['rail'],*carrier_xy(y,11),.8,pcb.F_SilkS)
        text(b,'K',*carrier_xy(y-1.27,8.8),.8,pcb.F_SilkS)
        text(b,'A',*carrier_xy(y+1.27,8.8),.8,pcb.F_SilkS)
    for label,y,z in [('RESET',91,12)]:
        text(b,label,*carrier_xy(y,z),.8,pcb.F_SilkS)
    stable_ids(b, 'carrier'); pcb.SaveBoard(str(hw/'big_modular.kicad_pcb'), b)

    p = board(); polygon(p, [panel_xy(*q) for q in [(0,0),(9.8,0),(9.8,128.5),(0,128.5)]])
    x,y,w,h,r = G['aperture_XYWHR_mm']; rounded_aperture(p, x+50,y+30,w,h,r)
    for i,(x,y,d) in enumerate(G['rail_holes_mm'],1): hole(p, f'H{i}', panel_xy(x,y),d,contact_radius=3)
    for i,(x,y,d) in enumerate(G['panel_bracket_holes_mm'],3): hole(p, f'H{i}',panel_xy(x,y),d,contact_radius=3.5)
    for led in G['LEDs']:
        x,y,d=led['panel_XY_diameter_mm']; hole(p,led['panel_hole_ref'],panel_xy(x,y),d,contact_radius=0)
        text(p,led['rail'],*panel_xy(4.9,y-4),.8,pcb.F_SilkS)
    x,y,d=G['reset_XY_diameter_mm']; hole(p,'H6',panel_xy(x,y),d,contact_radius=0)
    for label,y,size in [('BIG',10.5,.9),('MOD',13,.9),('PD 9V',76.5,.8),('USB',74.5,.8),('RESET',86,.8),('A4.2',118,.8)]:
        text(p,label,*panel_xy(4.9,y),size,pcb.F_SilkS)
    text(p,'2HP / round corner holes X2.42 = X7.50 minus one 5.08mm rail pitch',102,40,.9)
    text(p,'A4.2 plain L brackets: M3x8 panel / M3x8 countersunk side',101,44,.9)
    text(p,'TL3340AF160QG SMT reset; D10/D11/D12 RED 3mm LEDs formed 90 degrees',100,48,.9)
    stable_ids(p,'panel'); pcb.SaveBoard(str(hw/'front_panel.kicad_pcb'),p)

    (output/'assembly-geometry.json').write_text(json.dumps(G,indent=2)+'\n')
    # Source manifest includes unchanged electrical documents, not only boards.
    sources = [q for q in (ROOT/'hardware').rglob('*') if q.is_file() and q.suffix not in ('.lck','.kicad_prl')]
    sources += [ROOT/'BOM.csv',ROOT/'docs/pin-net-audit.json']
    (output/'source-manifest.json').write_text(json.dumps({
        'status':'placement candidate / not electrically synchronized / not fabrication ready',
        'common_tool_limit':'pcb inspect: 3D models, embedded files and images are unsupported dependencies; fail closed',
        'source_sha256':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in sources},
        'new_refs':['D11','D12'], 'reserved_LED_refs':['D10','D11','D12'], 'manual_assembly_refs':['D10','D11','D12'], 'removed_refs':['R32'], 'retired_board':'middle_plate', 'routing_performed':False},indent=2)+'\n')
    print('Created NEW two-board placement candidate:',output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='NEW directory; existing paths are rejected')
    build(parser.parse_args().output)
