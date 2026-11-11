"""Shared, open middle frame joining two existing skiffs side by side.

Run mechanical/case/tools/build_middle_frame.sh (defaults match cad/assembly.FCStd).
Reuses build_case.py; never rebuilds or overwrites the original case print set.

Local frame: X=0 is the left case's right inner face; X=width is the
right case's left inner face. Y/Z are the existing case coordinates.
Four blind rectangular sockets receive the unmodified rail ends along X,
not from the front/back. The outer side-panel screws and four existing
bottom-plate screws retain the assembly: the centre rail sockets have no screws.

Two 12 mm bottom tongues fit the original bottom-plate sockets. A clearance
channel between them straddles the adjacent socket walls, joining above them.
The original 1 HP lip faces right, as on the right case's replaced left panel.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = base.CASE
TOL = 1e-3

# Prototype fit allowances, deliberately independent of the original notches.
RAIL_CLEARANCE = float(os.environ.get("JOINER_RAIL_CLEARANCE", "0.25"))  # each Y/Z face
END_CLEARANCE = 0.30
PLATE_GAP = 0.30
BRIDGE_CLEARANCE = 0.40
COLLAR_OVERHANG = 3.40  # past the case front/back, not into the module bays
COLLAR_RISE = 2.40      # above the module faces, only over the middle frame
OUTLINE_FILLET = 2.0
WINDOW_FILLET = 6.0
POST_WIDTH = 17.0
BOTTOM_BAND = 14.0
TOP_BAND = 8.0
ENTRY_CHAMFER = 0.60


def moved(shape, dx=0, dy=0, dz=0):
    result = shape.copy()
    result.translate(V(dx, dy, dz))
    return result


def size(shape):
    # The fast box can include the untrimmed lead-in loft's 0.01 mm overrun.
    bb = shape.optimalBoundingBox(False, False)
    return [round(v, 3) for v in (bb.XLength, bb.YLength, bb.ZLength)]


def x_edges(shape):
    """Straight edges parallel to X, for filleting an extruded Y/Z outline."""
    return [e for e in shape.Edges if len(e.Vertexes) == 2
            and e.BoundBox.YLength < 1e-6 and e.BoundBox.ZLength < 1e-6
            and e.BoundBox.XLength > 1e-4]


def yz_prism(points, x0, length):
    pts = [V(x0, y, z) for y, z in points]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(length, 0, 0))


def yz_rectangle(x, y0, y1, z0, z1):
    return Part.makePolygon([V(x, y0, z0), V(x, y1, z0), V(x, y1, z1),
                             V(x, y0, z1), V(x, y0, z0)])


class Join:
    def __init__(self, d):
        assert 0.15 <= RAIL_CLEARANCE <= 0.50, "socket allowance must be 0.15..0.50 mm per face"
        self.width = 2 * (d.T + d.wall) + d.socket_clr + PLATE_GAP
        self.offset = d.L + self.width
        self.bridge_z = d.P + d.socket_h + BRIDGE_CLEARANCE
        self.bottom_slot = self.width - 2 * d.T
        self.rail_z = d.top - d.rail_h
        self.window_y = (d.y0 + POST_WIDTH, d.y0 + d.ylen - POST_WIDTH)
        self.window_z = (d.P + BOTTOM_BAND, d.case_top - TOP_BAND)
        self.collar_top = d.case_top + COLLAR_RISE
        assert self.window_z[1] - self.window_z[0] > 2 * WINDOW_FILLET
        assert self.window_z[0] - self.bridge_z >= 5.0
        assert self.window_z[0] - (d.P + base.SPACER_SOCKET_DEPTH) >= 3.0
        assert d.panel_t > RAIL_CLEARANCE + 1.0


def frame(d, j):
    """Perimeter only: rounded open window, two feet, four enclosed rail sockets."""
    y0, y1 = d.y0, d.y0 + d.ylen
    shoulder_low, shoulder_high = j.rail_z - 7, j.rail_z - 3
    collar_inner = d.rail_w + 3.0
    blend = 6.0
    outline = [
        (y0, d.P), (y1, d.P),
        (y1, shoulder_low), (y1 + COLLAR_OVERHANG, shoulder_high),
        (y1 + COLLAR_OVERHANG, j.collar_top),
        (y1 - collar_inner, j.collar_top),
        (y1 - collar_inner - blend, d.case_top),
        (y0 + collar_inner + blend, d.case_top),
        (y0 + collar_inner, j.collar_top),
        (y0 - COLLAR_OVERHANG, j.collar_top),
        (y0 - COLLAR_OVERHANG, shoulder_high), (y0, shoulder_low),
    ]
    body = yz_prism(outline, 0, j.width)
    # Keep both bottom seating corners square. All upper silhouette corners,
    # including the sloping transitions into the proud collars, are rounded.
    edges = [e for e in x_edges(body) if e.CenterOfMass.z > j.bridge_z]
    body = body.makeFillet(OUTLINE_FILLET, edges)
    assert body.isValid() and len(body.Solids) == 1

    # Exact original left-panel lip/web, attached on the right case side only.
    left = base.side_panel(d, left=True)
    clip = base.box((0, y0 - 1, d.P - 1), (d.fill + 1, d.ylen + 2, d.depth + 2))
    lip = moved(left.common(clip), dx=j.width)
    body = body.fuse(lip).removeSplitter()

    wy0, wy1 = j.window_y
    wz0, wz1 = j.window_z
    window = base.box((-1, wy0, wz0), (j.width + d.fill + 2, wy1 - wy0, wz1 - wz0))
    window = window.makeFillet(WINDOW_FILLET, x_edges(window))
    cuts = [window]

    # Original feet fit unchanged sockets. The bridge clears both adjacent
    # bottom-plate outer walls rather than forcing the plates to overlap.
    cuts.append(base.box((d.T, y0 - 1, d.P - 1),
                         (j.bottom_slot, d.ylen + 2, j.bridge_z - d.P + 1)))
    for x in (d.T / 2, j.width - d.T / 2):
        for y in d.bolt_y:
            cuts.append(base.spacer_socket((x, y), d.P, base.SPACER_SOCKET_DEPTH))

    # Original cover grooves on BOTH bay-facing sides, open from the bottom.
    for x in (0, j.width - d.groove_d):
        for gy in d.groove_y:
            cuts.append(base.box((x, gy, d.P - 1),
                                 (d.groove_d, d.groove_w, j.rail_z - d.P + 1.5)))

    # Four enclosed mouths. Square internal corners preserve clearance to the
    # square rail profile; a small loft makes a lead-in without reducing fit.
    for ry in d.rail_y:
        lo_y, hi_y = ry - RAIL_CLEARANCE, ry + d.rail_w + RAIL_CLEARANCE
        lo_z, hi_z = j.rail_z - RAIL_CLEARANCE, d.top + RAIL_CLEARANCE
        nd = d.tenon + END_CLEARANCE
        for right in (False, True):
            start = j.width - nd if right else -1.0
            end = j.width + d.fill + 1 if right else nd
            cuts.append(base.box((start, lo_y, lo_z), (end - start, hi_y - lo_y, hi_z - lo_z)))
            # The right-hand roof extends to the existing top lip. Chamfer at
            # the structural cheek mouth; also ease the exposed lip end.
            mouths = [(j.width, -1)] if right else [(0, 1)]
            if right:
                mouths.append((j.width + d.fill, -1))
            for x, direction in mouths:
                outer = yz_rectangle(x - direction * 0.01, lo_y - ENTRY_CHAMFER,
                                     hi_y + ENTRY_CHAMFER, lo_z - ENTRY_CHAMFER,
                                     hi_z + ENTRY_CHAMFER)
                inner = yz_rectangle(x + direction * ENTRY_CHAMFER, lo_y, hi_y, lo_z, hi_z)
                cuts.append(Part.makeLoft([outer, inner], True, True))
    return base.cut_all(body, cuts)


def print_pose(shape):
    """Left-bay-facing side down; original left-style lip points up."""
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(0, 1, 0), -90)
    b = s.optimalBoundingBox(False, False)
    # Remove only the kernel's sub-micron bounding tolerance, so the exported
    # mesh actually touches Z=0 rather than floating above the print bed.
    s.translate(V(-round(b.XMin, 6), -round(b.YMin, 6), -round(b.ZMin, 6)))
    return s


def source_parts(d):
    """Use actual saved native geometry; reject a changed source, don't silently guess."""
    generated = {"bottom_plate": base.bottom_plate(d),
                 "side_panel_left": base.side_panel(d, True),
                 "side_panel_right": base.side_panel(d, False),
                 "rail_front": base.rail(d, 0), "rail_back": base.rail(d, 1)}
    src = App.openDocument(str(CASE / "cad" / "assembly.FCStd"))
    result, differences = {}, {}
    for name, expected in generated.items():
        obj = src.getObject(name)
        assert obj is not None, f"missing source object {name}"
        actual = obj.Shape.copy()
        assert actual.isValid() and len(actual.Solids) == 1, name
        diff = actual.cut(expected).Volume + expected.cut(actual).Volume
        assert diff < TOL, f"{name}: current source differs from requested dimensions by {diff} mm3"
        result[name], differences[name] = actual, round(diff, 6)
    App.closeDocument(src.Name)
    return result, differences


