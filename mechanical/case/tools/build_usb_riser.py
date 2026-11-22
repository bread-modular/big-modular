"""8 HP USB riser for modules/32bit in the 42 HP / 60 mm skiff.

Build only this add-on: mechanical/case/tools/build_usb_riser.sh.
Original case exports are never overwritten.

The 32bit's USB-C socket is on the back of the carrier at the top edge and opens straight at the
top rail, 1.6 mm away, so no plug goes in while the module is in the case. The riser is a closed
collar that sits on the two rails in an 8 HP slot and lifts the whole module LIFT mm: a straight
plug then passes through one slot in the collar's back wall, over the back rail and out of the
case. Nothing else is open.

Fixing, two stages, the case's own M3 hardware:
  riser -> rails   3 x M3x8 socket head in counterbores, into the rail spacers (two at the front
                   rail, one at the back: the USB slot takes the place of the second)
  module -> riser  the module's two M3x6 into two M3x10 hex spacers superglued in the riser
The module's FR4 panel lies in a pocket, flush with the riser top, and hides the riser screws.

The module cannot sit centred in the 8 HP: the rail spacers are 2 HP apart, so a centred 6 HP
module lands between them and the riser screws would cut into the module spacers or the USB
slot. MOD_DX puts it right of centre; the web between the back / front-left counterbore and the
module spacer and the leg right of the USB slot share what is left (see `walls` in the report).

Frame = the case assembly frame of build_case.py (X along the rails, Y across them, Z up). The
module's top edge (panel Y 0) faces the case back (+Y): case Y = 128.5 - panel Y, case X = slot
X + MOD_DX + panel X. Prints as it sits: rail face on the bed, no supports, one 13.5 mm bridge
(the USB slot roof).

CAD-checked prototype against a stand-in of the module (modules/32bit/docs/geometry.json):
not printed, fits not measured.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base  # noqa: E402
import FreeCAD as App  # noqa: E402
import Mesh  # noqa: E402
import MeshPart  # noqa: E402
import Part  # noqa: E402

V = App.Vector
CASE = base.CASE
REPO = CASE.parents[1]
OUT = CASE / "print" / "accessories" / "usb-riser"
RESEARCH = CASE / "research" / "usb-riser" / "final"
NAME = "usb-riser-32bit-8hp"
TOL = 1e-3
box, cyl = base.box, base.cyl
HP = base.HP
PANEL_H = base.PANEL_H

d = base.Dims(42, 60.0, 0.5, base.module_panels())
geo = json.loads((REPO / "modules/32bit/docs/geometry.json").read_text())

# --- riser parameters ---------------------------------------------------------
RISER_HP = 8
LIFT = 18.0                  # rail top -> module panel rear
MOD_DX = 7.5                 # module slot left edge inside the riser slot (centred would be 5.08)
SIDE_GAP = 0.48              # panels start on the HP grid and end this much short (30.0 mm for 6 HP)
POCKET_CLR = 0.25            # panel pocket around the FR4 panel, each side
CAVITY_CLR = 0.3             # cavity around the carrier outline, each side
CB_FLOOR = 4.0               # riser floor under the rail screw heads (M3x8: 3.8 mm in the spacer)
RISER_SCREW_L = 8.0
MODULE_SCREW_L = 6.0
SLOT_W = 13.5                # USB plug slot width
SLOT_BELOW = 4.0             # slot roof: this far above the plug centre line ...
SLOT_SAG = 0.4               # ... plus this for the sag of the printed bridge
CORNER_R = 2.0               # outer vertical corners
TOP_CHAMFER = 0.5
BED_CHAMFER = 0.4            # around the footprint, against the first layer's squash
PLUG_W, PLUG_H, PLUG_L = 12.35, 6.5, 22.0   # USB-C plug overmold (USB-IF maximum section)
USB_BODY = (8.94, 7.35, 3.26)               # HRO TYPE-C-31-M-12 shell
SCENE_SLOT_HP = 16           # where the riser sits in the preview row (any even HP slot works)

panel_w, panel_h = geo["panel_mm"]
panel_t = geo["panel_pcb_thickness_mm"]
pcb = geo["main_pcb"]["outline_mm"]
seat = geo["stack_Z_mm"]["panel_rear_seat"]          # carrier F.Cu below the panel rear
usb = next(p for p in geo["back_side_parts"] if p["ref"] == "J7")
usb_face_py = pcb[1] + 0.35                           # geometry.json: face 0.35 mm inside the top edge

assert geo["hp"] == 6 and abs(geo["hp"] * HP - SIDE_GAP - panel_w) < 1e-6
assert abs(panel_t - d.panel_t) < 1e-6
assert SCENE_SLOT_HP % 2 == 0, "modules sit on even HP slots (rail spacers every 2 HP)"

slot_x = d.row_x0 + SCENE_SLOT_HP * HP               # riser HP slot, left edge
mod_x = slot_x + MOD_DX                              # module HP slot, left edge
z0 = d.top                                           # rail top
zr = z0 + LIFT                                       # module panel rear
z1 = zr + panel_t                                    # module panel front = riser top
rx0, rx1 = slot_x, slot_x + RISER_HP * HP - SIDE_GAP
ry0, ry1 = d.y0, d.y0 + d.ylen                       # over the whole rail width
rail_in = (d.rail_y[0] + d.rail_w, d.rail_y[1])      # rail inner faces
usb_z = zr - seat - 1.6 - USB_BODY[2] / 2            # socket / plug centre line
slot_top = usb_z + SLOT_BELOW + SLOT_SAG


def cy(py):
    return PANEL_H - py


def mx(px):
    return mod_x + px


usb_x, usb_y = mx(usb["XY"][0]), cy(usb_face_py)     # socket face centre
slot_y0 = usb_y - 1.0                                # the plug is wider than the carrier there


def rail_screws():
    """Rail spacers used by the riser: left of the module screw at both rails (clear of the USB
    slot at the back), and right of it at the front."""
    k = [12.58, 32.9]
    out = [(slot_x + k[0], d.hole_y[1]), (slot_x + k[0], d.hole_y[0]), (slot_x + k[1], d.hole_y[0])]
    sockets = d.module_hole_x()
    for sx, _ in out:
        assert min(abs(sx - s) for s in sockets) < 1e-6, "riser screw is not on a rail spacer"
    return out


def module_screws():
    return [(mx(hx), cy(hy)) for hx, hy, _ in geo["rail_holes_mm"]]


# --- riser ----------------------------------------------------------------------
def tools():
    """The cuts, by name (the wall checks measure between them)."""
    t = {}
    # cavity for the carrier, jacks and pots, rail to rail, open to the case below
    t["cavity"] = box((mx(pcb[0]) - CAVITY_CLR, rail_in[0], z0 - 1),
                      (pcb[2] - pcb[0] + 2 * CAVITY_CLR, rail_in[1] - rail_in[0], z1 - z0 + 2))
    # pocket: the FR4 panel lies flush with the riser top
    t["pocket"] = box((mx(0) - POCKET_CLR, cy(panel_h) - POCKET_CLR, zr),
                      (panel_w + 2 * POCKET_CLR, panel_h + 2 * POCKET_CLR, panel_t + 1))
    # USB plug slot through the back end block, open to the rail top
    t["usb_slot"] = box((usb_x - SLOT_W / 2, slot_y0, z0 - 1), (SLOT_W, ry1 - slot_y0 + 1, slot_top - z0 + 1))
    # in front of the end block the slot is a notch in the right side wall: 45 degree roof, no ledge
    cav_x1, slot_x1 = mx(pcb[2]) + CAVITY_CLR, usb_x + SLOT_W / 2
    wedge = Part.Face(Part.makePolygon([V(cav_x1 - 0.5, slot_y0, slot_top - 0.5), V(slot_x1, slot_y0, slot_top - 0.5),
                                        V(slot_x1, slot_y0, slot_top),
                                        V(cav_x1 - 0.5, slot_y0, slot_top + slot_x1 - cav_x1 + 0.5),
                                        V(cav_x1 - 0.5, slot_y0, slot_top - 0.5)]))
    t["usb_notch_roof"] = wedge.extrude(V(0, rail_in[1] - slot_y0, 0))
    # module screws: M3x10 hex spacers, 0.2 mm under the panel seat as in the rails, with a vent
    for k, (x, y) in enumerate(module_screws()):
        t[f"spacer_{k}"] = base.spacer_socket((x, y), zr - base.SPACER_SOCKET_DEPTH + 1,
                                              base.SPACER_SOCKET_DEPTH + 1, "x")
        t[f"vent_{k}"] = cyl(base.M3_CLEAR / 2, zr - z0 + 2, (x, y, z0 - 1))
    # riser -> rail screws: counterbore from the panel seat down to a floor over the rail
    for k, (x, y) in enumerate(rail_screws()):
        t[f"screw_{k}"] = cyl(base.M3_CLEAR / 2, CB_FLOOR + 2, (x, y, z0 - 1))
        t[f"counterbore_{k}"] = cyl(base.M3_CB_D / 2, zr - z0 - CB_FLOOR + 1, (x, y, z0 + CB_FLOOR))
    return t


def riser():
    body = box((rx0, ry0, z0), (rx1 - rx0, ry1 - ry0, z1 - z0))
    body = body.makeFillet(CORNER_R, [e for e in body.Edges
                                      if abs(e.Vertexes[0].X - e.Vertexes[1].X) < 1e-6
                                      and abs(e.Vertexes[0].Y - e.Vertexes[1].Y) < 1e-6])

    def loop(z):
        return [e for e in body.Edges if all(abs(v.Z - z) < 1e-6 for v in e.Vertexes)]

    body = body.makeChamfer(TOP_CHAMFER, loop(z1))
    body = body.makeChamfer(BED_CHAMFER, loop(z0))
    return base.cut_all(body, list(tools().values()))


# --- modules/32bit stand-in (boxes and cylinders at the geometry.json positions) --------
def module32():
    parts = {}
    panel = box((mx(0), cy(panel_h), zr), (panel_w, panel_h, panel_t))
    holes = [cyl(3.1, 4, (mx(j["XY"][0]), cy(j["XY"][1]), zr - 1)) for j in geo["jacks"]]
    holes += [cyl(3.6, 4, (mx(p["shaft_XY"][0]), cy(p["shaft_XY"][1]), zr - 1)) for p in geo["pots"]]
    holes += [cyl(1.6, 4, (mx(h[0]), cy(h[1]), zr - 1)) for h in geo["rail_holes_mm"]]
    parts["m32-panel"] = panel.cut(Part.makeCompound(holes))
    zf = zr - seat                                  # carrier F.Cu
    parts["m32-pcb"] = box((mx(pcb[0]), cy(pcb[3]), zf - 1.6), (pcb[2] - pcb[0], pcb[3] - pcb[1], 1.6))
    jacks, nuts, knobs, pots = [], [], [], []
    for j in geo["jacks"]:
        x, y = mx(j["XY"][0]), cy(j["XY"][1])
        jacks.append(box((x - 4.5, y - 5.25, zf), (9.0, 10.5, seat)))
        nuts.append(cyl(3.0, panel_t + 3.0, (x, y, zr)).fuse(cyl(4.0, 2.0, (x, y, z1))))
    for p in geo["pots"]:
        x, y = mx(p["shaft_XY"][0]), cy(p["shaft_XY"][1])
        pots.append(box((x - 4.9, y - 5.5, zf), (9.8, 11.0, 6.5)).fuse(cyl(3.0, 18.0, (x, y, zf + 6.5))))
        knobs.append(cyl(5.75, 13.5, (x, y, z1 + 1.0)))
    b = geo["button"]["XY"]
    knobs.append(cyl(3.25, 3.0, (mx(b[0]), cy(b[1]), z1)))
    led = geo["leds"][0]["XY"]
    nuts.append(cyl(1.5, panel_t + 0.3, (mx(led[0]), cy(led[1]), zr)))
    parts["m32-jacks"] = Part.makeCompound(jacks + pots)
    parts["m32-nuts"] = Part.makeCompound(nuts)
    parts["m32-knobs"] = Part.makeCompound(knobs)
    # back side: USB-C shell (opening towards the case back) and the power header
    zb = zf - 1.6
    shell = box((usb_x - USB_BODY[0] / 2, usb_y - USB_BODY[1], zb - USB_BODY[2]), USB_BODY)
    ph = geo["power_header"]
    hdr = box((mx(ph["column_X_mm"][0]) - 2.5, cy(ph["pin_rows_Y_mm"][0]) - 1.3, zb - 8.5),
              (7.6, ph["pin_rows_Y_mm"][0] - ph["pin_rows_Y_mm"][-1] + 2.6, 8.5))
    parts["m32-back"] = Part.makeCompound([shell, hdr])
    return parts


def usb_plug():
    """Straight USB-C plug in the socket: overmold, strain relief, cable (towards +Y)."""
    y = usb_y + 0.5                                  # overmold face just off the shell face
    over = box((usb_x - PLUG_W / 2, y, usb_z - PLUG_H / 2), (PLUG_W, PLUG_L, PLUG_H))
    over = over.makeFillet(2.0, [e for e in over.Edges if abs(e.Vertexes[0].Y - e.Vertexes[1].Y) > 1])
    relief = cyl(2.9, 12.0, (usb_x, y + PLUG_L, usb_z), (0, 1, 0))
    cable = cyl(1.9, 45.0, (usb_x, y + PLUG_L + 12.0, usb_z), (0, 1, 0))
    return over, Part.makeCompound([relief, cable])


def hardware():
    """Screws and spacers in place: M3 socket heads (5.5 x 3.0 head) and 5.5 AF hex spacers."""
    def screw(x, y, z_seat, length):
        return cyl(2.75, 3.0, (x, y, z_seat)).fuse(cyl(1.5, length, (x, y, z_seat - length)))

    def spacer(x, y, z_top):
        r = 5.5 / math.sqrt(3)
        w = Part.makePolygon([V(r * math.cos(math.radians(60 * i + 30)), r * math.sin(math.radians(60 * i + 30)), 0)
                              for i in range(7)])
        s = Part.Face(w).extrude(V(0, 0, base.SPACER_L))
        s.translate(V(x, y, z_top - base.SPACER_L))
        return s.cut(cyl(1.25, base.SPACER_L + 2, (x, y, z_top - base.SPACER_L - 1)))

    zs = zr - (base.SPACER_SOCKET_DEPTH - base.SPACER_L)      # spacer top, 0.2 mm under the panel
    return {
        "riser-screws": Part.makeCompound([screw(x, y, z0 + CB_FLOOR, RISER_SCREW_L) for x, y in rail_screws()]),
        "riser-spacers": Part.makeCompound([spacer(x, y, zs) for x, y in module_screws()]),
        "m32-screws": Part.makeCompound([screw(x, y, z1, MODULE_SCREW_L) for x, y in module_screws()]),
    }


# --- neighbours: plain panels with a generic jack / knob pattern (not real modules) --------
def neighbours():
    panels, knobs, nuts = [], [], []
    left = [6, 6, 4]
    right = [6, 6, 6]
    assert sum(left) == SCENE_SLOT_HP and SCENE_SLOT_HP + RISER_HP + sum(right) == d.hp
    x = d.row_x0
    for hp in left + [None] + right:
        if hp is None:
            x += RISER_HP * HP
            continue
        w = hp * HP - SIDE_GAP
        panels.append(box((x, 0, d.top), (w, PANEL_H, d.panel_t)))
        cols = [5.5, w - 5.5] if hp >= 6 else [w / 2]
        kcols = [7.5, w - 7.5] if hp >= 6 else [w / 2]
        for c in cols:
            for py in (18.0, 32.0, 104.0):
                nuts.append(cyl(3.0, d.panel_t + 3.0, (x + c, cy(py), d.top))
                            .fuse(cyl(4.0, 2.0, (x + c, cy(py), d.case_top))))
        for c in kcols:
            for py in (52.0, 80.0):
                knobs.append(cyl(5.75, 13.5, (x + c, cy(py), d.case_top + 1.0)))
        x += hp * HP
    return {"nb-panels": Part.makeCompound(panels), "nb-knobs": Part.makeCompound(knobs),
            "nb-nuts": Part.makeCompound(nuts)}


# --- checks -----------------------------------------------------------------------
def shared(a, b):
    return sum(s.common(b).Volume for s in (a.Solids or [a]))


def gap(a, b):
    return round(a.distToShape(b)[0], 3)


def moved(shape, dx=0.0, dy=0.0, dz=0.0):
    s = shape.copy()
    s.translate(V(dx, dy, dz))
    return s


def print_pose(shape):
    """As it sits on the rails, moved to the bed origin."""
    return moved(shape, -rx0, -ry0, -z0)


def overhangs(posed):
    """Downward faces of the print pose, from the mesh: bed contact, and anything past 45 degrees
    must be the USB slot roof (a bridge between the block and the leg)."""
    mesh = MeshPart.meshFromShape(Shape=posed, LinearDeflection=0.01, AngularDeflection=0.1)
    bed = steep = worst = 0.0
    roof_z = slot_top - z0
    for f in mesh.Facets:
        nz = f.Normal.z
        if nz > -1e-6:
            continue
        zs = [p[2] for p in f.Points]
        if max(zs) < 1e-6:
            bed += f.Area
            continue
        angle = math.degrees(math.asin(min(1.0, -nz)))   # 0 = vertical wall, 90 = flat ceiling
        if angle > 46.0:                                 # 45 degree chamfers on the round corners: cone facets
            assert all(abs(z - roof_z) < 1e-6 for z in zs), f"unsupported face at z {zs}, {angle:.2f} deg"
            steep += f.Area
        else:
            worst = max(worst, angle)
    roof_len = ry1 - rail_in[1]
    assert abs(steep - SLOT_W * roof_len) < 0.01, f"bridge area {steep:.2f} mm2"
    return {"bed_contact_mm2": round(bed, 1), "worst_overhang_from_vertical_deg": round(worst, 2),
            "bridges": [{"what": "USB slot roof", "span_mm": SLOT_W, "length_mm": round(roof_len, 2),
                         "height_over_bed_mm": round(roof_z, 2),
                         "supported_on": "both long sides (the end block and the leg)"}],
            "other_area_past_45_deg_mm2": 0, "supports_required": False}


def export_part(shape, path):
    bb = shape.BoundBox
    dims = [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]
    assert max(dims) <= base.BED - 4, (path.name, "bed", dims)
    assert abs(bb.XMin) < 1e-6 and abs(bb.YMin) < 1e-6 and abs(bb.ZMin) < 1e-6, (path.name, "origin")
    result = base.export(shape, path)
    for ext in (".stl", ".3mf"):
        m = Mesh.Mesh(str(path.with_suffix(ext)))
        assert m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections(), path.name + ext
        assert abs(m.Volume - shape.Volume) / shape.Volume < 0.002, path.name + ext + " volume"
        assert abs(m.BoundBox.ZMin) < 1e-5, "mesh does not touch the print bed"
    saved = Part.Shape()
    saved.read(str(path.with_suffix(".step")))
    assert saved.isValid() and len(saved.Solids) == 1, path.name + " STEP readback"
    assert saved.cut(shape).Volume + shape.cut(saved).Volume < TOL
    return {"print_bounds_mm": dims, "solid_volume_cm3": round(shape.Volume / 1000, 2),
            "STEP_STL_3MF_readback": "PASS", **result}


def save_native(path, objects):
    doc = App.newDocument(path.stem.replace("-", "_"))
    for name, shape in objects.items():
        obj = doc.addObject("Part::Feature", name.replace("-", "_"))
        obj.Shape = shape
        obj.addProperty("App::PropertyString", "Regenerate", "Build metadata")
        obj.Regenerate = "mechanical/case/tools/build_usb_riser.sh; dimensions in build_usb_riser.py"
    doc.recompute()
    tmp = path.with_name("." + path.name)
    doc.saveAs(str(tmp))
    App.closeDocument(doc.Name)
    check = App.openDocument(str(tmp))
    for name, expected in objects.items():
        got = check.getObject(name.replace("-", "_")).Shape
        assert got.isValid() and abs(got.Volume - expected.Volume) < TOL, name + " FCStd reload"
    App.closeDocument(check.Name)
    tmp.replace(path)


def main():
    for folder in (OUT, RESEARCH, CASE / "cad"):
        folder.mkdir(parents=True, exist_ok=True)
    doc = App.openDocument(str(CASE / "cad" / "assembly.FCStd"))
    case = {f"case-{o.Name}": o.Shape.copy() for o in doc.Objects if hasattr(o, "Shape")}
    App.closeDocument(doc.Name)
    for i in (0, 1):
        case[f"case-cover_{i}"] = base.cover_blank(d, i)

    r = riser()
    assert r.isValid() and len(r.Solids) == 1 and len(r.Shells) == 1
    cuts = tools()
    mod = module32()
    over, lead = usb_plug()
    nb = neighbours()
    hw = hardware()
    parts = {**case, **nb, "riser": r, **mod, **hw, "usb-plug": over, "usb-cable": lead}
    checks = {}

    # 1. nothing shares volume with the riser
    against = ("m32-panel", "m32-pcb", "m32-jacks", "m32-back", "m32-nuts", "m32-screws", "usb-plug",
               "usb-cable", "nb-panels", "nb-nuts", "nb-knobs", "riser-screws", "riser-spacers",
               "case-rail_front", "case-rail_back", "case-side_panel_left", "case-side_panel_right",
               "case-cover_0", "case-cover_1", "case-bottom_plate")
    clash = {n: round(shared(parts[n], r), 4) for n in against if shared(parts[n], r) > TOL}
    assert not clash, f"riser clashes: {clash}"
    for n in ("case-rail_back", "m32-pcb", "m32-panel", "m32-back"):
        assert shared(over, parts[n]) < TOL, f"plug clashes with {n}"
    checks["collisions"] = {"riser_against": list(against), "shared_volume_mm3": 0}

    # 2. it sits on both rails and on nothing else; the panel sits on the pocket floor
    rb = r.BoundBox
    assert abs(rb.ZMin - z0) < 1e-6 and abs(rb.ZMax - z1) < 1e-6
    foot = r.common(box((rx0 - 1, ry0 - 1, z0 - 0.01), (rx1 - rx0 + 2, ry1 - ry0 + 2, 0.02)))
    on_rail = sum(foot.common(box((rx0 - 1, y, z0 - 1), (rx1 - rx0 + 2, d.rail_w, 2))).Volume
                  for y in d.rail_y) / 0.01
    seat_area = r.common(box((mx(0), cy(panel_h), zr - 0.01), (panel_w, panel_h, 0.01))).Volume / 0.01
    assert gap(r, parts["m32-panel"]) < 1e-6 and seat_area > 300
    checks["seating"] = {
        "footprint_on_the_rails_mm2": round(on_rail, 1),
        "panel_seat_on_the_end_blocks_mm2": round(seat_area, 1),
        "panel_seat": "both end blocks, as on the rails; the long sides are a close fit, not a ledge",
        "panel_edge_over_the_side_walls_mm": round(pcb[0] - CAVITY_CLR, 2),
        "riser_top_flush_with_module_panel": True,
        "riser_top_above_neighbour_panels_mm": round(z1 - d.case_top, 2)}

    # 3. clearances
    checks["clearances_mm"] = {
        "panel_in_pocket_each_side": POCKET_CLR,
        "carrier_in_cavity_each_side": gap(r, parts["m32-pcb"]),
        "carrier_ends_to_end_blocks": round(pcb[1] - (PANEL_H - rail_in[1]), 2),
        "jacks_and_pots_to_riser": gap(r, parts["m32-jacks"]),
        "usb_socket_and_power_header_to_riser": gap(r, parts["m32-back"]),
        "riser_to_neighbour_panels": gap(r, parts["nb-panels"]),
        "plug_to_slot_walls": gap(over, r),
        "plug_under_slot_roof": round(slot_top - (usb_z + PLUG_H / 2), 2),
        "plug_over_rail_top": gap(over, parts["case-rail_back"]),
        "plug_to_carrier_edge": gap(over, parts["m32-pcb"]),
        "carrier_underside_above_rail_top": round(zr - seat - 1.6 - z0, 2)}
    c = checks["clearances_mm"]
    assert abs(c["carrier_in_cavity_each_side"] - CAVITY_CLR) < 1e-3
    assert c["plug_to_slot_walls"] >= 0.5 and c["plug_over_rail_top"] >= 1.0
    assert c["jacks_and_pots_to_riser"] >= 0.5 and c["usb_socket_and_power_header_to_riser"] >= 1.0
    assert abs(c["riser_to_neighbour_panels"] - SIDE_GAP) < 1e-3

    # 4. walls left between the cuts and to the faces
    hex_r = base.SPACER_SOCKET_AF / math.sqrt(3)
    rs, ms = rail_screws(), module_screws()
    walls = {
        "counterbore_to_module_spacer": min(gap(cuts[f"counterbore_{k}"], cuts[f"spacer_{j}"])
                                            for k in range(3) for j in range(2)),
        "leg_right_of_usb_slot": round(rx1 - (usb_x + SLOT_W / 2), 2),
        "usb_slot_to_module_spacer": gap(cuts["usb_slot"], cuts["spacer_0"]),
        # ms[0] / rs[0] are at the back rail, the others at the front; the hex corners point along Y
        "module_spacer_to_end_block_faces": round(min(ry1 - (ms[0][1] + hex_r), ms[0][1] - hex_r - rail_in[1],
                                                      ms[1][1] - hex_r - ry0, rail_in[0] - (ms[1][1] + hex_r)), 2),
        "counterbore_to_end_block_faces": round(min(ry1 - (rs[0][1] + base.M3_CB_D / 2),
                                                    rs[0][1] - base.M3_CB_D / 2 - rail_in[1],
                                                    rs[1][1] - base.M3_CB_D / 2 - ry0,
                                                    rail_in[0] - (rs[1][1] + base.M3_CB_D / 2)), 2),
        "floor_under_riser_screw_heads": CB_FLOOR,
        "beam_over_usb_slot": round(zr - slot_top, 2),
        "side_wall_left": round(mx(pcb[0]) - CAVITY_CLR - rx0, 2),
        "side_wall_right": round(rx1 - (mx(pcb[2]) + CAVITY_CLR), 2),
        "rim_left": round(mx(0) - POCKET_CLR - rx0, 2),
        "rim_right": round(rx1 - (mx(panel_w) + POCKET_CLR), 2),
        "rim_ends": round(cy(panel_h) - POCKET_CLR - ry0, 2)}
    assert walls["counterbore_to_module_spacer"] >= 1.2, walls
    assert walls["leg_right_of_usb_slot"] >= 1.6, walls
    assert min(v for v in walls.values()) >= 1.2, walls
    checks["walls_mm"] = walls

    # 5. hardware: spacer pocket depth, thread engagement
    x, y = ms[0]
    probe = V(x + 1.9, y, 0)                         # beside the vent, inside the hex
    floor = zr - base.SPACER_SOCKET_DEPTH
    assert not r.isInside(V(probe.x, probe.y, floor + 0.05), 1e-6, False)
    assert r.isInside(V(probe.x, probe.y, floor - 0.05), 1e-6, False)
    recess = base.SPACER_SOCKET_DEPTH - base.SPACER_L
    checks["hardware"] = {
        "riser_to_rails": f"3x M3x{RISER_SCREW_L:g} socket head into the rail spacers",
        "riser_screw_thread_in_rail_spacer_mm": round(RISER_SCREW_L - CB_FLOOR - recess, 2),
        "module_to_riser": f"2x M3x{base.SPACER_L:g} hex spacer (5.5 AF, superglued) + the module's 2x M3x{MODULE_SCREW_L:g}",
        "module_screw_thread_in_spacer_mm": round(MODULE_SCREW_L - panel_t - recess, 2),
        "spacer_socket": f"{base.SPACER_SOCKET_AF} AF x {base.SPACER_SOCKET_DEPTH} deep, as the rails, M3 vent to the rail face",
        "counterbore_mm": [base.M3_CB_D, round(zr - z0 - CB_FLOOR, 2)],
        "riser_screws_x_from_riser_left_edge_y": [[round(sx - slot_x, 2), sy] for sx, sy in rs],
        "module_screw_x_from_riser_left_edge": round(ms[0][0] - slot_x, 2),
        "riser_screws_hidden_under_the_module_panel": all(
            mx(0) < sx < mx(panel_w) and cy(panel_h) < sy < cy(0) for sx, sy in rs)}
    assert checks["hardware"]["riser_screw_thread_in_rail_spacer_mm"] >= 3.5
    assert checks["hardware"]["module_screw_thread_in_spacer_mm"] >= 3.5
    assert checks["hardware"]["riser_screws_hidden_under_the_module_panel"]

    # 6. it goes together: riser screws and the module drop in from above, the plug comes in level
    module = [mod[n] for n in ("m32-panel", "m32-pcb", "m32-jacks", "m32-back")]
    for k in range(1, 31):
        for s in module:
            assert shared(moved(s, dz=k), r) < TOL, f"module catches the riser {k} mm up"
        assert shared(moved(hw["riser-screws"], dz=k), r) < TOL, f"riser screw catches {k} mm up"
        assert shared(moved(hw["riser-spacers"], dz=k), r) < TOL, f"spacer catches {k} mm up"
    for k in range(1, 41):
        p = moved(over, dy=k)
        for n in ("riser", "case-rail_back", "m32-pcb", "m32-panel", "case-side_panel_right"):
            assert shared(p, parts[n]) < TOL, f"plug catches {n} {k} mm out"
    checks["assembly_motion"] = {"module_lifts_straight_out_mm": 30, "riser_screws_and_spacers_drop_in": True,
                                 "plug_slides_straight_out_mm": 40, "collisions": 0}
    checks["usb"] = {
        "slot_mm": [SLOT_W, round(slot_top - z0, 2)],
        "plug_modelled_mm": [PLUG_W, PLUG_H, PLUG_L],
        "plug_overmold_past_case_back_mm": round(usb_y + 0.5 + PLUG_L - ry1, 2),
        "plug_and_relief_past_case_back_mm": round(usb_y + 0.5 + PLUG_L + 12.0 - ry1, 2),
        "row": "the module's top edge must face the outside of the case (back row of a 2 x 2 set)"}

    # 7. any even HP slot: the riser screws land on rail spacers there too
    sockets = d.module_hole_x()
    slots = [hp for hp in range(0, d.hp - RISER_HP + 1, 2)
             if all(min(abs(d.row_x0 + hp * HP + sx - slot_x - s) for s in sockets) < 1e-6 for sx, _ in rs)]
    assert slots == list(range(0, d.hp - RISER_HP + 1, 2))
    checks["row_positions"] = {"riser_slot_start_hp": slots, "module_left_edge_in_riser_mm": MOD_DX,
                               "module_centred_in_riser": False}

    # --- exports --------------------------------------------------------------------
    posed = print_pose(r)
    checks["print"] = overhangs(posed)
    for old in list(OUT.glob(NAME + ".*")):
        old.unlink()
    exports = {NAME: export_part(posed, OUT / NAME)}
    save_native(CASE / "cad" / "usb-riser-parts.FCStd", {NAME: posed})
    save_native(CASE / "cad" / "usb-riser-assembly.FCStd", {k.replace("case-", ""): v for k, v in parts.items()})

    # preview meshes (ignored research folder)
    def stl(shape, name):
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.03, AngularDeflection=0.15).write(str(RESEARCH / name))

    for old in RESEARCH.glob("*.stl"):
        old.unlink()
    for name, s in parts.items():
        stl(s, f"{name}.stl")
    stl(posed, "print-riser.stl")
    # sections: through the USB centre line (keep X below it), and along the front rail hole line
    half_usb = box((-100, -100, -10), (100 + usb_x, 400, 200))
    half_rail = box((-100, d.hole_y[0], -10), (500, 400, 200))
    for name, s in parts.items():
        for tag, half in (("secu", half_usb), ("secf", half_rail)):
            if tag == "secf" and name.startswith(("usb", "nb-knobs", "nb-nuts")):
                continue
            cut = s.common(half)
            if cut.Volume > TOL:
                stl(cut, f"{tag}-{name}.stl")
    (RESEARCH / "camera.json").write_text(json.dumps({
        "cx": (rx0 + rx1) / 2, "cy": PANEL_H / 2, "z0": z0, "zr": zr, "z1": z1, "ux": usb_x, "uy": usb_y,
        "uz": usb_z, "case_cx": d.L / 2, "back_y": ry1, "size": exports[NAME]["print_bounds_mm"],
        "riser_screws": rs, "module_screws": ms}) + "\n")

    rel = f"print/accessories/usb-riser/{NAME}"
    sources = ["tools/build_usb_riser.py", "tools/build_usb_riser.sh", "tools/build_case.py", "cad/assembly.FCStd"]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    report = {
        "status": "PASS",
        "prototype": "CAD-checked against a stand-in of modules/32bit: not printed, fits not measured",
        "for": "modules/32bit (6 HP) in the 42 HP / 60 mm case",
        "dimensions": {
            "riser_hp": RISER_HP, "lift_mm": LIFT,
            "size_mm": exports[NAME]["print_bounds_mm"],
            "panel_pocket_mm": [panel_w + 2 * POCKET_CLR, panel_h + 2 * POCKET_CLR, panel_t],
            "cavity_mm": [round(pcb[2] - pcb[0] + 2 * CAVITY_CLR, 2), round(rail_in[1] - rail_in[0], 2)],
            "outer_corner_radius_mm": CORNER_R, "top_chamfer_mm": TOP_CHAMFER, "bed_chamfer_mm": BED_CHAMFER},
        "checks": checks, "print": exports,
        "source_sha256": {p: sha(CASE / p) for p in sources}
                         | {"modules/32bit/docs/geometry.json": sha(REPO / "modules/32bit/docs/geometry.json")},
        "export_sha256": {rel + ext: sha(CASE / (rel + ext)) for ext in (".step", ".stl", ".3mf")},
        "limits": ["not printed or fit-tested",
                   "module, plug and neighbours are stand-ins (boxes at the geometry.json positions)",
                   "plug: USB-IF maximum overmold section 12.35 x 6.5 mm; a thicker plug may not pass",
                   "the plug overmold ends 0.15 mm from the carrier's top edge in the model (board placement, "
                   "not the riser): a tall overmold may stop just short of fully seated"]}
    data = json.dumps(report, indent=2) + "\n"
    (OUT / "verification.json").write_text(data)
    (RESEARCH / "build-report.json").write_text(data)
    print("USB_RISER_BUILD_PASS", flush=True)


# FreeCADCmd imports scripts by stem, unlike CPython's __main__.
if __name__ == "__main__" or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
