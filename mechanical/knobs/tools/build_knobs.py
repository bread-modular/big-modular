"""FreeCAD generator for the 3D-printable push-on knobs for the RV09 tall trimmer pots.

Run with FreeCAD's headless interpreter (see tools/build_knobs.sh):
  mechanical/knobs/tools/build_knobs.sh

Push-on knob for the user-stock RV09 pot (Song Huei R0904N tall trimmer, shaft type KQ: plain
6 mm shaft, no bushing, no nut, KNURL_TEETH fine teeth on the top KNURL_L; the pot 3D model
tools/reference/RV09_proxy.step is the fit reference, with its shaft stretched to the
length the user measured: SHAFT_L, cross-checked by SHAFT_PAST_PANEL). Grip 4 is a solid knob
with a round blind bore and SPLINES teeth in the top SPLINE_L of it, one for every second groove
of the shaft knurl, so the knob is keyed to the shaft and cannot turn on it (user reference:
Thonk Tall Trimmer Toppers, a round tapered bore with grooves at the top that mate with the
knurl). The tooth tips close in toward the bore roof (TIP_TAPER): the teeth drop into the knurl
grooves and wedge tighter the further the knob is pushed on. There are no slits, pockets or thin
walls: the solid wall around the bore is what keeps the teeth in the grooves under torque. A fit
is the round bore and how deep the teeth reach into the knurl grooves (FITS). Grips 1 and 2
(slit sleeve with spring fingers) were loose and wobbly in the user's test prints, grip 3 (square
tapered bore, four thin walls, friction only) held but slipped on the shaft when the pot was
turned hard against its end stop. Of the first grip 4 gauge, where bore and teeth shrank
together, the loosest tile (`fit8`) dropped into the knurl and locked (all 2026-11-11): it is
REF_FIT here. The `t1` .. `t8` ladder that followed kept that tile's Ø6.2 bore and varied only the
teeth; its tightest knob, `t1`, was "not too tight" on the user's pots and the user asked for the
hole to get smaller too (2026-11-12). The `h1` .. `h8` ladder has that `t1` in the middle (MID_FIT):
toward `h1` the whole hole, bore and teeth, closes in; toward `h8` it is the old `t2` .. `t4`.

The top face has a closed pointer pocket (POINTER_W x POINTER_DEPTH) to fill with a white
paint pen. The two-colour version of every knob has no pocket: its pointer is an inlay in a second
filament (multi-material printer, sized for a Bambu Lab P2S with the 0.4 mm nozzle), INLAY_W wide
from the knob centre out to INLAY_RIM short of the edge of the top face and INLAY_DEPTH = the
first INLAY_LAYERS printed layers deep, so the print changes filament in those layers only. Its
3MF is one object with two parts (body, pointer). Fluted, slightly tapered side; the base diameter stays inside the panel's big-knob
reserve (tools/reference/panel.json big_knob, a reference panel with four big knobs in a row) and the script reports the clearances around it.

Four widths (SIZES: wide, slim, slimmer, slimmest) share the same grip and height; the solid
wall around the bore is asserted for each. Every width has its own folder with its eight fits
and its own fit gauge.

The fit gauge of a width is its eight knobs in one print, joined by break-off links and numbered
by notches in the base rim: a gauge knob is the knob of that fit, solid for solid, apart from the
notches. The first gauges were tiles with the bore in a boss. Their bores were the knobs' in CAD
(checked on the exported STEP files), but in the user's prints a tile and the knob of the same
number did not fit alike (2026-11-11). Cause not confirmed; what differed was the body around the
bore and the bore roof, where the teeth grip, 1.1 mm above the bed in a tile and 2.0 mm in a knob.

The puller is a pair of spring tongs for every width: it drops over a knob, a squeeze slides two
thin hooks under the knob base from opposite sides and the knob is pulled straight off the
shaft. The hooks only carry load at their root, beside the knob, so they can be thin enough for
the gap under it; the script checks them against every knob width, the pot and the panel neighbours.

Output frame = print orientation: Z0 = knob top face (pointer pocket) on the bed, open end
up, no supports; pointer toward -Y. The puller lies flat on its side. Writes
mechanical/knobs/<width>/*.step and *.stl, <width>/two-color/ and mechanical/knobs/puller/.
Nominal geometry only: not test-printed, no physical-fit claim.
"""

import json
import math
import os
import zipfile
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

V = App.Vector
KNOB = Path(os.environ.get('KNOB_DIR', Path(__file__).resolve().parents[1]))
REFERENCE = KNOB / 'tools/reference'
GEO = json.loads((REFERENCE / 'panel.json').read_text())
POT_MODEL = REFERENCE / 'RV09_proxy.step'
OUT = KNOB
RESEARCH = KNOB / 'research'
NAME = 'knob'

# Shell (knob frame: Z0 = open end facing the panel, Z = KNOB_H top face, pointer toward +Y)
# The key is the output folder and the tag in the file names.
SIZES = {
    'wide': {'d_base': 16.0, 'd_top': 15.0, 'flutes': 20, 'flute_depth': 0.4},
    'slim': {'d_base': 13.0, 'd_top': 12.2, 'flutes': 16, 'flute_depth': 0.3},
    'slimmer': {'d_base': 11.5, 'd_top': 10.8, 'flutes': 14, 'flute_depth': 0.25},
    'slimmest': {'d_base': 10.0, 'd_top': 9.4, 'flutes': 12, 'flute_depth': 0.2},
}
KNOB_H = 13.5            # = BORE_DEPTH + 2.0 mm roof
BASE_CHAMFER = 0.4
TOP_CHAMFER = 0.6
FLUTE_R = 1.2
SHELL_WALL_MIN = 1.35    # solid wall between the bore and a flute, the hoop behind the teeth: three printed lines