def assembly(d, j, s, source):
    objects = {"middle_frame": moved(s, dx=d.L)}
    for label, offset, outer in (("left", 0, "side_panel_left"),
                                  ("right", j.offset, "side_panel_right")):
        for name in ("bottom_plate", "rail_front", "rail_back", outer):
            objects[f"{label}_{name}"] = moved(source[name], dx=offset)
    return objects


def no_collision(a, b, description):
    v = a.common(b).Volume
    assert v < TOL, f"{description}: collision {v:.6f} mm3"
    return round(v, 6)


def check_geometry(d, j, s, asm):
    """Native solids, independent witness volumes, and swept assembly paths."""
    assert s.isValid() and len(s.Solids) == 1
    for name, shape in asm.items():
        assert shape.isValid() and len(shape.Solids) == 1, name
    collisions = {}
    items = list(asm.items())
    for i, (an, a) in enumerate(items):
        for bn, b in items[i + 1:]:
            collisions[f"{an}/{bn}"] = no_collision(a, b, f"{an}/{bn}")

    # Stock cover plates fit both bays. Full continuous downward sweep models
    # upside-down insertion before the two bottom plates are fitted.
    cover_checks = {}
    for label, offset in (("left", 0), ("right", j.offset)):
        for i in (0, 1):
            c = moved(base.cover_blank(d, i), dx=offset)
            for name, part in asm.items():
                no_collision(c, part, f"{label} cover {i}/{name}")
            gy = d.groove_y[i] + (d.groove_w - d.cover_t) / 2
            span = d.cover_blank_size()["plate"][0]
            lower = -d.depth
            swept = base.box((offset - (d.groove_d - d.cover_clr), gy, lower),
                             (span, d.cover_t, d.cover_z1 - lower))
            no_collision(swept, asm["middle_frame"], f"{label} cover {i} insertion")
            cover_checks[f"{label}_{i}"] = "fits; continuous bottom-entry sweep clear"

    socket_checks = {}
    for right in (False, True):
        side = "right" if right else "left"
        for i, ry in enumerate(d.rail_y):
            # Entire rectangular rail-end envelope, not the perforated mesh.
            # Each sweep goes from fully outside the lip to the seated end.
            x0 = j.width - d.tenon if right else -d.tenon - d.fill - 2
            length = d.tenon + d.fill + 2 if right else 2 * d.tenon + d.fill + 2
            swept = base.box((x0, ry, j.rail_z), (length, d.rail_w, d.rail_h))
            no_collision(s, swept, f"{side} rail {i} insertion")
            # Gauge fills the specified clearance envelope at full depth.
            eps = 1e-4
            gx = j.width - d.tenon - END_CLEARANCE + eps if right else eps
            gauge = base.box((gx, ry - RAIL_CLEARANCE + eps, j.rail_z - RAIL_CLEARANCE + eps),
                             (d.tenon + END_CLEARANCE - 2 * eps,
                              d.rail_w + 2 * RAIL_CLEARANCE - 2 * eps,
                              d.rail_h + 2 * RAIL_CLEARANCE - 2 * eps))
            no_collision(s, gauge, f"{side} rail {i} tolerance gauge")
            # Walls and closed back exist; not just two overlapping open notches.
            probe_x = j.width - 3.0 if right else 3.0
            mid_y, mid_z = ry + d.rail_w / 2, j.rail_z + d.rail_h / 2
            back_x = j.width - d.tenon - END_CLEARANCE - 0.25 if right else d.tenon + END_CLEARANCE + 0.25
            witnesses = [V(probe_x, ry - RAIL_CLEARANCE - 0.5, mid_z),
                         V(probe_x, ry + d.rail_w + RAIL_CLEARANCE + 0.5, mid_z),
                         V(probe_x, mid_y, d.top + RAIL_CLEARANCE + 0.5),
                         # Avoid the intended cover groove in the underside.
                         V(probe_x, mid_y + (2 if i == 0 else -2), j.rail_z - RAIL_CLEARANCE - 0.5),
                         V(back_x, mid_y, mid_z)]
            assert all(s.isInside(p, 1e-6, True) for p in witnesses), (side, i, "missing socket wall")
            socket_checks[f"{side}_{i}"] = "blind; enclosed; gauge and continuous X insertion clear"

    # Base attachment uses the actual four existing screw axes. Prove the
    # tongues, closed hex sockets, and retained wall material around each.
    fasteners = {}
    for x in (d.T / 2, j.width - d.T / 2):
        for y in d.bolt_y:
            for z in (0.1, 5, base.SPACER_SOCKET_DEPTH - 0.05):
                assert not s.isInside(V(x, y, d.P + z), 1e-6, True), "blocked spacer socket"
            assert s.isInside(V(x, y, d.P + base.SPACER_SOCKET_DEPTH + 0.3), 1e-6, True)
            for dx in (-3.1, 3.1):
                assert s.isInside(V(x + dx, y, d.P + 5), 1e-6, True)
            fasteners[f"{x:.2f},{y:.2f}"] = "open bottom, closed roof, original base screw axis"
    # No undercuts for the two plates to slide onto the tongues from below.
    for name, plate in asm.items():
        if not name.endswith("bottom_plate"):
            continue
        bb = plate.BoundBox
        for sx in (bb.XMin, bb.XMax - (2 * d.wall + d.T + d.socket_clr)):
            for wx in (sx, sx + d.wall + d.T + d.socket_clr):
                swept_wall = base.box((wx, d.y0, -d.depth),
                                     (d.wall, d.ylen, d.depth + d.P + d.socket_h))
                no_collision(asm["middle_frame"], swept_wall, f"{name} wall insertion")

    # Real module panel bounding envelopes at every supported even-HP slot.
    module_checks = 0
    for label, offset in (("left", 0), ("right", j.offset)):
        for name, p in d.panels.items():
            for slot in range(0, d.hp, 2):
                x = d.row_x0 + slot * base.HP
                if x + p["width"] > d.L + 1e-6:
                    continue
                panel = base.box((offset + x, 0, d.top), (p["width"], p["height"], p["thickness"]))
                no_collision(panel, asm["middle_frame"], f"{label}/{name}/slot{slot}")
                module_checks += 1
    # Central opening is genuinely through, not a shallow weight-saving pocket.
    mid = V(j.width / 2, sum(j.window_y) / 2, sum(j.window_z) / 2)
    opening = base.box((-1, mid.y - 1, mid.z - 1), (j.width + d.fill + 2, 2, 2))
    no_collision(s, opening, "through opening")
    plate_distance = asm["left_bottom_plate"].distToShape(asm["right_bottom_plate"])[0]
    assert abs(plate_distance - PLATE_GAP) < 1e-6
    return {"native_valid_single_solid": True, "assembly_pairs_checked": len(collisions),
            "max_pair_interference_mm3": max(collisions.values()),
            "plate_edge_gap_mm": round(plate_distance, 3),
            "rail_sockets": socket_checks, "cover_fit_and_insertion": cover_checks,
            "base_fasteners": fasteners, "base_wall_insertion_sweeps": "clear",
            "module_panel_envelopes_checked": module_checks, "through_window": True}


