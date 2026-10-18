"""FreeCAD generator for the 3D-printed Eurorack skiff (Bambu Lab P2S).

Run with FreeCAD's headless interpreter (see case/tools/build.sh):
  case/tools/build.sh                         # 42 HP, 70 mm clear depth
  CASE_HP=36 CASE_DEPTH=60 case/tools/build.sh

Assembly frame (all dimensions mm):
  X  along the rails (module row, left -> right); X = 0 is the inner face of the left side panel
  Y  across the rails (the 3U / 128.5 mm module height direction); Y = 0 is the module panel
     front edge. The rails and the case reach RAIL_OH past both panel edges (Y < 0, Y > 128.5)
  Z  up; Z = 0 is the floor under the bottom plate

Modules lie flat: their front panels rest on top of the rails, parallel to the bottom plate.
Each module screw goes into a 10 mm M3 hex spacer superglued in a hex socket in the rail.
The rail ends drop into notches at the top of the side panels; a horizontal M3 through the side
panel wall goes into a hex spacer superglued in the rail end.
"""

import json
import math
import os
import sys
import time
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = Path(os.environ.get("CASE_DIR", Path(__file__).resolve().parents[1]))

# --- Eurorack (Doepfer A-100) ---------------------------------------------
HP = 5.08            # horizontal pitch
PANEL_H = 128.5      # 3U panel height
HOLE_PITCH_Y = 122.5  # rail hole line to rail hole line
HOLE_EDGE = 3.0      # hole centre to panel top/bottom edge
HOLE_X0 = 7.5        # first panel hole from the module's left edge
RAIL_GAP_MIN = 112.5  # clear space between rails (PCBs up to ~110)

# --- Bambu Lab P2S ---------------------------------------------------------
BED = 256.0          # 256 x 256 x 256 build volume

# --- Fasteners -------------------------------------------------------------
M3_CLEAR = 3.4       # ISO 273 normal clearance
M3_CB_D = 6.5        # socket head counterbore
M3_CB_DEPTH = 3.2

# 10 mm M3 female hex spacer, superglued into a blind hex socket (as the Bread Modular case base
# corners: measured there as 5.7 across flats, 10.2 deep, closed end)
SPACER_L = 10.0
SPACER_SOCKET_AF = 5.7     # 5.5 AF spacer + 0.2 for print and glue
SPACER_SOCKET_DEPTH = SPACER_L + 0.2
SPACER_WALL = (10.0 - SPACER_SOCKET_AF) / 2   # 2.15: same walls as the side panel sockets
# rails are centred on the hole line, so they reach this far past the module panel edges
RAIL_OH = SPACER_SOCKET_AF / 2 + SPACER_WALL - HOLE_EDGE