# Shaft grip
SHAFT_D = 6.0            # RV09 shaft, over the knurl too (asserted against the proxy model)
SHAFT_D_MIN = 5.9        # Song Huei R0904N drawing R09N-003: 6.0 +0/-0.1
KNURL_TEETH = 40         # shaft type KQ (Song Huei shaft-type sheet; Thonk sells R0904N-...-KQ)
KNURL_L = 7.0            # knurl length from the shaft tip (KQ, L = 25)
KNURL_DEPTH = 0.2        # assumed V groove depth: not on the drawing, not measured
POT_BODY_H = 6.8         # carrier to the pot body top (proxy model, nominal)
SHAFT_L = 18.0           # shaft above the pot body top (user, measured 2026-11-10; proxy: 16.0)
SHAFT_PAST_PANEL = 13.0  # shaft tip above the panel front (user, "about 13 mm")
SHAFT_PANEL_TOL = 0.3    # allowed between that and POT_BODY_H + SHAFT_L on either panel
BORE_DEPTH = 11.5        # shaft tip stops on the bore roof: SHAFT_PAST_PANEL - 1.5 mm under the knob
BORE_D = 6.2             # widest round bore where the teeth stand: the bore of REF_FIT, which goes on
SPLINES = 20             # teeth in the bore: one for every second knurl groove
SPLINE_L = 6.0           # teeth from the bore roof down; they stay on the knurl
SPLINE_LEAD = 0.6        # below that the teeth run out to nothing
TOOTH_ANGLE = 90.0       # included angle of a tooth
TOOTH_GAP_MIN = 0.18     # bore wall left between two teeth at the roof (0.19 in the Ø6.0 bore of `h1`)
TIP_TAPER = 0.3          # tooth tip diameter, SPLINE_L below the roof minus at the roof
GUIDE_DRAFT = 0.1        # round bore diameter, mouth minus the cylinder the teeth stand in
# A fit = (round bore diameter where the teeth stand, tooth tip diameter at the bore roof), tightest
# first; the tooth height is (bore - tip) / 2. MID_FIT is the tightest knob of the ladder before
# (`t1`, teeth only in the Ø6.2 bore), "not too tight" on the user's pots (2026-11-12). From it
# toward `h1` the whole hole closes in, bore and tooth tips FIT_STEP at a time (user: "hole should
# also get smaller"); toward `h8` only the teeth get shallower, in the BORE_D bore, which is as
# loose as a bore needs to be: `h6` .. `h8` are the old `t2` .. `t4`. REF_FIT is the tile the user
# picked from the first grip 4 gauge (`fit8`, later `t4`: "goes to the groove and gets locked,
# workable").
FIT_STEP = 0.05
FITS = {'h1': (6.0, 5.25), 'h2': (6.05, 5.3), 'h3': (6.1, 5.35), 'h4': (6.15, 5.4),
        'h5': (6.2, 5.45), 'h6': (6.2, 5.5), 'h7': (6.2, 5.55), 'h8': (6.2, 5.6)}
MID_FIT = 'h5'           # = old `t1`
REF_FIT = 'h8'           # = old `t4` / `fit8`; also the fit in the sections and the puller check
MOUTH_CHAMFER = 0.3
LINE_W = 0.45            # printed line width, 0.4 mm nozzle: rounds the tooth tips (seat model only)
SEAT_SHORT_MAX = 2.0     # a fit seats if the shaft tip stops within this of the bore roof

# Pointer pocket on the top face
POINTER_W = 1.6
POINTER_DEPTH = 0.6
POINTER_R0 = 1.5         # inner end (pocket centreline radius)
POINTER_RIM = 0.8        # wall left between the pocket and the top chamfer

# Two-colour knob: a pointer inlay in a second filament instead of the pocket, flush with the top face
INLAY_W = 1.8            # user, 2026-11-12: 2.4 printed "too wide"
INLAY_R0 = 0.0           # inner end from the knob centre
INLAY_RIM = 1.0          # body left between the outer end and the top chamfer: two first-layer lines (user: "don't go close to the edge")
FIRST_LAYER_H = 0.2      # Bambu Lab P2S, 0.4 mm nozzle: first layer height of every process profile
FIRST_LAYER_LINE_W = 0.48    # and its first layer line width (120 % of the nozzle)
LAYER_H = 0.2            # layer height the pointer depth is cut for (0.20 mm Standard)
INLAY_LAYERS = 5         # user, 2026-11-12: five layers of the second colour (was one, then three)
INLAY_DEPTH = round(FIRST_LAYER_H + (INLAY_LAYERS - 1) * LAYER_H, 6)
INLAY_LINES_MIN = 3      # whole first-layer lines across the pointer
INLAY_AREA_MIN = 4.5     # mm2 of pointer on the bed, so the small island sticks
INLAY_ROOF_MIN = 0.8     # solid roof left between the pointer and the bore: four layers

# Fit gauge: the eight knobs of one width in one print, numbered by notches in the base rim
GAUGE_COLS = 4           # knobs in a row: h1 .. h4 behind, h5 .. h8 in front
GAUGE_GAP = 3.0          # between two knobs at the base
GAUGE_TURN = 45.0        # pointer pocket turned away from the links
GAUGE_LINK = (1.2, 0.6, 0.3)   # break-off link between two knobs: width, height off the bed, end inside the top chamfer
GAUGE_NOTCH = (1.0, 1.0, 1.2, 4)   # rim notch: width, radial depth, height, most in one group
GAUGE_NOTCH_WALL = 0.4   # base face left between a notch and the bore mouth

# Puller: spring tongs (tool frame: X across the legs, Y = width, Z0 = panel front)
PULL_W = 10.0            # leg width = print height
PULL_T = 2.8             # leg and arch thickness (the spring)
PULL_OPEN_R = 9.0        # hook tips when free: drops over the wide knob
PULL_LIP = 2.0           # hook length from the leg inner face
PULL_HOOK_T = 0.8        # two 0.4 mm perimeters; has to pass under the knob base
PULL_NOSE = (0.6, 0.4)   # lead-in on the hook tip: length, tip thickness
PULL_ROOT = 0.4          # 45 deg hook root, clear of the knob base chamfer
PULL_HEEL = 1.0          # chamfer on the outer bottom corner
PULL_LEG = 44.0          # straight leg below the arch
PULL_GRIP = (18.0, 34.0)   # ridged zone on the legs; squeezed at its middle
PULL_RIDGE = (2.0, 0.5)    # pitch, height
PULL_TIP_R = {'wide': 6.2, 'slim': 4.7, 'slimmer': 3.95, 'slimmest': 3.5}   # hook tips closed under the knob base
PULL_E = 2500.0          # MPa, nominal PLA: squeeze force only (the strain does not depend on it)
PULL_STRAIN_MAX = 0.015  # hook tips squeezed together, no knob between them
PULL_HOOK_CLEAR_MIN = 0.2    # hook top to the knob base, tongs seated on the panel
PULL_OVERLAP_MIN = 8.0       # mm2 of knob base over the two hooks
PULL_SPACE_MIN = 1.5

