"""FreeCAD generator for the 3D-printed Eurorack skiff (Bambu Lab P2S).

Run with FreeCAD's headless interpreter (see case/tools/build.sh):
  case/tools/build.sh                         # 42 HP, 60 mm side panels
  CASE_HP=36 CASE_DEPTH=50 case/tools/build.sh

Assembly frame (all dimensions mm):
  X  along the rails (module row, left -> right); X = 0 is the inner face of the left side panel
  Y  across the rails (the 3U / 128.5 mm module height direction); Y = 0 is the module panel
     front edge. The rails and the case reach RAIL_OH past both panel edges (Y < 0, Y > 128.5)
  Z  up; Z = 0 is the floor under the bottom plate

Modules lie flat: their front panels rest on top of the rails, parallel to the bottom plate. The
rails sit one module panel thickness (read from the modules' KiCad panel boards) below the side
panel top, so the module fronts are flush with the side panels.
Every module's rail hole is 1 HP off the A-100 7.5 mm phase (12.58 mm, or 2.42 mm on 2 HP), so a
module row that starts on a rail spacer begins 1 HP right of the rail origin: a 1 HP lip on top of
the left side panel, flush with the module fronts and one module panel thick, covers that gap. The
side panels are both 12 mm thick; rails and bottom plate are unchanged; the lip uses the spare width
on the right.
Each module screw goes into a 10 mm M3 hex spacer superglued in a hex socket in the rail.
The rail ends slide into notches in the top corners of the side panels from the front / back (under
the left lip too). The notches are closed on top by a roof flush with the side panel top, so both side
panel tops are one flat surface level with the module fronts; the rails cannot drop in from the top.
A horizontal M3 through the side panel wall goes into a hex spacer superglued in the rail end.
The front and back of the case stay open. Each side panel's inner face has a vertical groove near
its front and back edge for a slide-in cover plate (2 mm thick): the groove runs from the panel
bottom up into the rail notch. The rail underside and the bottom plate top have matching grooves
along X, so the cover is held on all four edges. Assembly: screw the rails into the side panels,
turn the frame upside down, slide the covers in from the open panel bottoms until their edges seat
in the rail grooves, then set the bottom plate on: the side panels drop into its sockets and the
cover edges into its grooves.
"""

import json
import math
import os
import sys
import time
from pathlib import Path

import re

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = Path(os.environ.get("CASE_DIR", Path(__file__).resolve().parents[1]))
MODULES = CASE.parent / "modules"

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


def module_panels():
    """Front panel boards of every module (modules/*/panels/front-pcb/*.kicad_pcb): board
    thickness, Edge.Cuts width/height and the rail hole X from the panel's left edge."""
    out = {}
    for f in sorted(MODULES.glob("*/panels/front-pcb/*.kicad_pcb")):
        s = f.read_text()
        thick = float(re.search(r"\(general\s*\(thickness ([\d.]+)\)", s).group(1))
        xs, ys = [], []
        for m in re.finditer(r"\(gr_(?:line|rect|arc)\s*\(start ([\d.-]+) ([\d.-]+)\)(.*?)\(layer \"([^\"]+)\"\)", s, re.S):
            if m.group(4) != "Edge.Cuts" or "(gr_" in m.group(3):
                continue
            pts = [(float(m.group(1)), float(m.group(2)))]
            pts += [(float(a), float(b)) for a, b in re.findall(r"\((?:mid|end) ([\d.-]+) ([\d.-]+)\)", m.group(3))]
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        x0, y0 = min(xs), min(ys)
        holes = []
        for m in re.finditer(r"\(footprint \"[^\"]*\"\s*\(layer[^)]*\)\s*\(uuid[^)]*\)\s*\(at ([\d.-]+) ([\d.-]+)", s):
            body = s[m.end():m.end() + 6000].split("(footprint ", 1)[0]
            if re.search(r'np_thru_hole circle\s*\(at 0 0\)\s*\(size 3\.2 3\.2\)', body):
                hy = float(m.group(2)) - y0
                if abs(hy - HOLE_EDGE) < 0.5 or abs(hy - (PANEL_H - HOLE_EDGE)) < 0.5:
                    holes.append(round(float(m.group(1)) - x0, 3))
        assert holes, f"{f}: no rail holes found"
        # one panel per module is named after the module; modules with several (blank) by file
        name = f.parts[-4] if len(list(f.parent.glob("*.kicad_pcb"))) == 1 else f.stem
        out[name] = {"thickness": thick, "width": round(max(xs) - x0, 3),
                            "height": round(max(ys) - y0, 3), "hole_x": min(holes)}
    assert out, "no module panels found"
    return out