class Dims:
    def __init__(self, hp, depth, row_gap):
        self.hp = hp
        self.row_gap = row_gap                  # free play across the whole module row
        # rail spacer sockets every 2 HP from the first module hole. The inner width puts the last
        # socket as far from the right panel as the first is from the left, so a rail turned end for
        # end is the same part: one rail file, print 2. The width left over past the module row
        # (about 1 HP at 42 HP) is free space on the right.
        self.hole_x0 = row_gap / 2 + HOLE_X0
        self.n_sockets = math.ceil((hp * HP + row_gap - 2 * self.hole_x0) / (2 * HP) - 1e-9) + 1
        self.L = 2 * self.hole_x0 + (self.n_sockets - 1) * 2 * HP   # inner width between side panels
        self.spare = self.L - (hp * HP + row_gap)
        # side panel
        self.T = 12.0                           # side panel thickness (X)
        self.depth = depth                      # side panel height = clear depth under the rails
        # rail
        self.rail_w = SPACER_SOCKET_AF + 2 * SPACER_WALL   # Y, centred on the hole line
        self.rail_floor = 1.8                   # under the spacer socket
        self.rail_h = SPACER_SOCKET_DEPTH + self.rail_floor  # Z
        # rail end engaged in the side panel notch: long enough that the end spacer socket
        # (10.2 deep along X) keeps a wall to the first module socket
        self.tenon = 8.0
        self.notch_clr = 0.2                    # notch clearance on X and on the inner Y wall
        # bottom plate
        self.P = 5.0                            # plate thickness
        self.wall = 3.0                         # socket wall thickness
        self.socket_h = 8.0                     # socket wall height above the plate
        self.socket_clr = 0.3                   # side panel to socket total clearance (X)
        self.frame = 20.0                       # plate frame width around the centre window
        # bolts side panel -> plate
        self.bolt_y = (25.0, PANEL_H - 25.0)

        self.y0 = -RAIL_OH                      # case front edge
        self.ylen = PANEL_H + 2 * RAIL_OH       # case depth (Y) of side panels and bottom plate
        self.top = self.P + self.depth          # rail top / module panel underside
        self.hole_y = (HOLE_EDGE, PANEL_H - HOLE_EDGE)   # front and back module hole lines
        self.rail_y = tuple(y - self.rail_w / 2 for y in self.hole_y)   # rail Y origins
        self.plate_x0 = -self.T - self.wall - self.socket_clr / 2
        self.plate_len = self.L + 2 * (self.T + self.wall) + self.socket_clr
        self.rail_len = self.L + 2 * self.tenon

        assert self.rail_y[1] - (self.rail_y[0] + self.rail_w) >= RAIL_GAP_MIN - 1e-9
        for size, what in ((self.plate_len, "bottom plate"), (self.rail_len, "rail")):
            if size > BED - 4:
                sys.exit(f"{what} is {size:.1f} mm: does not fit the P2S bed ({BED} mm); lower CASE_HP")

    def module_hole_x(self):
        """Rail spacer X positions: every 2 HP, symmetric about the rail centre. All modules are
        2N HP wide and sit on even HP slots, so each module's left hole lands on a spacer."""
        return [self.hole_x0 + k * 2 * HP for k in range(self.n_sockets)]

    def screws(self):
        """Shortest standard M3 lengths that reach ~4 mm into the hex spacer."""
        def pick(need):
            return next(s for s in (6, 8, 10, 12, 14, 16, 20) if s >= need)
        # side panel outer wall, notch clearance, 0.2 mm spacer recess, ~4 mm into the spacer
        rail_need = (self.T - self.tenon - self.notch_clr) + self.notch_clr + (SPACER_SOCKET_DEPTH - SPACER_L) + 4
        # through the plate under the counterbore and the 0.2 mm recess, then ~4 mm into the spacer
        plate_need = (self.P - M3_CB_DEPTH) + (SPACER_SOCKET_DEPTH - SPACER_L) + 4
        return {
            "side_panel_to_rail": f"4x M3x{pick(rail_need)} socket head into "
                                  f"4x M3x{SPACER_L:g} hex spacer (superglued in the rail ends)",
            "bottom_plate_to_side_panel": f"4x M3x{pick(plate_need)} socket head into "
                                          f"4x M3x{SPACER_L:g} hex spacer (superglued in the side panels)",
            "module_to_rail": f"M3x6 into {2 * len(self.module_hole_x())}x M3x{SPACER_L:g} hex spacer "
                              "(superglued in the rails; glue only the positions you use), 2 per module",
        }

    def summary(self):
        xs = self.module_hole_x()
        return {
            "hp": self.hp,
            "inner_width_mm": round(self.L, 3),
            "spare_width_right_of_module_row_mm": round(self.spare, 3),
            "clear_depth_under_rails_mm": self.depth,
            "rail_length_mm": round(self.rail_len, 3),
            "rail_section_mm": [self.rail_w, self.rail_h],
            "rail_spacer_sockets_per_rail": len(xs),
            "rail_spacer_pitch_mm": 2 * HP,
            "first_rail_hole_x_mm": round(xs[0], 3),
            "last_rail_hole_to_right_panel_mm": round(self.L - xs[-1], 3),
            "rail_hole_line_spacing_mm": HOLE_PITCH_Y,
            "rail_overhang_past_module_edge_mm": round(RAIL_OH, 3),
            "clear_gap_between_rails_mm": round(self.rail_y[1] - self.rail_y[0] - self.rail_w, 3),
            "module_holes": f"{SPACER_SOCKET_AF} AF x {SPACER_SOCKET_DEPTH} deep hex socket for a "
                            f"M3x{SPACER_L:g} hex spacer, {self.rail_floor} mm floor with M3 vent hole",
            "side_panel_mm": [self.T, round(self.ylen, 3), self.depth],
            "bottom_plate_mm": [round(self.plate_len, 3), round(self.ylen, 3), self.P],
            "overall_mm": [round(self.plate_len, 3), round(self.ylen, 3), self.top],
            "hardware": self.screws(),
        }