# Panel context
SCREW_HEAD_R = 3.0       # M3 pan head on the rails (the standoff head radius is in reference/panel.json)
PRINT_PANEL_T = 2.0      # 3D-printed front panel


def radius_at(size, z):
    return (size['d_base'] - (size['d_base'] - size['d_top']) * z / KNOB_H) / 2


def tip_r(fit, z):
    """Tooth tip radius at a height in the knob frame: TIP_TAPER wider SPLINE_L below the roof."""
    return fit[1] / 2 + TIP_TAPER / 2 * (BORE_DEPTH - z) / SPLINE_L


def tooth_h(fit):
    """Tooth height at the bore roof: round bore radius minus tooth tip radius."""
    return (fit[0] - fit[1]) / 2


def tooth(fit):
    """One tooth on +X: a triangular rib left standing in the round bore, flat flanks. Its tip
    runs from the bore wall (SPLINE_LEAD below the teeth) in to the fit's tip radius at the roof."""
    wall = fit[0] / 2
    back = wall + 0.2                      # root inside the knob wall
    flank = math.tan(math.radians(TOOTH_ANGLE / 2))
    z_s = BORE_DEPTH - SPLINE_L
    wires = []
    for z, tip in ((z_s - SPLINE_LEAD, wall), (z_s, tip_r(fit, z_s)), (BORE_DEPTH + 0.5, tip_r(fit, BORE_DEPTH + 0.5))):
        half = (back - tip) * flank
        wires.append(Part.makePolygon([V(tip, 0, z), V(back, half, z), V(back, -half, z), V(tip, 0, z)]))
    solid = Part.makeLoft(wires, True, True)
    assert solid.isValid() and solid.Volume > 0
    return solid


BORES = {}


def bore(fit):
    """Blind bore (the solid to cut): round, a cylinder where the teeth stand and GUIDE_DRAFT
    wider at the chamfered mouth, minus the SPLINES teeth, which close in toward the roof."""
    if fit not in BORES:
        wall = fit[0] / 2
        z0, z_g = -1.0, BORE_DEPTH - SPLINE_L - SPLINE_LEAD

        def guide(z):
            return wall + GUIDE_DRAFT / 2 * (z_g - z) / z_g

        cut = Part.makeCylinder(wall, BORE_DEPTH - z_g, V(0, 0, z_g))
        cut = cut.fuse(Part.makeCone(guide(z0), wall, z_g - z0, V(0, 0, z0)))
        cut = cut.fuse(Part.makeCone(guide(MOUTH_CHAMFER) + MOUTH_CHAMFER - z0, guide(MOUTH_CHAMFER),
                                     MOUTH_CHAMFER - z0, V(0, 0, z0))).removeSplitter()
        teeth = []
        for k in range(SPLINES):
            teeth.append(tooth(fit))
            teeth[-1].rotate(V(0, 0, 0), V(0, 0, 1), k * 360 / SPLINES)
        cut = cut.cut(teeth)
        assert cut.isValid() and len(cut.Solids) == 1, 'bore must be one valid solid'
        BORES[fit] = cut
    return BORES[fit]


def seat(fit, shaft_d):
    """Where the knurled shaft stops in the bore, printed to size (geometry only, not measured).
    Model: the knurl is KNURL_TEETH symmetric V grooves KNURL_DEPTH deep; a printed tooth tip is
    rounded to half a line width and seats on both flanks of a groove."""
    bore_d, fit_d = fit
    half = math.radians(TOOTH_ANGLE / 2)
    printed_tip = fit_d / 2 + LINE_W / 2 * (1 / math.sin(half) - 1)        # tip radius at the roof
    groove = math.atan(math.pi * shaft_d / KNURL_TEETH / 2 / KNURL_DEPTH)  # half angle
    seat_r = shaft_d / 2 - KNURL_DEPTH + LINE_W / 2 * (1 / math.sin(groove) - 1)
    short = (seat_r - printed_tip) / (TIP_TAPER / 2 / SPLINE_L)   # shaft tip to the roof when the teeth seat
    bore_clear = (bore_d - shaft_d) / 2                           # round bore to the shaft, radial
    if bore_clear < -1e-9 or short > SPLINE_L:
        state = 'does not go on'
    elif short > SEAT_SHORT_MAX:
        state = 'stops high'
    elif short >= 0:
        state = 'seats'
    elif seat_r - printed_tip > -KNURL_DEPTH / 4:
        state = 'on the roof, light'
    else:
        state = 'loose'
    return {'state': state, 'stops_above_roof': round(max(0.0, short), 2),
            'tooth_in_groove': round(min(shaft_d / 2 - printed_tip, shaft_d / 2 - seat_r), 3),
            'slack_on_roof': round(max(0.0, printed_tip - seat_r), 3),
            'bore_to_shaft': round(bore_clear, 3) + 0.0}


def shell(size):
    rb, rt = size['d_base'] / 2, size['d_top'] / 2
    prof = [(0, 0), (rb - BASE_CHAMFER, 0), (radius_at(size, BASE_CHAMFER), BASE_CHAMFER),
            (radius_at(size, KNOB_H - TOP_CHAMFER), KNOB_H - TOP_CHAMFER), (rt - TOP_CHAMFER, KNOB_H), (0, KNOB_H)]
    pts = [V(r, 0, z) for r, z in prof]
    body = Part.Face(Part.makePolygon(pts + pts[:1])).revolve(V(0, 0, 0), V(0, 0, 1), 360)
    # flutes follow the taper
    axis = V(rt - rb, 0, KNOB_H)
    axis.normalize()
    start = V(rb + FLUTE_R - size['flute_depth'], 0, 0) - axis * 2
    for k in range(size['flutes']):
        cutter = Part.makeCylinder(FLUTE_R, KNOB_H + 4, start, axis)
        cutter.rotate(V(0, 0, 0), V(0, 0, 1), (k + 0.5) * 360 / size['flutes'])
        body = body.cut(cutter)
    return body


def pointer_pocket(size):
    r1 = size['d_top'] / 2 - TOP_CHAMFER - POINTER_RIM - POINTER_W / 2
    z = KNOB_H - POINTER_DEPTH
    slot = Part.makeBox(POINTER_W, r1 - POINTER_R0, POINTER_DEPTH + 1, V(-POINTER_W / 2, POINTER_R0, z))
    for y in (POINTER_R0, r1):
        slot = slot.fuse(Part.makeCylinder(POINTER_W / 2, POINTER_DEPTH + 1, V(0, y, z)))
    return slot.removeSplitter(), r1 + POINTER_W / 2