def native_document(name, path, shapes, d, j):
    doc = App.newDocument(name)
    for key, shape in shapes.items():
        obj = doc.addObject("Part::Feature", key)
        obj.Label = key.replace("_", " ").title()
        obj.Shape = shape
        if key == "middle_frame":
            for prop, value in (("CaseDepth", d.depth), ("FrameWidth", j.width),
                                ("RailClearancePerFace", RAIL_CLEARANCE),
                                ("RailEndEngagement", d.tenon), ("PlateEdgeGap", PLATE_GAP),
                                ("OutsideRadius", OUTLINE_FILLET), ("WindowRadius", WINDOW_FILLET)):
                obj.addProperty("App::PropertyLength", prop, "Build dimensions")
                setattr(obj, prop, value)
                obj.setEditorMode(prop, 1)  # metadata, not misleading editable drivers
            obj.addProperty("App::PropertyString", "Regenerate", "Build dimensions")
            obj.Regenerate = "mechanical/case/tools/build_middle_frame.sh (source: build_middle_frame.py)"
    doc.recompute()
    temporary = path.with_name("." + path.name)
    doc.saveAs(str(temporary))
    App.closeDocument(doc.Name)
    verify = App.openDocument(str(temporary))
    for key, original in shapes.items():
        saved = verify.getObject(key).Shape
        assert saved.isValid() and len(saved.Solids) == 1
        assert saved.cut(original).Volume + original.cut(saved).Volume < TOL, key
    App.closeDocument(verify.Name)
    temporary.replace(path)