class Dims:
    def __init__(self, hp, depth, row_gap, panels):
        self.hp = hp
        self.panels = panels
        thick = {p["thickness"] for p in panels.values()}
        assert len(thick) == 1, f"module panels differ in thickness: {thick}"
        self.panel_t = thick.pop()              # module panel board thickness above the rails
        # module rail holes sit 1 HP off the 7.5 mm phase (12.58, 2.42 on 2 HP): cover that HP on
        # the left so the first module is row_gap / 2 from the panel
        phases = {round((p["hole_x"] - HOLE_X0) % (2 * HP), 2) for p in panels.values()}
        assert phases == {HP}, f"module rail hole phases: {phases}"
        self.fill = HP                          # top lip on the left side panel's inner face
        self.lip_fillet = 4.0                   # inside fillet under the lip, between the rails
        self.lip_round = 0.5                    # round on the lip's top outer edge
        self.row_gap = row_gap                  # free play across the whole module row
        # rail spacer sockets every 2 HP from the first module hole. The inner width puts the last
        # socket as far from the right panel as the first is from the left, so a rail turned end for
        # end is the same part: one rail file, print 2. The rails (and so the inner width) are sized
        # for the bare module row; the left lip takes its 1 HP from the width left over on the
        # right, and the module row starts row_gap / 2 after the lip.
        self.hole_x0 = row_gap / 2 + HOLE_X0
        self.n_sockets = math.ceil((hp * HP + row_gap - 2 * self.hole_x0) / (2 * HP) - 1e-9) + 1
        self.L = 2 * self.hole_x0 + (self.n_sockets - 1) * 2 * HP   # inner width between side panels
        self.spare = self.L - (self.fill + hp * HP + row_gap / 2)
        if self.spare < -1e-6:
            raise ValueError(f"{hp} HP and the 1 HP left lip do not fit the {self.L:.2f} mm rails")
        # side panel
        self.T = 12.0                           # side panel thickness (X)
        self.depth = depth                      # side panel height above the bottom plate
        # rail
        self.rail_w = SPACER_SOCKET_AF + 2 * SPACER_WALL   # Y, centred on the hole line
        self.rail_groove_d = 1.5                # cover groove in the rail underside (Z)
        self.rail_floor = 1.8 + self.rail_groove_d   # under the spacer socket; 1.8 left over the groove
        self.rail_h = SPACER_SOCKET_DEPTH + self.rail_floor  # Z
        # rail end engaged in the side panel notch: long enough that the end spacer socket
        # (10.2 deep along X) keeps a wall to the first module socket
        self.tenon = 8.0
        self.notch_clr = 0.2                    # notch clearance on X, on the inner Y wall and over the rail
        self.lip_clr = 0.3                      # lip fillet end to the rail notch (Y)
        # cover grooves in the side panel inner faces, front and back
        self.cover_t = 2.0                      # cover plate thickness (Y)
        self.groove_w = self.cover_t + 0.4      # groove width (Y)
        self.groove_d = 3.0                     # groove depth into the side panel (X)
        self.groove_edge = 2.0                  # side panel wall left in front of the groove (Y)
        self.cover_clr = 0.3                    # cover to every groove bottom and the plate socket walls
        self.plate_groove_d = 2.0               # cover groove in the bottom plate top (Z)
        # bottom plate
        self.P = 5.0                            # plate thickness
        self.wall = 3.0                         # socket wall thickness
        self.socket_h = 8.0                     # socket wall height above the plate
        self.socket_clr = 0.3                   # side panel to socket total clearance (X)
        self.frame = 20.0                       # plate frame width around the centre pocket
        self.skin = 1.2                         # floor left under the centre pocket
        # bolts side panel -> plate
        self.bolt_y = (25.0, PANEL_H - 25.0)

        self.y0 = -RAIL_OH                      # case front edge
        self.ylen = PANEL_H + 2 * RAIL_OH       # case depth (Y) of side panels and bottom plate
        self.case_top = self.P + self.depth     # side panel top = module panel front
        self.top = self.case_top - self.panel_t  # rail top / module panel underside
        self.hole_y = (HOLE_EDGE, PANEL_H - HOLE_EDGE)   # front and back module hole lines
        self.rail_y = tuple(y - self.rail_w / 2 for y in self.hole_y)   # rail Y origins
        self.plate_x0 = -self.T - self.wall - self.socket_clr / 2
        self.plate_len = self.L + 2 * (self.T + self.wall) + self.socket_clr
        self.row_x0 = self.fill + row_gap / 2  # first module's left edge
        self.rail_len = self.L + 2 * self.tenon
        self.groove_y = (self.y0 + self.groove_edge, self.y0 + self.ylen - self.groove_edge - self.groove_w)
        self.socket_in_x = self.plate_x0 + 2 * self.wall + self.T + self.socket_clr   # inner socket wall face
        self.cover_z0 = self.P - self.plate_groove_d + self.cover_clr   # cover bottom edge
        self.cover_z1 = self.top - self.rail_h + self.rail_groove_d - self.cover_clr   # cover top edge

        assert self.rail_y[1] - (self.rail_y[0] + self.rail_w) >= RAIL_GAP_MIN - 1e-9
        for size, what in ((self.plate_len, "bottom plate"), (self.rail_len, "rail")):
            if size > BED - 4:
                raise ValueError(f"{what} is {size:.1f} mm: does not fit the P2S bed ({BED} mm); lower CASE_HP")

    def module_hole_x(self):
        """Rail spacer X positions: every 2 HP, symmetric about the rail centre. All modules are
        2N HP wide and sit on even HP slots, so each module's left hole lands on a spacer."""
        return [self.hole_x0 + k * 2 * HP for k in range(self.n_sockets)]

    def cover_blank_size(self):
        """Front/back cover plate blank (X width, Y thickness, Z height) and its two bottom corner
        notches (X, Z) that clear the bottom plate's inner socket walls. Between the notches the
        bottom edge sits in the plate groove; the top edge sits in the rail groove."""
        w = self.L + 2 * (self.groove_d - self.cover_clr)
        h = self.cover_z1 - self.cover_z0
        notch = (self.groove_d - self.cover_clr + self.socket_in_x + self.cover_clr,
                 self.P + self.socket_h + self.cover_clr - self.cover_z0)
        return {"plate": [round(w, 2), self.cover_t, round(h, 2)],
                "bottom_corner_notches_x_z": [round(notch[0], 2), round(notch[1], 2)]}

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
            "side_panel_height_mm": self.depth,
            "module_panel_thickness_mm": self.panel_t,
            "rail_top_below_side_panel_top_mm": self.panel_t,
            "clear_depth_under_rails_mm": round(self.top - self.P, 3),
            "left_side_panel_top_lip_mm": [round(self.fill, 3), self.panel_t],
            "rail_notch_roof_mm": {"thickness": round(self.panel_t - self.notch_clr, 3),
                                   "clearance_over_rail": self.notch_clr,
                                   "rail_entry": "slides in from the case front / back"},
            "left_lip_inside_fillet_and_top_round_mm": [self.lip_fillet, self.lip_round],
            "first_module_left_edge_x_mm": round(self.row_x0, 3),
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
            "cover_groove_mm": {"width": self.groove_w, "depth": self.groove_d,
                                "from_case_front_back_edge": self.groove_edge,
                                "z_range": [self.P, round(self.top - self.rail_h, 3)],
                                "rail_underside_depth": self.rail_groove_d,
                                "bottom_plate_depth": self.plate_groove_d,
                                "cover_edge_engagement_rail_plate": [round(self.rail_groove_d - self.cover_clr, 2),
                                                                     round(self.plate_groove_d - self.cover_clr, 2)]},
            "cover_plate_blank_mm": self.cover_blank_size(),
            "bottom_plate_mm": [round(self.plate_len, 3), round(self.ylen, 3), self.P],
            "bottom_plate_centre_floor_mm": self.skin,
            "overall_mm": [round(self.plate_len, 3), round(self.ylen, 3), self.case_top],
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
    and takes a screw that is too long. Each end is a tenon that slides into a side panel notch from the front / back; a
    hex spacer glued into the end face takes a screw through the side panel wall. The underside has
    a cover groove along its full length on both sides (the cover's top edge sits in the outer
    one), so the rail stays one part either way round."""
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
    for gy in (d.groove_y[i], 2 * hole_y - d.groove_y[i] - d.groove_w):
        cuts.append(box((-d.tenon - 1, gy, zb - 1), (d.rail_len + 2, d.groove_w, d.rail_groove_d + 1)))
    return cut_all(s, cuts)


def side_panel(d, left):
    """Vertical plate, 128.5 mm long (one 3U module height). The top corners have rail notches
    open to the inner face and the front/back edge, under a roof flush with the panel top: the rail
    slides in from the front / back and an M3 through the outer wall goes into the spacer in the
    rail end. The bottom edge has two blind hex sockets for
    superglued M3 hex spacers that take the bolts coming up through the bottom plate."""
    sgn = 1 if left else -1
    x_out = -d.T if left else d.L + d.T
    x_in = 0.0 if left else d.L
    s = box((min(x_out, x_in), d.y0, d.P), (d.T, d.ylen, d.depth))
    if left:
        # 1 HP lip on top of the inner face, over the rails and flush with the module fronts. Its
        # top outer edge is rounded; between the rail notches an inside fillet under the lip ties
        # it to the wall (it prints as a ramp in the print pose, no supports)
        r, f = d.lip_round, d.lip_fillet
        lip = box((0, d.y0, d.top), (d.fill, d.ylen, d.panel_t))
        corner = box((d.fill - r, d.y0 - 1, d.case_top - r), (r + 1, d.ylen + 2, r + 1))
        corner = corner.cut(cyl(r, d.ylen + 4, (d.fill - r, d.y0 - 2, d.case_top - r), (0, 1, 0)))
        lip = lip.cut(corner)
        gy0 = d.y0 + d.rail_w + d.notch_clr + d.lip_clr
        gy1 = d.y0 + d.ylen - (d.rail_w + d.notch_clr + d.lip_clr)
        web = box((0, gy0, d.top - f), (f, gy1 - gy0, f))
        web = web.cut(cyl(f, gy1 - gy0 + 2, (f, gy0 - 1, d.top - f), (0, 1, 0)))
        s = s.fuse([lip, web]).removeSplitter()
    nd = d.tenon + d.notch_clr
    nw = d.rail_w + d.notch_clr
    nx = x_in - nd if left else x_in
    cuts = []
    for i, ny in enumerate((d.y0, d.y0 + d.ylen - nw)):
        # closed on top: the roof over the rail end is flush with the panel top, notch_clr over the
        # rail so it slides in from the front / back. On the left the clearance runs on under the lip
        cuts.append(box((nx, ny, d.top - d.rail_h), (nd, nw, d.rail_h + d.notch_clr)))
        if left:
            cuts.append(box((0, ny, d.top), (d.fill + 1, nw, d.notch_clr)))
        rail_mid = (d.rail_y[i] + d.rail_w / 2, d.top - d.rail_h / 2)
        cuts.append(cyl(M3_CLEAR / 2, d.T + 2, (x_out - sgn, rail_mid[0], rail_mid[1]), (sgn, 0, 0)))
    # cover grooves: open at the panel bottom, running up into the rail notch
    gz = d.top - d.rail_h - d.P + 1.5
    for gy in d.groove_y:
        cuts.append(box((x_in - d.groove_d if left else x_in, gy, d.P - 1), (d.groove_d, d.groove_w, gz)))
    bx = x_out + sgn * d.T / 2
    for by in d.bolt_y:
        cuts.append(spacer_socket((bx, by), d.P, SPACER_SOCKET_DEPTH))
    return cut_all(s, cuts)


def bottom_plate(d):
    """Floor plate with a socket at each end that the side panels stand in, counterbored M3
    holes from underneath, a centre pocket (open at the top, 1.2 mm floor left) to save filament,
    and a front and back cover groove between the inner socket walls."""
    x0, w = d.plate_x0, d.wall
    sock = d.T + d.socket_clr
    s = box((x0, d.y0, 0), (d.plate_len, d.ylen, d.P))
    for sx in (x0, x0 + d.plate_len - (2 * w + sock)):
        s = s.fuse(box((sx, d.y0, d.P), (w, d.ylen, d.socket_h)))
        s = s.fuse(box((sx + w + sock, d.y0, d.P), (w, d.ylen, d.socket_h)))
    cuts = [box((d.frame, d.y0 + d.frame, d.skin), (d.L - 2 * d.frame, d.ylen - 2 * d.frame, d.P))]
    for bx in (-d.T / 2, d.L + d.T / 2):
        for by in d.bolt_y:
            cuts.append(cyl(M3_CLEAR / 2, d.P + 2, (bx, by, -1)))
            cuts.append(cyl(M3_CB_D / 2, M3_CB_DEPTH + 1, (bx, by, -1)))
    gx0 = d.socket_in_x
    for gy in d.groove_y:
        cuts.append(box((gx0, gy, d.P - d.plate_groove_d), (d.L - 2 * gx0, d.groove_w, d.plate_groove_d + 1)))
    return cut_all(s, cuts)


def print_pose(name, shape, d):
    """Move a part from its assembly position to its print orientation, corner at the origin."""
    s = shape.copy()
    if name.startswith("side-panel"):
        # outer face down: notches, spacer sockets and rail screw holes print without supports
        s.rotate(V(0, 0, 0), V(0, 1, 0), -90 if name.endswith("left") else 90)
    bb = s.BoundBox
    s.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


def cover_blank(d, i):
    """Check-only front (i = 0) / back cover plate in its grooves: not exported."""
    c = d.cover_blank_size()
    w, t, h = c["plate"]
    nx, nz = c["bottom_corner_notches_x_z"]
    x0 = -(d.groove_d - d.cover_clr)
    y = d.groove_y[i] + (d.groove_w - d.cover_t) / 2
    z0 = d.cover_z0
    s = box((x0, y, z0), (w, t, h))
    return s.cut(Part.makeCompound([box((x0 - 1, y - 1, z0 - 1), (nx + 1, t + 2, nz + 1)),
                                    box((x0 + w - nx, y - 1, z0 - 1), (nx + 1, t + 2, nz + 1))]))


# --- slide-in cover plates -----------------------------------------------------
# Built flat in their print pose: X along the plate (width), Y up the plate (height), Z the 2 mm
# thickness. Every cutout goes straight through Z, so the plates print flat with no supports and
# no bridges. Front and back covers are the same part; print any two.

COVER_MARGIN = 6.0      # visible solid border: side panel inner face, rail underside, plate top
COVER_WEB = 2.0         # narrowest web between cutouts (about 4-5 perimeters at 0.4 mm)


def _prism(points):
    """Closed XY polygon extruded through the plate (Z -1 .. 3+)."""
    w = Part.makePolygon([V(x, y, -1) for x, y in points] + [V(*points[0], -1)])
    return Part.Face(w).extrude(V(0, 0, 10))


def _stadium(p0, p1, width):
    """Rounded slot between centre points p0 and p1."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    r = width / 2
    s = box((0, -r, -1), (L, width, 10)).fuse([cyl(r, 10, (0, 0, -1)), cyl(r, 10, (L, 0, -1))])
    s.rotate(V(0, 0, 0), V(0, 0, 1), math.degrees(math.atan2(y1 - y0, x1 - x0)))
    s.translate(V(x0, y0, 0))
    return s.removeSplitter()