# --- primitives --------------------------------------------------------------

def box(corner, size):
    return Part.makeBox(size[0], size[1], size[2], V(*corner))


def cyl(r, h, base, axis=(0, 0, 1)):
    return Part.makeCylinder(r, h, V(*base), V(*axis))


def cut_all(shape, tools):
    """Boolean cut, then ShapeFix if BRepCheck flags the result (fix() does not move geometry)."""
    r = shape.cut(Part.makeCompound(tools)).removeSplitter()
    if not r.isValid():
        r.fix(1e-7, 1e-7, 1e-3)
    assert r.isValid() and len(r.Solids) == 1, "cut produced an invalid shape"
    return r.Solids[0]


def spacer_socket(center_xy, z0, depth, flats="x"):
    """Hex socket for an M3 hex spacer, axis +Z from z0 to z0 + depth (overruns 1 mm below z0),
    flats facing +-X or +-Y (across the part's thin direction) so both walls are equal."""
    r = SPACER_SOCKET_AF / math.sqrt(3)
    hexw = Part.makePolygon([V(r * math.cos(a), r * math.sin(a), 0)
                             for a in [math.radians(60 * i) for i in range(7)]])
    if flats == "x":
        hexw.rotate(V(0, 0, 0), V(0, 0, 1), 30)   # vertices at 30 + 60k deg -> flats normal to X
    prism = Part.Face(hexw).extrude(V(0, 0, depth + 1))
    prism.translate(V(center_xy[0], center_xy[1], z0 - 1))
    return prism


def end_spacer_socket(x_end, sgn, y, z):
    """Spacer socket along X into a rail end face at x_end (sgn = +1: socket runs towards +X).
    Flats face +-Y, so the corners point up and down: the hole prints point-up without supports."""
    prism = spacer_socket((0, 0), 0, SPACER_SOCKET_DEPTH, "y")
    prism.rotate(V(0, 0, 0), V(0, 1, 0), 90 * sgn)   # +Z -> sgn * X
    prism.translate(V(x_end, y, z))
    return prism


# --- parts (built in assembly position) -------------------------------------

def rail(d, i):
    """Bar centred on a module hole line with a hex spacer socket every 2 HP, open at the top
    (the module side). The spacer sits 0.2 mm below the top so the module panel clamps on the
    rail. A small floor carries the spacer; an M3 clearance vent under it lets glue and air out
    and takes a screw that is too long. Each end is a tenon that drops into a side panel notch; a
    hex spacer glued into the end face takes a screw through the side panel wall."""
    y0, hole_y = d.rail_y[i], d.hole_y[i]
    zb = d.top - d.rail_h
    s = box((-d.tenon, y0, zb), (d.rail_len, d.rail_w, d.rail_h))
    cuts = []
    for x in d.module_hole_x():
        # flats face +-Y (across the rail): corners point along the rail, where there is room
        # socket from the floor (top - depth) up through the top: the helper overruns 1 mm below z0
        cuts.append(spacer_socket((x, hole_y), d.top - SPACER_SOCKET_DEPTH + 1, SPACER_SOCKET_DEPTH, "y"))
        cuts.append(cyl(M3_CLEAR / 2, d.rail_h + 2, (x, hole_y, zb - 1)))
    mid_y, mid_z = y0 + d.rail_w / 2, zb + d.rail_h / 2
    for x_end, sgn in ((-d.tenon, 1), (d.L + d.tenon, -1)):
        cuts.append(end_spacer_socket(x_end, sgn, mid_y, mid_z))
    return cut_all(s, cuts)