def knob(size, fit):
    """Knob in the knob frame (open end at Z0)."""
    body = shell(size).cut(bore(fit))
    pocket, _ = pointer_pocket(size)
    body = body.cut(pocket).removeSplitter()
    assert body.isValid() and len(body.Solids) == 1, 'knob must be one valid solid'
    return body


def pointer_inlay(size):
    """Second-colour pointer (knob frame): a bar with round ends in the top INLAY_DEPTH of the
    knob, from INLAY_R0 out to INLAY_RIM short of the top chamfer, so the body closes around it
    in every layer."""
    z = KNOB_H - INLAY_DEPTH
    y0 = INLAY_R0 + INLAY_W / 2
    y1 = size['d_top'] / 2 - TOP_CHAMFER - INLAY_RIM - INLAY_W / 2
    assert y1 > y0, 'no room for the pointer'
    inlay = Part.makeBox(INLAY_W, y1 - y0, INLAY_DEPTH, V(-INLAY_W / 2, y0, z))
    for y in (y0, y1):
        inlay = inlay.fuse(Part.makeCylinder(INLAY_W / 2, INLAY_DEPTH, V(0, y, z)))
    inlay = inlay.removeSplitter()
    assert inlay.isValid() and len(inlay.Solids) == 1, 'pointer inlay must be one valid solid'
    assert math.isclose(inlay.common(shell(size)).Volume, inlay.Volume, abs_tol=1e-6), 'pointer inlay must be inside the knob'
    return inlay


def knob_two_color(size, fit, inlay):
    """Body of the two-colour knob (knob frame): the knob with the inlay cut out instead of the
    pointer pocket."""
    body = shell(size).cut(bore(fit)).cut(inlay).removeSplitter()
    assert body.isValid() and len(body.Solids) == 1, 'knob must be one valid solid'
    return body


def to_print(shape):
    """Knob frame -> print frame: top face down on the bed."""
    out = shape.copy()
    out.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    out.translate(V(0, 0, KNOB_H))
    return out


def fit_notches(size, count):
    """Cutters (knob frame) for `count` notches in the base rim, each in the ridge between two
    flutes: up to four on neighbouring ridges, the fifth and up on the opposite side. They stay
    clear of the bore mouth."""
    w, depth, h, per_group = GAUGE_NOTCH
    rb = size['d_base'] / 2
    mouth = (BORE_D + GUIDE_DRAFT) / 2 + MOUTH_CHAMFER
    assert rb - depth - mouth >= GAUGE_NOTCH_WALL, 'rim notch too close to the bore mouth'
    assert size['flutes'] % 2 == 0 and size['flutes'] // 2 > per_group, 'two notch groups must stay apart'
    cuts = []
    for group in range(2):
        for j in range(min(per_group, count - group * per_group)):
            cuts.append(Part.makeBox(depth + 1, w, h + 1, V(rb - depth, -w / 2, -1)))
            cuts[-1].rotate(V(0, 0, 0), V(0, 0, 1), group * 180 + j * 360 / size['flutes'])
    return cuts


def gauge(size):
    """The eight knobs of one width in print orientation, 1 .. 8 rim notches = FITS order (tightest
    first), joined by break-off links on the bed. Each is the knob of that fit apart from the
    notches: same shell, roof, bore and bed face, so it prints as the knob does."""
    pitch = size['d_base'] + GAUGE_GAP
    foot = size['d_top'] / 2 - TOP_CHAMFER      # knob footprint on the bed
    link_w, link_h, link_in = GAUGE_LINK
    span = pitch - 2 * foot + 2 * link_in
    rows = math.ceil(len(FITS) / GAUGE_COLS)
    strip, voids = None, []
    for i, fit in enumerate(FITS.values()):
        col, row = i % GAUGE_COLS, i // GAUGE_COLS
        x, y = (col - (GAUGE_COLS - 1) / 2) * pitch, ((rows - 1) / 2 - row) * pitch
        body = knob(size, fit).cut(fit_notches(size, i + 1))
        void = bore(fit).fuse(pointer_pocket(size)[0])
        for shape in (body, void):
            shape.rotate(V(0, 0, 0), V(0, 0, 1), GAUGE_TURN)
        body, void = to_print(body), to_print(void)
        for shape in (body, void):
            shape.translate(V(x, y, 0))
        voids.append(void)
        strip = body if strip is None else strip.fuse(body)
        if col:
            strip = strip.fuse(Part.makeBox(span, link_w, link_h, V(x - pitch + foot - link_in, y - link_w / 2, 0)))
        if row:
            strip = strip.fuse(Part.makeBox(link_w, span, link_h, V(x - link_w / 2, y + foot - link_in, 0)))
    strip = strip.removeSplitter()
    assert strip.isValid() and len(strip.Solids) == 1, 'gauge must be one valid solid'
    assert abs(strip.BoundBox.ZMin) < 1e-4 and math.isclose(strip.BoundBox.ZMax, KNOB_H, abs_tol=1e-4), strip.BoundBox
    # no link reaches into a bore or a pointer pocket
    assert all(strip.common(void).Volume < 1e-6 for void in voids), 'gauge link in a bore or pocket'
    return strip


def puller_flex():
    """Half tongs per newton of squeeze at the grip middle (crown fixed by symmetry, bending only):
    toe-in rotation, inward and downward shift at the squeeze point, peak strain. The leg below
    the squeeze point carries no moment, so it moves as a rigid body."""
    xc, zp = PULL_OPEN_R + PULL_LIP + PULL_T / 2, sum(PULL_GRIP) / 2
    ei = PULL_E * PULL_W * PULL_T ** 3 / 12
    n = 2000
    pts = [(xc, zp + (PULL_LEG - zp) * (i + 0.5) / n, (PULL_LEG - zp) / n) for i in range(n)]
    pts += [(xc * math.cos(a), PULL_LEG + xc * math.sin(a), xc * math.pi / 2 / n)
            for a in ((i + 0.5) * math.pi / 2 / n for i in range(n))]
    return {'pivot': (xc, zp),
            'theta': sum((z - zp) * ds for x, z, ds in pts) / ei,
            'dx': sum((z - zp) ** 2 * ds for x, z, ds in pts) / ei,
            'dz': sum((z - zp) * (xc - x) * ds for x, z, ds in pts) / ei,
            'strain': (PULL_LEG + xc - zp) * PULL_T / 2 / ei}