def _hexagon(cx, cy, af):
    """Hexagon with flats facing +-X (corners up and down), so neighbours in a row share flats."""
    r = af / math.sqrt(3)
    return _prism([(cx + r * math.cos(math.radians(90 + 60 * i)), cy + r * math.sin(math.radians(90 + 60 * i)))
                   for i in range(6)])


def _rows(region, px, py, stagger):
    """Centres filling region (x0, y0, x1, y1), every row centred; staggered odd rows hold one
    centre fewer, which shifts them half a pitch."""
    x0, y0, x1, y1 = region
    ny = int((y1 - y0) / py + 1e-9) + 1
    nx = int((x1 - x0) / px + 1e-9) + 1
    oy = y0 + ((y1 - y0) - (ny - 1) * py) / 2
    out = []
    for j in range(ny):
        n = nx - 1 if stagger and j % 2 else nx
        ox = (x0 + x1) / 2 - (n - 1) * px / 2
        out += [(ox + i * px, oy + j * py) for i in range(n)]
    return out


def cover_patterns(region):
    """Cutout tools per variant, each kept inside region (x0, y0, x1, y1). The feature size is
    shrunk to the region so the outer features keep COVER_MARGIN."""
    x0, y0, x1, y1 = region
    web = COVER_WEB
    pats = {"solid": []}

    # grill: vertical rounded slots, full region height
    sw, pitch = 3.2, 3.2 + web * 1.5
    n = int((x1 - x0 - sw) / pitch) + 1
    ox = (x0 + x1) / 2 - (n - 1) * pitch / 2
    pats["grill"] = [_stadium((ox + i * pitch, y0 + sw / 2), (ox + i * pitch, y1 - sw / 2), sw) for i in range(n)]

    # honeycomb: hexagons 6 AF, rows share flats
    af = 6.0
    px, py = af + web, (af + web) * math.sqrt(3) / 2
    r = af / math.sqrt(3)
    pats["honeycomb"] = [_hexagon(cx, cy, af) for cx, cy in
                         _rows((x0 + af / 2, y0 + r, x1 - af / 2, y1 - r), px, py, True)]

    # perforated: staggered round holes
    dia = 4.5
    px = dia + web + 0.5
    pats["perforated"] = [cyl(dia / 2, 10, (cx, cy, -1)) for cx, cy in
                          _rows((x0 + dia / 2, y0 + dia / 2, x1 - dia / 2, y1 - dia / 2), px, px * math.sqrt(3) / 2, True)]

    # louvres: slanted parallelogram slots, 30 deg off vertical, flat ends on the margin lines
    slant = math.tan(math.radians(30))
    h = y1 - y0
    sw = 3.0 / math.cos(math.radians(30))          # 3.0 mm slot measured across the slant
    pitch = sw + web / math.cos(math.radians(30))
    span = sw + h * slant
    n = int((x1 - x0 - span) / pitch) + 1
    ox = (x0 + x1) / 2 - ((n - 1) * pitch + span) / 2
    pats["louvres"] = [_prism([(a, y0), (a + sw, y0), (a + sw + h * slant, y1), (a + h * slant, y1)])
                       for a in (ox + i * pitch for i in range(n))]

    # diamonds: 45 deg squares on a staggered grid, web between parallel edges
    a = 3.6                                         # centre to corner
    px = 2 * a + web * math.sqrt(2)
    pats["diamonds"] = [_prism([(cx + a, cy), (cx, cy + a), (cx - a, cy), (cx, cy - a)]) for cx, cy in
                        _rows((x0 + a, y0 + a, x1 - a, y1 - a), px, px / 2, True)]
    return pats