def side_panel(d, left):
    """Vertical plate, 128.5 mm long (one 3U module height). The top corners have rail notches
    open to the top, the inner face and the front/back edge: the rail drops in and an M3 through
    the outer wall goes into the spacer in the rail end. The bottom edge has two blind hex sockets for
    superglued M3 hex spacers that take the bolts coming up through the bottom plate."""
    sgn = 1 if left else -1
    x_out = -d.T if left else d.L + d.T
    x_in = 0.0 if left else d.L
    s = box((min(x_out, x_in), d.y0, d.P), (d.T, d.ylen, d.depth))
    nd = d.tenon + d.notch_clr
    nw = d.rail_w + d.notch_clr
    nx = x_in - nd if left else x_in
    cuts = []
    for i, ny in enumerate((d.y0, d.y0 + d.ylen - nw)):
        cuts.append(box((nx, ny, d.top - d.rail_h), (nd, nw, d.rail_h + 1)))
        rail_mid = (d.rail_y[i] + d.rail_w / 2, d.top - d.rail_h / 2)
        cuts.append(cyl(M3_CLEAR / 2, d.T + 2, (x_out - sgn, rail_mid[0], rail_mid[1]), (sgn, 0, 0)))
    bx = x_out + sgn * d.T / 2
    for by in d.bolt_y:
        cuts.append(spacer_socket((bx, by), d.P, SPACER_SOCKET_DEPTH))
    return cut_all(s, cuts)


def bottom_plate(d):
    """Floor plate with a socket at each end that the side panels stand in, counterbored M3
    holes from underneath, and a centre window to save filament."""
    x0, w = d.plate_x0, d.wall
    sock = d.T + d.socket_clr
    s = box((x0, d.y0, 0), (d.plate_len, d.ylen, d.P))
    for sx in (x0, x0 + d.plate_len - (2 * w + sock)):
        s = s.fuse(box((sx, d.y0, d.P), (w, d.ylen, d.socket_h)))
        s = s.fuse(box((sx + w + sock, d.y0, d.P), (w, d.ylen, d.socket_h)))
    cuts = [box((d.frame, d.y0 + d.frame, -1), (d.L - 2 * d.frame, d.ylen - 2 * d.frame, d.P + 2))]
    for bx in (-d.T / 2, d.L + d.T / 2):
        for by in d.bolt_y:
            cuts.append(cyl(M3_CLEAR / 2, d.P + 2, (bx, by, -1)))
            cuts.append(cyl(M3_CB_D / 2, M3_CB_DEPTH + 1, (bx, by, -1)))
    return cut_all(s, cuts)


def print_pose(name, shape, d):
    """Move a part from its assembly position to its print orientation, corner at the origin."""
    s = shape.copy()
    if name == "side-panel":
        # outer face down: notches, spacer sockets and rail screw holes print without supports
        s.rotate(V(0, 0, 0), V(0, 1, 0), -90)
    bb = s.BoundBox
    s.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


# --- checks ------------------------------------------------------------------