def puller_tip_r(flex, force):
    """Hook tip radius at a squeeze force."""
    (xc, zp), a = flex['pivot'], flex['theta'] * force
    return xc - flex['dx'] * force + (PULL_OPEN_R - xc) * math.cos(a) - zp * math.sin(a)


def puller_force(flex, tip_r):
    """Squeeze force that brings the hook tips to a radius."""
    lo, hi = 0.0, 100.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if puller_tip_r(flex, mid) > tip_r else (lo, mid)
    return (lo + hi) / 2


def puller(tilt):
    """Free tongs in the tool frame. The hooks hang down by `tilt` (rad) so they are level once
    the legs have toed in onto the wide knob."""
    xi = PULL_OPEN_R + PULL_LIP
    xo = xi + PULL_T
    slope, thick = math.tan(tilt), PULL_HOOK_T / math.cos(tilt)

    def foot(x):
        return (x - PULL_OPEN_R) * slope

    outer = [(PULL_OPEN_R, 0), (xo - PULL_HEEL, foot(xo - PULL_HEEL)), (xo, foot(xo) + PULL_HEEL)]
    pitch, height = PULL_RIDGE
    for k in range(int((PULL_GRIP[1] - PULL_GRIP[0]) / pitch)):
        z = PULL_GRIP[0] + k * pitch
        outer += [(xo, z), (xo + height, z + pitch / 2)]
    outer += [(xo, PULL_GRIP[1]), (xo, PULL_LEG)]
    inner = [(xi, PULL_LEG), (xi, foot(xi) + thick + PULL_ROOT), (xi - PULL_ROOT, foot(xi - PULL_ROOT) + thick),
             (PULL_OPEN_R + PULL_NOSE[0], foot(PULL_OPEN_R + PULL_NOSE[0]) + thick),
             (PULL_OPEN_R, PULL_NOSE[1]), (PULL_OPEN_R, 0)]

    def line(pts, side):
        return Part.makePolygon([V(side * x, 0, z) for x, z in pts]).Edges

    top = PULL_LEG
    edges = line(outer, 1) + line(outer, -1) + line(inner, 1) + line(inner, -1)
    edges += [Part.Arc(V(r, 0, top), V(0, 0, top + r), V(-r, 0, top)).toShape() for r in (xi, xo)]
    face = Part.Face(Part.Wire(Part.__sortEdges__(edges)))
    body = face.extrude(V(0, PULL_W, 0))
    body.translate(V(0, -PULL_W / 2, 0))
    assert body.isValid() and len(body.Solids) == 1 and body.Volume > 0, 'puller must be one valid solid'
    return body


def puller_closed(body, flex, force):
    """Both legs below the squeeze point at a squeeze force, seated on the panel."""
    xc, zp = flex['pivot']
    leg = body.common(Part.makeBox(40, 40, zp + 5, V(0, -20, -5)))
    leg.rotate(V(xc, 0, zp), V(0, 1, 0), math.degrees(flex['theta'] * force))
    leg.translate(V(-flex['dx'] * force, 0, -flex['dz'] * force))
    legs = Part.makeCompound([leg, leg.mirror(V(0, 0, 0), V(1, 0, 0))])
    legs.translate(V(0, 0, -legs.BoundBox.ZMin))
    return legs


def puller_space():
    """Free tongs on each big knob, one leg above and one below it (panel Y): plan gap, mm."""
    big = GEO['big_knob']
    pots = {p['ref']: p['shaft_XY'] for p in GEO['pots']}
    knob_r = max(size['d_base'] for size in SIZES.values()) / 2
    reach = PULL_OPEN_R + PULL_LIP + PULL_T + PULL_RIDGE[1]
    out = {}
    for ref in big['refs']:
        cx, cy = pots[ref]
        others = {
            'to_small_knob': [(xy, big['small_knob_R_mm']) for r, xy in pots.items() if r not in big['refs']],
            'to_big_knob': [(pots[r], knob_r) for r in big['refs'] if r != ref],
            'to_jack_nut': [(j['XY'], big['jack_nut_R_mm']) for j in GEO['jacks']],
            'to_standoff_screw_head': [(xy, GEO['mount_standoffs']['panel_bolt_head_R_mm'])
                                       for xy in GEO['mount_standoffs']['XY_mm']],
            'to_rail_screw_head': [(h[:2], SCREW_HEAD_R) for h in GEO['rail_holes_mm']],
        }
        for key, circles in others.items():
            for (x, y), r in circles:
                # legs: |dx| <= PULL_W / 2, PULL_OPEN_R <= |dy| <= reach
                gap = math.hypot(max(abs(x - cx) - PULL_W / 2, 0),
                                 max(PULL_OPEN_R - abs(y - cy), abs(y - cy) - reach, 0)) - r
                out[key] = min(out.get(key, gap), gap)
        out['to_panel_end'] = min(out.get('to_panel_end', 1e9), cy - reach, GEO['panel_mm'][1] - cy - reach)
        out['to_panel_side'] = min(out.get('to_panel_side', 1e9), cx - PULL_W / 2, GEO['panel_mm'][0] - cx - PULL_W / 2)
    assert min(out.values()) >= PULL_SPACE_MIN, out
    return {k: round(v, 3) for k, v in out.items()}