def cover_plates(d):
    """Cover plate blank (print pose) with each cutout pattern. The pattern region keeps
    COVER_MARGIN from the side panel inner faces, the rail underside and the bottom plate top (the
    edges hidden in the grooves come on top)."""
    c = d.cover_blank_size()
    w, t, h = c["plate"]
    nx, nz = c["bottom_corner_notches_x_z"]
    blank = box((0, 0, 0), (w, h, t)).cut(Part.makeCompound(
        [box((-1, -1, -1), (nx + 1, nz + 1, t + 2)), box((w - nx, -1, -1), (nx + 1, nz + 1, t + 2))]))
    ear = d.groove_d - d.cover_clr                    # plate edge to the side panel inner face
    low = d.P - d.cover_z0                            # bottom edge hidden in the plate groove
    high = d.cover_z1 - (d.top - d.rail_h)            # top edge hidden in the rail groove
    region = (ear + COVER_MARGIN, low + COVER_MARGIN, w - ear - COVER_MARGIN, h - high - COVER_MARGIN)
    out = {}
    for name, tools in cover_patterns(region).items():
        s = cut_all(blank, tools) if tools else blank.copy()
        border = blank.cut(box((region[0], region[1], -1), (region[2] - region[0], region[3] - region[1], t + 2)))
        assert abs(s.common(border).Volume - border.Volume) < 1e-3, f"cover-{name}: cutout in the border"
        out[name] = (s, len(tools), round(1 - s.Volume / blank.Volume, 3))
    return out, region, blank