def checks(d, asm):
    out = {}
    bodies = list(asm.items())
    clashes = {}
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            (na, a), (nb, b) = bodies[i], bodies[j]
            v = a.common(b).Volume
            if v > 1e-3:
                clashes[f"{na}/{nb}"] = round(v, 4)
    out["interference_mm3"] = clashes or "none"
    for name, s in asm.items():
        assert s.isValid() and len(s.Solids) == 1, f"{name}: invalid or not one solid"
    # rail spacer sockets: open at the top and the spacer length deep (probed on the axis and
    # inside the hex corners along X), floor below, solid walls across the rail
    misses = []
    for rname, hy in (("rail-front", d.hole_y[0]), ("rail-back", d.hole_y[1])):
        r = asm[rname]
        for x in d.module_hole_x():
            empty = all(not r.isInside(V(x + dx, hy, d.top - z), 1e-6, True)
                        for z in (0.1, SPACER_L / 2, SPACER_SOCKET_DEPTH - 0.05) for dx in (-3.0, 0, 3.0))
            floor = r.isInside(V(x + 2.5, hy, d.top - d.rail_h + d.rail_floor / 2), 1e-6, True)
            wall = all(r.isInside(V(x, hy + sg * (SPACER_SOCKET_AF / 2 + 0.3), d.top - 5), 1e-6, True)
                       for sg in (-1, 1))
            if not (empty and floor and wall):
                misses.append((rname, round(x, 3), empty, floor, wall))
    # rail end sockets: empty along X from the end face to the spacer length (axis and the hex
    # corners above/below), closed past it, and a solid wall left to the first module socket
    for rname, hy in (("rail-front", d.hole_y[0]), ("rail-back", d.hole_y[1])):
        r = asm[rname]
        mz = d.top - d.rail_h / 2
        for x_end, sg in ((-d.tenon, 1), (d.L + d.tenon, -1)):
            empty = all(not r.isInside(V(x_end + sg * x, hy, mz + dz), 1e-6, True)
                        for x in (0.1, SPACER_L / 2, SPACER_SOCKET_DEPTH - 0.05) for dz in (-3.0, 0, 3.0))
            closed = r.isInside(V(x_end + sg * (SPACER_SOCKET_DEPTH + 0.3), hy, mz), 1e-6, True)
            if not (empty and closed):
                misses.append((rname, "end", x_end, empty, closed))
    first_module_socket_from_end = d.tenon + d.hole_x0 - SPACER_SOCKET_AF / math.sqrt(3)
    out["rail_end_socket_to_module_socket_wall_mm"] = round(first_module_socket_from_end - SPACER_SOCKET_DEPTH, 2)
    assert out["rail_end_socket_to_module_socket_wall_mm"] >= 2.0
    out["rail_spacer_socket_misses"] = misses or "none"
    out["rail_spacer_socket_wall_mm"] = {"across_rail": SPACER_WALL,
                                         "between_sockets": round(2 * HP - 2 * SPACER_SOCKET_AF / math.sqrt(3), 2)}
    # spacer sockets: open at the panel bottom, at least the spacer length deep, closed above
    sockets = {}
    for name, x in (("side-panel-left", -d.T / 2), ("side-panel-right", d.L + d.T / 2)):
        for y in d.bolt_y:
            s = asm[name]
            empty = [not s.isInside(V(x + dx, y, d.P + z), 1e-6, True)
                     for z in (0.1, SPACER_L / 2, SPACER_L - 0.05) for dx in (-2.7, 0, 2.7)]
            closed = s.isInside(V(x, y, d.P + SPACER_SOCKET_DEPTH + 0.3), 1e-6, True)
            wall = min(s.isInside(V(x + sg * (SPACER_SOCKET_AF / 2 + 0.3), y, d.P + 5), 1e-6, True)
                       for sg in (-1, 1))
            assert all(empty) and closed and wall, (name, y, empty, closed, wall)
            sockets[f"{name}@y{y:g}"] = "ok"
    out["spacer_sockets"] = sockets
    out["spacer_socket_wall_mm"] = round((d.T - SPACER_SOCKET_AF) / 2, 2)
    assert not misses, f"rail spacer sockets wrong: {misses[:3]}"
    # one rail part: front = back moved across, and a rail turned end for end is the same solid
    r = asm["rail-front"]
    moved = asm["rail-back"].copy()
    moved.translate(V(0, d.hole_y[0] - d.hole_y[1], 0))
    turned = r.copy()
    turned.rotate(V(d.L / 2, d.hole_y[0], 0), V(0, 0, 1), 180)
    diff = {k: round(r.cut(o).Volume + o.cut(r).Volume, 4) for k, o in (("front_vs_back", moved),
                                                                          ("end_for_end", turned))}
    assert max(diff.values()) < 1e-3, f"rails are not one interchangeable part: {diff}"
    out["rail_interchangeable_diff_mm3"] = diff
    out["measured_rail_hole_line_spacing_mm"] = round(d.hole_y[1] - d.hole_y[0], 3)
    # every module position: 2N HP module at even slot s has its left hole at s*HP + 7.5 (+ row gap)
    out["module_widths_checked_hp"] = "2, 4 .. %d at every even slot" % (d.hp - d.hp % 2)
    xs = set(round(x, 6) for x in d.module_hole_x())
    for n in range(2, d.hp + 1, 2):
        for slot in range(0, d.hp - n + 1, 2):
            hx = round(d.row_gap / 2 + slot * HP + HOLE_X0, 6)
            assert hx in xs, (n, slot)
    return out