def exported_part(shape, path):
    p = print_pose(shape)
    assert max(size(p)) <= base.BED - 4
    result = base.export(p, path)
    # Reload both mesh formats and neutral CAD independently of their writers.
    for suffix in (".stl", ".3mf"):
        m = Mesh.Mesh(str(path.with_suffix(suffix)))
        assert m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections(), suffix
        assert abs(m.Volume - p.Volume) / p.Volume < 0.002
        bb = m.BoundBox
        assert max(abs(bb.XMin), abs(bb.YMin), abs(bb.ZMin)) < 1e-5, (suffix, "off print-bed origin")
    saved = Part.Shape()
    saved.read(str(path.with_suffix(".step")))
    assert saved.isValid() and len(saved.Solids) == 1
    assert saved.cut(p).Volume + p.cut(saved).Volume < TOL
    return {"bbox_mm": size(p), "native_volume_cm3": round(p.Volume / 1000, 3),
            "reload_STEP_STL_3MF": "pass", **result}


def main():
    d = base.Dims(int(os.environ.get("CASE_HP", 42)), float(os.environ.get("CASE_DEPTH", 60)),
                  float(os.environ.get("CASE_ROW_GAP", 0.5)), base.module_panels())
    j = Join(d)
    source, differences = source_parts(d)
    s = frame(d, j)
    asm = assembly(d, j, s, source)
    report = {"source": "mechanical/case/cad/assembly.FCStd", "source_geometry_difference_mm3": differences,
              "dimensions": {"case_hp_each": d.hp, "case_depth_mm": d.depth,
                             "frame_width_without_lip_mm": round(j.width, 3),
                             "frame_width_with_lip_mm": round(j.width + d.fill, 3),
                             "case_origin_offset_mm": round(j.offset, 3),
                             "two_case_overall_width_mm": round(d.plate_len + j.offset, 3),
                             "rail_socket_y_z_mm": [d.rail_w + 2 * RAIL_CLEARANCE, d.rail_h + 2 * RAIL_CLEARANCE],
                             "rail_engagement_mm": d.tenon, "rail_socket_depth_mm": d.tenon + END_CLEARANCE,
                             "rail_clearance_per_face_mm": RAIL_CLEARANCE,
                             "collar_overhang_front_back_mm": COLLAR_OVERHANG,
                             "collar_rise_above_modules_mm": COLLAR_RISE,
                             "outline_fillet_mm": OUTLINE_FILLET, "window_fillet_mm": WINDOW_FILLET,
                             "entry_chamfer_mm": ENTRY_CHAMFER,
                             "open_window_y_z_mm": [round(j.window_y[1] - j.window_y[0], 3),
                                                    round(j.window_z[1] - j.window_z[0], 3)],
                             "bridge_over_base_wall_clearance_mm": BRIDGE_CLEARANCE,
                             "bottom_tongue_thickness_mm": d.T,
                             "bottom_channel_width_mm": round(j.bottom_slot, 3)},
              "checks": check_geometry(d, j, s, asm)}

    cad, out = CASE / "cad", CASE / "print" / "side panels" / "middle-frame"
    research = CASE / "research" / "middle-frame"
    for folder in (cad, out, research):
        folder.mkdir(parents=True, exist_ok=True)
    native_document("SharedMiddleFrame", cad / "middle-frame.FCStd", {"middle_frame": s}, d, j)
    native_document("TwoSkiffsJoined", cad / "double-case-assembly.FCStd", asm, d, j)
    report["print"] = {"middle-frame": exported_part(s, out / "middle-frame")}

    # A small exact slice containing both opposing front sockets, including the
    # left/right lip difference: check fit before printing the full frame.
    coupon_clip = base.box((-1, d.y0 - COLLAR_OVERHANG - 1, j.rail_z - 3.0),
                          (j.width + d.fill + 2, d.rail_w + COLLAR_OVERHANG + 4,
                           j.collar_top - j.rail_z + 4))
    coupon = s.common(coupon_clip).removeSplitter()
    assert coupon.isValid() and len(coupon.Solids) == 1
    report["print"]["rail-fit-coupon"] = exported_part(coupon, out / "rail-fit-coupon")
    Part.makeCompound(list(asm.values())).exportStep(str(out / "double-case-assembly-preview.step"))
    report["native_documents_reopened"] = True
    report["hardware"] = {"middle_rail_screws": 0,
                          "base_screws": "4 existing M3x6 through the two bases",
                          "frame_spacers": "4 M3x10 female hex spacers glued into the bottom sockets",
                          "outer_rail_screws": "4 existing M3x10, retain the two outer side panels"}
    report["prototype_status"] = "CAD and mesh checks only; print fit and load capacity not tested"
    report["print_notes"] = ("Supplied pose: left-facing side down, right lip up. Supports required for the "
                               "down-facing blind rail pockets and underside-channel overhang; inspect slicer. "
                               "Keep supports out of the upward-facing rail and glue sockets.")
    # Assembly meshes only for the headless preview, not additional print parts.
    for name, shape in asm.items():
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.025, AngularDeflection=0.15)
        mesh.write(str(research / f"asm-{name}.stl"))
    mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.01, AngularDeflection=0.12)
    mesh.write(str(research / "connector.stl"))
    (research / "camera.json").write_text(json.dumps({"frame_width": j.width, "left_inner": d.L,
                                                    "right_origin": j.offset, "case_top": d.case_top,
                                                    "centre_y": base.PANEL_H / 2}, indent=2) + "\n")
    report["status"] = "PASS"
    exports = [cad / "middle-frame.FCStd", cad / "double-case-assembly.FCStd"]
    exports += sorted(p for p in out.iterdir() if p.suffix in (".step", ".stl", ".3mf"))
    report["export_sha256"] = {str(p.relative_to(CASE)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in exports}
    text = json.dumps(report, indent=2) + "\n"
    (out / "verification.json").write_text(text)
    # Write completion marker LAST: the wrapper rejects FreeCAD's sometimes-zero
    # return code after an exception, and cannot accept an old report as success.
    (research / "build-report.json").write_text(text)
    print("MIDDLE_FRAME_BUILD_PASS", flush=True)


# FreeCADCmd imports the requested script under its file stem.
if __name__ == "__main__" or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