def cover_in_assembly(d, s, i):
    """Print-pose cover moved into the front (i = 0) / back groove, as cover_blank()."""
    a = s.copy()
    a.rotate(V(0, 0, 0), V(1, 0, 0), 90)              # (X, Y, Z) -> (X, -Z, Y)
    a.translate(V(-(d.groove_d - d.cover_clr), d.groove_y[i] + (d.groove_w + d.cover_t) / 2, d.cover_z0))
    return a


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
    # cover grooves: a cover blank in each groove clears every part, and its ears sit in the
    # grooves of both side panels
    cov = {}
    for i, cname in enumerate(("cover-front", "cover-back")):
        c = cover_blank(d, i)
        hit = {n: round(c.common(b).Volume, 4) for n, b in asm.items() if c.common(b).Volume > 1e-3}
        assert not hit, f"{cname} clashes: {hit}"
        gy = d.groove_y[i] + d.groove_w / 2
        zm = (d.P + d.top - d.rail_h) / 2
        ears = [not asm[n].isInside(V(x, gy, zm), 1e-6, True) and c.isInside(V(x, gy, zm), 1e-6, True)
                for n, x in (("side-panel-left", -d.groove_d / 2), ("side-panel-right", d.L + d.groove_d / 2))]
        assert all(ears), (cname, ears)
        # top edge in the rail groove, bottom edge (between the socket walls) in the plate groove
        rname = ("rail-front", "rail-back")[i]
        edges = [c.isInside(V(x, gy, z), 1e-6, True) and not asm[n].isInside(V(x, gy, z), 1e-6, True)
                 and asm[n].isInside(V(x, gy + (1 if i else -1) * d.groove_w, z), 1e-6, True)
                 for n, z in ((rname, d.top - d.rail_h + d.rail_groove_d / 2),
                              ("bottom-plate", d.P - d.plate_groove_d / 2))
                 for x in (d.socket_in_x + 1.0, d.L / 2, d.L - d.socket_in_x - 1.0)]
        assert all(edges), (cname, "rail/plate groove", edges)
        cov[cname] = "fits, no interference"
    out["cover_grooves"] = cov
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
    # every module panel at every even HP slot from the left lip: its rail hole lands on a
    # spacer and the panel stays inside the side panels
    xs = [x for x in d.module_hole_x()]
    placed = {}
    for name, p in d.panels.items():
        n = round(p["width"] / HP)
        slots = [k for k in range(0, d.hp, 2)
                 if d.row_x0 + k * HP + p["width"] <= d.L + 1e-6]
        for k in slots:
            hx = d.row_x0 + k * HP + p["hole_x"]
            assert min(abs(hx - x) for x in xs) < 0.05, (name, k, hx)
        placed[name] = {"hp": n, "panel_mm": [p["width"], p["height"], p["thickness"]],
                        "rail_hole_x_mm": p["hole_x"], "even_slots": len(slots)}
    out["module_panels"] = placed
    out["module_row_capacity_mm"] = round(d.L - d.row_x0, 3)
    out["module_panel_top_z_mm"] = round(d.top + d.panel_t, 3)
    out["side_panel_top_z_mm"] = round(d.case_top, 3)
    # rail notch roofs: the side panel top is solid over every rail end (no hole, no step), with
    # notch_clr between the roof and the rail top
    roof = {}
    for name, x_in, sg in (("side-panel-left", 0.0, -1), ("side-panel-right", d.L, 1)):
        s = asm[name]
        for i, ry in enumerate(d.rail_y):
            pts = [(x_in + sg * dx, y) for dx in (0.5, d.tenon / 2, d.tenon - 0.1)
                   for y in (ry + 0.1, ry + d.rail_w / 2, ry + d.rail_w - 0.1)]
            solid = all(s.isInside(V(x, y, z), 1e-6, True) for x, y in pts
                        for z in (d.case_top - 0.05, d.top + d.notch_clr + 0.05))
            gap = all(not s.isInside(V(x, y, d.top + d.notch_clr / 2), 1e-6, True) for x, y in pts)
            top = s.common(box((x_in + (sg * d.tenon if sg < 0 else 0), ry, d.case_top - 0.01),
                               (d.tenon, d.rail_w, 0.02))).Volume
            assert solid and gap and abs(top - d.tenon * d.rail_w * 0.01) < 1e-6, (name, i, solid, gap, top)
            roof[f"{name}/{('front', 'back')[i]}"] = "closed, flush with the top"
    out["rail_notch_roofs"] = roof
    assert abs(out["module_panel_top_z_mm"] - out["side_panel_top_z_mm"]) < 1e-6
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
    d = Dims(int(os.environ.get("CASE_HP", 42)), float(os.environ.get("CASE_DEPTH", 60)),
             float(os.environ.get("CASE_ROW_GAP", 0.5)), module_panels())
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

    # one print file per unique part. The left side panel carries the 1 HP top lip, so the side
    # panels are two parts; the back rail is the front one (either way round; checked above).
    parts = {"rail": asm["rail-front"], "side-panel-left": asm["side-panel-left"],
             "side-panel-right": asm["side-panel-right"], "bottom-plate": asm["bottom-plate"]}
    report["print"] = {}
    for name, s in parts.items():
        p = print_pose(name, s, d)
        bb = p.BoundBox
        mesh_info = export(p, out / name)
        report["print"][name] = {
            "qty": 2 if name == "rail" else 1,
            "bbox_mm": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
            "fits_p2s_bed": max(bb.XLength, bb.YLength, bb.ZLength) <= BED,
            "volume_cm3": round(p.Volume / 1000, 2),
            **mesh_info,
        }

    # slide-in cover plates: one blank, six faces. Each is the blank minus through-cutouts, so it
    # fits both grooves as the checked blank does; checked again here in the assembly.
    covers, region, blank = cover_plates(d)
    cover_dir = out / "covers"
    cover_dir.mkdir(exist_ok=True)
    report["covers"] = {"print": "flat, 2 mm, cutouts through the plate: no supports, no bridges",
                        "qty": "2 per case (front + back), any mix",
                        "pattern_region_mm": [round(v, 2) for v in region],
                        "min_web_mm": COVER_WEB, "border_mm": COVER_MARGIN}
    for name, (s, n, open_frac) in covers.items():
        assert s.isValid() and len(s.Solids) == 1, f"cover-{name}: invalid or not one solid"
        assert s.cut(blank).Volume < 1e-3
        for i in (0, 1):
            a = cover_in_assembly(d, s, i)
            hit = {k: round(a.common(b).Volume, 4) for k, b in asm.items() if a.common(b).Volume > 1e-3}
            assert not hit, f"cover-{name} clashes: {hit}"
        bb = s.BoundBox
        report["covers"][f"cover-{name}"] = {
            "cutouts": n, "open_area_fraction": open_frac,
            "bbox_mm": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
            "fits_p2s_bed": max(bb.XLength, bb.YLength) <= BED,
            "volume_cm3": round(s.Volume / 1000, 2), "front_back_grooves": "fit, no interference",
            **export(s, cover_dir / f"cover-{name}"),
        }
    (CASE / "research" / "build-report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


main()