def export(shape, base):
    shape.exportStep(str(base.with_suffix(".step")))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.005, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds() and not mesh.hasSelfIntersections(), \
        f"{base.name}: mesh is not a clean closed solid"
    mesh.write(str(base.with_suffix(".stl")))
    mesh.write(str(base.with_suffix(".3mf")))
    return {"stl_facets": mesh.CountFacets, "mesh_closed_manifold": True,
            "mesh_volume_cm3": round(mesh.Volume / 1000, 2)}


def main():
    d = Dims(int(os.environ.get("CASE_HP", 42)), float(os.environ.get("CASE_DEPTH", 70)),
             float(os.environ.get("CASE_ROW_GAP", 0.5)))
    t0 = time.time()
    asm = {
        "bottom-plate": bottom_plate(d),
        "side-panel-left": side_panel(d, left=True),
        "side-panel-right": side_panel(d, left=False),
        "rail-front": rail(d, 0),
        "rail-back": rail(d, 1),
    }
    report = {"dimensions": d.summary(), "build_s": round(time.time() - t0, 1)}
    report["checks"] = checks(d, asm)

    cad, out = CASE / "cad", CASE / "print"
    for p in (cad, out, CASE / "research"):
        p.mkdir(exist_ok=True)
    doc = App.newDocument("EurorackSkiff")
    for name, s in asm.items():
        doc.addObject("Part::Feature", name.replace("-", "_")).Shape = s
    doc.saveAs(str(cad / "assembly.FCStd"))
    Part.makeCompound(list(asm.values())).exportStep(str(out / "assembly-preview.step"))

    # one print file per unique part. The right side panel is the left one turned 180 deg about
    # Z, and the back rail is the front one (either way round; checked above): print 2 of each.
    parts = {"rail": asm["rail-front"], "side-panel": asm["side-panel-left"],
             "bottom-plate": asm["bottom-plate"]}
    report["print"] = {}
    for name, s in parts.items():
        p = print_pose(name, s, d)
        bb = p.BoundBox
        mesh_info = export(p, out / name)
        report["print"][name] = {
            "qty": 1 if name == "bottom-plate" else 2,
            "bbox_mm": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
            "fits_p2s_bed": max(bb.XLength, bb.YLength, bb.ZLength) <= BED,
            "volume_cm3": round(p.Volume / 1000, 2),
            **mesh_info,
        }
    (CASE / "research" / "build-report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


main()