def build_puller(pot, pot_top):
    """Export the puller; check it closed on each knob width on both panels."""
    (OUT / 'puller').mkdir(parents=True, exist_ok=True)
    flex = puller_flex()
    force = {key: puller_force(flex, r) for key, r in PULL_TIP_R.items()}
    tilt = flex['theta'] * force['wide']
    body = puller(tilt)
    seat = GEO['panel_rear_seat_Z_mm']
    gaps = {'fr4': pot_top - BORE_DEPTH - seat - GEO['panel_pcb_thickness_mm'],
            'print': pot_top - BORE_DEPTH - seat - PRINT_PANEL_T}
    flat = PULL_LIP - PULL_ROOT       # level part of the hook top
    report = {'file': f'{NAME}-puller',
              'tongs_mm': {'w': PULL_W, 'leg_t': PULL_T, 'height': round(body.BoundBox.ZLength, 3),
                           'width': round(body.BoundBox.XLength, 3), 'opening': 2 * PULL_OPEN_R,
                           'hook_t': PULL_HOOK_T, 'hook_len': PULL_LIP,
                           'hook_hang_deg': round(math.degrees(tilt), 2)},
              'strain_tips_together': round(flex['strain'] * puller_force(flex, 0.0), 4),
              'space_mm': puller_space(), 'on': {}}
    assert report['strain_tips_together'] <= PULL_STRAIN_MAX, report
    for key, size in SIZES.items():
        tip = PULL_TIP_R[key]
        legs = puller_closed(body, flex, force[key])
        hooks = legs.common(Part.makeBox(2 * (tip + flat), 40, 5, V(-tip - flat, -20, -1)))
        tip_cad = min(abs(v.X) for v in hooks.Vertexes)
        assert math.isclose(tip_cad, tip, abs_tol=0.02), (key, tip_cad)
        hook_top = hooks.BoundBox.ZMax
        on = {'hook_tip_r': round(tip_cad, 3), 'squeeze_N': round(force[key], 2),
              'strain': round(flex['strain'] * force[key], 4),
              'hook_tip_up_deg': round(math.degrees(flex['theta'] * force[key] - tilt), 2),
              'hook_top_above_panel': round(hook_top, 3), 'panel': {}}
        for panel, gap in gaps.items():
            fitted = knob(size, FITS[REF_FIT])
            fitted.translate(V(0, 0, gap))
            shaft = pot.copy()
            shaft.translate(V(0, 0, gap))
            assert legs.common(fitted).Volume < 1e-6 and legs.common(shaft).Volume < 1e-6, (key, panel)
            pads = [Part.makeBox(flat, PULL_W, 0.05, V(x, -PULL_W / 2, gap)) for x in (tip, -tip - flat)]
            overlap = sum(fitted.common(p).Volume for p in pads) / 0.05
            on['panel'][panel] = {
                'hook_under_knob_base': round(gap - hook_top, 3),
                'to_knob': round(legs.distToShape(fitted)[0], 3),
                'to_pot_shaft': round(legs.distToShape(shaft)[0], 3),
                'hook_overlap_mm2': round(overlap, 2)}
            assert on['panel'][panel]['hook_under_knob_base'] >= PULL_HOOK_CLEAR_MIN, (key, panel, on)
            assert on['panel'][panel]['hook_overlap_mm2'] >= PULL_OVERLAP_MIN, (key, panel, on)
            if panel == 'fr4':
                # half legs in the knob frame, beside build()'s section-knob / section-pot
                half = legs.cut(Part.makeBox(40, 40, 80, V(-20, -40, -10)))
                half.rotate(V(0, 0, 0), V(0, 0, 1), 90)
                half.translate(V(0, 0, -gap))
                MeshPart.meshFromShape(Shape=half, LinearDeflection=0.01, AngularDeflection=0.1).write(
                    str(RESEARCH / f'section-puller-{key}.stl'))
        report['on'][key] = on
    flat_print = body.copy()
    flat_print.rotate(V(0, 0, 0), V(1, 0, 0), -90)
    flat_print.translate(V(0, 0, PULL_W / 2))
    assert abs(flat_print.BoundBox.ZMin) < 1e-6 and math.isclose(flat_print.BoundBox.ZMax, PULL_W, abs_tol=1e-6)
    report['facets'] = export(flat_print, 'puller', report['file'])
    bb = flat_print.BoundBox
    report['print_bbox'] = [round(v, 3) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)]
    return report


def export(shape, folder, name):
    shape.exportStep(str(OUT / folder / f'{name}.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds(), name
    mesh.write(str(OUT / folder / f'{name}.stl'))
    return mesh.CountFacets


TMF_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="text/xml"/>
</Types>
"""
TMF_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def export_two_color(parts, folder, name):
    """One 3MF with one object made of one part per colour, in the same print frame (body first,
    then the pointer). The parts are components of the one build item, and
    Metadata/model_settings.config (Bambu Studio / OrcaSlicer) names them and gives part N
    filament N. Two build items load as two objects in OrcaSlicer, the pointer (2 to 5 mm3) as a
    tiny object of its own. Returns the facet counts."""
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
             ' <metadata name="Application">big-modular mechanical/knobs/tools/build_knobs.py</metadata>',
             ' <resources>']
    config = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>', f'  <object id="{len(parts) + 1}">',
              f'    <metadata key="name" value="{name}"/>', '    <metadata key="extruder" value="1"/>']
    facets = {}
    for i, (label, shape) in enumerate(parts, 1):
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
        assert mesh.isSolid() and not mesh.hasNonManifolds(), (name, label)
        points, tris = mesh.Topology
        model += [f'  <object id="{i}" name="{label}" type="model">', '   <mesh>', '    <vertices>']
        model += [f'     <vertex x="{p.x:.6g}" y="{p.y:.6g}" z="{p.z:.6g}"/>' for p in points]
        model += ['    </vertices>', '    <triangles>']
        model += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
        model += ['    </triangles>', '   </mesh>', '  </object>']
        config += [f'    <part id="{i}" subtype="normal_part">', f'      <metadata key="name" value="{label}"/>',
                   f'      <metadata key="extruder" value="{i}"/>', '    </part>']
        facets[label] = len(tris)
    model += [f'  <object id="{len(parts) + 1}" name="{name}" type="model">', '   <components>']
    model += [f'    <component objectid="{i}"/>' for i in range(1, len(parts) + 1)]
    model += ['   </components>', '  </object>', ' </resources>', ' <build>',
              f'  <item objectid="{len(parts) + 1}"/>', ' </build>', '</model>']
    config += ['  </object>', '</config>']
    with zipfile.ZipFile(OUT / folder / f'{name}.3mf', 'w') as archive:
        for path, text in (('[Content_Types].xml', TMF_TYPES), ('_rels/.rels', TMF_RELS),
                           ('3D/3dmodel.model', '\n'.join(model) + '\n'),
                           ('Metadata/model_settings.config', '\n'.join(config) + '\n')):
            # fixed date: a rebuild writes the same bytes
            info = zipfile.ZipInfo(path, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text)
    return facets


def pot_on_knob():
    """RV09 proxy in the knob frame: shaft on the Z axis, shaft tip on the bore roof. The proxy
    shaft is stretched to the measured SHAFT_L; returns the pot and its tip height above the carrier."""
    pot = Part.read(str(POT_MODEL))
    sx, sy = GEO['pot_shaft_offset_mm'][0], -GEO['pot_shaft_offset_mm'][1]
    top = pot.BoundBox.ZMax
    tip = pot.common(Part.makeBox(40, 40, 2, V(-20, -20, top - 2))).BoundBox
    assert math.isclose(tip.XLength, SHAFT_D, abs_tol=1e-3) and math.isclose(tip.YLength, SHAFT_D, abs_tol=1e-3)
    assert math.isclose(tip.Center.x, sx, abs_tol=1e-3) and math.isclose(tip.Center.y, sy, abs_tol=1e-3)
    # body top = where the section drops from the body to the shaft collar
    below, above = (pot.common(Part.makeBox(40, 40, 0.1, V(-20, -20, POT_BODY_H + dz))).BoundBox.XLength
                    for dz in (-0.2, 0.1))
    assert below > 9.0 > above, 'pot body top is not at POT_BODY_H'
    grow = POT_BODY_H + SHAFT_L - top
    assert grow >= 0, 'the proxy shaft is longer than the measured one'
    if grow:
        pot = pot.fuse(Part.makeCylinder(SHAFT_D / 2, grow, V(sx, sy, top))).removeSplitter()
        top += grow
    assert pot.isValid() and len(pot.Solids) == 1 and math.isclose(pot.BoundBox.ZMax, top, abs_tol=1e-6)
    pot.translate(V(-sx, -sy, BORE_DEPTH - top))
    return pot, top


def space(size, pot_top):
    """Clearances on the panel front (panel frame, mm) and above it."""
    big = GEO['big_knob']
    r = size['d_base'] / 2
    pots = {p['ref']: p['shaft_XY'] for p in GEO['pots']}
    bigs = [pots[ref] for ref in big['refs']]
    others = [xy for ref, xy in pots.items() if ref not in big['refs']]

    def gap(pts, rad):
        return min(math.dist(a, b) for a in bigs for b in pts) - r - rad

    def rnd(v):
        return {k: rnd(x) for k, x in v.items()} if isinstance(v, dict) else round(v, 3)

    assert size['d_base'] <= big['reserve_D_mm'], 'knob must stay inside the big-knob reserve'
    seat = GEO['panel_rear_seat_Z_mm']
    front = {'fr4': seat + GEO['panel_pcb_thickness_mm'], 'print': seat + PRINT_PANEL_T}
    out = {
        'inside_reserve_radial': (big['reserve_D_mm'] - size['d_base']) / 2,
        'knob_to_knob': min(math.dist(a, b) for a in bigs for b in bigs if a != b) - 2 * r,
        'to_bare_pot_shaft': gap(others, SHAFT_D / 2),
        'to_small_knob': gap(others, big['small_knob_R_mm']),
        'to_jack_nut': gap([j['XY'] for j in GEO['jacks']], big['jack_nut_R_mm']),
        'to_standoff_screw_head': gap(GEO['mount_standoffs']['XY_mm'], GEO['mount_standoffs']['panel_bolt_head_R_mm']),
        'to_rail_screw_head': gap([h[:2] for h in GEO['rail_holes_mm']], SCREW_HEAD_R),
        'to_panel_side': min(min(x, GEO['panel_mm'][0] - x) for x, _ in bigs) - r,
        'shaft_past_panel_front': {k: pot_top - z for k, z in front.items()},
        'knob_base_above_panel': {k: pot_top - BORE_DEPTH - z for k, z in front.items()},
        'knob_top_above_panel': {k: pot_top - BORE_DEPTH + KNOB_H - z for k, z in front.items()},
    }
    flat = [v for v in out.values() if not isinstance(v, dict)] + list(out['knob_base_above_panel'].values())
    assert min(flat) >= 1.0, out
    # the two shaft measurements have to agree through the nominal stack, on either panel
    assert all(abs(v - SHAFT_PAST_PANEL) <= SHAFT_PANEL_TOL + 1e-9 for v in out['shaft_past_panel_front'].values()), out
    out['shaft_past_panel_measured'] = SHAFT_PAST_PANEL
    return rnd(out)


def build(key, size, pot, pot_top):
    """Export every fit of one width and its fit gauge to its folder; returns its report."""
    two = f'{key}/two-color'
    (OUT / two).mkdir(parents=True, exist_ok=True)
    inlay = pointer_inlay(size)
    shaft = Part.makeCylinder(SHAFT_D / 2, BORE_DEPTH)
    wall = {'bore_to_flute_min': round(radius_at(size, BORE_DEPTH) - size['flute_depth'] - BORE_D / 2, 3),
            'base_face': round(size['d_base'] / 2 - BASE_CHAMFER - (BORE_D + GUIDE_DRAFT) / 2 - MOUTH_CHAMFER, 3),
            'top_over_bore': round(KNOB_H - BORE_DEPTH, 3),
            'top_under_pocket': round(KNOB_H - BORE_DEPTH - POINTER_DEPTH, 3)}
    assert wall['bore_to_flute_min'] >= SHELL_WALL_MIN, wall
    report = {'knob_mm': {'d_base': size['d_base'], 'd_top': size['d_top'], 'h': KNOB_H,
                          'flutes': size['flutes'], 'flute_depth': size['flute_depth']},
              'pointer_pocket_mm': {'w': POINTER_W, 'depth': POINTER_DEPTH,
                                    'r': [POINTER_R0 - POINTER_W / 2, round(pointer_pocket(size)[1], 3)]},
              'wall_mm': wall, 'space_mm': space(size, pot_top), 'fits': {}}
    base = f'{NAME}-{key}'
    # the pointer: a rim of body around it, a solid roof under it, wide enough for whole lines, a
    # big enough island on the bed
    on_bed = to_print(inlay).common(Part.makeBox(40, 40, 1e-3, V(-20, -20, 0))).Volume / 1e-3
    report['two_color'] = {
        'pointer_mm': {'w': INLAY_W, 'depth': INLAY_DEPTH, 'layers': INLAY_LAYERS, 'layer_h': LAYER_H,
                       'r': [INLAY_R0, round(inlay.BoundBox.YMax, 3)],
                       'to_top_face_edge': round(size['d_top'] / 2 - TOP_CHAMFER - inlay.BoundBox.YMax, 3),
                       'first_layer_lines': round(INLAY_W / FIRST_LAYER_LINE_W, 2), 'on_bed_mm2': round(on_bed, 2),
                       'volume_mm3': round(inlay.Volume, 2)},
        'top_under_pointer': round(KNOB_H - BORE_DEPTH - INLAY_DEPTH, 3), 'fits': {}}
    assert INLAY_RIM >= 2 * FIRST_LAYER_LINE_W and INLAY_W >= INLAY_LINES_MIN * FIRST_LAYER_LINE_W, report['two_color']
    assert on_bed >= INLAY_AREA_MIN and report['two_color']['top_under_pointer'] >= INLAY_ROOF_MIN, report['two_color']
    to_print(inlay).exportStep(str(OUT / two / f'{base}-pointer.step'))
    for fit, fit_d in FITS.items():
        body = knob(size, fit_d)
        # the pot model's shaft is a plain nominal cylinder, no knurl: the teeth reach into it.
        # Nothing else of the pot may touch the knob.
        in_shaft = body.common(shaft).Volume
        assert body.common(pot).Volume - in_shaft < 1e-6, 'only the shaft may touch the knob'
        assert body.distToShape(Part.makeCylinder(
            SHAFT_D / 2, BORE_DEPTH - KNURL_L))[0] > 0, 'the plain shaft must be free'
        name = f'{base}-{fit}'
        report['fits'][fit] = {
            'file': name, 'bore_d': fit_d[0], 'tip_d_roof': fit_d[1], 'tooth_h_roof': round(tooth_h(fit_d), 3),
            'in_nominal_plain_shaft_mm3': round(in_shaft, 3), 'volume_mm3': round(body.Volume, 1),
            'facets': export(to_print(body), key, name)}
        # two-colour version: no pocket; body + pointer inlay make up the plain knob shape exactly
        body2 = knob_two_color(size, fit_d, inlay)
        assert body2.common(inlay).Volume < 1e-6, 'pointer inlay overlaps the knob'
        filled = shell(size).cut(bore(fit_d))
        assert math.isclose(body2.Volume + inlay.Volume, filled.Volume, abs_tol=1e-4), 'pointer inlay leaves a gap'
        assert len(body2.fuse(inlay).removeSplitter().Solids) == 1, 'pointer inlay must touch the knob'
        report['two_color']['fits'][fit] = {
            'file': f'{name}-two-color',
            'facets': export_two_color([('body', to_print(body2)), ('pointer', to_print(inlay))], two, f'{name}-two-color')}
        if fit == REF_FIT:
            half = Part.makeBox(40, 40, 40, V(0, -20, -10))
            for part, shape in (('knob', body.cut(half)), ('pot', pot.cut(half))):
                MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1).write(
                    str(RESEARCH / f'section-{part}-{key}.stl'))
            bb = to_print(body).BoundBox
            report['print_bbox'] = [round(v, 3) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)]
    strip = gauge(size)
    bb = strip.BoundBox
    report['gauge'] = {'file': f'{base}-fit-gauge', 'notches': {f: i + 1 for i, f in enumerate(FITS)},
                       'size': [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
                       'volume_mm3': round(strip.Volume, 1),
                       'facets': export(strip, key, f'{base}-fit-gauge')}
    return report


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RESEARCH.mkdir(parents=True, exist_ok=True)
    pot, pot_top = pot_on_knob()
    # every tooth has a knurl groove to drop into, and the teeth end on the knurl with the knob on the roof
    assert KNURL_TEETH % SPLINES == 0 and SPLINE_L + SPLINE_LEAD < KNURL_L
    z_s = BORE_DEPTH - SPLINE_L
    flank = 2 * math.tan(math.radians(TOOTH_ANGLE / 2))     # tooth base width per tooth height
    grip_report = {'knurl': {'teeth': KNURL_TEETH, 'length': KNURL_L, 'depth_assumed': KNURL_DEPTH,
                             'pitch': round(math.pi * SHAFT_D / KNURL_TEETH, 3)},
                   'teeth': SPLINES, 'tooth_angle_deg': TOOTH_ANGLE, 'tooth_length': SPLINE_L, 'tooth_lead': SPLINE_LEAD,
                   'tooth_pitch': [round(math.pi * min(FITS.values())[0] / SPLINES, 3), round(math.pi * BORE_D / SPLINES, 3)],
                   'between_teeth_min': round(min(math.pi * f[0] / SPLINES - tooth_h(f) * flank for f in FITS.values()), 3),
                   'tip_taper_d': TIP_TAPER, 'tip_deg': round(math.degrees(math.atan(TIP_TAPER / 2 / SPLINE_L)), 2),
                   'fit_step_d': FIT_STEP, 'seat_per_fit_step': round(FIT_STEP / (TIP_TAPER / SPLINE_L), 2),
                   'guide_draft_d': GUIDE_DRAFT, 'mid_fit': MID_FIT, 'ref_fit': REF_FIT, 'fits': {}}
    # every fit still has teeth at their lower end, the teeth stay separate ribs and the ladder is
    # even: the tooth tips step all the way, the bore steps with them up to MID_FIT and stays at
    # BORE_D from there on
    assert min(tooth_h(f) for f in FITS.values()) > TIP_TAPER / 2, grip_report
    assert grip_report['tooth_pitch'][0] > 2 * LINE_W and grip_report['between_teeth_min'] >= TOOTH_GAP_MIN, grip_report
    fits, mid = list(FITS.values()), list(FITS).index(MID_FIT)
    assert all(math.isclose(b[1] - a[1], FIT_STEP, abs_tol=1e-9) for a, b in zip(fits, fits[1:])), fits
    assert all(math.isclose(f[0], min(BORE_D, BORE_D + (i - mid) * FIT_STEP), abs_tol=1e-9) for i, f in enumerate(fits)), fits
    for fit, fit_d in FITS.items():
        grip_report['fits'][fit] = {
            'bore_d': [fit_d[0], round(fit_d[0] + GUIDE_DRAFT, 3)],
            'tip_d': [fit_d[1], round(2 * tip_r(fit_d, z_s), 3)],
            'tooth_h': [round(tooth_h(fit_d), 3), round(tooth_h(fit_d) - TIP_TAPER / 2, 3)],
            'tooth_base_w': round(tooth_h(fit_d) * flank, 3),
            'on_shaft': {str(d): seat(fit_d, d) for d in (SHAFT_D_MIN, SHAFT_D)}}
    ref = grip_report['fits'][REF_FIT]['on_shaft'][str(SHAFT_D)]
    # the user's pick is on the bore roof or seats just short of it in the model too, its teeth at
    # least half a groove deep, and the round bore clears a nominal shaft
    assert ref['state'] in ('seats', 'on the roof, light') and ref['bore_to_shaft'] > 0, ref
    assert ref['tooth_in_groove'] >= KNURL_DEPTH / 2, ref
    report = {'grip': grip_report,
              'sizes': {key: build(key, size, pot, pot_top) for key, size in SIZES.items()}}
    report['puller'] = build_puller(pot, pot_top)
    (RESEARCH / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('knob report', json.dumps(report))


main()
